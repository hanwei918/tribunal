"""The append-only, tamper-evident event log a run leaves behind.

Every run writes ``runs/<run directory>/events.jsonl``: one JSON object per
line, one line per event, appended and never rewritten. The file is the record
a reader can follow a single case through from the invocation that issued it to
the grade it received, in the order the events happened, without opening the
transcript, the cache entry or the metadata file.

What makes it worth having beside the transcript
------------------------------------------------
The transcript is the record of the agent calls and it is a hard deliverable.
It is also *per case* and it is rewritten whenever a case is re-run, so it
cannot answer "what did this invocation do, and in what order" once a second
invocation has touched the directory. The event log answers exactly that, and
it answers it cumulatively: a case re-run under ``--force`` appends its new
history rather than replacing the old one.

The append rule is absolute. Nothing in this module truncates, rewrites or
reorders the file, and ``--force`` does not change that: forcing a re-run
skips the cache, it does not clear the log. A reader can therefore treat every
line as a fact that was true when it was written.

Tamper evidence
---------------
Each line carries ``prev``, the SHA-256 of the previous line's canonical body,
and ``hash``, the SHA-256 of its own canonical body. ``prev`` chains the lines
together, so a line that is deleted, inserted or reordered breaks the chain at
the first line that no longer agrees with its predecessor. ``hash`` catches an
edit to the line itself, and it catches it *at that line* rather than at the
line after it, which is what makes :func:`verify_chain` able to name the first
line that was touched. A tamperer who edits a line and recomputes its ``hash``
is still caught, one line later, by the next line's ``prev``.

The chain is not a signature. It cannot prove the file was never rewritten by
someone who rewrote all of it; it can only prove that the file a reader holds
is the file the run wrote, which is the question worth being able to answer.

What is deliberately absent
---------------------------
No line carries a credential, a request header or a raw prompt. A line carries
digests, roles, token counts, durations, reason codes and the ruling -- the
things a reader needs to follow a case -- and never the material an API key
travels in. ``tests/test_events.py`` scans a produced log for the house
credential patterns with a positive control, the same way ``test_llm.py`` and
``test_transcript.py`` scan their own artifacts.

Determinism
-----------
Serialisation goes through :func:`tribunal.money.dumps_canonical`, the settings
this package uses everywhere: ``ensure_ascii=False``, ``sort_keys=True``,
``separators=(",", ":")``, with a ``Decimal`` written as the number literal it
was read as. The digest is taken over those exact bytes, so re-serialising a
line that parsed back to the same object reproduces the same digest -- which is
what lets the verifier recompute a hash from a line it read off disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import money

# The file every run appends to, under its own run directory.
EVENTS_FILE = "events.jsonl"

# The value ``prev`` carries on the first line of a log. It is a value no
# SHA-256 digest can take, so a first line that was moved to a later position
# cannot pass itself off as the beginning of the chain.
GENESIS = "0" * 64

# The reserved keys every line carries. A payload that tried to set one of
# these would shadow the field the chain is built on, so it is refused rather
# than allowed to overwrite it.
RESERVED_FIELDS = (
    "seq",
    "ts",
    "event",
    "invocation",
    "case",
    "commit",
    "prompts",
    "prev",
    "hash",
)

# The events a run writes. Named as constants so a reader of the log and the
# tests that read it cannot drift apart over a string.
EVENT_INVOCATION_START = "invocation_start"
EVENT_INVOCATION_END = "invocation_end"
EVENT_CASE_START = "case_start"
EVENT_AGENT_CALL = "agent_call"
EVENT_REFEREE_DECISION = "referee_decision"
EVENT_JUDGE_DRAFT = "judge_draft"
EVENT_VOTE = "vote"
# The draft verifier's one call and the verdicts it returned, recorded beside
# the vote rather than inside it: the verifier is a separate question about the
# drafts and its outcome is a fact about the case in its own right.
EVENT_VERIFICATION = "verification"
# Which precedents the judge was shown for one case, recorded when the switch is
# on. It is a fact about what the judge was given, and it belongs beside the
# calls rather than inside the ruling: the ruling says what the judge decided,
# and this says one of the things it was reading.
EVENT_PRECEDENTS_SHOWN = "precedents_shown"
# The ``POL-GEN-08(1)`` scope gate. A flagged dispute is never adjudicated
# automatically, so the pipeline assembles the record and publishes an
# ``ESCALATE`` without asking any agent. It is a fact about the case in its own
# right -- the record of a call that was deliberately **not** made -- and it
# belongs beside the calls rather than inside the ruling.
EVENT_SCOPE_GATE = "scope_gate"
EVENT_RULING = "ruling"
EVENT_CASE_FAILED = "case_failed"
EVENT_GRADE = "grade"

EVENT_TYPES = (
    EVENT_INVOCATION_START,
    EVENT_INVOCATION_END,
    EVENT_CASE_START,
    EVENT_AGENT_CALL,
    EVENT_REFEREE_DECISION,
    EVENT_JUDGE_DRAFT,
    EVENT_VOTE,
    EVENT_VERIFICATION,
    EVENT_PRECEDENTS_SHOWN,
    EVENT_SCOPE_GATE,
    EVENT_RULING,
    EVENT_CASE_FAILED,
    EVENT_GRADE,
)


def _default_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(body: Mapping[str, Any]) -> str:
    """The canonical serialisation of one event body, without its ``hash``."""
    return money.dumps_canonical(dict(body))


def digest_of(body: Mapping[str, Any]) -> str:
    """The SHA-256 of a body's canonical serialisation."""
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainBreak:
    """The first line at which the chain stops agreeing with itself."""

    # 1-based, so it matches the line number a reader sees in an editor.
    line_number: int
    # ``content`` is a line whose own bytes were edited; ``chain`` is a line
    # whose ``prev`` no longer names its predecessor; ``malformed`` is a line
    # that is not a JSON object with the reserved fields.
    kind: str
    detail: str

    def describe(self) -> str:
        return "line {0}: {1} ({2})".format(self.line_number, self.kind, self.detail)


def read_lines(path: Path) -> List[str]:
    """Every non-empty line of the log, as text, in order.

    Blank lines are skipped rather than treated as corruption: a trailing
    newline at the end of a file is not an event, and neither is a stray blank
    line a writer never wrote.
    """
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    return [line for line in text.split("\n") if line.strip()]


def read_events(path: Path) -> List[Dict[str, Any]]:
    """Every event in the log, parsed, in the order it was written.

    A line that does not parse is left out rather than raising, because the
    reader that most needs the log is the one looking at a log that has been
    damaged. :func:`verify_chain` is what reports the damage.
    """
    events: List[Dict[str, Any]] = []
    for line in read_lines(path):
        try:
            event = json.loads(line, parse_float=Decimal)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def verify_chain(path: Path) -> Optional[ChainBreak]:
    """Check the whole chain and return the first break, or ``None``.

    The checks, in order, for each line:

    1. it parses as a JSON object carrying every reserved field;
    2. ``hash`` equals the SHA-256 of its own canonical body, so an edit to the
       line is reported **at that line**;
    3. ``prev`` equals the previous line's ``hash`` (``GENESIS`` for the first),
       so a deleted, inserted or reordered line is reported at the first line
       that no longer agrees.

    ``None`` means the chain is intact from the first line to the last.
    """
    expected_prev = GENESIS
    for number, line in enumerate(read_lines(path), start=1):
        try:
            event = json.loads(line, parse_float=Decimal)
        except (ValueError, TypeError):
            return ChainBreak(number, "malformed", "the line is not valid JSON")
        if not isinstance(event, dict):
            return ChainBreak(number, "malformed", "the line is not a JSON object")
        missing = [name for name in RESERVED_FIELDS if name not in event]
        if missing:
            return ChainBreak(
                number, "malformed", "missing field(s): {0}".format(", ".join(missing))
            )
        recorded = event.get("hash")
        body = {key: value for key, value in event.items() if key != "hash"}
        if digest_of(body) != recorded:
            return ChainBreak(
                number,
                "content",
                "the line's own hash does not match its content",
            )
        if event.get("prev") != expected_prev:
            return ChainBreak(
                number,
                "chain",
                "prev does not name the previous line",
            )
        expected_prev = recorded
    return None


def events_for_case(path: Path, case_no: int) -> List[Dict[str, Any]]:
    """Every event the log records for one case, in order."""
    return [event for event in read_events(path) if event.get("case") == case_no]


class EventLog:
    """One run directory's append-only event log.

    The log is shared by every worker thread a run uses, so ``record`` takes a
    lock around the read-modify-append: the chain is a sequence and two threads
    appending at once would produce two lines claiming the same ``prev``. The
    lock is held for the length of one line's write and nothing else.

    The context fields -- the invocation id, the git commit and the prompts
    digest -- are carried on every line rather than written once at the top,
    because a log that only says at its head which invocation wrote it cannot
    answer the question once a second invocation has appended to it. Every line
    stands on its own.
    """

    def __init__(
        self,
        path: Path,
        *,
        invocation_id: str,
        git_commit: Optional[str] = None,
        prompts_sha256: Optional[str] = None,
        now: Callable[[], str] = _default_timestamp,
    ) -> None:
        self.path = Path(path)
        self.invocation_id = invocation_id
        self.git_commit = git_commit
        self.prompts_sha256 = prompts_sha256
        self._now = now
        self._lock = threading.Lock()
        self._last_hash, self._last_seq = self._tail()

    def _tail(self) -> Tuple[str, int]:
        """The last line's ``hash`` and ``seq``, or the genesis values.

        Read off disk rather than kept only in memory so that a second
        invocation writing into the same run directory continues the chain
        instead of restarting it. An unreadable tail restarts from genesis,
        which is the honest answer: this process cannot claim to know what came
        before a line it could not read, and the verifier will report the break
        where it is.
        """
        lines = read_lines(self.path)
        if not lines:
            return GENESIS, -1
        try:
            event = json.loads(lines[-1], parse_float=Decimal)
        except (ValueError, TypeError):
            return GENESIS, -1
        if not isinstance(event, dict):
            return GENESIS, -1
        recorded = event.get("hash")
        seq = event.get("seq")
        if not isinstance(recorded, str) or not isinstance(seq, int):
            return GENESIS, -1
        return recorded, seq

    def record(
        self, event: str, *, case_no: Optional[int] = None, **payload: Any
    ) -> Dict[str, Any]:
        """Append one event and return the body that was written.

        The body returned is the one without ``hash``, which is the object the
        line's digest was taken over -- so a caller that wants to check a line
        can recompute :func:`digest_of` on what it was handed.
        """
        clash = sorted(set(payload) & set(RESERVED_FIELDS))
        if clash:
            raise ValueError(
                "an event payload may not set the reserved field(s): {0}".format(
                    ", ".join(clash)
                )
            )
        if not isinstance(event, str) or not event:
            raise ValueError("an event needs a non-empty name")
        with self._lock:
            seq = self._last_seq + 1
            body: Dict[str, Any] = {
                "seq": seq,
                "ts": self._now(),
                "event": event,
                "invocation": self.invocation_id,
                "case": case_no,
                "commit": self.git_commit,
                "prompts": self.prompts_sha256,
                "prev": self._last_hash,
            }
            body.update(payload)
            text = canonical(body)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            line = canonical(dict(body, hash=digest))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # ``a`` and nothing else: the file is only ever appended to, and a
            # write that raced another would be serialised by the lock above.
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._last_hash = digest
            self._last_seq = seq
            return body


def new_invocation_id(now: Callable[[], str] = _default_timestamp) -> str:
    """A fresh id for one invocation.

    Built from the UTC instant and the process id so two invocations started in
    the same second -- which a replay into its own directory makes easy -- are
    still told apart, and so the id sorts in the order the invocations ran.
    """
    stamp = now().replace(":", "").replace("-", "").replace("+00:00", "Z")
    return "{0}-{1}".format(stamp, os.getpid())


def summarise(event: Mapping[str, Any]) -> str:
    """One line of a case's history, for the ``--case`` printer.

    Deliberately terse: the point of the printer is that a reader can follow a
    case's whole history on one screen, and a printer that pasted each event's
    payload in full would defeat that. ``--json`` prints the payloads.
    """
    parts: List[str] = [str(event.get("ts", ""))]
    parts.append("{0:<20}".format(str(event.get("event", ""))))
    case_no = event.get("case")
    parts.append("case {0}".format(case_no) if case_no is not None else "case -")
    for key in _SUMMARY_KEYS:
        if key in event:
            parts.append("{0}={1}".format(key, _render(event[key])))
    return "  ".join(parts)


# The payload fields the one-line summary shows, in the order it shows them.
# Every event carries at least one of these; an event with none of them still
# prints its timestamp, name and case number.
_SUMMARY_KEYS = (
    "role",
    "parse_outcome",
    "seconds",
    "total_tokens",
    "side",
    "status",
    "cached",
    "reason_code",
    "draft",
    "kind",
    "proposal",
    "abstention",
    "checks",
    "votes",
    "agreement",
    "outcome",
    "called",
    "statements",
    "supported",
    "contradicted",
    "material",
    "not_material",
    "not_in_evidence",
    "precedents",
    "ruling",
    "matched",
    "failure_kind",
    "stop_reason",
)


def _render(value: Any) -> str:
    if isinstance(value, str):
        return value if len(value) <= 60 else value[:57] + "..."
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render(item) for item in value) + "]"
    if isinstance(value, Mapping):
        return "{" + ", ".join(
            "{0}:{1}".format(key, _render(item)) for key, item in value.items()
        ) + "}"
    return str(value)


def summarise_all(path: Path, case_no: int) -> str:
    """A case's full history, one event per line, in the order it happened."""
    events = events_for_case(path, case_no)
    if not events:
        return "no events recorded for case {0} in {1}".format(case_no, path)
    return "\n".join(summarise(event) for event in events)


# The timeline's columns, in the order it prints them. Every event carries as
# many of them as apply, and a column an event has nothing to say about is a
# dash rather than a zero: a referee decision that spends no tokens and a ruling
# with no parse outcome are different from a call that cost nothing.
_TIMELINE_COLUMNS = (
    ("time", 32),
    ("event", 18),
    ("role or draft", 18),
    ("status", 9),
    ("tokens", 9),
    ("seconds", 9),
    ("parse", 0),
)


def _timeline_row(event: Mapping[str, Any]) -> str:
    """One event's line: the six columns, a dash where one does not apply."""
    who = event.get("role")
    if who is None and event.get("draft") is not None:
        who = "draft {0}".format(event["draft"])
    seconds = event.get("seconds")
    values = (
        str(event.get("ts", "")),
        str(event.get("event", "")),
        "-" if who is None else str(who),
        "-" if event.get("status") is None else str(event["status"]),
        "-" if event.get("total_tokens") is None else str(event["total_tokens"]),
        "-" if seconds is None else "{0:.3f}".format(float(seconds)),
        str(event.get("parse_outcome") or "-"),
    )
    cells = []
    for (name, width), value in zip(_TIMELINE_COLUMNS, values):
        cells.append(value if width == 0 else "{0:<{1}}".format(value, width))
    return "  ".join(cells).rstrip()


def _timeline_tail(events: Sequence[Mapping[str, Any]]) -> List[str]:
    """The two lines a case's timeline ends with: the vote, and the ruling.

    They are what the calls were for, and neither is an event of the same shape
    as a call, so they are rendered as sentences rather than as rows. A case that
    produced neither says so instead of printing a row of dashes.
    """
    last_vote = None
    last_ruling = None
    for event in events:
        if event.get("event") == EVENT_VOTE:
            last_vote = event
        elif event.get("event") == EVENT_RULING:
            last_ruling = event
    if last_vote is None:
        vote_line = "vote:    none -- this case produced no vote"
    else:
        vote_line = (
            "vote:    outcome {0}, {1} of {2} drafts valid, agreement {3}, "
            "threshold {4}".format(
                last_vote.get("outcome"),
                last_vote.get("valid"),
                last_vote.get("votes"),
                last_vote.get("agreement"),
                last_vote.get("threshold"),
            )
        )
    if last_ruling is None:
        ruling_line = "ruling:  none -- this case produced no ruling"
    else:
        inner = last_ruling.get("ruling")
        inner = inner if isinstance(inner, Mapping) else {}
        ruling_line = (
            "ruling:  {0}, amount_sgd {1}, driver_compensation_sgd {2}, "
            "referrals {3}".format(
                inner.get("ruling"),
                inner.get("amount_sgd"),
                inner.get("driver_compensation_sgd"),
                inner.get("referrals"),
            )
        )
    return [vote_line, ruling_line]


def timeline(path: Path, case_no: int) -> str:
    """One case's history as a timeline, ending with the vote and the ruling.

    The columns are the ones a reader following a case needs and cannot get from
    one line of prose: when each call happened, which agent or which draft made
    it, the status the provider returned, what it cost in tokens, how long it
    took and how its answer parsed. The last two lines are the vote and the
    ruling, which are what the calls were for.

    Reads only; writes nothing.
    """
    events = events_for_case(path, case_no)
    if not events:
        return "no events recorded for case {0} in {1}".format(case_no, path)
    lines = [
        "case {0} — {1} event(s) in {2}".format(case_no, len(events), path),
        "  ".join(
            name if width == 0 else "{0:<{1}}".format(name, width)
            for name, width in _TIMELINE_COLUMNS
        ).rstrip(),
    ]
    lines.extend(_timeline_row(event) for event in events)
    lines.append("")
    lines.extend(_timeline_tail(events))
    return "\n".join(lines)


def sequence_of(path: Path) -> Sequence[int]:
    """The ``seq`` values in the log, in order. Used by the tests."""
    return [event.get("seq") for event in read_events(path)]

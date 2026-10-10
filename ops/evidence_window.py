"""The evidence window: ``POL-GEN-06(4)``'s ``REQUEST_EVIDENCE``, made executable.

``POL-GEN-06(4)`` lets a human reviewer choose ``REQUEST_EVIDENCE``, "naming the
record-type items required". Nothing in the pipeline executes that choice: the
reviewer names the missing records and waits. This module is the wait, and it
opens **one window to both parties at once**: until the window closes each party
may upload a record, see the other's uploads and answer; after it closes the
reviewer decides on what arrived.

**The clock does not stop for missing evidence.** That is operations rule
``OPS-EW-01``, written into ``ops/config.json`` and disclosed in the README. It
is not a clause of the frozen policy, and every output says so. Three instants
fix the window, and only the first is the team's own:

* the reviewer must open the window within 24 hours of entry -- the figure
  ``POL-GEN-06(2)`` states as "A review is decided within 24 hours of entry";
* the window closes ``close_hours_after_filing`` after filing, which is the
  team's own figure in ``ops/config.json`` and is **not** policy; and
* the decision is due within the first-review limit ``POL-GEN-06(2)`` states,
  "a first-instance case is closed within 48 hours of filing", which leaves the
  reviewer the hours between the close and that deadline.

Both policy figures are matched **word for word** against the loaded clause and
refused when the sentence has moved, which is the rule the whole layer obeys.

**Four sub-commands.** ``open`` is the reviewer's ``REQUEST_EVIDENCE`` and
refuses an item that is not one of the six record kinds of ``POL-GEN-04(b)``, a
case that is neither escalated nor held under ``POL-GEN-05``, a second window on
the same case, and an opening more than the 24 hours after filing. ``submit``
takes one party's record, refuses a ``STATEMENT`` (``POL-GEN-06(5)``), refuses
after the close, and stores the file by its SHA-256 under the store's ``files/``.
``status`` prints the window, what each party has filed, the time left and what
is still missing. ``close`` refuses before the close instant; if the named
evidence arrived it says to decide on it, and if it did not it gives the default
outcome ``POL-GEN-07(1)(2)`` requires and the exact ``python3 -m ops.review``
command for it. It does **not** write the precedent store itself.

**What it writes, and where.** Only under the ``--store`` the caller names, and
that path is refused inside ``runs/``, ``data/``, ``policy/``, ``prompts/``,
``tribunal/``, ``eval/answers/`` or either sealed root, through
:func:`ops.refuse_a_forbidden_destination`. The store holds one append-only
``jsonl`` per case, each line carrying the previous line's hash, and reading
refuses a broken chain. Uploaded files are written by content address under
``<store>/files/``.

**No model call, and no answer key.** The window is built from the run's own
record and the public case; nothing here reads an answer, and no wall clock is
read without ``--now``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from ops import (
    OpsError,
    OpsWriteError,
    read_json_document,
    refuse_a_forbidden_destination,
)
from ops import appeal, escalation
from tribunal import loader, money

# The config this module reads when it is not given one. It sits beside the
# module, so the numbers a window is opened against travel with the code.
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# The operations rule the window's clock is, and the two clauses it rests on.
OPS_RULE = "OPS-EW-01"
CLAUSE_REVIEW = "POL-GEN-06"
CLAUSE_RESIDUAL = "POL-GEN-07"
CLAUSE_EXECUTION = appeal.CLAUSE_EXECUTION

# The sentence every output of this module carries, so a reader is never left to
# think the window's clock is a clause of the frozen policy. It is stated once,
# here, and printed by every renderer.
OPS_RULE_NOTE = (
    "{0}: the clock does not stop for missing evidence; this is an operations "
    "rule, not frozen policy.".format(OPS_RULE)
)

# The four sub-commands, in the order the task names them.
SUBCOMMANDS: Tuple[str, ...] = ("open", "submit", "status", "close")

# The two parties, as ``--party`` spells them.
PARTIES: Tuple[str, ...] = ("rider", "driver")
PARTY_RIDER = "rider"

# The six record kinds a window may name. They are ``ops.appeal``'s own list --
# the kinds ``POL-GEN-04(b)`` lists -- read rather than retyped, so a kind added
# there is one a window can name without this module being edited.
EVIDENCE_ITEMS: Tuple[str, ...] = tuple(appeal.RECORD_EVIDENCE_KINDS)

# The one kind ``POL-GEN-06(5)`` bars from a window: a statement made after
# filing is not evidence.
STATEMENT_KIND = "STATEMENT"

# The note is a party's argument and not a record. It travels marked, and it is
# capped so a window cannot become a place to file a brief.
NOTE_MAX_CHARS = 280
NOTE_LABEL = "argument, not evidence"

# The two events the store's chain records.
EVENT_OPEN = "open"
EVENT_SUBMIT = "submit"

# The config block the window's own figure lives in, and the key itself.
WINDOW_CONFIG_KEY = "evidence_window"
CLOSE_HOURS_KEY = "close_hours_after_filing"

# The store directory a caller may create at the repository root. It is
# gitignored; the module never assumes it and always writes where it is told.
DEFAULT_STORE_NAME = "evidence-windows"

# The three policy sentences the window depends on, matched as the clauses state
# them. A sentence that has moved is a refusal rather than a default.
REQUEST_EVIDENCE_SENTENCE = "REQUEST_EVIDENCE, naming the record-type items required"
BURDEN_SENTENCE = (
    "The party who asserts that money is owed - a fee, a charge, a refund, a "
    "compensation - carries the burden of proving the facts that make it owed."
)
CHARGE_DEFAULT_SENTENCE = (
    "A charge is the exception and no charge is the default: where the evidence "
    "does not establish the condition for a charge, the amount is returned to the "
    "party who paid it, not left with the party who collected it."
)
OPEN_LIMIT_RE = re.compile(r"A review is decided within (?P<hours>\d+) hours of entry")
CLOSE_LIMIT_RE = re.compile(
    r"a first-instance case is closed within (?P<hours>\d+) hours of filing"
)

# The ruling values the default outcomes and the hold are read against. They are
# values of the ruling vocabulary and not policy numbers, so they are named here.
ESCALATE = "ESCALATE"
FULL_REFUND = "FULL_REFUND"
NO_ACTION = "NO_ACTION"

# The two categories the pipeline adjudicates, as a case's own dispute names
# them. The default outcome is stated per category and per filing party.
CATEGORY_NO_SHOW = "NO_SHOW_CHARGE"
CATEGORY_ROUTE_DEVIATION = "ROUTE_DEVIATION"
RIDER = "RIDER"

# The fare line a no-show fee disputed by the rider is refunded from.
TOTAL_CHARGED_LINE = "total_charged"

# The missing artifact status the residual principles are read against.
MISSING = "MISSING"


class EvidenceWindowError(OpsError):
    """A window could not be opened, written or read."""


# --------------------------------------------------------------------------
# The config, and the two policy figures
# --------------------------------------------------------------------------
def read_close_hours(path: Optional[Path] = None) -> Decimal:
    """The window's own close figure, from ``ops/config.json``.

    It is the team's number and not the policy's, and it is **required**: a
    window that fell back to a figure nobody wrote down would close on a
    deadline nobody chose, which is the failure the layer's thresholds exist to
    prevent. ``OPS-EW-01`` is the operations rule the figure belongs to.
    """
    document = read_json_document(
        CONFIG_PATH if path is None else Path(path), EvidenceWindowError
    )
    if not isinstance(document, Mapping):
        raise EvidenceWindowError("the config must be a JSON object")
    block = document.get(WINDOW_CONFIG_KEY)
    if not isinstance(block, Mapping):
        raise EvidenceWindowError(
            "the config must state {0} as an object carrying {1} and the "
            "{2} note".format(WINDOW_CONFIG_KEY, CLOSE_HOURS_KEY, OPS_RULE)
        )
    raw = block.get(CLOSE_HOURS_KEY)
    if raw is None or isinstance(raw, bool):
        raise EvidenceWindowError(
            "the config states no {0}.{1}".format(WINDOW_CONFIG_KEY, CLOSE_HOURS_KEY)
        )
    try:
        value = Decimal(str(raw))
    except Exception as exc:  # pragma: no cover - a malformed config
        raise EvidenceWindowError(
            "the config's {0}.{1} is not a number: {2!r}".format(
                WINDOW_CONFIG_KEY, CLOSE_HOURS_KEY, raw
            )
        ) from exc
    if value <= 0:
        raise EvidenceWindowError(
            "the config's {0}.{1} is {2}; the window must close after it "
            "opens".format(WINDOW_CONFIG_KEY, CLOSE_HOURS_KEY, value)
        )
    return value


def _rule_text(clause_id: str, policies: Mapping[str, Any]) -> str:
    """One clause's rule text, refused when the loaded policy carries none."""
    try:
        return appeal.clause_rule_text(clause_id, policies)
    except appeal.AppealError as exc:
        raise EvidenceWindowError(str(exc)) from exc


def read_window_limits(policies: Mapping[str, Any]) -> Tuple[int, int]:
    """``(open_limit_hours, close_limit_hours)``, from ``POL-GEN-06(2)``.

    Both are read out of the clause's own sentence and refused when it has
    moved. The sentence that licenses ``REQUEST_EVIDENCE`` at all is matched in
    the same clause, so a window cannot be opened against a clause that no
    longer names the decision.
    """
    text = _rule_text(CLAUSE_REVIEW, policies)
    if REQUEST_EVIDENCE_SENTENCE not in text:
        raise EvidenceWindowError(
            "{0} states no {1!r}, so the decision a window executes has moved or "
            "gone and no window can be opened".format(CLAUSE_REVIEW, REQUEST_EVIDENCE_SENTENCE)
        )
    opened = OPEN_LIMIT_RE.search(text)
    closed = CLOSE_LIMIT_RE.search(text)
    if opened is None or closed is None:
        raise EvidenceWindowError(
            "{0} states no sentence this code can read for the entry limit or the "
            "first-review limit, so its text has moved and the hours can no longer "
            "be taken from it".format(CLAUSE_REVIEW)
        )
    return int(opened.group("hours")), int(closed.group("hours"))


def read_residual_sentences(policies: Mapping[str, Any]) -> Tuple[str, str]:
    """The two ``POL-GEN-07`` principles a default outcome rests on.

    Both are matched as the clause states them, so a moved sentence is a refusal
    rather than a rule read out of a clause nobody reviewed.
    """
    text = _rule_text(CLAUSE_RESIDUAL, policies)
    for sentence in (BURDEN_SENTENCE, CHARGE_DEFAULT_SENTENCE):
        if sentence not in text:
            raise EvidenceWindowError(
                "{0} no longer states {1!r}, so a default outcome can no longer "
                "rest on it".format(CLAUSE_RESIDUAL, sentence[:40] + "...")
            )
    return BURDEN_SENTENCE, CHARGE_DEFAULT_SENTENCE


def _execution_threshold(policies: Mapping[str, Any]) -> Optional[Decimal]:
    """``POL-GEN-05``'s threshold, or ``None`` when the policy carries none.

    Versions 1 and 2 carry no ``POL-GEN-05``, so a ruling cannot be held under
    it; where the clause **is** there its sentence is read with
    :func:`ops.appeal.read_execution_threshold`, so a moved sentence is a
    refusal rather than a figure nobody reviewed.
    """
    if CLAUSE_EXECUTION not in appeal.policy_clauses(policies):
        return None
    try:
        _sentence, threshold = appeal.read_execution_threshold(policies)
    except appeal.AppealError as exc:
        raise EvidenceWindowError(str(exc)) from exc
    return threshold


# --------------------------------------------------------------------------
# The store: one hash-chained jsonl per case
# --------------------------------------------------------------------------
def store_path(store: Path) -> Path:
    """The store directory, refused when it is a tree this layer does not write.

    The check is :func:`ops.refuse_a_forbidden_destination`, the layer's one
    guard, so a store inside ``runs/``, a sealed root or a headline directory is
    refused before anything is created.
    """
    try:
        return refuse_a_forbidden_destination(Path(store))
    except OpsWriteError as exc:
        raise EvidenceWindowError(str(exc)) from exc


def window_path(store: Path, case_no: int) -> Path:
    """The chain file for one case."""
    return Path(store) / "window-{0:05d}.jsonl".format(case_no)


def files_dir(store: Path) -> Path:
    """Where a submitted file is stored, by content address."""
    return Path(store) / "files"


def _canonical(record: Mapping[str, Any]) -> str:
    """One store line's bytes, canonically: sorted keys, Decimal literals."""
    return money.dumps_canonical(dict(record))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_lines(store: Path, case_no: int) -> List[Tuple[Dict[str, Any], str]]:
    """Every line of a case's chain as ``(record, text)``, or ``[]`` for none.

    The chain is verified as it is read: each line must carry the SHA-256 of the
    line before it, and the first must carry ``None``. A line that does not is a
    refusal, because a store whose history has been edited is not a record of
    what a reviewer decided.
    """
    path = window_path(store, case_no)
    if not path.is_file():
        return []
    found: List[Tuple[Dict[str, Any], str]] = []
    previous: Optional[str] = None
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line, parse_float=Decimal)
        except ValueError as exc:
            raise EvidenceWindowError(
                "the window store for case {0} has a line that is not JSON at line "
                "{1}".format(case_no, index)
            ) from exc
        if not isinstance(record, Mapping):
            raise EvidenceWindowError(
                "the window store for case {0} has a line that is not an object at "
                "line {1}".format(case_no, index)
            )
        if record.get("prev_sha256") != previous:
            raise EvidenceWindowError(
                "the window store for case {0} is a broken chain: line {1} does not "
                "carry the hash of the line before it, so the record has been "
                "edited".format(case_no, index)
            )
        previous = _sha256_text(line)
        found.append((dict(record), line))
    return found


def read_events(store: Path, case_no: int) -> List[Dict[str, Any]]:
    """Every event of a case's window, the chain verified, or ``[]`` for none."""
    return [record for record, _text in read_lines(store, case_no)]


def append_event(store: Path, case_no: int, record: Mapping[str, Any]) -> Dict[str, Any]:
    """Append one event, carrying the previous line's hash.

    The chain is verified first, so an event is never appended on top of a store
    that has been edited.
    """
    lines = read_lines(store, case_no)
    previous = _sha256_text(lines[-1][1]) if lines else None
    entry = dict(record)
    entry["prev_sha256"] = previous
    text = _canonical(entry)
    path = window_path(store, case_no)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")
    return entry


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
class Window(NamedTuple):
    """One case's window, as the store's open event records it."""

    case_no: int
    set_name: str
    category: str
    filed_by: str
    filed_at: datetime
    opened_at: datetime
    opened_by: str
    items: Tuple[str, ...]
    close_at: datetime
    decide_at: datetime


def _parse_instant(text: Any, where: str) -> datetime:
    if not isinstance(text, str) or not text:
        raise EvidenceWindowError("{0} is not an ISO 8601 instant: {1!r}".format(where, text))
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceWindowError(
            "{0} is not an ISO 8601 instant: {1!r}".format(where, text)
        ) from exc


def _require_zone(moment: datetime, where: str) -> datetime:
    if moment.tzinfo is None:
        raise EvidenceWindowError(
            "{0} must carry a UTC offset, so it names an instant rather than a "
            "wall time".format(where)
        )
    return moment


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def window_state(store: Path, case_no: int) -> Optional[Window]:
    """The open window for a case, or ``None`` when the store holds none."""
    events = read_events(store, case_no)
    if not events:
        return None
    opened = events[0]
    if opened.get("event") != EVENT_OPEN:
        raise EvidenceWindowError(
            "the window store for case {0} does not begin with an open event".format(case_no)
        )
    items = opened.get("items")
    return Window(
        case_no=case_no,
        set_name=str(opened.get("set") or ""),
        category=str(opened.get("category") or ""),
        filed_by=str(opened.get("filed_by") or ""),
        filed_at=_parse_instant(opened.get("filed_at"), "the store's filed_at"),
        opened_at=_parse_instant(opened.get("opened_at"), "the store's opened_at"),
        opened_by=str(opened.get("opened_by") or ""),
        items=tuple(str(item) for item in (items or [])),
        close_at=_parse_instant(opened.get("close_at"), "the store's close_at"),
        decide_at=_parse_instant(opened.get("decide_at"), "the store's decide_at"),
    )


def _submissions(events: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return [event for event in events if event.get("event") == EVENT_SUBMIT]


def _filed_kinds(events: Sequence[Mapping[str, Any]]) -> Tuple[str, ...]:
    found: List[str] = []
    for event in _submissions(events):
        kind = str(event.get("kind") or "")
        if kind and kind not in found:
            found.append(kind)
    return tuple(found)


def missing_items(window: Window, events: Sequence[Mapping[str, Any]]) -> Tuple[str, ...]:
    """The items the window named that no party has filed."""
    filed = _filed_kinds(events)
    return tuple(item for item in window.items if item not in filed)


def _may_open(packet: Mapping[str, Any], policies: Mapping[str, Any]) -> bool:
    """Whether a window may be opened: an escalated case, or a held amount."""
    ruling = packet["ruling"].get("ruling")
    if ruling == ESCALATE:
        return True
    threshold = _execution_threshold(policies)
    if threshold is None:
        return False
    effect = appeal.monetary_effect(
        ruling, packet["ruling"].get("amount_sgd"), packet["ruling"].get("driver_compensation_sgd")
    )
    return effect > threshold


def _packet_and_policies(run_dir: Path, case_no: int):
    """The case's packet and its loaded policy, refused as one thing."""
    try:
        packet = escalation.build_packet(Path(run_dir), case_no, any_ruling=True)
    except escalation.EscalationError as exc:
        raise EvidenceWindowError(str(exc)) from exc
    category = packet["case"].get("category")
    try:
        policies = loader.load_policies(category, packet.get("policy_version"))
    except loader.LoaderError as exc:
        raise EvidenceWindowError(
            "the policy for case {0} cannot be loaded: {1}".format(case_no, exc)
        ) from exc
    return packet, policies


def _items_from(raw: Any) -> Tuple[str, ...]:
    """The record kinds named: one comma-separated string, or a sequence of them."""
    if raw is None:
        raise EvidenceWindowError("--items names no record kind")
    pieces = raw.split(",") if isinstance(raw, str) else [str(item) for item in raw]
    items: List[str] = []
    for piece in pieces:
        name = str(piece).strip()
        if not name:
            continue
        if name not in items:
            items.append(name)
    if not items:
        raise EvidenceWindowError("--items names no record kind")
    unknown = [name for name in items if name not in EVIDENCE_ITEMS]
    if unknown:
        raise EvidenceWindowError(
            "{0} is not one of the record kinds POL-GEN-04(b) lists: {1}".format(
                ", ".join(unknown), ", ".join(EVIDENCE_ITEMS)
            )
        )
    return tuple(items)


# --------------------------------------------------------------------------
# open
# --------------------------------------------------------------------------
def open_window(
    store: Path,
    run_dir: Path,
    case_no: int,
    items: Sequence[str],
    opened_by: str,
    now: datetime,
    config_path: Optional[Path] = None,
) -> str:
    """Open one window for both parties, and return what it prints."""
    directory = store_path(store)
    _require_zone(now, "--now")
    if not str(opened_by).strip():
        raise EvidenceWindowError("--opened-by names no reviewer")
    named = _items_from(items)
    if read_events(directory, case_no):
        raise EvidenceWindowError(
            "case {0} already has an evidence window in this store; a case has one "
            "window".format(case_no)
        )

    packet, policies = _packet_and_policies(run_dir, case_no)
    if not _may_open(packet, policies):
        raise EvidenceWindowError(
            "case {0} is neither escalated nor held under POL-GEN-05, so it is not "
            "in front of a human reviewer and there is no window to open".format(case_no)
        )
    open_hours, close_limit_hours = read_window_limits(policies)
    case = packet["case"]
    filed_at = _require_zone(
        _parse_instant(case.get("filed_at"), "the case's filed_at"), "the case's filed_at"
    )
    if now > filed_at + timedelta(hours=open_hours):
        raise EvidenceWindowError(
            "the window must be opened within {0} hours of filing, and {1} is past "
            "{2}".format(
                open_hours,
                _iso(now),
                _iso(filed_at + timedelta(hours=open_hours)),
            )
        )

    close_at = filed_at + timedelta(hours=float(read_close_hours(config_path)))
    decide_at = filed_at + timedelta(hours=close_limit_hours)
    entry = append_event(
        directory,
        case_no,
        {
            "event": EVENT_OPEN,
            "case_no": case_no,
            "set": packet.get("set"),
            "category": case.get("category"),
            "filed_by": case.get("filed_by"),
            "filed_at": case.get("filed_at"),
            "opened_at": _iso(now),
            "opened_by": str(opened_by),
            "items": list(named),
            "close_at": _iso(close_at),
            "decide_at": _iso(decide_at),
            "ops_rule": OPS_RULE,
        },
    )
    return render_open(entry, directory)


def render_open(entry: Mapping[str, Any], store: Path) -> str:
    lines = [
        "evidence window opened for case {0} ({1}, {2})".format(
            entry["case_no"], entry["set"], entry["category"]
        ),
        "  store       {0}".format(store),
        "  opened at   {0} by {1}".format(entry["opened_at"], entry["opened_by"]),
        "  items       {0}".format(", ".join(entry["items"])),
        "  closes      {0}".format(entry["close_at"]),
        "  decide by   {0} (POL-GEN-06(2): a first-instance case is closed within "
        "the first-review limit of filing)".format(entry["decide_at"]),
        "  {0}".format(OPS_RULE_NOTE),
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# submit
# --------------------------------------------------------------------------
def submit(
    store: Path,
    case_no: int,
    party: str,
    kind: str,
    source: Path,
    note: str,
    now: datetime,
) -> str:
    """File one party's record into an open window, and return what it prints."""
    directory = store_path(store)
    _require_zone(now, "--now")
    events = read_events(directory, case_no)
    window = window_state(directory, case_no)
    if window is None:
        raise EvidenceWindowError(
            "case {0} has no evidence window in this store; open one first".format(case_no)
        )
    if party not in PARTIES:
        raise EvidenceWindowError(
            "--party is {0!r}; a window has two parties: {1}".format(party, ", ".join(PARTIES))
        )
    if kind == STATEMENT_KIND:
        raise EvidenceWindowError(
            "a party statement may not be filed: POL-GEN-06(5) refuses a statement "
            "made after filing as evidence"
        )
    if kind not in EVIDENCE_ITEMS:
        raise EvidenceWindowError(
            "{0!r} is not one of the record kinds POL-GEN-04(b) lists: {1}".format(
                kind, ", ".join(EVIDENCE_ITEMS)
            )
        )
    if now > window.close_at:
        raise EvidenceWindowError(
            "the window for case {0} closed at {1}, and {2} is after it".format(
                case_no, _iso(window.close_at), _iso(now)
            )
        )
    text = str(note or "").strip()
    if len(text) > NOTE_MAX_CHARS:
        raise EvidenceWindowError(
            "--note is {0} characters; a note is capped at {1}".format(
                len(text), NOTE_MAX_CHARS
            )
        )
    path = Path(source)
    if not path.is_file():
        raise EvidenceWindowError("no file to file at {0}".format(path))
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    files = files_dir(directory)
    files.mkdir(parents=True, exist_ok=True)
    (files / digest).write_bytes(data)

    entry = append_event(
        directory,
        case_no,
        {
            "event": EVENT_SUBMIT,
            "case_no": case_no,
            "ts": _iso(now),
            "party": party,
            "kind": kind,
            "sha256": digest,
            "bytes": len(data),
            "note": text or None,
            "note_label": NOTE_LABEL if text else None,
            "ops_rule": OPS_RULE,
        },
    )
    return render_submit(entry, directory)


def render_submit(entry: Mapping[str, Any], store: Path) -> str:
    lines = [
        "{0} filed {1} for case {2}".format(entry["party"], entry["kind"], entry["case_no"]),
        "  at          {0}".format(entry["ts"]),
        "  stored as   {0}".format(files_dir(store) / entry["sha256"]),
        "  bytes       {0}".format(entry["bytes"]),
    ]
    if entry.get("note"):
        lines.append(
            "  note        {0} ({1})".format(entry["note"], entry.get("note_label") or NOTE_LABEL)
        )
    lines.append("  {0}".format(OPS_RULE_NOTE))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------
def _duration(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    if total <= 0:
        return "0m"
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [(days, "d"), (hours, "h"), (minutes, "m")]
    while len(parts) > 1 and parts[-1][0] == 0:
        parts.pop()
    while len(parts) > 1 and parts[0][0] == 0:
        parts.pop(0)
    return " ".join("{0}{1}".format(value, unit) for value, unit in parts)


def status(store: Path, case_no: int, now: datetime) -> str:
    """Print the window, what each party has filed, the time left and the gap."""
    directory = store_path(store)
    _require_zone(now, "--now")
    window = window_state(directory, case_no)
    if window is None:
        return "case {0} has no evidence window in {1}\n".format(case_no, directory)
    events = read_events(directory, case_no)
    filed = _filed_kinds(events)
    lines = [
        "evidence window for case {0} ({1}, {2})".format(
            window.case_no, window.set_name, window.category
        ),
        "  opened      {0} by {1}".format(_iso(window.opened_at), window.opened_by),
        "  items       {0}".format(", ".join(window.items)),
        "  closes      {0}".format(_iso(window.close_at)),
        "  decide by   {0}".format(_iso(window.decide_at)),
        "  filed:",
    ]
    for party in PARTIES:
        rows = [
            event
            for event in _submissions(events)
            if event.get("party") == party
        ]
        if not rows:
            lines.append("    {0:<8}-".format(party))
            continue
        for event in rows:
            note = event.get("note")
            lines.append(
                "    {0:<8}{1} {2}{3}".format(
                    party,
                    event.get("kind"),
                    event.get("sha256"),
                    "" if not note else '  ({0}: "{1}")'.format(
                        event.get("note_label") or NOTE_LABEL, note
                    ),
                )
            )
    missing = missing_items(window, events)
    lines.append("  still missing: {0}".format(", ".join(missing) or "nothing"))
    remaining = window.close_at - now
    lines.append(
        "  time left   {0}".format(
            _duration(remaining) if remaining.total_seconds() >= 0 else "the window is closed"
        )
    )
    lines.append("  {0}".format(OPS_RULE_NOTE))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# close
# --------------------------------------------------------------------------
def _fare_line(packet: Mapping[str, Any], name: str) -> Optional[Any]:
    for line in packet.get("fare_lines") or []:
        if line.get("line") == name:
            return line.get("value")
    return None


def default_outcome(packet: Mapping[str, Any]) -> Tuple[str, Optional[Any]]:
    """The outcome ``POL-GEN-07(1)(2)`` gives when the evidence did not arrive.

    A no-show fee disputed by the rider is refunded in full: the driver asserts
    the charge is owed and carries the burden, and where the evidence does not
    establish it the amount is returned to the party who paid it. A no-show fee
    disputed by the driver, and a route-deviation claim, take ``NO_ACTION``: the
    burden is the complainant's and the record does not carry it.
    """
    case = packet.get("case") or {}
    category = case.get("category")
    filed_by = case.get("filed_by")
    if category == CATEGORY_NO_SHOW:
        if filed_by == RIDER:
            total = _fare_line(packet, TOTAL_CHARGED_LINE)
            if total is None:
                raise EvidenceWindowError(
                    "case {0} carries no {1} line, so the amount to return cannot be "
                    "read".format(packet.get("case_no"), TOTAL_CHARGED_LINE)
                )
            return FULL_REFUND, total
        return NO_ACTION, None
    if category == CATEGORY_ROUTE_DEVIATION:
        return NO_ACTION, None
    raise EvidenceWindowError(
        "no default outcome is stated for category {0!r}, so this window cannot "
        "say what the missing evidence leaves".format(category)
    )


def first_missing_evidence_id(packet: Mapping[str, Any]) -> Optional[str]:
    """The case's first absent artifact, in the case's own evidence order."""
    for artifact in packet.get("admissibility") or []:
        if artifact.get("status") == MISSING and artifact.get("evidence_id"):
            return str(artifact["evidence_id"])
    return None


def default_reason(
    window: Window,
    missing: Sequence[str],
    evidence_id: Optional[str],
    ruling: str,
    amount: Optional[Any],
) -> str:
    """The reason the default outcome's closure carries.

    It names the evidence id the case lacks and cites ``POL-GEN-07``, which is
    what ``POL-GEN-06(6)`` requires of a decision where no clause applies.
    """
    absent = evidence_id or "the record the window named"
    money_text = "" if amount is None else " and {0} is returned to the party who paid it".format(amount)
    return (
        "The window named {0} and it closed with {1} still missing. {2} is the "
        "record this case lacks: POL-GEN-07(1) puts the burden on the party "
        "asserting the money is owed and POL-GEN-07(2) makes {3} the outcome{4}."
    ).format(
        ", ".join(window.items),
        ", ".join(missing),
        absent,
        ruling,
        money_text,
    )


def review_command(
    run_dir: Path,
    case_no: int,
    packet: Mapping[str, Any],
    ruling: str,
    amount: Optional[Any],
    reason: str,
    closed_by: str,
) -> str:
    """The exact ``python3 -m ops.review`` command for the default outcome.

    It is ``tribunal.precedents close``'s own command line behind
    ``ops.review``, and it carries **no** ``close``: ``ops.review`` supplies the
    subcommand itself.
    """
    parts: List[str] = [
        "python3",
        "-m",
        "ops.review",
        "--run-dir",
        str(run_dir),
        "--case",
        str(case_no),
        "--packet-sha256",
        escalation.packet_sha256(packet),
        "--ruling",
        ruling,
    ]
    if amount is not None:
        parts += ["--amount", str(amount)]
    parts += [
        "--clause",
        CLAUSE_RESIDUAL,
        "--closed-by",
        '"{0}"'.format(closed_by),
        "--summary",
        '"{0}"'.format(ruling),
        "--reason",
        '"{0}"'.format(str(reason).replace('"', "'")),
    ]
    return " ".join(parts)


def close(store: Path, run_dir: Path, case_no: int, now: datetime) -> str:
    """Close a window, and say what the reviewer decides on.

    Refused before the close instant. If every item the window named arrived,
    the reviewer decides on the evidence. If any did not, the default outcome
    ``POL-GEN-07(1)(2)`` requires is given, with the exact command for it; this
    module does not write the precedent store itself.
    """
    directory = store_path(store)
    _require_zone(now, "--now")
    window = window_state(directory, case_no)
    if window is None:
        raise EvidenceWindowError(
            "case {0} has no evidence window in this store, so there is nothing to "
            "close".format(case_no)
        )
    if now < window.close_at:
        raise EvidenceWindowError(
            "the window for case {0} closes at {1}, and {2} is before it".format(
                case_no, _iso(window.close_at), _iso(now)
            )
        )
    events = read_events(directory, case_no)
    missing = missing_items(window, events)
    if not missing:
        return render_decide_on_the_evidence(window, events)

    packet, policies = _packet_and_policies(run_dir, case_no)
    read_residual_sentences(policies)
    ruling, amount = default_outcome(packet)
    evidence_id = first_missing_evidence_id(packet)
    reason = default_reason(window, missing, evidence_id, ruling, amount)
    command = review_command(
        run_dir, case_no, packet, ruling, amount, reason, window.opened_by
    )
    return render_close_default(window, missing, ruling, amount, evidence_id, command)


def render_decide_on_the_evidence(
    window: Window, events: Sequence[Mapping[str, Any]]
) -> str:
    lines = [
        "the evidence arrived for case {0}".format(window.case_no),
        "  the window named {0}".format(", ".join(window.items)),
        "  filed: {0}".format(
            ", ".join(
                "{0} {1}".format(event.get("party"), event.get("kind"))
                for event in _submissions(events)
            )
        ),
        "  decide on the evidence: the reviewer decides the case on what arrived, "
        "under POL-GEN-06(4).",
        "  {0}".format(OPS_RULE_NOTE),
    ]
    return "\n".join(lines) + "\n"


def render_close_default(
    window: Window,
    missing: Sequence[str],
    ruling: str,
    amount: Optional[Any],
    evidence_id: Optional[str],
    command: str,
) -> str:
    lines = [
        "the evidence did not arrive for case {0}".format(window.case_no),
        "  still missing: {0}".format(", ".join(missing)),
        "  default outcome under POL-GEN-07(1)(2): {0}{1}".format(
            ruling, "" if amount is None else " {0}".format(amount)
        ),
        "  the reason names the missing evidence's id: {0}".format(
            evidence_id or "(the case carries no absent artifact)"
        ),
        "  {0}".format(OPS_RULE_NOTE),
        "",
        command,
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ops.evidence_window",
        description=(
            "The evidence window: POL-GEN-06(4)'s REQUEST_EVIDENCE, made "
            "executable. One window is opened to both parties at once; each may "
            "submit a record until it closes, and at the close the reviewer "
            "decides on what arrived or the default outcome POL-GEN-07 requires. "
            "Makes no model call and reads no answer key."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(child: argparse.ArgumentParser) -> None:
        child.add_argument("--store", type=Path, required=True, help="the window store directory")
        child.add_argument("--run-dir", type=Path, required=True, help="the run directory")
        child.add_argument("--case", type=int, required=True, help="the case number")
        child.add_argument(
            "--now",
            required=True,
            help=(
                "an ISO 8601 instant with a UTC offset, e.g. 2026-08-11T20:00:00+08:00; "
                "the only wall clock this command reads"
            ),
        )

    open_parser = sub.add_parser("open", help="open the reviewer's REQUEST_EVIDENCE window")
    common(open_parser)
    open_parser.add_argument(
        "--items",
        required=True,
        help="the record kinds required, comma-separated, from POL-GEN-04(b)'s six",
    )
    open_parser.add_argument("--opened-by", required=True, help="the reviewer opening the window")
    open_parser.add_argument(
        "--config", type=Path, default=None, help="the config to read; defaults to ops/config.json"
    )

    submit_parser = sub.add_parser("submit", help="file one party's record into the window")
    common(submit_parser)
    submit_parser.add_argument("--party", required=True, help="rider or driver")
    submit_parser.add_argument("--kind", required=True, help="a record kind of POL-GEN-04(b)")
    submit_parser.add_argument("--file", type=Path, required=True, help="the record to file")
    submit_parser.add_argument(
        "--note", default="", help="at most 280 characters; an argument, not evidence"
    )

    status_parser = sub.add_parser("status", help="print the window and what each party filed")
    common(status_parser)

    close_parser = sub.add_parser("close", help="close the window and say what is decided")
    common(close_parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one sub-command of the evidence window."""
    args = _build_parser().parse_args(argv)
    try:
        now = _require_zone(_parse_instant(args.now, "--now"), "--now")
        if args.command == "open":
            sys.stdout.write(
                open_window(
                    args.store,
                    args.run_dir,
                    args.case,
                    args.items,
                    args.opened_by,
                    now,
                    args.config,
                )
            )
        elif args.command == "submit":
            sys.stdout.write(
                submit(
                    args.store,
                    args.case,
                    args.party,
                    args.kind,
                    args.file,
                    args.note,
                    now,
                )
            )
        elif args.command == "status":
            sys.stdout.write(status(args.store, args.case, now))
        else:
            sys.stdout.write(close(args.store, args.run_dir, args.case, now))
    except EvidenceWindowError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

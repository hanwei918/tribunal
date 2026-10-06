"""The precedent library: decisions a human reviewer has already closed.

A human reviewer reads a run and closes some of its cases. Those closures are
worth keeping, because they are the only record of what a person decided on this
material. The library holds them, and -- when a run is asked to -- the judge is
shown up to three of them that share clauses with the case in front of it.

What the library is not
-----------------------
It is not evidence and it is not policy. It never adds a clause and it decides
nothing; the block the judge receives says so in its own words. Every entry
carries the ruling a human decided and the clause ids they rested it on, and it
carries **no amount and no summary** in the block the judge sees, so a precedent
cannot be read as a figure to copy.

The store
---------
``precedents/precedents.jsonl``, append-only and hash-chained, one ``closure``
event per entry. It reuses :class:`tribunal.events.EventLog` rather than growing
a second append-only format: that class already reads its tail off disk when it
opens, so a second closure continues the chain instead of restarting it, and
:func:`tribunal.events.verify_chain` already names the first line that was
touched. The chain head is what a run records in its ``configuration``, so a
cached result produced against an earlier library is recognisable as such.

The path is a parameter with the repository's own path as its default, so every
test can point it at a temporary directory.

What this module may read
-------------------------
It is a module under ``tribunal/``, so it may name no path under ``eval/``. It
reads a run's case file for five fields and no others -- ``case_no``,
``ruling``, ``brief_sha256``, ``development_set`` and ``configuration`` -- and it
never reads ``matched`` and never reads ``events.jsonl``. The category, the
dispute id and the contested amount come from the **rebuilt brief**, which is
built from the case and the policy, so the answer-bearing half of a run is never
opened.

It also reads one case's **transcript**, and only for the recorded vote: the
panel's own proposals are what a human's ruling is compared against when the
``override`` flag is decided, and the case file carries the ruling the vote
produced rather than the proposals it was produced from. Nothing else in the
transcript is read, and no other case's transcript is opened.

What a closure records
----------------------
A closure carries a decision, the clause ids it rests on, and -- since the
reason became required -- three things it did not carry before: the reviewer's
own **reason**, whether the decision **overrides** the panel's best-supported
proposal, and the proposal it was compared against. The reason is written as a
separate ``human_decision`` event on the same chain rather than as a field of the
entry, because the block the judge is shown is built from the entry alone and the
reason is prose about one case. Entries written before this carry no reason, no
override and no schema version, they read as version 1, and they are never
rewritten: the store is append-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import brief, events, loader, money, policy_versions, referee

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The store. ``precedents/`` sits at the top level beside ``runs/`` and
# ``policy/``; ``precedents/precedents.jsonl`` is the chain.
PRECEDENTS_DIRNAME = "precedents"
PRECEDENTS_FILE = "precedents.jsonl"
README_FILE = "README.md"

# One event name, one event per entry. The event log's own reserved fields
# (``seq``, ``ts``, ``event``, ``prev``, ``hash``, ...) are written by
# ``EventLog``; everything else on the line is the entry.
EVENT_CLOSURE = "closure"

# The reviewer's own act, recorded beside the closure it produced. It is the one
# event in this store that is not a ``closure``, and it is deliberately not part
# of the entry: the reason is prose about one case, and the block the judge is
# shown is built from the entry alone.
EVENT_HUMAN_DECISION = "human_decision"

# The store's schema version, written on every entry and every decision this code
# appends. The two entries the owner closed before this existed carry no version
# and read as version 1, which is what they are; the store is append-only, so an
# older entry is never rewritten to say otherwise.
SCHEMA_VERSION = 2

# A reason has to say something. Twenty characters is a floor and not a target:
# "not convinced" is fourteen, and a reason that short is a note that a decision
# was made rather than a record of one.
MIN_REASON_CHARS = 20

# An evidence id as the case's own artifacts carry one.
EVIDENCE_ID_RE = re.compile(r"\bEV-[A-Za-z0-9]+-\d+\b")
# A clause reference as a reason would cite one. Deliberately loose, so a
# malformed one is *not* counted as a citation rather than silently matching.
CLAUSE_MENTION_RE = re.compile(r"POL-[A-Za-z]{1,6}-\d+")

# The id an entry carries. Four digits because a library that needed a fifth
# would already be a different kind of artefact.
PRECEDENT_ID_PREFIX = "P-"
PRECEDENT_ID_WIDTH = 4

# A summary is a note to a human, not a ruling.
MAX_SUMMARY_CHARS = 300

# The block the judge receives carries at most this many items.
MAX_ITEMS = 3

# The sets a run directory can belong to, named as the run directory path names
# them. The corpus is the exception and has no component of its own:
# ``runs/<model-slug>/`` *is* its directory, so it is the answer for a path that
# names no set at all.
SET_CORPUS = "corpus"
SET_CODEX = "codex"
SET_WILD = "wild"
SET_WILD_DEV = "wild-dev"

# The directory under ``data/external/`` each set's cases are loaded from. Two
# sets share one: ``wild-dev`` holds the held-out set's own 64 cases as
# development data, so it is loaded from ``data/external/wild`` while a closure
# of it records ``wild-dev`` as the set it came from. Naming the directory here
# rather than deriving it from the set name is what lets the two disagree on
# purpose.
#
# Nothing from ``eval/`` may be imported into this package, so this table and
# the registry in ``eval.development_sets`` are two statements of one layout;
# ``tests/test_precedents.py`` asserts that they agree.
EXTERNAL_SET_DIRS: Dict[str, str] = {
    SET_CODEX: SET_CODEX,
    SET_WILD: SET_WILD,
    SET_WILD_DEV: SET_WILD,
}

# The path component that identifies a runs root. The set is derived from the
# run directory's own path rather than from the case file's ``development_set``,
# because a schema-1 file has no such field and a closure must still be able to
# say which set it came from.
RUNS_DIRNAME = "runs"

# The four graded fields, in the order every other part of the repository
# writes them.
GRADED_FIELDS = ("ruling", "amount_sgd", "driver_compensation_sgd", "referrals")

# The five ruling values live in the policy, and the licenses list on POL-GEN-03
# is what says which of them a clause may produce. The clause id is named here
# for the same reason ``referee`` names POL-GEN-01: a clause id is not a policy
# *value*, and the value itself is read from the loaded policy.
POL_GEN_03 = "POL-GEN-03"
ESCALATE = "ESCALATE"

# The names an entry's fields may never carry. The first five are the loader's
# own forbidden keys, so an entry cannot smuggle an answer into a store that a
# later task might read back into a brief; the rest are the answer key's other
# field names and the grader's vocabulary.
FORBIDDEN_FIELD_NAMES = tuple(loader.FORBIDDEN_KEYS) + (
    "rationale",
    "difficulty",
    "governing_clauses",
    "matched",
    "expected",
    "grade",
)

# The note the judge receives whenever the block is present. Fixed text in code,
# and its sha256 is recorded beside the chain head, so a change to it is visible
# in the configuration of every later run.
NOTE = (
    "Earlier cases closed by a human reviewer, chosen because they share clauses "
    "with this case. They are not evidence and not policy: never cite a precedent "
    "id as a ground, and rest every finding on this case's evidence ids and clause "
    "ids. If your ruling differs from a precedent that shares its clauses, say in "
    "one sentence what in this case's evidence makes the difference."
)

# A clause reference as the policy writes it: a base id, optionally with a limb.
_CLAUSE_RE = re.compile(r"^POL-[A-Z]{2,4}-\d{2}(?:\([a-z0-9]+\))?$")
_LIMB_RE = re.compile(r"\([a-z0-9]+\)$")


class PrecedentError(Exception):
    """A closure, an entry or a store the library cannot accept."""


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------
def store_path(store: Optional[Any] = None) -> Path:
    """The chain's path, under ``store`` or under the repository's own store."""
    root = Path(store) if store is not None else PROJECT_ROOT / PRECEDENTS_DIRNAME
    return root / PRECEDENTS_FILE


def read_entries(path: Any) -> List[Dict[str, Any]]:
    """Every closure entry in the chain, in the order it was written.

    The reserved fields ``EventLog`` writes -- the sequence number, the
    timestamp, the chain links -- are dropped, because an entry is what a human
    closed and not how the file records it. The rest of the line *is* the entry.
    """
    entries: List[Dict[str, Any]] = []
    for event in events.read_events(Path(path)):
        if event.get("event") != EVENT_CLOSURE:
            continue
        entries.append(
            {
                key: value
                for key, value in event.items()
                if key not in events.RESERVED_FIELDS
            }
        )
    return entries


def chain_head(path: Any) -> str:
    """The last line's ``hash``, or the genesis sentinel for an empty store.

    An empty library still has a head, and it is a value rather than ``None``:
    a run that recorded "the library was empty" and a run that recorded nothing
    at all are different, and the first is what a run against an empty library
    writes.
    """
    lines = events.read_lines(Path(path))
    if not lines:
        return events.GENESIS
    try:
        event = json.loads(lines[-1], parse_float=Decimal)
    except (ValueError, TypeError):
        return events.GENESIS
    recorded = event.get("hash") if isinstance(event, Mapping) else None
    return recorded if isinstance(recorded, str) else events.GENESIS


def note_sha256() -> str:
    """The digest of the fixed note the judge is given."""
    return hashlib.sha256(NOTE.encode("utf-8")).hexdigest()


def library_document(store: Optional[Any] = None) -> Dict[str, Any]:
    """What a run records about the library it used.

    Both values, because both change what the judge was shown: the chain head
    moves when an entry is appended, and the note digest moves when the text
    moves.
    """
    return {"chain_head": chain_head(store_path(store)), "note_sha256": note_sha256()}


def append_entry(
    entry: Mapping[str, Any],
    *,
    store: Optional[Any] = None,
    invocation_id: str = "precedents-close",
    git_commit: Optional[str] = None,
    now: Optional[Any] = None,
    human_decision: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Append one closure to the chain and return the entry as written.

    ``human_decision``, when it is given, is appended as a second event on the
    same chain, **after** the closure. The reason lives there and not on the
    entry, because the block the judge is shown is built from the entry alone and
    the reason is prose about one case: an entry travels to another case's judge,
    and the reason must not travel with it. The two events go through one
    :class:`~tribunal.events.EventLog`, so the chain is continued once and the
    decision's line chains onto the closure's own line.
    """
    _assert_no_forbidden_field_names(entry)
    if human_decision is not None:
        _assert_no_forbidden_field_names(human_decision, "human_decision")
    path = store_path(store)
    kwargs: Dict[str, Any] = {}
    if now is not None:
        kwargs["now"] = now
    log = events.EventLog(
        path,
        invocation_id=invocation_id,
        git_commit=git_commit,
        **kwargs
    )
    case_no = entry.get("source", {}).get("case_no")
    log.record(EVENT_CLOSURE, case_no=case_no, **dict(entry))
    if human_decision is not None:
        log.record(EVENT_HUMAN_DECISION, case_no=case_no, **dict(human_decision))
    return dict(entry)


def next_precedent_id(entries: Sequence[Mapping[str, Any]]) -> str:
    """The next free ``P-nnnn``, read off the ids already in the chain."""
    highest = 0
    for entry in entries:
        raw = entry.get("precedent_id")
        if not isinstance(raw, str) or not raw.startswith(PRECEDENT_ID_PREFIX):
            continue
        suffix = raw[len(PRECEDENT_ID_PREFIX):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return "{0}{1:0{2}d}".format(PRECEDENT_ID_PREFIX, highest + 1, PRECEDENT_ID_WIDTH)


def latest_by_source_with_positions(
    entries: Sequence[Mapping[str, Any]],
) -> List[Tuple[int, Dict[str, Any]]]:
    """The latest entry per source case, each with its own position in the log.

    The position is the entry's index in the chain as it was written, and it is
    what :func:`matches` means by "the earlier entry" when two candidates score
    alike. It is the position of the entry that was **chosen** -- the latest
    closure for that source case -- and not where its source case first
    appeared: a case closed twice has one latest entry, and its position is the
    line that closure was written on.
    """
    latest: Dict[Tuple[str, Any], Tuple[int, Dict[str, Any]]] = {}
    for position, entry in enumerate(entries):
        source = entry.get("source")
        if not isinstance(source, Mapping):
            continue
        key = (str(source.get("set")), source.get("case_no"))
        latest[key] = (position, dict(entry))
    return list(latest.values())


def latest_by_source(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """The latest entry per source case, in the order the cases first appear.

    A superseded entry stays in the chain -- the store is append-only -- and is
    simply not what a later run is shown.
    """
    return [entry for _position, entry in latest_by_source_with_positions(entries)]


def _assert_no_forbidden_field_names(node: Any, where: str = "entry") -> None:
    """Recursively refuse an entry that carries a forbidden field name."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in FORBIDDEN_FIELD_NAMES:
                raise PrecedentError(
                    "a precedent entry may not carry the field {0!r} (at {1})".format(
                        key, where
                    )
                )
            _assert_no_forbidden_field_names(value, "{0}.{1}".format(where, key))
    elif isinstance(node, (list, tuple)):
        for position, value in enumerate(node):
            _assert_no_forbidden_field_names(value, "{0}[{1}]".format(where, position))


# --------------------------------------------------------------------------
# Reading a run's case file: five fields and no others
# --------------------------------------------------------------------------
# The fields a closure may read from a case file. Named as a constant so the
# list is one thing and not a claim spread over the code, and so a test can
# assert that the reader never touches a sixth.
CASE_FIELDS_READ = (
    "case_no",
    "ruling",
    "brief_sha256",
    "development_set",
    "configuration",
)


def read_case_document(case_file: Any) -> Dict[str, Any]:
    """The five fields a closure reads, and nothing else from the file.

    ``matched`` is deliberately not among them: it is the grade, and a library
    built from grades would be built from the answer key. The file is read as a
    whole document and then narrowed here, so what is read is one list in one
    place.
    """
    path = Path(case_file)
    if not path.is_file():
        raise PrecedentError("there is no case file at {0}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, ValueError) as exc:
        raise PrecedentError("the case file at {0} cannot be read: {1}".format(path, exc))
    if not isinstance(document, Mapping):
        raise PrecedentError("the case file at {0} is not a JSON object".format(path))
    return {name: document.get(name) for name in CASE_FIELDS_READ}


def case_file_for(run_dir: Any, case_no: int) -> Path:
    return Path(run_dir) / "case-{0:05d}.json".format(case_no)


# --------------------------------------------------------------------------
# The recorded vote, and the proposal a human's decision is compared against
# --------------------------------------------------------------------------
def transcript_file_for(run_dir: Any, case_no: int) -> Path:
    """The run's transcript for one case.

    Named by the convention the runner's own transcript path uses, so a closure
    reads the file the run wrote rather than one this module invented. The name
    is spelled here rather than imported: this package may not name the runner,
    which is a module under ``eval/``.
    """
    return Path(run_dir) / "case-{0:05d}.transcript.json".format(case_no)


def read_recorded_vote(run_dir: Any, case_no: int) -> Optional[Dict[str, Any]]:
    """The vote one case's run recorded, or ``None`` when there is none.

    Read from the case's **transcript**, which is where the panel's drafts and
    the proposals they made live. The case file carries the ruling the vote
    produced and not the proposals it was produced from, so a closure that
    compared against the case file would be comparing the reviewer with the
    system's own answer rather than with the panel's. Nothing else in the
    transcript is read.
    """
    path = transcript_file_for(run_dir, case_no)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, ValueError):
        return None
    vote = document.get("vote") if isinstance(document, Mapping) else None
    return dict(vote) if isinstance(vote, Mapping) else None


def best_supported_proposal(vote_block: Any) -> Optional[Dict[str, Any]]:
    """The plurality proposal among a recorded vote's valid drafts, or ``None``.

    "Best supported" is counted and not judged: the proposal the most valid
    drafts made, with a tie going to the one whose first draft came earliest --
    the same rule :func:`tribunal.pipeline._reduce_vote` uses to carry a ruling,
    stated over proposals rather than over draft keys, so a closure compares the
    reviewer against what the panel actually proposed.

    A draft's proposal is grouped by its canonical serialisation, because two
    drafts that proposed the same four graded fields have proposed the same
    thing whatever order they were written in.

    ``None`` when there is no vote, no valid draft, or no proposal on any valid
    draft. That is a case a closure can still be made about, and it is why the
    override is then ``None`` rather than ``False``: "the reviewer agreed with
    the panel" and "there was no panel answer" are different facts.
    """
    if not isinstance(vote_block, Mapping):
        return None
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for draft in vote_block.get("drafts") or []:
        if not isinstance(draft, Mapping) or not draft.get("valid"):
            continue
        proposal = draft.get("proposal")
        if not isinstance(proposal, Mapping):
            continue
        groups.setdefault(money.dumps_canonical(dict(proposal)), []).append(draft)
    if not groups:
        return None
    key, drafts = max(
        groups.items(),
        key=lambda item: (len(item[1]), -int(item[1][0].get("draft") or 0)),
    )
    return json.loads(key, parse_float=Decimal)


def override_for(decision: Mapping[str, Any], proposal: Any) -> Optional[bool]:
    """Whether a reviewer's decision differs from the panel's best proposal.

    Both sides are put through the pipeline's own key, so a referral is compared
    as the clause references it leads with rather than as prose -- which is the
    only comparison that can be made between two free-text referral lists, and
    the one the vote itself makes between two drafts.

    ``None`` when there is no proposal to compare against. A boolean cannot hold
    that case and "the reviewer agreed", and the two mean different things.
    """
    if not isinstance(proposal, Mapping):
        return None
    from . import pipeline  # local: the pipeline imports this module

    human = pipeline.proposal_from_key(pipeline.vote_key({"ruling": dict(decision)}))
    return human != dict(proposal)


def check_reason(reason: Any, brief_object: Mapping[str, Any]) -> str:
    """A reviewer's reason, or a refusal naming what it is missing.

    Three things are required and each is checked rather than trusted. The reason
    says something -- at least :data:`MIN_REASON_CHARS` characters. It cites at
    least one evidence id of **this case**, read off the rebuilt brief's own
    evidence list. And it cites at least one clause id the loaded policy carries,
    the limb allowed and the base id required to resolve.

    A closure is the only record of what a person decided and why. A reason that
    cites neither this case's evidence nor the policy's clauses is not a record
    of a decision; it is a note that one was made, and the next reader cannot
    tell it apart from a guess.
    """
    if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON_CHARS:
        raise PrecedentError(
            "a closure carries a reason of at least {0} characters".format(
                MIN_REASON_CHARS
            )
        )
    case = brief_object.get("case") or {}
    evidence_ids = {
        item.get("evidence_id")
        for item in (case.get("evidence") or [])
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }
    cited_evidence = set(EVIDENCE_ID_RE.findall(reason))
    if not cited_evidence & evidence_ids:
        raise PrecedentError(
            "the reason cites no evidence id of this case; it cites {0}, and the "
            "case's own are {1}".format(
                ", ".join(sorted(cited_evidence)) or "none",
                ", ".join(sorted(evidence_ids)) or "none",
            )
        )
    clauses = referee.policy_clauses(brief_object)
    cited_clauses = [
        token
        for token in CLAUSE_MENTION_RE.findall(reason)
        if base_clause_id(token) in clauses
    ]
    if not cited_clauses:
        raise PrecedentError(
            "the reason cites no clause id the loaded policy carries"
        )
    return reason


def set_from_run_directory(run_dir: Any) -> str:
    """Which set a run directory belongs to, read off its path.

    The rule is one component: the part that follows the last ``runs`` segment,
    where that component names a set this module knows. ``runs/codex/<model>/``
    is the second development set, ``runs/wild/<model>/`` is the held-out set,
    and ``runs/wild-dev/<model>/`` is the same 64 cases as development data.
    Everything else -- ``runs/<model>/``, ``runs/precedents/<model>/``,
    ``runs/ablation/<name>/<model>/``, ``runs/policy-v2/<model>/`` -- is the
    corpus. A schema-1 case file has no ``development_set`` to consult, which is
    why the path decides.

    The corpus is the fallback rather than a name looked up, because its run
    directory carries no component of its own. The two wild sets are told apart
    here and share a case directory one level down, in
    :data:`EXTERNAL_SET_DIRS`.
    """
    parts = Path(run_dir).resolve().parts
    indices = [index for index, part in enumerate(parts) if part == RUNS_DIRNAME]
    if not indices:
        return SET_CORPUS
    following = indices[-1] + 1
    if following < len(parts) and parts[following] in EXTERNAL_SET_DIRS:
        return parts[following]
    return SET_CORPUS


def load_case_for_run(run_dir: Any, case_no: int) -> Dict[str, Any]:
    """The case itself, through the loader its set uses.

    The corpus is loaded from the manifest and every other set from the external
    directory it is filed under, exactly as a run of that set loads it -- and
    ``wild-dev`` is filed under ``wild``'s, because it holds the held-out set's
    own cases. Nothing here reads the run's result: the case is what the brief
    is rebuilt from.
    """
    external = EXTERNAL_SET_DIRS.get(set_from_run_directory(run_dir))
    if external is None:
        return loader.load_case(case_no)
    return loader.load_external_set_case(loader.EXTERNAL_DIR / external, case_no)


def repository_relative(path: Any) -> str:
    """A path as the repository names it, or as it is when it is outside.

    A closure of a run under the repository records ``runs/<...>``. A run
    somewhere else -- a temporary directory in a test, say -- records its own
    path rather than a chain of ``..`` segments that would name nothing.
    """
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# The block the judge sees
# --------------------------------------------------------------------------
def block(items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The judge's precedents block: the fixed note and up to three items.

    An item carries the id, the category, the clause ids and the ruling, and
    nothing else. No amount and no summary travel here: a figure in the block
    would be a figure to copy, and a summary is prose about a different case.
    """
    return {
        "note": NOTE,
        "items": [
            {
                "precedent_id": item.get("precedent_id"),
                "category": item.get("category"),
                "clause_ids": list(item.get("clause_ids") or []),
                "ruling": (item.get("decision") or {}).get("ruling"),
            }
            for item in items[:MAX_ITEMS]
        ],
    }


def base_clause_id(clause_id: Any) -> Optional[str]:
    """A clause id with its limb dropped, or ``None`` when it is not one."""
    if not isinstance(clause_id, str):
        return None
    trimmed = clause_id.strip()
    if not _CLAUSE_RE.match(trimmed):
        return None
    return _LIMB_RE.sub("", trimmed)


def kept_clause_ids(referee_result: Any) -> Tuple[str, ...]:
    """Every clause id cited by a claim the referee kept, sorted and unique.

    Sorted and de-duplicated because the matching scores an entry by how many of
    its clause ids appear here: a set with an order and without repeats is what
    makes that count a function of the claims and not of the order they arrived
    in.
    """
    kept: set = set()
    claims = getattr(referee_result, "kept_claims", None) or {}
    for side_claims in claims.values():
        for claim in side_claims or ():
            if not isinstance(claim, Mapping):
                continue
            for clause_id in claim.get("clause_ids") or ():
                base = base_clause_id(clause_id)
                if base is not None:
                    kept.add(base)
    return tuple(sorted(kept))


def _amount_difference(entry_amount: Any, contested: Any) -> Optional[Decimal]:
    """How far an entry's contested amount is from this case's, in Decimal.

    The relative difference ``|a-b|/b`` where ``b`` is this case's contested
    amount, and the absolute difference where ``b`` is zero or absent -- a
    relative difference against zero is not a number.
    """
    a = _as_decimal(entry_amount)
    if a is None:
        return None
    b = _as_decimal(contested)
    if b is None or b == 0:
        return abs(a - (b if b is not None else Decimal(0)))
    return abs(a - b) / b


def _as_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _entry_clause_ids(entry: Mapping[str, Any]) -> Optional[List[str]]:
    """An entry's clause ids with limbs dropped, or ``None`` when it cannot match.

    ``None`` means the entry is excluded whole, and there are two ways to earn
    it: an entry that rests on an id that is not a clause id, and an entry that
    rests on no clause id at all. Dropping the unparseable id instead would
    leave the entry resting on whichever ids happened to parse, which is a
    different entry from the one a human closed -- and the matching scores an
    entry by how many of its clause ids a kept claim cites, so a shortened list
    is a different score as well.
    """
    ids: List[str] = []
    for item in entry.get("clause_ids") or []:
        base = base_clause_id(item)
        if base is None:
            return None
        ids.append(base)
    return ids or None


def matches(
    entries: Sequence[Mapping[str, Any]],
    *,
    brief_object: Mapping[str, Any],
    kept_clause_ids_: Sequence[str],
    category: Any,
    amount_contested: Any,
    case_no: Any,
    dispute_id: Any,
    set_name: str,
) -> List[Dict[str, Any]]:
    """The precedents shown for one case, chosen by a rule written down here.

    Seven steps, in order, and each one is a filter a reader can check:

    1. the latest entry per source case;
    2. entries of the same category;
    3. everything except the case being judged, matched by set and case number
       and, separately, by ``dispute_id``;
    4. everything whose clause ids **all** resolve in this case's brief. An
       entry resting on one id that is not a clause id is excluded **whole**:
       dropping the bad id would leave it resting on whichever ids happened to
       parse, and that is not the entry a human closed;
    5. entries that share at least one clause with a claim the referee kept,
       scored by how many;
    6. ties broken by the relative amount difference and then by the earlier
       entry -- "earlier" being the chosen entry's own position in the log, the
       line the latest closure for its source case was written on, and not
       where its source case first appeared;
    7. the top three.
    """
    resolvable = set(referee.policy_clauses(brief_object))
    kept = set(kept_clause_ids_)
    scored: List[Tuple[int, Decimal, int, Dict[str, Any]]] = []
    for position, entry in latest_by_source_with_positions(entries):
        source = entry.get("source") or {}
        if entry.get("category") != category:
            continue
        if str(source.get("set")) == set_name and source.get("case_no") == case_no:
            continue
        if dispute_id is not None and source.get("dispute_id") == dispute_id:
            continue
        clause_ids = _entry_clause_ids(entry)
        if clause_ids is None:
            continue
        if any(base not in resolvable for base in clause_ids):
            # A clause that does not resolve in this case's policy cannot be
            # matched against, and an entry resting on one is not a precedent
            # for this case.
            continue
        shared = len(set(clause_ids) & kept)
        if shared < 1:
            continue
        difference = _amount_difference(entry.get("amount_contested_sgd"), amount_contested)
        scored.append(
            (
                -shared,
                difference if difference is not None else Decimal(0),
                position,
                dict(entry),
            )
        )
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in scored[:MAX_ITEMS]]


def block_for(
    library: "Library",
    brief_object: Mapping[str, Any],
    referee_result: Any,
    *,
    case_no: Any,
    dispute_id: Any,
) -> Tuple[Optional[Dict[str, Any]], Tuple[str, ...]]:
    """The judge's block for one case, and the ids it names.

    ``(None, ())`` when nothing matches, so the caller can leave the key out of
    the judge's message entirely rather than send an empty one.
    """
    case = brief_object.get("case") or {}
    dispute = case.get("dispute") or {}
    chosen = matches(
        library.entries,
        brief_object=brief_object,
        kept_clause_ids_=kept_clause_ids(referee_result),
        category=dispute.get("category"),
        amount_contested=dispute.get("amount_contested_sgd"),
        case_no=case_no,
        dispute_id=dispute_id,
        set_name=library.set_name,
    )
    if not chosen:
        return None, ()
    return block(chosen), tuple(str(item.get("precedent_id")) for item in chosen)


class Library:
    """One store's entries, its chain head and its note digest, read once.

    Read once because a run asks the same question of the same chain for every
    case, and because the chain head recorded in the run's configuration has to
    be the head the whole invocation was shown against.
    """

    def __init__(
        self,
        path: Path,
        entries: Sequence[Mapping[str, Any]],
        set_name: str = SET_CORPUS,
    ) -> None:
        self.path = Path(path)
        self.entries = tuple(dict(entry) for entry in entries)
        self.set_name = set_name
        self.chain_head = chain_head(self.path)

    @classmethod
    def load(cls, store: Optional[Any] = None, *, set_name: str = SET_CORPUS) -> "Library":
        path = store_path(store)
        return cls(path, read_entries(path), set_name=set_name)

    @property
    def note_sha256(self) -> str:
        return note_sha256()

    def configuration(self) -> Dict[str, Any]:
        """What a run records about this library, for every artifact it writes."""
        return {"chain_head": self.chain_head, "note_sha256": self.note_sha256}

    def block_for(self, brief_object, referee_result, *, case_no, dispute_id):
        return block_for(
            self,
            brief_object,
            referee_result,
            case_no=case_no,
            dispute_id=dispute_id,
        )


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _amount(text: Any, field: str) -> Decimal:
    """One money argument, as a decimal with at most two places."""
    try:
        value = Decimal(str(text))
    except (InvalidOperation, ValueError):
        raise PrecedentError("{0} is not a decimal: {1!r}".format(field, text))
    if not value.is_finite():
        raise PrecedentError("{0} is not a finite decimal: {1!r}".format(field, text))
    if value != value.quantize(Decimal("0.01")):
        raise PrecedentError(
            "{0} must have at most two decimal places, and {1!r} has more".format(
                field, text
            )
        )
    return value.quantize(Decimal("0.01"))


def _ruling_licenses(brief_object: Mapping[str, Any]) -> Tuple[str, ...]:
    """The five values POL-GEN-03 licenses, read out of the loaded policy."""
    clause = referee.policy_clauses(brief_object).get(POL_GEN_03)
    if not isinstance(clause, Mapping):
        raise PrecedentError("{0} is not in the loaded policy".format(POL_GEN_03))
    licenses = clause.get("licenses")
    if not isinstance(licenses, list) or not licenses:
        raise PrecedentError("{0} states no licenses".format(POL_GEN_03))
    return tuple(str(item) for item in licenses)


def _produced_outcome(document: Mapping[str, Any]) -> Dict[str, Any]:
    """The four graded fields the system produced, out of the case file.

    The stored result nests the ruling one level down -- ``{"discarded_claims":
    [...], "ruling": {...}}`` -- and a file that carries the flat object is read
    as it stands, so both shapes are answered without importing the grader.
    """
    produced = document.get("ruling")
    if isinstance(produced, Mapping) and isinstance(produced.get("ruling"), Mapping):
        produced = produced["ruling"]
    if not isinstance(produced, Mapping):
        produced = {}
    return {name: produced.get(name) for name in GRADED_FIELDS}


def _latest_for_source(
    entries: Sequence[Mapping[str, Any]], set_name: str, case_no: Any
) -> Optional[Dict[str, Any]]:
    for entry in reversed(latest_by_source(entries)):
        source = entry.get("source") or {}
        if str(source.get("set")) == set_name and source.get("case_no") == case_no:
            return dict(entry)
    return None


def close(args: argparse.Namespace) -> int:
    """Store one human reviewer's closing decision about one case."""
    from . import pipeline  # local: the pipeline imports this module

    run_dir = Path(args.run_dir)
    case_file = case_file_for(run_dir, args.case)
    document = read_case_document(case_file)
    if document.get("case_no") != args.case:
        raise PrecedentError(
            "the case file at {0} declares case_no {1!r}".format(
                case_file, document.get("case_no")
            )
        )

    set_name = set_from_run_directory(run_dir)
    case = load_case_for_run(run_dir, args.case)

    configuration = document.get("configuration")
    if not isinstance(configuration, Mapping):
        configuration = {}
    ablation = configuration.get("ablation")
    # The version the case file records, not the version this process happens
    # to default to. ``pipeline.replay_verdict`` rebuilds a replayed case's
    # brief at the version its source recorded for the same reason: a brief
    # rebuilt at another version is a different brief, and the digest check
    # below would refuse every case of a run briefed at a later policy version
    # -- which is every case of such a run, so the closure could not be made at
    # all.
    policy_version = configuration.get("policy_version") or policy_versions.BASE_VERSION
    brief_object = brief.build_brief_for_case(
        case, ablate=ablation, policy_version=policy_version
    )
    rebuilt = brief.brief_digest(brief_object)[1]
    recorded = document.get("brief_sha256")
    if not isinstance(recorded, str) or not recorded:
        raise PrecedentError("the case file records no brief_sha256 to check against")
    if rebuilt != recorded:
        raise PrecedentError(
            "the brief does not rebuild to the recorded digest: recorded {0}, "
            "rebuilt {1}. The case is not the case that produced this result, or "
            "the code has moved past it.".format(recorded, rebuilt)
        )

    licenses = _ruling_licenses(brief_object)
    if args.ruling not in licenses:
        raise PrecedentError(
            "{0!r} is not a ruling POL-GEN-03 licenses; it licenses {1}".format(
                args.ruling, ", ".join(licenses)
            )
        )
    if args.ruling == ESCALATE:
        raise PrecedentError(
            "a closure records a decision, and ESCALATE is the absence of one: "
            "the case is going to a human reviewer, so there is nothing to store"
        )

    decision = {
        "ruling": args.ruling,
        "amount_sgd": None if args.amount is None else _amount(args.amount, "--amount"),
        "driver_compensation_sgd": (
            None
            if args.driver_compensation is None
            else _amount(args.driver_compensation, "--driver-compensation")
        ),
        "referrals": list(args.referral or []),
    }

    clauses = referee.policy_clauses(brief_object)
    clause_ids: List[str] = []
    for raw in args.clause or []:
        base = base_clause_id(raw)
        if base is None:
            raise PrecedentError("{0!r} is not a clause id".format(raw))
        if base not in clauses:
            raise PrecedentError(
                "{0!r} does not resolve in this case's policy".format(raw)
            )
        clause_ids.append(raw)
    if not clause_ids:
        raise PrecedentError("a closure rests on at least one clause id")

    for referral in decision["referrals"]:
        leading = pipeline.leading_clause_reference(referral)
        base = base_clause_id(leading)
        if base is None or base not in clauses:
            raise PrecedentError(
                "the referral {0!r} leads with {1!r}, which does not resolve in "
                "this case's policy".format(referral, leading)
            )

    summary = args.summary
    if not isinstance(summary, str) or not summary.strip():
        raise PrecedentError("a closure carries a summary")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise PrecedentError(
            "a summary is at most {0} characters; this one is {1}".format(
                MAX_SUMMARY_CHARS, len(summary)
            )
        )

    # The reason is checked here, with every other refusal and before anything is
    # written, so a closure with no usable reason leaves the store exactly as it
    # found it.
    reason = check_reason(args.reason, brief_object)

    entries = read_entries(store_path(args.store))
    previous = _latest_for_source(entries, set_name, args.case)
    if previous is not None:
        if args.supersedes != previous.get("precedent_id"):
            raise PrecedentError(
                "case {0} of the {1} set already has a closure, {2}; supersede it "
                "by naming it with --supersedes".format(
                    args.case, set_name, previous.get("precedent_id")
                )
            )

    # What the panel proposed, and whether the reviewer departed from it. Read
    # after every refusal above, so a closure that is going to be refused does not
    # open the transcript either.
    proposal = best_supported_proposal(read_recorded_vote(run_dir, args.case))
    override = override_for(decision, proposal)

    dispute = (brief_object.get("case") or {}).get("dispute") or {}
    entry = {
        "precedent_id": next_precedent_id(entries),
        "source": {
            "set": set_name,
            "case_no": args.case,
            "dispute_id": dispute.get("dispute_id"),
            "run_dir": repository_relative(run_dir),
            "case_sha256": _sha256_of_file(case_file),
        },
        "category": dispute.get("category"),
        "system_outcome": _produced_outcome(document),
        "decision": decision,
        "clause_ids": clause_ids,
        "amount_contested_sgd": dispute.get("amount_contested_sgd"),
        "summary": summary,
        "closed_by": args.closed_by,
        "policy_version": policy_version,
        "supersedes": args.supersedes,
        "schema_version": SCHEMA_VERSION,
        "override": override,
        "override_proposal": proposal,
    }
    append_entry(
        entry,
        store=args.store,
        invocation_id=args.invocation_id,
        human_decision={
            "schema_version": SCHEMA_VERSION,
            "reviewer": args.closed_by,
            "decision": dict(decision),
            "reason": reason,
            "override": override,
        },
    )
    print(
        "stored {0} for case {1} of the {2} set ({3})".format(
            entry["precedent_id"],
            args.case,
            set_name,
            {
                None: "no panel proposal to compare against",
                True: "overrides the panel's best-supported proposal",
                False: "agrees with the panel's best-supported proposal",
            }[override],
        )
    )
    return 0


def list_entries(args: argparse.Namespace) -> int:
    """Print the library, one entry per line."""
    entries = read_entries(store_path(args.store))
    if not entries:
        print("the library is empty ({0})".format(store_path(args.store)))
        return 0
    for entry in entries:
        source = entry.get("source") or {}
        decision = entry.get("decision") or {}
        print(
            "{0}  {1}/{2}  {3}  {4}  {5}  by {6}".format(
                entry.get("precedent_id"),
                source.get("set"),
                source.get("case_no"),
                entry.get("category"),
                decision.get("ruling"),
                ",".join(entry.get("clause_ids") or []) or "-",
                entry.get("closed_by"),
            )
        )
    print("{0} entr{1}".format(len(entries), "y" if len(entries) == 1 else "ies"))
    return 0


def verify(args: argparse.Namespace) -> int:
    """Walk the chain and report the first break, or that there is none."""
    path = store_path(args.store)
    break_ = events.verify_chain(path)
    if break_ is None:
        print("the chain is intact: {0} ({1} entries)".format(
            path, len(read_entries(path))
        ))
        return 0
    print("the chain is broken at {0}".format(break_.describe()), file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tribunal.precedents",
        description=(
            "The precedent library: decisions a human reviewer has closed. "
            "Append-only and hash-chained, and no model is called by any "
            "subcommand."
        ),
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="the store directory, defaulting to the repository's own precedents/",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    close_parser = sub.add_parser(
        "close", help="store one reviewer's decision about one case"
    )
    close_parser.add_argument("--run-dir", type=Path, required=True)
    close_parser.add_argument("--case", type=int, required=True)
    close_parser.add_argument("--ruling", required=True)
    close_parser.add_argument("--amount", default=None)
    close_parser.add_argument("--driver-compensation", default=None)
    close_parser.add_argument("--referral", action="append", default=[])
    close_parser.add_argument("--clause", action="append", default=[])
    close_parser.add_argument("--closed-by", required=True)
    close_parser.add_argument("--summary", required=True)
    # Required, and required here rather than checked only in `close`, so a
    # closure with no reason is refused by the argument parser before a run
    # directory, a case file or a transcript is opened at all.
    close_parser.add_argument(
        "--reason",
        required=True,
        help=(
            "why the reviewer decided this; at least {0} characters, citing at "
            "least one evidence id of the case and one clause id of the policy".format(
                MIN_REASON_CHARS
            )
        ),
    )
    close_parser.add_argument("--supersedes", default=None)
    close_parser.add_argument("--invocation-id", default="precedents-close")

    sub.add_parser("list", help="print the library")
    sub.add_parser("verify", help="check the chain")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "close":
            return close(args)
        if args.command == "list":
            return list_entries(args)
        return verify(args)
    except (PrecedentError, loader.LoaderError, brief.AblationError) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())

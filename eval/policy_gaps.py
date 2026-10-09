"""The policy-gap loop: where the policy runs out, and a clause proposed for it.

The precedent library lets the judge see earlier human decisions, but it never
adds a clause. This loop finds the cases the policy could not decide, groups
them, and -- for a group a person has closed at least twice -- asks a model to
draft **one clause** that would decide them. Nothing it drafts takes effect on
its own: a draft is a proposal under ``policy/proposals/`` until a person runs
``approve``, and ``approve`` is the only writer of an amendments directory.

The commands
------------

* ``report --run-dir DIR [...] [--min-cases N]`` -- read the recorded runs,
  classify every case that ended undecided, group the cases into clusters, and
  write ``runs/policy-gaps/report.json`` and ``report.md``. **No model call.**
* ``draft --report FILE --cluster ID`` -- one model call, for a flagged cluster
  that has at least two human closures, writing a proposal.
* ``approve --proposal FILE --approved-by NAME [--base-version N]`` -- write the
  amendment, on base 1 by default and on a separate base where the caller names
  one (base 3 writes ``policy/v3/amendments/`` and makes policy version 4).
* ``reject --proposal FILE --by NAME --reason TEXT`` -- record a rejection.
* ``rerun --amendment NNNN --run-dir DIR [...] [--yes]`` -- re-run the affected
  cases at the new policy version.
* ``diff --amendment NNNN`` -- compare the before and after rulings.

What this module may read
-------------------------
Of a case file, five fields and no others -- ``case_no``, ``ruling``,
``brief_sha256``, ``development_set`` and ``configuration`` -- exactly the five
:mod:`tribunal.precedents` reads, through that module's own reader. It reads the
transcript's **vote and verification blocks** and nothing else from the
transcript, the rebuilt brief, and the precedent library. It never reads
``matched`` and never reads a grade event. The one exception is :func:`diff`,
which grades the before and after rulings against the frozen version-1 key and
states in its own output that it does so; the key is loaded there and nowhere
else. ``rerun``'s cost estimate reads one further field, ``tokens``, which is a
cost and not an answer, and the queue asks for exactly that -- or, for a case
the run recorded only a transcript for, the ``prompt_tokens`` and
``completion_tokens`` of that transcript's entries, which is the same cost by
another name and is likewise not an answer.

The stores are parameters
-------------------------
The precedent store, the amendments directory, the proposals directory and the
runs root are all parameters with the repository's own paths as their defaults,
so every test can point them at a temporary directory.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"
POLICY_DIR = PROJECT_ROOT / "policy"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark, sealed_roots  # noqa: E402
from tribunal import (  # noqa: E402
    brief,
    llm,
    loader,
    money,
    pipeline,
    policy_versions,
    precedents,
    transcript as transcript_module,
)

# --------------------------------------------------------------------------
# Where things live
# --------------------------------------------------------------------------
POLICY_GAPS_DIRNAME = "policy-gaps"
REPORT_FILE = "report.json"
REPORT_MD = "report.md"

PROPOSALS_DIRNAME = "proposals"
POLICY_DRAFTER_PROMPT_FILE = "policy_drafter.system.md"
PROPOSAL_STATUS_PROPOSED = "PROPOSED"
PROPOSAL_STATUS_REJECTED = "REJECTED"
REJECTED_BY_CODE = "REJECTED_BY_CODE"

RERUN_FILE = "rerun.json"
DIFF_MD = "diff.md"
DIFF_JSON = "diff.json"

# A held-out set is run once and nothing is created under it again. Its cases
# are development data from 2026-10-01, so this loop re-runs them as the set's
# own re-runnable twin: a source under ``runs/wild/<model>/`` is re-run as
# ``wild-dev``, into ``runs/wild-dev/policy-v<N>/<model>/``. The mapping is
# named once, here, and every source in ``rerun.json`` records both halves of
# it -- the set it was read as and the set it was run as -- because a reader of
# the record has to be able to tell a re-run of development data from the
# held-out measurement it was read from.
RERUN_SET_FOR = {
    development_sets.SEALED_SET.name: development_sets.WILD_DEV.name,
}

# The two names that are one set of 64 cases. A command given both would read
# one set twice and count it twice, and no figure it printed could say which of
# the two it came from.
TWIN_SETS = (development_sets.SEALED_SET.name, development_sets.WILD_DEV.name)

# How a re-run's cost estimate was arrived at, in the words the plan prints. A
# case whose only record is its transcript is still costed, and the plan says
# which of the two the number came from.
TOKENS_FROM = {
    "case_file": "from the case file",
    "transcript": "from the transcript, which is all this run recorded",
}

# A diff at policy version 2 measures two things at once. Version 2 carries the
# amendment *and* part B's POL-RD-11 upfront-quote remedy, which changes the
# money block of every UPFRONT_QUOTE fare's brief, so a case that moved between
# version 1 and version 2 may have moved for either reason.
VERSION_TWO_NOTE = (
    "**This diff is at policy version 2, which carries two changes.** Version 2 "
    "holds this amendment and part B's POL-RD-11 upfront-quote remedy, which "
    "changes the money block of every UPFRONT_QUOTE fare's brief. A case that "
    "moved between version 1 and version 2 may have moved for either reason, so "
    "these gains cannot be attributed to the amendment alone."
)

# --------------------------------------------------------------------------
# The triggers
# --------------------------------------------------------------------------
ESCALATE = pipeline.ESCALATE
VOTE_ESCALATED = pipeline.VOTE_ESCALATED

TRIGGER_NO_MAJORITY = "no_majority"
TRIGGER_TOO_FEW = "too_few_valid_drafts"
TRIGGER_TOO_FEW_VERIFIER = "too_few_valid_drafts:verifier"
TRIGGER_BELOW_FLOOR = "below_confidence_floor"
TRIGGER_JUDGE_NO_CLAUSE = "judge_no_clause"
TRIGGER_CLAUSE_PREFIX = "clause:"
TRIGGER_SINGLE_PREFIX = "single_draft:"

# The three rows a single-draft file is classified by, without the vote
# condition. Named once because the trigger and the report both name them.
SINGLE_DRAFT_ROWS = (
    TRIGGER_BELOW_FLOOR,
    TRIGGER_CLAUSE_PREFIX,
    TRIGGER_JUDGE_NO_CLAUSE,
)

# The statuses an artifact can carry that make it a candidate for the evidence
# signature. A COMPLETE artifact is not one: the signature is about what is
# wrong with the record, not about what it holds.
IMPAIRED = "IMPAIRED"
MISSING = "MISSING"

# A pair present in at least this share of the given runs' cases is noise and is
# dropped from every signature. The share is a Decimal, not a float, so the
# comparison is exact.
NOISE_SHARE = Decimal("0.8")

# Two decimal places: the money the policy states, and the places the diff
# renders a money field at so equal values render equally.
CENTS = Decimal("0.01")

DEFAULT_MIN_CASES = 3

CLUSTER_PREFIX = "C"

# The five ruling values, so a report can say which of them an escalation is.
RULING_FIELDS = precedents.GRADED_FIELDS


class PolicyGapError(Exception):
    """The loop was asked for something it cannot do."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _relative(path: Any) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def as_decimal(value: Any) -> Optional[Decimal]:
    """A recorded number as a ``Decimal``, or ``None`` when it is not one.

    ``bool`` is refused before ``Decimal`` sees it: ``isinstance(True, int)`` is
    true, and a confidence recorded as ``true`` is not the number one.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, ArithmeticError, TypeError):
        return None


def policy_gaps_directory(runs_dir: Path = RUNS_DIR) -> Path:
    """Where the report and the rerun's own record live."""
    return Path(runs_dir) / POLICY_GAPS_DIRNAME


def proposals_directory(root: Optional[Any] = None) -> Path:
    """Where the drafts live, under ``policy/`` unless told otherwise."""
    base = Path(root) if root is not None else POLICY_DIR
    return base / PROPOSALS_DIRNAME


def amendments_directory(
    root: Optional[Any] = None, base_version: int = policy_versions.BASE_VERSION
) -> Path:
    """The amendments directory **of one base**, through the module that owns its layout.

    Base 1's is ``policy/amendments/``; base 3's is ``policy/v3/amendments/``, one
    directory down beside the three files it amends.
    """
    return policy_versions.amendments_dir_for(base_version, root)


def assert_not_a_run_directory(destination: Path, runs_dir: Path, model: str) -> Path:
    """Refuse a destination that is a headline run directory, or lies inside one.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/``,
    ``runs/wild/<model-slug>/`` and everything under ``runs/external/`` hold
    the results the submission reports. The policy-gap
    report is not a run, and a reader who found these figures there would read
    them as that run's, so the destination is refused before anything is
    written. The check is structural as well as by name: a directory holding a
    run's own ``run.json`` or case files is a run directory whichever model it
    belongs to.

    The comparisons are case-folded, through
    :func:`eval.run_benchmark.path_components`, because this volume is
    case-insensitive: ``runs/WILD/<slug>`` names the same directory as
    ``runs/wild/<slug>``, and a guard that answered about the spelling rather
    than the directory could be walked around by changing one letter's case.
    """
    resolved = Path(destination).resolve()
    root = Path(runs_dir).resolve()
    folded = run_benchmark.path_components(destination)

    for headline in run_benchmark.headline_run_directories(runs_dir, model):
        if folded == run_benchmark.path_components(headline):
            raise PolicyGapError(
                "the policy-gap report may not be written to the headline run "
                "directory {0}; it is not that run's figures".format(resolved)
            )

    external = (root / run_benchmark.EXTERNAL_RUNS_SUBDIR).resolve()
    external_parts = run_benchmark.path_components(external)
    if folded == external_parts or folded[: len(external_parts)] == external_parts:
        raise PolicyGapError(
            "the policy-gap report may not be written under {0}; every "
            "directory there is a headline directory".format(external)
        )

    # The whole of a sealed set's root, not only its run directory: both sealed
    # runs have been made and nothing is created under either again, report
    # included. That rule is one rule for every command that writes to a path a
    # caller names, so it lives in :mod:`eval.sealed_roots`; only the closing
    # sentence is this command's own.
    try:
        sealed_roots.refuse_a_sealed_destination(resolved, runs_dir)
    except sealed_roots.SealedDestinationError as exc:
        raise PolicyGapError(
            "{0} A policy-gap report over those cases belongs in a directory of "
            "its own, not under the run it read.".format(exc)
        ) from None

    candidate = resolved
    while candidate != root and root in candidate.parents:
        if (candidate / run_benchmark.METADATA_FILE).is_file() or any(
            candidate.glob("case-*.json")
        ):
            raise PolicyGapError(
                "the policy-gap report may not be written to {0}, which holds a "
                "run's own results".format(candidate)
            )
        candidate = candidate.parent
    return resolved


def assert_not_an_external_run_directory(run_dir: Path, runs_dir: Path) -> Path:
    """Refuse a run directory under ``runs/external/``.

    An external case has no answer-key entry and is not part of either
    development set, so it is not a case the policy-gap loop may re-run.
    """
    resolved = Path(run_dir).resolve()
    external = (Path(runs_dir) / run_benchmark.EXTERNAL_RUNS_SUBDIR).resolve()
    if resolved == external or external in resolved.parents:
        raise PolicyGapError(
            "{0} is under {1}: an external case is not part of either "
            "development set and is never re-run by this loop".format(
                resolved, external
            )
        )
    return resolved


# The sealed roots whose run directory this loop does not read. ``wild`` is not
# one of them: its 64 cases have been development data since 2026-10-01, so a
# source under ``runs/wild/`` is re-run as ``wild-dev`` and the loop does read
# it. The second sealed set has no such twin -- its cases are not development
# data and are never re-run -- so a run directory under its root is refused.
SEALED_ROOTS_THE_LOOP_DOES_NOT_READ: Tuple[str, ...] = (
    run_benchmark.WILD_V2_SET_RUNS_SUBDIR,
)


def assert_not_a_sealed_record_the_loop_does_not_read(run_dir: Path) -> Path:
    """Refuse a run directory of a sealed set this loop does not read.

    ``runs/wild-v2/`` holds the second sealed set's single run. That run has
    been made -- once, on 2026-10-04 -- and committed exactly as it was
    produced, so what the loop has in front of it is a sealed **record**. The
    set is deliberately absent from ``tribunal.precedents.EXTERNAL_SET_DIRS``,
    because it is a held-out record and not development data, so a run directory
    under that root reads as the corpus -- and the report would then say
    "nothing could be analysed", which is a statement about this loop rather
    than about the set. So the loop refuses the directory by name.

    The test is **component by component**: the component after the last
    ``runs`` segment must be one of
    :data:`SEALED_ROOTS_THE_LOOP_DOES_NOT_READ`. That catches
    ``runs/wild-v2/<model>/`` and nothing else -- ``runs/wild-dev/`` is a
    different component and is not caught, and neither is a sibling whose name
    merely starts the same way.

    **Both comparisons are case-folded**, through
    :func:`eval.run_benchmark.path_components`, because this volume is
    case-insensitive: ``runs/WILD-V2/<model>/`` names the same directory as
    ``runs/wild-v2/<model>/``, and a guard that answered about the spelling
    rather than the directory could be walked around by changing one letter's
    case. The name in the refusal is the folded one, so the message says which
    set was refused rather than which spelling was typed.
    """
    folded = run_benchmark.path_components(run_dir)
    resolved = Path(run_dir).resolve()
    runs_name = precedents.RUNS_DIRNAME.casefold()
    indices = [index for index, part in enumerate(folded) if part == runs_name]
    if not indices:
        return resolved
    following = indices[-1] + 1
    sealed = tuple(name.casefold() for name in SEALED_ROOTS_THE_LOOP_DOES_NOT_READ)
    if following < len(folded) and folded[following] in sealed:
        raise PolicyGapError(
            "{0} is a run directory of the sealed set {1}. That set has been "
            "run: it is a sealed record, made once, and the policy-gap loop "
            "does not read it".format(resolved, folded[following])
        )
    return resolved


def _set_of_run_directory(run_dir: Any) -> str:
    """Which set a run directory belongs to, by the one rule that decides it."""
    return precedents.set_from_run_directory(Path(run_dir))


def _refuse_both_wild_sets(set_names: Sequence[str], *, command: str) -> None:
    """Refuse a command that was given both of the two wild run directories.

    ``wild`` is the held-out record -- made once and never written to again --
    and ``wild-dev`` is those same 64 cases as development data. Reading both
    would read one set twice and count it twice, and worse, no figure the
    command printed could say which of the two it came from, which is the only
    thing the two names exist to say. So the command is refused rather than
    silently deduplicated: which run a number came from is not a detail a reader
    can be left to guess.
    """
    names = set(set_names)
    if all(name in names for name in TWIN_SETS):
        raise PolicyGapError(
            "this {0} was given both a `{1}` and a `{2}` run directory. They are "
            "the same 64 cases under two names -- `{1}` is the held-out record "
            "and `{2}` is those cases as development data -- so reading both "
            "would read one set twice. Give one of them.".format(
                command, TWIN_SETS[0], TWIN_SETS[1]
            )
        )


# --------------------------------------------------------------------------
# Reading a run
# --------------------------------------------------------------------------
def read_vote_block(transcript_file: Path) -> Optional[Dict[str, Any]]:
    """A transcript's vote block, and nothing else from the file.

    The transcript carries the advocate calls, the referee's ledger and the
    vote; this reads the file and hands back the vote alone, so what the loop
    may use from a transcript is one list in one place. A run asked the judge
    once has no vote block, and that is ``None`` rather than an empty one.
    """
    payload = run_benchmark.read_json(Path(transcript_file))
    vote = payload.get("vote") if isinstance(payload, Mapping) else None
    return dict(vote) if isinstance(vote, Mapping) else None


def produced_inner(document: Mapping[str, Any]) -> Mapping[str, Any]:
    """The POL-GEN-03 object a case file's ``ruling`` nests, or an empty one.

    The stored result is ``{"discarded_claims": [...], "ruling": {...}}``; a
    file that carries the flat object is read as it stands, so both shapes are
    answered without importing the grader.
    """
    produced = document.get("ruling")
    if isinstance(produced, Mapping) and isinstance(produced.get("ruling"), Mapping):
        produced = produced["ruling"]
    return produced if isinstance(produced, Mapping) else {}


def produced_outcome(document: Mapping[str, Any]) -> Dict[str, Any]:
    """The four graded fields the system produced, out of a case file."""
    inner = produced_inner(document)
    return {name: inner.get(name) for name in RULING_FIELDS}


def confidence_floor(brief_object: Mapping[str, Any]) -> Optional[Decimal]:
    """The brief's ``confidence_floor``, read from the loaded category policy.

    It is carried per policy file, so it is read from the loaded policy rather
    than written down here. The category policy is the one the case was briefed
    under; the general policy's own floor is the fallback for a brief that does
    not carry a category one.
    """
    policies = brief_object.get("policies") or {}
    for key in ("category", "general"):
        policy = policies.get(key) or {}
        value = as_decimal(policy.get("confidence_floor"))
        if value is not None:
            return value
    return None


def signature_pairs(brief_object: Mapping[str, Any]) -> Tuple[str, ...]:
    """Every ``<evidence type>:<issue code>`` pair on an impaired or missing artifact.

    Taken from the rebuilt brief, so it is a function of the case and the policy
    and not of anything a model said. An artifact whose status is COMPLETE
    contributes nothing: the signature is about what is wrong with the record.
    """
    pairs = set()
    case = brief_object.get("case") or {}
    for artifact in case.get("evidence") or ():
        if not isinstance(artifact, Mapping):
            continue
        admissibility = artifact.get("admissibility")
        if not isinstance(admissibility, Mapping):
            continue
        if admissibility.get("status") not in (IMPAIRED, MISSING):
            continue
        evidence_type = artifact.get("evidence_type")
        if not isinstance(evidence_type, str):
            continue
        for code in admissibility.get("issues") or ():
            if isinstance(code, str):
                pairs.add("{0}:{1}".format(evidence_type, code))
    return tuple(sorted(pairs))


def leading_referral_clause(referrals: Any) -> Optional[str]:
    """The clause id the first referral leads with, its limb dropped.

    ``None`` when there is no referral or the first one leads with no clause
    reference at all, which is a value the trigger treats as "no clause".

    The limb is dropped because this names a *clause*: ``POL-NS-05(i)`` and
    ``POL-NS-05(ii)`` are one clause, and keeping the limb would split one
    cluster of cases into one per limb. The diff keeps the limb, because there
    it is comparing two references rather than naming a clause.
    """
    if not isinstance(referrals, (list, tuple)) or not referrals:
        return None
    leading = pipeline.leading_clause_reference(referrals[0])
    return precedents.base_clause_id(leading)


def trigger_of(
    *,
    has_vote: bool,
    vote_outcome: Optional[str],
    ruling: Optional[str],
    confidence: Optional[Decimal],
    floor: Optional[Decimal],
    leading_clause: Optional[str],
    valid: Optional[int],
    threshold: Optional[int],
    abstained: Sequence[int],
) -> Optional[str]:
    """Which policy-gap trigger a case falls under, or ``None`` for none.

    The rules, in the order they are applied:

    * a **single-draft file** -- one with no vote block -- is classified by the
      three carried rows below, without the vote condition, and its trigger is
      prefixed ``single_draft:``;
    * a vote that **escalated** is ``no_majority`` when at least a quorum of
      drafts was valid, and ``too_few_valid_drafts`` otherwise -- with
      ``:verifier`` appended when the verifier abstained on a draft;
    * a **carried** case is a gap only when its ruling is ESCALATE, and then it
      is ``below_confidence_floor`` when the confidence is under the brief's
      floor, else ``clause:<id>`` when there is a referral, else
      ``judge_no_clause``.

    A confidence that was not recorded counts as below the floor: "not recorded"
    is not "at or above", and the row exists to find the cases the policy left
    the judge without a number to stand on.
    """
    prefix = "" if has_vote else TRIGGER_SINGLE_PREFIX

    if not has_vote:
        if ruling != ESCALATE:
            return None
        if confidence is None or floor is None or confidence < floor:
            return prefix + TRIGGER_BELOW_FLOOR
        if leading_clause:
            return prefix + TRIGGER_CLAUSE_PREFIX + leading_clause
        return prefix + TRIGGER_JUDGE_NO_CLAUSE

    if vote_outcome == VOTE_ESCALATED:
        if valid is not None and threshold is not None and valid >= threshold:
            return TRIGGER_NO_MAJORITY
        if abstained:
            return TRIGGER_TOO_FEW_VERIFIER
        return TRIGGER_TOO_FEW

    if ruling != ESCALATE:
        return None
    if confidence is None or floor is None or confidence < floor:
        return TRIGGER_BELOW_FLOOR
    if leading_clause:
        return TRIGGER_CLAUSE_PREFIX + leading_clause
    return TRIGGER_JUDGE_NO_CLAUSE


@dataclass
class CaseReading:
    """One case that fell through the policy, read off a recorded run."""

    run_dir: Path
    set_name: str
    case_no: int
    category: str
    policy_version: int
    ablation: Optional[str]
    ruling: Optional[str]
    confidence: Optional[Decimal]
    system_outcome: Dict[str, Any]
    leading_referral_clause: Optional[str]
    vote_outcome: Optional[str]
    valid: Optional[int]
    threshold: Optional[int]
    abstained: Tuple[int, ...]
    trigger: str
    signature: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_dir": _relative(self.run_dir),
            "set": self.set_name,
            "case_no": self.case_no,
            "category": self.category,
            "policy_version": self.policy_version,
            "ablation": self.ablation,
            "ruling": self.ruling,
            "confidence": None if self.confidence is None else str(self.confidence),
            "system_outcome": dict(self.system_outcome),
            "leading_referral_clause": self.leading_referral_clause,
            "vote_outcome": self.vote_outcome,
            "valid": self.valid,
            "threshold": self.threshold,
            "abstained": list(self.abstained),
            "trigger": self.trigger,
            "signature": list(self.signature),
        }


@dataclass
class NotAnalysed:
    """A case the report could not analyse, and why."""

    run_dir: Path
    set_name: str
    case_no: int
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_dir": _relative(self.run_dir),
            "set": self.set_name,
            "case_no": self.case_no,
            "reason": self.reason,
        }


@dataclass
class RunReading:
    """One run directory as the report reads it."""

    run_dir: Path
    set_name: str
    cached_cases: Tuple[int, ...] = ()
    readings: Tuple[CaseReading, ...] = ()
    not_analysed: Tuple[NotAnalysed, ...] = ()
    signatures: Mapping[int, Tuple[str, ...]] = field(default_factory=dict)


def _read_cached_cases(run_dir: Path) -> Tuple[int, ...]:
    return tuple(run_benchmark.cached_case_numbers(run_dir))


def read_run(
    run_dir: Path,
    *,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> RunReading:
    """Read one run directory: its undecided cases, and the ones it cannot analyse.

    Every case whose brief rebuilds and whose recorded digests have not moved is
    classified. A case the code has moved past is reported as not analysed with
    the channel that moved; a case whose brief cannot be rebuilt is reported as
    not analysed with the reason; and a case that decided normally is simply not
    a gap and appears in neither list.
    """
    run_dir = Path(run_dir)
    set_name = precedents.set_from_run_directory(run_dir)
    development_set = development_sets.named(set_name)
    case_numbers = _read_cached_cases(run_dir)

    readings: List[CaseReading] = []
    not_analysed: List[NotAnalysed] = []
    signatures: Dict[int, Tuple[str, ...]] = {}
    seen: List[int] = []
    # One checker per (ablation, policy version), not one per case: the checker
    # memoises the prompt digest and each case's transcript entries, and the
    # only thing that makes two cases of one run need different checkers is a
    # different recorded configuration. A run whose cases all record the same
    # configuration -- which is every run this code writes -- builds one.
    checkers: Dict[Tuple[Optional[str], int], run_benchmark.BriefStaleness] = {}

    for case_no in case_numbers:
        case_file = run_benchmark.case_cache_path(run_dir, case_no)
        try:
            document = precedents.read_case_document(case_file)
        except precedents.PrecedentError as exc:
            not_analysed.append(
                NotAnalysed(run_dir, set_name, case_no, str(exc))
            )
            continue
        seen.append(case_no)
        configuration = run_benchmark.configuration_of(document)
        policy_version = configuration["policy_version"]
        ablation = configuration["ablation"]

        try:
            brief_object = brief.build_brief_for_case(
                development_set.load_case(case_no),
                ablate=ablation,
                policy_version=policy_version,
            )
        except Exception as exc:  # noqa: BLE001 - a brief that will not build is a finding
            not_analysed.append(
                NotAnalysed(
                    run_dir,
                    set_name,
                    case_no,
                    "the brief cannot be rebuilt: {0}: {1}".format(
                        type(exc).__name__, exc
                    ),
                )
            )
            continue

        signatures[case_no] = signature_pairs(brief_object)

        checker_key = (ablation, policy_version)
        checker = checkers.get(checker_key)
        if checker is None:
            checker = run_benchmark.BriefStaleness(
                run_benchmark.brief_digest_for(
                    development_set.load_case,
                    ablate=ablation,
                    policy_version=policy_version,
                ),
                run_dir=run_dir,
                prompts_dir=prompts_dir,
            )
            checkers[checker_key] = checker
        status = checker.status_of(case_no, document)
        if status != grade.STALENESS_CURRENT:
            if status == grade.STALENESS_STALE:
                moved = ", ".join(checker.moved_for(case_no, document))
                reason = "stale: {0} moved".format(moved or "a recorded digest")
            else:
                reason = (
                    "unknown: this code cannot establish that the result still "
                    "belongs to it"
                )
            not_analysed.append(NotAnalysed(run_dir, set_name, case_no, reason))
            continue

        vote = read_vote_block(run_benchmark.transcript_path(run_dir, case_no))
        inner = produced_inner(document)
        ruling = inner.get("ruling")
        confidence = as_decimal(inner.get("confidence"))
        floor = confidence_floor(brief_object)
        referrals = inner.get("referrals")
        leading = leading_referral_clause(referrals)

        if vote is None:
            has_vote = False
            vote_outcome = None
            valid = None
            threshold = None
            abstained: Tuple[int, ...] = ()
        else:
            has_vote = True
            vote_outcome = vote.get("outcome")
            valid = vote.get("valid") if isinstance(vote.get("valid"), int) else None
            threshold = (
                vote.get("threshold") if isinstance(vote.get("threshold"), int) else None
            )
            verification = vote.get("verification")
            raw_abstained = (
                verification.get("abstained")
                if isinstance(verification, Mapping)
                else None
            )
            abstained = tuple(
                item for item in (raw_abstained or ()) if isinstance(item, int)
            )

        trigger = trigger_of(
            has_vote=has_vote,
            vote_outcome=vote_outcome,
            ruling=ruling if isinstance(ruling, str) else None,
            confidence=confidence,
            floor=floor,
            leading_clause=leading,
            valid=valid,
            threshold=threshold,
            abstained=abstained,
        )
        if trigger is None:
            continue

        readings.append(
            CaseReading(
                run_dir=run_dir,
                set_name=set_name,
                case_no=case_no,
                category=str(
                    ((brief_object.get("case") or {}).get("dispute") or {}).get(
                        "category"
                    )
                ),
                policy_version=policy_version,
                ablation=ablation,
                ruling=ruling if isinstance(ruling, str) else None,
                confidence=confidence,
                system_outcome=produced_outcome(document),
                leading_referral_clause=leading,
                vote_outcome=vote_outcome,
                valid=valid,
                threshold=threshold,
                abstained=abstained,
                trigger=trigger,
                # Filled in once every run has been read: the noise pairs are
                # decided across all of them, not run by run.
                signature=(),
            )
        )

    return RunReading(
        run_dir=run_dir,
        set_name=set_name,
        cached_cases=tuple(seen),
        readings=tuple(readings),
        not_analysed=tuple(not_analysed),
        signatures=signatures,
    )


def dropped_noise_pairs(
    signatures: Mapping[int, Tuple[str, ...]], *, share: Decimal = NOISE_SHARE
) -> Tuple[str, ...]:
    """The pairs present in at least ``share`` of the given cases.

    A pair that appears on almost every case does not distinguish one case from
    another, so a signature built from it would cluster the whole set together
    and say nothing. The base is every case in the given runs whose brief could
    be rebuilt, and the share is a ``Decimal`` so the comparison is exact.
    """
    total = len(signatures)
    if total == 0:
        return ()
    counts: Dict[str, int] = {}
    for pairs in signatures.values():
        for pair in pairs:
            counts[pair] = counts.get(pair, 0) + 1
    dropped = [
        pair
        for pair, count in counts.items()
        if Decimal(count) / Decimal(total) >= share
    ]
    return tuple(sorted(dropped))


# --------------------------------------------------------------------------
# Clusters
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Cluster:
    """One group of cases the policy could not decide.

    Clusters form at two levels: ``(category, trigger)`` and
    ``(category, trigger, signature)``. The coarse level says these cases ran
    out of policy in the same way; the fine level adds that their records are
    impaired the same way too. Ids run ``C1``, ``C2``, ... in sorted order, and
    a cluster is flagged when it holds at least ``min_cases`` cases.
    """

    cluster_id: str
    level: int
    category: str
    trigger: str
    signature: Tuple[str, ...]
    cases: Tuple[int, ...]
    flagged: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "level": self.level,
            "category": self.category,
            "trigger": self.trigger,
            "signature": list(self.signature),
            "cases": list(self.cases),
            "case_count": len(self.cases),
            "flagged": self.flagged,
        }


def build_clusters(
    readings: Sequence[CaseReading], min_cases: int = DEFAULT_MIN_CASES
) -> Tuple[Cluster, ...]:
    """Every cluster at both levels, id'd in sorted order.

    Sorted by ``(level, category, trigger, signature)``, so two runs of the same
    data name the same cluster the same way and the coarse level always precedes
    the fine ones that refine it.

    A fine cluster whose signature is **empty** is not emitted: it holds exactly
    the cases its coarse cluster holds, and an empty signature adds nothing to
    say about them. Emitting it would name one set of cases twice under two ids,
    and a reader counting clusters would count two where there is one. So the
    fine level is only ever the refinement that a non-empty signature makes it.
    """
    coarse: Dict[Tuple[str, str], List[int]] = {}
    fine: Dict[Tuple[str, str, Tuple[str, ...]], List[int]] = {}
    for reading in readings:
        coarse.setdefault((reading.category, reading.trigger), []).append(reading.case_no)
        fine.setdefault(
            (reading.category, reading.trigger, reading.signature), []
        ).append(reading.case_no)

    entries: List[Tuple[Tuple[Any, ...], int, str, str, Tuple[str, ...], Tuple[int, ...]]] = []
    for (category, trigger), cases in coarse.items():
        entries.append(
            ((1, category, trigger, ()), 1, category, trigger, (), tuple(sorted(cases)))
        )
    for (category, trigger, signature), cases in fine.items():
        if not signature:
            continue
        entries.append(
            (
                (2, category, trigger, signature),
                2,
                category,
                trigger,
                signature,
                tuple(sorted(cases)),
            )
        )
    entries.sort(key=lambda item: item[0])

    clusters: List[Cluster] = []
    for position, (_key, level, category, trigger, signature, cases) in enumerate(
        entries, start=1
    ):
        clusters.append(
            Cluster(
                cluster_id="{0}{1}".format(CLUSTER_PREFIX, position),
                level=level,
                category=category,
                trigger=trigger,
                signature=signature,
                cases=cases,
                flagged=len(cases) >= min_cases,
            )
        )
    return tuple(clusters)


# --------------------------------------------------------------------------
# The precedent library's closures
# --------------------------------------------------------------------------
def closure_index(store: Optional[Any] = None) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """The latest closure per source case, keyed by ``(set, case_no)``."""
    entries = precedents.read_entries(precedents.store_path(store))
    index: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for entry in precedents.latest_by_source(entries):
        source = entry.get("source") or {}
        case_no = source.get("case_no")
        if isinstance(case_no, int):
            index[(str(source.get("set")), case_no)] = entry
    return index


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
@dataclass
class PolicyGapReport:
    """One report over one or more run directories."""

    runs: Tuple[RunReading, ...]
    min_cases: int
    dropped_pairs: Tuple[str, ...]
    clusters: Tuple[Cluster, ...]

    @property
    def readings(self) -> List[CaseReading]:
        return [reading for run in self.runs for reading in run.readings]

    @property
    def not_analysed(self) -> List[NotAnalysed]:
        return [item for run in self.runs for item in run.not_analysed]

    @property
    def flagged(self) -> List[Cluster]:
        return [cluster for cluster in self.clusters if cluster.flagged]

    def cluster(self, cluster_id: str) -> Optional[Cluster]:
        for cluster in self.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None


def build_report(
    run_dirs: Sequence[Path],
    *,
    min_cases: int = DEFAULT_MIN_CASES,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> PolicyGapReport:
    """Read every run, drop the noise pairs, and cluster what is left."""
    if not run_dirs:
        raise PolicyGapError("at least one --run-dir is required")
    _refuse_both_wild_sets(
        (_set_of_run_directory(run_dir) for run_dir in run_dirs), command="report"
    )
    # Before any case is loaded: a sealed set this loop does not read is refused
    # by name, so the report cannot read its sealed record as the corpus and call
    # that "nothing could be analysed".
    for run_dir in run_dirs:
        assert_not_a_sealed_record_the_loop_does_not_read(run_dir)
    runs = tuple(read_run(Path(run_dir), prompts_dir=prompts_dir) for run_dir in run_dirs)

    combined: Dict[int, Tuple[str, ...]] = {}
    for run in runs:
        combined.update(run.signatures)
    dropped = dropped_noise_pairs(combined)

    readings: List[CaseReading] = []
    for run in runs:
        for reading in run.readings:
            reading.signature = tuple(
                pair for pair in run.signatures.get(reading.case_no, ())
                if pair not in dropped
            )
            readings.append(reading)

    return PolicyGapReport(
        runs=runs,
        min_cases=min_cases,
        dropped_pairs=dropped,
        clusters=build_clusters(readings, min_cases),
    )


def _human_decisions(
    cluster: Cluster, closures: Mapping[Tuple[str, int], Dict[str, Any]], readings: Mapping[int, CaseReading]
) -> Dict[str, int]:
    """How the human closures of a cluster's cases are distributed, by ruling."""
    tally: Dict[str, int] = {}
    for case_no in cluster.cases:
        reading = readings.get(case_no)
        if reading is None:
            continue
        entry = closures.get((reading.set_name, case_no))
        if entry is None:
            continue
        decision = entry.get("decision") or {}
        value = decision.get("ruling")
        if isinstance(value, str):
            tally[value] = tally.get(value, 0) + 1
    return tally


def case_detail(
    reading: CaseReading,
    closures: Mapping[Tuple[str, int], Dict[str, Any]],
) -> Dict[str, Any]:
    """One case as a cluster shows it: what it decided, and what a person decided."""
    entry = closures.get((reading.set_name, reading.case_no))
    closure = None
    if entry is not None:
        closure = {
            "precedent_id": entry.get("precedent_id"),
            "decision": dict(entry.get("decision") or {}),
            "clause_ids": list(entry.get("clause_ids") or []),
            "closed_by": entry.get("closed_by"),
        }
    return {
        "case_no": reading.case_no,
        "set": reading.set_name,
        "run_dir": _relative(reading.run_dir),
        "system_outcome": dict(reading.system_outcome),
        "confidence": None if reading.confidence is None else str(reading.confidence),
        "leading_referral_clause": reading.leading_referral_clause,
        "closure": closure,
        "awaiting_review": closure is None,
    }


def cluster_document(
    cluster: Cluster,
    readings: Mapping[int, CaseReading],
    closures: Mapping[Tuple[str, int], Dict[str, Any]],
) -> Dict[str, Any]:
    details = [
        case_detail(readings[case_no], closures)
        for case_no in cluster.cases
        if case_no in readings
    ]
    document = cluster.as_dict()
    document["case_details"] = details
    document["human_decisions"] = _human_decisions(cluster, closures, readings)
    document["closures"] = sum(1 for item in details if item["closure"] is not None)
    document["awaiting_review"] = [
        item["case_no"] for item in details if item["awaiting_review"]
    ]
    return document


def report_document(
    report: PolicyGapReport, closures: Mapping[Tuple[str, int], Dict[str, Any]]
) -> Dict[str, Any]:
    readings = {reading.case_no: reading for reading in report.readings}
    return {
        "runs": [
            {
                "run_dir": _relative(run.run_dir),
                "set": run.set_name,
                "cached_cases": list(run.cached_cases),
                "gap_cases": [reading.case_no for reading in run.readings],
            }
            for run in report.runs
        ],
        "min_cases": report.min_cases,
        "note": (
            "No model call was made. Of a case file this reads five fields and no "
            "others, and of a transcript it reads the vote and verification blocks "
            "and nothing else."
        ),
        "dropped_signature_pairs": list(report.dropped_pairs),
        "not_analysed": [item.as_dict() for item in report.not_analysed],
        "clusters": [
            cluster_document(cluster, readings, closures) for cluster in report.clusters
        ],
    }


# What a report says about a run it could not read at all, and about one it read
# and found no gap in. The two are different findings and a reader must not be
# able to take one for the other: "nothing could be analysed" says the report has
# no reading of the run, and "no case was left undecided" says the policy decided
# every case the report could read. A run whose briefs will not rebuild, whose
# recorded digests have moved, or which holds no case file at all is the first.
NOTHING_ANALYSED = "nothing could be analysed"
NO_UNDECIDED_CASE = "no case in the given runs was left undecided"


def analysed_cases(run: RunReading) -> int:
    """How many of a run's cached cases this report could analyse.

    A case is analysed when its brief rebuilds and its recorded digests have not
    moved; every other case is in ``not_analysed`` with the reason, so the two
    counts partition the cache. Zero is a finding about the report and not about
    the policy, which is why it is reported in those words rather than as an
    absence of gaps.
    """
    return len(run.cached_cases) - len(run.not_analysed)


def _run_line(run: RunReading) -> str:
    """One run's line in the report, in the words its own reading calls for."""
    if analysed_cases(run) == 0:
        return "- `{0}` ({1}) — {2} case(s) cached, and {3}".format(
            _relative(run.run_dir),
            run.set_name,
            len(run.cached_cases),
            NOTHING_ANALYSED,
        )
    return "- `{0}` ({1}) — {2} case(s) cached, {3} of them undecided".format(
        _relative(run.run_dir),
        run.set_name,
        len(run.cached_cases),
        len(run.readings),
    )


def render_report(
    report: PolicyGapReport, closures: Mapping[Tuple[str, int], Dict[str, Any]]
) -> str:
    """The report a person reads: the clusters, and the cases left out."""
    lines = [
        "# Policy gaps",
        "",
        "**No model call was made.** Every figure is read out of the recorded "
        "runs: each case's transcript vote block, its rebuilt brief, and the "
        "precedent library.",
        "",
        "Of a case file this reads five fields -- `case_no`, `ruling`, "
        "`brief_sha256`, `development_set` and `configuration` -- and no others, "
        "and of a transcript it reads the vote and verification blocks only. It "
        "never reads `matched`, a grade event or the answer key.",
        "",
        "The runs:",
        "",
    ]
    for run in report.runs:
        lines.append(_run_line(run))
    lines.append("")
    lines.append(
        "A cluster is flagged when it holds at least {0} case(s).".format(
            report.min_cases
        )
    )
    lines.append("")

    if report.dropped_pairs:
        lines.append(
            "Dropped from every signature, because each appears in at least 80% "
            "of the given runs' cases and so distinguishes none of them:"
        )
        lines.append("")
        for pair in report.dropped_pairs:
            lines.append("- `{0}`".format(pair))
        lines.append("")
    else:
        lines.append("No signature pair was dropped as noise.")
        lines.append("")

    if not report.clusters:
        if sum(analysed_cases(run) for run in report.runs) == 0:
            lines.append(
                "**Nothing could be analysed in the given runs, so there is no "
                "cluster to report.**"
            )
        else:
            lines.append(
                "**No case in the given runs was left undecided, so there is no "
                "cluster to report.**"
            )
        lines.append("")
    for cluster in report.clusters:
        lines.extend(_cluster_lines(cluster, report, closures))

    lines.append("Not analysed, and why:")
    lines.append("")
    if report.not_analysed:
        for item in report.not_analysed:
            lines.append(
                "- `{0}/{1}` — {2}".format(item.set_name, item.case_no, item.reason)
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _cluster_lines(
    cluster: Cluster,
    report: PolicyGapReport,
    closures: Mapping[Tuple[str, int], Dict[str, Any]],
) -> List[str]:
    readings = {reading.case_no: reading for reading in report.readings}
    document = cluster_document(cluster, readings, closures)
    lines = [
        "## {0} — {1} / {2}{3}".format(
            cluster.cluster_id,
            cluster.category,
            cluster.trigger,
            "" if not cluster.signature else " / " + ", ".join(cluster.signature),
        ),
        "",
        "{0} case(s); level {1}; {2}.".format(
            len(cluster.cases),
            cluster.level,
            "flagged" if cluster.flagged else "not flagged",
        ),
        "",
        "| case | set | system outcome | confidence | leading referral clause | human closure |",
        "|---|---|---|---|---|---|",
    ]
    for item in document["case_details"]:
        outcome = item["system_outcome"].get("ruling")
        closure = item["closure"]
        lines.append(
            "| `{0}` | {1} | {2} | {3} | {4} | {5} |".format(
                item["case_no"],
                item["set"],
                outcome if outcome is not None else "-",
                item["confidence"] if item["confidence"] is not None else "-",
                item["leading_referral_clause"] or "-",
                (
                    "{0} ({1})".format(
                        (closure["decision"] or {}).get("ruling"),
                        closure["precedent_id"],
                    )
                    if closure is not None
                    else "awaiting review"
                ),
            )
        )
    lines.append("")
    distribution = document["human_decisions"]
    if distribution:
        lines.append(
            "Human decisions: {0}.".format(
                ", ".join(
                    "{0} x{1}".format(name, count)
                    for name, count in sorted(distribution.items())
                )
            )
        )
    else:
        lines.append("Human decisions: none — the library holds no closure for these cases.")
    lines.append(
        "Awaiting review: {0}.".format(
            ", ".join(str(case_no) for case_no in document["awaiting_review"]) or "none"
        )
    )
    lines.append("")
    return lines


# --------------------------------------------------------------------------
# The drafter
# --------------------------------------------------------------------------
def _assert_no_answer_fields(node: Any, where: str = "policy drafter input") -> None:
    """Refuse an input that carries a forbidden field name anywhere.

    The same recursive walk the precedent library applies to an entry, so the
    control is one function and this is one more place it is applied.
    """
    precedents._assert_no_forbidden_field_names(node, where)


def drafter_input(
    policies: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    closures: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """What the drafter is given, assembled and then proved.

    The policies as loaded; for each case its dispute block and, per artifact,
    the ``evidence_id``, ``evidence_type``, ``admissibility`` and ``derived``
    facts -- no raw payload; and the human closures. The document is walked for
    a forbidden field name before it is returned, so what leaves this function
    carries no answer field whichever way the case files were written.
    """
    document = {
        "policy": {
            "general": dict(policies.get("general") or {}),
            "category": dict(policies.get("category") or {}),
        },
        "cases": list(cases),
        "closures": list(closures),
    }
    _assert_no_answer_fields(document)
    return document


def drafter_user_message(document: Mapping[str, Any]) -> str:
    return money.dumps_canonical(document)


def case_for_drafter(brief_object: Mapping[str, Any]) -> Dict[str, Any]:
    """One case's dispute block and its artifacts' facts, with no raw payload."""
    case = brief_object.get("case") or {}
    artifacts = []
    for artifact in case.get("evidence") or ():
        if not isinstance(artifact, Mapping):
            continue
        payload = artifact.get("payload")
        derived = payload.get("derived") if isinstance(payload, Mapping) else None
        artifacts.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "admissibility": artifact.get("admissibility"),
                "derived": derived,
            }
        )
    return {
        "case_no": case.get("case_no"),
        "dispute": dict(case.get("dispute") or {}),
        "artifacts": artifacts,
    }


def closure_for_drafter(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "precedent_id": entry.get("precedent_id"),
        "category": entry.get("category"),
        "decision": dict(entry.get("decision") or {}),
        "clause_ids": list(entry.get("clause_ids") or []),
        "amount_contested_sgd": entry.get("amount_contested_sgd"),
        "summary": entry.get("summary"),
        "closed_by": entry.get("closed_by"),
    }


def _clause_reference_tokens(text: Any) -> Tuple[str, ...]:
    if not isinstance(text, str):
        return ()
    return tuple(re.findall(r"POL-[A-Z]{2,4}-\d{2}", text))


def validate_draft(
    parsed: Any,
    *,
    policies: Mapping[str, Any],
    category: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Check one drafted answer. Returns ``(draft, "")`` or ``(None, reason)``.

    The checks are the shape, the id rules, the clause's category against the
    prefix's file, ``licenses`` within POL-GEN-03, and that every clause the
    draft mentions resolves in the loaded policy.
    """
    if not isinstance(parsed, Mapping):
        return None, "the answer is not a JSON object"

    expected = {"clause", "reproduces", "does_not_reproduce", "interacts_with"}
    missing = sorted(expected - set(parsed))
    extra = sorted(set(parsed) - expected)
    if missing or extra:
        return None, (
            "the answer carries the wrong fields: missing {0}, unexpected {1}".format(
                missing or "none", extra or "none"
            )
        )

    clause = parsed.get("clause")
    if not isinstance(clause, Mapping):
        return None, "the answer's clause is not an object"
    clause_missing = sorted(set(policy_versions.CLAUSE_FIELDS) - set(clause))
    clause_extra = sorted(set(clause) - set(policy_versions.CLAUSE_FIELDS))
    if clause_missing or clause_extra:
        return None, (
            "the clause carries the wrong fields: missing {0}, unexpected {1}".format(
                clause_missing or "none", clause_extra or "none"
            )
        )

    clause_id = clause.get("id")
    match = (
        policy_versions.CLAUSE_ID_RE.match(clause_id)
        if isinstance(clause_id, str)
        else None
    )
    if match is None:
        return None, (
            "the clause id {0!r} does not match {1}".format(
                clause_id, policy_versions.CLAUSE_ID_RE.pattern
            )
        )
    prefix = match.group(1)
    target = policy_versions.PREFIX_FILES[prefix]
    declared = clause.get("category")
    if declared != policy_versions.PREFIX_CATEGORY[prefix]:
        return None, (
            "the clause declares category {0!r}, and {1} is the {2!r} file".format(
                declared, target, policy_versions.PREFIX_CATEGORY[prefix]
            )
        )
    if declared != category:
        return None, (
            "the clause is for category {0!r} and the cluster is {1!r}".format(
                declared, category
            )
        )

    # Which loaded policy the clause would join. The category policy carries the
    # cluster's category; the general policy is always loaded.
    if prefix == "GEN":
        policy_key = "general"
    else:
        policy_key = "category"
    policy = policies.get(policy_key)
    if not isinstance(policy, Mapping):
        return None, (
            "the clause joins {0}, which this case's brief does not carry".format(target)
        )

    numbers = [
        int(item.group(2))
        for item in (
            policy_versions.CLAUSE_ID_RE.match(existing.get("id"))
            if isinstance(existing, Mapping) and isinstance(existing.get("id"), str)
            else None
            for existing in (policy.get("clauses") or ())
        )
        if item is not None and item.group(1) == prefix
    ]
    next_free = max(numbers) + 1 if numbers else 1
    if int(match.group(2)) != next_free:
        return None, (
            "{0} is not the next free {1} clause; that is POL-{1}-{2:02d}".format(
                clause_id, prefix, next_free
            )
        )

    licenses = clause.get("licenses")
    if not isinstance(licenses, list) or not licenses:
        return None, "the clause's licenses is not a non-empty list"
    allowed = _general_licenses(policies)
    outside = [value for value in licenses if value not in allowed]
    if outside:
        return None, (
            "the clause licenses {0}, and POL-GEN-03 licenses {1}".format(
                ", ".join(str(value) for value in outside), ", ".join(allowed)
            )
        )

    known = set(_clause_ids(policies))
    mentioned = set()
    for name in ("rule", "notes"):
        mentioned.update(_clause_reference_tokens(clause.get(name)))
    for name in ("interacts_with",):
        value = parsed.get(name)
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            return None, "{0} is not a list of clause ids".format(name)
        mentioned.update(value)
    mentioned.discard(clause_id)
    unresolved = sorted(item for item in mentioned if item not in known)
    if unresolved:
        return None, (
            "the draft names clause(s) that do not resolve: {0}".format(
                ", ".join(unresolved)
            )
        )

    reproduces = parsed.get("reproduces")
    if not isinstance(reproduces, list) or any(
        not isinstance(item, str) for item in reproduces
    ):
        return None, "reproduces is not a list of precedent ids"

    does_not = parsed.get("does_not_reproduce")
    if not isinstance(does_not, list):
        return None, "does_not_reproduce is not a list"
    for entry in does_not:
        if not isinstance(entry, Mapping):
            return None, "does_not_reproduce holds an entry that is not an object"
        if not isinstance(entry.get("precedent_id"), str):
            return None, "does_not_reproduce holds an entry with no precedent_id"
        if not isinstance(entry.get("reason"), str) or not entry.get("reason").strip():
            return None, (
                "does_not_reproduce entry {0!r} carries no reason".format(
                    entry.get("precedent_id")
                )
            )

    return dict(parsed), ""


def _general_licenses(policies: Mapping[str, Any]) -> Tuple[str, ...]:
    general = policies.get("general") or {}
    for clause in general.get("clauses") or ():
        if isinstance(clause, Mapping) and clause.get("id") == "POL-GEN-03":
            return tuple(str(item) for item in (clause.get("licenses") or ()))
    return ()


def _clause_ids(policies: Mapping[str, Any]) -> Tuple[str, ...]:
    found: List[str] = []
    for key in ("general", "category"):
        policy = policies.get(key) or {}
        for clause in policy.get("clauses") or ():
            if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
                found.append(clause["id"])
    return tuple(found)


def slug_for(clause_id: str) -> str:
    """``POL-RD-13`` becomes ``pol-rd-13``, the slug an amendment file uses."""
    return re.sub(r"[^a-z0-9]+", "-", str(clause_id).lower()).strip("-")


def next_proposal_number(root: Optional[Any] = None) -> int:
    """The next free proposal number, continuing the amendment sequence."""
    directory = proposals_directory(root)
    highest = 0
    if directory.is_dir():
        for path in directory.iterdir():
            match = re.match(r"^(\d{4})-", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return max(policy_versions.current_version(), highest + 1)


def _default_client_factory(model: str, timeout_seconds: float):
    def build(sink):
        return llm.LLMClient(
            model=model, timeout_seconds=timeout_seconds, record_sink=sink
        )

    return build


def draft_proposal(
    report: PolicyGapReport,
    cluster: Cluster,
    *,
    store: Optional[Any] = None,
    proposals_root: Optional[Any] = None,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
    model: str,
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS,
    client_factory: Optional[Callable[[Callable[[Dict[str, Any]], None]], Any]] = None,
    report_file: Optional[Path] = None,
    now: Optional[Callable[[], str]] = None,
) -> Tuple[Optional[Path], str]:
    """Draft one clause for one cluster. Returns ``(proposal_path, "")`` or ``(None, reason)``.

    Refused before any call when the cluster is not flagged, when it has fewer
    than two human closures, or when the report names no report file to record.
    """
    if not cluster.flagged:
        return None, (
            "cluster {0} is not flagged: it holds {1} case(s) and at least {2} "
            "are needed".format(cluster.cluster_id, len(cluster.cases), report.min_cases)
        )

    closures = closure_index(store)
    readings = {reading.case_no: reading for reading in report.readings}
    chosen = [
        reading
        for case_no in cluster.cases
        for reading in (readings.get(case_no),)
        if reading is not None
    ]
    closed = [
        (reading, closures[(reading.set_name, reading.case_no)])
        for reading in chosen
        if (reading.set_name, reading.case_no) in closures
    ]
    if len(closed) < 2:
        return None, (
            "cluster {0} has {1} human closure(s) and at least 2 are needed "
            "before a clause can be drafted from it".format(
                cluster.cluster_id, len(closed)
            )
        )

    if report_file is None:
        return None, "the report path must be named, so the proposal can record it"

    policies = loader.load_policies(cluster.category, policy_versions.current_version())
    cases = []
    for reading in chosen:
        brief_object = brief.build_brief_for_case(
            development_sets.named(reading.set_name).load_case(reading.case_no),
            ablate=reading.ablation,
            policy_version=reading.policy_version,
        )
        cases.append(case_for_drafter(brief_object))
    document = drafter_input(
        policies, cases, [closure_for_drafter(entry) for _reading, entry in closed]
    )

    system_prompt = (Path(prompts_dir) / POLICY_DRAFTER_PROMPT_FILE).read_text(
        encoding="utf-8"
    )
    user_message = drafter_user_message(document)

    build_client = (
        _default_client_factory(model, timeout_seconds)
        if client_factory is None
        else client_factory
    )
    transcript = transcript_module.Transcript(now=now)
    client = build_client(lambda record: None)
    result = client.complete(
        system_prompt,
        user_message,
        response_format=llm.JSON_OBJECT_FORMAT,
    )
    transcript.record(
        role=transcript_module.ROLE_POLICY_DRAFTER,
        system_prompt=system_prompt,
        user_message=user_message,
        result=result,
    )

    parsed = result.json_body
    draft, reason = validate_draft(parsed, policies=policies, category=cluster.category)

    directory = proposals_directory(proposals_root)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (now or (lambda: datetime.now(timezone.utc).isoformat()))()
    number = next_proposal_number(proposals_root)

    if draft is None:
        slug = "{0}-{1}".format("{0:04d}".format(number), cluster.cluster_id.lower())
        (directory / (slug + ".transcript.json")).write_text(
            transcript.to_json(), encoding="utf-8"
        )
        (directory / (slug + ".rejected.json")).write_text(
            money.dumps_canonical(
                {
                    "status": REJECTED_BY_CODE,
                    "reason": reason,
                    "cluster_id": cluster.cluster_id,
                    "cases": list(cluster.cases),
                    "model": model,
                    "created_at": stamp,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return None, reason

    slug = "{0:04d}-{1}".format(number, slug_for(draft["clause"]["id"]))
    proposal = {
        "status": PROPOSAL_STATUS_PROPOSED,
        "cluster_id": cluster.cluster_id,
        "cases": list(cluster.cases),
        "category": cluster.category,
        "trigger": cluster.trigger,
        "signature": list(cluster.signature),
        "report_file": _relative(report_file),
        "report_sha256": _sha256_of_file(Path(report_file)),
        "model": model,
        "created_at": stamp,
        "clause": dict(draft["clause"]),
        "reproduces": list(draft["reproduces"]),
        "does_not_reproduce": list(draft["does_not_reproduce"]),
        "interacts_with": list(draft["interacts_with"]),
    }
    proposal_path = directory / (slug + ".json")
    proposal_path.write_text(money.dumps_canonical(proposal) + "\n", encoding="utf-8")
    (directory / (slug + ".transcript.json")).write_text(
        transcript.to_json(), encoding="utf-8"
    )
    return proposal_path, ""


# --------------------------------------------------------------------------
# approve / reject
# --------------------------------------------------------------------------
def next_free_number(policy_path: Path, prefix: str) -> int:
    """The next free clause number for ``prefix`` in one policy file."""
    document = run_benchmark.read_json(Path(policy_path)) or {}
    numbers = []
    for clause in document.get("clauses") or ():
        if not isinstance(clause, Mapping):
            continue
        clause_id = clause.get("id")
        match = (
            policy_versions.CLAUSE_ID_RE.match(clause_id)
            if isinstance(clause_id, str)
            else None
        )
        if match is not None and match.group(1) == prefix:
            numbers.append(int(match.group(2)))
    return max(numbers) + 1 if numbers else 1


def approve_proposal(
    proposal_file: Path,
    *,
    approved_by: str,
    amendments_root: Optional[Any] = None,
    base_version: int = policy_versions.BASE_VERSION,
    now: Optional[Callable[[], str]] = None,
) -> Tuple[int, Path]:
    """Write the amendment for one proposal, on ``base_version``. Returns ``(new_version, path)``.

    ``base_version`` is the policy base the clause joins: 1 for the amendment
    sequence the repository shipped with, or a separate base -- 3, Ji Guofang's
    platform-aligned policy. The amendment is written under **that base's** own
    amendments directory, numbered from ``0001`` within it, and the version it
    computes is ``base_version`` plus its number. So the first amendment on base 3
    is ``policy/v3/amendments/0001-<slug>.json`` and makes version 4.

    The refusal that matters is unchanged: an amendment may not compute a version
    another base owns, so a **second** amendment on base 1 is still refused, and
    an amendment on base 3 whose version is base 3's own is allowed.
    """
    proposal_file = Path(proposal_file)
    proposal = run_benchmark.read_json(proposal_file)
    if not isinstance(proposal, Mapping):
        raise PolicyGapError("there is no proposal at {0}".format(proposal_file))
    if proposal.get("status") != PROPOSAL_STATUS_PROPOSED:
        raise PolicyGapError(
            "the proposal at {0} has status {1!r}; only a PROPOSED proposal can "
            "be approved".format(proposal_file, proposal.get("status"))
        )
    clause = proposal.get("clause")
    if not isinstance(clause, Mapping):
        raise PolicyGapError("the proposal carries no clause")

    clause_id = clause.get("id")
    match = (
        policy_versions.CLAUSE_ID_RE.match(clause_id)
        if isinstance(clause_id, str)
        else None
    )
    if match is None:
        raise PolicyGapError(
            "the proposal's clause id {0!r} is not a policy clause id".format(clause_id)
        )
    prefix = match.group(1)
    target = policy_versions.PREFIX_FILES[prefix]
    if clause.get("category") != policy_versions.PREFIX_CATEGORY[prefix]:
        raise PolicyGapError(
            "the proposal's clause declares category {0!r}, and {1} is the "
            "{2!r} file".format(
                clause.get("category"), target, policy_versions.PREFIX_CATEGORY[prefix]
            )
        )
    # The next free number is read off the **repository's own** file for this
    # base: ``policy/`` for base 1, ``policy/v3/`` for base 3. The amendment is
    # written wherever the caller names, but the clause numbers a proposal has to
    # match are the ones the policy the repository briefs at carries.
    base_policy_dir = policy_versions.base_directory(base_version)
    free = next_free_number(base_policy_dir / target, prefix)
    if int(match.group(2)) != free:
        raise PolicyGapError(
            "the proposal adds {0}, and the next free {1} clause is POL-{1}-{2:02d}".format(
                clause_id, prefix, free
            )
        )

    directory = amendments_directory(amendments_root, base_version)
    number = policy_versions.amendments_on(base_version, amendments_root) + 1
    new_version = base_version + number
    # An amendment numbered N on base B computes policy version B + N. Since
    # 2026-10-08 version 3 is a separate policy base of its own, kept at
    # ``policy/v3/``, so amendment 0002 on base 1 would be a second policy under
    # one number -- and ``loader.load_policies`` would read the separate base's own
    # files for it. Refused before the directory is created, so a refused approval
    # writes nothing at all. It is this module's own error type, like every other
    # refusal an approve can make.
    try:
        policy_versions.refuse_a_taken_version(new_version, base_version)
    except policy_versions.AmendmentError as exc:
        raise PolicyGapError(str(exc))
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (now or (lambda: datetime.now(timezone.utc).isoformat()))()

    amendment = {
        "base_version": base_version,
        "proposal_file": _relative(proposal_file),
        "proposal_sha256": _sha256_of_file(proposal_file),
        "report_file": proposal.get("report_file"),
        "report_sha256": proposal.get("report_sha256"),
        "cluster_id": proposal.get("cluster_id"),
        "cases": list(proposal.get("cases") or []),
        "approved_by": approved_by,
        "approved_at": stamp,
        "clause": dict(clause),
    }

    path = directory / "{0:04d}-{1}.json".format(number, slug_for(clause_id))
    path.write_text(money.dumps_canonical(amendment) + "\n", encoding="utf-8")
    try:
        policy_versions.load_amendment(path, base_version=base_version)
    except policy_versions.AmendmentError:
        path.unlink()
        raise
    return new_version, path


def reject_proposal(
    proposal_file: Path,
    *,
    rejected_by: str,
    reason: str,
    now: Optional[Callable[[], str]] = None,
) -> Path:
    """Record a rejection in the proposal file itself."""
    proposal_file = Path(proposal_file)
    proposal = run_benchmark.read_json(proposal_file)
    if not isinstance(proposal, Mapping):
        raise PolicyGapError("there is no proposal at {0}".format(proposal_file))
    stamp = (now or (lambda: datetime.now(timezone.utc).isoformat()))()
    updated = dict(proposal)
    updated["status"] = PROPOSAL_STATUS_REJECTED
    updated["rejected_by"] = rejected_by
    updated["rejected_at"] = stamp
    updated["rejection_reason"] = reason
    proposal_file.write_text(money.dumps_canonical(updated) + "\n", encoding="utf-8")
    return proposal_file


# --------------------------------------------------------------------------
# rerun
# --------------------------------------------------------------------------
def load_amendment_file(number: int, amendments_root: Optional[Any] = None) -> Dict[str, Any]:
    """One amendment by its number, or a refusal naming the numbers that exist."""
    directory = amendments_directory(amendments_root)
    matches = sorted(directory.glob("{0:04d}-*.json".format(number)))
    if not matches:
        available = [
            path.name for path in policy_versions.amendment_files(amendments_root)
        ]
        raise PolicyGapError(
            "there is no amendment {0:04d} under {1}; on disk: {2}".format(
                number, directory, ", ".join(available) or "none"
            )
        )
    return policy_versions.load_amendment(matches[0])


def recorded_tokens(document: Mapping[str, Any]) -> int:
    """The tokens a case file records, and nothing else from the file.

    A cost, not an answer: ``rerun`` prints an estimate summed from these, which
    is the one field beyond the five the loop reads.
    """
    tokens = document.get("tokens")
    value = tokens.get("total_tokens") if isinstance(tokens, Mapping) else None
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def transcript_recorded_tokens(path: Path) -> int:
    """The tokens a transcript records, summed the way a case file sums them.

    A case file's ``tokens.total_tokens`` is the prompt plus the completion of
    every call the case made, so a case whose only record is its transcript is
    costed the same way and the estimate stays comparable across the two. Like
    ``tokens``, this is a cost and not an answer.
    """
    payload = run_benchmark.read_json(Path(path))
    entries = payload.get("entries") if isinstance(payload, Mapping) else None
    total = 0
    for entry in entries or ():
        if not isinstance(entry, Mapping):
            continue
        total += run_benchmark.billed_tokens(
            entry.get("prompt_tokens"), entry.get("completion_tokens")
        )
    return total


def recorded_cases(
    run_dir: Path, development_set: development_sets.DevelopmentSet
) -> List[Tuple[int, int, str]]:
    """The cases one run recorded, and how each one's cost was recorded.

    The list comes from the **set's own case list** and not from the case files
    on disk. A case the run recorded only a transcript for is still a case the
    run produced -- the held-out set has two of them, 517 and 533 -- and a
    listing taken from the files would leave them out of a re-run entirely. A
    case the set does not hold is never included, whichever file happens to be
    sitting in the directory.

    Each case's cost is read from its case file when there is one and from its
    transcript when that is all there is, and the third element says which, so a
    reader can tell an estimate read off a recorded result from one summed out
    of a transcript.
    """
    recorded: List[Tuple[int, int, str]] = []
    for case_no in development_set.cases:
        document = run_benchmark.read_json(
            run_benchmark.case_cache_path(run_dir, case_no)
        )
        if isinstance(document, Mapping):
            recorded.append((case_no, recorded_tokens(document), "case_file"))
            continue
        transcript_file = run_benchmark.transcript_path(run_dir, case_no)
        if transcript_file.is_file():
            recorded.append(
                (case_no, transcript_recorded_tokens(transcript_file), "transcript")
            )
    return recorded


def plan_rerun(
    number: int,
    run_dirs: Sequence[Path],
    *,
    amendments_root: Optional[Any] = None,
    runs_dir: Path = RUNS_DIR,
) -> Dict[str, Any]:
    """The case list and the token estimate, with nothing run and nothing written.

    A source under the held-out set's root is planned as its re-runnable twin:
    the same cases, run into ``runs/wild-dev/policy-v<N>/<model>/``. The record
    keeps both names, so a reader can tell which set a source was read as from
    which set it will be run as.

    A run directory of a sealed set this loop does not read is refused **before
    the amendment is read**, the way :func:`build_report` refuses it: the
    refusal is about the directory the caller named, so it must not depend on
    the amendment file being loadable.
    """
    _refuse_both_wild_sets(
        (_set_of_run_directory(run_dir) for run_dir in run_dirs), command="rerun"
    )
    # Before the amendment: the set's root holds a sealed record this loop does
    # not read, and reading it as the corpus would plan a rerun of nothing.
    for run_dir in run_dirs:
        assert_not_a_sealed_record_the_loop_does_not_read(run_dir)
    amendment = load_amendment_file(number, amendments_root)
    clause = amendment.get("clause") or {}
    category = clause.get("category")
    cluster_cases = [int(item) for item in amendment.get("cases") or []]

    sources: List[Dict[str, Any]] = []
    per_case: Dict[int, Dict[str, Any]] = {}
    for run_dir in run_dirs:
        run_dir = assert_not_an_external_run_directory(run_dir, runs_dir)
        source_set = precedents.set_from_run_directory(run_dir)
        # A source that is the held-out record is re-run as its re-runnable
        # twin: the same cases, under a root that may be written to.
        set_name = RERUN_SET_FOR.get(source_set, source_set)
        development_set = development_sets.named(set_name)
        regression: List[int] = []
        for case_no, tokens, origin in recorded_cases(run_dir, development_set):
            case = development_set.load_case(case_no)
            if (case.get("dispute") or {}).get("category") != category:
                continue
            regression.append(case_no)
            if case_no not in per_case:
                per_case[case_no] = {
                    "case_no": case_no,
                    "set": set_name,
                    "source_set": source_set,
                    "source_dir": run_dir,
                    "recorded_tokens": tokens,
                    "recorded_tokens_from": origin,
                }
        sources.append(
            {
                "run_dir": run_dir,
                "set": set_name,
                "source_set": source_set,
                "regression_cases": sorted(regression),
            }
        )

    for case_no in cluster_cases:
        if case_no in per_case:
            per_case[case_no]["in_cluster"] = True
            continue
        # A cluster case from a run the caller did not name: it still has to be
        # run, but there is no recorded cost to read for it.
        per_case[case_no] = {
            "case_no": case_no,
            "set": None,
            "source_set": None,
            "source_dir": None,
            "recorded_tokens": 0,
            "recorded_tokens_from": None,
            "in_cluster": True,
        }
    for case_no, item in per_case.items():
        item.setdefault("in_cluster", case_no in cluster_cases)

    affected = sorted(per_case)
    estimate = sum(item["recorded_tokens"] for item in per_case.values())
    return {
        "amendment": "{0:04d}".format(number),
        "policy_version": number + 1,
        "category": category,
        "cluster_id": amendment.get("cluster_id"),
        "cluster_cases": cluster_cases,
        "regression_cases": sorted(
            case_no for case_no in affected if not per_case[case_no]["in_cluster"]
        ),
        "affected_cases": affected,
        "sources": sources,
        "estimate_tokens": estimate,
        "cases": [per_case[case_no] for case_no in affected],
    }


def rerun_amendment(
    number: int,
    run_dirs: Sequence[Path],
    *,
    model: str,
    runs_dir: Path = RUNS_DIR,
    amendments_root: Optional[Any] = None,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
    yes: bool = False,
    client_factory: Optional[Callable[[Callable[[Dict[str, Any]], None]], Any]] = None,
    git_runner: Optional[Callable[[Sequence[str]], Optional[str]]] = None,
    progress: Callable[[str], None] = lambda text: print(text, flush=True),
    now: Optional[Callable[[], str]] = None,
) -> Tuple[Optional[Path], str]:
    """Run the affected cases at the new version, or refuse and say what it would run.

    Returns ``(rerun_record, "")`` when it ran, and ``(None, reason)`` when it
    stopped. Without ``yes`` it prints the plan and refuses, making no call.
    """
    plan = plan_rerun(number, run_dirs, amendments_root=amendments_root, runs_dir=runs_dir)
    version = plan["policy_version"]
    affected = plan["affected_cases"]
    if not affected:
        return None, "no case is affected by amendment {0:04d}".format(number)

    progress(
        "amendment {0}: policy version {1}, {2} case(s) to run, about {3} "
        "recorded token(s)".format(plan["amendment"], version, len(affected), plan["estimate_tokens"])
    )
    for item in plan["cases"]:
        progress(
            "  case {0} ({1}) — {2} recorded token(s){3}{4}".format(
                item["case_no"],
                item["set"] or "unnamed run",
                item["recorded_tokens"],
                ""
                if item["recorded_tokens_from"] is None
                else ", {0}".format(TOKENS_FROM[item["recorded_tokens_from"]]),
                " [cluster]" if item["in_cluster"] else " [regression]",
            )
        )

    if not yes:
        return None, (
            "refusing to run without --yes: {0} case(s) would be run at policy "
            "version {1}".format(len(affected), version)
        )

    # A brief is built by ``loader.load_policies``, which reads the repository's
    # own ``policy/amendments/`` and takes no root. So a policy version exists
    # only when its amendment is *there*, and the runner checks the version
    # against that directory. An amendment found under some other root names a
    # version no case can be briefed at, and the runner would say so once per
    # case; the loop says it once, here, and names both directories. This branch
    # cannot fire when the amendment was found in the repository's own
    # directory, because then the version is already within reach. It is asked
    # only once the run is going ahead: without ``yes`` nothing is run and
    # nothing is written, so the plan is printed and the version is left alone.
    available = policy_versions.current_version()
    if version > available:
        raise PolicyGapError(
            "amendment {0:04d} is under {1} and names policy version {2}, and this "
            "repository is at version {3}. Every brief is built from {4} -- that is "
            "the directory loader.load_policies reads -- so version {2} cannot be "
            "run until the amendment is approved into it.".format(
                number,
                amendments_directory(amendments_root),
                version,
                available,
                amendments_directory(None),
            )
        )

    destinations: Dict[str, str] = {}
    by_set: Dict[str, List[int]] = {}
    for item in plan["cases"]:
        if item["set"] is None:
            raise PolicyGapError(
                "case {0} is not in any run directory given, so this loop cannot "
                "say which development set it belongs to".format(item["case_no"])
            )
        by_set.setdefault(item["set"], []).append(item["case_no"])

    for set_name, cases in sorted(by_set.items()):
        development_set = development_sets.named(set_name)
        set_runs_root = development_set.runs_dir(runs_dir)
        summary = run_benchmark.run_benchmark(
            model,
            sorted(cases),
            runs_dir=set_runs_root,
            prompts_dir=prompts_dir,
            policy_version=version,
            case_loader=development_set.load_case,
            key=development_set.key(),
            key_path=development_set.key_path,
            label=None if development_set.runs_subdir is None else development_set.name,
            client_factory=client_factory,
            git_runner=git_runner,
            progress=progress,
            now=now or (lambda: datetime.now(timezone.utc).isoformat()),
        )
        destinations[set_name] = _relative(
            run_benchmark.policy_v_run_directory(set_runs_root, version, model)
        )

    stamp = (now or (lambda: datetime.now(timezone.utc).isoformat()))()
    record = dict(plan)
    record["model"] = model
    record["destinations"] = destinations
    record["created_at"] = stamp
    record["sources"] = [
        {"run_dir": _relative(item["run_dir"]), "set": item["set"],
         "source_set": item["source_set"],
         "regression_cases": item["regression_cases"]}
        for item in plan["sources"]
    ]
    record["cases"] = [
        {
            "case_no": item["case_no"],
            "set": item["set"],
            "source_set": item["source_set"],
            "source_dir": None if item["source_dir"] is None else _relative(item["source_dir"]),
            "destination": destinations.get(item["set"]),
            "recorded_tokens": item["recorded_tokens"],
            "recorded_tokens_from": item["recorded_tokens_from"],
            "in_cluster": item["in_cluster"],
        }
        for item in plan["cases"]
    ]

    out_dir = Path(runs_dir) / run_benchmark.policy_v_directory_name(version)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / RERUN_FILE
    path.write_text(money.dumps_canonical(record) + "\n", encoding="utf-8")
    return path, ""


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------
def _referral_references(referrals: Any) -> Tuple[str, ...]:
    """The clause reference each referral leads with, limb included, in order.

    The grader compares referral lists by the clause references they carry and
    not by their prose, so the diff compares them the same way -- and it keeps
    the limb, because a limb is part of the reference and the grader treats it
    as significant where the key states one. A referral whose wording moved
    while its clause reference did not is not a change to the graded field, and
    reporting it as one would put ``changed: yes`` in a row whose two sides
    render identically -- a contradiction a reader cannot resolve without
    opening both case files.

    A referral that leads with no clause reference at all keeps
    :data:`tribunal.pipeline.NO_LEADING_CLAUSE`, which is a value of its own
    rather than an absence, so a list that gains one reads as changed and two
    such referrals do not compare equal to none.
    """
    if not isinstance(referrals, (list, tuple)):
        return ()
    return tuple(pipeline.leading_clause_reference(referral) for referral in referrals)


def _render_amount(value: Any) -> str:
    """One money field, rendered so that equal values render equally.

    A value that is a number with at most two decimal places is rendered at two
    places, so ``4.0`` and ``4.00`` -- the same money, written by two different
    writers -- render the same and the ``changed`` column cannot contradict the
    row it sits in. A value that is not such a number is rendered as the file
    carries it, so an anomaly stays visible rather than being rounded into a
    plausible figure.
    """
    number = as_decimal(value)
    if number is None:
        return grade.render_money(value)
    try:
        if number == number.quantize(CENTS):
            return str(number.quantize(CENTS))
    except (InvalidOperation, ArithmeticError):
        pass
    return grade.render_money(value)


def _render_fields(fields: Mapping[str, Any]) -> Dict[str, Any]:
    """The four graded fields as the diff shows them, and as it compares them.

    A referral is rendered as the clause reference it leads with, because that
    is the part the comparison turns on; the referral's own wording is not
    carried, so the diff stays an index of what moved rather than a copy of two
    rulings. The full ruling of either side is in that run's own case file.

    Money is rendered by :func:`_render_amount` and each referral by
    :func:`_referral_references`, and ``changed`` is computed from *this* -- so
    whatever the rendering does not distinguish, the comparison does not count
    as a change either, and the two cannot disagree.
    """
    return {
        name: (
            _render_amount(fields.get(name))
            if name in ("amount_sgd", "driver_compensation_sgd")
            else (
                list(_referral_references(fields.get(name)))
                if name == "referrals"
                else fields.get(name)
            )
        )
        for name in RULING_FIELDS
    }


def _fields_differ(old: Mapping[str, Any], new: Mapping[str, Any]) -> bool:
    """Whether the four graded fields differ, as the diff renders them.

    Defined as a comparison of the rendered fields rather than as a second,
    parallel comparison, so the ``changed`` column cannot contradict the ``old``
    and ``new`` columns it sits between: money that differs only in its trailing
    zeros (``4.0`` against ``4.00``) and a referral that differs only in its
    wording (the same clause reference) are both not a change, and both render
    identically. ``null`` is still never zero, because the rendering keeps them
    apart.
    """
    return _render_fields(old) != _render_fields(new)


def _exact(case_no: int, key: Mapping[int, grade.Ruling], produced: Any) -> Optional[bool]:
    """Whether one produced ruling is a four-field match, or ``None`` without a key."""
    expected = key.get(case_no)
    if expected is None:
        return None
    try:
        scored = grade.produced_from_mapping(produced, case_no)
    except grade.GradeError:
        return False
    return grade.score_case(case_no, expected, scored).exact


def build_diff(
    number: int,
    *,
    runs_dir: Path = RUNS_DIR,
    amendments_root: Optional[Any] = None,
) -> Dict[str, Any]:
    """Compare the before and after rulings of one amendment's affected cases.

    **This is the one command that reads the answer key.** The development-set
    cases are graded before and after against the frozen version-1 key, and the
    output says so.
    """
    amendment = load_amendment_file(number, amendments_root)
    version = number + 1
    rerun_path = (
        Path(runs_dir) / run_benchmark.policy_v_directory_name(version) / RERUN_FILE
    )
    record = run_benchmark.read_json(rerun_path)
    if not isinstance(record, Mapping):
        raise PolicyGapError(
            "there is no rerun record at {0}; run the amendment first".format(rerun_path)
        )
    cluster_cases = [int(item) for item in amendment.get("cases") or []]
    _refuse_both_wild_sets(
        (
            _set_of_run_directory(item["run_dir"])
            for item in record.get("sources") or ()
            if isinstance(item, Mapping) and item.get("run_dir")
        ),
        command="diff",
    )
    # Before any case is loaded: a source or a destination that is a run
    # directory of a sealed set this loop does not read is refused by name, so a
    # hand-made record cannot make this command read a directory the loop is not
    # allowed to read.
    for item in record.get("sources") or ():
        if isinstance(item, Mapping) and item.get("run_dir"):
            assert_not_a_sealed_record_the_loop_does_not_read(Path(item["run_dir"]))
    for item in record.get("cases") or ():
        if not isinstance(item, Mapping):
            continue
        for key in ("source_dir", "destination"):
            if item.get(key):
                assert_not_a_sealed_record_the_loop_does_not_read(Path(item[key]))

    keys: Dict[str, Mapping[int, grade.Ruling]] = {}
    cases: List[Dict[str, Any]] = []
    for item in record.get("cases") or ():
        if not isinstance(item, Mapping):
            continue
        case_no = int(item["case_no"])
        set_name = item.get("set")
        source_dir = item.get("source_dir")
        destination = item.get("destination")
        old_document = (
            run_benchmark.read_json(
                run_benchmark.case_cache_path(Path(source_dir), case_no)
            )
            if source_dir
            else None
        )
        new_document = (
            run_benchmark.read_json(
                run_benchmark.case_cache_path(Path(destination), case_no)
            )
            if destination
            else None
        )
        old_inner = produced_inner(old_document) if isinstance(old_document, Mapping) else {}
        new_inner = produced_inner(new_document) if isinstance(new_document, Mapping) else {}
        old_fields = {name: old_inner.get(name) for name in RULING_FIELDS}
        new_fields = {name: new_inner.get(name) for name in RULING_FIELDS}

        # A destination case file that is not there is a **miss**, not a blank.
        # The held-out set has two cases that recorded only a transcript, and a
        # re-run that wrote no file for a case is a case the new version left
        # without a ruling -- which is a finding about the amendment. Reading it
        # as "nothing to compare" would hide exactly what the diff is for.
        new_no_ruling = bool(destination) and not isinstance(new_document, Mapping)

        key: Mapping[int, grade.Ruling] = {}
        if set_name and set_name not in keys:
            keys[set_name] = development_sets.named(set_name).key()
        if set_name:
            key = keys[set_name]

        old_exact = _exact(case_no, key, old_document.get("ruling")) if old_document else None
        if isinstance(new_document, Mapping):
            new_exact = _exact(case_no, key, new_document.get("ruling"))
        else:
            new_exact = False if destination else None

        cases.append(
            {
                "case_no": case_no,
                "set": set_name,
                "in_cluster": case_no in cluster_cases,
                "changed": _fields_differ(old_fields, new_fields),
                "old": _render_fields(old_fields),
                "new": _render_fields(new_fields),
                "old_exact": old_exact,
                "new_exact": new_exact,
                "new_no_ruling": new_no_ruling,
                "old_escalated": old_fields.get("ruling") == ESCALATE,
                "new_escalated": new_fields.get("ruling") == ESCALATE,
            }
        )

    return {
        "amendment": "{0:04d}".format(number),
        "policy_version": version,
        "model": record.get("model"),
        "cluster_id": record.get("cluster_id"),
        "cluster_cases": cluster_cases,
        "key_note": (
            "This command reads the frozen version-1 answer key, to grade each "
            "development-set case before and after. No other command in this "
            "module reads it, and the keys are never edited."
        ),
        # Version 2 carries two changes, not one, so a gain measured here is not
        # the amendment's alone. Empty at any other version: a later diff says
        # what *it* carries when it is written, rather than borrowing this.
        "version_note": VERSION_TWO_NOTE if version == 2 else "",
        "totals": _totals(cases, exclude=set()),
        "totals_without_the_cluster": _totals(cases, exclude=set(cluster_cases)),
        "cases": cases,
    }


def _totals(cases: Sequence[Mapping[str, Any]], *, exclude: set) -> Dict[str, Any]:
    """The totals over the cases not excluded. Counts, and no arithmetic but that."""
    chosen = [case for case in cases if case["case_no"] not in exclude]
    graded = [case for case in chosen if case["old_exact"] is not None]
    return {
        "cases": len(chosen),
        "graded": len(graded),
        "changed": sum(1 for case in chosen if case["changed"]),
        "newly_matching": sum(
            1
            for case in graded
            if case["old_exact"] is False and case["new_exact"] is True
        ),
        "newly_missing": sum(
            1
            for case in graded
            if case["old_exact"] is True and case["new_exact"] is False
        ),
        "escalations_before": sum(1 for case in chosen if case["old_escalated"]),
        "escalations_after": sum(1 for case in chosen if case["new_escalated"]),
    }


def render_diff(document: Mapping[str, Any]) -> str:
    lines = [
        "# Policy-gap diff — amendment {0} (policy version {1})".format(
            document["amendment"], document["policy_version"]
        ),
        "",
        "Model: {0}. Cluster: {1}.".format(
            document.get("model"), document.get("cluster_id")
        ),
        "",
        "**A change under a new policy is not necessarily an error.** The new "
        "version says something the old one did not, and a case that moved may "
        "have moved because the new clause is right.",
        "",
        "**The amendment was drafted from closures on these same sets, so the "
        "newly matching counts are in-sample and are not comparable to the "
        "headline.**",
        "",
        "`changed` compares the four graded fields: money as a decimal, so `4.0` "
        "and `4.00` are the same money and `null` is never zero, and each referral "
        "by the clause reference it leads with, which is how the grader compares "
        "it. A referral whose wording moved while its clause reference did not is "
        "therefore not a change, and the `old` and `new` columns show the "
        "references rather than the wording.",
        "",
        document["key_note"],
        "",
    ]
    if document.get("version_note"):
        lines.extend([document["version_note"], ""])
    lines.extend(
        [
            "| case | set | changed | old | new |",
            "|---|---|---|---|---|",
        ]
    )
    for case in document["cases"]:
        lines.append(
            "| `{0}` | {1} | {2} | {3} | {4} |".format(
                case["case_no"],
                case["set"] or "-",
                "yes" if case["changed"] else "no",
                _summarise(case["old"]),
                "no ruling" if case.get("new_no_ruling") else _summarise(case["new"]),
            )
        )
    lines.append("")
    lines.extend(_totals_lines("All affected cases", document["totals"]))
    lines.extend(
        _totals_lines(
            "Affected cases with the cluster's own cases excluded",
            document["totals_without_the_cluster"],
        )
    )
    return "\n".join(lines)


def _summarise(fields: Mapping[str, Any]) -> str:
    referrals = fields.get("referrals") or ()
    return "{0} / {1} / {2} / {3}".format(
        fields.get("ruling"),
        fields.get("amount_sgd"),
        fields.get("driver_compensation_sgd"),
        ", ".join(str(item) for item in referrals) if referrals else "-",
    )


def _totals_lines(label: str, totals: Mapping[str, Any]) -> List[str]:
    return [
        "## {0}".format(label),
        "",
        "- cases: {0} ({1} graded against the key)".format(
            totals["cases"], totals["graded"]
        ),
        "- changed: {0}".format(totals["changed"]),
        "- newly matching: {0}".format(totals["newly_matching"]),
        "- newly missing: {0}".format(totals["newly_missing"]),
        "- escalations before: {0}; after: {1}".format(
            totals["escalations_before"], totals["escalations_after"]
        ),
        "",
    ]


def write_diff(
    number: int,
    *,
    runs_dir: Path = RUNS_DIR,
    amendments_root: Optional[Any] = None,
) -> Tuple[Path, Path]:
    document = build_diff(number, runs_dir=runs_dir, amendments_root=amendments_root)
    out_dir = Path(runs_dir) / run_benchmark.policy_v_directory_name(document["policy_version"])
    # A diff is a file about the run, and the held-out set's run is not written
    # about under its own root either: a version directory beside it would change
    # what that root means. The rule is the runner's, so both refuse the same
    # paths.
    try:
        run_benchmark.assert_not_under_the_held_out_root(out_dir, runs_dir)
    except run_benchmark.BenchmarkError as exc:
        raise PolicyGapError(str(exc)) from None
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / DIFF_MD
    js = out_dir / DIFF_JSON
    md.write_text(render_diff(document), encoding="utf-8")
    js.write_text(money.dumps_canonical(document) + "\n", encoding="utf-8")
    return md, js


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.policy_gaps",
        description=(
            "The policy-gap loop: find the cases the policy could not decide, "
            "draft one clause for a cluster a human has closed, and compare the "
            "result. Only `draft` and `rerun` call a model."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="write the policy-gap report")
    report.add_argument("--run-dir", type=Path, action="append", required=True)
    report.add_argument("--min-cases", type=int, default=DEFAULT_MIN_CASES)
    report.add_argument("--store", type=Path, default=None)
    report.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    report.add_argument("--out-dir", type=Path, default=None)
    report.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    report.add_argument("--model", default=None)

    draft = sub.add_parser("draft", help="draft one clause for a cluster")
    draft.add_argument("--report", type=Path, required=True)
    draft.add_argument("--cluster", required=True)
    draft.add_argument("--store", type=Path, default=None)
    draft.add_argument("--proposals-dir", type=Path, default=None)
    draft.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    draft.add_argument("--model", default=None)
    draft.add_argument("--timeout", type=float, default=llm.DEFAULT_TIMEOUT_SECONDS)

    approve = sub.add_parser("approve", help="write the amendment for a proposal")
    approve.add_argument("--proposal", type=Path, required=True)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--amendments-dir", type=Path, default=None)
    # The base the clause joins. Version 1's amendment sequence is the default,
    # so an invocation that does not name a base is the one it always was; base 3
    # writes under ``policy/v3/amendments/`` and makes version 4.
    approve.add_argument(
        "--base-version", type=int, default=policy_versions.BASE_VERSION
    )

    reject = sub.add_parser("reject", help="record a rejection in the proposal")
    reject.add_argument("--proposal", type=Path, required=True)
    reject.add_argument("--by", required=True)
    reject.add_argument("--reason", required=True)

    rerun = sub.add_parser("rerun", help="run the affected cases at the new version")
    rerun.add_argument("--amendment", required=True)
    rerun.add_argument("--run-dir", type=Path, action="append", required=True)
    rerun.add_argument("--amendments-dir", type=Path, default=None)
    rerun.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    rerun.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    rerun.add_argument("--model", default=None)
    rerun.add_argument("--yes", action="store_true")

    diff = sub.add_parser("diff", help="compare the before and after rulings")
    diff.add_argument("--amendment", required=True)
    diff.add_argument("--amendments-dir", type=Path, default=None)
    diff.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    return parser


def _amendment_number(text: str) -> int:
    value = str(text).strip()
    if not value.isdigit():
        raise PolicyGapError(
            "{0!r} is not an amendment number; it is four digits, e.g. 0001".format(text)
        )
    return int(value)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "report":
            return _main_report(args)
        if args.command == "draft":
            return _main_draft(args)
        if args.command == "approve":
            return _main_approve(args)
        if args.command == "reject":
            return _main_reject(args)
        if args.command == "rerun":
            return _main_rerun(args)
        return _main_diff(args)
    except (
        PolicyGapError,
        policy_versions.AmendmentError,
        run_benchmark.BenchmarkError,
        sealed_roots.SealedDestinationError,
        precedents.PrecedentError,
        loader.LoaderError,
    ) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


def _main_report(args: argparse.Namespace) -> int:
    model = run_benchmark.resolve_model(args.model)
    out_dir = (
        policy_gaps_directory(args.runs_dir) if args.out_dir is None else Path(args.out_dir)
    )
    assert_not_a_run_directory(out_dir, args.runs_dir, model)
    report = build_report(
        args.run_dir, min_cases=args.min_cases, prompts_dir=Path(args.prompts_dir)
    )
    closures = closure_index(args.store)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_FILE).write_text(
        money.dumps_canonical(report_document(report, closures)) + "\n",
        encoding="utf-8",
    )
    (out_dir / REPORT_MD).write_text(
        render_report(report, closures) + "\n", encoding="utf-8"
    )

    print("Policy gaps — {0}".format(model))
    for run in report.runs:
        if analysed_cases(run) == 0:
            print(
                "  {0} ({1}): {2} cached, and {3}".format(
                    _relative(run.run_dir),
                    run.set_name,
                    len(run.cached_cases),
                    NOTHING_ANALYSED,
                )
            )
        else:
            print(
                "  {0} ({1}): {2} cached, {3} undecided".format(
                    _relative(run.run_dir),
                    run.set_name,
                    len(run.cached_cases),
                    len(run.readings),
                )
            )
    if not report.clusters:
        if sum(analysed_cases(run) for run in report.runs) == 0:
            print("  {0} in the given runs".format(NOTHING_ANALYSED))
        else:
            print("  {0}".format(NO_UNDECIDED_CASE))
    for cluster in report.clusters:
        print(
            "  {0} level {1} {2} / {3}: {4} case(s){5}".format(
                cluster.cluster_id,
                cluster.level,
                cluster.category,
                cluster.trigger,
                len(cluster.cases),
                "  FLAGGED" if cluster.flagged else "",
            )
        )
    print("Wrote {0}".format(_relative(out_dir / REPORT_FILE)))
    print("Wrote {0}".format(_relative(out_dir / REPORT_MD)))
    return 0


def _main_draft(args: argparse.Namespace) -> int:
    # The proposals directory is the caller's to name, so it is refused before
    # the report is read and before a proposal is written. The rule is
    # :mod:`eval.sealed_roots`'s, so this command and every other one that
    # writes to a path a caller names refuse the same paths.
    sealed_roots.refuse_a_sealed_destination(proposals_directory(args.proposals_dir))
    model = run_benchmark.resolve_model(args.model)
    document = run_benchmark.read_json(args.report)
    if not isinstance(document, Mapping):
        raise PolicyGapError("there is no report at {0}".format(args.report))
    report = _report_from_document(document)
    cluster = report.cluster(args.cluster)
    if cluster is None:
        raise PolicyGapError(
            "the report holds no cluster {0!r}".format(args.cluster)
        )
    path, reason = draft_proposal(
        report,
        cluster,
        store=args.store,
        proposals_root=args.proposals_dir,
        prompts_dir=Path(args.prompts_dir),
        model=model,
        timeout_seconds=args.timeout,
        report_file=args.report,
    )
    if path is None:
        print("FATAL: {0}".format(reason), file=sys.stderr)
        return 1
    print("Wrote {0}".format(_relative(path)))
    return 0


def _main_approve(args: argparse.Namespace) -> int:
    # The amendments directory is the caller's to name, so it is refused before
    # the proposal is read and before an amendment is written. The rule is
    # :mod:`eval.sealed_roots`'s, so this command and every other one that
    # writes to a path a caller names refuse the same paths.
    sealed_roots.refuse_a_sealed_destination(
        amendments_directory(args.amendments_dir, args.base_version)
    )
    version, path = approve_proposal(
        args.proposal,
        approved_by=args.approved_by,
        amendments_root=args.amendments_dir,
        base_version=args.base_version,
    )
    number = version - args.base_version
    print("policy version is now {0}".format(version))
    print("Wrote {0}".format(_relative(path)))
    print(
        "rerun: python3 -m eval.policy_gaps rerun --amendment {0:04d} "
        "--run-dir runs/<model-slug> --yes".format(number)
    )
    return 0


def _main_reject(args: argparse.Namespace) -> int:
    # A rejection rewrites the proposal file in place, so the path the caller
    # names is both read and written. Two refusals, both before the file is
    # opened: the sealed-root rule every command that writes to a named path
    # obeys -- without it ``reject`` would rewrite any JSON file it was handed,
    # a committed run file under either sealed root included -- and this
    # command's own rule that a proposal is a file under ``policy/proposals/``.
    proposal = Path(args.proposal).resolve()
    sealed_roots.refuse_a_sealed_destination(proposal)
    root = proposals_directory(None).resolve()
    folded = run_benchmark.path_components(proposal)
    root_parts = run_benchmark.path_components(root)
    if len(folded) <= len(root_parts) or folded[: len(root_parts)] != root_parts:
        raise PolicyGapError(
            "a proposal is a file under {0}, and {1} is not under it".format(
                _relative(root), proposal
            )
        )
    path = reject_proposal(proposal, rejected_by=args.by, reason=args.reason)
    print("Recorded the rejection in {0}".format(_relative(path)))
    return 0


def _main_rerun(args: argparse.Namespace) -> int:
    model = run_benchmark.resolve_model(args.model)
    number = _amendment_number(args.amendment)
    path, reason = rerun_amendment(
        number,
        args.run_dir,
        model=model,
        runs_dir=args.runs_dir,
        amendments_root=args.amendments_dir,
        prompts_dir=Path(args.prompts_dir),
        yes=args.yes,
    )
    if path is None:
        print("FATAL: {0}".format(reason), file=sys.stderr)
        return 1
    print("Wrote {0}".format(_relative(path)))
    return 0


def _main_diff(args: argparse.Namespace) -> int:
    number = _amendment_number(args.amendment)
    md, js = write_diff(
        number, runs_dir=args.runs_dir, amendments_root=args.amendments_dir
    )
    print("Wrote {0}".format(_relative(md)))
    print("Wrote {0}".format(_relative(js)))
    return 0


# --------------------------------------------------------------------------
# Rebuilding a report from its own file, for `draft`
# --------------------------------------------------------------------------
def _report_from_document(document: Mapping[str, Any]) -> PolicyGapReport:
    """A report as ``draft`` needs it, rebuilt from the file ``report`` wrote.

    Only what ``draft`` uses is rebuilt: the clusters, and enough of each case
    to name it and rebuild its brief. Nothing here reads a run.

    A document that is not a report -- a truncated write, a hand-edited file,
    something that was never a report at all -- is refused with a reason rather
    than raising whatever the parse happened to hit. ``draft``'s job is to
    refuse when it cannot do what it was asked, and a traceback names neither
    the file nor the field that was wrong.
    """
    try:
        return _report_from_document_or_raise(document)
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise PolicyGapError(
            "the report file cannot be read as a policy-gap report: {0}: {1}".format(
                type(exc).__name__, exc
            )
        ) from None


def _report_from_document_or_raise(document: Mapping[str, Any]) -> PolicyGapReport:
    # A case appears once in every cluster that holds it -- its coarse cluster
    # and, when its signature says something, the fine one -- so the details are
    # read once per case and the highest level wins: that is the level whose
    # signature is the case's own.
    chosen: Dict[Tuple[str, int], Tuple[int, CaseReading]] = {}
    for cluster in document.get("clusters") or ():
        if not isinstance(cluster, Mapping):
            continue
        level = int(cluster.get("level") or 1)
        for item in cluster.get("case_details") or ():
            if not isinstance(item, Mapping):
                continue
            reading = CaseReading(
                run_dir=PROJECT_ROOT / str(item.get("run_dir")),
                set_name=str(item.get("set")),
                case_no=int(item["case_no"]),
                category=str(cluster.get("category")),
                policy_version=int(document.get("policy_version") or 1),
                ablation=None,
                ruling=(item.get("system_outcome") or {}).get("ruling"),
                confidence=as_decimal(item.get("confidence")),
                system_outcome=dict(item.get("system_outcome") or {}),
                leading_referral_clause=item.get("leading_referral_clause"),
                vote_outcome=None,
                valid=None,
                threshold=None,
                abstained=(),
                trigger=str(cluster.get("trigger")),
                signature=tuple(cluster.get("signature") or ()),
            )
            key = (reading.set_name, reading.case_no)
            seen = chosen.get(key)
            if seen is None or level > seen[0]:
                chosen[key] = (level, reading)

    # A reading is looked up off the run it came from, because that is where
    # ``report.readings`` finds it. Every run the document names is rebuilt with
    # its own readings, and a reading whose run is not named gets a run of its
    # own rather than being dropped, so the rebuild loses no case.
    by_run: Dict[Tuple[str, str], List[CaseReading]] = {}
    for _level, reading in chosen.values():
        by_run.setdefault(
            (reading.set_name, reading.run_dir.as_posix()), []
        ).append(reading)

    def _readings_for(set_name: str, run_dir: Path) -> Tuple[CaseReading, ...]:
        return tuple(
            sorted(
                by_run.get((set_name, run_dir.as_posix()), []),
                key=lambda reading: reading.case_no,
            )
        )

    runs: List[RunReading] = []
    named: List[Tuple[str, str]] = []
    for run in document.get("runs") or ():
        if not isinstance(run, Mapping):
            continue
        set_name = str(run.get("set"))
        run_dir = PROJECT_ROOT / str(run.get("run_dir"))
        named.append((set_name, run_dir.as_posix()))
        runs.append(
            RunReading(
                run_dir=run_dir,
                set_name=set_name,
                cached_cases=tuple(int(item) for item in run.get("cached_cases") or ()),
                readings=_readings_for(set_name, run_dir),
            )
        )
    for set_name, run_dir_text in sorted(by_run):
        if (set_name, run_dir_text) in named:
            continue
        runs.append(
            RunReading(
                run_dir=Path(run_dir_text),
                set_name=set_name,
                readings=_readings_for(set_name, Path(run_dir_text)),
            )
        )

    clusters = tuple(
        Cluster(
            cluster_id=str(cluster["cluster_id"]),
            level=int(cluster.get("level") or 1),
            category=str(cluster.get("category")),
            trigger=str(cluster.get("trigger")),
            signature=tuple(cluster.get("signature") or ()),
            cases=tuple(int(item) for item in cluster.get("cases") or ()),
            flagged=bool(cluster.get("flagged")),
        )
        for cluster in document.get("clusters") or ()
        if isinstance(cluster, Mapping) and "cluster_id" in cluster
    )
    return PolicyGapReport(
        runs=tuple(runs),
        min_cases=int(document.get("min_cases") or DEFAULT_MIN_CASES),
        dropped_pairs=tuple(document.get("dropped_signature_pairs") or ()),
        clusters=clusters,
    )


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())

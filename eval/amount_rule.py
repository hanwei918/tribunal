"""Measure the amount read-off rule on the drafts three runs already recorded.

The amount read-off rule is what holds a judge draft's money to the brief's own
calculator. A draft whose amount is not a figure the brief's money block
publishes is rejected with ``DRAFT_AMOUNT_NOT_READ_OFF`` and abstains, and the
default rule -- ``published`` -- accepts a published figure or the **sum** of
two or three of them and never a **difference**. Two of the held-out set's cases
died on exactly that: 517 and 533 published no ruling because every one of their
four drafts computed an amount the block does not publish as a sum, and the
drafts were right about the money.

``signed`` is the same rule with a sign on every term after the first. This
module asks what it would have made of the drafts the three runs **already
recorded** -- the 29 corpus cases, the 15 second-development-set cases and the 64
held-out cases -- by rebuilding each case's panel with
:func:`tribunal.pipeline.recorded_judge_drafts` and reducing it twice, once per
rule, through :func:`tribunal.pipeline.reduce_vote`.

Why it re-reduces rather than re-runs
-------------------------------------
Re-running the judge would resample it, and a difference between two runs would
then be a difference between two panels rather than the effect of the rule. The
drafts are held still, exactly as :mod:`eval.verify_drafts` and
:mod:`eval.baselines` hold them, and the two readings differ in the rule and in
nothing else.

Nothing here calls a model, and nothing here builds a client. The module does
not name ``LLMClient``, ``_default_client_factory``, ``verify_recorded_case`` or
``verify_recorded_run`` at all.

Where the output goes
---------------------
``runs/amount-rule/``, and never into a run directory: these figures are a
measurement *about* three runs and not one of them. A run of ``--amount-rule``
under a non-default rule lives at ``runs/amount-rule/<rule>/<model>/``, so a
destination that is one of those, or inside one, is refused as well.

The cases with no cached result
-------------------------------
A case the run failed produced a transcript and no cache entry, and 517 and 533
are exactly that: they are two of the cases this measurement exists for, and
:func:`eval.run_benchmark.check_replay` refuses any case whose run recorded no
brief digest -- which is the digest a cache entry carries. So the verdict is
asked of :func:`tribunal.pipeline.replay_verdict`, the one function that states
the acceptance conditions, with the digest the missing cache entry would have
carried read instead from the transcript's own advocate entries. Those entries
record that digest beside the call it was handed to, so it is the same fact from
the other place it was written down and not a weaker one. Every other condition
is the verdict's own, unchanged: a case whose recorded digest is not the brief
this code builds is still refused, and the refusal is reported with its reason.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "runs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark, sealed_roots, verify_drafts  # noqa: E402
from tribunal import pipeline  # noqa: E402
from tribunal import transcript as transcript_module  # noqa: E402

# The directory this module writes, under the runs root. The same name the
# switched runs of ``--amount-rule`` use, one level up from their rule
# directories, so the measurement and the runs it measures are findable together
# -- and so that "never a run directory" is a property of the path.
AMOUNT_RULE_DIRNAME = run_benchmark.AMOUNT_RULE_DIRNAME
REPORT_FILE = "report.md"
DATA_FILE = "amount-rule.json"

# The two rules, read from the pipeline rather than restated: a rule added there
# is measured here without this module being edited, and a rule this module
# named that the pipeline does not have could not be measured at all.
PUBLISHED = pipeline.AMOUNT_RULE_PUBLISHED
SIGNED = pipeline.AMOUNT_RULE_SIGNED
RULES: Tuple[str, ...] = (PUBLISHED, SIGNED)

# The three runs, in the order the report prints them: the two development sets
# and then the held-out set. ``ALL_SETS`` is the registry's own tuple, so a set
# added there is measured here without a second list to keep in step.
MEASURED_SETS: Tuple[development_sets.DevelopmentSet, ...] = development_sets.ALL_SETS

# How a case moved between the two rules. Named rather than described, because
# the report counts them and a count of prose would have to be parsed back.
MOVEMENT_MATCHING_TO_MISSING = "matching -> missing"
MOVEMENT_MISSING_TO_MATCHING = "missing -> matching"
MOVEMENT_BOTH_MATCHING = "matching both ways"
MOVEMENT_BOTH_MISSING = "missing both ways"


class AmountRuleError(Exception):
    """The measurement was asked for something it cannot do."""


# --------------------------------------------------------------------------
# Where the output may go
# --------------------------------------------------------------------------
def amount_rule_directory(runs_dir: Path = RUNS_DIR) -> Path:
    """Where the measurement lives: ``runs/amount-rule/``."""
    return Path(runs_dir) / AMOUNT_RULE_DIRNAME


def assert_not_a_run_directory(
    destination: Path, runs_dir: Path, model: str
) -> Path:
    """Refuse a destination that is a run directory, or lies inside one.

    ``runs/<model-slug>/`` holds the corpus result the submission reports,
    ``runs/codex/<model-slug>/`` the second development set's and
    ``runs/wild/<model-slug>/`` the held-out set's, whose single run is one of
    the two generalisation figures; and ``runs/amount-rule/<rule>/<model-slug>/``
    holds a run of ``--amount-rule`` under a rule other than the published one. This
    measurement is not any of those, and a reader who found these figures there
    would read them as that run's, so the destination is refused before anything
    is written.

    The check is the one :func:`eval.baselines.assert_not_a_run_directory` makes,
    for the same reasons and stated in the same three parts: every headline
    directory for this model is refused by name, so the refusal is the same
    whether or not those runs have been made yet; everything under
    ``runs/external/`` is refused, because every directory there is a headline
    directory; and every directory from the destination up to the runs root is
    refused if it holds a run's own ``run.json`` or its case files, so a
    destination *inside* a run directory is caught as well as the directory
    itself. It is written out here rather than imported because the two modules
    refuse different things in their own words, and a caller reading one refusal
    should not have to know which module raised it.

    **Two roots are walked, not one.** ``--runs-dir`` and ``--out-dir`` are
    separate arguments, so a caller who points ``--runs-dir`` at a scratch root
    has not thereby made the repository's own run directories safe to write
    into. Every headline directory under either root is refused.

    **A sealed set's whole root is refused, not only its run directory.** Both
    sealed runs have been made and nothing is created under either again, so a
    destination anywhere under ``runs/wild/`` or ``runs/wild-v2/`` is refused,
    ``--out-dir`` included. That rule is
    :func:`eval.sealed_roots.refuse_a_sealed_destination`'s, so this command and
    every other one that writes to a path a caller names refuse the same paths.
    """
    resolved = Path(destination).resolve()
    roots = [Path(runs_dir).resolve()]
    repository = Path(RUNS_DIR).resolve()
    if repository not in roots:
        roots.append(repository)

    for root in roots:
        for headline in run_benchmark.headline_run_directories(root, model):
            if resolved == headline.resolve():
                raise AmountRuleError(
                    "the amount-rule measurement may not be written to the "
                    "headline run directory {0}; it is not that run's figures".format(
                        resolved
                    )
                )

        external = (root / run_benchmark.EXTERNAL_RUNS_SUBDIR).resolve()
        if resolved == external or external in resolved.parents:
            raise AmountRuleError(
                "the amount-rule measurement may not be written under {0}; every "
                "directory there is a headline directory".format(external)
            )

        candidate = resolved
        while candidate != root and root in candidate.parents:
            if (candidate / run_benchmark.METADATA_FILE).is_file() or any(
                candidate.glob("case-*.json")
            ):
                raise AmountRuleError(
                    "the amount-rule measurement may not be written to {0}, which "
                    "holds a run's own results".format(candidate)
                )
            candidate = candidate.parent

    # And the whole of a sealed set's root, not only its run directory: both
    # sealed runs have been made and nothing is created under either again, this
    # measurement included. That rule is one rule for every command that writes
    # to a path a caller names, so it lives in :mod:`eval.sealed_roots`; only
    # the closing sentence is this command's own.
    try:
        sealed_roots.refuse_a_sealed_destination(resolved, runs_dir)
    except sealed_roots.SealedDestinationError as exc:
        raise AmountRuleError(
            "{0} The amount-rule measurement over those cases belongs in a "
            "directory of its own, not under the run it read.".format(exc)
        ) from None
    return resolved


# --------------------------------------------------------------------------
# One case, read twice
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseReading:
    """One case's panel of recorded drafts, reduced under each rule.

    ``published`` and ``signed`` are the two rulings the same drafts produce,
    each as the POL-GEN-03 object the vote published, or ``None`` when the vote
    produced none. ``carried`` is the ruling the run itself published, which the
    published reading has to reproduce: a reading that did not would be a
    different panel from the one the run counted, and the difference between the
    two rules would then be a difference between two reconstructions.

    ``recorded`` is whether the run produced a cached result for the case. A
    case the run failed has a transcript and no result, and its ``carried`` is
    therefore ``None`` rather than a ruling.
    """

    case_no: int
    set_name: str
    key: Any
    published: Optional[Mapping[str, Any]]
    signed: Optional[Mapping[str, Any]]
    carried: Optional[Mapping[str, Any]]
    recorded: bool
    drafts: int
    published_voting: int
    signed_voting: int
    published_matches_recorded: bool

    def _ruling_of(self, ruling: Optional[Mapping[str, Any]]) -> Optional[str]:
        inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
        if not isinstance(inner, Mapping):
            return None
        value = inner.get("ruling")
        return value if isinstance(value, str) else None

    def _amount_of(self, ruling: Optional[Mapping[str, Any]]) -> Optional[Any]:
        """The figure a ruling moves, from the fields POL-GEN-03 requires of it.

        Read off ``pipeline.REQUIRED_AMOUNTS`` rather than from a list written
        here, so a ruling added to the policy is measured without this module
        being edited and a ruling that moves no money answers ``None`` because
        the pipeline says it requires no amount -- not because this module
        happens to have left it out.
        """
        inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
        if not isinstance(inner, Mapping):
            return None
        for name in pipeline.REQUIRED_AMOUNTS.get(inner.get("ruling"), ()):
            amount = pipeline.as_money(inner.get(name))
            if amount is not None:
                return amount
        return None

    @property
    def published_ruling(self) -> Optional[str]:
        return self._ruling_of(self.published)

    @property
    def signed_ruling(self) -> Optional[str]:
        return self._ruling_of(self.signed)

    @property
    def key_ruling(self) -> Optional[str]:
        return getattr(self.key, "ruling", None)

    @property
    def published_amount(self) -> Optional[Any]:
        return self._amount_of(self.published)

    @property
    def signed_amount(self) -> Optional[Any]:
        return self._amount_of(self.signed)

    @property
    def key_amount(self) -> Optional[Any]:
        """The key's own amount, from the same required-fields table."""
        for name in pipeline.REQUIRED_AMOUNTS.get(self.key_ruling, ()):
            return grade.money_or_none(self.key.field(name))
        return None

    @property
    def published_exact(self) -> bool:
        return _is_exact(self.case_no, self.published, self.key)

    @property
    def signed_exact(self) -> bool:
        return _is_exact(self.case_no, self.signed, self.key)

    @property
    def published_moves_money(self) -> bool:
        """Whether the published reading is a ruling that moves money."""
        return bool(pipeline.REQUIRED_AMOUNTS.get(self.published_ruling))

    @property
    def signed_moves_money(self) -> bool:
        return bool(pipeline.REQUIRED_AMOUNTS.get(self.signed_ruling))

    @property
    def movement(self) -> str:
        """Which way the case moved, in the words the report counts."""
        if self.published_exact and not self.signed_exact:
            return MOVEMENT_MATCHING_TO_MISSING
        if self.signed_exact and not self.published_exact:
            return MOVEMENT_MISSING_TO_MATCHING
        return (
            MOVEMENT_BOTH_MATCHING if self.signed_exact else MOVEMENT_BOTH_MISSING
        )

    @property
    def turned_unsafe(self) -> bool:
        """Whether the signed rule turned a safe outcome into a wrong one.

        Safe is the published reading moving no money: an ``ESCALATE``, a
        ``NO_ACTION``, or no ruling at all. Those are the outcomes the policy
        and the pipeline decline to answer with, and they are what a rejected
        draft leaves behind. The case is turned unsafe when the signed rule
        makes the panel publish a **ruling that moves money** which does not
        agree with the key on all four graded fields -- a case that was left
        alone now decided, and decided wrongly.
        """
        return (
            not self.published_moves_money
            and self.signed_moves_money
            and not self.signed_exact
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_no": self.case_no,
            "set": self.set_name,
            "recorded": self.recorded,
            "drafts": self.drafts,
            "published": {
                "ruling": self.published_ruling,
                "amount": _render_amount(self.published_amount),
                "voting_drafts": self.published_voting,
                "exact": self.published_exact,
                "matches_recorded": self.published_matches_recorded,
            },
            "signed": {
                "ruling": self.signed_ruling,
                "amount": _render_amount(self.signed_amount),
                "voting_drafts": self.signed_voting,
                "exact": self.signed_exact,
            },
            "key": {
                "ruling": self.key_ruling,
                "amount": _render_amount(self.key_amount),
            },
            "movement": self.movement,
            "turned_unsafe": self.turned_unsafe,
        }


def _render_amount(amount: Any) -> Optional[str]:
    return None if amount is None else grade.render_money(amount)


def _is_exact(case_no: int, ruling: Optional[Mapping[str, Any]], key: Any) -> bool:
    """Whether a rebuilt ruling is a four-field match, judged by ``eval.grade``.

    ``eval.run_benchmark._match_for`` is the same comparison, and it is not
    reused because it answers ``None`` both for a case that produced no ruling
    and for a case with no key entry. Here the first is a finding the report
    states and the second cannot happen -- every case measured has a key -- so
    the two are kept apart instead of collapsing into one ``None``.
    """
    if ruling is None or key is None:
        return False
    try:
        produced = grade.produced_from_mapping(ruling, case_no)
    except grade.GradeError:
        return False
    return grade.score_case(case_no, key, produced).exact


# --------------------------------------------------------------------------
# One set
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SetMeasurement:
    """One set's cases, each read under both rules."""

    name: str
    run_dir: Path
    expected: int
    source_commit: Optional[str]
    cases: Tuple[CaseReading, ...] = ()
    refused: Tuple[Tuple[int, str], ...] = ()

    @property
    def produced(self) -> int:
        return len(self.cases)

    @property
    def counted(self) -> int:
        """The cases a movement count is over: the ones with a key and a panel."""
        return len(self.cases)

    @property
    def unrecorded_cases(self) -> List[CaseReading]:
        """The cases the run published nothing for.

        Read from the transcript alone, which is the one thing this measurement
        does that :func:`eval.run_benchmark.check_replay` does not do -- see the
        module docstring. Named in the report rather than left for a reader to
        infer from a ``no ruling`` cell, because a case with no cached result is
        also a case with no brief digest on file.
        """
        return [case for case in self.cases if not case.recorded]

    def with_movement(self, movement: str) -> List[CaseReading]:
        return [case for case in self.cases if case.movement == movement]

    @property
    def turned_unsafe(self) -> List[CaseReading]:
        return [case for case in self.cases if case.turned_unsafe]

    @property
    def agreement_failures(self) -> List[CaseReading]:
        """Cases whose published reading is not the ruling the run published.

        Empty for a faithful measurement, and reported rather than asserted: a
        non-empty list is the finding that the reconstruction is not the run's
        own panel, which would make every difference below it a difference
        between two reconstructions.
        """
        return [case for case in self.cases if not case.published_matches_recorded]


def _recorded_brief_digest(source: pipeline.ReplaySource) -> Optional[str]:
    """The brief digest the transcript's own advocate entries recorded, or ``None``.

    Only used for a case the run recorded no cache entry for, which is the one
    case that has no digest to read. Both advocates are handed the same bytes,
    so both entries carry the same digest; entries that disagree cannot say which
    brief the judge's inputs came from, and nothing is returned rather than one
    of the two being picked.
    """
    seen = {
        entry.get("user_sha256")
        for role in (
            transcript_module.ROLE_RIDER_ADVOCATE,
            transcript_module.ROLE_DRIVER_ADVOCATE,
        )
        for entry in source.for_role(role)
        if entry.get("user_sha256")
    }
    if len(seen) != 1:
        return None
    return seen.pop()


def _verdict(
    case_no: int,
    development_set: development_sets.DevelopmentSet,
    run_dir: Path,
    model: str,
    prompts_dir: Path,
    git_commit: Optional[str],
) -> Tuple[Optional[Any], str]:
    """One case's :class:`tribunal.pipeline.Replayable`, or the reason there is none.

    Every acceptance condition is :func:`tribunal.pipeline.replay_verdict`'s. The
    one thing supplied here that the caller of ``check_replay`` does not supply
    is the source's brief digest for a case with no cache entry, read from the
    transcript -- see the module docstring.
    """
    source = run_benchmark.read_replay_source(
        run_dir,
        case_no,
        git_commit=run_benchmark.source_advocate_commit(
            run_dir, case_no, fallback=git_commit
        ),
        model=model,
    )
    if source.brief_sha256 is None:
        recorded = _recorded_brief_digest(source)
        if recorded is not None:
            source = dataclasses.replace(source, brief_sha256=recorded)
    return pipeline.replay_verdict(
        development_set.load_case(case_no),
        source,
        model=model,
        prompts_dir=prompts_dir,
    )


def read_case(
    case_no: int,
    set_name: str,
    found: Mapping[str, Any],
    key: Any,
    carried: Optional[Mapping[str, Any]],
    recorded: bool,
) -> CaseReading:
    """Reduce one case's recorded panel under both rules.

    One panel, two reductions: the drafts are rebuilt once per rule because the
    rule is what decides which of them may vote, and the reduction is the same
    :func:`tribunal.pipeline.reduce_vote` the pipeline itself uses. The vote
    count is the recorded one, so a panel that was asked four times is reduced
    over four drafts under both rules and the quorum is the same quorum.
    """
    vote_block = found["vote"]
    votes = vote_block.get("votes")
    if not isinstance(votes, int) or votes < 2:
        votes = len(vote_block.get("drafts") or [])

    readings: Dict[str, Any] = {}
    draft_counts: Dict[str, int] = {}
    for rule in RULES:
        drafts = pipeline.recorded_judge_drafts(
            vote_block,
            found["entries"],
            found["referee_result"],
            found["brief_object"],
            rule,
        )
        readings[rule] = pipeline.reduce_vote(drafts, votes, found["referee_result"])
        draft_counts[rule] = sum(1 for draft in drafts if draft.valid)

    published = readings[PUBLISHED]
    published_record = published.record or {}
    matches_recorded = (
        published_record.get("outcome") == vote_block.get("outcome")
        and published_record.get("agreement") == vote_block.get("agreement")
    )
    return CaseReading(
        case_no=case_no,
        set_name=set_name,
        key=key,
        published=published.ruling,
        signed=readings[SIGNED].ruling,
        carried=carried,
        recorded=recorded,
        drafts=len(vote_block.get("drafts") or []),
        published_voting=draft_counts[PUBLISHED],
        signed_voting=draft_counts[SIGNED],
        published_matches_recorded=matches_recorded,
    )


def read_set_case(
    development_set: development_sets.DevelopmentSet,
    case_no: int,
    model: str,
    *,
    run_dir: Path,
    key: Any,
    git_commit: Optional[str] = None,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> Tuple[Optional[CaseReading], str]:
    """One case of one set, its recorded panel read under both rules.

    The body of :func:`measure_set`'s loop, named so that a reader -- or a test
    -- can follow one figure back to the case it came from without measuring
    the whole set. It is the code the set measurement runs and not a second
    implementation of it, which is the only way the two can be relied on to
    agree.

    Returns the reading and ``""``, or ``None`` and the reason the case was
    refused. A case whose recorded brief or recorded prompts are not the ones
    this code builds is refused by :func:`tribunal.pipeline.replay_verdict`,
    and the reason is returned rather than swallowed -- the same reason
    :func:`measure_set` reports beside the set it belongs to.
    """
    replayable, reason = _verdict(
        case_no, development_set, run_dir, model, prompts_dir, git_commit
    )
    if replayable is None:
        return None, reason
    found, reason = verify_drafts.recorded_drafts_for_case(
        case_no,
        replayable,
        source_dir=run_dir,
        prompts_dir=prompts_dir,
    )
    if found is None:
        return None, reason
    document = run_benchmark.load_cached(run_dir, case_no)
    return (
        read_case(
            case_no,
            development_set.name,
            found,
            key,
            None if document is None else document.get("ruling"),
            recorded=document is not None,
        ),
        "",
    )


def measure_set(
    development_set: development_sets.DevelopmentSet,
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> SetMeasurement:
    """Read one set's recorded drafts and reduce them under both rules."""
    run_dir = development_set.run_dir(model, runs_dir)
    key = development_set.key()
    metadata = run_benchmark.read_json(run_benchmark.metadata_path(run_dir))
    git_commit = metadata.get("git_commit") if isinstance(metadata, Mapping) else None

    # Every case the run recorded a transcript for, in set order. Not the cases
    # it cached a result for: 517 and 533 have a transcript and no result, and
    # they are two of the cases the rule is being measured on.
    recorded_cases = [
        case_no
        for case_no in development_set.cases
        if run_benchmark.transcript_path(run_dir, case_no).is_file()
    ]

    cases: List[CaseReading] = []
    refused: List[Tuple[int, str]] = []
    for case_no in recorded_cases:
        reading, reason = read_set_case(
            development_set,
            case_no,
            model,
            run_dir=run_dir,
            key=key.get(case_no),
            git_commit=git_commit,
            prompts_dir=prompts_dir,
        )
        if reading is None:
            refused.append((case_no, reason))
            continue
        cases.append(reading)

    return SetMeasurement(
        name=development_set.name,
        run_dir=run_dir,
        expected=len(development_set.cases),
        source_commit=git_commit,
        cases=tuple(cases),
        refused=tuple(refused),
    )


# --------------------------------------------------------------------------
# The whole measurement
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Measurement:
    """Every set, read under both rules, and where the reading was written."""

    model: str
    out_dir: Path
    sets: Tuple[SetMeasurement, ...] = ()
    prompts_sha256: Optional[str] = None
    caveat: str = development_sets.DEVELOPMENT_DATA_CAVEAT

    def all_cases(self) -> List[CaseReading]:
        return [case for item in self.sets for case in item.cases]

    def with_movement(self, movement: str) -> List[CaseReading]:
        return [case for case in self.all_cases() if case.movement == movement]

    @property
    def turned_unsafe(self) -> List[CaseReading]:
        return [case for case in self.all_cases() if case.turned_unsafe]

    @property
    def agreement_failures(self) -> List[CaseReading]:
        return [
            case
            for item in self.sets
            for case in item.agreement_failures
        ]

    @property
    def refused(self) -> List[Tuple[str, int, str]]:
        return [
            (item.name, case_no, reason)
            for item in self.sets
            for case_no, reason in item.refused
        ]


def measure(
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> Measurement:
    """Read all three runs and reduce every recorded panel under both rules.

    No model call and no client: the only things opened are the three run
    directories, the frozen prompts and the three keys.
    """
    if not model:
        raise AmountRuleError("model is required and has no default")
    return Measurement(
        model=model,
        out_dir=amount_rule_directory(runs_dir),
        sets=tuple(
            measure_set(development_set, model, runs_dir, prompts_dir)
            for development_set in MEASURED_SETS
        ),
        prompts_sha256=run_benchmark.current_prompts_sha256(Path(prompts_dir)),
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _cell(ruling: Optional[str], amount: Any) -> str:
    """One ruling as the table prints it: the value, then the figure it moves."""
    if ruling is None:
        return "no ruling"
    if amount is None:
        return ruling
    return "{0} {1}".format(ruling, grade.render_money(amount))


def _case_row(case: CaseReading) -> str:
    return "| {0} | {1} | {2} | {3} | {4} |".format(
        case.case_no,
        _cell(case.published_ruling, case.published_amount),
        _cell(case.signed_ruling, case.signed_amount),
        _cell(case.key_ruling, case.key_amount),
        case.movement,
    )


def _named(cases: Sequence[CaseReading]) -> str:
    """The cases, as a list a sentence can hold: ``a``, ``a and b``, ``a, b and c``."""
    numbers = [str(case.case_no) for case in cases]
    if not numbers:
        return "no case"
    if len(numbers) == 1:
        return numbers[0]
    return "{0} and {1}".format(", ".join(numbers[:-1]), numbers[-1])


def render_report(measurement: Measurement) -> str:
    """The per-case table, then what the rule changes, then what it does not."""
    lines = [
        "# The amount read-off rule, measured on the recorded drafts",
        "",
        "Model: {0}. **No model call was made.** Every figure below is computed "
        "from the judge drafts three runs already recorded: their transcripts "
        "hold the drafts and the vote each was counted in, and the two rules are "
        "two reductions of those same drafts.".format(measurement.model),
        "",
        "`published` is the rule every run so far was judged by: an amount is a "
        "figure the brief's money block publishes, or the **sum** of two or three "
        "of them. `signed` is the same rule with a sign on every term after the "
        "first: a difference of two or three published figures, leading term "
        "positive, result above zero. **The default is unchanged.** This file "
        "measures; it adopts nothing.",
        "",
        "`published` is the reading re-derived from the recorded drafts, and it "
        "is reported beside the ruling the run itself published: where the two "
        "disagree the panel is not the one the run counted, and the difference "
        "between the rules would be a difference between two reconstructions "
        "rather than the effect of the rule.",
        "",
        measurement.caveat,
        "",
        "The held-out set is one of the three runs measured here and is not a "
        "development set. It is read, never written: nothing in this measurement "
        "goes near a run directory.",
        "",
    ]

    for item in measurement.sets:
        lines.append("## {0} — {1}".format(item.name, _relative(item.run_dir)))
        lines.append("")
        lines.append(
            "Read over {0} of the {1} cases in the set; {2} refused. The run "
            "directory's own last recorded commit is {3} -- per-case provenance "
            "is the commit each case's advocates were made under, and a "
            "directory several invocations have written to names the last of "
            "them here.".format(
                item.produced,
                item.expected,
                len(item.refused),
                str(item.source_commit or "unrecorded")[:12],
            )
        )
        lines.append("")
        unrecorded = item.unrecorded_cases
        if unrecorded:
            lines.append(
                "The run published no ruling for {0}, so {1} read from the "
                "transcript alone: there is no cached result to carry the brief "
                "digest, and the digest the transcript's own advocate entries "
                "record is used instead.".format(
                    _named(unrecorded),
                    "it is" if len(unrecorded) == 1 else "they are",
                )
            )
            lines.append("")
        lines.append("| case | published | signed | key | movement |")
        lines.append("|---|---|---|---|---|")
        for case in item.cases:
            lines.append(_case_row(case))
        lines.append("")
        if item.agreement_failures:
            lines.append(
                "**The published reading is not the ruling this run published "
                "for: {0}.** Every difference below is a difference between two "
                "reconstructions for those cases and not the effect of the "
                "rule.".format(_named(item.agreement_failures))
            )
        else:
            lines.append(
                "The published reading reproduces the ruling this run published "
                "for every case above, so the two rules are being compared on the "
                "run's own panel."
            )
        lines.append("")

    lines.extend(
        [
            "## What the signed rule changes",
            "",
            "Counted over the {0} cases read, across all three sets.".format(
                len(measurement.all_cases())
            ),
            "",
            "| movement | cases |",
            "|---|---|",
        ]
    )
    for movement in (
        MOVEMENT_BOTH_MATCHING,
        MOVEMENT_MATCHING_TO_MISSING,
        MOVEMENT_MISSING_TO_MATCHING,
        MOVEMENT_BOTH_MISSING,
    ):
        lines.append(
            "| {0} | {1} |".format(
                movement, len(measurement.with_movement(movement))
            )
        )
    lines.append("")
    lines.append(
        "Matching and missing are the four graded fields: the ruling, both "
        "amounts and the sorted referral clause references."
    )
    lines.append("")
    lines.append(
        "**Turns a match into a miss: {0}.**".format(
            _named(measurement.with_movement(MOVEMENT_MATCHING_TO_MISSING))
        )
    )
    lines.append("")
    lines.append(
        "**Turns a miss into a match: {0}.**".format(
            _named(measurement.with_movement(MOVEMENT_MISSING_TO_MATCHING))
        )
    )
    lines.append("")
    unsafe = measurement.turned_unsafe
    lines.append(
        "**Turns a safe outcome into a monetary ruling that differs from the "
        "key: {0}.** A safe outcome is one the published rule left moving no "
        "money -- an `ESCALATE`, a `NO_ACTION`, or no ruling at all, which is "
        "what a panel whose every draft was rejected produces. Those are the "
        "cases where the signed rule decides a case that was previously left "
        "alone, and decides it wrongly.".format(_named(unsafe))
    )
    for case in unsafe:
        lines.append("")
        lines.append(
            "- `{0}` — published `{1}`, signed `{2}`, key `{3}`".format(
                case.case_no,
                _cell(case.published_ruling, case.published_amount),
                _cell(case.signed_ruling, case.signed_amount),
                _cell(case.key_ruling, case.key_amount),
            )
        )
    lines.append("")

    refused = measurement.refused
    if refused:
        lines.append("## Refused cases, and why")
        lines.append("")
        for set_name, case_no, reason in refused:
            lines.append("- `{0}` case {1} — {2}".format(set_name, case_no, reason))
        lines.append("")
    else:
        lines.append("No case was refused: every recorded panel was rebuilt.")
        lines.append("")

    lines.append(
        "Prompts digest {0}. The measurement reads only; it writes {1} and {2} "
        "and nothing else.".format(
            str(measurement.prompts_sha256 or "unrecorded")[:16],
            REPORT_FILE,
            DATA_FILE,
        )
    )
    return "\n".join(lines)


def data_document(measurement: Measurement) -> Dict[str, Any]:
    return {
        "model": measurement.model,
        "note": (
            "Computed from recorded drafts. No model call was made. The published "
            "reading is re-derived from the same drafts as the signed one, so a "
            "difference between them is the rule and not a second sampling of "
            "the judge."
        ),
        "rules": {
            PUBLISHED: (
                "a published figure, or the sum of two or three of them"
            ),
            SIGNED: (
                "a published figure, a sum, or a signed combination of two or "
                "three with the leading term positive and the result above zero"
            ),
        },
        "default_rule": pipeline.DEFAULT_AMOUNT_RULE,
        "prompts_sha256": measurement.prompts_sha256,
        "caveat": measurement.caveat,
        "sets": [
            {
                "name": item.name,
                "run_dir": _relative(item.run_dir),
                "expected": item.expected,
                "read": item.produced,
                "source_commit": item.source_commit,
                "cases": [case.as_dict() for case in item.cases],
                "refused": [
                    {"case_no": case_no, "reason": reason}
                    for case_no, reason in item.refused
                ],
                "movement": {
                    movement: len(item.with_movement(movement))
                    for movement in (
                        MOVEMENT_BOTH_MATCHING,
                        MOVEMENT_MATCHING_TO_MISSING,
                        MOVEMENT_MISSING_TO_MATCHING,
                        MOVEMENT_BOTH_MISSING,
                    )
                },
                "turned_unsafe": [
                    case.case_no for case in item.turned_unsafe
                ],
                "published_reading_not_the_runs_own": [
                    case.case_no for case in item.agreement_failures
                ],
                "no_cached_result": [
                    case.case_no for case in item.unrecorded_cases
                ],
            }
            for item in measurement.sets
        ],
        "totals": {
            "cases_read": len(measurement.all_cases()),
            "matching_to_missing": [
                case.case_no
                for case in measurement.with_movement(MOVEMENT_MATCHING_TO_MISSING)
            ],
            "missing_to_matching": [
                case.case_no
                for case in measurement.with_movement(MOVEMENT_MISSING_TO_MATCHING)
            ],
            "turned_unsafe": [case.case_no for case in measurement.turned_unsafe],
            "published_reading_not_the_runs_own": [
                case.case_no for case in measurement.agreement_failures
            ],
        },
    }


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.amount_rule",
        description=(
            "Reduce the judge drafts the three runs already recorded under the "
            "published rule and under the signed rule, and report what the "
            "signed rule would change. Reads only and makes no model call."
        ),
    )
    parser.add_argument(
        "--model", default=None, help="the model id; defaults to tribunal/model.py"
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="where report.md and amount-rule.json go; defaults to runs/amount-rule/",
    )
    parser.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    model = run_benchmark.resolve_model(args.model)

    runs_dir = Path(args.runs_dir)
    out_dir = (
        amount_rule_directory(runs_dir) if args.out_dir is None else Path(args.out_dir)
    )
    try:
        assert_not_a_run_directory(out_dir, runs_dir, model)
    except AmountRuleError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    measurement = measure(model, runs_dir, Path(args.prompts_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_FILE).write_text(
        render_report(measurement), encoding="utf-8"
    )
    run_benchmark.write_json(out_dir / DATA_FILE, data_document(measurement))

    print("The amount read-off rule — {0}".format(model))
    print("")
    for item in measurement.sets:
        print(
            "  {0:<8} {1:>3}/{2:<3} cases read, {3} refused".format(
                item.name, item.produced, item.expected, len(item.refused)
            )
        )
    print("")
    print(
        "  cases read              {0}".format(len(measurement.all_cases()))
    )
    for movement in (
        MOVEMENT_BOTH_MATCHING,
        MOVEMENT_MATCHING_TO_MISSING,
        MOVEMENT_MISSING_TO_MATCHING,
        MOVEMENT_BOTH_MISSING,
    ):
        print(
            "  {0:<23} {1}".format(
                movement, len(measurement.with_movement(movement))
            )
        )
    print(
        "  turned unsafe           {0}".format(
            _named(measurement.turned_unsafe)
        )
    )
    print("")
    print("Wrote {0}".format(_relative(out_dir / REPORT_FILE)))
    print("Wrote {0}".format(_relative(out_dir / DATA_FILE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

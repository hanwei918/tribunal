"""Measure the draft verifier on drafts a run already recorded.

The verifier is a new pass over the judge's drafts, and the honest way to ask
what it does is to hold the drafts still. Re-running the judge would resample
it, and a difference between the two runs would then be a difference between
two panels rather than the effect of the verifier. This module therefore reuses
a run's **recorded** judge drafts, rebuilds them with the same assembly and the
same code checks a live draft goes through, and calls only the verifier.

Two commands drive it, and both name a run directory to read from:

* ``python3 -m eval.run_benchmark --verify-recorded-drafts RUN_DIR``
* ``python3 -m eval.development_sets --verify-recorded-drafts RUN_DIR``

What is refused, and why
------------------------
A case is refused rather than guessed at when the recorded drafts answer a
different question from the one this code would ask:

* the source run has no transcript for the case, or the transcript no longer
  hashes to what that run recorded for it;
* the brief this code builds is not the brief the recorded agents were handed;
* the advocates' rendered prompts are not the ones the recorded calls recorded;
* the recorded calls were made on another model;
* **the recorded judge drafts answer a different judge prompt** -- the judge
  entries' own system digest is compared with the judge prompt rendered now;
* the source run asked the judge once, so it has no panel of drafts to verify.

The first four are the conditions :func:`eval.run_benchmark.check_replay`
already enforces, and they are reused rather than restated. The last two are
this mode's own, because it reads the judge side as well.

Where the results go
--------------------
``runs/verify-recorded-drafts/<model>/``, and for a development set
``runs/<set>/verify-recorded-drafts/<model>/``. Never into a model's headline
run directory: these figures are a measurement *about* that run, not that run.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark  # noqa: E402
from tribunal import events, llm, money, pipeline, referee  # noqa: E402
from tribunal import transcript as transcript_module  # noqa: E402

# The subdirectory the recorded-drafts results live under. It is a name of its
# own and not ``<model>``, which is what makes "never the headline directory" a
# property of the path rather than a promise.
VERIFY_RECORDED_SUBDIR = "verify-recorded-drafts"
VERIFY_RECORDED_REPORT = "verify-recorded.md"
VERIFY_RECORDED_JSON = "verify-recorded.json"

_TOKEN_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cached_tokens",
    "total_tokens",
)
ZERO_TOKENS: Dict[str, int] = {key: 0 for key in _TOKEN_KEYS}


def verify_recorded_directory(runs_dir: Path, model: str) -> Path:
    """Where a recorded-drafts measurement for ``model`` is written."""
    return Path(runs_dir) / VERIFY_RECORDED_SUBDIR / run_benchmark.model_slug(model)


def assert_recorded_drafts_destination(runs_dir: Path, model: str) -> Path:
    """The recorded-drafts directory for ``model``, refused if it is a reported one.

    The destination is always ``<runs-dir>/verify-recorded-drafts/<model-slug>/``
    -- a directory of its own, which is what makes "never the headline
    directory" a property of the path. But ``--runs-dir`` is the caller's to
    choose, and pointing it at a run directory the submission reports
    (``runs/wild/<model-slug>/`` for the sealed set, ``runs/codex/<model-slug>/``
    for the second development set, ``runs/<model-slug>/`` for the corpus)
    would put this measurement inside that result. So the destination is
    refused if it is a headline run directory or lies inside one, and the run
    is refused before anything is read or written.

    **Two roots are asked, not one.** A runs root that is itself a reported run
    directory is caught by asking about the directory the runs root sits in as
    well as about the root itself: the destination then lies inside that run
    directory rather than merely beside it. Asking only about the root -- which
    is what the check used to do -- could never refuse anything, because the
    destination always goes through ``verify-recorded-drafts/`` while the
    headline directories are named after the model. Returns the destination
    when nothing refuses it.
    """
    run_dir = verify_recorded_directory(runs_dir, model)
    resolved = run_dir.resolve()
    for root in (Path(runs_dir), Path(runs_dir).parent):
        for headline in run_benchmark.headline_run_directories(root, model):
            headline = headline.resolve()
            if resolved == headline or headline in resolved.parents:
                raise run_benchmark.BenchmarkError(
                    "the recorded-drafts results may not be written to the "
                    "headline run directory {0} or inside it".format(headline)
                )
    return run_dir


def _default_client_factory(model: str, timeout_seconds: float):
    """A real client over the real transport, built the way the runner builds it."""

    def build(sink):
        return llm.LLMClient(
            model=model, timeout_seconds=timeout_seconds, record_sink=sink
        )

    return build


def _tokens_of(entry: Any) -> Dict[str, int]:
    if entry is None:
        return dict(ZERO_TOKENS)
    return {
        "prompt_tokens": entry.prompt_tokens,
        "completion_tokens": entry.completion_tokens,
        "reasoning_tokens": entry.reasoning_tokens,
        "cached_tokens": entry.cached_tokens,
        "total_tokens": entry.prompt_tokens + entry.completion_tokens,
    }


def _add_tokens(left: Mapping[str, int], right: Mapping[str, int]) -> Dict[str, int]:
    return {key: int(left.get(key, 0)) + int(right.get(key, 0)) for key in _TOKEN_KEYS}


@dataclass(frozen=True)
class VoteReading:
    """One reading of a case's vote: how it came out, and on what ruling."""

    outcome: Optional[str]
    agreement: Optional[float]
    ruling: Optional[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "agreement": self.agreement,
            "ruling": self.ruling,
        }


@dataclass(frozen=True)
class CaseVerification:
    """One case's vote read **three ways**, on the same drafts and the same verdicts.

    ``without`` is the vote the run already recorded, re-derived from the
    recorded drafts with no verification applied. ``any_contradiction`` applies
    the verdicts and lets **every** contradiction stop its draft -- what the pass
    did before materiality existed. ``material_only`` lets only a contradiction
    that could change a conclusion stop a draft, which is what the pipeline does.

    All three come from one verifier call. Two of them are reductions of the same
    verdicts, which is the point: the difference between them is the rule, and
    nothing else.
    """

    case_no: int
    statements: int
    called: bool
    usable: bool
    reason: str
    without: VoteReading
    any_contradiction: VoteReading
    material_only: VoteReading
    matches_recorded: bool
    abstained: Tuple[int, ...] = ()
    contradicted: Tuple[Mapping[str, Any], ...] = ()
    material: Tuple[Mapping[str, Any], ...] = ()
    not_in_evidence: Tuple[Mapping[str, Any], ...] = ()
    judged: Tuple[Mapping[str, Any], ...] = ()
    tokens: Mapping[str, int] = field(default_factory=lambda: dict(ZERO_TOKENS))
    verifier_entry: Optional[Mapping[str, Any]] = None

    @property
    def changed(self) -> bool:
        """Whether the verifier moved the vote under the pipeline's own reading."""
        return (self.without.outcome, self.without.agreement) != (
            self.material_only.outcome,
            self.material_only.agreement,
        )

    @property
    def strict_changed(self) -> bool:
        """Whether reading every contradiction as material would have moved it.

        A case where this is true and :attr:`changed` is false is the case
        materiality exists for: a correct draft that the stricter rule would have
        stopped.
        """
        return (self.without.outcome, self.without.agreement) != (
            self.any_contradiction.outcome,
            self.any_contradiction.agreement,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_no": self.case_no,
            "statements": self.statements,
            "called": self.called,
            "usable": self.usable,
            "reason": self.reason,
            "without": self.without.as_dict(),
            "any_contradiction": self.any_contradiction.as_dict(),
            "material_only": self.material_only.as_dict(),
            "matches_recorded": self.matches_recorded,
            "changed": self.changed,
            "strict_changed": self.strict_changed,
            "abstained": list(self.abstained),
            "contradicted": [dict(item) for item in self.contradicted],
            "material": [dict(item) for item in self.material],
            "not_in_evidence": [dict(item) for item in self.not_in_evidence],
            "judged": [dict(item) for item in self.judged],
            "tokens": dict(self.tokens),
            "verifier_entry": None
            if self.verifier_entry is None
            else dict(self.verifier_entry),
        }


@dataclass(frozen=True)
class RecordedReport:
    """What a recorded-drafts measurement produced, case by case."""

    source_dir: Path
    run_dir: Path
    model: str
    label: Optional[str]
    prompts_sha256: Optional[str]
    source_commit: Optional[str]
    cases: Tuple[CaseVerification, ...] = ()
    refused: Mapping[int, str] = field(default_factory=dict)
    tokens: Mapping[str, int] = field(default_factory=lambda: dict(ZERO_TOKENS))

    @property
    def verified_cases(self) -> List[int]:
        return sorted(case.case_no for case in self.cases)

    @property
    def contradicted_statements(self) -> int:
        return sum(len(case.contradicted) for case in self.cases)

    @property
    def material_statements(self) -> int:
        return sum(len(case.material) for case in self.cases)

    @property
    def changed_cases(self) -> List[int]:
        return [case.case_no for case in self.cases if case.changed]

    @property
    def strict_changed_cases(self) -> List[int]:
        return [case.case_no for case in self.cases if case.strict_changed]

    @property
    def saved_cases(self) -> List[int]:
        """Cases the stricter rule would have moved and this one does not."""
        return [
            case.case_no
            for case in self.cases
            if case.strict_changed and not case.changed
        ]

    @property
    def ok(self) -> bool:
        """Whether every case was verified and none was refused."""
        return not self.refused and all(case.usable for case in self.cases)


def _recorded_judge_prompt_matches(
    entries: Sequence[Mapping[str, Any]], judge_prompt: str
) -> bool:
    """Whether every recorded judge entry answers the judge prompt rendered now.

    The judge entries' own ``system_sha256`` is compared with the digest of the
    prompt this code holds, through the one comparison the prompt channel of the
    staleness check also uses. A transcript that recorded no judge entry, or an
    entry with no digest, cannot be shown to answer this prompt, so it is a
    mismatch and not a pass.
    """
    state, _reason = pipeline.compare_recorded_system_prompts(
        entries,
        role=transcript_module.ROLE_JUDGE,
        rendered_sha256=transcript_module.sha256_text(judge_prompt),
    )
    return state == pipeline.PROMPT_MATCH


def _verifier_prompt(prompts_dir: Path) -> str:
    return (Path(prompts_dir) / pipeline.VERIFIER_PROMPT_FILE).read_text(encoding="utf-8")


def _ruling_of(vote: Any) -> Optional[str]:
    ruling = vote.ruling
    inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
    return inner.get("ruling") if isinstance(inner, Mapping) else None


def _reading_of(vote: Any) -> VoteReading:
    """One vote as the report reads it: outcome, agreement and ruling."""
    record = vote.record
    return VoteReading(
        outcome=record.get("outcome"),
        agreement=record.get("agreement"),
        ruling=_ruling_of(vote),
    )


def recorded_drafts_for_case(
    case_no: int,
    replayable: Any,
    *,
    source_dir: Path,
    prompts_dir: Path,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """A case's recorded vote block, its entries, and the referee's ledger.

    Returns ``(found, "")`` or ``(None, reason)``. Every refusal here is a
    refusal to compare two different measurements: the recorded judge drafts
    must have been produced under the judge prompt this code holds, and there
    must be a panel of them.
    """
    payload = run_benchmark.read_json(run_benchmark.transcript_path(source_dir, case_no))
    if not isinstance(payload, Mapping):
        return None, "the source run holds no transcript for case {0}".format(case_no)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return None, "the source transcript for case {0} holds no entries".format(case_no)

    if not _recorded_judge_prompt_matches(entries, replayable.judge_prompt):
        return None, (
            "the recorded judge drafts on case {0} were produced under a different "
            "judge prompt from the one this code holds, so verifying them would "
            "measure a different instruction".format(case_no)
        )

    vote_block = payload.get("vote")
    if not isinstance(vote_block, Mapping):
        return None, (
            "the source run asked the judge once on case {0}, so there is no panel "
            "of drafts to verify".format(case_no)
        )
    drafts = vote_block.get("drafts")
    if not isinstance(drafts, list) or len(drafts) < 2:
        return None, (
            "the source run recorded no panel of drafts on case {0}, so there is "
            "nothing to verify".format(case_no)
        )

    brief_object = json.loads(replayable.brief_json, parse_float=Decimal)
    referee_result = referee.referee(
        brief_object, replayable.rider_claims, replayable.driver_claims
    )
    return (
        {
            "entries": entries,
            "vote": vote_block,
            "brief_object": brief_object,
            "referee_result": referee_result,
        },
        "",
    )


def verify_recorded_case(
    case_no: int,
    *,
    replayable: Any,
    source_dir: Path,
    client: Any,
    prompts_dir: Path,
    verifier_prompt: str,
    case_deadline_seconds: float,
    events_log: Optional[Any] = None,
    clock: Optional[Callable[[], float]] = None,
    now: Optional[Callable[[], str]] = None,
) -> Tuple[Optional[CaseVerification], str]:
    """Verify one case's recorded drafts. Returns ``(case, "")`` or ``(None, reason)``."""
    found, reason = recorded_drafts_for_case(
        case_no, replayable, source_dir=source_dir, prompts_dir=prompts_dir
    )
    if found is None:
        return None, reason

    drafts = pipeline.recorded_judge_drafts(
        found["vote"], found["entries"], found["referee_result"], found["brief_object"]
    )
    votes = found["vote"].get("votes")
    if not isinstance(votes, int) or votes < 2:
        votes = len(drafts)

    without = pipeline.reduce_vote(drafts, votes, found["referee_result"])

    transcript = transcript_module.Transcript(now=now)
    timer = clock if clock is not None else time.monotonic
    deadline = pipeline.CaseDeadline(
        case_no=case_no,
        started_at=timer(),
        limit_seconds=case_deadline_seconds,
        clock=timer,
    )
    updated, verification = pipeline.verify_draft_statements(
        client,
        brief_json=replayable.brief_json,
        drafts=drafts,
        verifier_prompt=verifier_prompt,
        transcript=transcript,
        deadline=deadline,
        events_log=events_log,
        case_no=case_no,
    )
    material_vote = pipeline.reduce_vote(updated, votes, found["referee_result"])

    entry = transcript.entries[-1] if len(transcript) else None
    judged = verification.get("judged") or []
    contradicted = [
        item for item in judged if item["verdict"] == pipeline.VERDICT_CONTRADICTED
    ]
    material = [item for item in contradicted if item[pipeline.VERDICT_MATERIAL]]
    not_in_evidence = [
        item for item in judged if item["verdict"] == pipeline.VERDICT_NOT_IN_EVIDENCE
    ]

    # The second reading of the same verdicts, and no call is made for it: it is
    # the strict rule this pass used before materiality existed, applied to the
    # answer the one call returned, so the readings differ in the rule and in
    # nothing else. With no usable verdicts there is nothing to re-apply, and all
    # three readings are then the same vote.
    if judged:
        strict, _ignored = pipeline.apply_verification(
            drafts,
            verification.get("statements") or [],
            [
                {
                    "statement": item["n"],
                    "verdict": item["verdict"],
                    "evidence": item["evidence"],
                    pipeline.VERDICT_MATERIAL: item[pipeline.VERDICT_MATERIAL],
                    pipeline.VERDICT_BRIEF_VALUE: item[pipeline.VERDICT_BRIEF_VALUE],
                }
                for item in judged
            ],
            abstain_on=pipeline.ABSTAIN_ON_ANY,
        )
        any_vote = pipeline.reduce_vote(strict, votes, found["referee_result"])
    else:
        any_vote = without

    recorded = without.record

    return (
        CaseVerification(
            case_no=case_no,
            statements=len(verification.get("statements") or []),
            called=bool(verification.get("called")),
            usable=bool(verification.get("usable")),
            reason=verification.get("reason") or "",
            without=_reading_of(without),
            any_contradiction=_reading_of(any_vote),
            material_only=_reading_of(material_vote),
            matches_recorded=(
                recorded.get("outcome") == found["vote"].get("outcome")
                and recorded.get("agreement") == found["vote"].get("agreement")
            ),
            abstained=tuple(verification.get("abstained") or ()),
            contradicted=tuple(contradicted),
            material=tuple(material),
            not_in_evidence=tuple(not_in_evidence),
            judged=tuple(judged),
            tokens=verification.get("tokens") or dict(ZERO_TOKENS),
            verifier_entry=None if entry is None else entry.as_dict(),
        ),
        "",
    )


def verify_recorded_run(
    source_dir: Path,
    cases: Sequence[int],
    *,
    model: str,
    runs_dir: Path = run_benchmark.RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS,
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    label: Optional[str] = None,
    client_factory: Optional[Callable[[Callable[[Dict[str, Any]], None]], Any]] = None,
    progress: Callable[[str], None] = lambda text: print(text, flush=True),
    now: Optional[Callable[[], str]] = None,
) -> RecordedReport:
    """Reuse a run's recorded judge drafts, call only the verifier, and report.

    The provenance check runs first and in full, through
    :func:`eval.run_benchmark.check_replay`, so a case that is refused is
    refused before any call is made. What this adds is the judge-side check: the
    recorded drafts must have been produced under the judge prompt this code
    holds, which is the one condition a replay of the advocates cannot answer.
    """
    source_dir = Path(source_dir)
    if not model:
        raise run_benchmark.BenchmarkError("model is required and has no default")

    requested = list(dict.fromkeys(cases))
    if not requested:
        raise run_benchmark.BenchmarkError("no cases were selected")

    # Refused before anything is read or written if the destination is a
    # headline run directory or lies inside one, so pointing --runs-dir at a
    # run directory cannot put this measurement inside the result that
    # directory holds. The sealed set's own directory is one of the three
    # headline directories, which is what keeps this measurement out of the
    # generalisation figure as well as out of the corpus result.
    run_dir = assert_recorded_drafts_destination(runs_dir, model)

    # Read every source entry this run needs before anything is written, exactly
    # as a replay does, so a run pointed at its own directory has read
    # everything before the first file is. The destination is created after the
    # check, so an invocation that refuses every case leaves no directory behind.
    check = run_benchmark.check_replay(
        source_dir,
        requested,
        model=model,
        prompts_dir=prompts_dir,
        case_loader=case_loader,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    stamp = (now or (lambda: datetime.now(timezone.utc).isoformat()))()
    events_log = events.EventLog(
        run_dir / events.EVENTS_FILE,
        invocation_id=events.new_invocation_id(lambda: stamp),
        git_commit=check.git_commit,
        prompts_sha256=run_benchmark.current_prompts_sha256(Path(prompts_dir)),
        now=lambda: stamp,
    )
    events_log.record(
        events.EVENT_INVOCATION_START,
        model=model,
        cases=requested,
        verify_recorded_drafts=str(source_dir),
        development_set=label,
    )

    verifier_prompt = _verifier_prompt(Path(prompts_dir))
    # Built once, and only when there is a case to verify. Building it costs no
    # call: a missing credential is raised when a request is made, not when the
    # client is built, so a run whose cases all state no checkable fact needs no
    # credential and makes no call.
    client = None
    if check.accepted_cases:
        build_client = (
            _default_client_factory(model, timeout_seconds)
            if client_factory is None
            else client_factory
        )
        client = build_client(lambda record: None)

    results: List[CaseVerification] = []
    refused: Dict[int, str] = dict(check.refused)
    totals = dict(ZERO_TOKENS)

    for case_no in check.accepted_cases:
        progress("verify {0}".format(case_no))
        case, reason = verify_recorded_case(
            case_no,
            replayable=check.accepted[case_no],
            source_dir=source_dir,
            client=client,
            prompts_dir=Path(prompts_dir),
            verifier_prompt=verifier_prompt,
            case_deadline_seconds=case_deadline_seconds,
            events_log=events_log,
            now=lambda: stamp,
        )
        if case is None:
            refused[case_no] = reason
            continue
        results.append(case)
        totals = _add_tokens(totals, case.tokens)

    events_log.record(
        events.EVENT_INVOCATION_END,
        stop_reason="completed",
        verified_cases=len(results),
        refused_cases=len(refused),
        contradicted_statements=sum(len(case.contradicted) for case in results),
        material_statements=sum(len(case.material) for case in results),
        changed_cases=[case.case_no for case in results if case.changed],
        tokens_consumed=totals.get("total_tokens", 0),
    )

    report = RecordedReport(
        source_dir=source_dir,
        run_dir=run_dir,
        model=model,
        label=label,
        prompts_sha256=events_log.prompts_sha256,
        source_commit=check.git_commit,
        cases=tuple(results),
        refused=refused,
        tokens=totals,
    )
    (run_dir / VERIFY_RECORDED_REPORT).write_text(
        render_report(report), encoding="utf-8"
    )
    (run_dir / VERIFY_RECORDED_JSON).write_text(
        money.dumps_canonical(
            {
                "source": str(source_dir),
                "model": model,
                "label": label,
                "source_commit": check.git_commit,
                "prompts_sha256": events_log.prompts_sha256,
                "cases": [case.as_dict() for case in results],
                "refused": {str(key): value for key, value in sorted(refused.items())},
                "tokens": totals,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def render_report(report: RecordedReport) -> str:
    """The per-case comparison, then the totals.

    Per case: the vote without the verifier and the vote with it, and every
    statement the verifier judged contradicted, quoted. A reader has to be able
    to see both what changed and what it changed because of.
    """
    lines = [
        "Draft verification on recorded drafts — {0}".format(report.model),
        "",
        "  source        {0}".format(report.source_dir),
        "  source commit {0}".format(report.source_commit or "unrecorded"),
        "  results       {0}".format(report.run_dir),
        "  prompts       {0}".format(str(report.prompts_sha256 or "unrecorded")[:16]),
        "",
        "Per case — three readings of the vote, on the same drafts and the same",
        "verdicts: without the verifier, abstaining on any contradiction, and",
        "abstaining on material contradictions only (what the pipeline does).",
        "",
    ]

    def describe(reading: VoteReading) -> str:
        return "{0} (agreement {1}, {2})".format(
            reading.outcome or "none", reading.agreement, reading.ruling or "no ruling"
        )

    for case in report.cases:
        lines.append("  case {0}".format(case.case_no))
        for label, reading in (
            ("without the verifier", case.without),
            ("abstaining on any contradiction", case.any_contradiction),
            ("abstaining on material only", case.material_only),
        ):
            lines.append("    {0:<34} {1}".format(label + ":", describe(reading)))
        if not case.usable:
            lines.append(
                "    verification not usable: {0}".format(
                    case.reason or "no reason recorded"
                )
            )
        if case.abstained:
            lines.append(
                "    abstained on a material contradiction: draft(s) {0}".format(
                    ", ".join(str(item) for item in case.abstained)
                )
            )
        if case.contradicted:
            for item in case.contradicted:
                lines.append(
                    '    contradicted (draft {0}, {1}): "{2}" [{3}]'.format(
                        item["draft"],
                        "material"
                        if item[pipeline.VERDICT_MATERIAL]
                        else "not material",
                        item["text"],
                        item.get("evidence") or "no evidence named",
                    )
                )
                held = item.get(pipeline.VERDICT_BRIEF_VALUE)
                if held:
                    lines.append('      the brief holds: "{0}"'.format(held))
        else:
            lines.append("    contradicted: none")

    for case_no in sorted(report.refused):
        lines.append("  case {0}  REFUSED   {1}".format(case_no, report.refused[case_no]))

    lines.append("")
    lines.append(
        "  {0} case(s) verified, {1} refused, {2} contradicted statement(s) "
        "({3} material, {4} not), {5} verifier token(s).".format(
            len(report.cases),
            len(report.refused),
            report.contradicted_statements,
            report.material_statements,
            report.contradicted_statements - report.material_statements,
            report.tokens.get("total_tokens", 0),
        )
    )
    lines.append(
        "  the verifier moved the vote on: {0}".format(
            ", ".join(str(case_no) for case_no in report.changed_cases)
            if report.changed_cases
            else "no case"
        )
    )
    lines.append(
        "  abstaining on any contradiction would have moved: {0}".format(
            ", ".join(str(case_no) for case_no in report.strict_changed_cases)
            if report.strict_changed_cases
            else "no case"
        )
    )
    if report.saved_cases:
        lines.append(
            "  materiality alone keeps the vote on: {0}".format(
                ", ".join(str(case_no) for case_no in report.saved_cases)
            )
        )
    lines.append("")
    lines.append(
        "All three readings are of the source run's own drafts and of one set of "
        "verdicts, so a difference between them is the rule and not a second "
        "sampling of the judge."
    )
    return "\n".join(lines)

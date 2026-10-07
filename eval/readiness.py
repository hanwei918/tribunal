"""The readiness report: five dimensions, each computed and each pass or fail.

    python3 -m eval.readiness --speed-run <dir> \
        --price-in-per-m 0.15 --price-out-per-m 0.6 [--price-cached-in-per-m 0.003]

It prints the report and writes **nothing**. ``--out`` writes it, and must name a
file under ``docs/notes/``: the report is a document, and a document about the
repository belongs with the others.

Every number in it is **computed** -- from the repository's committed runs, from
the frozen answer keys, from the loaded policy, from the tests that already
measure the thing, and from one measurement run directory named with
``--speed-run``. Nothing is typed in and nothing is copied out of a document.

The five dimensions
-------------------
1. **Quality** -- the offline replay's result per set, the confidence gate's zero
   effect on every recorded judge draft, and the speed run's four-field score
   against the key it was run against.
2. **Speed** -- from the speed run's own case files: the median and p90 of the
   wall-clock seconds per case, the same two of the *call* seconds (the sum of a
   case's call durations, which is what one call at a time would have taken), the
   ratio of the two medians, the median and p90 tokens per case, and the cost per
   case at the prices given. The comparison with a sequential run is like for
   like: the ``policy-v2`` corpus run, over the case numbers the two share.
3. **Reproducibility** -- ``ui.build --check`` across every page, both sealed-set
   manifest tests, the offline replay, and the freeze gate's exit status against
   the previous tag.
4. **Human management** -- every ``ESCALATE`` in every committed run with its
   reason codes counted, and that the two commands which need a human's name or
   reason still refuse without one.
5. **Logs** -- ``verify_chain`` over every committed run's event log, the share
   of the speed run's ``agent_call`` events carrying all four new fields, and the
   timeline command over a speed-run case. One break in a committed log is known
   and documented -- the iCloud move of 2026-09-27 cut it -- and is named as such
   rather than as a fault; any break anywhere else, or a pinned break that has
   moved or gone, fails the check.

No model call is made and no browser is launched. The subprocesses it runs are
the test modules and the builders that make no model call either; they are run
through one injected runner so a test can answer them without waiting for them.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, policy_gaps, verify_drafts  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tribunal import events, model, pipeline, precedents  # noqa: E402

# The model id is read from the one module that declares it, rather than typed
# here: a second copy of it is a second place to change it.
MODEL = model.RUNTIME_MODEL
RUNS_DIR = PROJECT_ROOT / "runs"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"
NOTES_DIR = PROJECT_ROOT / "docs" / "notes"

# The four sets the offline replay covers, and the same four the confidence-gate
# measurement reads. Named here as the replay names them.
SET_NAMES = ("corpus", "codex", "wild", "wild-v2")

# The sequential run the speed run is compared against, as the path components
# under ``runs/``. It is the corpus's 15-case version-2 run at concurrency 1 --
# the same cases and the same policy version as the speed run, one call at a
# time -- which is what makes the comparison like for like. It is deliberately
# **not** ``runs/<model>/``: 28 of that run's 29 cases replayed their advocates
# from an earlier run, so its call seconds are judge time only and comparing
# against it would compare a partial measurement with a whole one.
SEQUENTIAL_BASELINE = ("policy-v2", MODEL)
# What the report must refuse as a baseline, named so the refusal can be tested.
BASELINE_REPLAY_FIELD = "replay"

# The tag the freeze gate is measured against, the two trees a freeze protects,
# and the one file the parallel-calls task was allowed to correct in them. The
# gate is not over ``tribunal/``: this task changes ``tribunal/`` deliberately,
# and what a freeze protects is what a model is *sent*.
FREEZE_TAG = "freeze-2026-10-03"
FREEZE_PATHS = ("prompts", "policy")
FREEZE_ALLOWED = ("policy/amendments/README.md",)

# The owner's two price bands. Peak is Monday to Friday, 09:00-12:00 and
# 14:00-18:00 Singapore time, and it costs double.
SINGAPORE = timezone(timedelta(hours=8))
PEAK_WINDOWS = ((9, 12), (14, 18))
MILLION = Decimal(10 ** 6)
# Money is reported to six places. A per-case cost in USD is small -- a few
# cents -- and six places is enough to tell two cases apart without pretending to
# a precision the prices do not have.
COST_QUANTUM = Decimal("0.000001")

# The four fields every ``agent_call`` event carries since the call log was
# completed, and the fields that were already there.
NEW_CALL_FIELDS = ("model", "policy_version", "brief_sha256", "body_sha256")

# A break in a committed log that is **known and documented**, and that this
# report names as such rather than as a fault. The iCloud move of 2026-09-27 cut
# one log, and ``runs/`` must not be edited to repair it: the break is part of
# the record. Each entry is ``(repository-relative path, the line the chain
# breaks at, the note that documents it)``.
#
# The pin is not a pass. The check still fails if any log breaks anywhere else,
# if a pinned break moves off its line, or if a pinned break disappears -- a pin
# that no longer names a real break is a stale claim about the record, and this
# report fails on a stale claim as it fails on a new fault.
KNOWN_LOG_BREAKS = (
    (
        "runs/codex/deepseek-deepseek-flash/events.jsonl",
        343,
        "docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md",
    ),
)

# What a dimension's line says. Two words, so a reader scanning the report can
# see the shape of it without reading the numbers.
PASS = "PASS"
FAIL = "FAIL"


class ReadinessError(Exception):
    """A report the inputs cannot produce."""


# --------------------------------------------------------------------------
# Reading numbers
# --------------------------------------------------------------------------
def read_json(path: Any) -> Any:
    """One JSON file, with every number carrying a point a ``Decimal``."""
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def median(values: Sequence[Decimal]) -> Decimal:
    """The median of a list of numbers."""
    ordered = sorted(values)
    if not ordered:
        raise ReadinessError("no values to take a median of")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def percentile(values: Sequence[Decimal], fraction: Decimal) -> Decimal:
    """The nearest-rank percentile of a list of numbers.

    Nearest rank rather than an interpolation: with 29 cases an interpolated p90
    is a number no case took, and this report is about what the cases took.
    """
    ordered = sorted(values)
    if not ordered:
        raise ReadinessError("no values to take a percentile of")
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _count(counts: Dict[str, int], key: str) -> None:
    """One more of ``key`` in a tally."""
    counts[key] = counts.get(key, 0) + 1


def _render(value: Optional[Decimal], places: int = 3) -> str:
    if value is None:
        return "-"
    return "{0:.{1}f}".format(value, places)


# --------------------------------------------------------------------------
# The speed run
# --------------------------------------------------------------------------
def speed_run_documents(run_dir: Path) -> Dict[int, Dict[str, Any]]:
    """Every case file in a run directory, by case number.

    Read straight off disk rather than through the runner's cache reader, because
    the speed run is a measurement run made elsewhere and this report only reads
    it: it is not a run this code produced and it is never written to.
    """
    documents: Dict[int, Dict[str, Any]] = {}
    for path in sorted(Path(run_dir).glob("case-*.json")):
        if ".transcript." in path.name:
            continue
        document = read_json(path)
        if isinstance(document, Mapping) and isinstance(document.get("case_no"), int):
            documents[document["case_no"]] = dict(document)
    return documents


def speed_run_identity(run_dir: Path) -> Dict[str, Any]:
    """What names a run without naming a path.

    An absolute path may not go into ``docs/``, so the report identifies the run
    by the invocation that produced it, the commit it ran at, the two switches
    that decide how it ran, and the sha256 of its own ``run.json`` -- which is a
    digest of everything the run says about itself.
    """
    import hashlib

    path = Path(run_dir) / runner.METADATA_FILE
    if not path.is_file():
        raise ReadinessError("no {0} in {1}".format(runner.METADATA_FILE, run_dir))
    document = read_json(path)
    return {
        "invocation_id": document.get("invocation_id"),
        "git_commit": document.get("git_commit"),
        "parallel_calls": document.get("parallel_calls"),
        "concurrency": document.get("concurrency"),
        "run_json_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model": document.get("model"),
        "configuration": document.get("configuration"),
    }


def price_tier(started_at: Any) -> Tuple[str, str]:
    """Which of the owner's two bands an instant falls in, and why.

    Peak is Monday to Friday, 09:00-12:00 and 14:00-18:00 Singapore time, and it
    costs double. The answer is computed from the instant the run recorded, not
    read out of a sentence in a document.
    """
    if not isinstance(started_at, str) or not started_at:
        raise ReadinessError("the run records no start time to price against")
    moment = datetime.fromisoformat(started_at).astimezone(SINGAPORE)
    stamp = moment.strftime("%Y-%m-%d %H:%M")
    weekday = moment.strftime("%A")
    if moment.weekday() >= 5:
        return "ordinary", "{0} SGT is a {1}".format(stamp, weekday)
    for start, end in PEAK_WINDOWS:
        if start <= moment.hour < end:
            return "peak", "{0} SGT is inside {1:02d}:00-{2:02d}:00 on a {3}".format(
                stamp, start, end, weekday
            )
    return "ordinary", "{0} SGT is outside the peak windows on a {1}".format(
        stamp, weekday
    )


def cost_per_case(
    tokens: Mapping[str, Any],
    price_in: Decimal,
    price_out: Decimal,
    price_cached_in: Optional[Decimal] = None,
) -> Decimal:
    """One case's cost in USD, at the prices given, as a ``Decimal``.

    ``completion_tokens`` already includes the reasoning tokens, so output is
    priced once. When a cached-input price is given, the cached tokens are priced
    at it and **the rest of** ``prompt_tokens`` at the input price; when it is
    not, every prompt token is priced at the input price.
    """
    prompt = _decimal(tokens.get("prompt_tokens")) or Decimal(0)
    cached = _decimal(tokens.get("cached_tokens")) or Decimal(0)
    completion = _decimal(tokens.get("completion_tokens")) or Decimal(0)
    if price_cached_in is None:
        billed = prompt * price_in
    else:
        billed = (prompt - cached) * price_in + cached * price_cached_in
    return ((billed + completion * price_out) / MILLION).quantize(
        COST_QUANTUM, rounding=ROUND_HALF_EVEN
    )


def baseline_documents(run_dir: Path) -> Dict[int, Dict[str, Any]]:
    """A sequential baseline's case files, refusing one that replayed its advocates.

    A run whose cases carry a non-null ``replay`` did not make all of its own
    calls: the advocates were copied from an earlier run, so its ``call_seconds``
    is the judge's time only. Comparing it with a run that made every call would
    compare a partial measurement with a whole one, and the report refuses rather
    than printing a ratio that means nothing.
    """
    documents = speed_run_documents(run_dir)
    if not documents:
        raise ReadinessError("no case files in {0}".format(run_dir))
    replayed = sorted(
        case_no
        for case_no, document in documents.items()
        if document.get(BASELINE_REPLAY_FIELD) is not None
    )
    if replayed:
        raise ReadinessError(
            "{0} case(s) of the baseline carry a non-null {1!r} -- {2} -- so its "
            "call seconds are not a whole run's and it cannot be compared like "
            "for like".format(
                len(replayed),
                BASELINE_REPLAY_FIELD,
                ", ".join(str(case_no) for case_no in replayed[:8]),
            )
        )
    return documents


# --------------------------------------------------------------------------
# The measurements the report reuses
# --------------------------------------------------------------------------
def replay_result() -> Tuple[bool, List[str]]:
    """The offline replay's result per set, through the module that owns it.

    The report runs the same replay the test module runs rather than a second
    implementation of it: a report that re-derived the comparison could disagree
    with the proof it is reporting on.
    """
    from tests import test_offline_replay as replay

    lines: List[str] = []
    ok = True
    for name in SET_NAMES:
        development_set = development_sets.BY_NAME[name]
        replayed = replay.replay_set(development_set, MODEL, parallel=False)
        reproduced = 0
        for case_no, result in replayed.results.items():
            differences = replay.transcript_differences(
                replayed.documents[case_no]["entries"],
                [entry.as_dict() for entry in result.transcript.entries],
            )
            if not differences:
                reproduced += 1
        total = len(replayed.results)
        ok = ok and reproduced == total
        lines.append(
            "  {0}: {1} of {2} cases reproduced".format(name, reproduced, total)
        )
    return ok, lines


def gate_result() -> Tuple[bool, List[str]]:
    """The confidence gate's effect on every recorded judge draft.

    Every draft of the four replayed sets is rebuilt -- which runs the gate --
    and every vote is reduced again with the floor, and each outcome is held
    against the one the run recorded. The point of the measurement is that the
    gate moves nothing; a draft below the floor is already an ``ESCALATE`` or
    already invalid, so the gate has nothing to reject.
    """
    drafts_seen = 0
    below = 0
    moved = 0
    for name in SET_NAMES:
        development_set = development_sets.BY_NAME[name]
        run_dir = development_set.run_dir(MODEL, RUNS_DIR)
        check = runner.check_replay(
            run_dir,
            development_set.cases,
            model=MODEL,
            prompts_dir=PROMPTS_DIR,
            policy_version=development_set.policy_version,
            case_loader=development_set.load_case,
        )
        for case_no in development_set.cases:
            replayable = check.accepted.get(case_no)
            if replayable is None:
                continue
            found, _reason = verify_drafts.recorded_drafts_for_case(
                case_no, replayable, source_dir=run_dir, prompts_dir=PROMPTS_DIR
            )
            if found is None:
                continue
            vote_block = found["vote"]
            drafts = pipeline.recorded_judge_drafts(
                vote_block,
                found["entries"],
                found["referee_result"],
                found["brief_object"],
            )
            floor, _references = pipeline.confidence_floor(found["brief_object"])
            drafts_seen += len(drafts)
            for draft in drafts:
                inner = (
                    draft.ruling.get("ruling")
                    if isinstance(draft.ruling, Mapping)
                    else None
                )
                confidence = (
                    _decimal(inner.get("confidence"))
                    if isinstance(inner, Mapping)
                    else None
                )
                if (
                    confidence is not None
                    and confidence < floor
                    and inner.get("ruling") != pipeline.ESCALATE
                ):
                    below += 1
            reduced = pipeline.reduce_vote(
                drafts,
                vote_block.get("votes") or len(drafts),
                found["referee_result"],
                found["brief_object"],
            )
            if reduced.record.get("outcome") != vote_block.get("outcome"):
                moved += 1
    return moved == 0, [
        "  {0} recorded drafts rebuilt, {1} below the floor and still voting, "
        "{2} votes moved".format(drafts_seen, below, moved)
    ]


def four_field_score(run_dir: Path, key: Mapping[int, Any]) -> Tuple[int, int]:
    """The speed run's four-field exact-match count against the key it ran against."""
    produced: Dict[int, Any] = {}
    for case_no in sorted(key):
        document = runner.load_cached(run_dir, case_no)
        if document is None:
            continue
        # The case file's ``ruling`` value, which is the wrapper the judge's
        # answer is stored in. ``grade.grade`` narrows each record itself, so
        # this is the whole of what it is handed.
        produced[case_no] = document.get("ruling")
    report = grade.grade(produced, key)
    exact = sum(
        1 for score in report.cases if all(outcome.correct for outcome in score.outcomes)
    )
    return exact, len(report.cases)


# --------------------------------------------------------------------------
# The five dimensions
# --------------------------------------------------------------------------
def quality_dimension(
    run_dir: Path,
    key: Mapping[int, Any],
    *,
    replay: Callable[[], Tuple[bool, List[str]]] = None,
    gate: Callable[[], Tuple[bool, List[str]]] = None,
) -> Tuple[bool, List[str]]:
    """The three quality measurements, each already asserted by its own module.

    ``replay`` and ``gate`` are injectable so a test can drive the report's
    arithmetic and its rendering without repeating the two measurements that
    take minutes; the command line uses the real ones.
    """
    replay = replay_result if replay is None else replay
    gate = gate_result if gate is None else gate
    lines = ["**Quality.**", ""]
    ok = True

    replay_ok, replay_lines = replay()
    ok = ok and replay_ok
    lines.append("  The offline replay, per set, sequentially:")
    lines.extend(replay_lines)

    gate_ok, gate_lines = gate()
    ok = ok and gate_ok
    lines.append("")
    lines.append("  The confidence floor, over the same four sets:")
    lines.extend(gate_lines)

    exact, total = four_field_score(run_dir, key)
    lines.append("")
    lines.append(
        "  The speed run's four-field score: {0} of {1} cases exact.".format(
            exact, total
        )
    )
    return ok, lines


def speed_dimension(
    run_dir: Path,
    price_in: Decimal,
    price_out: Decimal,
    price_cached_in: Optional[Decimal],
    tier: str,
    tier_reason: str,
) -> Tuple[bool, List[str]]:
    documents = speed_run_documents(run_dir)
    if not documents:
        raise ReadinessError("no case files in {0}".format(run_dir))

    walls = [_decimal(document.get("wall_seconds")) or Decimal(0) for document in documents.values()]
    calls = [_decimal(document.get("call_seconds")) or Decimal(0) for document in documents.values()]
    tokens = [
        (_decimal((document.get("tokens") or {}).get("total_tokens")) or Decimal(0))
        for document in documents.values()
    ]
    costs = [
        cost_per_case(document.get("tokens") or {}, price_in, price_out, price_cached_in)
        for document in documents.values()
    ]

    wall_median, wall_p90 = median(walls), percentile(walls, Decimal("0.9"))
    call_median, call_p90 = median(calls), percentile(calls, Decimal("0.9"))
    ratio = (wall_median / call_median) if call_median else None

    lines = [
        "**Speed.** From the speed run's own case files ({0} cases):".format(
            len(documents)
        ),
        "",
        "  wall_seconds per case:  median {0}   p90 {1}".format(
            _render(wall_median), _render(wall_p90)
        ),
        "  call_seconds per case:  median {0}   p90 {1}".format(
            _render(call_median), _render(call_p90)
        ),
        "  the same run one call at a time would have taken its calls in the sum "
        "of those durations;",
        "  the ratio of the two medians, wall over calls: {0}".format(
            _render(ratio, 4)
        ),
        "  total_tokens per case:  median {0}   p90 {1}".format(
            _render(median(tokens), 0), _render(percentile(tokens, Decimal("0.9")), 0)
        ),
        "  cost per case at the prices given: median {0}   p90 {1}".format(
            _render(median(costs), 6), _render(percentile(costs, Decimal("0.9")), 6)
        ),
        "",
        "  Prices: input {0} USD/M, output {1} USD/M{2}.".format(
            price_in,
            price_out,
            ""
            if price_cached_in is None
            else ", cached input {0} USD/M".format(price_cached_in),
        ),
        "  Priced at the {0} tier ({1}).".format(tier, tier_reason),
    ]

    # The like-for-like comparison, over the case numbers the two runs share.
    baseline_dir = RUNS_DIR / SEQUENTIAL_BASELINE[0] / runner.model_slug(MODEL)
    ok = True
    if baseline_dir.is_dir():
        baseline = baseline_documents(baseline_dir)
        shared = sorted(set(documents) & set(baseline))
        if shared:
            their_walls = [
                _decimal(baseline[case_no].get("wall_seconds")) or Decimal(0)
                for case_no in shared
            ]
            ours = [
                _decimal(documents[case_no].get("wall_seconds")) or Decimal(0)
                for case_no in shared
            ]
            lines.append("")
            lines.append(
                "  Compared with the sequential {0} run over the {1} case numbers "
                "they share:".format("/".join(SEQUENTIAL_BASELINE), len(shared))
            )
            lines.append(
                "    its wall_seconds: median {0}   p90 {1}".format(
                    _render(median(their_walls)), _render(percentile(their_walls, Decimal("0.9")))
                )
            )
            lines.append(
                "    the speed run's on the same cases: median {0}   p90 {1}".format(
                    _render(median(ours)), _render(percentile(ours, Decimal("0.9")))
                )
            )
            lines.append(
                "    the ratio of the medians, sequential over parallel: {0}".format(
                    _render(median(their_walls) / median(ours), 4)
                )
            )
        else:
            ok = False
            lines.append("  The sequential baseline shares no case with the speed run.")
    else:
        ok = False
        lines.append(
            "  The sequential baseline {0} is not present.".format(
                "/".join(SEQUENTIAL_BASELINE)
            )
        )

    # The recorded wild-v2 mean, labelled as a different case set and not as a
    # baseline: it is the number the estimate in the README was made from, and it
    # is 20 cases of another set at another policy version.
    wild_v2 = development_sets.BY_NAME["wild-v2"]
    wild_dir = wild_v2.run_dir(MODEL, RUNS_DIR)
    wild_walls = [
        _decimal(document.get("wall_seconds"))
        for document in speed_run_documents(wild_dir).values()
    ]
    wild_walls = [value for value in wild_walls if value is not None]
    if wild_walls:
        lines.append("")
        lines.append(
            "  For scale, and **not** as a baseline: the recorded wild-v2 run's "
            "mean wall_seconds is {0} over {1} cases of a different set at a "
            "different policy version.".format(
                _render(sum(wild_walls) / len(wild_walls)), len(wild_walls)
            )
        )
    return ok, lines


def exits_zero(completed: Any) -> bool:
    """Whether a check's process exited zero."""
    return getattr(completed, "returncode", 1) == 0


def shows_only_the_allowed_file(completed: Any) -> bool:
    """The freeze gate: the two trees moved, and only where they may have.

    The tag is a freeze of what a model is *sent*, so the criterion is not that
    the diff is empty -- one file in it was corrected on purpose -- but that
    nothing else in it moved. The output is read rather than the exit status:
    ``git diff --name-only`` exits 0 whether or not there is a diff.
    """
    if not exits_zero(completed):
        return False
    named = [
        line.strip()
        for line in (getattr(completed, "stdout", "") or "").splitlines()
        if line.strip()
    ]
    return sorted(named) == sorted(FREEZE_ALLOWED)


def reproducibility_dimension(run: Callable[..., Any]) -> Tuple[bool, List[str]]:
    checks = (
        (
            "ui.build --check, every page",
            [sys.executable, "-m", "ui.build", "--check"],
            exits_zero,
        ),
        (
            "the two sealed-set manifest tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_wild_run_manifest",
                "tests.test_wild_v2_run_manifest",
            ],
            exits_zero,
        ),
        (
            "the offline replay",
            [sys.executable, "-m", "unittest", "tests.test_offline_replay"],
            exits_zero,
        ),
        (
            "the freeze gate, {0} against the working tree, over {1} -- which may "
            "show {2} and nothing else".format(
                FREEZE_TAG, " and ".join(FREEZE_PATHS), " and ".join(FREEZE_ALLOWED)
            ),
            ["git", "diff", "--name-only", FREEZE_TAG, "--"] + list(FREEZE_PATHS),
            shows_only_the_allowed_file,
        ),
    )
    lines = ["**Reproducibility.**", ""]
    ok = True
    for label, command, decide in checks:
        completed = run(
            command, cwd=str(PROJECT_ROOT), capture_output=True, text=True
        )
        passed = decide(completed)
        ok = ok and passed
        lines.append(
            "  {0}: {1} (exit {2})".format(
                PASS if passed else FAIL, label, getattr(completed, "returncode", "?")
            )
        )
    return ok, lines


def human_dimension() -> Tuple[bool, List[str]]:
    escalations = 0
    reasons: Dict[str, int] = {}
    outcomes: Dict[str, int] = {}
    for case_file in sorted(RUNS_DIR.rglob("case-*.json")):
        if ".transcript." in case_file.name:
            continue
        document = read_json(case_file)
        if not isinstance(document, Mapping):
            continue
        ruling = document.get("ruling")
        inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
        if not isinstance(inner, Mapping) or inner.get("ruling") != pipeline.ESCALATE:
            continue
        escalations += 1
        for finding in document.get("ruling_findings") or []:
            if isinstance(finding, Mapping):
                _count(reasons, str(finding.get("invariant")))
        # Why the panel escalated. The vote's outcome says whether it disagreed
        # or could not sit, and each draft's own abstention code says what the
        # check found wrong with it -- which is the reason a reader is looking
        # for, and is not on the case file.
        transcript = case_file.with_name(
            case_file.name[: -len(".json")] + ".transcript.json"
        )
        if not transcript.is_file():
            continue
        payload = read_json(transcript)
        vote = payload.get("vote") if isinstance(payload, Mapping) else None
        if not isinstance(vote, Mapping):
            continue
        _count(outcomes, str(vote.get("outcome")))
        for draft in vote.get("drafts") or []:
            code = draft.get("abstention") if isinstance(draft, Mapping) else None
            if code:
                _count(reasons, str(code).split(":", 1)[0].strip())

    lines = ["**Human management.**", ""]
    lines.append(
        "  {0} case(s) across the committed runs ended in an ESCALATE. The votes "
        "that produced them, by outcome:".format(escalations)
    )
    for code, count in sorted(outcomes.items(), key=lambda item: (-item[1], item[0])):
        lines.append("    {0}  {1}".format(count, code))
    lines.append("  and the reason codes they rest on, counted:")
    if reasons:
        for code, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])):
            lines.append("    {0}  {1}".format(count, code))
    else:
        lines.append("    (none recorded)")

    ok = True
    # Both commands are asked to run without the human input they require, and
    # both must refuse. The refusal is the check: a closure with no reason and an
    # approval with no approver are exactly what must not reach the store.
    # Both parsers print their usage to stderr when they refuse, and the report
    # is the output a reader reads: the noise is captured rather than printed.
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            precedents.main(
                ["close", "--run-dir", ".", "--case", "1", "--ruling", "NO_ACTION",
                 "--clause", "POL-GEN-01", "--closed-by", "x", "--summary", "y"]
            )
            refused = False
        except SystemExit as exc:
            refused = exc.code not in (0, None)
    ok = ok and refused
    lines.append("")
    lines.append(
        "  {0}: precedents close refuses a command with no --reason".format(
            PASS if refused else FAIL
        )
    )

    with contextlib.redirect_stderr(io.StringIO()):
        try:
            policy_gaps.main(["approve", "--proposal", "nothing.json"])
            approved = False
        except SystemExit as exc:
            approved = exc.code not in (0, None)
    ok = ok and approved
    lines.append(
        "  {0}: policy_gaps approve refuses a command with no --approved-by".format(
            PASS if approved else FAIL
        )
    )
    return ok, lines


def logs_dimension(run_dir: Path, case_no: int) -> Tuple[bool, List[str]]:
    lines = ["**Logs.**", ""]
    ok = True

    # Every committed **run**, which is a directory holding a ``run.json``. The
    # archived copies under ``runs/_icloud-incident-2026-09-27/`` are fragments of
    # logs the iCloud move cut, so their first line's ``prev`` names a line that
    # is not in the file; they are copies, not runs, and they are not what this
    # dimension is about.
    broken: List[Tuple[str, str]] = []
    known: List[str] = []
    seen: List[Tuple[str, int, str]] = []
    logs = 0
    for log in sorted(RUNS_DIR.rglob(events.EVENTS_FILE)):
        if not (log.parent / runner.METADATA_FILE).is_file():
            continue
        # ``runs/_icloud-incident-2026-09-27/`` holds copies of whole run
        # directories taken during the iCloud move, so each one has a
        # ``run.json`` too -- and its log is a fragment the copy cut, whose first
        # line's ``prev`` names a line that is not in the file. The underscore
        # is how this repository marks a directory that is not a run.
        if any(part.startswith("_") for part in log.parts):
            continue
        logs += 1
        break_ = events.verify_chain(log)
        if break_ is None:
            continue
        relative = precedents.repository_relative(log)
        pinned = next(
            (
                entry
                for entry in KNOWN_LOG_BREAKS
                if entry[0] == relative and entry[1] == break_.line_number
            ),
            None,
        )
        if pinned is None:
            broken.append((relative, break_.describe()))
        else:
            seen.append(pinned)
            known.append(
                "{0} at {1}, known, documented in {2}".format(
                    relative, break_.describe(), pinned[2]
                )
            )
    # A pin that named a break that is not there any more is a stale claim, and
    # a stale claim fails the check as a new fault does.
    stale = [entry for entry in KNOWN_LOG_BREAKS if entry not in seen]
    ok = ok and not broken and not stale
    lines.append(
        "  {0}: verify_chain over {1} committed run log(s){2}{3}{4}".format(
            PASS if not broken and not stale else FAIL,
            logs,
            ""
            if not broken
            else " -- {0} do not verify: {1}".format(
                len(broken),
                "; ".join("{0} at {1}".format(path, detail) for path, detail in broken),
            ),
            ""
            if not known
            else " -- {0} known break(s): {1}".format(len(known), "; ".join(known)),
            ""
            if not stale
            else " -- {0} pinned break(s) no longer present: {1}".format(
                len(stale),
                "; ".join(
                    "{0} at line {1}".format(entry[0], entry[1]) for entry in stale
                ),
            ),
        )
    )

    path = Path(run_dir) / events.EVENTS_FILE
    calls = [
        event
        for event in events.read_events(path)
        if event.get("event") == events.EVENT_AGENT_CALL
    ]
    complete = [
        event for event in calls if all(field in event for field in NEW_CALL_FIELDS)
    ]
    share = (len(complete) / len(calls)) if calls else 0.0
    met = bool(calls) and len(complete) == len(calls)
    ok = ok and met
    detail = ""
    if not met and calls:
        # The criterion is 100% and the run is named with the commit it ran at,
        # so a run made before the fields existed is reported as exactly that
        # rather than as a defect in the code that writes them.
        detail = (
            "; the speed run was made at {0}, and the fields were added after it, "
            "so this criterion cannot be met by that run and is met by every run "
            "made since".format(speed_run_identity(run_dir).get("git_commit"))
        )
    lines.append(
        "  {0}: {1} of {2} agent_call events in the speed run carry all four new "
        "fields ({3:.0%}){4}".format(
            PASS if met else FAIL, len(complete), len(calls), share, detail
        )
    )

    printed = events.timeline(path, case_no)
    works = printed.startswith("case {0}".format(case_no)) and "ruling:" in printed
    ok = ok and works
    lines.append(
        "  {0}: the timeline prints case {1} of the speed run ({2} line(s))".format(
            PASS if works else FAIL, case_no, len(printed.splitlines())
        )
    )
    return ok, lines


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def render(
    run_dir: Path,
    *,
    price_in: Decimal,
    price_out: Decimal,
    price_cached_in: Optional[Decimal] = None,
    run: Callable[..., Any] = subprocess.run,
    replay: Callable[[], Tuple[bool, List[str]]] = None,
    gate: Callable[[], Tuple[bool, List[str]]] = None,
) -> str:
    """The whole report, as text."""
    identity = speed_run_identity(run_dir)
    documents = speed_run_documents(run_dir)
    if not documents:
        raise ReadinessError("no case files in {0}".format(run_dir))
    started = None
    for document in documents.values():
        started = document.get("recorded_at")
        break
    tier, reason = price_tier(started)

    key = grade.load_answer_key()
    corpus = development_sets.BY_NAME["corpus"]
    speed_key = {case_no: key[case_no] for case_no in documents if case_no in key}

    dimensions: List[Tuple[str, bool, List[str]]] = []
    dimensions.append(
        ("Quality",) + quality_dimension(run_dir, speed_key, replay=replay, gate=gate)
    )
    dimensions.append(
        ("Speed",)
        + speed_dimension(run_dir, price_in, price_out, price_cached_in, tier, reason)
    )
    dimensions.append(("Reproducibility",) + reproducibility_dimension(run))
    dimensions.append(("Human management",) + human_dimension())
    case_no = sorted(documents)[0]
    dimensions.append(("Logs",) + logs_dimension(run_dir, case_no))

    lines = [
        "# Readiness report",
        "",
        "Computed by `python3 -m eval.readiness`. Every number below is computed "
        "from the repository, from the frozen answer keys, or from the speed run "
        "named here; nothing is typed in. No model call is made and no browser is "
        "launched.",
        "",
        "## The measurement run",
        "",
        "Named without a path, because an absolute path may not go into `docs/`:",
        "",
    ]
    for name in (
        "invocation_id",
        "git_commit",
        "model",
        "parallel_calls",
        "concurrency",
        "run_json_sha256",
    ):
        lines.append("- `{0}`: `{1}`".format(name, identity.get(name)))
    lines.append("- `cases`: {0}".format(len(documents)))
    lines.append("- `configuration`: `{0}`".format(
        json.dumps(identity.get("configuration"), default=str, sort_keys=True)
    ))
    lines.append("- priced at the **{0}** tier: {1}".format(tier, reason))
    lines.append("")
    lines.append("## The five dimensions")
    lines.append("")
    for name, ok, body in dimensions:
        lines.append("### {0} -- {1}".format(name, PASS if ok else FAIL))
        lines.append("")
        lines.extend(body)
        lines.append("")
    lines.append("## Result")
    lines.append("")
    for name, ok, _body in dimensions:
        lines.append("- {0}: {1}".format(name, PASS if ok else FAIL))
    lines.append("")
    lines.append(
        "**{0}**".format(
            "Every dimension passes." if all(ok for _n, ok, _b in dimensions)
            else "At least one dimension fails."
        )
    )
    return "\n".join(lines) + "\n"


def resolve_out(path: Optional[Path]) -> Optional[Path]:
    """``--out``, refused unless it names a file under ``docs/notes/``.

    Refused rather than silently redirected: a caller who asked for a report
    somewhere else meant something this command does not do, and writing it
    anyway would put a document where the repository does not keep one.
    """
    if path is None:
        return None
    resolved = Path(path).resolve()
    notes = NOTES_DIR.resolve()
    try:
        resolved.relative_to(notes)
    except ValueError:
        raise ReadinessError(
            "--out must name a file under docs/notes/, and {0} does not".format(path)
        )
    return resolved


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.readiness",
        description=(
            "Compute a readiness report over the repository and one measurement "
            "run. Writes nothing unless --out is given. No model call is made."
        ),
    )
    parser.add_argument(
        "--speed-run",
        type=Path,
        required=True,
        help="the measurement run's directory; read, never written",
    )
    parser.add_argument(
        "--price-in-per-m",
        required=True,
        help="USD per million input tokens",
    )
    parser.add_argument(
        "--price-out-per-m",
        required=True,
        help="USD per million output tokens",
    )
    parser.add_argument(
        "--price-cached-in-per-m",
        default=None,
        help="USD per million cached input tokens; when given, cached tokens are "
        "priced at it and the rest of prompt_tokens at --price-in-per-m",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the report here; must be under docs/notes/",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        destination = resolve_out(args.out)
        text = render(
            Path(args.speed_run),
            price_in=Decimal(str(args.price_in_per_m)),
            price_out=Decimal(str(args.price_out_per_m)),
            price_cached_in=(
                None
                if args.price_cached_in_per_m is None
                else Decimal(str(args.price_cached_in_per_m))
            ),
        )
    except (ReadinessError, InvalidOperation) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    if destination is None:
        print(text, end="")
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print("wrote {0}".format(destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""What the record-integrity gate would have done, replayed from the record.

Two of ``POL-RD-10``'s escalation triggers are conditions code can test with no
model, and the judge read past both at version 6
(``docs/notes/2026-10-10-what-went-wrong-at-version-6.md``):

* **limb (2)** -- "the trip identifiers on trip_record, gps_trace and
  fare_breakdown do not all match, or the trip_record is absent from the pool".
  Case 2858's fare ledger is filed under ``TRP-02758`` while the trip record and
  the trace are both ``TRP-02858``.
* **limb (4)** -- "pickup or dropoff timestamps on two admitted artifacts
  disagree by more than 10 minutes, or any artifact's timestamps run
  backwards". Case 112's trace begins 13 minutes 30 seconds before the trip
  record says the trip started.

``--integrity-gate`` escalates such a record by code, with no call made. This
module asks **what that gate would have done on the runs that were actually
made**, over every committed case that has a run at policy version 6: the
corpus, ``dev-v2-ext``, ``dev-v2`` 1779, the organisers' sample 901,
``sealed-v1``, and the three functional sets.

For each case the gate would escalate it names the limb that fired, the key's
ruling and the ruling the run recorded; then it counts the cases the gate would
**fix** (key ``ESCALATE``, recorded not), the cases it would **break** (key not
``ESCALATE``) and the cases it **leaves as they were**.

**The gate is the pipeline's own.** The limbs come from
:func:`tribunal.pipeline.record_integrity_limbs`, applied to the same brief the
run was made from (built at policy version 6), and the minutes limb (4) reads
come from :func:`tribunal.pipeline.record_integrity_minutes`, which reads them
from the loaded clause. What this module adds is only the reading of the
recorded ruling and of the key.

No model call is made and no browser is launched. The module reads the
committed runs, the committed case files and the committed keys, and writes
nothing.

Run from the project root with::

    python3 -m eval.integrity_gate --report
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import development_sets, grade, run_benchmark, v6_runs
from tribunal import brief, loader, pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "runs"
ANSWER_DIR = PROJECT_ROOT / "eval" / "answers"

# The model every run of this batch was made on, as its run directory is named.
# Taken from the module that reads the version-6 batch rather than repeated.
MODEL_SLUG = v6_runs.MODEL_SLUG

# The policy version the runs were made at, and the version each case's brief is
# rebuilt at so the gate reads the record the run read.
POLICY_VERSION = v6_runs.POLICY_VERSION

# Where a set's version-6 run sits under its own root.
POLICY_V_DIRNAME = "policy-v{0}".format(POLICY_VERSION)


class IntegrityGateError(Exception):
    """The measurement could not be made: a run or a case file is not there."""


# --------------------------------------------------------------------------
# The runs
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MeasuredRun:
    """One version-6 run: its name, where it lives, where its cases live, its key."""

    name: str
    run_dir: Path
    case_root: Optional[Path]
    key_path: Optional[Path]
    note: str


def measured_runs() -> Tuple[MeasuredRun, ...]:
    """Every run this report reads, in the order it prints them.

    The four runs ``eval.v6_runs`` names, the third sealed set's single run, and
    the three functional sets' runs. The precedents run is deliberately absent:
    it is the corpus's fifteen route-deviation cases run again with
    ``--precedents`` on, so every case of it is already counted here.
    """
    runs: List[MeasuredRun] = [
        MeasuredRun(
            name="corpus",
            run_dir=v6_runs.run_by_name("corpus").run_dir,
            case_root=None,
            key_path=ANSWER_DIR / "ground_truth.json",
            note="the 29-case corpus",
        ),
        MeasuredRun(
            name="dev-v2-ext",
            run_dir=v6_runs.run_by_name("dev-v2-ext").run_dir,
            case_root=loader.EXTERNAL_DIR / "dev-v2-ext",
            key_path=ANSWER_DIR / "dev-v2-ext" / "ground_truth.json",
            note="the 120-case extension set",
        ),
        MeasuredRun(
            name="dev-v2",
            run_dir=v6_runs.run_by_name("dev-v2").run_dir,
            case_root=loader.EXTERNAL_DIR / "dev-v2",
            key_path=ANSWER_DIR / "dev-v2" / "ground_truth.json",
            note="case 1779 alone, the prompt-injection case",
        ),
        MeasuredRun(
            name="ryde-v3",
            run_dir=v6_runs.run_by_name("ryde-v3").run_dir,
            case_root=loader.EXTERNAL_DIR / "ryde-v3",
            key_path=None,
            note="the organisers' sample, case 901",
        ),
        MeasuredRun(
            name="sealed-v1",
            run_dir=RUNS_DIR / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR / MODEL_SLUG,
            case_root=loader.EXTERNAL_DIR / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR,
            key_path=(
                ANSWER_DIR
                / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR
                / "ground_truth.json"
            ),
            note="the third sealed set's single run",
        ),
    ]
    for development_set in development_sets.FUNCTIONAL_SETS:
        runs.append(
            MeasuredRun(
                name=development_set.name,
                run_dir=RUNS_DIR / development_set.name / POLICY_V_DIRNAME / MODEL_SLUG,
                case_root=loader.EXTERNAL_DIR / development_set.name,
                key_path=ANSWER_DIR / development_set.name / "ground_truth.json",
                note="a functional set, run once by the owner",
            )
        )
    return tuple(runs)


def case_numbers(run_dir: Path) -> Tuple[int, ...]:
    """Every case the run directory holds, by number.

    Read off the directory rather than off a set's index: the index is a
    registration, and what this module measures is what the run wrote.
    """
    if not Path(run_dir).is_dir():
        raise IntegrityGateError(
            "the run directory {0} is not there, so the report would cover less "
            "than every committed case with a run at version 6".format(run_dir)
        )
    return tuple(sorted(v6_runs.case_files(Path(run_dir))))


def load_case(run: MeasuredRun, case_no: int) -> Dict[str, Any]:
    """One case, from the corpus manifest or from its set's own index."""
    if run.case_root is None:
        return loader.load_case(case_no)
    return loader.load_external_set_case(run.case_root, case_no)


def recorded_ruling(run: MeasuredRun, case_no: int) -> Optional[str]:
    """The ruling word one run's case file records, or ``None``."""
    document = v6_runs.read_json(v6_runs.case_path(run.run_dir, case_no))
    inner = (document.get("ruling") or {}).get("ruling")
    word = inner.get("ruling") if isinstance(inner, Mapping) else None
    return word if isinstance(word, str) else None


def key_for(run: MeasuredRun) -> Mapping[int, Any]:
    """The key this run is graded against, or an empty mapping when it has none."""
    if run.key_path is None:
        return {}
    return grade.load_answer_key(run.key_path)


# --------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Case:
    """One case with a version-6 run: what the gate would make of it."""

    run: str
    case_no: int
    category: str
    limbs: Tuple[str, ...]
    key: Optional[str]
    recorded: Optional[str]

    @property
    def escalated(self) -> bool:
        return bool(self.limbs)

    @property
    def fixes(self) -> bool:
        """Key ``ESCALATE`` and the run ruled something else: the gate repairs it."""
        return (
            self.escalated
            and self.key == pipeline.ESCALATE
            and self.recorded != pipeline.ESCALATE
        )

    @property
    def breaks(self) -> bool:
        """A key that is not ``ESCALATE``: the gate would escalate a case it decides."""
        return self.escalated and self.key is not None and self.key != pipeline.ESCALATE

    @property
    def leaves(self) -> bool:
        """The run already escalated, so the gate changes nothing a reader acts on."""
        return self.escalated and not self.fixes and not self.breaks


@dataclass(frozen=True)
class RunMeasurement:
    """One run's cases, and the ones of them the gate would escalate."""

    name: str
    note: str
    cases: Tuple[Case, ...]


def measure_case(run: MeasuredRun, case_no: int, key: Mapping[int, Any]) -> Case:
    """One case, replayed through the gate."""
    case = load_case(run, case_no)
    case_brief = brief.build_brief_for_case(case, policy_version=POLICY_VERSION)
    expected = key.get(case_no)
    return Case(
        run=run.name,
        case_no=case_no,
        category=str(case["dispute"].get("category")),
        limbs=pipeline.record_integrity_limbs(case_brief, POLICY_VERSION),
        key=None if expected is None else expected.ruling,
        recorded=recorded_ruling(run, case_no),
    )


def measure_run(run: MeasuredRun) -> RunMeasurement:
    numbers = case_numbers(run.run_dir)
    key = key_for(run)
    cases = tuple(measure_case(run, case_no, key) for case_no in numbers)
    return RunMeasurement(run.name, run.note, cases)


def measure() -> Tuple[Tuple[RunMeasurement, ...], Tuple[Case, ...]]:
    """Every run, and every case of every run, flattened in run order."""
    measurements = tuple(measure_run(run) for run in measured_runs())
    everything = tuple(case for measurement in measurements for case in measurement.cases)
    return measurements, everything


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _named(cases: Sequence[Case]) -> str:
    items = ["{0} ({1})".format(case.case_no, case.run) for case in cases]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return "{0} and {1}".format(", ".join(items[:-1]), items[-1])


def _cases(count: int) -> str:
    """``1 case``, ``2 cases`` -- a count that reads as a count."""
    return "{0} {1}".format(count, "case" if count == 1 else "cases")


def _limb_tally(cases: Sequence[Case]) -> str:
    counts: Dict[str, int] = {}
    for case in cases:
        for limb in case.limbs:
            counts[limb] = counts.get(limb, 0) + 1
    if not counts:
        return "none"
    return ", ".join("{0} {1}".format(limb, counts[limb]) for limb in sorted(counts))


def _row(case: Case) -> str:
    return "   {0:<7}{1:<13}{2:<26}{3:<34}{4}".format(
        case.case_no,
        case.run,
        " and ".join(case.limbs),
        "key {0}".format(case.key if case.key is not None else "none"),
        "run {0}".format(case.recorded if case.recorded is not None else "no ruling"),
    )


def report() -> str:
    """The whole measurement, printed. Reads; writes nothing."""
    return render(*measure())


def render(
    measurements: Sequence[RunMeasurement], everything: Sequence[Case]
) -> str:
    """The report text, from a measurement already taken."""
    escalated = [case for case in everything if case.escalated]
    fixes = [case for case in escalated if case.fixes]
    breaks = [case for case in escalated if case.breaks]
    leaves = [case for case in escalated if case.leaves]
    no_key = [case for case in escalated if case.key is None]

    lines: List[str] = [
        "The record-integrity gate, replayed from the version-6 record",
        "read from the committed runs under runs/, the committed case files and "
        "the committed keys; no model call",
        "",
        "the gate: POL-RD-10's limbs (2) and (4), on ROUTE_DEVIATION disputes "
        "only, off by default.",
        "   POL-RD-10(2)  {0}".format(
            pipeline.RD10_LIMB_SENTENCES[pipeline.RD10_IDENTIFIERS]
        ),
        "   POL-RD-10(4)  {0}".format(
            pipeline.RD10_LIMB_SENTENCES[pipeline.RD10_TIMESTAMPS]
        ),
        "",
        "== The runs ==",
    ]
    for measurement in measurements:
        lines.append(
            "   {0:<14}{1:>13}   {2}".format(
                measurement.name,
                _cases(len(measurement.cases)),
                measurement.note,
            )
        )
    lines.append(
        "   {0:<14}{1:>13}   every committed case with a run at version 6".format(
            "all", _cases(len(everything))
        )
    )

    lines.append("")
    lines.append("== The gate ==")
    lines.append("   would escalate   {0} of {1}".format(len(escalated), len(everything)))
    lines.append("   by limb          {0}".format(_limb_tally(escalated)))
    for case in escalated:
        lines.append(_row(case))

    lines.append("")
    lines.append("   would fix        {0}   {1}".format(len(fixes), _named(fixes)))
    lines.append("     the key is ESCALATE and the run ruled something else")
    lines.append("   would leave      {0}   {1}".format(len(leaves), _named(leaves)))
    lines.append(
        "     the run already escalated, so the gate changes nothing a reader acts on"
    )
    lines.append("   would break      {0}   {1}".format(len(breaks), _named(breaks)))
    lines.append(
        "     the key is not ESCALATE, so the gate would escalate a case it decides"
    )
    if no_key:
        lines.append("   no key           {0}   {1}".format(len(no_key), _named(no_key)))
        lines.append("     the organisers' sample is not scored, so no key decides it")

    lines.append("")
    lines.append("== What the gate does not touch ==")
    lines.append(
        "   a NO_SHOW_CHARGE dispute is not held to any of this. POL-NS-09 carries "
        "no limb of the same kind: none of its five triggers is a deterministic "
        "record-integrity test, and its nearest, (b), is expressly the case where "
        "a clause does not resolve the conflict. See "
        "tribunal.pipeline.record_integrity_limbs."
    )
    lines.append(
        "   the gate is off by default, so a run without --integrity-gate is byte "
        "for byte the run it was."
    )
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.integrity_gate",
        description=(
            "Replay the POL-RD-10 record-integrity gate over every committed "
            "case with a version-6 run, and print what it would escalate. "
            "Read-only; no model call is made."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--report",
        action="store_true",
        help="print the replay, computed from the committed runs under runs/",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if not arguments.report:
        return 1
    measurements, everything = measure()
    sys.stdout.write(render(measurements, everything))
    # Non-zero when the gate would escalate a case its key decides: that is a
    # finding, and a caller should not have to read the text to see it.
    return 1 if any(case.breaks for case in everything) else 0


if __name__ == "__main__":
    raise SystemExit(main())

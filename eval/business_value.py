"""What one run of the system is worth: the clock, the cost, and who decides.

Read-only, and no model call: every figure is read off the committed version-6
runs -- the four the product view is built from -- and the published prices
``eval/v6_runs.py`` bills at. It writes nothing, and it names no case of a
sealed set: the sealed figures are the submission's generalisation figures and
this module reads none of them.

Four figures, and the definition each is read under:

* **Time to a decision.** The wall clock one case takes, from the run's own
  ``wall_seconds``: the median and the 90th percentile over the cases the four
  runs hold. The clock is the system's, so a case that goes to a human is timed
  by the same rule and for the same reason.
* **Cost per case.** What one case was charged for -- prompt minus cached,
  cached, and completion, at the prices ``eval/v6_runs`` states -- and the
  median over the same cases.
* **Decided automatically, and sent to a human.** A case is **sent to a human**
  when it produced no ruling (an ``ESCALATE``) or when its ruling's monetary
  effect is above ``POL-GEN-05``'s execution threshold, which holds the money
  for release and places the case in the human queue by the policy itself.
  Every other case is **decided automatically**. That is the routing rule
  ``ops/queue.py`` states, read here rather than imported: nothing under
  ``eval/`` may import ``ops``, and this module is a reading rather than the
  router. ``POL-GEN-03`` states the one exception the money rule carries: on a
  ``DRIVER_COMPENSATION`` ruling the amount and the driver compensation are the
  same figure and are counted once.

**These are development and submission runs, not a generalisation figure.** The
three sealed sets are the generalisation figures, each run exactly once, and no
figure here is added to one of theirs.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade, v6_runs  # noqa: E402
from tribunal import loader  # noqa: E402

# The four runs the product view is built from: the corpus, ``dev-v2-ext``, the
# ``dev-v2`` prompt-injection case and the organisers' sample. The precedents
# run is deliberately absent -- it is the corpus's own fifteen route-deviation
# cases read a second time with the precedents block on, so counting it would
# count those fifteen twice.
RUNS: Tuple[v6_runs.V6Run, ...] = v6_runs.RUNS

# The labels the README states, once, so the table and the test that recomputes
# it cannot come to name the same figure two ways.
LABELS: Tuple[str, ...] = (
    "Time to a decision — median wall clock",
    "Time to a decision — 90th percentile wall clock",
    "Cost per case — median, at the published prices",
    "Decided automatically",
    "Sent to a human",
)


class BusinessValueError(Exception):
    """A reading this module cannot make."""


# --------------------------------------------------------------------------
# Reading the runs
# --------------------------------------------------------------------------
def documents() -> Dict[int, Mapping[str, Any]]:
    """Every case the four runs hold, by case number.

    The four runs cover disjoint cases, so the case number is a key rather than
    a coincidence; a collision would mean one run's case overwrote another's and
    is refused rather than resolved.
    """
    found: Dict[int, Mapping[str, Any]] = {}
    for run in RUNS:
        for case_no, document in v6_runs.documents(run.run_dir, run.cases).items():
            if case_no in found:
                raise BusinessValueError(
                    "case {0} is held by two of the four runs".format(case_no)
                )
            found[case_no] = document
    return found


def policy_version() -> int:
    """The policy version the runs were made at, read off their own records.

    A case file records the configuration its run was made with, so the version
    is read from the run rather than assumed. The four runs must agree; a set
    that disagreed would make the threshold below a figure about two policies.
    """
    versions = set()
    for document in documents().values():
        configuration = document.get("configuration")
        if isinstance(configuration, Mapping) and configuration.get("policy_version"):
            versions.add(int(configuration["policy_version"]))
    if len(versions) != 1:
        raise BusinessValueError(
            "the four runs do not agree on one policy version: {0}".format(
                sorted(versions)
            )
        )
    return versions.pop()


def execution_threshold(version: int) -> Optional[Decimal]:
    """``POL-GEN-05``'s execution threshold at one policy version.

    Read from the general policy through the loader's own API, so a figure the
    policy moved moves here. A version whose general policy carries no such key
    has no hold: nothing is above a threshold that is not there.
    """
    general = loader.load_policies(grade.CATEGORY_FOR_POLICY_LOOKUP, version)["general"]
    value = general.get("execution_threshold_sgd")
    if value is None:
        return None
    return Decimal(str(value))


def monetary_effect(ruling: Any, amount_sgd: Any, driver_compensation_sgd: Any) -> Decimal:
    """The money one ruling moves, the way ``ops/appeal.py`` reads it.

    ``POL-GEN-03`` states the one exception: on a ``DRIVER_COMPENSATION`` ruling
    the two money fields carry the same figure, which is the amount the ruling
    moves and not a second payment, so it is counted once. On every other ruling
    the two are independent and are added. A missing value is zero.
    """

    def value(cell: Any) -> Decimal:
        if cell is None or isinstance(cell, bool):
            return Decimal(0)
        try:
            return Decimal(str(cell))
        except Exception:
            return Decimal(0)

    amount = value(amount_sgd)
    driver = value(driver_compensation_sgd)
    if ruling == "DRIVER_COMPENSATION" and driver:
        return driver
    return amount + driver


def wall_seconds() -> List[Decimal]:
    """Every case's wall clock, in case-number order."""
    return [
        Decimal(str(document.get("wall_seconds") or 0))
        for _case_no, document in sorted(documents().items())
    ]


def costs_per_case() -> List[Decimal]:
    """Every case's cost, in case-number order, at the prices the runs are billed at."""
    costs: List[Decimal] = []
    for _case_no, document in sorted(documents().items()):
        tokens = document.get("tokens") or {}
        prompt = Decimal(tokens.get("prompt_tokens", 0))
        cached = Decimal(tokens.get("cached_tokens", 0))
        completion = Decimal(tokens.get("completion_tokens", 0))
        costs.append(
            (
                (prompt - cached) * v6_runs.PRICE_INPUT
                + cached * v6_runs.PRICE_CACHED_INPUT
                + completion * v6_runs.PRICE_OUTPUT
            )
            / v6_runs.MILLION
        )
    return costs


def lanes() -> Tuple[int, int, int, int]:
    """``(automatic, human, escalations, held)`` over the four runs.

    A case that produced no ruling is a human case, and so is one whose money is
    above the execution threshold; the two are counted separately as well, so a
    reader can see what sent each case to a person.
    """
    threshold = execution_threshold(policy_version())
    automatic = human = escalations = held = 0
    for _case_no, document in sorted(documents().items()):
        ruling = (document.get("ruling") or {}).get("ruling") or {}
        value = ruling.get("ruling")
        effect = monetary_effect(
            value, ruling.get("amount_sgd"), ruling.get("driver_compensation_sgd")
        )
        escalated = value == "ESCALATE"
        is_held = threshold is not None and effect > threshold
        escalations += 1 if escalated else 0
        held += 1 if is_held else 0
        if escalated or is_held:
            human += 1
        else:
            automatic += 1
    return automatic, human, escalations, held


# --------------------------------------------------------------------------
# The figures
# --------------------------------------------------------------------------
def figures() -> Dict[str, str]:
    """Every business-value figure the README states, recomputed from the runs."""
    walls = wall_seconds()
    costs = costs_per_case()
    automatic, human, _escalations, _held = lanes()
    total = automatic + human
    return {
        LABELS[0]: "{0} s".format(
            v6_runs._seconds(v6_runs._median(walls))
        ),
        LABELS[1]: "{0} s".format(
            v6_runs._seconds(v6_runs._percentile(walls, Decimal("0.9")))
        ),
        LABELS[2]: "{0:.4f} USD".format(v6_runs._median(costs)),
        LABELS[3]: "{0}/{1} = {2}".format(
            automatic, total, grade.render_percent(grade._percent(automatic, total))
        ),
        LABELS[4]: "{0}/{1} = {2}".format(
            human, total, grade.render_percent(grade._percent(human, total))
        ),
    }


def report() -> str:
    """The figures, the definition each is read under, and the runs behind them."""
    walls = wall_seconds()
    costs = costs_per_case()
    automatic, human, escalations, held = lanes()
    total = automatic + human
    threshold = execution_threshold(policy_version())
    lines: List[str] = [
        "What one run is worth, read off the version-6 runs",
        "==================================================",
        "",
        "The four runs the product view is built from, and no sealed set:",
    ]
    for run in RUNS:
        lines.append(
            "  {0:<12}{1} case(s)".format(run.name, len(run.cases))
        )
    lines.extend(
        [
            "  total       {0} case(s), at policy version {1}".format(
                total, policy_version()
            ),
            "",
            "  time to a decision   median {0} s   p90 {1} s".format(
                v6_runs._seconds(v6_runs._median(walls)),
                v6_runs._seconds(v6_runs._percentile(walls, Decimal("0.9"))),
            ),
            "  cost per case        median {0:.4f} USD   p90 {1:.4f} USD".format(
                v6_runs._median(costs),
                v6_runs._percentile(costs, Decimal("0.9")),
            ),
            "  decided automatically {0}".format(
                "{0}/{1} = {2}".format(
                    automatic,
                    total,
                    grade.render_percent(grade._percent(automatic, total)),
                )
            ),
            "  sent to a human       {0}".format(
                "{0}/{1} = {2}".format(
                    human, total, grade.render_percent(grade._percent(human, total))
                )
            ),
            "    {0} produced no ruling, {1} held above the execution threshold".format(
                escalations, held
            ),
            "",
            "  the execution threshold is POL-GEN-05's own figure at this version: {0}".format(
                "none" if threshold is None else str(threshold)
            ),
            "  the prices are eval/v6_runs': input {0}, cached input {1}, output {2} USD "
            "per million tokens".format(
                v6_runs.PRICE_INPUT, v6_runs.PRICE_CACHED_INPUT, v6_runs.PRICE_OUTPUT
            ),
            "",
            "These are development and submission runs and are not a generalisation",
            "figure. The three sealed sets are, and this module reads none of them.",
        ]
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.business_value",
        description=(
            "What one run is worth, from the committed version-6 runs: the time "
            "to a decision, the cost per case, and the share decided "
            "automatically against the share sent to a human. Reads and writes "
            "nothing, and makes no model call."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print every figure; the only thing this command does",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the figures. Nothing is written and no model is called."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.report:
        parser.error("nothing to do: pass --report (this module writes nothing)")
    sys.stdout.write(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

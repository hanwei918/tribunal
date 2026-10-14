"""Every figure the product site shows that comes from a run, computed here.

The policy owner's pages state figures -- a median time, a cost, the lane counts,
the two cases the featured cards are built on -- and a figure typed into a page
is a figure that can drift away from the file it came from. This module reads
each one back out of the committed runs with the ``eval`` functions the README's
own table tests use, so the pages and the repository cannot come to state the
same number two ways. ``tests/test_site_figures.py`` binds every one of them to
the page that shows it, in both languages.

**No model call, no network.** Every reading is a committed run, a committed
key or a frozen measurement, exactly as ``eval.v6_runs --report``,
``eval.business_value --report``, ``eval.func_sets --report`` and
``eval.fairness --report`` read them.

What is read, and from where
----------------------------
* the four version-6 development runs, through :mod:`eval.business_value` for
  the wall clock, the cost and the lanes, and through :mod:`eval.v6_runs` for
  the medians and the percentiles;
* the same four runs' own case files and transcripts, through
  :mod:`ui.v2.build`'s readers, for the featured cases' figures;
* ``inject-v1``'s committed run, through :mod:`eval.func_sets`;
* the two measured development runs' transcripts, through :mod:`eval.fairness`,
  for the position swap and the calibration error;
* the sealed and held-out sets, through the same
  :func:`eval.run_benchmark.grade_run` over the same
  :func:`eval.development_sets.named(...).run_dir` calls that
  ``tests/test_readme_figures.py`` grades them with;
* the three version-7 sets -- ``sealed-v4``, ``ryde-v7`` and ``dev-v7``, the
  policy version 7 runs of 2026-10-13/14 -- through the same call, over the
  directory each run was **written to**:
  :func:`eval.development_sets.run_dir_at_its_version` moves a set registered
  for a policy base one level down (``runs/dev-v7/policy-v7/<model>/``), which
  is where ``tools/check_figures.py``'s own ``graded_version_seven`` reads them;
* the two version-8 sets -- ``ryde-v8`` and ``dev-v8``, the policy version 8
  runs of 2026-10-14, v2.1 with Ryde's answers -- through the same call, over
  ``runs/<set>/policy-v8/<model>/`` for the same reason.

The figure names are the module's own; the strings are what the pages show, to
the page's own formatting -- ``"160.4 s"``, ``"$0.058"``, ``"12/12"`` -- so a
test can assert the page carries the figure rather than a number near it.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    business_value,
    development_sets,
    fairness,
    func_sets,
    grade,
    run_benchmark,
    v6_runs,
)
from tribunal import referee as referee_module  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

MODEL = run_benchmark.resolve_model(None)

# The case the how-it-works page walks through, the organisers' sample, and the
# safety flag the featured cards name. Named here so a reading of another case
# is a change to this list rather than a number typed into a function.
FEATURED_CASE = 208
SAMPLE_CASE = 901
SAFETY_CASE = 2735


# --------------------------------------------------------------------------
# The runs
# --------------------------------------------------------------------------
def cases_by_number() -> Dict[int, "v2.CaseData"]:
    """Every case of the four version-6 runs, by case number."""
    return {case.case_no: case for case in v2.read_every_case()}


def graded_set(name: str) -> "grade.GradeReport":
    """One set's committed run, graded against its own key.

    The ``eval.run_benchmark.grade_run`` call that
    ``tests/test_readme_figures.py`` grades the same sets with, over the
    directory the run was **written to**. The held-out set and the sealed sets
    carry keys of their own and keep their own directory; a set registered for a
    policy base writes its run one level down under that directory, so
    ``dev-v7`` and ``ryde-v7`` are read at
    ``runs/<set>/policy-v7/<model>/`` -- the un-versioned path holds nothing.
    The briefs are rebuilt at the set's own registered version, which is the one
    its run was decided under.
    """
    development_set = development_sets.named(name)
    return run_benchmark.grade_run(
        development_sets.run_dir_at_its_version(development_set, MODEL),
        development_set.key(),
        case_loader=development_set.load_case,
        policy_version=development_set.policy_version,
    )


def v6_report(name: str) -> "grade.GradeReport":
    """One version-6 run graded, through the grader ``eval.v6_runs`` itself uses."""
    run = v6_runs.run_by_name(name)
    documents = v6_runs.documents(run.run_dir, run.cases)
    key = grade.load_answer_key(run.key_path) if run.key_path is not None else {}
    return v6_runs._grade_run(run, documents, key)


def pair(exact: int, total: int) -> str:
    """``112/151`` -- the page's own way of stating a count against its total."""
    return "{0}/{1}".format(exact, total)


def interval(low: float, high: float, separator: str, precision: int = 1) -> str:
    """A Wilson interval as one page spells it, from ``eval.v6_runs.wilson``.

    The two pages spell it differently -- ``results.html``'s table writes
    ``90.6-98.2%`` and the front page writes ``75.8%, 100%`` -- so the separator
    is the caller's and the bounds are the measurement's.
    """
    return "{0:.{2}f}{1}{3:.{2}f}%".format(
        low * 100, separator, precision, high * 100
    )


# --------------------------------------------------------------------------
# The figures
# --------------------------------------------------------------------------
def figures() -> Dict[str, str]:
    """Every run-derived figure the pages show, by the name this module gives it.

    Computed once per call; the caller holds the result. The values are the
    strings the pages carry, so a page and this module are compared as text.
    """
    business = business_value.figures()
    walls = business_value.wall_seconds()
    costs = business_value.costs_per_case()
    automatic, human, escalations, held = business_value.lanes()
    total = automatic + human

    median_wall = v6_runs._median(walls)
    p90_wall = v6_runs._percentile(walls, Decimal("0.9"))
    median_cost = v6_runs._median(costs)
    cost_mean = sum(costs) / len(costs)

    triggers = {
        v2.TRIGGER_SCOPE: 0,
        v2.TRIGGER_NO_VALID_DRAFTS: 0,
        v2.TRIGGER_NO_MAJORITY: 0,
        v2.TRIGGER_JUDGE: 0,
    }
    for case in cases_by_number().values():
        if case.trigger is not None:
            triggers[case.trigger] = triggers.get(case.trigger, 0) + 1

    _lean, swap, calibration = fairness.combined_measurements()

    readings = func_sets.injection_readings()
    injected_escalations = sum(
        1 for reading in readings if reading.injected.ruling == v2.ESCALATE
    )
    unchanged = sum(1 for reading in readings if reading.same_fields)
    flipped = sum(
        1
        for reading in readings
        if reading.injected.ruling != reading.clean.ruling
        and reading.injected.ruling != v2.ESCALATE
    )

    dev = v6_report("dev-v2-ext")
    dev_calibration = dev.calibration
    true_positives = len(dev_calibration.true_positives)
    corpus = v6_report("corpus")
    with_precedents, without_precedents = precedent_pair()
    dev_bounds = v6_runs.wilson(dev.exact_matches, dev.total)

    featured = featured_case_figures()

    figures: Dict[str, str] = {
        # Time and cost, over the 151 cases of the four version-6 runs. The
        # seconds are bare numbers because the two languages write the unit
        # differently -- "585 s" in English, "585 \u79d2" in Chinese -- and the page
        # is what carries the unit.
        "median_wall_seconds": v6_runs._seconds(median_wall),
        "median_wall_minutes": "{0:.1f}".format(median_wall / 60),
        "p90_wall_seconds": v6_runs._seconds(p90_wall),
        "p90_wall_minutes": "{0:.1f}".format(p90_wall / 60),
        "median_cost_usd": "{0:.4f}".format(median_cost),
        "median_cost_dollars": "${0:.3f}".format(median_cost),
        "cost_sum_usd": "{0:.2f}".format(sum(costs)),
        "cost_per_1000_usd": "${0:.0f}".format(cost_mean * 1000),
        # The lanes, and the four reasons a case reached a person.
        "cases_total": str(total),
        "decided_automatically": str(automatic),
        "held_for_release": str(held),
        "no_ruling": str(escalations),
        "decided_share": "{0:.0f}%".format(Decimal(automatic) / Decimal(total) * 100),
        "trigger_safety": str(triggers[v2.TRIGGER_SCOPE]),
        "trigger_failed_checks": str(triggers[v2.TRIGGER_NO_VALID_DRAFTS]),
        "trigger_split": str(triggers[v2.TRIGGER_NO_MAJORITY]),
        "trigger_judge": str(triggers[v2.TRIGGER_JUDGE]),
        # The two robustness measurements.
        "position_swap_agreed": str(swap.agree_all_four),
        "position_swap_total": str(swap.total),
        "calibration_error": fairness.calibration_error_cell(calibration),
        # The injection set.
        "inject_total": str(len(readings)),
        "inject_flipped": str(flipped),
        "inject_unchanged": str(unchanged),
        "inject_sent_to_a_person": str(injected_escalations),
        # The featured cases.
        "case_208_evidence": str(featured["208"]["evidence"]),
        "case_208_rider_points": str(featured["208"]["rider_points"]),
        "case_208_driver_points": str(featured["208"]["driver_points"]),
        "case_208_claims": str(featured["208"]["claims"]),
        "case_208_claims_kept": pair(featured["208"]["kept"], featured["208"]["claims"]),
        "case_208_driver_amount": v2._money(
            featured["208"]["driver_amount"], featured["208"]["currency"]
        ),
        "case_208_confidence": str(featured["208"]["confidence"]),
        "case_208_waiting_seconds": v2._whole(featured["208"]["waiting"]),
        "case_208_wall_seconds": v2._seconds(featured["208"]["wall"]).split(" ")[0],
        "case_901_driver_amount": v2._money(
            featured["901"]["driver_amount"], featured["901"]["currency"]
        ),
        "case_901_confidence": str(featured["901"]["confidence"]),
        "case_2735_model_calls": str(featured["2735"]["calls"]),
        # The development sets at policy version 6.
        "dev_v2_ext_exact": pair(dev.exact_matches, dev.total),
        "dev_v2_ext_interval": interval(dev_bounds[0], dev_bounds[1], "-"),
        "dev_v2_ext_precision": pair(
            true_positives, true_positives + len(dev_calibration.false_positives)
        ),
        "dev_v2_ext_recall": pair(
            true_positives, true_positives + len(dev_calibration.false_negatives)
        ),
        "corpus_v6_exact": pair(corpus.exact_matches, corpus.total),
        "precedents_with": pair(with_precedents[0], with_precedents[1]),
        "precedents_without": pair(without_precedents[0], without_precedents[1]),
    }

    # The sealed and held-out sets, graded through the same calls the README's
    # table tests grade them with. Each set is graded once and read twice.
    sealed = {
        name: graded_set(name) for name in ("wild-v2", "sealed-v1", "sealed-v2")
    }
    for name, prefix in (
        ("wild-v2", "wild_v2"),
        ("sealed-v1", "sealed_v1"),
        ("sealed-v2", "sealed_v2"),
    ):
        report = sealed[name]
        figures["{0}_exact".format(prefix)] = pair(report.exact_matches, report.total)
    fourth = sealed["sealed-v2"]
    bounds = v6_runs.wilson(fourth.exact_matches, fourth.total)
    figures["sealed_v2_interval"] = "{0:.1f}%, {1:.0f}%".format(
        bounds[0] * 100, bounds[1] * 100
    )
    figures["sealed_v1_imported"] = pair(sealed["sealed-v1"].exact_matches - 1, 24)

    # Policy version 7 -- Ryde's own Dispute Resolution Policy v2.1, adopted
    # 2026-10-13. Three sets, one run each, each graded once here. The interval
    # is the fourth sealed set's, spelt exactly as the second sealed set's is:
    # the page writes the percent sign once and the two bounds bare.
    version_seven = {
        name: graded_set(name) for name in ("sealed-v4", "ryde-v7", "dev-v7")
    }
    fourth_v7 = version_seven["sealed-v4"]
    v7_bounds = v6_runs.wilson(fourth_v7.exact_matches, fourth_v7.total)
    figures["sealed_v4_exact"] = pair(fourth_v7.exact_matches, 30)
    figures["sealed_v4_interval"] = "{0:.1f}%, {1:.0f}%".format(
        v7_bounds[0] * 100, v7_bounds[1] * 100
    )
    figures["ryde_v7_exact"] = pair(version_seven["ryde-v7"].exact_matches, 2)
    figures["dev_v7_exact"] = pair(version_seven["dev-v7"].exact_matches, 40)

    # Policy version 8 -- v2.1 with Ryde's answers of 2026-10-14. Two sets, one
    # run each, each graded once here. ``ryde-v8`` and ``dev-v8`` reuse the
    # version-7 case files and are registered for the version-8 base, so
    # :func:`graded_set` reads them at ``runs/<set>/policy-v8/<model>/``.
    version_eight = {
        name: graded_set(name) for name in ("ryde-v8", "dev-v8")
    }
    figures["ryde_v8_exact"] = pair(version_eight["ryde-v8"].exact_matches, 2)
    figures["dev_v8_exact"] = pair(version_eight["dev-v8"].exact_matches, 40)
    return figures


def precedent_pair() -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """The 15 route-deviation cases graded with the precedents block and without.

    The reading ``tests/test_readme_figures.py`` makes: the precedents run's own
    documents against the corpus key, and the corpus's own rulings for the same
    fifteen cases reduced a second time.
    """
    corpus = v6_runs.run_by_name("corpus")
    key = grade.load_answer_key(corpus.key_path)
    subset = {case_no: key[case_no] for case_no in v6_runs.ROUTE_DEVIATION_CASES}
    precedents = v6_runs.PRECEDENTS_RUN
    with_precedents = v6_runs._grade_run(
        precedents,
        v6_runs.documents(precedents.run_dir, precedents.cases),
        key,
    )
    corpus_documents = v6_runs.documents(corpus.run_dir, corpus.cases)
    without_precedents = grade.grade(
        {
            case_no: corpus_documents[case_no].get("ruling")
            for case_no in v6_runs.ROUTE_DEVIATION_CASES
        },
        subset,
        corpus=subset,
    )
    return (
        (with_precedents.exact_matches, with_precedents.total),
        (without_precedents.exact_matches, without_precedents.total),
    )


def featured_case_figures() -> Dict[str, Dict[str, Any]]:
    """The three cases the pages name, read off their own run records.

    Every number is read: the brief's evidence list and its dwell, the two
    advocates' own claim lists, the referee's verdict on each claim, the ruling's
    amount and confidence, and the run's wall clock. A model call count is the
    number of entries the transcript recorded, which is zero for a case the
    scope gate stopped before any client was built.
    """
    cases = cases_by_number()
    found: Dict[str, Dict[str, Any]] = {}
    for case_no in (FEATURED_CASE, SAMPLE_CASE, SAFETY_CASE):
        case = cases[case_no]
        claims = v2._claims(case.transcript, "RIDER") + v2._claims(case.transcript, "DRIVER")
        arrival = v2._derived_block(case.brief, "GPS_TRACE", "arrival")
        found[str(case_no)] = {
            "currency": case.policy.currency,
            "evidence": len(v2._evidence(case.brief)),
            "rider_points": len(v2._claims(case.transcript, "RIDER")),
            "driver_points": len(v2._claims(case.transcript, "DRIVER")),
            "claims": len(claims),
            "kept": sum(
                1 for claim in claims if claim["status"] == referee_module.STATUS_KEPT
            ),
            "waiting": v2._fact_value(arrival or {}, "accumulated_dwell", "longest_run_sec"),
            "wall": case.document.get("wall_seconds"),
            "driver_amount": case.ruling.get("driver_compensation_sgd"),
            "confidence": case.ruling.get("confidence"),
            "calls": len(case.transcript.get("entries") or []),
        }
    return found


def page_figures() -> Dict[str, str]:
    """The figures, with the reading cached for the process."""
    global _FIGURES
    if _FIGURES is None:
        _FIGURES = figures()
    return dict(_FIGURES)


_FIGURES: "Dict[str, str] | None" = None


def named(name: str) -> str:
    """One figure by name, refusing a name this module does not state."""
    values = page_figures()
    if name not in values:
        raise KeyError(
            "{0!r} is not a figure this module reads; it states {1}".format(
                name, ", ".join(sorted(values))
            )
        )
    return values[name]

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
  ``runs/<set>/policy-v8/<model>/`` for the same reason;
* the organisers' own two samples, at version 8, off the ``ryde-v8`` set's own
  case files: their version-8 briefs for the distances, the excess distance fare
  and the free wait, the committed run's own case document and transcript for
  the judge's four drafts, and ``policy/v8/general.json`` for the thresholds the
  safety page states.

The figure names are the module's own; the strings are what the pages show, to
the page's own formatting -- ``"160.4 s"``, ``"$0.058"``, ``"12/12"`` -- so a
test can assert the page carries the figure rather than a number near it.
"""

from __future__ import annotations

import json
import re
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
    v8_report,
)
from tribunal import brief as brief_module  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import policy_versions  # noqa: E402
from tribunal import referee as referee_module  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

MODEL = run_benchmark.resolve_model(None)

# The organisers' own two samples, read at policy version 8 -- the set that
# carries v2.1 with Ryde's answers of 2026-10-14. The two cases are the ones the
# version-7 set already held, keyed as Ryde's own answer of that day leaves them.
RYDE_SAMPLES_SET = "ryde-v8"
RYDE_DEVIATION_CASE = 902
RYDE_NO_SHOW_CASE = 903

# Policy version 8 -- v2.1 with Ryde's answers of 2026-10-14 -- is what the
# submission applies, and it is what the pages describe as how Tribunal decides
# now. Every version-8 figure is measured on the ``dev-v8`` run's 40 development
# cases unless a name says otherwise, and the case the how-it-works page walks
# through is 5051.
V8_SET = "dev-v8"
V8_CASE = 5051

# The version-8 authority gate's three limbs, as a gated case's own ruling
# explanation opens. A case the gate stopped has **no vote in its transcript**
# and an explanation that begins "Under <clause>"; the clause it opens with is
# the limb that fired.
V8_GATE_CLAUSES: Mapping[str, str] = {
    "POL-RD-25": "2km",
    "POL-GEN-22": "value",
    "POL-GEN-21": "safety",
}
V8_GATE_OPENING_RE = re.compile(r"^Under (POL-[A-Z]+-\d+)\b")

# The two vote outcomes that mean the panel carried what its drafts agreed on.
CARRIED_OUTCOMES: Tuple[str, ...] = (
    pipeline_module.VOTE_CARRIED,
    pipeline_module.VOTE_CARRIED_NOT_UNANIMOUS,
)


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

    # The organisers' own two samples, at version 8 -- Ryde's own Dispute
    # Resolution Policy v2.1 with Ryde's answers of 2026-10-14. Every figure is
    # read: the two version-8 briefs' own distances, excess distance fare and
    # free wait, the committed run's own case document and transcript for the
    # judge's four drafts, and the version-8 general policy for the thresholds
    # the safety page states.
    deviation_brief = version_eight_brief(RYDE_DEVIATION_CASE)
    no_show_brief = version_eight_brief(RYDE_NO_SHOW_CASE)
    actual_km = _derived_value(
        deviation_brief, "TRIP_RECORD", "v7", "deviation", "actual_distance_km"
    )
    optimal_km = _derived_value(
        deviation_brief, "TRIP_RECORD", "v7", "deviation", "optimal_distance_km"
    )
    deviation_km = _derived_value(
        deviation_brief, "TRIP_RECORD", "v7", "deviation", "deviation_km"
    )
    limit_km = _derived_value(
        deviation_brief, "TRIP_RECORD", "v7", "deviation", "ai_limit_km"
    )
    excess_sgd = _derived_value(
        deviation_brief, "FARE_BREAKDOWN", "money", "excess_distance_fare_sgd"
    )
    rate_sgd = _derived_value(
        deviation_brief, "FARE_BREAKDOWN", "money", "per_km_rate_sgd"
    )
    arrived_at = _derived_value(
        no_show_brief, "TRIP_RECORD", "v7", "free_wait", "arrived_at"
    )
    wait_ends_at = _derived_value(
        no_show_brief, "TRIP_RECORD", "v7", "free_wait", "ends_at"
    )
    cancelled_at = _derived_value(
        no_show_brief, "TRIP_RECORD", "v7", "free_wait", "cancelled_at"
    )
    required_confidence = no_show_brief["case"]["authority"]["required_confidence"][
        "value"
    ]
    gps_fixes = _derived_value(no_show_brief, "GPS_TRACE", "v7", "point_count")
    drafts = ryde_no_show_drafts()
    thresholds = version_eight_thresholds()

    # Policy version 8 -- the same policy text the two samples above are read
    # at, measured over the 40 cases of ``dev-v8``. The measurements come from
    # ``eval.v8_report``, which reads the committed run itself, and the lane
    # counts from each escalated case's own document.
    measured = version_eight_measurements()
    v8_escalations = version_eight_escalations()
    walkthrough = case_fifty_one_figures()
    version_eight_cases = (
        len(development_sets.named(V8_SET).cases)
        + len(development_sets.named(RYDE_SAMPLES_SET).cases)
    )

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
        # The organisers' two samples at version 8. A distance and an amount are
        # written to the decimal place their unit is read at -- the brief holds
        # "0.8" where the page states "0.80" -- and the three clock times are the
        # hour and minute the record carries.
        "ryde902_actual_km": "{0:.1f}".format(Decimal(str(actual_km))),
        "ryde902_optimal_km": "{0:.1f}".format(Decimal(str(optimal_km))),
        "ryde902_deviation_km": "{0:.2f}".format(Decimal(str(deviation_km))),
        "ryde902_limit_km": "{0:.1f}".format(Decimal(str(limit_km))),
        "ryde902_excess_sgd": "{0:.2f}".format(Decimal(str(excess_sgd))),
        "ryde902_rate_sgd": "{0:.2f}".format(Decimal(str(rate_sgd))),
        "ryde903_arrived": _clock(arrived_at),
        "ryde903_free_wait_ends": _clock(wait_ends_at),
        "ryde903_cancelled": _clock(cancelled_at),
        "ryde903_required_confidence": str(required_confidence),
        "ryde903_gps_fixes": str(gps_fixes),
        "ryde903_drafts_escalate": str(drafts["escalate"]),
        "ryde903_drafts_fee": str(drafts["fee"]),
        "ryde903_drafts_voided": str(drafts["voided"]),
        "v8_ai_final_below": thresholds["ai_final_below"],
        "v8_human_above": thresholds["human_above"],
        "v8_confidence_between": thresholds["confidence_between"],
        "v8_confidence_fraud": thresholds["confidence_fraud"],
        # Policy version 8's own measurements, over ``dev-v8``'s 40 cases: the
        # clock, the cost, the share the AI decided, the lanes the other cases
        # took, the position swap and the calibration.
        "v8_cases": str(measured.cases),
        "v8_case_pages": str(version_eight_cases),
        "v8_median_seconds": "{0} s".format(v6_runs._seconds(measured.wall_median)),
        "v8_median_minutes": "{0:.1f}".format(measured.wall_median / 60),
        "v8_p90_seconds": "{0} s".format(v6_runs._seconds(measured.wall_p90)),
        "v8_median_cost_usd": "{0:.4f}".format(measured.cost_median),
        "v8_median_cost_dollars": "${0:.3f}".format(measured.cost_median),
        "v8_median_cost_cents": "about {0:.0f} cents".format(
            measured.cost_median * 100
        ),
        "v8_median_cost_cents_zh": "\u7ea6 {0:.0f} \u7f8e\u5206".format(
            measured.cost_median * 100
        ),
        "v8_decided": "{0} of {1}".format(
            measured.decided_with_no_person, measured.cases
        ),
        "v8_decided_count": str(measured.decided_with_no_person),
        "v8_decided_share": "{0:.0f}%".format(
            Decimal(measured.decided_with_no_person)
            / Decimal(measured.cases)
            * 100
        ),
        "v8_to_person": str(measured.escalated_produced),
        "v8_route_limit_km": version_eight_route_limit(),
        "v8_gate_2km": str(v8_escalations["2km"]),
        "v8_gate_value": str(v8_escalations["value"]),
        "v8_gate_safety": str(v8_escalations["safety"]),
        "v8_gate_total": str(
            v8_escalations["2km"]
            + v8_escalations["value"]
            + v8_escalations["safety"]
        ),
        "v8_panel_escalated": str(v8_escalations["panel"]),
        "v8_no_majority": str(v8_escalations["no_majority"]),
        "v8_swap": "{0} of {1}".format(
            measured.swap.agree_all_four, measured.swap.total
        ),
        "v8_swap_agreed": str(measured.swap.agree_all_four),
        "v8_swap_total": str(measured.swap.total),
        "v8_ece": fairness.render_ece(measured.calibration.ece),
        "v8_drafts": str(measured.calibration.total),
        # The case the how-it-works page walks through, case 5051 of dev-v8.
        "case5051_evidence": str(walkthrough["evidence"]),
        "case5051_rider_points": str(walkthrough["rider_points"]),
        "case5051_driver_points": str(walkthrough["driver_points"]),
        "case5051_claims": str(walkthrough["claims"]),
        "case5051_claims_kept": pair(walkthrough["kept"], walkthrough["claims"]),
        "case5051_dropped": str(walkthrough["claims"] - walkthrough["kept"]),
        "case5051_agree": "{0} of {1}".format(
            walkthrough["agreeing"], walkthrough["votes"]
        ),
        "case5051_confidence": str(walkthrough["confidence"]),
        "case5051_wait_seconds": v2._whole(walkthrough["wait"]),
        "case5051_free_wait_seconds": v2._whole(walkthrough["free_wait"]),
        "case5051_amount": v2._money(
            walkthrough["driver_amount"], walkthrough["currency"]
        ),
        "case5051_wall": v2._seconds(walkthrough["wall"]),
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
    # The sixth hidden set's own lane: the cases that needed a person. The run
    # sent the same nine the key does, which is why the sentence says all nine
    # got one.
    figures["sealed_v4_to_person"] = str(
        len(fourth_v7.calibration.produced_escalations)
    )

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


# --------------------------------------------------------------------------
# The organisers' own two samples, at version 8
# --------------------------------------------------------------------------
def version_eight_brief(case_no: int) -> Dict[str, Any]:
    """One of the organisers' samples, briefed at the version its run used.

    ``build_brief_for_case`` at the version the ``ryde-v8`` registration fixes,
    over the case file the set's own ``case_root`` holds. That version is 8 --
    version 7's policy text with Ryde's answers of 2026-10-14 -- and it is read
    off the registration rather than typed here, so the brief is the one the
    committed run was decided under.
    """
    development_set = development_sets.named(RYDE_SAMPLES_SET)
    return brief_module.build_brief_for_case(
        development_set.load_case(case_no),
        policy_version=development_set.policy_version,
    )


def _derived_value(brief: Mapping[str, Any], evidence_type: str, *path: str) -> Any:
    """One derived figure, off the artifact of ``evidence_type`` that carries it.

    The path is the artifact's own. The version-7 block is keyed ``v7`` because
    a later version on this base is the same policy text with a settled reading
    rather than a second brief, and the fare record's money block sits at the top
    of the same object rather than under that key.
    """
    for artifact in brief["case"]["evidence"]:
        if artifact.get("evidence_type") != evidence_type:
            continue
        node: Any = (artifact.get("payload") or {}).get("derived") or {}
        for key in path:
            node = node[key]
        return node["value"]
    raise KeyError(
        "the brief carries no {0} artifact, so {1} cannot be read".format(
            evidence_type, "/".join(path)
        )
    )


def _clock(timestamp: Any) -> str:
    """A recorded timestamp as the page writes it: the hour and minute it carries."""
    return str(timestamp).split("T", 1)[1][:5]


def _sgd_whole(value: Any) -> str:
    """A threshold in whole SGD, without the cents the policy file spells it with."""
    return format(Decimal(str(value)).normalize(), "f")


def ryde_sample_run_dir() -> Path:
    """The directory the organisers' two samples were run into.

    ``run_dir_at_its_version`` moves a set registered for a policy base one level
    down, so the run is at ``runs/ryde-v8/policy-v8/<model>/``.
    """
    development_set = development_sets.named(RYDE_SAMPLES_SET)
    return development_sets.run_dir_at_its_version(development_set, MODEL)


def ryde_no_show_drafts() -> Dict[str, int]:
    """The no-show sample's four judge drafts, counted by what each one did.

    Read from the run's own case document, which names the transcript beside it,
    and that transcript's vote block. Each draft records the proposal it made, so
    a draft that proposed ``ESCALATE``, a draft that upheld the fee by proposing
    ``DRIVER_COMPENSATION``, and a draft the code checks refused -- its proposal
    is ``null`` and its abstention names the reason -- are counted apart.
    """
    run_dir = ryde_sample_run_dir()
    document = json.loads(
        (run_dir / "case-{0:05d}.json".format(RYDE_NO_SHOW_CASE)).read_text(
            encoding="utf-8"
        )
    )
    transcript = json.loads(
        (run_dir / document["transcript_file"]).read_text(encoding="utf-8")
    )
    proposals = [
        (draft.get("proposal") or {}).get("ruling")
        for draft in transcript["vote"]["drafts"]
    ]
    return {
        "escalate": sum(
            1 for ruling in proposals if ruling == pipeline_module.ESCALATE
        ),
        "fee": sum(
            1 for ruling in proposals if ruling == pipeline_module.DRIVER_COMPENSATION
        ),
        "voided": sum(1 for ruling in proposals if ruling is None),
    }


def version_eight_thresholds() -> Dict[str, str]:
    """``policy/v8/general.json``'s thresholds, as the safety page writes them.

    Read from the version-8 base's own general policy file -- the file the
    version-8 briefs are built from -- rather than from a second copy of the
    numbers.
    """
    general = json.loads(
        (policy_versions.base_directory(8) / "general.json").read_text(
            encoding="utf-8"
        )
    )
    thresholds = general["thresholds"]
    return {
        "ai_final_below": _sgd_whole(thresholds["ai_final_below_sgd"]),
        "human_above": _sgd_whole(thresholds["human_above_sgd"]),
        "confidence_between": str(thresholds["confidence_required_between_sgd"]),
        "confidence_fraud": str(thresholds["confidence_required_with_fraud_flag"]),
    }


# --------------------------------------------------------------------------
# Policy version 8 -- v2.1 with Ryde's answers of 2026-10-14
# --------------------------------------------------------------------------
def _inner_ruling(document: Mapping[str, Any]) -> Mapping[str, Any]:
    """A run document's ruling, one level down -- the shape ``ui.v2.build`` reads."""
    block = document.get("ruling")
    inner = block.get("ruling") if isinstance(block, Mapping) else None
    return inner if isinstance(inner, Mapping) else {}


def version_eight_run_dir() -> Path:
    """The directory the ``dev-v8`` run was written to.

    ``dev-v8`` is registered for the version-8 policy base, so its run sits one
    level down at ``runs/dev-v8/policy-v8/<model>/`` -- the path
    :func:`graded_set` and ``ui.v8.build`` both read.
    """
    return development_sets.run_dir_at_its_version(
        development_sets.named(V8_SET), MODEL
    )


def version_eight_measurements() -> "v8_report.Measurements":
    """The ``dev-v8`` measurements, by the module that measures them.

    ``eval.v8_report`` (part 90) reads the committed run through the same
    functions ``eval.v6_runs`` measures the version-6 runs with, so a figure the
    pages state here is the figure ``python3 -m eval.v8_report --report`` prints
    rather than a second reading of the same files: the wall clock's median and
    90th percentile, the model cost's median, the cases decided with no person,
    the position swap, the calibration error and the draft count.
    """
    return v8_report.measure(V8_SET)


def _gate_limb(explanation: Any) -> str:
    """Which version-8 limb stopped a case, from its own explanation's first words.

    A gated case's explanation opens "Under <clause>". The clause is read rather
    than the reason code, and a case whose explanation opens with a clause this
    table does not state is refused rather than counted somewhere else.
    """
    match = V8_GATE_OPENING_RE.match(str(explanation or ""))
    if match is None or match.group(1) not in V8_GATE_CLAUSES:
        raise KeyError(
            "an escalated case's explanation opens with {0!r}, which is not one "
            "of the version-8 gate's clauses: {1}".format(
                str(explanation or "")[:40], ", ".join(sorted(V8_GATE_CLAUSES))
            )
        )
    return V8_GATE_CLAUSES[match.group(1)]


def version_eight_escalations() -> Dict[str, int]:
    """The ``dev-v8`` cases that went to a person, by how they got there.

    **The rule.** A case the version-8 authority gate stopped **before the judge
    was asked** has no ``vote`` in its transcript, and its ruling explanation
    begins "Under POL-RD-25" (the 2 km ceiling on an AI ruling), "Under
    POL-GEN-22" (a value above the second band edge) or "Under POL-GEN-21" (a
    safety flag); the clause the explanation opens with is the limb that fired,
    and the three limbs are counted apart. Every other escalated case **was**
    asked of the judge: one whose vote outcome is ``carried`` is a panel that
    sent the case on, and one whose vote did not carry is a panel with no
    majority.

    Read off each escalated case's own run document and the transcript that
    document names, so a case that moves from one lane to another moves the
    figure with it.
    """
    run_dir = version_eight_run_dir()
    counts = {"2km": 0, "value": 0, "safety": 0, "panel": 0, "no_majority": 0}
    for case_no in sorted(development_sets.named(V8_SET).cases):
        document = json.loads(
            (run_dir / "case-{0:05d}.json".format(case_no)).read_text(
                encoding="utf-8"
            )
        )
        ruling = _inner_ruling(document)
        if ruling.get("ruling") != pipeline_module.ESCALATE:
            continue
        transcript = json.loads(
            (run_dir / document["transcript_file"]).read_text(encoding="utf-8")
        )
        vote = transcript.get("vote")
        if vote is None:
            counts[_gate_limb(ruling.get("explanation"))] += 1
        elif vote.get("outcome") in CARRIED_OUTCOMES:
            counts["panel"] += 1
        else:
            counts["no_majority"] += 1
    return counts


def version_eight_route_limit() -> str:
    """The route deviation above which v2.1 sends a case to a person.

    Read from ``policy/v8/route_deviation.json`` -- the file the version-8
    briefs are built from -- rather than from a second copy of the number, and
    written as whole kilometres because that is how the pages state it.
    """
    route = json.loads(
        (policy_versions.base_directory(8) / "route_deviation.json").read_text(
            encoding="utf-8"
        )
    )
    return _sgd_whole(route["thresholds"]["ai_ruling_max_deviation_km"])


def case_fifty_one_figures() -> Dict[str, Any]:
    """Case 5051 of ``dev-v8``, read off its own run, brief and vote.

    Every figure the how-it-works page walks through: the brief's own evidence
    list, the two advocates' own claim lists, the referee's verdict on each
    claim (one of the driver's eight was discarded, for
    ``IMPAIRMENT_UNDISCLOSED``), the vote's agreement over its four drafts, the
    ruling's confidence and the amount it pays the driver, the free wait's two
    clocks -- how long from the wait's start to the cancellation, and the free
    wait the policy allows -- and the run's wall clock.
    """
    development_set = development_sets.named(V8_SET)
    run_dir = version_eight_run_dir()
    document = json.loads(
        (run_dir / "case-{0:05d}.json".format(V8_CASE)).read_text(encoding="utf-8")
    )
    transcript = json.loads(
        (run_dir / document["transcript_file"]).read_text(encoding="utf-8")
    )
    brief = brief_module.build_brief_for_case(
        development_set.load_case(V8_CASE),
        policy_version=development_set.policy_version,
    )
    claims = v2._claims(transcript, "RIDER") + v2._claims(transcript, "DRIVER")
    vote = transcript.get("vote") or {}
    votes = int(vote.get("votes") or 0)
    agreement = vote.get("agreement")
    agreeing = (
        int((Decimal(str(agreement)) * votes).quantize(Decimal(1)))
        if agreement is not None
        else 0
    )
    ruling = _inner_ruling(document)
    return {
        "currency": str(
            _derived_value(brief, "FARE_BREAKDOWN", brief_module.MONEY_KEY, "currency")
        ),
        "evidence": len(v2._evidence(brief)),
        "rider_points": len(v2._claims(transcript, "RIDER")),
        "driver_points": len(v2._claims(transcript, "DRIVER")),
        "claims": len(claims),
        "kept": sum(
            1 for claim in claims if claim["status"] == referee_module.STATUS_KEPT
        ),
        "agreeing": agreeing,
        "votes": votes,
        "confidence": ruling.get("confidence"),
        "driver_amount": ruling.get("driver_compensation_sgd"),
        "wait": _derived_value(
            brief,
            "TRIP_RECORD",
            brief_module.V7_KEY,
            "free_wait",
            "seconds_from_start_to_cancel",
        ),
        "free_wait": _derived_value(
            brief,
            "TRIP_RECORD",
            brief_module.V7_KEY,
            "free_wait",
            "free_wait_sec",
        ),
        "wall": document.get("wall_seconds"),
    }


def _derived_block(
    brief: Mapping[str, Any], evidence_type: str, block: str
) -> Mapping[str, Any]:
    """One derived block, off the artifact of ``evidence_type`` that carries it."""
    for artifact in brief["case"]["evidence"]:
        if artifact.get("evidence_type") != evidence_type:
            continue
        payload = artifact.get("payload") or {}
        found = (payload.get("derived") or {}).get(block)
        return found if isinstance(found, Mapping) else {}
    return {}


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

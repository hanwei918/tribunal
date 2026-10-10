"""The queue, the SLA and the routing of ``ops/queue.py``.

The queue is a reader: it takes the disputes a run holds and says which lane
each belongs in, in what order they are worked and how long each has. This
module holds it to the rules the part states, and to the measurements the corpus
run actually produces.

Six things are asserted:

* **The lanes.** An in-scope case the pipeline ruled is ``AUTO``, an escalated
  one is ``HUMAN_REVIEW``, an out-of-scope category is ``HUMAN_REVIEW`` and a
  safety category is fast-tracked. The in-scope categories are the loader's own
  map, which is checked by asserting the module does not name either of them.
* **The kill switch.** ``auto_rulings_enabled`` false moves every dispute the
  pipeline would have ruled on into human review with the reason
  ``AUTO_PAUSED``, and leaves an escalated case, an out-of-scope case and the
  safety lane exactly where they were.
* **The order.** Four tiers, then the earliest due time, then the larger
  contested amount, then the case number.
* **The SLA.** The due time is ``filed_at`` plus the lane's target, the status is
  the time left or ``BREACHED`` at a fixed ``--now``, and without ``--now`` the
  status is a dash and **no clock is read at all** -- asserted by making the
  module's ``datetime`` refuse to answer.
* **The ``POL-GEN-05`` hold.** A ruling whose monetary effect is above the
  execution threshold is held for release: the lane is ``HUMAN_REVIEW`` with the
  reason ``GEN05_RELEASE``, and the case still counts as one the pipeline decided
  in the timing figures. Versions 1 and 2 carry no ``POL-GEN-05``, so there is no
  threshold and no hold.
* **The 48-hour clock.** Every human-lane case carries ``POL-GEN-06(2)``'s
  first-review deadline, ``filed_at`` plus ``end_to_end_hours``; past it the
  status is the clause's own consequence. The corpus acceptance is case 213 at a
  fixed ``--now``.
* **The measured SLA.** Counted off ``wall_seconds`` and reported as a count of
  cases, on the corpus run and on a small fixture run.
* **The config.** Every target is required, and the shipped file says in its own
  note that the targets are the team's and not Ryde's.

The rules that bind every module of the layer -- the import graph, the answer
keys, the write guard and determinism -- are asserted once, over every ``ops``
command, in ``tests/test_ops_layer.py``.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import queue  # noqa: E402
from tribunal import loader  # noqa: E402

CORPUS_RUN = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"

# The version-6 corpus run, where ``POL-GEN-05``'s 8.00 execution threshold is in
# force, and the cases the sheet's acceptance names as held above it.
CORPUS_V6_RUN = PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash"
CORPUS_V6_HELD = (101, 105, 106, 114)

# The corpus queue, measured on the committed run: five escalations, and the two
# of them whose part-1 signals trip. Nothing here is computed from the module
# under test.
CORPUS_CASES = 29
CORPUS_ESCALATED = (110, 112, 207, 210, 213)
CORPUS_TIER_TWO = (207, 213)
CORPUS_AUTO = 24
CORPUS_AUTO_MET = 14

# The targets the shipped config states, as the module reads them.
SHIPPED_TARGETS = {
    "auto_ruling_minutes": Decimal(5),
    "human_review_hours": Decimal(24),
    "safety_hours": Decimal(2),
    "end_to_end_hours": Decimal(48),
}


def dispute(
    case_no: int,
    category: str = "NO_SHOW_CHARGE",
    filed_at: str = "2026-07-01T10:00:00+08:00",
    amount: Optional[str] = "4.0",
    ruling: Optional[str] = "NO_ACTION",
    wall_seconds: Optional[str] = None,
    risk_tripped: bool = False,
) -> queue.Dispute:
    """One dispute fixture, with only the fields the queue reads."""
    return queue.Dispute(
        case_no=case_no,
        category=category,
        filed_at=filed_at,
        amount_contested_sgd=None if amount is None else Decimal(amount),
        ruling=ruling,
        wall_seconds=None if wall_seconds is None else Decimal(wall_seconds),
        risk_tripped=risk_tripped,
    )


def config(
    enabled: bool = True,
    auto_ruling_minutes: str = "5",
    human_review_hours: str = "24",
    safety_hours: str = "2",
    end_to_end_hours: str = "48",
    note: str = "fixture",
) -> queue.Config:
    return queue.Config(
        auto_rulings_enabled=enabled,
        sla=queue.Slas(
            auto_ruling_minutes=Decimal(auto_ruling_minutes),
            human_review_hours=Decimal(human_review_hours),
            safety_hours=Decimal(safety_hours),
            end_to_end_hours=Decimal(end_to_end_hours),
        ),
        note=note,
    )


def run_command(arguments: Sequence[str]) -> tuple:
    import contextlib
    import io

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = queue.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def rows(text: str) -> List[List[str]]:
    """The queue's table rows, split into cells, without the header."""
    body = [line for line in text.splitlines() if line and not line.startswith(("queue:", "auto rulings:", "end-to-end", "measured", "tier "))]
    return [line.split() for line in body]


def case_numbers(text: str) -> List[int]:
    """The case number of each row, in the order printed."""
    found = []
    for cells in rows(text):
        if len(cells) >= 2 and cells[0].isdigit() and cells[1].isdigit():
            found.append(int(cells[1]))
    return found


class NoClock(datetime):
    """A ``datetime`` that refuses to say what time it is.

    ``ops.queue`` imports the class by name, so patching that name is enough to
    catch a call to ``now``, ``utcnow`` or ``today`` anywhere in the module while
    leaving ``fromisoformat`` working.
    """

    @classmethod
    def now(cls, tz=None):  # pragma: no cover - only reached on a failure
        raise AssertionError("the queue read the wall clock")

    @classmethod
    def utcnow(cls):  # pragma: no cover - only reached on a failure
        raise AssertionError("the queue read the wall clock")

    @classmethod
    def today(cls):  # pragma: no cover - only reached on a failure
        raise AssertionError("the queue read the wall clock")


# --------------------------------------------------------------------------
# The lanes
# --------------------------------------------------------------------------
class TheLanesTests(unittest.TestCase):
    """Which lane a dispute is in, and why."""

    def setUp(self):
        self.config = config()

    def test_an_in_scope_case_the_pipeline_ruled_is_auto(self):
        lane, reasons = queue.lane_for(dispute(101, "ROUTE_DEVIATION"), self.config)
        self.assertEqual(queue.LANE_AUTO, lane)
        self.assertEqual((queue.REASON_RULED,), reasons)

    def test_an_escalated_case_goes_to_human_review(self):
        lane, reasons = queue.lane_for(dispute(207, ruling="ESCALATE"), self.config)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_ESCALATED,), reasons)

    def test_an_out_of_scope_category_goes_to_human_review(self):
        lane, reasons = queue.lane_for(dispute(901, "PROPERTY_DAMAGE"), self.config)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_OUT_OF_SCOPE,), reasons)

    def test_a_safety_category_is_fast_tracked(self):
        lane, reasons = queue.lane_for(dispute(902, "SAFETY_INCIDENT"), self.config)
        self.assertEqual(queue.LANE_SAFETY, lane)
        self.assertEqual((queue.REASON_SAFETY,), reasons)

    def test_the_in_scope_categories_are_the_loader_s_own(self):
        """The module must not type them, so it must not name them."""
        source = (PROJECT_ROOT / "ops" / "queue.py").read_text(encoding="utf-8")
        for category in loader.CATEGORY_POLICY_FILES:
            with self.subTest(category=category):
                self.assertNotIn(
                    category,
                    source,
                    "ops/queue.py names {0}, so the in-scope list is typed rather "
                    "than read off the loader".format(category),
                )
        for category in loader.CATEGORY_POLICY_FILES:
            with self.subTest(category=category):
                lane, _reasons = queue.lane_for(dispute(101, category), self.config)
                self.assertNotEqual(queue.LANE_HUMAN, lane)

    def test_the_safety_list_is_disjoint_from_the_loader_s_map(self):
        """A safety category the pipeline adjudicates is not a safety category.

        The lane is for a category the pipeline does not adjudicate; if one were
        ever added to the loader's map, fast-tracking it would skip the pipeline
        silently, so the two lists are asserted apart.
        """
        self.assertTrue(queue.SAFETY_CATEGORIES)
        self.assertEqual(
            set(), set(queue.SAFETY_CATEGORIES) & set(loader.CATEGORY_POLICY_FILES)
        )
        for category in queue.SAFETY_CATEGORIES:
            with self.subTest(category=category):
                self.assertNotIn(category, loader.CATEGORY_POLICY_FILES)

    def test_every_lane_is_reachable_and_named_once(self):
        self.assertEqual(3, len(set(queue.LANES)))
        self.assertEqual(4, len({queue.TIER_SAFETY, queue.TIER_HUMAN_RISK, queue.TIER_HUMAN, queue.TIER_AUTO}))


# --------------------------------------------------------------------------
# The kill switch
# --------------------------------------------------------------------------
class TheKillSwitchTests(unittest.TestCase):
    """``auto_rulings_enabled`` false pauses the router and nothing else."""

    def setUp(self):
        self.paused = config(enabled=False)

    def test_the_kill_switch_moves_an_auto_case_to_human_review(self):
        lane, reasons = queue.lane_for(dispute(101, "ROUTE_DEVIATION"), self.paused)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_AUTO_PAUSED,), reasons)

    def test_the_kill_switch_leaves_an_escalated_case_with_its_own_reason(self):
        lane, reasons = queue.lane_for(dispute(207, ruling="ESCALATE"), self.paused)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_ESCALATED,), reasons)

    def test_the_kill_switch_leaves_an_out_of_scope_case_with_its_own_reason(self):
        lane, reasons = queue.lane_for(dispute(901, "PROPERTY_DAMAGE"), self.paused)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_OUT_OF_SCOPE,), reasons)

    def test_the_kill_switch_leaves_the_safety_lane_alone(self):
        lane, reasons = queue.lane_for(dispute(902, "SAFETY_INCIDENT"), self.paused)
        self.assertEqual(queue.LANE_SAFETY, lane)
        self.assertEqual((queue.REASON_SAFETY,), reasons)

    def test_the_switch_changes_the_tier_of_a_case_it_pauses(self):
        entries = queue.build_queue([dispute(101, "ROUTE_DEVIATION")], self.paused)
        self.assertEqual(queue.TIER_HUMAN, entries[0].tier)
        entries = queue.build_queue([dispute(101, "ROUTE_DEVIATION")], config())
        self.assertEqual(queue.TIER_AUTO, entries[0].tier)

    def test_the_command_reports_the_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "note": "paused for the fixture",
                        "auto_rulings_enabled": False,
                        "sla": {
                            "auto_ruling_minutes": 5,
                            "human_review_hours": 24,
                            "safety_hours": 2,
                            "end_to_end_hours": 48,
                        },
                    }
                ),
                encoding="utf-8",
            )
            code, out, err = run_command(
                ["--run-dir", str(CORPUS_RUN), "--config", str(path)]
            )
            self.assertEqual(0, code, err)
            self.assertIn("auto rulings: paused", out)
            self.assertIn("AUTO_PAUSED", out)
            lanes = {cells[3] for cells in rows(out) if len(cells) > 3}
            self.assertNotIn(queue.LANE_AUTO, lanes)
            self.assertIn("0 of 0 AUTO case(s)", out)

    def test_nothing_in_tribunal_reads_the_config(self):
        """The kill switch is the router's, and it changes no pipeline code."""
        source = (PROJECT_ROOT / "ops" / "queue.py").read_text(encoding="utf-8")
        self.assertIn("auto_rulings_enabled", source)
        for path in sorted((PROJECT_ROOT / "tribunal").glob("*.py")):
            with self.subTest(module=path.name):
                self.assertNotIn("auto_rulings_enabled", path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# The order
# --------------------------------------------------------------------------
class TheOrderingTests(unittest.TestCase):
    """Tier, then the earliest due time, then the larger amount, then the case."""

    def setUp(self):
        self.config = config()

    def order(self, disputes):
        return [entry.case_no for entry in queue.build_queue(disputes, self.config)]

    def test_the_four_tiers_come_in_their_order(self):
        disputes = [
            dispute(10, ruling="NO_ACTION"),
            dispute(20, ruling="ESCALATE"),
            dispute(21, "PROPERTY_DAMAGE"),
            dispute(22, ruling="ESCALATE", risk_tripped=True),
            dispute(30, "SAFETY_INCIDENT"),
        ]
        self.assertEqual([30, 22, 20, 21, 10], self.order(disputes))
        tiers = [entry.tier for entry in queue.build_queue(disputes, self.config)]
        self.assertEqual(
            [
                queue.TIER_SAFETY,
                queue.TIER_HUMAN_RISK,
                queue.TIER_HUMAN,
                queue.TIER_HUMAN,
                queue.TIER_AUTO,
            ],
            tiers,
        )

    def test_a_tripped_signal_orders_a_human_review_above_an_untripped_one(self):
        found = self.order(
            [
                dispute(20, ruling="ESCALATE", filed_at="2026-07-01T10:00:00+08:00"),
                dispute(21, ruling="ESCALATE", filed_at="2026-07-09T10:00:00+08:00", risk_tripped=True),
            ]
        )
        self.assertEqual([21, 20], found)

    def test_a_tripped_signal_does_not_reroute_an_auto_case(self):
        entries = queue.build_queue(
            [dispute(10, ruling="NO_ACTION", risk_tripped=True)], self.config
        )
        self.assertEqual(queue.LANE_AUTO, entries[0].lane)
        self.assertEqual(queue.TIER_AUTO, entries[0].tier)
        self.assertIn(queue.REASON_RISK_TRIPPED, entries[0].reasons)

    def test_the_earliest_due_time_is_first_within_a_tier(self):
        found = self.order(
            [
                dispute(11, filed_at="2026-07-05T10:00:00+08:00"),
                dispute(12, filed_at="2026-07-01T10:00:00+08:00"),
                dispute(13, filed_at="2026-07-03T10:00:00+08:00"),
            ]
        )
        self.assertEqual([12, 13, 11], found)

    def test_the_larger_amount_breaks_a_due_time_tie(self):
        found = self.order(
            [
                dispute(11, amount="4.0"),
                dispute(12, amount="14.0"),
                dispute(13, amount="9.0"),
            ]
        )
        self.assertEqual([12, 13, 11], found)

    def test_the_case_number_breaks_a_tie(self):
        found = self.order([dispute(13), dispute(11), dispute(12)])
        self.assertEqual([11, 12, 13], found)

    def test_a_case_with_no_amount_sorts_as_zero(self):
        found = self.order([dispute(11, amount=None), dispute(12, amount="1.0")])
        self.assertEqual([12, 11], found)

    def test_the_safety_lane_is_ordered_by_due_time_across_categories(self):
        found = self.order(
            [
                dispute(12, "SAFETY_INCIDENT", filed_at="2026-07-05T10:00:00+08:00"),
                dispute(11, "SAFETY_INCIDENT", filed_at="2026-07-01T10:00:00+08:00"),
            ]
        )
        self.assertEqual([11, 12], found)


# --------------------------------------------------------------------------
# The SLA
# --------------------------------------------------------------------------
class TheSlaTests(unittest.TestCase):
    """The due time, the status, and the clock that is not read."""

    def setUp(self):
        self.config = config()

    def due(self, one, cfg=None):
        return queue.build_queue([one], cfg or self.config)[0].due_at

    def test_the_due_time_is_filed_at_plus_the_lane_s_target(self):
        filed = "2026-07-01T10:00:00+08:00"
        self.assertEqual(
            datetime.fromisoformat("2026-07-01T10:05:00+08:00"),
            self.due(dispute(11, "ROUTE_DEVIATION", filed_at=filed)),
        )
        self.assertEqual(
            datetime.fromisoformat("2026-07-02T10:00:00+08:00"),
            self.due(dispute(11, ruling="ESCALATE", filed_at=filed)),
        )
        self.assertEqual(
            datetime.fromisoformat("2026-07-01T12:00:00+08:00"),
            self.due(dispute(11, "SAFETY_INCIDENT", filed_at=filed)),
        )
        self.assertEqual(
            datetime.fromisoformat("2026-07-02T10:00:00+08:00"),
            self.due(dispute(11, "PROPERTY_DAMAGE", filed_at=filed)),
        )

    def test_the_targets_come_from_the_config_and_not_from_here(self):
        other = config(auto_ruling_minutes="30", human_review_hours="1", safety_hours="3")
        filed = "2026-07-01T10:00:00+08:00"
        self.assertEqual(
            datetime.fromisoformat("2026-07-01T10:30:00+08:00"),
            self.due(dispute(11, "ROUTE_DEVIATION", filed_at=filed), other),
        )
        self.assertEqual(
            datetime.fromisoformat("2026-07-01T11:00:00+08:00"),
            self.due(dispute(11, ruling="ESCALATE", filed_at=filed), other),
        )
        self.assertEqual(
            datetime.fromisoformat("2026-07-01T13:00:00+08:00"),
            self.due(dispute(11, "SAFETY_INCIDENT", filed_at=filed), other),
        )

    def test_the_status_is_the_time_remaining_at_a_fixed_now(self):
        entry = queue.build_queue(
            [dispute(11, "ROUTE_DEVIATION", filed_at="2026-07-01T10:00:00+08:00")],
            self.config,
            datetime.fromisoformat("2026-07-01T10:02:00+08:00"),
        )[0]
        self.assertEqual("3m remaining", entry.status)

    def test_a_whole_day_of_remaining_time_reads_as_a_day(self):
        entry = queue.build_queue(
            [dispute(11, ruling="ESCALATE", filed_at="2026-07-01T10:00:00+08:00")],
            self.config,
            datetime.fromisoformat("2026-07-01T10:00:00+08:00"),
        )[0]
        self.assertEqual("1d remaining", entry.status)

    def test_the_status_is_breached_past_the_due_time(self):
        entry = queue.build_queue(
            [dispute(11, "ROUTE_DEVIATION", filed_at="2026-07-01T10:00:00+08:00")],
            self.config,
            datetime.fromisoformat("2026-07-01T10:06:00+08:00"),
        )[0]
        self.assertEqual("BREACHED", entry.status)

    def test_the_boundary_is_not_a_breach(self):
        entry = queue.build_queue(
            [dispute(11, "ROUTE_DEVIATION", filed_at="2026-07-01T10:00:00+08:00")],
            self.config,
            datetime.fromisoformat("2026-07-01T10:05:00+08:00"),
        )[0]
        self.assertEqual("0m remaining", entry.status)

    def test_without_now_the_status_is_a_dash(self):
        entry = queue.build_queue([dispute(11)], self.config)[0]
        self.assertEqual("-", entry.status)

    def test_without_now_no_clock_is_read(self):
        """The command is run with the module's own ``datetime`` refusing."""
        with mock.patch.object(queue, "datetime", NoClock):
            code, out, err = run_command(["--run-dir", str(CORPUS_RUN)])
        self.assertEqual(0, code, err)
        self.assertIn("-", out)

    def test_with_now_the_clock_is_still_not_read(self):
        """``--now`` names an instant; the machine's clock is not consulted."""
        with mock.patch.object(queue, "datetime", NoClock):
            code, out, err = run_command(
                ["--run-dir", str(CORPUS_RUN), "--now", "2026-07-30T00:00:00+08:00"]
            )
        self.assertEqual(0, code, err)
        self.assertIn("remaining", out)

    def test_a_now_without_an_offset_is_refused(self):
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_RUN), "--now", "2026-07-30T00:00:00"]
        )
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertIn("UTC offset", err)

    def test_a_now_that_is_not_an_instant_is_refused(self):
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_RUN), "--now", "yesterday"]
        )
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)

    def test_the_end_to_end_target_is_printed_and_is_not_a_due_time(self):
        code, out, err = run_command(["--run-dir", str(CORPUS_RUN)])
        self.assertEqual(0, code, err)
        self.assertIn("end-to-end target: 2d from filing to resolution", out)
        for entry in queue.build_queue(
            queue.disputes_from_run(CORPUS_RUN), self.config
        ):
            with self.subTest(case=entry.case_no):
                self.assertLess(
                    entry.due_at,
                    datetime.fromisoformat(entry.filed_at) + self.config.sla.end_to_end(),
                )


# --------------------------------------------------------------------------
# POL-GEN-05: the amount held for release
# --------------------------------------------------------------------------
def held_dispute(
    case_no: int = 101,
    ruling: str = "PARTIAL_REFUND",
    amount_sgd: Optional[str] = "8.05",
    driver_compensation_sgd: Optional[str] = None,
    threshold: Optional[str] = "8.0",
) -> queue.Dispute:
    """One dispute carrying the money ``POL-GEN-05`` is read against."""
    return queue.Dispute(
        case_no=case_no,
        category="ROUTE_DEVIATION",
        filed_at="2026-07-01T10:00:00+08:00",
        amount_contested_sgd=Decimal("10.0"),
        ruling=ruling,
        wall_seconds=Decimal("10"),
        risk_tripped=False,
        amount_sgd=None if amount_sgd is None else Decimal(amount_sgd),
        driver_compensation_sgd=(
            None if driver_compensation_sgd is None else Decimal(driver_compensation_sgd)
        ),
        execution_threshold_sgd=None if threshold is None else Decimal(threshold),
    )


class TheGen05HoldTests(unittest.TestCase):
    """A ruling above the execution threshold is issued but not executed."""

    def setUp(self):
        self.config = config()

    def test_a_ruling_above_the_threshold_is_held_for_release(self):
        dispute_ = held_dispute(amount_sgd="8.05", threshold="8.0")
        self.assertTrue(queue.money_is_held(dispute_))
        lane, reasons = queue.lane_for(dispute_, self.config)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_GEN05_RELEASE,), reasons)

    def test_a_ruling_at_the_threshold_is_not_held(self):
        """The clause holds a ruling that *exceeds* the threshold, and no other."""
        dispute_ = held_dispute(amount_sgd="8.00", threshold="8.0")
        self.assertFalse(queue.money_is_held(dispute_))
        lane, reasons = queue.lane_for(dispute_, self.config)
        self.assertEqual(queue.LANE_AUTO, lane)
        self.assertEqual((queue.REASON_RULED,), reasons)

    def test_no_threshold_means_no_hold(self):
        """Versions 1 and 2 carry no POL-GEN-05, so nothing is held."""
        dispute_ = held_dispute(amount_sgd="80.0", threshold=None)
        self.assertFalse(queue.money_is_held(dispute_))
        self.assertEqual(queue.LANE_AUTO, queue.lane_for(dispute_, self.config)[0])

    def test_a_driver_compensation_ruling_counts_its_two_fields_once(self):
        """POL-GEN-03's one exception: amount_sgd repeats the driver figure."""
        dispute_ = held_dispute(
            ruling="DRIVER_COMPENSATION",
            amount_sgd="8.05",
            driver_compensation_sgd="8.05",
            threshold="8.0",
        )
        self.assertTrue(queue.money_is_held(dispute_))
        self.assertEqual(queue.LANE_HUMAN, queue.lane_for(dispute_, self.config)[0])

    def test_an_escalated_case_keeps_the_escalation_reason(self):
        dispute_ = held_dispute(ruling="ESCALATE", amount_sgd=None, threshold="8.0")
        lane, reasons = queue.lane_for(dispute_, self.config)
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_ESCALATED,), reasons)

    def test_the_kill_switch_reason_wins_while_the_switch_is_off(self):
        dispute_ = held_dispute(amount_sgd="8.05", threshold="8.0")
        lane, reasons = queue.lane_for(dispute_, config(enabled=False))
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertEqual((queue.REASON_AUTO_PAUSED,), reasons)

    def test_a_held_case_still_counts_as_decided_automatically(self):
        """A hold moves the lane, and it does not move the timing figures."""
        disputes = [held_dispute(case_no=101), held_dispute(case_no=102, amount_sgd="4.0")]
        entries = queue.build_queue(disputes, self.config)
        self.assertEqual((2, 2), queue.measured_auto_sla(entries, self.config))
        for entry in entries:
            with self.subTest(case=entry.case_no):
                self.assertTrue(queue.counts_as_decided_automatically(entry))

    def test_the_hold_is_read_off_the_run_s_policy_version(self):
        """The threshold is the run's own version's, read from the policy text."""
        self.assertEqual(Decimal("8.0"), queue._execution_threshold("ROUTE_DEVIATION", 6))
        self.assertIsNone(queue._execution_threshold("ROUTE_DEVIATION", 1))
        self.assertIsNone(queue._execution_threshold("ROUTE_DEVIATION", 2))
        self.assertIsNone(queue._execution_threshold("PROPERTY_DAMAGE", 6))


class TheVersion6CorpusHoldTests(unittest.TestCase):
    """The version-6 corpus run's own held cases, as the sheet's acceptance."""

    @classmethod
    def setUpClass(cls):
        cls.entries = queue.build_queue(
            queue.disputes_from_run(CORPUS_V6_RUN), queue.load_config()
        )

    def test_the_held_cases_are_the_four_the_sheet_names(self):
        held = sorted(
            entry.case_no
            for entry in self.entries
            if queue.REASON_GEN05_RELEASE in entry.reasons
        )
        self.assertEqual(list(CORPUS_V6_HELD), held)

    def test_every_held_case_is_in_the_human_lane(self):
        for entry in self.entries:
            if queue.REASON_GEN05_RELEASE in entry.reasons:
                with self.subTest(case=entry.case_no):
                    self.assertEqual(queue.LANE_HUMAN, entry.lane)

    def test_the_held_cases_are_counted_as_automatic_in_the_timing_figures(self):
        met, of = queue.measured_auto_sla(self.entries, queue.load_config())
        auto = [entry for entry in self.entries if entry.lane == queue.LANE_AUTO]
        held = [
            entry
            for entry in self.entries
            if queue.REASON_GEN05_RELEASE in entry.reasons
        ]
        self.assertEqual(len(auto) + len(held), of)
        self.assertLessEqual(met, of)


# --------------------------------------------------------------------------
# POL-GEN-06(2): the first-review clock
# --------------------------------------------------------------------------
# The instant the sheet's acceptance names, and the case it names.
ACCEPTANCE_NOW = "2026-08-12T10:00:00+08:00"
ACCEPTANCE_CASE = 213


class TheFirstReviewClockTests(unittest.TestCase):
    """Every human-lane case carries POL-GEN-06(2)'s 48-hour deadline."""

    def setUp(self):
        self.config = config()

    def entry(self, one, now=None):
        return queue.build_queue([one], self.config, now)[0]

    def test_the_deadline_is_filing_time_plus_end_to_end_hours(self):
        entry = self.entry(
            dispute(11, ruling="ESCALATE", filed_at="2026-08-11T18:40:00+08:00")
        )
        self.assertEqual(
            datetime.fromisoformat("2026-08-13T18:40:00+08:00"), entry.review_due_at
        )

    def test_an_auto_case_carries_no_first_review_deadline(self):
        entry = self.entry(dispute(11, "ROUTE_DEVIATION"))
        self.assertIsNone(entry.review_due_at)
        self.assertEqual("-", entry.review_status)

    def test_without_now_the_review_status_is_a_dash_and_no_clock_is_read(self):
        with mock.patch.object(queue, "datetime", NoClock):
            entry = self.entry(dispute(11, ruling="ESCALATE"))
        self.assertEqual("-", entry.review_status)

    def test_the_status_is_the_time_remaining_at_a_fixed_now(self):
        entry = self.entry(
            dispute(11, ruling="ESCALATE", filed_at="2026-08-11T18:40:00+08:00"),
            datetime.fromisoformat(ACCEPTANCE_NOW),
        )
        self.assertEqual("1d 8h 40m remaining", entry.review_status)

    def test_past_the_deadline_the_clause_s_consequence_is_shown(self):
        entry = self.entry(
            dispute(11, ruling="ESCALATE", filed_at="2026-08-11T18:40:00+08:00"),
            datetime.fromisoformat("2026-08-14T10:00:00+08:00"),
        )
        self.assertEqual(queue.BREACHED_REVIEW, entry.review_status)

    def test_the_breach_sentence_is_pol_gen_06_s_consequence(self):
        self.assertIn("escalated to the duty supervisor", queue.BREACHED_REVIEW)
        self.assertIn("the disputed amount stays frozen", queue.BREACHED_REVIEW)

    def test_case_213_shows_the_remaining_time_the_sheet_names(self):
        """The acceptance: 213 at ``--now 2026-08-12T10:00:00+08:00``."""
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_V6_RUN), "--now", ACCEPTANCE_NOW]
        )
        self.assertEqual(0, code, err)
        rows_for_213 = [
            line
            for line in out.splitlines()
            if len(line.split()) >= 2 and line.split()[1] == str(ACCEPTANCE_CASE)
        ]
        self.assertEqual(1, len(rows_for_213), out)
        self.assertIn("1d 8h 40m remaining", rows_for_213[0])

    def test_the_command_reports_the_breach_past_the_deadline(self):
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_V6_RUN), "--now", "2027-01-01T00:00:00+08:00"]
        )
        self.assertEqual(0, code, err)
        self.assertIn(queue.BREACHED_REVIEW, out)

    def test_the_windows_option_reads_the_part_26_store(self):
        """``--windows`` reads part 26's store and reports each human case's window."""
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_V6_RUN), "--windows", "/tmp/evidence-windows"]
        )
        self.assertEqual(0, code, err)
        self.assertIn("evidence windows: /tmp/evidence-windows", out)
        self.assertIn("no evidence window", out)


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------
class TheCorpusQueueTests(unittest.TestCase):
    """The queue the committed corpus run produces."""

    @classmethod
    def setUpClass(cls):
        cls.config = queue.load_config()
        cls.disputes = queue.disputes_from_run(CORPUS_RUN)
        cls.entries = queue.build_queue(cls.disputes, cls.config)

    def test_the_run_holds_every_case(self):
        self.assertEqual(CORPUS_CASES, len(self.entries))

    def test_five_cases_go_to_human_review_and_the_rest_are_auto(self):
        human = [entry for entry in self.entries if entry.lane == queue.LANE_HUMAN]
        auto = [entry for entry in self.entries if entry.lane == queue.LANE_AUTO]
        self.assertEqual(list(CORPUS_ESCALATED), sorted(entry.case_no for entry in human))
        self.assertEqual(CORPUS_AUTO, len(auto))
        self.assertEqual([], [entry for entry in self.entries if entry.lane == queue.LANE_SAFETY])

    def test_a_tripped_pair_test_still_routes_the_case_to_the_second_tier(self):
        """The queue reads ``tripped``, and the pair test's side does not move it.

        ``POL-NS-09(c)`` is reported against ``PAIR`` rather than against one
        party; the queue is unaffected by that, which is the point -- it routes
        on whether a signal tripped and never on which side a signal names.
        """
        entries = queue.build_queue(
            [
                dispute(11, ruling="ESCALATE", risk_tripped=True),
                dispute(12, ruling="ESCALATE", risk_tripped=False),
            ],
            self.config,
        )
        self.assertEqual(queue.TIER_HUMAN_RISK, entries[0].tier)
        self.assertEqual(11, entries[0].case_no)
        self.assertIn(queue.REASON_RISK_TRIPPED, entries[0].reasons)
        self.assertEqual(queue.TIER_HUMAN, entries[1].tier)
        self.assertNotIn(queue.REASON_RISK_TRIPPED, entries[1].reasons)

    def test_the_two_tier_two_cases_are_the_two_that_trip_a_signal(self):
        self.assertEqual(
            list(CORPUS_TIER_TWO),
            sorted(entry.case_no for entry in self.entries if entry.tier == queue.TIER_HUMAN_RISK),
        )

    def test_the_tier_two_cases_carry_the_risk_reason(self):
        for entry in self.entries:
            if entry.tier == queue.TIER_HUMAN_RISK:
                with self.subTest(case=entry.case_no):
                    self.assertIn(queue.REASON_RISK_TRIPPED, entry.reasons)

    def test_the_queue_is_in_tier_order(self):
        tiers = [entry.tier for entry in self.entries]
        self.assertEqual(sorted(tiers), tiers)

    def test_the_measured_auto_sla_is_the_one_the_run_produces(self):
        self.assertEqual(
            (CORPUS_AUTO_MET, CORPUS_AUTO), queue.measured_auto_sla(self.entries, self.config)
        )

    def test_the_command_prints_one_row_per_case_and_the_measured_line(self):
        code, out, err = run_command(["--run-dir", str(CORPUS_RUN)])
        self.assertEqual(0, code, err)
        self.assertEqual(CORPUS_CASES, len(case_numbers(out)))
        self.assertEqual(
            list(CORPUS_TIER_TWO) + [110, 210, 112],
            case_numbers(out)[:5],
        )
        self.assertIn(
            "measured auto-ruling SLA: {0} of {1} AUTO case(s)".format(
                CORPUS_AUTO_MET, CORPUS_AUTO
            ),
            out,
        )

    def test_the_measured_line_is_a_count_and_not_a_rate(self):
        code, out, err = run_command(["--run-dir", str(CORPUS_RUN)])
        self.assertEqual(0, code, err)
        line = [l for l in out.splitlines() if l.startswith("measured")][0]
        self.assertNotIn("%", line)
        self.assertNotIn("percent", line)

    def test_two_runs_are_byte_identical(self):
        self.assertEqual(
            run_command(["--run-dir", str(CORPUS_RUN)]),
            run_command(["--run-dir", str(CORPUS_RUN)]),
        )

    def test_a_run_directory_that_is_not_there_is_refused(self):
        code, out, err = run_command(["--run-dir", "/tmp/no-such-run-directory"])
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)


# --------------------------------------------------------------------------
# The measured SLA on a fixture run
# --------------------------------------------------------------------------
class TheMeasuredSlaOnAFixtureRunTests(unittest.TestCase):
    """A run of two cases: one inside the auto target, one outside it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "runs" / "a-model"
        self.run_dir.mkdir(parents=True)
        self._write(101, "PARTIAL_REFUND", "100.0")
        self._write(102, "NO_ACTION", "900.0")

    def _write(self, case_no: int, ruling: str, wall_seconds: str) -> None:
        document = {
            "schema_version": 2,
            "case_no": case_no,
            "ruling": {"ruling": {"ruling": ruling}},
            "wall_seconds": Decimal(wall_seconds),
        }
        path = self.run_dir / "case-{0:05d}.json".format(case_no)
        path.write_text(
            json.dumps(document, default=str) + "\n", encoding="utf-8"
        )

    def test_the_fixture_run_is_read_as_the_corpus(self):
        self.assertEqual(
            [101, 102],
            sorted(dispute.case_no for dispute in queue.disputes_from_run(self.run_dir)),
        )

    def test_one_of_two_auto_cases_met_the_target(self):
        disputes = queue.disputes_from_run(self.run_dir)
        entries = queue.build_queue(disputes, queue.load_config())
        self.assertEqual((1, 2), queue.measured_auto_sla(entries, queue.load_config()))

    def test_the_command_reports_one_of_two(self):
        code, out, err = run_command(["--run-dir", str(self.run_dir)])
        self.assertEqual(0, code, err)
        self.assertIn("measured auto-ruling SLA: 1 of 2 AUTO case(s)", out)

    def test_a_case_with_no_recorded_seconds_is_counted_and_did_not_meet(self):
        path = self.run_dir / "case-00102.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document.pop("wall_seconds")
        path.write_text(json.dumps(document) + "\n", encoding="utf-8")
        entries = queue.build_queue(
            queue.disputes_from_run(self.run_dir), queue.load_config()
        )
        self.assertEqual((1, 2), queue.measured_auto_sla(entries, queue.load_config()))

    def test_the_seconds_are_compared_at_the_target_and_not_a_second_over(self):
        self._write(103, "NO_ACTION", "300.0")
        entries = queue.build_queue(
            queue.disputes_from_run(self.run_dir), queue.load_config()
        )
        self.assertEqual((2, 3), queue.measured_auto_sla(entries, queue.load_config()))

    def test_a_case_file_with_no_ruling_is_refused(self):
        path = self.run_dir / "case-00104.json"
        path.write_text(
            json.dumps({"schema_version": 2, "case_no": 104}) + "\n", encoding="utf-8"
        )
        with self.assertRaises(queue.QueueError):
            queue.disputes_from_run(self.run_dir)


# --------------------------------------------------------------------------
# The config
# --------------------------------------------------------------------------
class TheConfigTests(unittest.TestCase):
    """The shipped config, and the refusals a config that moved earns."""

    def test_the_shipped_config_states_every_target(self):
        loaded = queue.load_config()
        self.assertTrue(loaded.auto_rulings_enabled)
        self.assertEqual(SHIPPED_TARGETS, dict(loaded.sla._asdict()))

    def test_the_note_says_the_targets_are_the_team_s_and_names_the_baseline(self):
        note = queue.load_config().note
        self.assertIsInstance(note, str)
        self.assertIn("not Ryde", note)
        self.assertIn("24\u201372 hours per dispute", note)

    def test_the_config_is_the_file_the_command_reads_by_default(self):
        self.assertEqual(PROJECT_ROOT / "ops" / "config.json", queue.CONFIG_PATH)
        self.assertTrue(queue.CONFIG_PATH.is_file())

    def _write(self, document: Any) -> Path:
        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        path = Path(directory) / "config.json"
        path.write_text(
            document if isinstance(document, str) else json.dumps(document),
            encoding="utf-8",
        )
        return path

    def _good(self) -> Dict[str, Any]:
        return {
            "note": "fixture",
            "auto_rulings_enabled": True,
            "sla": {
                "auto_ruling_minutes": 5,
                "human_review_hours": 24,
                "safety_hours": 2,
                "end_to_end_hours": 48,
            },
        }

    def test_a_config_that_states_everything_is_taken(self):
        loaded = queue.load_config(self._write(self._good()))
        self.assertEqual(SHIPPED_TARGETS, dict(loaded.sla._asdict()))

    def test_a_missing_target_is_refused(self):
        for key in queue.SLA_KEYS:
            with self.subTest(key=key):
                document = self._good()
                document["sla"].pop(key)
                with self.assertRaises(queue.QueueError) as caught:
                    queue.load_config(self._write(document))
                self.assertIn(key, str(caught.exception))

    def test_a_target_that_is_not_a_number_is_refused(self):
        document = self._good()
        document["sla"]["safety_hours"] = "soon"
        with self.assertRaises(queue.QueueError):
            queue.load_config(self._write(document))

    def test_a_target_of_zero_is_refused(self):
        document = self._good()
        document["sla"]["safety_hours"] = 0
        with self.assertRaises(queue.QueueError):
            queue.load_config(self._write(document))

    def test_a_config_without_the_switch_is_refused(self):
        document = self._good()
        document.pop("auto_rulings_enabled")
        with self.assertRaises(queue.QueueError) as caught:
            queue.load_config(self._write(document))
        self.assertIn("auto_rulings_enabled", str(caught.exception))

    def test_a_switch_that_is_not_a_boolean_is_refused(self):
        document = self._good()
        document["auto_rulings_enabled"] = "yes"
        with self.assertRaises(queue.QueueError):
            queue.load_config(self._write(document))

    def test_a_config_that_is_not_an_object_is_refused(self):
        with self.assertRaises(queue.QueueError):
            queue.load_config(self._write("[1, 2, 3]"))

    def test_a_config_that_is_not_json_is_refused(self):
        with self.assertRaises(queue.QueueError):
            queue.load_config(self._write("{not json"))

    def test_a_config_that_is_not_there_is_refused(self):
        with self.assertRaises(queue.QueueError):
            queue.load_config(Path("/tmp/no-such-config-at-all.json"))

    def test_the_command_takes_a_config_of_its_own(self):
        document = self._good()
        document["sla"]["human_review_hours"] = 1
        path = self._write(document)
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_RUN), "--config", str(path)]
        )
        self.assertEqual(0, code, err)
        self.assertIn("2026-07-29T08:20:40+08:00", out)

    def test_the_command_reports_a_bad_config_as_a_refusal(self):
        document = self._good()
        document["sla"].pop("safety_hours")
        path = self._write(document)
        code, out, err = run_command(
            ["--run-dir", str(CORPUS_RUN), "--config", str(path)]
        )
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertIn("safety_hours", err)
        self.assertEqual("", out)


if __name__ == "__main__":
    unittest.main()

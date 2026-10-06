"""Tests for ``eval/readiness.py``.

The report is a measurement, so what is checked here is the measurement: the
arithmetic, the tier, the refusals, and that each of the five dimensions says
PASS or FAIL rather than printing a number and leaving the reader to judge.

The two quality measurements -- the offline replay and the confidence-gate
rebuild -- take minutes and are asserted by their own modules; the tests here
drive the report over a small **fixture** run with those two injected, so what is
exercised is the report rather than the things it reports on. The command line's
own measurements are the real ones and are run in the closing checks.

No model call is made and no browser is launched.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import readiness  # noqa: E402
from tribunal import events, money  # noqa: E402

# A start instant inside the peak band, and one outside it. The owner's speed run
# began at 20:41 SGT on a Tuesday, which is outside both windows.
PEAK_INSTANT = "2026-10-05T02:00:00+00:00"  # 10:00 SGT, Monday
ORDINARY_INSTANT = "2026-10-06T12:41:14+00:00"  # 20:41 SGT, Tuesday
WEEKEND_INSTANT = "2026-10-03T02:00:00+00:00"  # 10:00 SGT, Saturday


class Done:
    """What an injected subprocess runner returns."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def always(returncode: int = 0):
    def run(command, **kwargs):
        return Done(returncode)

    return run


def a_case(case_no: int, *, wall: float, call: float, tokens: dict, replay=None):
    """One case file, shaped as the runner writes one."""
    return {
        "case_no": case_no,
        "ruling": {
            "ruling": {
                "ruling": "NO_ACTION",
                "amount_sgd": None,
                "driver_compensation_sgd": None,
                "referrals": [],
            },
            "discarded_claims": [],
        },
        "configuration": {
            "ablation": None,
            "judge_votes": 4,
            "policy_version": 2,
            "precedents": None,
            "verify_drafts": False,
        },
        "wall_seconds": wall,
        "call_seconds": call,
        "tokens": tokens,
        "replay": replay,
        "recorded_at": ORDINARY_INSTANT,
        "brief_sha256": "b" * 64,
    }


def build_run(root: Path, *, replay=None) -> Path:
    """A small run directory: two cases, a ``run.json`` and one call event."""
    run_dir = Path(root)
    run_dir.mkdir(parents=True, exist_ok=True)
    for case_no in (101, 102):
        (run_dir / "case-{0:05d}.json".format(case_no)).write_text(
            money.dumps_canonical(
                a_case(
                    case_no,
                    wall=100.0 * case_no,
                    call=250.0 * case_no,
                    tokens={
                        "prompt_tokens": 1000,
                        "completion_tokens": 500,
                        "cached_tokens": 400,
                        "total_tokens": 1500,
                    },
                    replay=replay,
                )
            ),
            encoding="utf-8",
        )
    (run_dir / "run.json").write_text(
        money.dumps_canonical(
            {
                "invocation_id": "20261006T124114.291705+0000-1",
                "git_commit": "b129824178b51b6d655bc0863f805cc75fe1f82b",
                "model": readiness.MODEL,
                "parallel_calls": True,
                "concurrency": 2,
                "configuration": {"policy_version": 2, "judge_votes": 4},
            }
        ),
        encoding="utf-8",
    )
    log = events.EventLog(run_dir / events.EVENTS_FILE, invocation_id="fixture")
    log.record(events.EVENT_CASE_START, case_no=101, position=1, total=2)
    log.record(
        events.EVENT_AGENT_CALL,
        case_no=101,
        role="RIDER_ADVOCATE",
        attempt=1,
        status=200,
        total_tokens=1500,
        seconds=12.5,
        parse_outcome="PARSED",
        **{
            "model": readiness.MODEL,
            "policy_version": 2,
            "brief_sha256": "b" * 64,
            "body_sha256": "c" * 64,
        }
    )
    log.record(
        events.EVENT_RULING,
        case_no=101,
        ruling={"ruling": "NO_ACTION"},
        findings=0,
    )
    return run_dir


def fake_quality():
    """The two quality measurements, answered without doing the work."""
    return (True, ["  stub"]), (True, ["  stub"])


class CostTests(unittest.TestCase):
    """The arithmetic, in ``Decimal``, at the prices the owner gave."""

    def test_the_cost_is_a_decimal_and_not_a_float(self):
        cost = readiness.cost_per_case(
            {"prompt_tokens": 1000, "cached_tokens": 400, "completion_tokens": 500},
            Decimal("0.15"),
            Decimal("0.6"),
        )
        self.assertIsInstance(cost, Decimal)
        self.assertEqual(Decimal("0.000450"), cost)

    def test_the_cached_tokens_are_priced_at_the_cached_price(self):
        """``cached_tokens`` are inside ``prompt_tokens``, not beside them."""
        tokens = {"prompt_tokens": 1000, "cached_tokens": 400, "completion_tokens": 0}
        plain = readiness.cost_per_case(tokens, Decimal("0.15"), Decimal("0.6"))
        cached = readiness.cost_per_case(
            tokens, Decimal("0.15"), Decimal("0.6"), Decimal("0.003")
        )
        self.assertEqual(Decimal("0.000150"), plain)
        # (1000 - 400) * 0.15 + 400 * 0.003 = 90 + 1.2 = 91.2, per million.
        self.assertEqual(Decimal("0.000091"), cached)

    def test_float_arithmetic_would_round_this_case_differently(self):
        """The reason the arithmetic is ``Decimal``, stated as a case.

        Sixty-four prompt tokens and 2,234 completion tokens at 0.15 and 0.6 cost
        exactly 0.00135 USD. Rounded to four places the exact value is 0.0014 and
        the float is 0.0013, because ``0.00135`` is not a binary fraction: the
        nearest double is a hair below it and rounds the other way. A cost that
        moved with the representation of the number would be a cost nobody could
        reproduce.
        """
        tokens = {"prompt_tokens": 64, "cached_tokens": 0, "completion_tokens": 2234}
        exact = (
            Decimal(64) * Decimal("0.15") + Decimal(2234) * Decimal("0.6")
        ) / Decimal(10 ** 6)
        self.assertEqual(Decimal("0.00135"), exact)
        self.assertEqual(
            Decimal("0.0014"), exact.quantize(Decimal("0.0001"))
        )
        from_float = Decimal(
            str(round((64 * 0.15 + 2234 * 0.6) / 10 ** 6, 4))
        )
        self.assertEqual(Decimal("0.0013"), from_float)
        self.assertNotEqual(
            exact.quantize(Decimal("0.0001")),
            from_float,
            "the two representations agreed, so this case proves nothing",
        )


class TierTests(unittest.TestCase):
    def test_the_peak_windows_are_monday_to_friday_nine_to_twelve_and_two_to_six(self):
        self.assertEqual("peak", readiness.price_tier(PEAK_INSTANT)[0])

    def test_a_tuesday_evening_is_ordinary(self):
        """The owner's speed run began at 20:41 SGT on a Tuesday."""
        tier, reason = readiness.price_tier(ORDINARY_INSTANT)
        self.assertEqual("ordinary", tier)
        self.assertIn("20:41", reason)
        self.assertIn("Tuesday", reason)

    def test_a_weekend_morning_is_ordinary(self):
        self.assertEqual("ordinary", readiness.price_tier(WEEKEND_INSTANT)[0])

    def test_an_instant_that_is_not_a_time_is_refused(self):
        with self.assertRaises(readiness.ReadinessError):
            readiness.price_tier(None)


class StatisticTests(unittest.TestCase):
    def test_the_median_of_an_even_count_is_the_mean_of_the_two_middles(self):
        self.assertEqual(
            Decimal("2.5"), readiness.median([Decimal(1), Decimal(2), Decimal(3), Decimal(4)])
        )

    def test_the_p90_is_nearest_rank(self):
        """With ten values the ninth is the p90, not an interpolated number."""
        values = [Decimal(value) for value in range(1, 11)]
        self.assertEqual(Decimal(9), readiness.percentile(values, Decimal("0.9")))

    def test_no_values_is_refused_rather_than_answered(self):
        with self.assertRaises(readiness.ReadinessError):
            readiness.median([])
        with self.assertRaises(readiness.ReadinessError):
            readiness.percentile([], Decimal("0.9"))


class RefusalTests(unittest.TestCase):
    def test_out_must_be_under_docs_notes(self):
        with self.assertRaises(readiness.ReadinessError):
            readiness.resolve_out(PROJECT_ROOT / "README.md")
        self.assertIsNone(readiness.resolve_out(None))
        target = readiness.NOTES_DIR / "a-report.md"
        self.assertEqual(target.resolve(), readiness.resolve_out(target))

    def test_the_command_refuses_an_out_outside_docs_notes_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            err = io.StringIO()
            with redirect_stderr(err):
                code = readiness.main(
                    [
                        "--speed-run", tmp,
                        "--price-in-per-m", "0.15",
                        "--price-out-per-m", "0.6",
                        "--out", str(out),
                    ]
                )
            self.assertEqual(1, code)
            self.assertIn("docs/notes", err.getvalue())
            self.assertFalse(out.exists())

    def test_a_speed_run_with_no_case_files_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual({}, readiness.speed_run_documents(Path(tmp)))
            with self.assertRaises(readiness.ReadinessError):
                readiness.render(
                    Path(tmp),
                    price_in=Decimal("0.15"),
                    price_out=Decimal("0.6"),
                    run=always(0),
                )

    def test_a_baseline_that_replayed_its_advocates_is_refused(self):
        """Its call seconds are the judge's only, so it is not a whole run.

        28 of ``runs/<model>/``'s 29 cases replayed their advocates from an
        earlier run. Comparing such a run's call seconds with a run that made
        every call would compare a partial measurement with a whole one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_run(Path(tmp) / "run", replay={"run_dir": "runs/earlier"})
            with self.assertRaises(readiness.ReadinessError) as caught:
                readiness.baseline_documents(run_dir)
            self.assertIn("replay", str(caught.exception))

    def test_a_baseline_that_made_its_own_calls_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_run(Path(tmp) / "run")
            self.assertEqual({101, 102}, set(readiness.baseline_documents(run_dir)))


class IdentityTests(unittest.TestCase):
    def test_the_identity_names_the_run_without_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_run(Path(tmp) / "run")
            identity = readiness.speed_run_identity(run_dir)

            self.assertEqual("20261006T124114.291705+0000-1", identity["invocation_id"])
            self.assertEqual(
                "b129824178b51b6d655bc0863f805cc75fe1f82b", identity["git_commit"]
            )
            self.assertIs(True, identity["parallel_calls"])
            self.assertEqual(2, identity["concurrency"])
            self.assertEqual(64, len(identity["run_json_sha256"]))
            self.assertNotIn(tmp, json.dumps(identity, default=str))


class FreezeGateTests(unittest.TestCase):
    """The freeze gate is read from the diff, not from the exit status.

    ``git diff --name-only`` exits 0 whether or not there is a diff, so a check
    that only looked at the exit status would pass over a prompt that moved. The
    criterion is that the two protected trees show the one file this repository
    corrected on purpose and nothing else.
    """

    def test_the_allowed_file_alone_passes(self):
        self.assertTrue(
            readiness.shows_only_the_allowed_file(
                Done(0, "policy/amendments/README.md\n")
            )
        )

    def test_a_moved_prompt_fails_even_though_git_exited_zero(self):
        self.assertFalse(
            readiness.shows_only_the_allowed_file(
                Done(0, "policy/amendments/README.md\nprompts/v1/judge.system.md\n")
            )
        )

    def test_a_moved_policy_json_fails(self):
        self.assertFalse(
            readiness.shows_only_the_allowed_file(Done(0, "policy/no_show.json\n"))
        )

    def test_a_non_zero_exit_fails(self):
        self.assertFalse(
            readiness.shows_only_the_allowed_file(
                Done(1, "policy/amendments/README.md\n")
            )
        )

    def test_an_empty_diff_fails(self):
        """The criterion is what the diff shows, and it should show that file."""
        self.assertFalse(readiness.shows_only_the_allowed_file(Done(0, "")))

    def test_a_process_that_exited_zero_passes_the_exit_check(self):
        self.assertTrue(readiness.exits_zero(Done(0)))
        self.assertFalse(readiness.exits_zero(Done(1)))


class ReportTests(unittest.TestCase):
    """The whole report, over the fixture, with the heavy parts injected."""

    def render(self, run_dir: Path, run=None, replay=None, gate=None):
        return readiness.render(
            run_dir,
            price_in=Decimal("0.15"),
            price_out=Decimal("0.6"),
            price_cached_in=Decimal("0.003"),
            run=run or always(0),
            replay=replay or (lambda: fake_quality()[0]),
            gate=gate or (lambda: fake_quality()[1]),
        )

    def test_every_dimension_says_pass_or_fail_and_the_result_lists_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(build_run(Path(tmp) / "run"))

            for name in (
                "Quality",
                "Speed",
                "Reproducibility",
                "Human management",
                "Logs",
            ):
                self.assertIn("### {0} -- ".format(name), text)
            headings = [
                line for line in text.splitlines() if line.startswith("### ")
            ]
            self.assertEqual(5, len(headings))
            for heading in headings:
                self.assertTrue(
                    heading.endswith(readiness.PASS) or heading.endswith(readiness.FAIL),
                    heading,
                )
            self.assertIn("## Result", text)
            self.assertEqual(
                5,
                len(
                    [
                        line
                        for line in text.splitlines()
                        if line.startswith("- ") and ":" in line
                        and line.split(":")[0][2:]
                        in (
                            "Quality",
                            "Speed",
                            "Reproducibility",
                            "Human management",
                            "Logs",
                        )
                    ]
                ),
            )

    def test_the_report_prints_no_absolute_path(self):
        """An absolute path may not go into ``docs/``, so none is in the text."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_run(Path(tmp) / "run")
            text = self.render(run_dir)

            self.assertNotIn(str(run_dir), text)
            self.assertNotIn(tmp, text)
            self.assertNotIn("/Users/", text)

    def test_a_failing_subprocess_fails_the_reproducibility_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(build_run(Path(tmp) / "run"), run=always(1))

            self.assertIn("### Reproducibility -- {0}".format(readiness.FAIL), text)
            self.assertIn("At least one dimension fails.", text)

    def test_the_speed_section_compares_like_for_like_and_names_the_shared_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(build_run(Path(tmp) / "run"))

            self.assertIn("Compared with the sequential", text)
            self.assertIn("policy-v2", text)
            self.assertIn("case numbers", text)

    def test_the_wild_v2_mean_is_labelled_as_another_case_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(build_run(Path(tmp) / "run"))

            self.assertIn("not** as a baseline", text)
            self.assertIn("different set", text)

    def test_the_prices_and_the_tier_are_stated(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(build_run(Path(tmp) / "run"))

            self.assertIn("0.15 USD/M", text)
            self.assertIn("0.6 USD/M", text)
            self.assertIn("cached input 0.003 USD/M", text)
            self.assertIn("ordinary", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

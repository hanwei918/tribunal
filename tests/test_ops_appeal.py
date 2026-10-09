"""The appeal command of ``ops/appeal.py``.

Policy version 6 carries an appeal clause, ``POL-GEN-04``, and this is the module
that executes it. Nine things are asserted here, over the committed version-6
corpus run rather than over a restatement of it:

* **The window.** The number of days is read out of ``POL-GEN-04``'s own
  sentence, the boundary is inclusive, and a sentence whose number has been
  edited in a copied policy is **refused** rather than honoured.
* **The once rule.** A second appeal on the same trip is refused, and an appeal
  on another trip is not.
* **The ruling.** An escalated case has no ruling to appeal.
* **The evidence.** Only the listed record kinds may be added; a statement, a
  mix with a statement, and an unknown kind are all refused.
* **The reviewer.** A reviewer who heard the trip before is refused, and so is a
  reviewer whose id is the rider's or the driver's.
* **The execution.** The threshold is read out of ``POL-GEN-05``; a ruling at or
  under it was executed and a granted appeal reverses it, and one above it is
  held.
* **The writes.** Nothing is written without ``--out``, and an ``--out`` inside
  ``runs/`` is refused.
* **The determinism.** Two runs of one command are byte-identical.
* **The layer's rules.** The import-graph and answer-key tests in
  ``tests/test_ops_layer.py`` cover this module through ``every_command``.

**No test is run here.** The owner runs every test outside the sandbox.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import appeal  # noqa: E402
from tribunal import loader  # noqa: E402

# The committed version-6 corpus run, which the task names as the runs to test
# against. Its case files record ``configuration.policy_version`` 6, so the
# general policy it is read at carries ``POL-GEN-04`` and ``POL-GEN-05``.
V6_RUN = PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash"

# A decided corpus case: 101 ruled ``PARTIAL_REFUND``, so a ruling issued and
# there is something to appeal. An escalated case: 107 was sent to a reviewer,
# so there is not.
DECIDED_CASE = 101
ESCALATED_CASE = 107

# A ruling under the threshold (103, ``PARTIAL_REFUND`` 4.00) and one over it
# (105, ``FULL_REFUND`` 65.13), for the two execution states.
UNDER_THRESHOLD_CASE = 103
OVER_THRESHOLD_CASE = 105

# The six checks, in the order the task lists them.
EXPECTED_CHECKS: Tuple[str, ...] = (
    "once",
    "in_time",
    "ruling_exists",
    "evidence",
    "reviewer",
    "execution",
)

# The five checks that must pass for an appeal to be accepted. The execution
# check reports the state of the money and never refuses.
DECISION_CHECKS: Tuple[str, ...] = EXPECTED_CHECKS[:-1]

# A reviewer id that is a party to no corpus trip.
NEW_REVIEWER = "REV-9001"

# Directories that are not repository content, for the write check.
NOT_REPOSITORY_CONTENT = frozenset(
    {".git", ".workbuddy-ai", "__pycache__", ".venv", "tmp", "output"}
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def run_command(arguments: Sequence[str]) -> Tuple[int, str, str]:
    """``appeal.main`` with both streams captured. Returns ``(code, out, err)``."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = appeal.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def run_and_policies(case_no: int = DECIDED_CASE):
    """``(LoadedRun, policies)`` for one corpus case of the version-6 run."""
    run = appeal.load_run(V6_RUN, case_no)
    policies = loader.load_policies(run.category, run.policy_version)
    return run, policies


def later_instant(run) -> datetime:
    """The later of the trip's time and the ruling's issue time."""
    trip = datetime.fromisoformat(run.trip_at) if run.trip_at else None
    issue = datetime.fromisoformat(run.issue_at)
    return max(instant for instant in (trip, issue) if instant is not None)


def appeal_arguments(
    case_no: int = DECIDED_CASE,
    *,
    lodged_at: str,
    evidence: str = "GPS_EXPORT",
    reviewer: str = NEW_REVIEWER,
    filed_by: str = "rider",
    run_dir: Path = V6_RUN,
    now: Optional[str] = None,
    earlier_reviews: Optional[Path] = None,
    earlier_appeals: Optional[Path] = None,
    out: Optional[Path] = None,
) -> List[str]:
    arguments = [
        "--run-dir",
        str(run_dir),
        "--case",
        str(case_no),
        "--filed-by",
        filed_by,
        "--lodged-at",
        lodged_at,
        "--evidence",
        evidence,
        "--reviewer",
        reviewer,
    ]
    if now is not None:
        arguments += ["--now", now]
    if earlier_reviews is not None:
        arguments += ["--earlier-reviews", str(earlier_reviews)]
    if earlier_appeals is not None:
        arguments += ["--earlier-appeals", str(earlier_appeals)]
    if out is not None:
        arguments += ["--out", str(out)]
    return arguments


def parse(out: str) -> Dict[str, Any]:
    return json.loads(out)


def check_of(result: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for check in result["checks"]:
        if check["check"] == name:
            return check
    raise AssertionError("{0} is not in the result's checks".format(name))


def repository_files() -> set:
    found = set()
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in NOT_REPOSITORY_CONTENT for part in relative.parts[:-1]):
            continue
        found.add(str(relative))
    return found


def mutate_rule(policies: Dict[str, Any], clause_id: str, replace) -> Dict[str, Any]:
    """A JSON round-tripped copy of ``policies`` with one clause's rule changed.

    The copy is made through JSON so the mutation is applied to a document
    rather than to a live object the caller still holds, and a mutation that
    failed to apply is a test that fails rather than one that silently passes.
    """
    copy = json.loads(json.dumps(policies, default=str))
    found = False
    for policy in copy.values():
        for clause in policy.get("clauses") or []:
            if clause.get("id") == clause_id:
                clause["rule"] = replace(clause["rule"])
                found = True
    if not found:
        raise AssertionError("{0} is not in the loaded policy".format(clause_id))
    return copy


# --------------------------------------------------------------------------
# The accepted appeal
# --------------------------------------------------------------------------
class TheAcceptedAppealTests(unittest.TestCase):
    """A timely appeal with a record kind and a new reviewer is accepted."""

    def test_a_timely_appeal_with_a_record_kind_and_a_new_reviewer_is_accepted(self):
        run, _policies = run_and_policies()
        lodged = (later_instant(run) + timedelta(days=10)).isoformat()
        code, out, err = run_command(
            appeal_arguments(lodged_at=lodged, evidence="GPS_EXPORT", reviewer=NEW_REVIEWER)
        )
        self.assertEqual(0, code, err)
        result = parse(out)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(NEW_REVIEWER, result["reviewer"])
        self.assertEqual(101, result["case_no"])
        self.assertEqual("corpus", result["set"])
        self.assertEqual("rider", result["filed_by"])
        for name in DECISION_CHECKS:
            with self.subTest(check=name):
                self.assertTrue(check_of(result, name)["result"], name)

    def test_the_checks_are_the_six_the_task_names_in_order(self):
        run, _policies = run_and_policies()
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        _code, out, _err = run_command(appeal_arguments(lodged_at=lodged))
        result = parse(out)
        self.assertEqual(
            list(EXPECTED_CHECKS), [check["check"] for check in result["checks"]]
        )

    def test_every_check_carries_a_clause_and_the_text_it_read(self):
        run, policies = run_and_policies()
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        _code, out, _err = run_command(appeal_arguments(lodged_at=lodged))
        result = parse(out)
        rule04 = appeal.clause_rule_text("POL-GEN-04", policies)
        rule05 = appeal.clause_rule_text("POL-GEN-05", policies)
        for check in result["checks"]:
            with self.subTest(check=check["check"]):
                self.assertTrue(check["sentence"], check)
                if check["clause"] == "POL-GEN-04":
                    self.assertIn(check["sentence"], rule04)
                else:
                    self.assertIn(check["sentence"], rule05)

    def test_the_assigned_reviewer_is_absent_when_the_appeal_is_refused(self):
        run, _policies = run_and_policies()
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        _code, out, _err = run_command(
            appeal_arguments(lodged_at=lodged, evidence="STATEMENT")
        )
        result = parse(out)
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["reviewer"])


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
class TheWindowTests(unittest.TestCase):
    """The number of days is read out of the clause, and the boundary is the clause's."""

    def setUp(self):
        self.run, self.policies = run_and_policies()

    def test_the_window_is_read_out_of_the_clause(self):
        sentence, days = appeal.read_appeal_window(self.policies)
        self.assertEqual(30, days)
        self.assertIn(sentence, appeal.clause_rule_text("POL-GEN-04", self.policies))
        self.assertIn("30", sentence)

    def test_the_boundary_day_thirty_is_accepted_and_day_thirty_one_is_refused(self):
        later = later_instant(self.run)
        day_30 = (later + timedelta(days=30)).isoformat()
        day_31 = (later + timedelta(days=31)).isoformat()

        code, out, err = run_command(appeal_arguments(lodged_at=day_30))
        self.assertEqual(0, code, err)
        self.assertTrue(parse(out)["accepted"], "day 30 is inside the window")

        code, out, err = run_command(appeal_arguments(lodged_at=day_31))
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"], "day 31 is outside the window")
        self.assertFalse(check_of(result, "in_time")["result"])

    def test_the_deadline_is_the_later_of_the_trip_and_the_issue(self):
        result_deadline = parse(
            run_command(
                appeal_arguments(lodged_at=later_instant(self.run).isoformat())
            )[1]
        )["deadline"]
        expected = later_instant(self.run) + timedelta(days=30)
        self.assertEqual(expected, datetime.fromisoformat(result_deadline))

    def test_a_changed_number_in_a_copied_policy_is_refused(self):
        """The red-first fixture: the ``30`` in a copy of the clause's sentence."""
        changed = mutate_rule(
            self.policies, "POL-GEN-04", lambda rule: rule.replace("within 30 days", "within 31 days")
        )
        self.assertNotEqual(self.policies, changed, "the fixture did not change the policy")
        with self.assertRaises(appeal.AppealPolicyError):
            appeal.read_appeal_window(changed)

    def test_a_reworded_sentence_in_a_copied_policy_is_refused(self):
        changed = mutate_rule(
            self.policies,
            "POL-GEN-04",
            lambda rule: rule.replace(
                "or of the ruling's issue, whichever is later", "or of the ruling's date"
            ),
        )
        with self.assertRaises(appeal.AppealPolicyError):
            appeal.read_appeal_window(changed)


# --------------------------------------------------------------------------
# The once rule
# --------------------------------------------------------------------------
class TheOnceTests(unittest.TestCase):
    """A second appeal on the same trip is refused."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run, _policies = run_and_policies()
        self.lodged = (later_instant(self.run) + timedelta(days=1)).isoformat()

    def _write(self, name: str, entries: List[Mapping[str, Any]]) -> Path:
        path = self.root / name
        path.write_text(json.dumps(entries), encoding="utf-8")
        return path

    def test_a_second_appeal_on_the_same_trip_is_refused(self):
        appeals = self._write(
            "appeals.json", [{"case": 101, "trip_id": self.run.trip_id}]
        )
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, earlier_appeals=appeals)
        )
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"])
        self.assertFalse(check_of(result, "once")["result"])

    def test_an_appeal_on_another_trip_does_not_refuse(self):
        appeals = self._write(
            "appeals.json", [{"case": 999, "trip_id": "TRP-99999"}]
        )
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, earlier_appeals=appeals)
        )
        self.assertEqual(0, code, err)
        self.assertTrue(parse(out)["accepted"])


# --------------------------------------------------------------------------
# The ruling
# --------------------------------------------------------------------------
class TheRulingTests(unittest.TestCase):
    """An escalated case has no ruling to appeal."""

    def test_an_escalated_case_is_refused_for_having_no_ruling(self):
        run, _policies = run_and_policies(ESCALATED_CASE)
        self.assertEqual("ESCALATE", run.ruling_value)
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        code, out, err = run_command(
            appeal_arguments(case_no=ESCALATED_CASE, lodged_at=lodged)
        )
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"])
        ruling_check = check_of(result, "ruling_exists")
        self.assertFalse(ruling_check["result"])
        self.assertIn("ESCALATE", ruling_check["detail"])


# --------------------------------------------------------------------------
# The evidence
# --------------------------------------------------------------------------
class TheEvidenceTests(unittest.TestCase):
    """Only the listed record kinds may be added."""

    def setUp(self):
        self.run, self.policies = run_and_policies()
        self.lodged = (later_instant(self.run) + timedelta(days=1)).isoformat()

    def test_every_listed_record_kind_is_accepted(self):
        for kind in appeal.RECORD_EVIDENCE_KINDS:
            with self.subTest(kind=kind):
                code, out, err = run_command(
                    appeal_arguments(lodged_at=self.lodged, evidence=kind)
                )
                self.assertEqual(0, code, err)
                self.assertTrue(parse(out)["accepted"], kind)

    def test_an_appeal_adding_only_a_statement_is_refused(self):
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, evidence="STATEMENT")
        )
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"])
        evidence_check = check_of(result, "evidence")
        self.assertFalse(evidence_check["result"])
        self.assertIn("statement", evidence_check["detail"])

    def test_a_statement_beside_a_record_kind_is_refused(self):
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, evidence="GPS_EXPORT,STATEMENT")
        )
        self.assertEqual(3, code, err)
        self.assertFalse(parse(out)["accepted"])

    def test_a_kind_the_clause_does_not_list_is_refused(self):
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, evidence="SELFIE")
        )
        self.assertEqual(3, code, err)
        self.assertFalse(parse(out)["accepted"])

    def test_the_evidence_sentence_is_the_clause_s(self):
        _code, out, _err = run_command(appeal_arguments(lodged_at=self.lodged))
        sentence = check_of(parse(out), "evidence")["sentence"]
        self.assertIn(sentence, appeal.clause_rule_text("POL-GEN-04", self.policies))


# --------------------------------------------------------------------------
# The reviewer
# --------------------------------------------------------------------------
class TheReviewerTests(unittest.TestCase):
    """A reviewer may not have heard the trip, and may not be a party."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run, _policies = run_and_policies()
        self.lodged = (later_instant(self.run) + timedelta(days=1)).isoformat()

    def _reviews(self, entries: List[Mapping[str, Any]]) -> Path:
        path = self.root / "reviews.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return path

    def test_a_reviewer_who_reviewed_the_trip_before_is_refused(self):
        reviews = self._reviews(
            [{"case": 101, "trip_id": self.run.trip_id, "reviewer": NEW_REVIEWER}]
        )
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, earlier_reviews=reviews)
        )
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"])
        self.assertFalse(check_of(result, "reviewer")["result"])

    def test_a_reviewer_who_reviewed_another_trip_is_accepted(self):
        reviews = self._reviews(
            [{"case": 999, "trip_id": "TRP-99999", "reviewer": NEW_REVIEWER}]
        )
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, earlier_reviews=reviews)
        )
        self.assertEqual(0, code, err)
        self.assertTrue(parse(out)["accepted"])

    def test_a_reviewer_whose_id_is_the_rider_is_refused(self):
        self.assertIsNotNone(self.run.rider_id)
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, reviewer=self.run.rider_id)
        )
        self.assertEqual(3, code, err)
        result = parse(out)
        self.assertFalse(result["accepted"])
        self.assertFalse(check_of(result, "reviewer")["result"])

    def test_a_reviewer_whose_id_is_the_driver_is_refused(self):
        self.assertIsNotNone(self.run.driver_id)
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, reviewer=self.run.driver_id)
        )
        self.assertEqual(3, code, err)
        self.assertFalse(parse(out)["accepted"])


# --------------------------------------------------------------------------
# The execution
# --------------------------------------------------------------------------
class TheExecutionTests(unittest.TestCase):
    """The threshold is read out of ``POL-GEN-05``, and the state follows it."""

    def setUp(self):
        self._run, self.policies = run_and_policies()

    def test_the_threshold_is_read_out_of_the_clause(self):
        sentence, threshold = appeal.read_execution_threshold(self.policies)
        self.assertIn(sentence, appeal.clause_rule_text("POL-GEN-05", self.policies))
        self.assertEqual(Decimal("8.0"), threshold)

    def test_a_moved_execution_sentence_is_refused(self):
        changed = mutate_rule(
            self.policies,
            "POL-GEN-05",
            lambda rule: rule.replace(
                "does not exceed execution_threshold_sgd is executed automatically on issue",
                "is settled at once",
            ),
        )
        with self.assertRaises(appeal.AppealPolicyError):
            appeal.read_execution_threshold(changed)

    def _state(self, case_no: int) -> Mapping[str, Any]:
        run, _policies = run_and_policies(case_no)
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        _code, out, _err = run_command(
            appeal_arguments(case_no=case_no, lodged_at=lodged)
        )
        return parse(out)["execution"]

    def test_a_ruling_at_or_under_the_threshold_was_executed_and_is_reversible(self):
        execution = self._state(UNDER_THRESHOLD_CASE)
        self.assertEqual(appeal.STATE_EXECUTED, execution["state"])
        self.assertLessEqual(
            execution["monetary_effect_sgd"], execution["execution_threshold_sgd"]
        )

    def test_a_ruling_over_the_threshold_is_suspended(self):
        execution = self._state(OVER_THRESHOLD_CASE)
        self.assertEqual(appeal.STATE_SUSPENDED, execution["state"])
        self.assertGreater(
            execution["monetary_effect_sgd"], execution["execution_threshold_sgd"]
        )

    def test_the_execution_check_names_pol_gen_05_and_never_refuses(self):
        run, _policies = run_and_policies(UNDER_THRESHOLD_CASE)
        lodged = (later_instant(run) + timedelta(days=1)).isoformat()
        _code, out, _err = run_command(
            appeal_arguments(case_no=UNDER_THRESHOLD_CASE, lodged_at=lodged)
        )
        execution_check = check_of(parse(out), "execution")
        self.assertEqual("POL-GEN-05", execution_check["clause"])
        self.assertEqual(appeal.STATE_EXECUTED, execution_check["result"])


# --------------------------------------------------------------------------
# The writes
# --------------------------------------------------------------------------
class TheWritesTests(unittest.TestCase):
    """Nothing is written without ``--out``, and ``runs/`` is refused."""

    def setUp(self):
        self.run, _policies = run_and_policies()
        self.lodged = (later_instant(self.run) + timedelta(days=1)).isoformat()

    def test_nothing_is_written_without_an_out(self):
        before = repository_files()
        code, out, err = run_command(appeal_arguments(lodged_at=self.lodged))
        self.assertEqual(0, code, err)
        self.assertTrue(out.strip(), "the result was printed to stdout")
        self.assertEqual(before, repository_files())

    def test_an_out_inside_runs_is_refused_and_nothing_is_written(self):
        destination = V6_RUN / "appeal-scratch.json"
        code, out, err = run_command(
            appeal_arguments(lodged_at=self.lodged, out=destination)
        )
        self.assertEqual(2, code)
        self.assertIn("FATAL", err)
        self.assertFalse(destination.exists())

    def test_an_out_of_its_own_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "appeal.json"
            code, out, err = run_command(
                appeal_arguments(lodged_at=self.lodged, out=destination)
            )
            self.assertEqual(0, code, err)
            self.assertTrue(destination.is_file())
            self.assertEqual("", out)
            written = json.loads(destination.read_text(encoding="utf-8"))
            self.assertTrue(written["accepted"])


# --------------------------------------------------------------------------
# The determinism
# --------------------------------------------------------------------------
class TheDeterminismTests(unittest.TestCase):
    """Two runs of one command are byte-identical."""

    def test_two_runs_are_byte_identical(self):
        run, _policies = run_and_policies()
        arguments = appeal_arguments(
            lodged_at=(later_instant(run) + timedelta(days=2)).isoformat(),
            evidence="GPS_EXPORT,PHOTOGRAPH",
            now=(later_instant(run) + timedelta(days=3)).isoformat(),
        )
        self.assertEqual(run_command(arguments), run_command(arguments))


if __name__ == "__main__":
    unittest.main()

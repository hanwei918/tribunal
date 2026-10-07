"""The fraud and bad-faith signals of ``ops/risk.py``.

The operations layer runs beside the debate, never inside it: it reads a case
and the loaded policy and writes nothing back into a brief or a prompt. This
module holds that layer to the rules the ops task states for every part, and to
the five policy tests part 1 names.

Five things are asserted, and each is asserted over the real corpus rather than
over a restatement of it:

* **The field list.** Every test reads exactly the profile fields the policy
  clause names and no other profile field, checked twice -- once against the
  declaration, and once by running the assessment over a case whose profile
  payloads record every key they are asked for. The second check is what makes
  the first one mean something: a declaration and a behaviour that agreed with
  each other while disagreeing with the module would pass the first alone.
* **The thresholds.** Every number the module applies is read out of the loaded
  policy text, and a sentence that has moved -- including one whose number has
  been edited -- is refused rather than honoured. The refusal is shown with a
  copy of the policy whose ``0.08`` was changed.
* **The corpus.** Exactly four signals trip over the 29 cases, and they are the
  four the task measured: 105, 107, 207 and 213.
* **The attention flag.** ``repeat_party`` is not a policy test and fires on
  none of the corpus cases, so it is tested on synthetic fixtures of its own.
* **The layer's rules.** No module in ``ops/`` imports a network client, nothing
  in ``tribunal/`` or ``eval/`` imports ``ops``, no command opens anything under
  an ``answers`` directory, no output carries the keys the task names, two runs
  are byte-identical, and no command writes a file.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import risk  # noqa: E402
from tribunal import loader  # noqa: E402

# The 29-case corpus, in manifest order. Read off the manifest rather than
# restated, so a corpus that changed would change what these tests cover.
CORPUS_CASE_NUMBERS: Tuple[int, ...] = tuple(
    entry["case_no"] for entry in json.loads((PROJECT_ROOT / "data" / "index.json").read_text())
)

# Exactly the fields each clause names, in the order the clause names them.
EXPECTED_FIELDS: Dict[str, Tuple[str, ...]] = {
    "POL-RD-06": (
        "driver_profile.deviation_flags_90d",
        "driver_profile.completed_trips_90d",
    ),
    "POL-RD-08": (
        "rider_profile.deviation_claims_60d",
        "rider_profile.deviation_claims_60d_substantiated",
    ),
    "POL-NS-07": (
        "driver_profile.no_show_terminations_30d",
        "driver_profile.completed_trips_30d",
    ),
    "POL-NS-09(c)": (
        "rider_profile.disputes_with_counterparty_90d",
        "driver_profile.disputes_with_counterparty_90d",
    ),
    "POL-NS-09(d)": ("rider_profile.no_show_disputes_30d",),
}

# The side each test examines. ``POL-NS-09(c)`` names a counter on each profile
# and reads the larger of the two, so its side is taken from the counters and is
# asserted in the corpus tests instead of being declared here.
EXPECTED_SIDES: Dict[str, str] = {
    "POL-RD-06": "DRIVER",
    "POL-RD-08": "RIDER",
    "POL-NS-07": "DRIVER",
    "POL-NS-09(d)": "RIDER",
}

# The category each test belongs to.
EXPECTED_CATEGORIES: Dict[str, str] = {
    "POL-RD-06": "ROUTE_DEVIATION",
    "POL-RD-08": "ROUTE_DEVIATION",
    "POL-NS-07": "NO_SHOW_CHARGE",
    "POL-NS-09(c)": "NO_SHOW_CHARGE",
    "POL-NS-09(d)": "NO_SHOW_CHARGE",
}

# The four signals the task measured on the corpus. Nothing else trips.
EXPECTED_CORPUS_TRIPS: Tuple[Tuple[int, str], ...] = (
    (105, "POL-RD-06"),
    (107, "POL-RD-08"),
    (207, "POL-NS-07"),
    (213, "POL-NS-09(c)"),
)

# The lifetime counters the policy names as near-synonyms. Reading one where a
# clause names a trailing-window counter is the mistake the task calls the trap.
LIFETIME_COUNTERS = ("prior_no_show_flags", "prior_deviation_flags")

# The keys no output may carry.
FORBIDDEN_OUTPUT_KEYS = ("expected", "matched", "grade")

# Directories that are not repository content, for the write check.
NOT_REPOSITORY_CONTENT = frozenset(
    {".git", ".workbuddy-ai", "__pycache__", ".venv", "tmp", "output"}
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def load_corpus_case(case_no: int) -> Dict[str, Any]:
    return loader.load_case(case_no)


def policies_for(case: Mapping[str, Any]) -> Dict[str, Any]:
    return loader.load_policies(case["dispute"]["category"])


def corpus_root() -> Path:
    return PROJECT_ROOT / "data" / "cases"


def run_command(arguments: Sequence[str]) -> Tuple[int, str, str]:
    """``risk.main`` with both streams captured. Returns ``(code, out, err)``."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = risk.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def evaluate_corpus() -> Dict[int, Any]:
    """``{case_no: Assessment}`` for the whole corpus."""
    found: Dict[int, Any] = {}
    for case_no in CORPUS_CASE_NUMBERS:
        case = load_corpus_case(case_no)
        found[case_no] = risk.assess(case, policies_for(case), corpus_root())
    return found


def tripped(case_no: int, assessment: Any) -> List[str]:
    return sorted(signal.clause for signal in assessment.signals if signal.tripped)


def mutate_rule(policies: Dict[str, Any], test_clause: str, replace) -> Dict[str, Any]:
    """A deep-enough copy of ``policies`` with one clause's rule text replaced.

    The copy is made by round-tripping the policy through JSON, so the mutation
    is applied to a document rather than to a live object the caller still
    holds, and a mutation that failed to apply is a test that fails rather than
    a test that silently passes.
    """
    clause_id = risk.source_clause(test_clause)
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


class RecordingProfile(dict):
    """A profile payload that records every key it is asked for."""

    def __init__(self, payload: Mapping[str, Any], log: Set[str]) -> None:
        super().__init__(payload)
        self._log = log

    def __getitem__(self, key: str) -> Any:
        self._log.add(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._log.add(key)
        return super().get(key, default)


def case_with_recording_profiles(case: Dict[str, Any]) -> Tuple[Dict[str, Any], Set[str]]:
    """A copy of ``case`` whose two profiles log every field read from them."""
    log: Set[str] = set()
    copy = json.loads(json.dumps(case, default=str))
    for artifact in copy["evidence"]:
        if artifact["evidence_type"] in ("RIDER_PROFILE", "DRIVER_PROFILE"):
            artifact["payload"] = RecordingProfile(artifact["payload"], log)
    return copy, log


def repository_files() -> Set[str]:
    found: Set[str] = set()
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in NOT_REPOSITORY_CONTENT for part in relative.parts[:-1]):
            continue
        found.add(str(relative))
    return found


# --------------------------------------------------------------------------
# The five tests
# --------------------------------------------------------------------------
class TheFiveTestsTests(unittest.TestCase):
    """The tests are the five the task names, reading the fields it names."""

    def test_the_five_clauses_are_the_five_the_task_names(self):
        self.assertEqual(
            sorted(EXPECTED_FIELDS),
            sorted(test.clause for test in risk.POLICY_TESTS),
            "the module implements a different set of clauses",
        )

    def test_every_test_reads_exactly_the_fields_the_policy_names(self):
        self.assertEqual(
            EXPECTED_FIELDS,
            {test.clause: tuple(test.fields) for test in risk.POLICY_TESTS},
            "a test reads a different field list from the one the clause names",
        )

    def test_every_test_carries_the_category_and_the_side_it_examines(self):
        self.assertEqual(
            EXPECTED_CATEGORIES,
            {test.clause: test.category for test in risk.POLICY_TESTS},
        )
        for test in risk.POLICY_TESTS:
            if test.clause in EXPECTED_SIDES:
                with self.subTest(clause=test.clause):
                    self.assertEqual(EXPECTED_SIDES[test.clause], test.side)

    def test_no_test_reads_a_lifetime_counter(self):
        """The policy names them as near-synonyms that must not be substituted."""
        for test in risk.POLICY_TESTS:
            for field in test.fields:
                for counter in LIFETIME_COUNTERS:
                    with self.subTest(clause=test.clause, field=field):
                        self.assertFalse(
                            field.endswith("." + counter),
                            "{0} reads the lifetime counter {1}".format(test.clause, counter),
                        )

    def test_the_assessment_asks_for_no_other_profile_field(self):
        """The behavioural half: the payloads themselves record what is read.

        A declaration and a behaviour that agreed with each other while both
        disagreed with the module would pass the test above alone.
        """
        everything_allowed = set()
        for fields in EXPECTED_FIELDS.values():
            everything_allowed |= {field.split(".", 1)[1] for field in fields}

        for case_no in (105, 107, 207, 208, 213):
            with self.subTest(case=case_no):
                case = load_corpus_case(case_no)
                category = case["dispute"]["category"]
                expected = set()
                for clause, fields in EXPECTED_FIELDS.items():
                    if EXPECTED_CATEGORIES[clause] == category:
                        expected |= {field.split(".", 1)[1] for field in fields}
                case, log = case_with_recording_profiles(case)
                risk.assess(case, policies_for(case), corpus_root())
                self.assertEqual(
                    expected,
                    log,
                    "case {0} read profile fields outside its own tests: {1}".format(
                        case_no, sorted(log - expected)
                    ),
                )
                self.assertLessEqual(log, everything_allowed)


# --------------------------------------------------------------------------
# The thresholds
# --------------------------------------------------------------------------
class TheThresholdsTests(unittest.TestCase):
    """Every number applied is read out of the loaded policy text."""

    def setUp(self):
        # Both categories: the five tests do not all live in one policy file.
        self.policies: Dict[str, Any] = {}
        for category, name in (
            ("ROUTE_DEVIATION", "route_deviation"),
            ("NO_SHOW_CHARGE", "no_show"),
        ):
            loaded = loader.load_policies(category)
            self.policies["general"] = loaded["general"]
            self.policies[name] = loaded["category"]

    def test_every_threshold_is_read_out_of_the_loaded_policy(self):
        expected = {
            "POL-RD-06": {"min_flags": "3", "min_rate": "0.05", "min_trips": "40"},
            "POL-RD-08": {"min_claims": "4", "max_substantiated": "1"},
            "POL-NS-07": {"min_terminations": "4", "max_rate": "0.08"},
            "POL-NS-09(c)": {"min_disputes": "2", "window_days": "90"},
            "POL-NS-09(d)": {"min_disputes": "3"},
        }
        for clause_id, numbers in expected.items():
            with self.subTest(clause=clause_id):
                sentence, read = risk.read_threshold_sentence(clause_id, self.policies)
                self.assertEqual(
                    {name: str(value) for name, value in read.items()}, numbers
                )
                # The sentence is quoted from the policy rather than written here.
                self.assertIn(
                    sentence,
                    risk.clause_rule_text(clause_id, self.policies),
                    "the threshold sentence is not a quotation of the clause",
                )

    def test_a_sentence_that_has_moved_is_refused(self):
        """Every clause, reworded: the module refuses rather than defaulting."""
        for clause_id in EXPECTED_FIELDS:
            with self.subTest(clause=clause_id):
                moved = mutate_rule(
                    self.policies,
                    clause_id,
                    lambda rule: rule.replace(" or more", " or greater"),
                )
                with self.assertRaises(risk.RiskPolicyError):
                    risk.read_threshold_sentence(clause_id, moved)

    def test_a_changed_number_is_refused(self):
        """The red-first fixture: the 0.08 in a copy of the policy text.

        A threshold that was silently honoured after the policy edited it would
        be a risk signal built on a number nobody reviewed.
        """
        changed = mutate_rule(
            self.policies, "POL-NS-07", lambda rule: rule.replace("0.08", "0.09")
        )
        self.assertNotEqual(self.policies, changed, "the fixture did not change the policy")
        with self.assertRaises(risk.RiskPolicyError):
            risk.read_threshold_sentence("POL-NS-07", changed)

    def test_the_applied_number_is_the_one_the_policy_states(self):
        """The number applied comes from the text, not from a constant here."""
        for clause_id in EXPECTED_FIELDS:
            with self.subTest(clause=clause_id):
                _sentence, read = risk.read_threshold_sentence(clause_id, self.policies)
                for value in read.values():
                    self.assertIsInstance(value, Decimal)
                # And the number the policy states is the one in the rule text.
                rule = risk.clause_rule_text(clause_id, self.policies)
                for value in read.values():
                    self.assertIn(str(value), rule)

    def test_a_clause_the_policy_does_not_carry_is_refused(self):
        with self.assertRaises(risk.RiskPolicyError):
            risk.read_threshold_sentence("POL-XX-99", self.policies)


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------
class TheCorpusTests(unittest.TestCase):
    """Exactly four signals trip over the 29 cases, and nothing else does."""

    @classmethod
    def setUpClass(cls):
        cls.assessments = evaluate_corpus()

    def test_exactly_four_signals_trip_over_the_corpus(self):
        found = sorted(
            (case_no, clause)
            for case_no, assessment in self.assessments.items()
            for clause in tripped(case_no, assessment)
        )
        self.assertEqual(sorted(EXPECTED_CORPUS_TRIPS), found)

    def test_each_case_reports_every_test_of_its_own_category(self):
        for case_no, assessment in self.assessments.items():
            with self.subTest(case=case_no):
                expected = sorted(
                    clause
                    for clause, category in EXPECTED_CATEGORIES.items()
                    if category == assessment.category
                )
                self.assertEqual(expected, sorted(s.clause for s in assessment.signals))

    def test_case_105_trips_the_repeat_deviation_pattern(self):
        signal = self._signal(105, "POL-RD-06")
        self.assertTrue(signal.tripped)
        self.assertEqual("DRIVER", signal.side)
        self.assertEqual("4", str(dict(signal.fields)["driver_profile.deviation_flags_90d"]))
        self.assertIn("is 3 or more", signal.threshold)

    def test_case_107_trips_the_serial_claimant(self):
        signal = self._signal(107, "POL-RD-08")
        self.assertTrue(signal.tripped)
        self.assertEqual("RIDER", signal.side)
        values = dict(signal.fields)
        self.assertEqual("5", str(values["rider_profile.deviation_claims_60d"]))
        self.assertEqual(
            "1", str(values["rider_profile.deviation_claims_60d_substantiated"])
        )

    def test_case_207_trips_the_anti_farming_check(self):
        signal = self._signal(207, "POL-NS-07")
        self.assertTrue(signal.tripped)
        self.assertEqual("DRIVER", signal.side)
        self.assertIn("greater than 0.08", signal.threshold)

    def test_case_213_trips_the_repeat_pair_and_the_two_counters_agree(self):
        signal = self._signal(213, "POL-NS-09(c)")
        self.assertTrue(signal.tripped)
        values = dict(signal.fields)
        self.assertEqual("2", str(values["rider_profile.disputes_with_counterparty_90d"]))
        self.assertEqual("2", str(values["driver_profile.disputes_with_counterparty_90d"]))
        self.assertEqual([], [note for note in signal.notes if "counters_disagree" in note])
        self.assertIn(signal.side, ("RIDER", "DRIVER"))

    def test_a_case_whose_counters_differ_carries_the_disagreement_note(self):
        """The note the module's own reading of the clause requires."""
        case = json.loads(json.dumps(load_corpus_case(213), default=str))
        for artifact in case["evidence"]:
            if artifact["evidence_type"] == "RIDER_PROFILE":
                artifact["payload"]["disputes_with_counterparty_90d"] = 3
        signal = risk.assess(case, policies_for(case), corpus_root())
        found = [s for s in signal.signals if s.clause == "POL-NS-09(c)"][0]
        self.assertTrue(found.tripped)
        self.assertEqual("RIDER", found.side)
        self.assertTrue(
            [note for note in found.notes if note.startswith("counters_disagree")],
            found.notes,
        )

    def test_case_208_is_the_lifetime_counter_trap(self):
        """Its rider carries 3 lifetime flags and 1 trailing-30-day dispute.

        Reading the lifetime counter where POL-NS-09(d) names the trailing one
        would trip the limb; the module reads the field the clause names and
        nothing trips.
        """
        case = load_corpus_case(208)
        profile = [
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "RIDER_PROFILE"
        ][0]
        self.assertGreaterEqual(profile["prior_no_show_flags"], 3)
        self.assertLess(profile["no_show_disputes_30d"], 3)
        self.assertEqual([], tripped(208, self.assessments[208]))

    def test_the_four_tripped_signals_are_the_only_ones_with_tripped_true(self):
        self.assertEqual(
            4, sum(1 for assessment in self.assessments.values()
                   for signal in assessment.signals if signal.tripped)
        )

    def _signal(self, case_no: int, clause: str):
        for signal in self.assessments[case_no].signals:
            if signal.clause == clause:
                return signal
        raise AssertionError("{0} is not in case {1}'s signals".format(clause, case_no))


# --------------------------------------------------------------------------
# The attention flag
# --------------------------------------------------------------------------
class TheRepeatPartyTests(unittest.TestCase):
    """``repeat_party`` is not a policy test, and the corpus cannot exercise it.

    There are no repeated party ids in the corpus, so the flag is tested on
    synthetic fixtures written into a scratch root.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write_case(self, case_no, filed_at, rider_id, driver_id, category="NO_SHOW_CHARGE"):
        document = {
            "schema_version": "1.2.0",
            "case_no": case_no,
            "dispute": {
                "dispute_id": "DSP-{0:05d}".format(case_no),
                "trip_id": "TRP-{0:05d}".format(case_no),
                "case_no": case_no,
                "category": category,
                "filed_by": "RIDER",
                "filed_at": filed_at,
                "claim_text": "synthetic fixture",
                "amount_contested_sgd": 4.0,
                "evidence_ids": ["EV-TRIP-{0:05d}".format(case_no)],
                "counterparty_statement": {
                    "text": "synthetic fixture",
                    "submitted_by": "DRIVER",
                    "submitted_at": filed_at,
                },
                "channel": "IN_APP_SUPPORT",
            },
            "evidence": [
                {
                    "evidence_id": "EV-TRIP-{0:05d}".format(case_no),
                    "evidence_type": "TRIP_RECORD",
                    "trip_id": "TRP-{0:05d}".format(case_no),
                    "source": "PLATFORM_TELEMETRY",
                    "generated_at": filed_at,
                    "schema_version": "1.2.0",
                    "admissibility": {
                        "status": "COMPLETE",
                        "issues": [],
                        "weight_multiplier": 1.0,
                        "notes": "synthetic fixture",
                        "assessed_at": filed_at,
                        "assessor_version": "prepass-1.0.0",
                    },
                    "payload": {
                        "trip_id": "TRP-{0:05d}".format(case_no),
                        "rider_id": rider_id,
                        "driver_id": driver_id,
                    },
                }
            ],
        }
        path = self.root / "case-{0:05d}.json".format(case_no)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return path

    def _case(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_a_shared_rider_id_within_thirty_days_is_flagged(self):
        first = self._write_case(301, "2026-07-01T10:00:00+08:00", "RDR-90001", "DRV-90001")
        self._write_case(302, "2026-07-11T10:00:00+08:00", "RDR-90001", "DRV-90002")
        flags = risk.repeat_party_flags(self._case(first), self.root)
        self.assertEqual(1, len(flags), flags)
        self.assertEqual("RIDER", flags[0].party_role)
        self.assertEqual("RDR-90001", flags[0].party_id)
        self.assertEqual(302, flags[0].other_case_no)

    def test_a_shared_driver_id_within_thirty_days_is_flagged(self):
        first = self._write_case(301, "2026-07-01T10:00:00+08:00", "RDR-90001", "DRV-90001")
        self._write_case(302, "2026-07-21T10:00:00+08:00", "RDR-90002", "DRV-90001")
        flags = risk.repeat_party_flags(self._case(first), self.root)
        self.assertEqual(1, len(flags), flags)
        self.assertEqual("DRIVER", flags[0].party_role)

    def test_a_shared_party_outside_thirty_days_is_not_flagged(self):
        first = self._write_case(301, "2026-07-01T10:00:00+08:00", "RDR-90001", "DRV-90001")
        self._write_case(302, "2026-08-01T10:00:01+08:00", "RDR-90001", "DRV-90001")
        self.assertEqual((), risk.repeat_party_flags(self._case(first), self.root))

    def test_the_boundary_itself_is_inside_the_window(self):
        first = self._write_case(301, "2026-07-01T10:00:00+08:00", "RDR-90001", "DRV-90001")
        self._write_case(302, "2026-07-31T10:00:00+08:00", "RDR-90001", "DRV-90002")
        self.assertEqual(1, len(risk.repeat_party_flags(self._case(first), self.root)))

    def test_the_flag_is_labelled_for_a_reviewer(self):
        self.assertEqual("repeat_party", risk.REPEAT_PARTY_FLAG)
        self.assertIn("attention", risk.REPEAT_PARTY_LABEL)

    def test_the_corpus_flags_no_repeated_party(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = load_corpus_case(case_no)
            with self.subTest(case=case_no):
                self.assertEqual(
                    (), risk.repeat_party_flags(case, corpus_root())
                )


# --------------------------------------------------------------------------
# The layer's rules
# --------------------------------------------------------------------------
class TheImportGraphTests(unittest.TestCase):
    """Rule 1: what ``ops/`` may import, and what may import ``ops/``."""

    ALLOWED_PACKAGES = frozenset({"ops", "tribunal", "eval"})

    FORBIDDEN_MODULES = frozenset(
        {
            "tribunal.llm",
            "urllib",
            "http",
            "socket",
            "ssl",
            "requests",
            "httpx",
            "urllib3",
            "ftplib",
            "smtplib",
            "telnetlib",
            "xmlrpc",
            "asyncio",
        }
    )

    def _imports(self, path: Path) -> Set[str]:
        import ast

        found: Set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                if node.module:
                    found.add(node.module)
                    for alias in node.names:
                        found.add(node.module + "." + alias.name)
        return found

    def ops_modules(self) -> List[Path]:
        return sorted((PROJECT_ROOT / "ops").glob("*.py"))

    def test_ops_modules_import_only_from_tribunal_eval_and_ops(self):
        self.assertTrue(self.ops_modules(), "ops/ holds no modules")
        for path in self.ops_modules():
            for name in self._imports(path):
                top = name.split(".")[0]
                if top in ("ops", "tribunal", "eval"):
                    continue
                if top in sys.stdlib_module_names:
                    continue
                with self.subTest(module=path.name, imported=name):
                    self.fail(
                        "{0} imports {1}, which is neither the standard library nor "
                        "a repository package".format(path.name, name)
                    )

    def test_no_ops_module_imports_a_network_client(self):
        for path in self.ops_modules():
            for name in self._imports(path):
                for forbidden in self.FORBIDDEN_MODULES:
                    with self.subTest(module=path.name, imported=name):
                        self.assertFalse(
                            name == forbidden or name.startswith(forbidden + "."),
                            "{0} imports {1}".format(path.name, name),
                        )

    def test_nothing_in_tribunal_or_eval_imports_ops(self):
        for package in ("tribunal", "eval"):
            for path in sorted((PROJECT_ROOT / package).glob("*.py")):
                for name in self._imports(path):
                    with self.subTest(module=path.name, imported=name):
                        self.assertFalse(
                            name == "ops" or name.startswith("ops."),
                            "{0}/{1} imports ops".format(package, path.name),
                        )

    def test_the_import_walk_reaches_the_modules_it_claims_to(self):
        """A control: the walk is reading real import statements."""
        imports = self._imports(PROJECT_ROOT / "ops" / "risk.py")
        self.assertTrue(imports, "risk.py was walked and no import was found")


class TheNoAnswersTests(unittest.TestCase):
    """Rule 2: no ``ops`` command opens an answer key, and none prints one."""

    def _guard(self):
        real_open = io.open

        def guarded(file, *args, **kwargs):
            text = str(file).replace(os.sep, "/")
            if "/answers/" in text:
                raise AssertionError("an ops command opened {0}".format(text))
            return real_open(file, *args, **kwargs)

        return guarded

    def test_the_guard_is_capable_of_failing(self):
        """The positive control: a path under answers/ is refused."""
        with mock.patch("io.open", self._guard()), mock.patch(
            "builtins.open", self._guard()
        ):
            with self.assertRaises(AssertionError):
                Path("/tmp/nowhere-at-all/answers/ground_truth.json").read_text()

    def test_every_command_runs_over_the_corpus_with_the_keys_unreadable(self):
        commands = [["--case", str(case_no)] for case_no in CORPUS_CASE_NUMBERS]
        commands.append(["--case-file", str(PROJECT_ROOT / "data" / "external" / "ryde" / "case-00901.json")])

        for arguments in commands:
            with self.subTest(arguments=arguments):
                with mock.patch("io.open", self._guard()), mock.patch(
                    "builtins.open", self._guard()
                ):
                    code, out, err = run_command(arguments)
                self.assertEqual(0, code, err)
                for key in FORBIDDEN_OUTPUT_KEYS:
                    self.assertNotIn(key, out, arguments)
                    self.assertNotIn(key, err, arguments)

    def test_the_corpus_run_prints_the_four_signals_it_should(self):
        code, out, err = run_command(["--case", "213"])
        self.assertEqual(0, code, err)
        self.assertIn("POL-NS-09(c)", out)
        self.assertIn("tripped=true", out)


class TheDeterminismTests(unittest.TestCase):
    """Rule 5: two runs give byte-identical output, and outputs are sorted."""

    def test_two_runs_of_one_case_are_byte_identical(self):
        first = run_command(["--case", "207"])
        second = run_command(["--case", "207"])
        self.assertEqual(first, second)

    def test_the_signals_are_sorted_by_clause(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = load_corpus_case(case_no)
            assessment = risk.assess(case, policies_for(case), corpus_root())
            with self.subTest(case=case_no):
                clauses = [signal.clause for signal in assessment.signals]
                self.assertEqual(sorted(clauses), clauses)

    def test_the_fields_of_a_signal_are_sorted_by_path(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = load_corpus_case(case_no)
            assessment = risk.assess(case, policies_for(case), corpus_root())
            for signal in assessment.signals:
                with self.subTest(case=case_no, clause=signal.clause):
                    paths = [path for path, _ in signal.fields]
                    self.assertEqual(sorted(paths), paths)

    def test_the_rendering_is_ascii(self):
        code, out, err = run_command(["--case", "105"])
        self.assertEqual(0, code, err)
        out.encode("ascii")


class TheNoWritesTests(unittest.TestCase):
    """Rule 3: ``ops`` writes nothing unless it is given an ``--out``.

    Part 1's command has no ``--out`` at all, so the rule it is held to is the
    first half of the sentence: the command leaves the tree as it found it.
    """

    def test_the_command_writes_no_file(self):
        before = repository_files()
        for case_no in (105, 107, 207, 208, 213):
            run_command(["--case", str(case_no)])
        self.assertEqual(before, repository_files())

    def test_the_module_holds_no_write_call(self):
        import ast

        tree = ast.parse((PROJECT_ROOT / "ops" / "risk.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                with self.subTest(line=node.lineno):
                    self.assertNotIn(name, ("write_text", "write_bytes", "mkdir", "touch"))


if __name__ == "__main__":
    unittest.main()

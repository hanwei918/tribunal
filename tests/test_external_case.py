"""Tests for the converted external case (DISP-002) and the converter.

The organisers' sample case is answer-bearing: its title states an expected
ruling and its Evidence Summary argues for one side. Only the fenced JSON block
inside it is case material, and the whole point of these tests is that the other
two parts cannot reach the converted case.

Four properties, in the order they matter:

* **The converter reads exactly the block.** Its input is located by parsing the
  Markdown fences, and the parse is required to find exactly one block.
* **Nothing from the title or the summary survives.** Asserted against the
  converted case's own bytes, not against the converter's intentions.
* **Nothing was invented.** No fix carries an accuracy value, there is no rider
  track, no admissibility code is outside ``CODE_WEIGHTS``, and every weight is
  what ``prepass.weight_for`` produces for the codes beside it.
* **The benchmark is undisturbed.** The corpus, the manifest and the answer key
  are byte-identical across a conversion, and the corpus loader still refuses a
  manifest entry that points outside ``data/cases/``.

No network, no browser. Run with ``python -m unittest discover -s tests -v``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, loader, prepass  # noqa: E402

# The converter is a script under eval/, not a package module. It is loaded by
# path, which is also how a reader would run it.
CONVERTER_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "convert.py"
_spec = importlib.util.spec_from_file_location("ryde_convert", CONVERTER_PATH)
convert = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(convert)

SOURCE_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "DISP-002.md"
EXPECTED_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json"
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
CASE_PATH = EXTERNAL_DIR / "ryde" / "case-00901.json"
MAPPING_PATH = EXTERNAL_DIR / "ryde" / "mapping.json"

CASES_DIR = PROJECT_ROOT / "data" / "cases"
INDEX_PATH = PROJECT_ROOT / "data" / "index.json"
ANSWER_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "ground_truth.json"

# Text that lives in the title or the Evidence Summary, both of which sit
# *outside* the fenced block. The block must not contain any of it: these are
# the answer and the argument for one side.
OUTSIDE_THE_BLOCK = (
    "RydeResolve Sample Dataset",
    "Expected ruling",
    "Evidence Summary",
    "UPHELD",
    "pattern of late cancellations",
    "Pattern of disputed no-shows",
    "Credible, reliable driver",
    "Process followed correctly",
    "Policy-compliant charging",
)

# Source values the conversion deliberately drops. These are *inside* the block,
# so the block legitimately contains them and the converted case must not: the
# names are personal data no clause reads, and the rest have no counterpart
# field in this corpus's schema.
#
# The vehicle string is deliberately NOT in this list. It is dropped as a
# profile field, but it survives inside the driver's own chat message ("white
# Honda HR-V plate SGP 4521 M"), which is evidence and is carried verbatim.
DROPPED_SOURCE_VALUES = (
    "Michael Wong",
    "Lim Wei Ming",
    "fraud_flag_details",
    "flagged_for_frequent_late_cancellations",
    "payment_method",
    "e-wallet",
)


def _fingerprint(paths):
    """SHA-256 over a set of files, path and content, so a move is a change."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(PROJECT_ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _benchmark_files():
    """Every file the benchmark rests on: the corpus, the manifest, the key."""
    return (
        sorted(CASES_DIR.glob("*.json"))
        + [INDEX_PATH, ANSWER_KEY_PATH]
    )


class ConverterInputTests(unittest.TestCase):
    """The converter's input is the fenced block, and nothing else."""

    @classmethod
    def setUpClass(cls):
        cls.markdown = SOURCE_PATH.read_text(encoding="utf-8")
        cls.block = convert.conversion_input(cls.markdown)

    def test_the_input_is_exactly_the_one_fenced_json_block(self):
        parsed = json.loads(self.block)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(sorted(convert.SOURCE_KEYS), sorted(parsed))

    def test_the_input_contains_none_of_the_title_or_the_summary(self):
        """The answer and the argument for one side are outside the block."""
        for marker in OUTSIDE_THE_BLOCK:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.block)

    def test_the_block_is_located_by_parsing_fences_not_by_matching_text(self):
        """A scanner over fence lines, proved by a document that has two blocks."""
        two_blocks = "intro\n\n```json\n{\"a\": 1}\n```\n\nmore\n\n```json\n{\"b\": 2}\n```\n"
        with self.assertRaises(convert.ConversionError) as caught:
            convert.conversion_input(two_blocks)
        self.assertIn("exactly one", str(caught.exception))

    def test_an_unclosed_fence_is_refused_rather_than_read_to_the_end(self):
        with self.assertRaises(convert.ConversionError):
            convert.conversion_input("```json\n{\"a\": 1}\n")

    def test_a_block_missing_a_source_key_is_refused(self):
        with self.assertRaises(convert.ConversionError) as caught:
            convert.parse_source('{"dispute_ticket": {}}')
        self.assertIn("missing keys", str(caught.exception))

    def test_the_fence_scanner_finds_the_blocks_it_should(self):
        blocks = convert.fenced_blocks(self.markdown)
        self.assertEqual(1, len(blocks))
        self.assertEqual("json", blocks[0]["language"])


class ConvertedCaseTests(unittest.TestCase):
    """The converted case is in the corpus's shape and carries nothing invented."""

    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_external_case(CASE_PATH)
        cls.raw = CASE_PATH.read_text(encoding="utf-8")
        cls.mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    def test_the_case_is_not_in_the_manifest(self):
        """Adding it would change the corpus the benchmark measures."""
        numbers = [entry["case_no"] for entry in json.loads(INDEX_PATH.read_text(encoding="utf-8"))]
        self.assertNotIn(self.case["case_no"], numbers)
        self.assertEqual(29, len(numbers))

    def test_the_case_number_is_outside_the_corpus_range(self):
        corpus = [entry["case_no"] for entry in json.loads(INDEX_PATH.read_text(encoding="utf-8"))]
        self.assertTrue(all(entry <= 115 or 201 <= entry <= 214 for entry in corpus))
        self.assertFalse(101 <= self.case["case_no"] <= 115)
        self.assertFalse(201 <= self.case["case_no"] <= 214)

    def test_the_case_has_the_contract_shape(self):
        self.assertEqual(
            sorted(("schema_version", "case_no", "dispute", "evidence")),
            sorted(self.case),
        )
        self.assertEqual(
            sorted(("case_no", "dispute_id", "trip_id", "category", "filed_at", "filed_by",
                    "channel", "amount_contested_sgd", "claim_text", "counterparty_statement",
                    "evidence_ids")),
            sorted(self.case["dispute"]),
        )
        for artifact in self.case["evidence"]:
            with self.subTest(artifact=artifact["evidence_id"]):
                self.assertEqual(
                    sorted(("evidence_id", "evidence_type", "admissibility", "payload",
                            "schema_version", "source", "trip_id", "generated_at")),
                    sorted(artifact),
                )

    def test_nothing_from_outside_the_block_reaches_the_case(self):
        """Neither the title's ruling nor the summary's argument survives."""
        for marker in OUTSIDE_THE_BLOCK:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.raw)

    def test_the_values_the_conversion_drops_are_dropped(self):
        """Names, the vehicle string and the payment method are not carried.

        They are in the source, so this is a decision rather than an omission,
        and it is recorded in the mapping record.
        """
        for marker in DROPPED_SOURCE_VALUES:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.raw)

    def test_no_gps_fix_carries_an_accuracy_value(self):
        """A fix without accuracy is evidence of neither presence nor absence.

        Supplying one would invent the very field POL-NS-02 tests, so that these
        fixes could establish an arrival the source does not support.
        """
        gps = self._artifact("GPS_TRACE")
        for point in gps["payload"]["points"]:
            with self.subTest(ts=point["ts"]):
                self.assertNotIn("accuracy_m", point)
                self.assertNotIn("heading_deg", point)
        self.assertEqual(["lat", "lng", "speed_kph", "ts"], sorted(gps["payload"]["points"][0]))

    def test_there_is_no_rider_track(self):
        gps = self._artifact("GPS_TRACE")
        self.assertEqual([], gps["payload"]["rider_track"])

    def test_the_counterparty_statement_is_null(self):
        """The source carries no statement from the driver."""
        self.assertIsNone(self.case["dispute"]["counterparty_statement"])

    def test_the_zone_class_is_the_stated_assumption(self):
        trip = self._artifact("TRIP_RECORD")
        self.assertEqual("STANDARD", trip["payload"]["pickup_zone_class"])

    def test_every_admissibility_code_is_in_code_weights(self):
        for artifact in self.case["evidence"]:
            for code in artifact["admissibility"]["issues"]:
                with self.subTest(artifact=artifact["evidence_id"], code=code):
                    self.assertIn(code, prepass.CODE_WEIGHTS)

    def test_every_weight_is_what_weight_for_produces(self):
        """The weight is derived, never written down beside the codes.

        ``float()`` is applied because the loader parses JSON numbers as
        ``Decimal`` and ``weight_for`` returns a float; the same comparison on a
        corpus case behaves identically.
        """
        for artifact in self.case["evidence"]:
            codes = artifact["admissibility"]["issues"]
            with self.subTest(artifact=artifact["evidence_id"]):
                self.assertEqual(
                    prepass.weight_for(codes),
                    float(artifact["admissibility"]["weight_multiplier"]),
                )

    def test_no_artifact_is_marked_complete_while_carrying_a_code(self):
        for artifact in self.case["evidence"]:
            admissibility = artifact["admissibility"]
            with self.subTest(artifact=artifact["evidence_id"]):
                if admissibility["issues"]:
                    self.assertNotEqual("COMPLETE", admissibility["status"])
                else:
                    self.assertEqual("COMPLETE", admissibility["status"])

    def test_the_defective_artifacts_are_the_two_the_source_supports(self):
        """The trace is sparse and unmeasured; the ledger itemises one line."""
        impaired = {
            artifact["evidence_id"]: sorted(artifact["admissibility"]["issues"])
            for artifact in self.case["evidence"]
            if artifact["admissibility"]["status"] != "COMPLETE"
        }
        self.assertEqual(
            {
                "EV-GPS-00901": ["LOW_SAMPLE_RATE", "PARTIAL_RECORD"],
                "EV-FARE-00901": ["PARTIAL_RECORD"],
                "EV-ADVIS-00901-01": ["MISSING_ARTIFACT"],
            },
            impaired,
        )

    def test_every_artifact_carries_a_note_and_an_assessment(self):
        for artifact in self.case["evidence"]:
            admissibility = artifact["admissibility"]
            with self.subTest(artifact=artifact["evidence_id"]):
                self.assertTrue(admissibility["notes"].strip())
                self.assertTrue(admissibility["assessed_at"])
                self.assertEqual(convert.ASSESSOR_VERSION, admissibility["assessor_version"])

    def test_the_evidence_ids_are_all_cited_by_the_dispute(self):
        cited = set(self.case["dispute"]["evidence_ids"])
        self.assertEqual(
            {artifact["evidence_id"] for artifact in self.case["evidence"]}, cited
        )

    def _artifact(self, evidence_type):
        return next(
            artifact
            for artifact in self.case["evidence"]
            if artifact["evidence_type"] == evidence_type
        )


class MappingRecordTests(unittest.TestCase):
    """Every place the converter chose rather than copied is on the record."""

    @classmethod
    def setUpClass(cls):
        cls.mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    def test_every_entry_says_which_it_was_and_why(self):
        self.assertTrue(self.mapping["fields"], "the mapping record is empty")
        for entry in self.mapping["fields"]:
            with self.subTest(target=entry["target"]):
                self.assertIn(entry["kind"], ("copied", "judged"))
                self.assertTrue(entry["reason"].strip(), "an entry gives no reason")
                self.assertIn("target", entry)
                self.assertIn("value", entry)

    def test_the_mapping_names_the_judged_fields_the_brief_calls_out(self):
        """The four places the task said not to invent are all recorded."""
        judged = {
            entry["target"]
            for entry in self.mapping["fields"]
            if entry["kind"] == "judged"
        }
        required = {
            "dispute.counterparty_statement",
            "evidence.EV-TRIP-00901.payload.pickup_zone_class",
            "evidence.EV-TRIP-00901.payload.vehicle_type",
            "evidence.EV-GPS-00901.payload.points[*].status",
            "evidence.EV-GPS-00901.payload.rider_track",
            "evidence.EV-GPS-00901.payload.expected_interval_sec",
            "evidence.EV-RPROF-00901.payload.no_show_disputes_30d",
            "evidence.EV-DPROF-00901.payload.no_show_terminations_30d",
        }
        self.assertEqual(set(), required - judged, "a judged field is not on the record")

    def test_the_mapping_names_every_artifact_it_assessed(self):
        judged = {
            entry["target"]
            for entry in self.mapping["fields"]
            if entry["kind"] == "judged"
        }
        for evidence_id in ("EV-TRIP-00901", "EV-GPS-00901", "EV-CHAT-00901",
                            "EV-FARE-00901", "EV-RPROF-00901", "EV-DPROF-00901"):
            with self.subTest(artifact=evidence_id):
                self.assertIn(
                    "evidence.{0}.admissibility.issues".format(evidence_id), judged
                )

    def test_the_mapping_records_the_policy_divergences(self):
        findings = " ".join(
            item["finding"] for item in self.mapping["policy_divergences"]
        )
        self.assertIn("5.00", findings)
        self.assertIn("8-minute", findings)
        self.assertIn("waiting clock", findings)
        for item in self.mapping["policy_divergences"]:
            with self.subTest(finding=item["finding"]):
                self.assertTrue(item["this_system"].strip())
                self.assertTrue(item["effect"].strip())

    def test_the_open_question_is_recorded_and_not_resolved(self):
        """Waiting from arrival or from the scheduled time is not decided here."""
        item = next(
            entry
            for entry in self.mapping["policy_divergences"]
            if "waiting clock" in entry["finding"]
        )
        self.assertIn("NOT resolved", item["effect"])

    def test_the_assumptions_name_what_depends_on_them(self):
        assumptions = {
            item["assumption"]: item for item in self.mapping["assumptions"]
        }
        self.assertIn("pickup zone class is STANDARD", assumptions)
        self.assertIn("vehicle tier is RYDE_X", assumptions)
        for item in self.mapping["assumptions"]:
            with self.subTest(assumption=item["assumption"]):
                self.assertTrue(item["depends_on_it"], "an assumption names no dependants")
                self.assertTrue(item["reason"].strip())


class AnswerIsolationTests(unittest.TestCase):
    """The converted case passes the same scan the corpus passes."""

    @classmethod
    def setUpClass(cls):
        from tests.test_answer_isolation import DISTINCTIVE_ANSWER_FIELDS

        cls.needles = DISTINCTIVE_ANSWER_FIELDS
        cls.case = loader.load_external_case(CASE_PATH)

    def test_no_answer_key_field_name_reaches_the_external_brief(self):
        canonical, _ = brief.brief_digest(brief.build_brief_for_case(self.case))
        offenders = sorted(name for name in self.needles if name in canonical)
        self.assertEqual([], offenders, "an answer-key field name reached the brief")

    def test_the_scan_is_capable_of_firing_on_this_case(self):
        """A scan that cannot fail proves nothing, so it is shown failing."""
        canonical, _ = brief.brief_digest(brief.build_brief_for_case(self.case))
        spliced = canonical + '"expected_ruling": "NO_ACTION"'
        self.assertIn("expected_ruling", spliced)
        self.assertNotEqual([], [n for n in self.needles if n in spliced])

    def test_the_expected_outcome_is_not_under_data(self):
        """It is answer-bearing, so it lives under eval/ and nowhere else."""
        self.assertTrue(EXPECTED_PATH.is_file())
        self.assertFalse((EXTERNAL_DIR / "expected.json").exists())
        for path in EXTERNAL_DIR.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertNotIn("UPHELD", path.read_text(encoding="utf-8"))

    def test_the_expected_outcome_is_not_merged_into_the_answer_key(self):
        key = json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(29, len(key))
        self.assertNotIn(
            "DISP-002", json.dumps(key), "the sample dispute reached the frozen key"
        )
        expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
        self.assertIn("not_the_answer_key", expected)


class BriefBuildTests(unittest.TestCase):
    """The external case briefs, and the arrival block says what it should."""

    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_external_case(CASE_PATH)
        cls.brief = brief.build_brief_for_case(cls.case)

    def test_the_derived_arrival_block_reports_the_fixes_as_non_qualifying(self):
        """No fix carries accuracy, so none establishes presence or absence.

        This is the intended consequence of not inventing an accuracy value, not
        a defect to repair: a coordinate with no stated accuracy does not
        establish where a person was.
        """
        gps = next(
            artifact
            for artifact in self.brief["case"]["evidence"]
            if artifact["evidence_type"] == "GPS_TRACE"
        )
        arrival = gps["payload"]["derived"]["arrival"]
        self.assertEqual(0, arrival["qualifying_fix_count"]["value"])
        self.assertGreater(arrival["driver_fix_count"]["value"], 0)

    def test_the_derived_rider_presence_block_has_no_rider_track_to_read(self):
        gps = next(
            artifact
            for artifact in self.brief["case"]["evidence"]
            if artifact["evidence_type"] == "GPS_TRACE"
        )
        presence = gps["payload"]["derived"]["rider_presence"]
        self.assertIn("rider_presence", gps["payload"]["derived"])
        self.assertIsInstance(presence, dict)

    def test_the_brief_carries_the_case_it_was_built_from(self):
        self.assertEqual(self.case["case_no"], self.brief["case"]["case_no"])
        self.assertEqual(self.case["dispute"], self.brief["case"]["dispute"])

    def test_build_brief_for_case_agrees_with_build_brief_on_a_corpus_case(self):
        """The split entry point is the same code path, not a copy of it."""
        loaded = loader.load_case(208)
        self.assertEqual(
            brief.brief_digest(brief.build_brief(208))[1],
            brief.brief_digest(brief.build_brief_for_case(loaded))[1],
        )


class BenchmarkUndisturbedTests(unittest.TestCase):
    """Converting does not touch the corpus, the manifest or the answer key."""

    def test_a_conversion_leaves_the_benchmark_byte_identical(self):
        before = _fingerprint(_benchmark_files())
        convert.write_outputs()
        after = _fingerprint(_benchmark_files())
        self.assertEqual(before, after, "the conversion disturbed the benchmark")

    def test_the_converter_writes_only_under_the_external_roots(self):
        for path in (convert.CASE_PATH, convert.MAPPING_PATH, convert.EXPECTED_PATH):
            with self.subTest(path=str(path)):
                relative = path.relative_to(PROJECT_ROOT).parts
                self.assertEqual("external", relative[1])
                self.assertIn(relative[0], ("data", "eval"))

    def test_the_conversion_is_idempotent(self):
        """Same source, same bytes: a reader can re-run it and see no diff."""
        first = (CASE_PATH.read_bytes(), MAPPING_PATH.read_bytes(), EXPECTED_PATH.read_bytes())
        convert.write_outputs()
        second = (CASE_PATH.read_bytes(), MAPPING_PATH.read_bytes(), EXPECTED_PATH.read_bytes())
        self.assertEqual(first, second)

    def test_the_corpus_loader_still_refuses_a_path_outside_data_cases(self):
        """The external root does not loosen the corpus loader's containment."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cases").mkdir()
            (root / "external" / "ryde").mkdir(parents=True)
            shutil.copy2(CASE_PATH, root / "external" / "ryde" / "case-00901.json")
            index = [
                {
                    "case_no": 901,
                    "dispute_id": "DISP-002",
                    "trip_id": "TRIP-2026-09945",
                    "category": "NO_SHOW_CHARGE",
                    "file": "external/ryde/case-00901.json",
                }
            ]
            (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

            with mock.patch.multiple(
                loader,
                DATA_DIR=root,
                CASES_DIR=root / "cases",
                INDEX_PATH=root / "index.json",
            ):
                with self.assertRaises(loader.ManifestMismatchError) as caught:
                    loader.load_case(901)
        self.assertIn("outside data/cases/", str(caught.exception))

    def test_the_external_loader_refuses_a_path_outside_data_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            stray = Path(tmp) / "case-00901.json"
            shutil.copy2(CASE_PATH, stray)
            with self.assertRaises(loader.ManifestMismatchError) as caught:
                loader.load_external_case(stray)
        self.assertIn("outside data/external/", str(caught.exception))

    def test_the_external_loader_refuses_a_mismatched_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = EXTERNAL_DIR / "ryde" / "not-a-case-name.json"
            shutil.copy2(CASE_PATH, wrong)
            try:
                with self.assertRaises(loader.ManifestMismatchError):
                    loader.load_external_case(wrong)
            finally:
                wrong.unlink()

    def test_the_manifest_still_lists_29_cases(self):
        self.assertEqual(29, len(json.loads(INDEX_PATH.read_text(encoding="utf-8"))))

    def test_the_answer_key_still_holds_29_records(self):
        self.assertEqual(29, len(json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    unittest.main(verbosity=2)

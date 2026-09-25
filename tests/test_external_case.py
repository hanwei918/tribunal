"""Tests for the converted external case (DISP-002) and the converter.

The organisers' sample case is answer-bearing: its title states an expected
ruling and its Evidence Summary argues for one side. Only the fenced JSON block
inside it is case material, and the whole point of these tests is that the other
two parts cannot reach the converted case.

Five properties, in the order they matter:

* **The converter reads exactly the block.** Its input is located by parsing the
  Markdown fences, and the parse is required to find exactly one block.
* **Nothing from the title or the summary survives.** Asserted against the
  converted case's own bytes, not against the converter's intentions.
* **Nothing was invented.** No fix carries an accuracy value, there is no rider
  track, no admissibility code is outside ``CODE_WEIGHTS``, and every weight is
  what ``prepass.weight_for`` produces for the codes beside it.
* **Nothing is dropped in silence.** Every item in the block is either carried
  into the converted case or recorded in the mapping with the reason it is not,
  and the converter refuses to write a mapping that fails that. The one item
  that was neither -- the source's account of how the arrival marker was made --
  is now carried, and carried as what it is.
* **The benchmark is undisturbed.** The corpus, the manifest and the answer key
  are byte-identical across a conversion, and the corpus loader still refuses a
  manifest entry that points outside ``data/cases/``.

No network, no browser. Run with ``python -m unittest discover -s tests -v``.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
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

from eval import run_benchmark as runner  # noqa: E402
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

# The one committed run of the converted case. It is read by the summary test
# below, which checks the printed fields against the artifact's own values: the
# defect it guards against was a property of this stored shape, not of a
# scripted one.
EXTERNAL_RESULT_PATH = (
    PROJECT_ROOT / "runs" / "external" / "ryde" / "case-00901.json"
)

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

    def test_the_trace_note_counts_the_gaps_the_payload_lists(self):
        """The note's fraction and the payload's own list are the same count.

        They disagreed. The note said three of the seven intervals exceeded
        POL-NS-08(b)'s 120 s limb while ``payload.gaps`` held five, and the
        mapping repeated the typed figure. Both counts are now derived from the
        list of intervals, and this reads the rendered artifact back to check
        that what it says and what it carries agree.
        """
        gps = self._artifact("GPS_TRACE")
        expected = "{0} of the {1} exceed".format(
            len(gps["payload"]["gaps"]), len(gps["payload"]["points"]) - 1
        )
        self.assertIn(expected, gps["admissibility"]["notes"])
        entry = next(
            item
            for item in self.mapping["fields"]
            if item["target"] == "evidence.EV-GPS-00901.payload.gaps"
        )
        self.assertIn(expected, entry["reason"])

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


class SourceCoverageTests(unittest.TestCase):
    """Nothing in the source is dropped in silence.

    The converter's contract is that every item in the fenced block is either
    carried into the converted case or recorded in the mapping record with the
    reason it is not. A drop is a decision, and a decision that leaves no trace
    is indistinguishable from an oversight -- which is what happened here. The
    source's ``driver_arrived`` details are the one record that says the arrival
    marker was auto-confirmed from a GPS measurement, and they were in neither
    the case nor the mapping.

    The check is the converter's own, ``unrecorded_items``, rather than a second
    implementation in the test: a test that re-derived the answer could agree
    with a converter that was wrong in the same way.
    """

    @classmethod
    def setUpClass(cls):
        cls.block = convert.conversion_input(SOURCE_PATH.read_text(encoding="utf-8"))
        cls.source = convert.parse_source(cls.block)
        cls.case = loader.load_external_case(CASE_PATH)
        cls.mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    def test_every_source_item_is_carried_or_recorded(self):
        self.assertEqual([], convert.unrecorded_items(self.source, self.mapping))

    def test_the_walk_finds_the_items_the_source_actually_has(self):
        """A walk that found nothing would satisfy the check above vacuously.

        The count is a literal because the source is a fixed document: an item
        added to it should show up here rather than pass unnoticed.
        """
        items = convert.source_items(self.source)
        self.assertEqual(86, len(items))
        # One of each shape, so a walk that stopped at the top level fails here.
        for path in (
            "dispute_ticket.filed_at",
            "rider_profile.dispute_history.upheld",
            "trip_data.pickup_location.lat",
            "gps_telemetry[*].status",
            "chat_logs[*].content",
            "cancellation_policy.fee_goes_to",
            "app_events[driver_arrived].details",
        ):
            with self.subTest(path=path):
                self.assertIn(path, items)

    def test_the_check_fails_when_an_item_is_left_unrecorded(self):
        """Falsifiability, on the item that was actually dropped.

        Every entry that names the path is removed, which is what the check
        itself asks: the item is recorded once by the trip record and again by
        the per-event audit, and leaving either one standing would be a record.
        """
        stripped = {
            "fields": [
                entry
                for entry in self.mapping["fields"]
                if "app_events[driver_arrived].details"
                not in [part.strip() for part in (entry.get("source") or "").split(",")]
            ]
        }
        self.assertIn(
            "app_events[driver_arrived].details",
            convert.unrecorded_items(self.source, stripped),
        )

    def test_the_writer_refuses_a_mapping_that_drops_an_item(self):
        """The guard is at the write, not only in this file.

        A mapping with a hole in it is wrong the moment it is written, so the
        refusal is checked where it happens. It fires before the output
        directory is created, so this writes nothing.
        """
        with mock.patch.object(
            convert, "convert", return_value=(self.case, {"fields": []})
        ):
            with self.assertRaises(convert.ConversionError) as caught:
                convert.write_outputs()
        self.assertIn("neither carried nor recorded", str(caught.exception))

    # -- the record that was dropped, and what carrying it means ------------
    def test_the_auto_arrival_claim_is_carried_verbatim(self):
        """The dropped text is now in the trip record's admissibility notes."""
        arrival = self._event("driver_arrived")
        self.assertIn(arrival["details"], self._trip()["admissibility"]["notes"])

    def test_the_auto_arrival_claim_is_carried_as_what_it_is(self):
        """Labelled: a platform distance claim, not a reported accuracy.

        "Within 10m" is a distance the platform reports between two things it
        measured. It is not a horizontal accuracy the device reported, and the
        difference is the whole of POL-NS-02: writing it into an accuracy field
        would invent the very value that clause tests.
        """
        notes = self._trip()["admissibility"]["notes"]
        self.assertIn("distance claim", notes)
        self.assertIn("a reported horizontal accuracy", notes)
        self.assertIn("measurable under POL-NS-02", notes)

    def test_the_auto_arrival_claim_became_neither_a_fix_nor_an_accuracy(self):
        """It is a statement about the record, and it stays one."""
        gps = self._artifact("GPS_TRACE")
        self.assertEqual(
            len(self.source["gps_telemetry"]), gps["payload"]["point_count"]
        )
        self.assertEqual(len(self.source["gps_telemetry"]), len(gps["payload"]["points"]))
        for point in gps["payload"]["points"]:
            with self.subTest(ts=point["ts"]):
                self.assertNotIn("accuracy_m", point)

    def test_the_independence_consequence_is_recorded(self):
        """The marker and the trace are one measurement, so one carrier.

        This is the fact a reader needs and would not otherwise have: the source
        states that the arrival marker was produced from the GPS reading, so the
        trip record and the trace corroborate nothing. Both the case and the
        mapping say so.
        """
        self.assertIn("one carrier", self._trip()["admissibility"]["notes"])
        entry = next(
            item
            for item in self.mapping["fields"]
            if item.get("source") == "app_events[driver_arrived].details"
        )
        self.assertIn("ONE carrier", entry["reason"])
        self.assertEqual("judged", entry["kind"])

    # -- the rest of the block, item by item -------------------------------
    def test_every_app_event_is_recorded_one_by_one(self):
        """A wildcard entry would hide an event nobody read."""
        for event in self.source["app_events"]:
            kind = event["event_type"]
            with self.subTest(event=kind):
                entry = next(
                    (
                        item
                        for item in self.mapping["fields"]
                        if item["target"] == "app_events[{0}]".format(kind)
                    ),
                    None,
                )
                self.assertIsNotNone(entry, "the event is not on the record")
                for field in ("timestamp", "event_type", "details"):
                    self.assertIn("app_events[{0}].{1}".format(kind, field), entry["source"])

    def test_every_app_event_type_has_a_disposition(self):
        kinds = {event["event_type"] for event in self.source["app_events"]}
        self.assertEqual(set(), kinds - set(convert._APP_EVENT_DISPOSITION))

    def test_an_unrecognised_app_event_is_refused_rather_than_dropped(self):
        """A source that grew an event must not lose it quietly."""
        source = json.loads(self.block)
        source["app_events"].append(
            {
                "timestamp": "2026-09-13T08:51:10+08:00",
                "event_type": "something_this_converter_has_never_seen",
                "details": "Not an event this converter knows what to do with.",
            }
        )
        with self.assertRaises(convert.ConversionError) as caught:
            convert.convert(json.dumps(source))
        self.assertIn("something_this_converter_has_never_seen", str(caught.exception))

    def test_the_source_policy_block_is_recorded_as_dropped(self):
        """The source's own policy is not this system's, and that is recorded."""
        sources = {entry.get("source") for entry in self.mapping["fields"]}
        for field in self.source["cancellation_policy"]:
            with self.subTest(field=field):
                self.assertIn("cancellation_policy." + field, sources)

    def test_the_records_that_are_read_and_not_carried_say_which_they_are(self):
        """A drop and a read-but-not-carried are both decisions, both stated."""
        for path in (
            "trip_data.scheduled_time",
            "chat_logs[*].type",
            "rider_profile.fraud_flag_details",
            "driver_profile.name",
            "driver_profile.dispute_history.rejected",
        ):
            with self.subTest(path=path):
                entry = next(
                    item for item in self.mapping["fields"] if item.get("source") == path
                )
                self.assertEqual("judged", entry["kind"])
                self.assertTrue(entry["reason"].strip())

    # -- helpers -----------------------------------------------------------
    def _artifact(self, evidence_type):
        return next(
            artifact
            for artifact in self.case["evidence"]
            if artifact["evidence_type"] == evidence_type
        )

    def _trip(self):
        return self._artifact("TRIP_RECORD")

    def _event(self, event_type):
        return next(
            event
            for event in self.source["app_events"]
            if event["event_type"] == event_type
        )


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


class ExternalRunTests(unittest.TestCase):
    """An external case runs through the same machinery, into its own place.

    The transport is the one the corpus runner's own tests use, so "the same
    guards" is checked with the same instrument that checks them for a corpus
    case, rather than with a second fake written to agree with a second
    implementation.
    """

    # A ruling in the shape POL-GEN-03 asks for, produced by the scripted
    # transport rather than by a model. It is never compared with the
    # organisers' expectation: an external case has no answer-key entry to
    # compare against, and inventing one would put a case into the frozen key
    # that the key does not measure.
    RULING = {
        "ruling": "DRIVER_COMPENSATION",
        "amount_sgd": None,
        "driver_compensation_sgd": 4.0,
        "referrals": [],
        "confidence": 0.82,
        "explanation": "Produced by a scripted transport; no model was called.",
    }

    def setUp(self):
        from tests.test_run_benchmark import (  # noqa: PLC0415 - one shared fake
            MODEL,
            ScriptedTransport,
            client_factory,
            git_runner,
        )

        self.model = MODEL
        self.transport = ScriptedTransport({901: {"ruling": self.RULING}})
        self.factory = client_factory(MODEL, self.transport)
        self.git_runner = git_runner

    def _run(self, runs_dir, **overrides):
        kwargs = {
            "runs_dir": Path(runs_dir),
            "client_factory": self.factory,
            "git_runner": self.git_runner,
            "progress": lambda text: None,
            # One judge draft, as every run before the vote used.
            "judge_votes": 1,
        }
        kwargs.update(overrides)
        return runner.run_external_case(CASE_PATH, self.model, **kwargs)

    # -- where it is written ----------------------------------------------
    def test_the_run_lands_under_runs_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            # run_dir comes back resolved, and on macOS the temporary root is
            # reached through a symlink, so the comparison is made resolved too.
            self.assertEqual("external", run_dir.parent.name)
            self.assertEqual("ryde", run_dir.name)
            self.assertTrue(run_dir.is_relative_to(Path(tmp).resolve()))
            self.assertTrue(run_dir.is_dir())

    def test_the_guard_refuses_a_model_run_directory(self):
        """The headline directory holds the 29-case result the submission reports."""
        with tempfile.TemporaryDirectory() as tmp:
            headline = Path(tmp) / "deepseek-deepseek-flash"
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.assert_external_run_directory(headline, Path(tmp))
        self.assertIn("runs/external/", str(caught.exception))

    def test_an_external_run_leaves_a_headline_directory_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            headline = runs_dir / "deepseek-deepseek-flash"
            headline.mkdir()
            sentinel = headline / "case-00208.json"
            sentinel.write_text('{"case_no": 208}\n', encoding="utf-8")
            before = (sentinel.read_bytes(), sorted(p.name for p in headline.iterdir()))

            self._run(runs_dir)

            after = (sentinel.read_bytes(), sorted(p.name for p in headline.iterdir()))
            self.assertEqual(before, after, "the headline run directory was disturbed")
            self.assertFalse((headline / "case-00901.json").exists())

    # -- the guards, which are the corpus runner's -------------------------
    def test_the_case_is_arbitrated_by_the_same_pipeline(self):
        """Both advocates, then the judge, in that order -- as for any case."""
        with tempfile.TemporaryDirectory() as tmp:
            outcome, run_dir = self._run(tmp)
            self.assertEqual("completed", outcome.status)
            self.assertEqual(
                ["RIDER_ADVOCATE", "DRIVER_ADVOCATE", "JUDGE"],
                self.transport.roles_for(901),
            )
            self.assertTrue((run_dir / "case-00901.json").is_file())
            self.assertTrue((run_dir / "case-00901.transcript.json").is_file())

    def test_the_brief_identity_proof_holds_for_the_external_case(self):
        """One brief, one serialisation, both advocates handed those bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)

            document = json.loads(
                (run_dir / "case-00901.json").read_text(encoding="utf-8")
            )
            transcript = json.loads(
                (run_dir / "case-00901.transcript.json").read_text(encoding="utf-8")
            )
            by_role = {entry["role"]: entry for entry in transcript["entries"]}
            rider = by_role["RIDER_ADVOCATE"]
            driver = by_role["DRIVER_ADVOCATE"]

            self.assertEqual(rider["user_sha256"], driver["user_sha256"])
            self.assertEqual(rider["user_sha256"], document["brief_sha256"])
            self.assertEqual(driver["user_sha256"], document["brief_sha256"])
            self.assertNotEqual(rider["system_sha256"], driver["system_sha256"])

            # And the brief those bytes are is the one this repository builds for
            # the external case, not some other case's.
            case = loader.load_external_case(CASE_PATH)
            self.assertEqual(
                brief.brief_digest(brief.build_brief_for_case(case))[1],
                document["brief_sha256"],
            )

    def test_the_stance_only_check_ran(self):
        from tribunal import pipeline

        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            document = json.loads(
                (run_dir / "case-00901.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [list(item) for item in pipeline.check_stance_only_difference()],
                document["stance_differing_ranges"],
            )

    def test_the_cache_entry_carries_provenance_and_the_token_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            document = json.loads(
                (run_dir / "case-00901.json").read_text(encoding="utf-8")
            )

            for field in (
                "schema_version", "case_no", "model", "recorded_at", "brief_sha256",
                "git_commit", "prompts_sha256", "python_version", "transcript_sha256",
                "transcript_file", "ruling", "ruling_findings",
                "stance_differing_ranges", "tokens", "wall_seconds", "call_seconds",
                "matched",
            ):
                with self.subTest(field=field):
                    self.assertIn(field, document)

            self.assertEqual(901, document["case_no"])
            self.assertGreater(document["tokens"]["prompt_tokens"], 0)
            self.assertGreater(document["tokens"]["completion_tokens"], 0)

    def test_the_run_metadata_says_it_is_external_and_ungraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

            self.assertTrue(metadata["external"])
            self.assertFalse(metadata["graded"])
            self.assertEqual([901], metadata["cases"])
            self.assertIn("answer_key_sha256", metadata)
            self.assertIn("prompts_sha256", metadata)

    def test_the_calls_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            calls = json.loads((run_dir / "calls.json").read_text(encoding="utf-8"))
        self.assertIsInstance(calls, list)
        self.assertGreaterEqual(len(calls), 3)

    # -- no score ----------------------------------------------------------
    def test_no_four_field_score_is_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp)
            document = json.loads(
                (run_dir / "case-00901.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(
                document["matched"],
                "an external case was scored against a key that has no entry for it",
            )

    def test_the_answer_key_has_no_entry_for_the_external_case(self):
        key = json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))
        self.assertNotIn(901, [record["case_no"] for record in key])

    def test_the_ruling_is_printed_beside_the_stated_expectation(self):
        printed = []
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, progress=printed.append)
        text = "\n".join(printed)

        self.assertIn("DRIVER_COMPENSATION", text)
        self.assertIn("Cancellation charge UPHELD", text)
        self.assertIn("NOT A VERIFIED ANSWER", text)
        self.assertIn("no four-field grade is computed", text)
        self.assertIn("case 901", text)

    def test_the_stated_expectation_is_read_from_under_eval(self):
        expected = runner.read_expected_outcome()
        self.assertIsNotNone(expected, "eval/external/ryde/expected.json is missing")
        self.assertIn("not_the_answer_key", expected)
        self.assertEqual("DISP-002", expected["dispute_id"])

    def test_a_ruling_of_the_stored_shape_prints_its_own_four_fields(self):
        """The stored result nests the four fields, and the printer must go in.

        ``case-00901.json`` holds the result object the judge returns --
        ``{"discarded_claims": [...], "ruling": {...}}`` -- so ``amount_sgd``,
        ``driver_compensation_sgd``, ``referrals`` and ``confidence`` are one
        level down from the object the printer is handed. The printer read them
        off the outer object, where they do not exist, and printed ``None`` for
        all four while still printing ``PARTIAL_REFUND``. Asserting the ruling
        word therefore proves nothing, which is why the existing test above did
        not catch it; this one reads the four values back out of the printed
        summary and compares each with the committed artifact's own value.

        Both sides are read from the artifact rather than typed, so this cannot
        pass by the printer and the expectation being wrong together. The
        artifact is the committed run, not a scripted one, because the defect
        was a property of the real stored shape.
        """
        stored = json.loads(EXTERNAL_RESULT_PATH.read_text(encoding="utf-8"))
        inner = stored["ruling"]["ruling"]

        outcome = runner.CaseOutcome(
            case_no=901,
            status=runner.STATUS_COMPLETED,
            ruling=stored["ruling"],
            tokens=runner.TokenSplit.from_mapping(stored["tokens"]),
            wall_seconds=stored["wall_seconds"],
        )
        text = runner.format_external_result(
            outcome, loader.load_external_case(CASE_PATH), None, Path("runs/external/ryde")
        )

        # The summary prints two labels on one line and aligns the rest with
        # spaces, so a value is read as what follows its label, cut at the run
        # of spaces that introduces the next label on that line.
        def printed_value(label):
            for line in text.splitlines():
                stripped = line.strip()
                at = stripped.find(label)
                if at == -1:
                    continue
                remainder = (
                    stripped[at + len(label) :].lstrip().lstrip(":").strip()
                )
                return remainder.split("   ")[0].strip()
            return None

        for label in (
            "amount_sgd",
            "driver_compensation_sgd",
            "referrals",
            "confidence",
        ):
            with self.subTest(label=label):
                self.assertEqual(str(inner[label]), printed_value(label))
        self.assertEqual(
            "ruling {0}".format(inner["ruling"]), printed_value("produced")
        )

    # -- the CLI -----------------------------------------------------------
    def test_the_cli_writes_only_under_runs_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            with mock.patch.object(
                runner, "_default_client_factory", return_value=self.factory
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = runner.main(
                        [
                            "--external", str(CASE_PATH),
                            "--runs-dir", str(runs_dir),
                            "--model", self.model,
                        ]
                    )
            written = sorted(
                path.relative_to(runs_dir).as_posix()
                for path in runs_dir.rglob("*")
                if path.is_file()
            )

        self.assertEqual(0, code)
        self.assertTrue(written, "the external run wrote nothing")
        for name in written:
            with self.subTest(path=name):
                self.assertTrue(
                    name.startswith("external/"),
                    "an external run wrote outside runs/external/: {0}".format(name),
                )

    def test_the_cli_refuses_to_mix_external_with_the_corpus_selection(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                runner.main(["--external", str(CASE_PATH), "--cases", "208"])

    def test_the_cli_refuses_compare_with_external(self):
        """``--compare`` reads cached runs; ``--external`` runs a case."""
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(io.StringIO()):
                runner.main(["--compare", "--external", str(CASE_PATH)])
        self.assertEqual(2, caught.exception.code)

    def test_the_cli_exits_non_zero_when_it_cannot_run_the_case(self):
        """A caller in a shell has to be able to tell, so the code is pinned.

        Both of these fail before a client is built, so neither reaches the
        network: the first resolves outside ``data/external/`` and the second is
        not there at all. The exit code is what a script reads, and it is not
        implied by the message being printed.
        """
        for argv, expected in (
            (["--external", "/etc/passwd"], 1),
            (["--external", "data/external/ryde/does-not-exist.json"], 1),
        ):
            with self.subTest(argv=argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()):
                        code = runner.main(argv + ["--model", self.model])
                self.assertEqual(expected, code)

    def test_the_compare_path_still_works(self):
        """The edit to main added guards beside --compare; it must still run."""
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = runner.main(["--compare"])
        self.assertEqual(0, code)
        self.assertIn("deepseek/deepseek-flash", out.getvalue())

    # -- the token budget, which is the corpus runner's --------------------
    def test_a_budget_that_cannot_cover_the_case_is_refused_not_ignored(self):
        """The corpus runner would issue nothing on a spent budget.

        There is no later case here for the budget to be saved for, so running
        the case anyway and ignoring the flag would be the one thing worse than
        refusing: it would look as though the budget had been applied.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError) as caught:
                self._run(tmp, token_budget=0)
            self.assertIn("token budget of 0", str(caught.exception))
            self.assertFalse(
                (Path(tmp) / "external").exists(),
                "the run directory was created before the budget was checked",
            )
            self.assertEqual(0, self.transport.calls(), "a call was made anyway")

    def test_a_negative_budget_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError) as caught:
                self._run(tmp, token_budget=-1)
        self.assertIn("cannot be negative", str(caught.exception))

    def test_a_budget_that_covers_the_case_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _outcome, run_dir = self._run(tmp, token_budget=10_000_000)
            metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(10_000_000, metadata["token_budget"])

    def test_the_cli_refuses_a_budget_of_zero_rather_than_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = runner.main(
                        [
                            "--external", str(CASE_PATH),
                            "--runs-dir", str(Path(tmp)),
                            "--token-budget", "0",
                            "--model", self.model,
                        ]
                    )
            self.assertEqual(1, code)
            self.assertIn("token budget of 0", err.getvalue())
            self.assertFalse((Path(tmp) / "external").exists())
            self.assertEqual(0, self.transport.calls(), "a call was made anyway")
            self.assertEqual("", out.getvalue())

    # -- the benchmark is untouched ---------------------------------------
    def test_an_external_run_leaves_the_benchmark_byte_identical(self):
        before = _fingerprint(_benchmark_files())
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp)
        self.assertEqual(before, _fingerprint(_benchmark_files()))

    def test_an_external_run_never_writes_into_the_real_runs_tree(self):
        """The test above proves the files did not change; this proves no new ones."""
        before = sorted(p.as_posix() for p in runner.RUNS_DIR.rglob("*") if p.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp)
        after = sorted(p.as_posix() for p in runner.RUNS_DIR.rglob("*") if p.is_file())
        self.assertEqual(before, after, "an external run wrote into the real runs/ tree")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""The mocked source systems and the collector: ``ops/sources.py``, ``ops/evidence.py``.

The stretch goal is an "Evidence Collection Agent"; what is built here is the
honest half of it -- a deterministic index over the repository's own case files
and six adapters that answer key lookups against it. This module holds the two
modules to what the part states, and to the proof the part asks for: that the
collection **is** the case file's evidence, so no request can change.

Six things are asserted:

* **The adapters.** Each one's name, the artifact types it holds, the ``source``
  values it answers for and the key it takes are the table's, and a key that
  names nothing answers with nothing rather than raising.
* **No adapter returns a case.** Every answer is a tuple of artifacts, each
  carrying its own ``evidence_id`` and ``evidence_type``; no answer carries a
  case's ``dispute`` or ``evidence``.
* **The order of the lookups and of the result.** The trip first, because the
  party ids come off it; then the rest; and the result in the order every case
  file files its artifacts, which is the order the 129 committed files use.
* **What the collector may read.** It reads the dispute's ``trip_id`` and never
  its ``evidence_ids`` -- asserted by running it over a dispute that records
  every key it is asked for.
* **The proof.** For all 29 corpus cases and all 301 cases under
  ``data/external/``, each against its own root, the collection equals the case
  file's ``evidence`` array exactly: same artifacts, same order, same canonical
  JSON. And a brief built from the collected case has the ``brief_sha256`` the
  run recorded.
* **The command.** It prints the retrieval log and the check, and two runs are
  byte-identical.

The rules that bind every module of the layer -- the import graph, the answer
keys, the write guard and determinism -- are asserted once, over every ``ops``
command, in ``tests/test_ops_layer.py``.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import evidence, sources  # noqa: E402
from tribunal import brief, loader, money  # noqa: E402

CORPUS_ROOT = PROJECT_ROOT / "data" / "cases"
CORPUS_RUN = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"
EXTERNAL_ROOT = PROJECT_ROOT / "data" / "external"

# The 29-case corpus, in manifest order, read off the manifest.
CORPUS_CASE_NUMBERS: Tuple[int, ...] = tuple(
    entry["case_no"] for entry in json.loads((PROJECT_ROOT / "data" / "index.json").read_text())
)

# The adapter table, as the part states it: name -> (types, sources, key).
ADAPTER_TABLE = {
    "TripService": (("TRIP_RECORD",), ("PLATFORM_TELEMETRY",), sources.KEY_TRIP),
    "TelemetryService": (
        ("GPS_TRACE",),
        ("PLATFORM_TELEMETRY", "DRIVER_DEVICE"),
        sources.KEY_TRIP,
    ),
    "ChatService": (("CHAT_LOG",), None, sources.KEY_TRIP),
    "PaymentsLedger": (("FARE_BREAKDOWN",), None, sources.KEY_TRIP),
    "ProfileService": (
        ("RIDER_PROFILE", "DRIVER_PROFILE"),
        None,
        sources.KEY_PARTY,
    ),
    "AdvisoryFeed": (
        ("TRAFFIC_ADVISORY",),
        ("THIRD_PARTY_LTA", "USER_SUBMITTED"),
        sources.KEY_TRIP,
    ),
}


def corpus_systems() -> sources.SourceSystems:
    return sources.SourceSystems.over(CORPUS_ROOT)


def case_of(case_no: int) -> Mapping[str, Any]:
    return loader.load_case(case_no)


def run_command(arguments: Sequence[str]) -> Tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = evidence.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def external_roots() -> List[Path]:
    return [path for path in sorted(EXTERNAL_ROOT.iterdir()) if path.is_dir()]


def external_cases(root: Path) -> List[Path]:
    return [
        path
        for path in sorted(root.glob("case-*.json"))
        if not path.name.endswith(".transcript.json")
    ]


class RecordingDispute(dict):
    """A dispute that records every key it is asked for."""

    def __init__(self, payload: Mapping[str, Any], log: Set[str]) -> None:
        super().__init__(payload)
        self._log = log

    def __getitem__(self, key: str) -> Any:
        self._log.add(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._log.add(key)
        return super().get(key, default)


# --------------------------------------------------------------------------
# The adapters
# --------------------------------------------------------------------------
class TheAdapterTests(unittest.TestCase):
    """Each adapter is the one the table names, and answers only its own keys."""

    @classmethod
    def setUpClass(cls):
        cls.systems = corpus_systems()

    def test_the_six_adapters_are_the_table_s(self):
        self.assertEqual(
            sorted(ADAPTER_TABLE),
            sorted(adapter.name for adapter in self.systems.adapters()),
        )
        for adapter in self.systems.adapters():
            types, allowed, key = ADAPTER_TABLE[adapter.name]
            with self.subTest(service=adapter.name):
                self.assertEqual(types, tuple(adapter.evidence_types))
                self.assertEqual(allowed, adapter.sources)
                self.assertEqual(key, adapter.key_kind)

    def test_the_trip_service_answers_with_the_trip_record(self):
        answer = self.systems.trip.fetch("TRP-00207")
        self.assertEqual(1, len(answer))
        self.assertEqual("TRIP_RECORD", answer[0]["evidence_type"])
        self.assertEqual("PLATFORM_TELEMETRY", answer[0]["source"])
        self.assertEqual("EV-TRIP-00207", answer[0]["evidence_id"])

    def test_the_telemetry_service_answers_with_the_trace(self):
        answer = self.systems.telemetry.fetch("TRP-00207")
        self.assertEqual(["EV-GPS-00207"], [a["evidence_id"] for a in answer])
        for artifact in answer:
            self.assertIn(artifact["source"], ("PLATFORM_TELEMETRY", "DRIVER_DEVICE"))

    def test_the_telemetry_service_answers_for_a_driver_device_trace(self):
        """Case 107's trace is the driver's own device, not the platform's."""
        answer = self.systems.telemetry.fetch("TRP-00107")
        self.assertEqual(1, len(answer))
        self.assertEqual("DRIVER_DEVICE", answer[0]["source"])
        self.assertEqual("EV-GPS-00107", answer[0]["evidence_id"])
        # The service holds traces: a key that is not a trip id answers nothing,
        # so an evidence id cannot be used to pull a trace out of it.
        self.assertEqual((), self.systems.telemetry.fetch("EV-GPS-00107"))

    def test_the_profile_service_answers_by_party_id(self):
        """A profile is looked up by its own party id, and by nothing else."""
        answer = self.systems.profiles.fetch("RDR-00874")
        self.assertEqual(1, len(answer))
        self.assertEqual("RIDER_PROFILE", answer[0]["evidence_type"])
        self.assertEqual("RDR-00874", answer[0]["payload"]["party_id"])
        self.assertEqual("EV-RPROF-00104", answer[0]["evidence_id"])
        # A trip id is not a party id, so the service answers nothing for one.
        self.assertEqual((), self.systems.profiles.fetch("TRP-00104"))

    def test_the_advisory_feed_answers_with_the_advisories_of_a_trip(self):
        answer = self.systems.advisories.fetch("TRP-00104")
        self.assertEqual(
            ["EV-ADVIS-00104-01", "EV-ADVIS-00104-02"],
            [a["evidence_id"] for a in answer],
        )
        for artifact in answer:
            self.assertIn(artifact["source"], ("THIRD_PARTY_LTA", "USER_SUBMITTED"))

    def test_a_key_that_names_nothing_answers_with_nothing(self):
        for adapter in self.systems.adapters():
            with self.subTest(service=adapter.name):
                self.assertEqual((), adapter.fetch("NOTHING-AT-ALL"))

    def test_no_adapter_returns_a_whole_case_file(self):
        """Every answer is a tuple of artifacts, and none of them is a case."""
        for adapter in self.systems.adapters():
            for key in ("TRP-00207", "RDR-00571", "DRV-01561"):
                answer = adapter.fetch(key)
                for artifact in answer:
                    with self.subTest(service=adapter.name, key=key):
                        self.assertIsInstance(artifact, Mapping)
                        self.assertIn("evidence_id", artifact)
                        self.assertIn("evidence_type", artifact)
                        self.assertNotIn("dispute", artifact)
                        self.assertNotIn("evidence", artifact)
                        self.assertNotIn("case_no", artifact)

    def test_the_index_holds_artifacts_and_not_documents(self):
        index = self.systems.index
        self.assertEqual(len(CORPUS_CASE_NUMBERS), index.case_count)
        for name in ("case", "cases", "document", "documents", "load_case"):
            with self.subTest(attribute=name):
                self.assertFalse(hasattr(index, name))

    def test_a_case_root_that_is_not_there_is_refused(self):
        with self.assertRaises(sources.SourceError):
            sources.SourceIndex(Path("/tmp/no-such-case-root-at-all"))

    def test_the_index_sorts_a_multi_artifact_answer_by_evidence_id(self):
        answer = self.systems.index.artifacts(
            "TRP-00104", sources.KEY_TRIP, ("TRAFFIC_ADVISORY",), None
        )
        self.assertEqual(
            ["EV-ADVIS-00104-01", "EV-ADVIS-00104-02"],
            [a["evidence_id"] for a in answer],
        )


# --------------------------------------------------------------------------
# The collector
# --------------------------------------------------------------------------
class TheCollectorTests(unittest.TestCase):
    """The lookups, their order, and what the collector is allowed to read."""

    @classmethod
    def setUpClass(cls):
        cls.systems = corpus_systems()

    def test_the_lookups_are_the_six_the_table_names_in_order(self):
        case = case_of(207)
        collection = evidence.collect(case["dispute"], self.systems)
        self.assertEqual(
            [
                "TripService",
                "TelemetryService",
                "ChatService",
                "PaymentsLedger",
                "ProfileService",
                "ProfileService",
                "AdvisoryFeed",
            ],
            [entry.service for entry in collection.log],
        )

    def test_the_trip_is_looked_up_first_so_the_parties_can_be_read_off_it(self):
        case = case_of(207)
        collection = evidence.collect(case["dispute"], self.systems)
        trip = case["evidence"][0]["payload"]
        self.assertEqual(
            [trip["rider_id"], trip["driver_id"]],
            [entry.key for entry in collection.log if entry.service == "ProfileService"],
        )

    def test_the_log_names_the_key_and_the_ids_of_every_call(self):
        case = case_of(207)
        collection = evidence.collect(case["dispute"], self.systems)
        for entry in collection.log:
            with self.subTest(service=entry.service):
                self.assertIsInstance(entry.key, str)
                self.assertTrue(entry.key)
                self.assertIsInstance(entry.artifact_ids, tuple)
        self.assertEqual(7, len(collection.log))
        self.assertEqual(7, len(collection.artifacts))

    def test_a_call_that_found_nothing_is_in_the_log(self):
        """A source system that holds nothing for a trip is a fact, not an error.

        Every corpus case carries an advisory artifact -- a MISSING one is minted
        rather than omitted -- so this is asserted on a fixture root that holds a
        trip record and nothing else.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "case-00999.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.2.0",
                        "case_no": 999,
                        "dispute": {
                            "case_no": 999,
                            "trip_id": "TRP-00999",
                            "category": "NO_SHOW_CHARGE",
                            "filed_by": "RIDER",
                            "filed_at": "2026-07-01T10:00:00+08:00",
                            "claim_text": "fixture",
                            "amount_contested_sgd": 4.0,
                            "evidence_ids": ["EV-TRIP-00999"],
                            "counterparty_statement": {
                                "text": "fixture",
                                "submitted_by": "DRIVER",
                                "submitted_at": "2026-07-01T10:00:00+08:00",
                            },
                            "channel": "IN_APP_SUPPORT",
                        },
                        "evidence": [
                            {
                                "evidence_id": "EV-TRIP-00999",
                                "evidence_type": "TRIP_RECORD",
                                "trip_id": "TRP-00999",
                                "source": "PLATFORM_TELEMETRY",
                                "payload": {
                                    "trip_id": "TRP-00999",
                                    "rider_id": "RDR-00999",
                                    "driver_id": "DRV-00999",
                                },
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            systems = sources.SourceSystems.over(root)
            dispute = json.loads((root / "case-00999.json").read_text())["dispute"]
            collection = evidence.collect(dispute, systems)
        self.assertEqual(7, len(collection.log))
        for entry in collection.log:
            if entry.service == "TripService":
                self.assertEqual(("EV-TRIP-00999",), entry.artifact_ids)
            else:
                with self.subTest(service=entry.service):
                    self.assertEqual((), entry.artifact_ids)
        self.assertEqual(("EV-TRIP-00999",), collection.artifact_ids)
        self.assertTrue(evidence.check(collection, dispute).agrees)

    def test_the_result_is_in_the_order_every_case_file_uses(self):
        for case_no in (104, 207, 110, 213):
            case = case_of(case_no)
            collection = evidence.collect(case["dispute"], self.systems)
            with self.subTest(case=case_no):
                self.assertEqual(
                    [a["evidence_id"] for a in case["evidence"]],
                    list(collection.artifact_ids),
                )

    def test_the_collector_never_reads_the_list_of_evidence_ids(self):
        """The list is the check, not the instruction."""
        case = case_of(207)
        log: Set[str] = set()
        recording = RecordingDispute(case["dispute"], log)
        evidence.collect(recording, self.systems)
        self.assertNotIn("evidence_ids", log)
        self.assertEqual({"trip_id"}, log)

    def test_the_check_is_where_the_list_is_read(self):
        """The control: the check does read it, so the test above is not vacuous."""
        case = case_of(207)
        log: Set[str] = set()
        recording = RecordingDispute(case["dispute"], log)
        collection = evidence.collect(recording, self.systems)
        evidence.check(collection, recording)
        self.assertIn("evidence_ids", log)

    def test_a_dispute_with_no_trip_id_is_refused(self):
        with self.assertRaises(evidence.EvidenceError):
            evidence.collect({"trip_id": None}, self.systems)

    def test_a_trip_the_index_does_not_hold_is_refused(self):
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.collect({"trip_id": "TRP-99999"}, self.systems)
        self.assertIn("TRP-99999", str(caught.exception))

    def test_the_check_reports_a_missing_artifact(self):
        case = case_of(207)
        collection = evidence.collect(case["dispute"], self.systems)
        trimmed = evidence.Collection(
            artifacts=collection.artifacts[:-1], log=collection.log
        )
        result = evidence.check(trimmed, case["dispute"])
        self.assertFalse(result.agrees)
        self.assertEqual((case["evidence"][-1]["evidence_id"],), result.missing)

    def test_the_check_reports_an_artifact_the_dispute_does_not_list(self):
        case = case_of(207)
        collection = evidence.collect(case["dispute"], self.systems)
        dispute = dict(case["dispute"], evidence_ids=case["dispute"]["evidence_ids"][:-1])
        result = evidence.check(collection, dispute)
        self.assertFalse(result.agrees)
        self.assertEqual((collection.artifact_ids[-1],), result.unlisted)

    def test_the_check_reports_a_different_order(self):
        case = case_of(104)
        collection = evidence.collect(case["dispute"], self.systems)
        reversed_ids = list(reversed(case["dispute"]["evidence_ids"]))
        result = evidence.check(collection, dict(case["dispute"], evidence_ids=reversed_ids))
        self.assertFalse(result.agrees)
        self.assertFalse(result.same_order)
        self.assertEqual((), result.missing)
        self.assertEqual((), result.unlisted)


# --------------------------------------------------------------------------
# The proof that no request changes
# --------------------------------------------------------------------------
class TheCorpusEqualityTests(unittest.TestCase):
    """The collection is the case file's evidence array, exactly."""

    @classmethod
    def setUpClass(cls):
        cls.systems = corpus_systems()
        cls.collections = {
            case_no: evidence.collect(case_of(case_no)["dispute"], cls.systems)
            for case_no in CORPUS_CASE_NUMBERS
        }

    def test_every_corpus_case_collects_to_its_own_evidence_array(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = case_of(case_no)
            with self.subTest(case=case_no):
                self.assertEqual(
                    money.dumps_canonical(case["evidence"]),
                    money.dumps_canonical(list(self.collections[case_no].artifacts)),
                )

    def test_every_corpus_case_collects_to_the_same_artifacts_in_the_same_order(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = case_of(case_no)
            with self.subTest(case=case_no):
                self.assertEqual(len(case["evidence"]), len(self.collections[case_no].artifacts))
                for expected, found in zip(case["evidence"], self.collections[case_no].artifacts):
                    self.assertEqual(expected, found)

    def test_every_corpus_case_agrees_with_the_list_it_carries(self):
        for case_no in CORPUS_CASE_NUMBERS:
            case = case_of(case_no)
            result = evidence.check(self.collections[case_no], case["dispute"])
            with self.subTest(case=case_no):
                self.assertTrue(result.agrees, result)

    def test_case_104_collects_both_of_its_advisories_and_the_second_is_a_user_s(self):
        case = case_of(104)
        advisories = [
            artifact
            for artifact in self.collections[104].artifacts
            if artifact["evidence_type"] == "TRAFFIC_ADVISORY"
        ]
        self.assertEqual(2, len(advisories))
        self.assertEqual("USER_SUBMITTED", advisories[1]["source"])
        self.assertEqual(2, len([i for i in case["dispute"]["evidence_ids"] if "ADVIS" in i]))

    def test_a_brief_built_from_the_collected_case_has_the_recorded_digest(self):
        for path in sorted(CORPUS_RUN.glob("case-*.json")):
            if path.name.endswith(".transcript.json"):
                continue
            recorded = json.loads(path.read_text())
            case_no = recorded["case_no"]
            rebuilt = copy.deepcopy(case_of(case_no))
            rebuilt["evidence"] = list(self.collections[case_no].artifacts)
            digest = brief.brief_digest(brief.build_brief_for_case(rebuilt))[1]
            with self.subTest(case=case_no):
                self.assertEqual(recorded["brief_sha256"], digest)


class TheExternalEqualityTests(unittest.TestCase):
    """The same, over the 301 converted cases, each against its own root.

    ``ryde-v3/`` joined the tree on 2026-10-08: the organisers' sample converted
    for policy version 3, under a path of its own so that the version-1 case the
    recorded run read stays where it is. ``dev-v2/`` and ``dev-v2-ext/`` joined
    it the same day: Ji Guofang's 80 synthetic development cases and their 120
    variants, written for policy version 3. All four are ordinary agent-visible,
    answer-free external cases, so the same two checks apply to them.
    """

    @classmethod
    def setUpClass(cls):
        cls.roots = external_roots()

    def test_the_external_tree_holds_the_seven_sets(self):
        self.assertEqual(
            ["codex", "dev-v2", "dev-v2-ext", "ryde", "ryde-v3", "wild", "wild-v2"],
            [root.name for root in self.roots],
        )

    def test_every_external_case_collects_to_its_own_evidence_array(self):
        total = 0
        for root in self.roots:
            systems = sources.SourceSystems.over(root)
            for path in external_cases(root):
                case = json.loads(path.read_text(), parse_float=Decimal)
                collection = evidence.collect(case["dispute"], systems)
                result = evidence.check(collection, case["dispute"])
                total += 1
                with self.subTest(set=root.name, case=path.name):
                    self.assertEqual(
                        money.dumps_canonical(case["evidence"]),
                        money.dumps_canonical(list(collection.artifacts)),
                    )
                    self.assertTrue(result.agrees, result)
        self.assertEqual(301, total)

    def test_wild_v2_case_708_collects_its_user_submitted_fare_breakdown(self):
        root = EXTERNAL_ROOT / "wild-v2"
        case = json.loads((root / "case-00708.json").read_text(), parse_float=Decimal)
        collection = evidence.collect(case["dispute"], sources.SourceSystems.over(root))
        fares = [
            artifact
            for artifact in collection.artifacts
            if artifact["evidence_type"] == "FARE_BREAKDOWN"
        ]
        self.assertEqual(1, len(fares))
        self.assertEqual("USER_SUBMITTED", fares[0]["source"])
        self.assertTrue(evidence.check(collection, case["dispute"]).agrees)


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
class TheCommandTests(unittest.TestCase):
    """The retrieval log, then the check, and the same bytes twice."""

    def test_the_command_prints_the_log_then_the_check(self):
        code, out, err = run_command(["--case", "104"])
        self.assertEqual(0, code, err)
        self.assertIn("retrieval log: 7 call(s), 8 artifact(s)", out)
        self.assertIn("TripService", out)
        self.assertIn("AdvisoryFeed", out)
        self.assertIn("EV-ADVIS-00104-01, EV-ADVIS-00104-02", out)
        self.assertIn("found-versus-listed: agree (8 listed, 8 found, same order)", out)
        self.assertLess(out.index("retrieval log"), out.index("found-versus-listed"))

    def test_the_command_runs_over_the_corpus(self):
        for case_no in CORPUS_CASE_NUMBERS:
            code, out, err = run_command(["--case", str(case_no)])
            with self.subTest(case=case_no):
                self.assertEqual(0, code, err)
                self.assertIn("found-versus-listed: agree", out)

    def test_the_command_takes_a_case_file_and_indexes_its_own_root(self):
        code, out, err = run_command(
            ["--case-file", str(EXTERNAL_ROOT / "wild-v2" / "case-00708.json")]
        )
        self.assertEqual(0, code, err)
        self.assertIn("case root: {0}".format(EXTERNAL_ROOT / "wild-v2"), out)
        self.assertIn("found-versus-listed: agree", out)

    def test_the_command_needs_one_source(self):
        with self.assertRaises(SystemExit):
            run_command([])

    def test_a_case_file_that_is_not_there_is_refused(self):
        code, out, err = run_command(["--case-file", "/tmp/no-such-case-file.json"])
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)

    def test_two_runs_are_byte_identical(self):
        self.assertEqual(run_command(["--case", "104"]), run_command(["--case", "104"]))

    def test_the_command_writes_nothing(self):
        before = sorted(str(path) for path in CORPUS_ROOT.glob("*.json"))
        run_command(["--case", "104"])
        self.assertEqual(before, sorted(str(path) for path in CORPUS_ROOT.glob("*.json")))


if __name__ == "__main__":
    unittest.main()

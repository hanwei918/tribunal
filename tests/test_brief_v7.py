"""Tests for the version-7 brief -- ``tribunal.brief.build_v7_brief``.

Version 7 is Ryde's own Dispute Resolution Policy v2.1, and its clauses test
facts the version-6 brief never computed: whether the driver messaged **and**
called before cancelling, when the free wait started and ended, whether the
driver reached the pickup by the deadline, the deviation between the
**recorded** distances and the excess distance fare POL-RD-24 charges on it,
whether a traffic advisory justifies the reroute, and the value band and
confidence a ruling needs. Since part 79 the frame POL-GEN-03's party-relative
reading rests on travels too: the party who filed, the amount they contest and
the money the platform has already moved. The version-6 path also reads clauses
version 7 does not have, so version 7 has a builder of its own, entered at the
top of ``build_brief_for_case`` when ``policy_version >= 7``.

**The one rule this module holds the builder to: versions 1 to 6 do not move.**
The first class below rebuilds every recorded version-6 digest from the runs
themselves -- 194 case files across seven run directories -- and asserts each
one still hashes to the value its run recorded. The second half of that class is
the control: the same rebuild at version 7 does **not** hash to the recorded
value, so the comparison is shown to be capable of failing.

The rest of the module tests the new arithmetic and the new readings against
the policy's own numbers, over the fixtures in ``tests/fixtures/v7/`` for the
contact reading and over the real corpus for everything else. The last class
builds a version-7 brief for every corpus case and for the organisers' sample
case and holds each one to ``_assert_no_forbidden_keys``.

No model is called and no sealed root is read.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from tribunal import brief, facts, loader, money  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v7"
RUNS_DIR = PROJECT_ROOT / "runs"
INDEX_PATH = PROJECT_ROOT / "data" / "index.json"

# The version-7 development set, whose advisories record LTA DataMall's own
# traffic-incident vocabulary. Loaded through the loader every other version-7
# test uses, so its case files are held to their own index's digests.
DEV_V7_DIR = loader.EXTERNAL_DIR / "dev-v7"

# The recorded version-6 runs. A corpus run lives at ``runs/<V6_RUN_DIRNAME>/<slug>/``
# and any other set's at ``runs/<set>/<V6_RUN_DIRNAME>/<slug>/``. Two of those set
# names brief the 29-case corpus and are loaded by number from ``data/cases/``;
# every other set's cases live under ``data/external/<set>/``.
#
# The run directory's name is a constant rather than a literal in the two
# listings below, because a listing of a directory whose name spells "policy"
# is what ``tests/test_policy_versions.py`` refuses: the hazard it guards is a
# module that lists ``policy/`` rather than reading the three files by name.
V6_RUN_DIRNAME = "policy-v6"
CORPUS_RUN_SETS = frozenset({V6_RUN_DIRNAME, "precedents"})

# The fixtures that exercise POL-NS-23's contact reading, one scenario each.
CONTACT_FIXTURES = (
    "contact-messages-only.json",
    "contact-call-only.json",
    "contact-both.json",
    "contact-after-cancel.json",
    "contact-initiated-shape.json",
    "contact-voice-log-duplicate.json",
    "contact-truncated-log.json",
    "contact-missing-log.json",
)


def corpus_case_numbers():
    """Every case number of the 29-case corpus, from the manifest."""
    return [entry["case_no"] for entry in json.loads(INDEX_PATH.read_text(encoding="utf-8"))]


def recorded_run_files():
    """Every recorded version-6 case file, corpus runs and set runs alike.

    The two listings are disjoint: ``runs/<V6_RUN_DIRNAME>/<slug>/`` is the
    corpus run and ``runs/<set>/<V6_RUN_DIRNAME>/<slug>/`` is every other
    set's, and the corpus run is not reachable through the second pattern.
    """
    paths = list((RUNS_DIR / V6_RUN_DIRNAME).glob("*/case-*.json"))
    paths += list(RUNS_DIR.glob("*/" + V6_RUN_DIRNAME + "/*/case-*.json"))
    return sorted(path for path in paths if not path.name.endswith(".transcript.json"))


def the_case_of(path):
    """The case one recorded run file briefs, loaded from that run's own set."""
    set_name = path.relative_to(RUNS_DIR).parts[0]
    case_no = int(path.name[len("case-"):-len(".json")])
    if set_name in CORPUS_RUN_SETS:
        return loader.load_case(case_no)
    return loader.load_external_set_case(loader.EXTERNAL_DIR / set_name, case_no)


def the_case_number_of(path):
    """The case number a recorded run file is named for.

    ``case-02745.json`` names case 2745, the same parse ``the_case_of`` makes, so
    the number a run directory is asked about is the number its own file records.
    """
    return int(path.name[len("case-"):-len(".json")])


def leaf_paths(node, path=()):
    """The path of every leaf of a brief, in a fixed walk order."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaf_paths(value, path + (key,))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from leaf_paths(value, path + (index,))
    else:
        yield path


def first_float_outside_the_mean_distance(built):
    """The path of the first float that is not ``driver_track.mean_distance_m``.

    The platform guard may move only the mean distance, so the control that
    shows it accepts nothing else has to move something else. A float whose last
    place ``1.0`` cannot reach would leave the digest unchanged and the control
    vacuous, so the first float the change actually moves is the one taken.
    ``None`` where the brief carries no such float. The mean distance is skipped
    by the field name ``portability`` itself names, and the path and the value
    are read with ``portability``'s own helpers.
    """
    for path in leaf_paths(built):
        if portability.MEAN_DISTANCE_FIELD in path:
            continue
        value = portability._value_at(built, path)
        if isinstance(value, float) and value + 1.0 != value:
            return path
    return None


def the_json_path(path):
    """A path of keys and indices written as one JSON path, for a message.

    ``("case", "evidence", 3, "payload", "value")`` becomes
    ``case.evidence[3].payload.value``, so a failure message can name the value
    a reader would look for in the brief rather than a Python tuple.
    """
    written = ""
    for step in path:
        if isinstance(step, int):
            written += "[{0}]".format(step)
        else:
            written += ("." if written else "") + str(step)
    return written


def the_moved_float_diagnosis(moved):
    """What ``portability.which_float_moved`` found, written for a message.

    One line per ``(path, ulps)`` it returned, the path as a JSON path and the
    number of units in the last place; the sentence the sheet asks for when it
    returned nothing. It decides nothing and is only ever written into a
    failure message.
    """
    if not moved:
        return "no single float within 2 ulps reproduces it"
    return "; ".join(
        "{0} by {1} ulp{2}".format(
            the_json_path(path), ulps, "" if ulps == 1 else "s"
        )
        for path, ulps in moved
    )


def derived_block(brief_case, evidence_id, key="v7"):
    """One artifact's derived block of a built brief, by evidence id."""
    for artifact in brief_case["case"]["evidence"]:
        if artifact["evidence_id"] == evidence_id:
            return (artifact.get("payload") or {}).get("derived", {}).get(key)
    raise AssertionError("no artifact {0!r} in the brief".format(evidence_id))


def case_with(case_no, value=None, safety=None, fraud_flags=None):
    """A corpus case, edited in memory only, for the authority readings.

    Nothing here is written back: the case files under ``data/`` are frozen, and
    an authority reading is a function of the record, so the record is edited in
    a copy and the brief is built from that.
    """
    case = copy.deepcopy(loader.load_case(case_no))
    if value is not None:
        case["dispute"]["amount_contested_sgd"] = value
    if safety is not None:
        case["dispute"]["safety_flag"] = safety
    if fraud_flags is not None:
        for artifact in case["evidence"]:
            if artifact["evidence_type"] == "RIDER_PROFILE":
                artifact["payload"]["fraud_flags"] = fraud_flags
    return case


def authority_of(case):
    """``case.authority`` of a version-7 brief, with the wrappers unwrapped."""
    brief_case = brief.build_brief_for_case(case, policy_version=7)
    return {
        name: (item["value"] if isinstance(item, dict) and "value" in item else item)
        for name, item in brief_case["case"]["authority"].items()
    }


def dev_v7_case(case_no):
    """One dev-v7 case, loaded from the set's own directory."""
    return loader.load_external_set_case(DEV_V7_DIR, case_no)


def filing_frame_of(case):
    """``case.authority.filing_frame`` of a version-7 brief."""
    built = brief.build_brief_for_case(case, policy_version=7)
    return built["case"]["authority"]["filing_frame"]


def money_block_of(case):
    """The fare breakdown's version-7 money block of a built brief."""
    built = brief.build_brief_for_case(case, policy_version=7)
    for artifact in built["case"]["evidence"]:
        if artifact["evidence_type"] == "FARE_BREAKDOWN":
            return (artifact.get("payload") or {}).get("derived", {}).get("money")
    raise AssertionError("no fare breakdown in the brief")


class TheRecordedVersionSixDigestsTests(unittest.TestCase):
    """Version 6 is untouched: every recorded brief rebuilds to the digest it recorded."""

    def test_every_recorded_version_six_digest_rebuilds_unchanged(self):
        """194 recorded case files, seven run directories, no digest moved.

        The digests were recorded on macOS, and glibc and macOS ``libm`` can
        round a distance computed through a trigonometric function in the last
        place apart -- ``tests/portability.py`` names each such difference and
        holds a bounded check for it: :func:`portability.known_platform_difference`
        for case 111's ``driver_track.mean_distance_m``, one unit in the last
        place, and :func:`portability.named_platform_difference` for case 2745's
        ``rider_presence.min_distance_m``, two units, the one entry of
        ``NAMED_PLATFORM_DIFFERENCES``. Each accepts **only** a brief that
        reproduces the recorded digest when its own one value is moved within its
        own bound. Off macOS a rebuilt digest that differs is therefore accepted
        only when one of those two checks says the difference is the known one;
        the files accepted that way are printed below so the Actions log names
        them, and each is held to carrying a ``driver_track.mean_distance_m`` for
        the guard to have moved. On macOS the comparison fails as it always did,
        no other difference is accepted on any platform, and the count and the run
        directories walked are asserted exactly as before.
        """
        checked = 0
        sets = set()
        accepted = []
        for path in recorded_run_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            configuration = document.get("configuration") or {}
            self.assertEqual(
                configuration.get("policy_version"),
                6,
                "{0} is not a version-6 run".format(path),
            )
            case = the_case_of(path)
            built = brief.build_brief_for_case(case, policy_version=6)
            _canonical, digest = brief.brief_digest(built)
            recorded = document["brief_sha256"]
            if digest != recorded:
                if sys.platform == "darwin":
                    # The recorded digests are this code's own on macOS, so a
                    # difference here is a defect and fails as it always did.
                    self.assertEqual(digest, recorded, str(path))
                # Off macOS two differences are accepted, and only those two:
                # the one known last-place difference of
                # ``driver_track.mean_distance_m``, and the one named difference
                # of a second case's ``rider_presence.min_distance_m``.
                # ``portability`` states both rules and holds both bounds, and a
                # difference of two units in any other value, a difference in
                # another field, or a digest that is not the recorded one for any
                # other reason reproduces nothing and still fails here.
                as_the_platform_difference = portability.known_platform_difference(
                    built, recorded
                )
                as_a_named_difference = (
                    not as_the_platform_difference
                    and portability.named_platform_difference(
                        path.parent, the_case_number_of(path), built, recorded
                    )
                )
                as_a_known_difference = (
                    as_the_platform_difference or as_a_named_difference
                )
                # The diagnosis is for the failure message and is asked for only
                # when the case is refused: it names the one float a single move
                # of at most two units in the last place reproduces the recorded
                # digest with, or says no single float does, so the Ubuntu log
                # says which value moved and not only that one did. It decides
                # nothing and the assertion below does not read it.
                moved = (
                    []
                    if as_a_known_difference
                    else portability.which_float_moved(built, recorded)
                )
                self.assertTrue(
                    as_a_known_difference,
                    "{0} differs from the digest its run recorded by more than "
                    "the one known last-place difference or the one named "
                    "difference; {1}".format(
                        path, the_moved_float_diagnosis(moved)
                    ),
                )
                accepted.append((path, built))
            sets.add(path.relative_to(RUNS_DIR).parts[0])
            checked += 1

        if accepted:
            print(
                "\nrecorded version-6 digests rebuilt only by the known "
                "last-place difference of driver_track.mean_distance_m on {0}: "
                "{1}\n".format(
                    sys.platform,
                    ", ".join(str(path) for path, _built in accepted),
                ),
                file=sys.stderr,
            )
        for path, built in accepted:
            with self.subTest(accepted_as_the_platform_difference=str(path)):
                self.assertTrue(
                    list(portability._mean_distance_paths(built)),
                    "{0} was accepted as the platform difference but its brief "
                    "carries no driver_track.mean_distance_m".format(path),
                )

        self.assertEqual(checked, 194, "the recorded runs walked are not the ones on disk")
        self.assertEqual(
            sets,
            {
                "policy-v6",
                "precedents",
                "dev-v2",
                "dev-v2-ext",
                "ryde-v3",
                "inject-v1",
                "pii-v1",
                "collusion-v1",
            },
            "the run directories walked are not the ones on disk",
        )

    def test_the_corpus_run_is_walked_at_its_own_root(self):
        """``runs/<V6_RUN_DIRNAME>/`` is the run the sheet names, and its 29 cases are in the walk."""
        roots = {path.relative_to(RUNS_DIR).parts[0] for path in recorded_run_files()}
        self.assertIn(V6_RUN_DIRNAME, roots)
        corpus = [
            path
            for path in recorded_run_files()
            if path.relative_to(RUNS_DIR).parts[0] == V6_RUN_DIRNAME
        ]
        self.assertEqual(len(corpus), 29)

    def test_the_comparison_can_fail(self):
        """The control: the same rebuild at version 7 does not hash to the recorded value."""
        path = recorded_run_files()[0]
        document = json.loads(path.read_text(encoding="utf-8"))
        case = the_case_of(path)
        _canonical, digest = brief.brief_digest(
            brief.build_brief_for_case(case, policy_version=7)
        )
        self.assertNotEqual(digest, document["brief_sha256"])

    def test_a_different_float_is_not_the_platform_difference(self):
        """The control: the guard accepts the mean distance and nothing else.

        The same comparison the test above makes is handed a brief whose
        **other** float is moved by ``1.0``: the digest moves, and
        :func:`portability.known_platform_difference` refuses it -- on every
        platform, since moving the mean distance one unit in the last place
        cannot reproduce a digest that differs somewhere else. That is what
        shows the acceptance above is the one value in the last place and not a
        tolerance for any difference. ``portability``'s own helpers are used and
        no tolerance is added here.
        """
        path = recorded_run_files()[0]
        document = json.loads(path.read_text(encoding="utf-8"))
        recorded = document["brief_sha256"]
        built = brief.build_brief_for_case(the_case_of(path), policy_version=6)
        moved = first_float_outside_the_mean_distance(built)
        self.assertIsNotNone(
            moved,
            "{0}'s brief carries no float outside the mean distance".format(path),
        )
        changed = copy.deepcopy(built)
        portability._replace(
            changed, moved, portability._value_at(changed, moved) + 1.0
        )
        self.assertNotEqual(
            recorded,
            brief.brief_digest(changed)[1],
            "moving a float that is not the mean distance left the digest "
            "unchanged, so the control proves nothing",
        )
        self.assertFalse(
            portability.known_platform_difference(changed, recorded),
            "a difference outside the mean distance was accepted as the "
            "platform's",
        )


class TheMovedFloatDiagnosisTests(unittest.TestCase):
    """``portability.which_float_moved``: the value a recorded digest moved at.

    The helper decides nothing -- it is written for the failure message of the
    class above -- so it is tested on a synthetic brief whose digest is
    ``tribunal.brief.brief_digest``'s own. A float three levels deep moved one
    unit in the last place is found with its path; two floats moved are not
    found; and a change that is not a float is not found. The control removes
    the neighbour step and shows the one-ulp find disappear, which is what makes
    the first test capable of failing.
    """

    # Three levels deep, and two floats, so the path the helper returns is a real
    # JSON path and there is a second float that can be moved and still not found.
    SYNTHETIC_BRIEF = {
        "case": {"dispute": {"amount": 1.5, "note": "unchanged"}, "count": 7},
        "meta": {"weight": 0.25, "ok": True},
    }
    AMOUNT = ("case", "dispute", "amount")
    WEIGHT = ("meta", "weight")

    def moved(self, document, path, ulps, direction=math.inf):
        """``document`` with the float at ``path`` moved ``ulps`` in the last place."""
        shifted = copy.deepcopy(document)
        value = portability._value_at(shifted, path)
        for _step in range(ulps):
            value = math.nextafter(value, direction)
        portability._replace(shifted, path, value)
        return shifted

    def test_a_float_three_levels_deep_moved_one_ulp_is_found_with_its_path(self):
        built = copy.deepcopy(self.SYNTHETIC_BRIEF)
        recorded = brief.brief_digest(self.moved(built, self.AMOUNT, 1))[1]
        self.assertEqual(
            portability.which_float_moved(built, recorded), [(self.AMOUNT, 1)]
        )

    def test_two_floats_moved_are_not_found(self):
        built = copy.deepcopy(self.SYNTHETIC_BRIEF)
        two = self.moved(built, self.AMOUNT, 1)
        two = self.moved(two, self.WEIGHT, 1)
        recorded = brief.brief_digest(two)[1]
        self.assertEqual(portability.which_float_moved(built, recorded), [])

    def test_a_change_that_is_not_a_float_is_not_found(self):
        built = copy.deepcopy(self.SYNTHETIC_BRIEF)
        changed = copy.deepcopy(built)
        changed["case"]["count"] = 8
        recorded = brief.brief_digest(changed)[1]
        self.assertEqual(portability.which_float_moved(built, recorded), [])

    def test_without_the_neighbour_step_the_one_ulp_case_is_not_found(self):
        """The control: with the neighbour step removed, the find above is gone."""
        built = copy.deepcopy(self.SYNTHETIC_BRIEF)
        recorded = brief.brief_digest(self.moved(built, self.AMOUNT, 1))[1]
        with mock.patch.object(
            portability.math, "nextafter", lambda value, direction: value
        ):
            self.assertEqual(portability.which_float_moved(built, recorded), [])


class TheExcessDistanceFareTests(unittest.TestCase):
    """POL-RD-24's excess distance fare: no surge, to the cent, half up."""

    def test_the_three_products_the_sheet_pins(self):
        self.assertEqual(
            money.excess_distance_fare(Decimal("4.3"), Decimal("0.80")), Decimal("3.44")
        )
        self.assertEqual(
            money.excess_distance_fare(Decimal("1.25"), Decimal("0.75")), Decimal("0.94")
        )
        self.assertEqual(
            money.excess_distance_fare(Decimal("0.125"), Decimal("1.00")), Decimal("0.13")
        )

    def test_the_figures_are_decimal_and_never_float(self):
        for deviation, rate in (("4.3", "0.80"), ("1.25", "0.75"), ("0.125", "1.00")):
            figure = money.excess_distance_fare(Decimal(deviation), Decimal(rate))
            self.assertIsInstance(figure, Decimal)
            self.assertEqual(figure.as_tuple().exponent, -2, "a cent figure is written to two places")

    def test_a_float_implementation_fails_one_of_them(self):
        """The control: the same arithmetic in binary floating point is not the same figure.

        ``0.125`` is exactly representable in binary, so a float implementation
        rounds it to even and writes ``0.12`` where the clause says ``0.13``.
        Two of the three products happen to survive the float path; the third
        does not, which is why the arithmetic is Decimal.
        """
        products = ((4.3, 0.80, "3.44"), (1.25, 0.75, "0.94"), (0.125, 1.00, "0.13"))
        wrong = [
            text
            for left, right, text in products
            if "{0:.2f}".format(left * right) != text
        ]
        self.assertEqual(wrong, ["0.13"])


class TheContactBeforeCancelTests(unittest.TestCase):
    """POL-NS-23's contact reading, over one fixture per scenario."""

    def reading_of(self, name):
        fixture = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
        return fixture, facts.contact_before_cancel(
            fixture["messages"],
            fixture["in_app_calls"],
            fixture["cancelled_at"],
            chat_log_complete=fixture["chat_log_complete"],
        )

    def test_the_fixtures_are_the_scenarios_the_sheet_names(self):
        on_disk = sorted(path.name for path in FIXTURE_DIR.glob("contact-*.json"))
        self.assertEqual(on_disk, sorted(CONTACT_FIXTURES))

    def test_every_fixture_reads_as_its_own_expectation_says(self):
        for name in CONTACT_FIXTURES:
            fixture, reading = self.reading_of(name)
            expect = fixture["expect"]
            self.assertEqual(
                [message["msg_id"] for message in reading["messages"]],
                expect["messages"],
                name,
            )
            self.assertEqual(
                [call["placed_at"] for call in reading["calls"]], expect["calls"], name
            )
            self.assertEqual(reading["message_count"], expect["message_count"], name)
            self.assertEqual(reading["call_count"], expect["call_count"], name)
            self.assertIs(reading["obligation_met"], expect["obligation_met"], name)
            self.assertIs(reading["complete"], expect["complete"], name)

    def test_the_obligation_needs_both_limbs(self):
        """One message and no call, and one call and no message, are both short."""
        _fixture, only_messages = self.reading_of("contact-messages-only.json")
        _fixture, only_calls = self.reading_of("contact-call-only.json")
        _fixture, both = self.reading_of("contact-both.json")
        self.assertIs(only_messages["obligation_met"], False)
        self.assertIs(only_calls["obligation_met"], False)
        self.assertIs(both["obligation_met"], True)

    def test_a_duplicate_call_is_counted_once_and_carries_its_answers(self):
        """The call is in ``in_app_calls`` and in the chat log, at the same second."""
        _fixture, reading = self.reading_of("contact-voice-log-duplicate.json")
        self.assertEqual(len(reading["calls"]), 1)
        self.assertEqual(
            reading["calls"][0],
            {
                "placed_at": "2026-07-30T16:09:40+08:00",
                "answered": True,
                "duration_sec": 34,
                "source": facts.CALLS_SOURCE,
            },
        )
        self.assertEqual([message["msg_id"] for message in reading["messages"]], ["MSG-FIX-007"])

    def test_the_second_call_shape_is_read(self):
        _fixture, reading = self.reading_of("contact-initiated-shape.json")
        self.assertEqual(
            [call["placed_at"] for call in reading["calls"]],
            ["2026-07-30T16:06:00+08:00"],
        )

    def test_a_call_at_the_cancellation_second_is_not_before_it(self):
        _fixture, reading = self.reading_of("contact-after-cancel.json")
        self.assertEqual(reading["calls"], [])
        self.assertEqual(reading["message_count"], 1)

    def test_an_incomplete_log_says_so_rather_than_counting_zero(self):
        _fixture, truncated = self.reading_of("contact-truncated-log.json")
        _fixture, missing = self.reading_of("contact-missing-log.json")
        self.assertIs(truncated["complete"], False)
        self.assertIs(missing["complete"], False)
        self.assertIs(missing["obligation_met"], False)

    def test_a_truncated_corpus_log_makes_the_brief_say_so(self):
        """Case 210's chat log is TRUNCATED, so its trip record's block is incomplete."""
        built = brief.build_brief_for_case(loader.load_case(210), policy_version=7)
        block = derived_block(built, "EV-TRIP-00210")["contact_before_cancel"]
        self.assertIs(block["complete"]["value"], False)
        self.assertEqual(block["reason"], brief.V7_CHAT_LOG_INCOMPLETE_REASON)

    def test_case_208_met_the_obligation_and_says_which_records_show_it(self):
        built = brief.build_brief_for_case(loader.load_case(208), policy_version=7)
        block = derived_block(built, "EV-TRIP-00208")["contact_before_cancel"]
        self.assertIs(block["obligation_met"]["value"], True)
        self.assertIs(block["complete"]["value"], True)
        self.assertEqual(block["message_count"]["value"], 3)
        self.assertEqual(block["message_count"]["evidence_id"], "EV-CHAT-00208")
        self.assertEqual(block["call_count"]["value"], 1)
        self.assertEqual(block["call_count"]["evidence_id"], "EV-TRIP-00208")
        self.assertEqual(block["calls"][0]["answered"], True)
        self.assertEqual(block["calls"][0]["duration_sec"], 34)


class TheFreeWaitAndDeadlineTests(unittest.TestCase):
    """POL-NS-21's free wait and POL-NS-24's deadline, on the policy's own numbers."""

    def test_an_on_demand_trip_runs_from_the_arrival(self):
        reading = facts.free_wait(
            "2026-07-30T16:02:25+08:00", None, 300, "2026-07-30T16:12:10+08:00"
        )
        self.assertEqual(reading["starts_from"], facts.FREE_WAIT_FROM_ARRIVAL)
        self.assertEqual(reading["starts_at"], "2026-07-30T16:02:25+08:00")
        self.assertEqual(reading["ends_at"], "2026-07-30T16:07:25+08:00")
        self.assertIs(reading["cancelled_after_free_wait"], True)
        self.assertEqual(reading["seconds_from_start_to_cancel"], 585.0)

    def test_a_scheduled_trip_the_driver_reached_early_runs_from_the_schedule(self):
        reading = facts.free_wait(
            "2026-07-30T08:43:00+08:00",
            "2026-07-30T08:45:00+08:00",
            300,
            "2026-07-30T08:50:01+08:00",
        )
        self.assertEqual(reading["starts_from"], facts.FREE_WAIT_FROM_SCHEDULE)
        self.assertEqual(reading["starts_at"], "2026-07-30T08:45:00+08:00")
        self.assertEqual(reading["ends_at"], "2026-07-30T08:50:00+08:00")

    def test_a_scheduled_trip_the_driver_reached_late_runs_from_the_arrival(self):
        reading = facts.free_wait(
            "2026-07-30T08:47:00+08:00",
            "2026-07-30T08:45:00+08:00",
            300,
            "2026-07-30T08:50:00+08:00",
        )
        self.assertEqual(reading["starts_from"], facts.FREE_WAIT_FROM_ARRIVAL)
        self.assertEqual(reading["starts_at"], "2026-07-30T08:47:00+08:00")
        self.assertEqual(reading["ends_at"], "2026-07-30T08:52:00+08:00")
        self.assertIs(reading["cancelled_after_free_wait"], False)

    def test_the_moment_the_wait_elapses_is_after_it_and_the_second_before_is_not(self):
        cases = (
            ("2026-07-30T08:49:59+08:00", False),
            ("2026-07-30T08:50:00+08:00", True),
            ("2026-07-30T08:50:01+08:00", True),
        )
        for cancelled_at, expected in cases:
            reading = facts.free_wait(
                "2026-07-30T08:43:00+08:00",
                "2026-07-30T08:45:00+08:00",
                300,
                cancelled_at,
            )
            self.assertIs(reading["cancelled_after_free_wait"], expected, cancelled_at)

    def test_an_on_demand_trip_fixes_no_deadline(self):
        reading = facts.driver_deadline(None, "2026-07-30T08:43:00+08:00", 300)
        self.assertIsNone(reading["deadline"])
        self.assertEqual(reading["reason"], facts.ON_DEMAND_REASON)
        self.assertNotIn("arrived_by_deadline", reading)

    def test_a_scheduled_trip_measures_the_arrival_against_the_deadline(self):
        early = facts.driver_deadline(
            "2026-07-30T08:45:00+08:00", "2026-07-30T08:43:00+08:00", 300
        )
        late = facts.driver_deadline(
            "2026-07-30T08:45:00+08:00", "2026-07-30T08:51:00+08:00", 300
        )
        never = facts.driver_deadline("2026-07-30T08:45:00+08:00", None, 300)
        self.assertEqual(early["deadline"], "2026-07-30T08:50:00+08:00")
        self.assertIs(early["arrived_by_deadline"], True)
        self.assertIs(late["arrived_by_deadline"], False)
        self.assertIs(never["arrived_by_deadline"], False)

    def test_the_brief_publishes_the_wait_and_the_deadline_for_case_208(self):
        built = brief.build_brief_for_case(loader.load_case(208), policy_version=7)
        block = derived_block(built, "EV-TRIP-00208")
        self.assertEqual(block["free_wait"]["free_wait_sec"]["value"], 300)
        self.assertEqual(block["free_wait"]["free_wait_sec"]["clause_id"], "POL-NS-21")
        self.assertIs(block["free_wait"]["cancelled_after_free_wait"]["value"], True)
        self.assertIsNone(block["driver_deadline"]["deadline"])
        self.assertEqual(block["driver_deadline"]["reason"], facts.ON_DEMAND_REASON)
        self.assertEqual(
            block["driver_deadline"]["driver_late_after_scheduled_sec"]["clause_id"], "POL-NS-24"
        )


class TheDeviationTests(unittest.TestCase):
    """POL-RD-22's recorded-distance deviation and POL-RD-25's 2 km limb."""

    def test_the_recorded_distances_give_the_deviation(self):
        reading = facts.deviation(
            Decimal("24.8"), Decimal("20.5"), Decimal("1.0"), Decimal("2.0"), False
        )
        self.assertIs(reading["available"], True)
        self.assertEqual(reading["deviation_km"], Decimal("4.30"))
        self.assertIs(reading["within_tolerance"], False)
        self.assertIs(reading["over_ai_limit"], True)
        self.assertIs(reading["ai_limit_applied"], False)

    def test_a_deviation_of_exactly_the_tolerance_is_within_it(self):
        reading = facts.deviation(
            Decimal("21.0"), Decimal("20.0"), Decimal("1.0"), Decimal("2.0"), False
        )
        self.assertIs(reading["within_tolerance"], True)
        self.assertIs(reading["over_ai_limit"], False)

    def test_a_null_distance_leaves_the_deviation_unestablished(self):
        reading = facts.deviation(None, Decimal("20.0"), Decimal("1.0"), Decimal("2.0"), False)
        self.assertIs(reading["available"], False)
        self.assertNotIn("deviation_km", reading)
        self.assertEqual(reading["reason"], facts.DEVIATION_NOT_MEASURABLE_REASON)

    def test_an_impaired_record_leaves_it_unestablished_too(self):
        reading = facts.deviation(
            Decimal("24.8"), Decimal("20.5"), Decimal("1.0"), Decimal("2.0"), False, impaired=True
        )
        self.assertIs(reading["available"], False)
        self.assertNotIn("deviation_km", reading)

    def test_case_101_deviation_and_its_excess_distance_fare(self):
        built = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        deviation = derived_block(built, "EV-TRIP-00101")["deviation"]
        money_block = derived_block(built, "EV-FARE-00101", key="money")
        self.assertEqual(deviation["deviation_km"]["value"], Decimal("6.20"))
        self.assertIs(deviation["over_ai_limit"]["value"], True)
        self.assertIs(deviation["ai_limit_applied"]["value"], False)
        self.assertEqual(deviation["tolerance_km"]["clause_id"], "POL-RD-22")
        self.assertEqual(deviation["ai_limit_km"]["clause_id"], "POL-RD-25")
        self.assertEqual(money_block["excess_distance_fare_sgd"]["value"], Decimal("4.65"))
        self.assertEqual(money_block["per_km_rate_sgd"]["value"], Decimal("0.75"))
        self.assertEqual(money_block["deviation_km"]["value"], Decimal("6.20"))

    def test_the_message_index_holds_what_was_sent_while_the_trip_ran(self):
        built = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        block = derived_block(built, "EV-TRIP-00101")["messages_during_trip"]
        self.assertEqual(block["clause_id"], "POL-RD-21")
        self.assertEqual(
            [message["sender"] for message in block["messages"]],
            ["RIDER", "DRIVER", "RIDER"],
        )
        self.assertEqual(
            [message["sent_at"] for message in block["messages"]],
            [
                "2026-07-12T10:41:12+08:00",
                "2026-07-12T10:42:05+08:00",
                "2026-07-12T10:42:31+08:00",
            ],
        )

    def test_a_missing_advisory_says_it_is_missing_rather_than_justifying_nothing(self):
        built = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        block = derived_block(built, "EV-ADVIS-00101-01")
        self.assertIs(block["available"], False)
        self.assertIn("MISSING", block["reason"])
        self.assertIs(block["justifies_reroute"]["value"], False)

    def test_an_advisory_of_a_kind_the_clause_names_justifies_the_reroute(self):
        built = brief.build_brief_for_case(loader.load_case(103), policy_version=7)
        block = derived_block(built, "EV-ADVIS-00103-01")
        self.assertEqual(block["type"]["value"], "CLOSURE")
        self.assertIs(block["justifies_reroute"]["value"], True)
        self.assertEqual(block["justification_kind"]["value"], "closure")
        self.assertEqual(block["admissible_types"]["clause_id"], "POL-RD-23")
        self.assertEqual(
            sorted(block["admissible_types"]["value"]),
            ["closure", "congestion", "incident", "normalisation", "note"],
        )

    def test_an_advisory_that_does_not_intersect_the_route_justifies_nothing(self):
        built = brief.build_brief_for_case(loader.load_case(104), policy_version=7)
        block = derived_block(built, "EV-ADVIS-00104-02")
        self.assertIs(block["intersects_route"]["value"], False)
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIn("does not intersect the recommended route", block["reason"])

    def test_an_accident_on_the_route_in_the_window_justifies_as_an_incident(self):
        """The policy's type map, not the clause's three words, decides the kind.

        POL-RD-23 names "congestion, an incident or a closure", and the policy
        states which recorded types each admits in
        ``thresholds.traffic_justification_types``: an accident is an incident
        because the policy lists it under that kind. This advisory intersects
        the route and overlaps the trip window, so the type is the only
        condition in question and it holds.
        """
        built = brief.build_brief_for_case(loader.load_case(104), policy_version=7)
        block = derived_block(built, "EV-ADVIS-00104-01")
        self.assertEqual(block["type"]["value"], "ACCIDENT")
        self.assertIs(block["intersects_route"]["value"], True)
        self.assertIs(block["overlaps_trip_window"]["value"], True)
        self.assertIs(block["justifies_reroute"]["value"], True)
        self.assertEqual(block["justification_kind"]["value"], "incident")
        self.assertNotIn("reason", block)

    def test_a_kerb_restriction_and_a_traffic_flow_justify_nothing(self):
        """Two recorded types the policy's own note says do not justify a reroute.

        Neither value is in the policy's map, so neither names a kind -- and the
        reason says so, naming the three kinds the map does carry rather than
        the values the two advisories happen to hold. The kerb restriction is
        the corpus's own case 214 advisory, which intersects the route and
        overlaps the trip, read through the reader the block calls: case 214 is
        a no-show, and a no-show brief carries no advisory block at all. The
        traffic flow is DISP-001's third advisory, read through the brief.
        """
        mapped = loader.load_policies("ROUTE_DEVIATION", 7)["category"]["thresholds"][
            "traffic_justification_types"
        ]
        kerb = {
            "type": "KERB_RESTRICTION",
            "intersects_route": True,
            "overlaps_trip_window": True,
            "severity": "MODERATE",
        }
        reading = facts.advisory_justification("EV-ADVIS-00214-01", kerb, mapped)
        self.assertIs(reading["justifies_reroute"], False)
        self.assertIsNone(reading["justification_kind"])

        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v7", 902)
        built = brief.build_brief_for_case(sample, policy_version=7)
        flow = derived_block(built, "EV-ADVIS-00902-03")
        self.assertEqual(flow["type"]["value"], "TRAFFIC_FLOW")
        self.assertIs(flow["justifies_reroute"]["value"], False)
        self.assertIsNone(flow["justification_kind"]["value"])
        self.assertIn("not one of the kinds POL-RD-23 names", flow["reason"])
        self.assertIn("closure, congestion, incident", flow["reason"])

    def test_rydes_vehicle_fire_advisory_justifies_as_an_incident(self):
        """DISP-001's first advisory, which the clause's three words did not name."""
        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v7", 902)
        built = brief.build_brief_for_case(sample, policy_version=7)
        block = derived_block(built, "EV-ADVIS-00902-01")
        self.assertEqual(block["type"]["value"], "VEHICLE_FIRE")
        self.assertIs(block["justifies_reroute"]["value"], True)
        self.assertEqual(block["justification_kind"]["value"], "incident")

    def test_the_accident_reading_fails_when_the_type_map_is_emptied(self):
        """The control: the justification is the map's, not the word's.

        The same case, the same advisory and the same brief, with the policy's
        type map replaced by an empty one: the ACCIDENT advisory no longer
        justifies anything, which is what shows the first assertion above rests
        on the map rather than on the word ``ACCIDENT``.
        """
        built = brief.build_brief_for_case(loader.load_case(104), policy_version=7)
        self.assertIs(
            derived_block(built, "EV-ADVIS-00104-01")["justifies_reroute"]["value"], True
        )

        with mock.patch.object(brief, "_v7_justification_types", lambda *a, **k: {}):
            emptied = brief.build_brief_for_case(loader.load_case(104), policy_version=7)
        block = derived_block(emptied, "EV-ADVIS-00104-01")
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIsNone(block["justification_kind"]["value"])
        self.assertIn("not one of the kinds POL-RD-23 names", block["reason"])


class TheAdvisoryShapeTests(unittest.TestCase):
    """POL-RD-23 reads every advisory shape the record holds.

    The public contract fixes the shape of no condition the clause tests, and the
    data holds three shapes: the corpus shape (``type``,
    ``active_from``/``active_to``, ``intersects_route``, ``overlaps_trip_window``),
    the LTA shape (``advisory_type``, ``valid_from``/``valid_to``, ``road``,
    ``direction``, ``location_desc``) and the road-segment shape (``type``,
    ``valid_from``/``valid_to``, ``road``, ``segment``).

    Read only the corpus way, the block told every LTA advisory that it named no
    type, overlapped no window and did not intersect the route -- case 5011, an
    accident on the PIE on the recommended route inside the trip window, was
    told it had no traffic justification at all. The one condition no shape can
    answer is whether the advisory lies on the recommended route, and that is
    reported ``null`` with the Judge named as the one who decides it, never
    ``false``.
    """

    def dev_v7(self, case_no):
        """One dev-v7 case, loaded from the set's own directory."""
        return loader.load_external_set_case(loader.EXTERNAL_DIR / "dev-v7", case_no)

    def block_of(self, case, evidence_id):
        """One advisory's version-7 block of a built brief."""
        return derived_block(
            brief.build_brief_for_case(case, policy_version=7), evidence_id
        )

    def lta_case(self, case_no, **fields):
        """A dev-v7 case with its LTA advisory's payload edited in memory only.

        The case files under ``data/`` are frozen, so the record is edited in a
        copy and the brief is built from that, exactly as :func:`case_with` does
        for the authority readings.
        """
        case = copy.deepcopy(self.dev_v7(case_no))
        for artifact in case["evidence"]:
            if artifact["evidence_type"] == "TRAFFIC_ADVISORY":
                artifact["payload"].update(fields)
        return case

    def test_dev_v7_5011s_accident_is_an_incident_and_the_route_is_the_judges(self):
        """The LTA shape: ``advisory_type``, ``valid_from``/``valid_to``, no route.

        Case 5011's advisory is an accident on the PIE, in the trip window. Its
        type now comes from ``advisory_type``, its window is computed from
        ``valid_from``/``valid_to`` against the trip record's
        ``started_at``/``ended_at``, and the route -- the one fact the payload
        does not state -- is ``null`` with ``determined_by: "judge"`` rather than
        a ``false`` the record does not hold.
        """
        block = self.block_of(self.dev_v7(5011), "EV-ADVIS-05011-01")
        self.assertIs(block["available"], True)
        self.assertEqual(block["type"]["value"], "ACCIDENT")
        self.assertEqual(block["justification_kind"]["value"], "incident")
        # The payload states no overlap of its own, so the one reading published
        # is the computed one, and there is no second to disagree with it.
        self.assertIs(block["overlaps_trip_window"]["value"], True)
        self.assertNotIn("overlaps_trip_window_computed", block)
        self.assertIsNone(block["intersects_route"]["value"])
        self.assertIsNone(block["justifies_reroute"]["value"])
        self.assertEqual(block["determined_by"], "judge")
        self.assertEqual(block["undetermined"], "on the recommended route")
        self.assertEqual(
            "the record does not say whether this advisory lies on the "
            "recommended route; the Judge decides from its road, direction and "
            "location against the trip (POL-RD-23)",
            block["reason"],
        )
        # The facts the Judge decides it from travel in the block.
        self.assertEqual(
            block["location"]["road"]["value"], "Pan-Island Expressway (PIE)"
        )
        self.assertEqual(block["location"]["direction"]["value"], "towards Changi")
        self.assertEqual(
            block["location"]["location_desc"]["value"], "after Adam Road exit"
        )

    def test_an_lta_window_ending_before_the_trip_starts_justifies_nothing(self):
        """The window is measured, and the route is not turned into a failure.

        The same advisory with its window moved before the trip's
        ``started_at``: the overlap is computed ``false``, so POL-RD-23 is not
        satisfied -- and the reason names the window alone. The route, which this
        shape never states, is not listed as a second failure, because the block
        never reports a fact the record does not hold as false.
        """
        case = self.lta_case(
            5011,
            valid_from="2026-08-28T06:00:00+08:00",
            valid_to="2026-08-28T07:00:00+08:00",
        )
        block = self.block_of(case, "EV-ADVIS-05011-01")
        self.assertEqual(block["justification_kind"]["value"], "incident")
        self.assertIs(block["overlaps_trip_window"]["value"], False)
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIn("outside the trip window", block["reason"])
        self.assertNotIn("does not intersect the recommended route", block["reason"])

    def test_an_lta_kerb_restriction_names_no_kind_and_justifies_nothing(self):
        """A type the policy's own map does not carry, read through the LTA field."""
        case = self.lta_case(5011, advisory_type="KERB_RESTRICTION")
        block = self.block_of(case, "EV-ADVIS-05011-01")
        self.assertEqual(block["type"]["value"], "KERB_RESTRICTION")
        self.assertIsNone(block["justification_kind"]["value"])
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIn("not one of the kinds POL-RD-23 names", block["reason"])

    def test_the_corpus_shape_reads_exactly_as_it_did(self):
        """Case 104's two advisories and case 902's three, unchanged.

        Both shapes here spell every condition the corpus way, so the three-shape
        reader must give them the readings the block gave before it: 104's first
        justifies as an incident, its second fails on the route alone, and 902's
        three read incident, congestion and no-kind.
        """
        first = self.block_of(loader.load_case(104), "EV-ADVIS-00104-01")
        self.assertEqual(first["type"]["value"], "ACCIDENT")
        self.assertEqual(first["justification_kind"]["value"], "incident")
        self.assertIs(first["intersects_route"]["value"], True)
        self.assertIs(first["overlaps_trip_window"]["value"], True)
        self.assertIs(first["justifies_reroute"]["value"], True)
        self.assertNotIn("reason", first)

        second = self.block_of(loader.load_case(104), "EV-ADVIS-00104-02")
        self.assertIs(second["intersects_route"]["value"], False)
        self.assertIs(second["justifies_reroute"]["value"], False)
        self.assertIn("does not intersect the recommended route", second["reason"])

        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v7", 902)
        expected = (
            ("EV-ADVIS-00902-01", "VEHICLE_FIRE", "incident", True, True),
            ("EV-ADVIS-00902-02", "HEAVY_CONGESTION", "congestion", True, True),
            ("EV-ADVIS-00902-03", "TRAFFIC_FLOW", None, False, False),
        )
        for evidence_id, type_value, kind, intersects, justifies in expected:
            with self.subTest(evidence_id=evidence_id):
                block = self.block_of(sample, evidence_id)
                self.assertEqual(block["type"]["value"], type_value)
                self.assertEqual(block["justification_kind"]["value"], kind)
                self.assertIs(block["intersects_route"]["value"], intersects)
                self.assertIs(block["justifies_reroute"]["value"], justifies)
                # The payload states its own overlap, and the window computed
                # from it against the trip record agrees with it.
                self.assertIs(block["overlaps_trip_window"]["value"], True)
                self.assertIs(block["overlaps_trip_window_computed"]["value"], True)
                self.assertNotIn("overlaps_trip_window_note", block)

    def test_the_road_segment_shape_builds_and_reads_no_kind(self):
        """sealed-v3's shape, read from its own payload and from no key.

        sealed-v3 is closed and is never run again; this only proves the reader
        holds the third shape. Case 4059 is a no-show, so a version-7 brief
        carries no advisory block for it at all -- POL-RD-23 is a route-deviation
        clause -- and the payload is read through the block builder directly.
        Nothing under ``eval/`` is read, and no answer key is opened.
        """
        case = loader.load_external_set_case(loader.EXTERNAL_DIR / "sealed-v3", 4059)
        advisory = next(
            artifact
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRAFFIC_ADVISORY"
        )
        trip = next(
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRIP_RECORD"
        )
        policy = loader.load_policies("ROUTE_DEVIATION", 7)["category"]
        block = brief._v7_advisory_block(
            advisory,
            policy["thresholds"]["traffic_justification_types"],
            policy["policy_id"],
            trip,
        )
        self.assertIs(block["available"], True)
        self.assertEqual(block["type"]["value"], "KERB_RESTRICTION")
        self.assertIsNone(block["justification_kind"]["value"])
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIn("not one of the kinds POL-RD-23 names", block["reason"])
        self.assertEqual(block["location"]["road"]["value"], "Serangoon Road")
        self.assertIn("bus lane", block["location"]["segment"]["value"])

    def test_the_5011_reading_fails_when_the_advisory_type_fallback_is_removed(self):
        """The control: the type is the LTA shape's field, not a guess.

        The same case, the same advisory and the same brief, with the reader
        made to look only at the corpus field ``type``: the accident names no
        kind and justifies nothing, so the assertions of the 5011 test above are
        the ones that fail. That is what shows the reading rests on the LTA
        shape's own type field rather than on anything else in the payload.
        """
        case = self.dev_v7(5011)
        self.assertEqual(
            self.block_of(case, "EV-ADVIS-05011-01")["justification_kind"]["value"],
            "incident",
        )

        def corpus_field_only(payload):
            value = payload.get("type")
            return value.strip() if isinstance(value, str) and value.strip() else None

        with mock.patch.object(facts, "advisory_type_token", corpus_field_only):
            block = self.block_of(case, "EV-ADVIS-05011-01")
        self.assertIsNone(block["type"]["value"])
        self.assertIsNone(block["justification_kind"]["value"])
        self.assertIs(block["justifies_reroute"]["value"], False)
        self.assertIn("not one of the kinds POL-RD-23 names", block["reason"])


class TheAdvisoryVocabularyTests(unittest.TestCase):
    """The types the version-7 sets record, read against the policy's own map.

    dev-v7 and sealed-v4 record LTA DataMall's traffic-incident vocabulary --
    ``HEAVY_TRAFFIC``, ``VEHICLE_BREAKDOWN``, ``ROAD_CLOSURE``, ``ROADWORK``,
    ``ACCIDENT``, ``NONE`` -- while C18's map was written from the corpus's
    spellings. The map is the policy's and not this module's: a type names a
    kind because the policy lists it under that kind, and a type the map does
    not carry names none. The policy's own ``normalisation`` rule folds a
    recorded type before the match, so a ``Vehicle breakdown`` or a
    ``road-closure`` names the same kind the map's upper-case tokens do.
    """

    def dev_v7(self, case_no):
        """One dev-v7 case, loaded from the set's own directory."""
        return loader.load_external_set_case(DEV_V7_DIR, case_no)

    def mapped_types(self):
        """The policy's own type map, as the version-7 reader is handed it."""
        return loader.load_policies("ROUTE_DEVIATION", 7)["category"]["thresholds"][
            "traffic_justification_types"
        ]

    def block_of(self, case, evidence_id):
        """One advisory's version-7 block of a built brief."""
        return derived_block(
            brief.build_brief_for_case(case, policy_version=7), evidence_id
        )

    def lta_case(self, case_no, **fields):
        """A dev-v7 case with its LTA advisory's payload edited in memory only."""
        case = copy.deepcopy(self.dev_v7(case_no))
        for artifact in case["evidence"]:
            if artifact["evidence_type"] == "TRAFFIC_ADVISORY":
                artifact["payload"].update(fields)
        return case

    def test_each_type_the_version_seven_sets_use_names_its_kind(self):
        """The four LTA types the two version-7 sets record, each its own kind."""
        for type_value, kind in (
            ("HEAVY_TRAFFIC", "congestion"),
            ("VEHICLE_BREAKDOWN", "incident"),
            ("ROAD_CLOSURE", "closure"),
            ("ROADWORK", "closure"),
        ):
            with self.subTest(type=type_value):
                block = self.block_of(
                    self.lta_case(5011, advisory_type=type_value), "EV-ADVIS-05011-01"
                )
                self.assertEqual(block["type"]["value"], type_value)
                self.assertEqual(block["justification_kind"]["value"], kind)

    def test_a_spaced_or_hyphenated_type_is_normalised_before_it_is_matched(self):
        """The policy's rule: upper case, then an underscore for a space or hyphen."""
        for written, token, kind in (
            ("Vehicle breakdown", "VEHICLE_BREAKDOWN", "incident"),
            ("road-closure", "ROAD_CLOSURE", "closure"),
        ):
            with self.subTest(type=written):
                block = self.block_of(
                    self.lta_case(5011, advisory_type=written), "EV-ADVIS-05011-01"
                )
                self.assertEqual(block["type"]["value"], token)
                self.assertEqual(block["justification_kind"]["value"], kind)

    def test_the_types_the_policy_does_not_name_still_name_no_kind(self):
        """``NONE`` and the three the policy's own note names as justifying nothing."""
        for type_value in ("NONE", "WEATHER", "KERB_RESTRICTION", "TRAFFIC_FLOW"):
            with self.subTest(type=type_value):
                block = self.block_of(
                    self.lta_case(5011, advisory_type=type_value), "EV-ADVIS-05011-01"
                )
                self.assertEqual(block["type"]["value"], type_value)
                self.assertIsNone(block["justification_kind"]["value"])

    def test_every_typed_advisory_of_dev_v7_names_a_kind(self):
        """Read from the set's own case files: 41 advisories, 11 of them typed.

        The 21 with no payload at all are MISSING artifacts and carry no type;
        the nine recorded ``NONE`` name no kind on purpose and are read by
        :meth:`test_the_types_the_policy_does_not_name_still_name_no_kind`. What
        is left is every advisory the set records a traffic event for, and each
        of them now names one of POL-RD-23's three kinds.
        """
        mapped = self.mapped_types()
        advisories = 0
        typed = 0
        entries = json.loads((DEV_V7_DIR / "index.json").read_text(encoding="utf-8"))
        for entry in entries:
            case = self.dev_v7(entry["case_no"])
            for artifact in case["evidence"]:
                if artifact["evidence_type"] != "TRAFFIC_ADVISORY":
                    continue
                advisories += 1
                payload = artifact.get("payload")
                token = (
                    facts.advisory_type_token(payload)
                    if isinstance(payload, dict)
                    else None
                )
                if token is None or token == "NONE":
                    continue
                with self.subTest(case=entry["case_no"], type=token):
                    typed += 1
                    self.assertIsNotNone(
                        facts.justification_kind(token, mapped),
                        "{0} names no kind".format(token),
                    )
        self.assertEqual(41, advisories, "the advisories walked are not the ones on disk")
        self.assertEqual(11, typed, "the typed advisories are not the ones on disk")

    def test_the_normalisation_is_what_makes_a_spaced_type_match(self):
        """The control: with the normalisation step removed, the spaced type fails.

        The same case, the same advisory and the same brief, with
        :func:`facts.normalise_advisory_type` replaced by the identity: the
        recorded ``Vehicle breakdown`` is matched as it was written and names no
        kind, which is what shows the assertion in
        :meth:`test_a_spaced_or_hyphenated_type_is_normalised_before_it_is_matched`
        rests on the policy's own rule rather than on the reader folding the two
        words anyway.
        """
        written = self.lta_case(5011, advisory_type="Vehicle breakdown")
        self.assertEqual(
            self.block_of(written, "EV-ADVIS-05011-01")["justification_kind"]["value"],
            "incident",
        )

        with mock.patch.object(facts, "normalise_advisory_type", lambda value: value):
            block = self.block_of(written, "EV-ADVIS-05011-01")
        self.assertEqual(block["type"]["value"], "Vehicle breakdown")
        self.assertIsNone(block["justification_kind"]["value"])


class TheArrivalAccuracyFilterTests(unittest.TestCase):
    """POL-NS-21's arrival test, and the policy's rule for its accuracy filter.

    The policy states the rule in ``arrival_test.accuracy_filter_applies``: the
    filter reaches **only a fix that reports an accuracy**. A fix that reports
    none is used at its reported position rather than dropped, and the block
    says its accuracy is unreported; a fix that reports one is filtered as it
    always was.
    """

    def test_rydes_no_show_reads_corroborated_with_an_unreported_accuracy(self):
        """Case 903's nearest fix is at the pickup and reports no accuracy.

        DISP-002's trace has the vehicle at 0 m from the pin at the arrival
        marker with no accuracy in the record. Under the policy's rule the fix
        is used as it stands, so the arrival is corroborated -- and the block
        says the accuracy is unreported rather than leaving the reader to
        notice it.
        """
        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v7", 903)
        built = brief.build_brief_for_case(sample, policy_version=7)
        block = derived_block(built, "EV-GPS-00903")["arrival_check"]
        self.assertIs(block["accuracy_reported"]["value"], False)
        self.assertIs(block["corroborated"]["value"], True)
        self.assertIsNone(block["nearest_fix"]["accuracy_m"]["value"])
        self.assertEqual(Decimal("0.0"), block["nearest_fix"]["distance_m"]["value"])
        self.assertIn("reports no accuracy", block["accuracy_note"])
        self.assertIn("accuracy_filter_applies", block["accuracy_note"])

    def test_the_policys_own_rule_is_published_beside_the_reading(self):
        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v7", 903)
        built = brief.build_brief_for_case(sample, policy_version=7)
        block = derived_block(built, "EV-GPS-00903")["arrival_check"]
        self.assertEqual("POL-NS-21", block["accuracy_filter_applies"]["clause_id"])
        self.assertIn(
            "only to a fix that reports an accuracy",
            block["accuracy_filter_applies"]["value"],
        )

    def test_a_fix_reporting_a_poor_accuracy_inside_the_radius_is_filtered_out(self):
        """The filter is not switched off: 40 m of accuracy fails the 25 m one.

        The fix is about 10 m from the pin -- well inside the 50 m arrival
        radius -- so the only condition that can fail is the accuracy, and the
        reading is asserted to have failed on exactly that one.
        """
        pickup = {"lat": 1.2847, "lng": 103.8382}
        points = [
            {
                "lat": 1.28479,
                "lng": 103.8382,
                "ts": "2026-09-13T08:43:00+08:00",
                "accuracy_m": 40,
            }
        ]
        reading = facts.arrival_check(
            points, pickup, "2026-09-13T08:43:00+08:00", 120, 50, 25
        )
        self.assertIs(reading["accuracy_reported"], True)
        self.assertLess(reading["nearest_fix"]["distance_m"], 50)
        self.assertEqual(40, reading["nearest_fix"]["accuracy_m"])
        self.assertIs(reading["corroborated"], False)

    def test_the_same_fix_with_no_reported_accuracy_is_used_as_it_stands(self):
        """The control for the test above: the filter is the accuracy's absence."""
        pickup = {"lat": 1.2847, "lng": 103.8382}
        points = [{"lat": 1.28479, "lng": 103.8382, "ts": "2026-09-13T08:43:00+08:00"}]
        reading = facts.arrival_check(
            points, pickup, "2026-09-13T08:43:00+08:00", 120, 50, 25
        )
        self.assertIs(reading["accuracy_reported"], False)
        self.assertLess(reading["nearest_fix"]["distance_m"], 50)
        self.assertIs(reading["corroborated"], True)


class TheAuthorityTests(unittest.TestCase):
    """POL-GEN-22's bands and bars, POL-GEN-21's safety limb, POL-RD-25's 0.80."""

    def test_the_band_edges_are_the_policys_own(self):
        edges = (
            ("9.99", "AI_FINAL", 0.0),
            ("10.00", "CONFIDENCE_0_80", 0.80),
            ("50.00", "CONFIDENCE_0_80", 0.80),
            ("50.01", "HUMAN_ONLY", 0.0),
        )
        for value, band, confidence in edges:
            authority = authority_of(case_with(208, value=Decimal(value)))
            self.assertEqual(authority["value_band"], band, value)
            self.assertEqual(authority["required_confidence"], Decimal(str(confidence)), value)

    def test_only_a_value_above_the_second_band_is_a_persons(self):
        self.assertIs(authority_of(case_with(208, value=Decimal("50.00")))["human_only"], False)
        self.assertIs(authority_of(case_with(208, value=Decimal("50.01")))["human_only"], True)

    def test_a_fraud_flag_raises_the_bar_to_the_policys_own_figure(self):
        authority = authority_of(case_with(208, value=Decimal("50.00"), fraud_flags=1))
        self.assertEqual(authority["fraud_flags"], 1)
        self.assertEqual(authority["required_confidence"], Decimal("0.95"))

    def test_a_safety_flag_is_a_persons_however_small_the_amount(self):
        authority = authority_of(case_with(208, value=Decimal("4.00"), safety=True))
        self.assertIs(authority["safety_flag"], True)
        self.assertIs(authority["human_only"], True)
        self.assertEqual(authority["value_band"], "AI_FINAL")

    def test_a_route_deviation_needs_the_policys_own_confidence_at_any_band(self):
        for value in ("4.00", "30.00"):
            authority = authority_of(case_with(101, value=Decimal(value)))
            self.assertEqual(authority["required_confidence"], Decimal("0.80"), value)

    def test_a_route_deviation_reports_the_2_km_limb_and_its_switch(self):
        authority = authority_of(case_with(101))
        self.assertIs(authority["over_ai_limit"], True)
        self.assertIs(authority["ai_limit_applied"], False)

    def test_a_no_show_below_the_first_band_has_no_bar(self):
        authority = authority_of(case_with(208))
        self.assertEqual(authority["required_confidence"], Decimal("0.0"))
        self.assertEqual(authority["value_band"], "AI_FINAL")

    def test_the_authority_names_the_clause_each_reading_rests_on(self):
        built = brief.build_brief_for_case(loader.load_case(208), policy_version=7)
        authority = built["case"]["authority"]
        self.assertEqual(authority["value_band"]["clause_id"], "POL-GEN-22")
        self.assertEqual(authority["dispute_value_sgd"]["clause_id"], "POL-GEN-22")
        self.assertEqual(authority["safety_flag"]["clause_id"], "POL-GEN-21")
        # A no-show below the first band has no bar, and POL-NS-26 is the clause
        # that makes its ruling final; a route deviation's bar is POL-RD-25's.
        self.assertEqual(authority["required_confidence"]["clause_id"], "POL-NS-26")
        route = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        self.assertEqual(
            route["case"]["authority"]["required_confidence"]["clause_id"], "POL-RD-25"
        )
        self.assertEqual(
            route["case"]["authority"]["over_ai_limit"]["clause_id"], "POL-RD-25"
        )

    def test_the_profiles_travel_with_their_optional_counters(self):
        """POL-GEN-22 and POL-NS-25 read two optional profile fields; both survive."""
        built = brief.build_brief_for_case(loader.load_case(208), policy_version=7)
        profiles = {
            artifact["evidence_type"]: artifact["payload"]
            for artifact in built["case"]["evidence"]
            if artifact["evidence_type"] in ("RIDER_PROFILE", "DRIVER_PROFILE")
        }
        self.assertEqual(set(profiles), {"RIDER_PROFILE", "DRIVER_PROFILE"})
        source = loader.load_case(208)
        for artifact in source["evidence"]:
            if artifact["evidence_type"] in profiles:
                self.assertEqual(artifact["payload"], profiles[artifact["evidence_type"]])


class TheFilingFrameTests(unittest.TestCase):
    """POL-GEN-03 is party-relative: the frame names the outcome for the filer.

    The first dev-v7 run got every driver-filed case wrong in the same way. A
    driver-filed route deviation where the platform had already refunded the
    rider and recovered the amount from the driver -- ``refund_issued_sgd`` > 0,
    a ``fare_adjusted`` event -- is not a case in which part of the charge comes
    back: the rider is owed exactly the excess distance fare already refunded,
    the driver is contesting that, and POL-GEN-03's own words make the ruling
    NO_ACTION, "the filing party's claim is not supported and the present state
    stands". The facts and the money were right; the ruling value was not.

    ``case.authority.filing_frame`` states the party, the amount contested, the
    money already moved and the clause's vocabulary for that party, so the
    ruling value is read off the clause rather than inferred from the claim.
    """

    def test_dev_v7_5006_the_driver_filed_and_the_frame_names_that_outcome(self):
        frame = filing_frame_of(dev_v7_case(5006))
        self.assertEqual("POL-GEN-03", frame["clause_id"])
        self.assertEqual("DRIVER", frame["filed_by"])
        self.assertEqual(Decimal("1.37"), frame["contested_sgd"])
        self.assertEqual(Decimal("1.37"), frame["already_moved"])
        self.assertEqual(
            [{"event_type": "fare_adjusted", "at": "2026-08-19T01:56:34+08:00"}],
            frame["already_moved_events"],
        )
        words = " ".join(frame["outcome_words"])
        # The driver-filed sentences, each naming the figure already moved.
        self.assertIn(
            "the rider is owed the 1.37 SGD already refunded -> the driver's "
            "claim fails and the present state stands: NO_ACTION",
            words,
        )
        self.assertIn("the driver is owed the whole 1.37 SGD back", words)
        self.assertIn("the driver is owed part of the 1.37 SGD back", words)
        # Not the rider-filed vocabulary: the rider did not file this dispute.
        self.assertNotIn("the rider is owed 1.37 SGD -> FULL_REFUND", words)

    def test_dev_v7_5006_the_money_block_publishes_what_was_already_issued(self):
        figure = money_block_of(dev_v7_case(5006))["refund_already_issued_sgd"]
        self.assertEqual(Decimal("1.37"), figure["value"])
        self.assertEqual("POL-GEN-03", figure["clause_id"])

    def test_dev_v7_5001_the_rider_filed_and_nothing_has_moved(self):
        frame = filing_frame_of(dev_v7_case(5001))
        self.assertEqual("RIDER", frame["filed_by"])
        self.assertEqual(Decimal("3.00"), frame["contested_sgd"])
        self.assertEqual(Decimal("0"), frame["already_moved"])
        self.assertEqual([], frame["already_moved_events"])
        words = " ".join(frame["outcome_words"])
        self.assertIn("the rider is owed 3.00 SGD -> FULL_REFUND", words)
        self.assertIn("the rider is owed nothing -> NO_ACTION", words)
        self.assertIn("DRIVER_COMPENSATION", words)
        self.assertNotIn("the driver's claim fails", words)

    def test_dev_v7_5058_the_reversed_fee_is_what_has_already_moved(self):
        """A driver-filed no-show: the fee was charged, then reversed."""
        case = dev_v7_case(5058)
        frame = filing_frame_of(case)
        refund = next(
            artifact["payload"]["refund_issued_sgd"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "FARE_BREAKDOWN"
        )
        self.assertEqual("DRIVER", frame["filed_by"])
        self.assertEqual(refund, frame["already_moved"])
        self.assertEqual(Decimal("5.00"), frame["already_moved"])
        self.assertEqual(
            [{"event_type": "fee_reversed", "at": "2026-08-24T07:59:40+08:00"}],
            frame["already_moved_events"],
        )

    def test_the_5006_reading_fails_when_the_refund_field_is_ignored(self):
        """The control: ignore ``refund_issued_sgd`` and the 5006 reading does not hold.

        ``money.refund_already_issued`` is the one reader of the field, so
        patching it to zero is exactly "the field is ignored": the frame reads
        no money moved, takes the reading for a driver who filed with nothing
        already moved, and the money block publishes 0. Every assertion the 5006
        test makes about the amount then fails.
        """
        with mock.patch.object(money, "refund_already_issued", return_value=money.ZERO):
            frame = filing_frame_of(dev_v7_case(5006))
            block = money_block_of(dev_v7_case(5006))
        self.assertEqual(Decimal("0"), frame["already_moved"])
        self.assertNotIn(
            "the driver is owed the whole 1.37 SGD back",
            " ".join(frame["outcome_words"]),
        )
        self.assertEqual(Decimal("0"), block["refund_already_issued_sgd"]["value"])


class EveryVersionSevenBriefBuildsTests(unittest.TestCase):
    """The whole corpus and the organisers' sample case, at version 7."""

    def test_every_corpus_case_builds_and_carries_no_forbidden_key(self):
        numbers = corpus_case_numbers()
        self.assertEqual(len(numbers), 29)
        for case_no in numbers:
            with self.subTest(case=case_no):
                built = brief.build_brief_for_case(loader.load_case(case_no), policy_version=7)
                brief._assert_no_forbidden_keys(built)
                self.assertIn("authority", built["case"])

    def test_the_organisers_sample_case_builds_at_version_seven(self):
        sample = loader.load_external_set_case(loader.EXTERNAL_DIR / "ryde-v3", 901)
        built = brief.build_brief_for_case(sample, policy_version=7)
        brief._assert_no_forbidden_keys(built)
        self.assertEqual(built["case"]["case_no"], 901)
        self.assertIn("authority", built["case"])

    def test_the_brief_is_serialisable_with_its_decimals(self):
        """A version-7 brief carries Decimals, and the canonical serialiser writes them."""
        built = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        canonical, digest = brief.brief_digest(built)
        self.assertIn('"excess_distance_fare_sgd":{"clause_id":"POL-RD-24"', canonical)
        self.assertNotIn('"4.65"', canonical, "a Decimal is written as a number, not quoted")
        self.assertEqual(len(digest), 64)

    def test_no_version_six_clause_id_reaches_a_version_seven_brief(self):
        """The version-7 policy's own ids, and none of the clauses version 7 does not have."""
        built = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        canonical, _digest = brief.brief_digest(built)
        for gone in ("POL-RD-01", "POL-RD-02", "POL-RD-03", "POL-RD-07", "POL-NS-06", "POL-RD-11"):
            self.assertNotIn(gone, canonical)

    def test_the_version_six_path_is_still_the_version_six_path(self):
        """A version-6 brief carries no version-7 block, and the version-7 one does."""
        six = brief.build_brief_for_case(loader.load_case(101), policy_version=6)
        seven = brief.build_brief_for_case(loader.load_case(101), policy_version=7)
        for artifact in six["case"]["evidence"]:
            derived = (artifact.get("payload") or {}).get("derived") or {}
            self.assertNotIn("v7", derived)
        self.assertIn("authority", seven["case"])
        self.assertNotIn("authority", six["case"])


if __name__ == "__main__":
    unittest.main()

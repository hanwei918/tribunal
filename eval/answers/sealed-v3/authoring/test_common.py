"""Self-tests for build/common.py and build/generate.py.

run:  python3 build/test_common.py            (all green expected)
      BREAK=hav python3 build/test_common.py   (feeds hav_km a perturbed input; the hav test must go red)
      BREAK=fare python3 build/test_common.py  (corrupts the dummy fare; the check_set tests must go red)
Throwaway output goes to tmp/selftest/.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from decimal import Decimal

BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BUILD_DIR)
sys.path.insert(0, BUILD_DIR)

import common as C  # noqa: E402
import generate as G  # noqa: E402

BREAK = os.environ.get("BREAK", "")
TMP = os.path.join(ROOT_DIR, "tmp", "selftest")
CHECK = os.path.join(ROOT_DIR, "ref", "check_set.py")

_spec = importlib.util.spec_from_file_location("check_set_ref", CHECK)
CS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CS)


# ---------------------------------------------------------------------------
# dummy fixtures (format only; not part of the set)
# ---------------------------------------------------------------------------
def dummy_rd(n=4001):
    r = C.rng(n, "dummy")
    day = "2026-09-02"
    t_req = C.ts(day, "08:10:00")
    t_acc = C.add_s(t_req, 20)
    t_arr = C.add_s(t_acc, 240)
    t_start = C.add_s(t_arr, 60)
    route = [(1.33240, 103.84740), (1.33900, 103.84900), (1.34600, 103.85100), (1.35070, 103.84860)]
    pts = C.drive(route, t_start, [35, 45, 30], 5, rng=r, jitter_m=2.0, accuracy_m=(3, 8), speed_noise_kph=2)
    t_end = pts[-1]["ts"]
    gps = C.gps_trace(n, pts, expected_interval_sec=5)
    dist = Decimal(str(gps["trace_distance_km"]))
    mins = Decimal(int(C.diff_s(t_start, t_end))) / 60
    lines = C.metered_lines(dist.quantize(Decimal("0.01")), mins.quantize(Decimal("0.1")))
    gantry = C.erp_gantry("ERP-TEST-01", "Test gantry", 1.3400, 103.8495, C.add_s(t_start, 120), "1.00")
    fare_kw = dict(lines, erp_gantries=[gantry], charged_at=t_end)
    if BREAK == "fare":
        fare = C.fare_breakdown(n, **fare_kw)
        fare["total_charged"] = round(fare["total_charged"] + 1.0, 2)
    else:
        fare = C.fare_breakdown(n, **fare_kw)
    gen = C.add_min(t_end, 30)
    trip = C.trip_record(n, rider_id="R-1001", driver_id="D-2001", requested_at=t_req, accepted_at=t_acc,
                         arrived_at=t_arr, started_at=t_start, ended_at=t_end, status="COMPLETED",
                         pickup=C.place("Fixture pickup", *route[0]), dropoff=C.place("Fixture dropoff", *route[-1]),
                         vehicle_type="RYDE_X", pickup_zone_class="STANDARD", chat_message_count=2,
                         optimal_distance_km=2.4, actual_distance_km=gps["trace_distance_km"],
                         events=[C.event("trip_started", t_start, "Trip started.")])
    chat = C.chat_log(n, [C.msg("RIDER", "omw down now", C.add_s(t_arr, 10)),
                          C.msg("DRIVER", "ok wait ah", C.add_s(t_arr, 30))])
    ev = [
        C.artifact(n, "TRAFFIC_ADVISORY", None, C.adm_missing("Artifact absent.", gen), source="THIRD_PARTY_LTA",
                   generated_at=gen, seq=1),
        C.artifact(n, "TRIP_RECORD", trip, C.adm_complete("Fixture record.", gen), source="PLATFORM_TELEMETRY",
                   generated_at=gen),
        C.artifact(n, "GPS_TRACE", gps, C.adm_impaired(["GPS_GAP"], "Fixture trace.", gen,
                                                       gps_gap_grade="SHORT_OR_OUTSIDE_WINDOW"),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "CHAT_LOG", chat, C.adm_complete("Fixture chat.", gen), source="PLATFORM_TELEMETRY",
                   generated_at=gen),
        C.artifact(n, "FARE_BREAKDOWN", fare, C.adm_complete("Fixture ledger.", gen), source="PAYMENTS_LEDGER",
                   generated_at=gen),
        C.artifact(n, "RIDER_PROFILE", C.rider_profile("R-1001", gen, account_age_days=100),
                   C.adm_complete("Fixture profile.", gen), source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "DRIVER_PROFILE", C.driver_profile("D-2001", gen, vehicle_type="RYDE_X"),
                   C.adm_complete("Fixture profile.", gen), source="PLATFORM_TELEMETRY", generated_at=gen),
    ]
    filed = C.add_min(t_end, 120)
    builder = C.make_case if BREAK != "fare" else _make_case_unchecked
    case = builder(n, C.RD, ev, filed_at=filed, filed_by="RIDER", channel="IN_APP_SUPPORT",
                   amount_contested_sgd="2.00", claim_text="Fixture claim text.",
                   counterparty_statement=C.counterparty("Fixture reply.", "DRIVER", C.add_min(filed, 60)))
    key = C.key_record(n, "NO_ACTION", None, None, [], ["POL-RD-01"], "EASY",
                       "Fixture record for the format self-test only. It cites EV-GPS-{0:05d} and "
                       "EV-FARE-{0:05d} and names POL-RD-01 so that the key checks have something to read; "
                       "it is not an answer to anything.".format(n))
    return case, key


def _make_case_unchecked(n, category, evidence, **kw):
    ev = sorted(evidence, key=lambda e: (C.EVIDENCE_ORDER.index(e["evidence_type"]), e["evidence_id"]))
    d = C.dispute(n, category, evidence_ids=[e["evidence_id"] for e in ev], **kw)
    return {"schema_version": C.SCHEMA_VERSION, "case_no": n, "dispute": d, "evidence": ev}


def dummy_ns(n=4051):
    r = C.rng(n, "dummy")
    day = "2026-09-20"
    pin = (1.30080, 103.90580)
    t_req = C.ts(day, "19:00:00")
    t_acc = C.add_s(t_req, 15)
    approach = C.drive([(1.30600, 103.90200), pin], C.add_s(t_acc, 30), 30, 10, rng=r, accuracy_m=(4, 9))
    t_arr = approach[-1]["ts"]
    wait = C.dwell(pin[0], pin[1], t_arr, 330, 15, rng=r, jitter_m=3.0, accuracy_m=(4, 12), include_start=False)
    pts = C.concat(approach, wait)
    t_can = C.add_s(t_arr, 335)
    gen = C.add_min(t_can, 20)
    pp = C.platform_policy(free_wait_sec=300, cancellation_fee_sgd="4.50")
    trip = C.trip_record(n, rider_id="R-1002", driver_id="D-2002", requested_at=t_req, accepted_at=t_acc,
                         arrived_at=t_arr, cancelled_at=t_can, status="CANCELLED_BY_DRIVER", cancelled_by="DRIVER",
                         cancellation_reason_code="RIDER_NO_SHOW", pickup=C.place("Fixture pin", *pin),
                         dropoff=C.place("Fixture drop", 1.31200, 103.89000), vehicle_type="RYDE_XL",
                         pickup_zone_class="STANDARD", chat_message_count=0,
                         in_app_calls=[C.in_app_call(n, 1, C.add_s(t_arr, 120), "DRIVER", False, 20)],
                         platform_policy=pp)
    fare = C.fare_breakdown(n, cancellation_fee="4.50", charged_at=t_can)
    ev = [
        C.artifact(n, "TRIP_RECORD", trip, C.adm_complete("Fixture.", gen), source="PLATFORM_TELEMETRY",
                   generated_at=gen),
        C.artifact(n, "GPS_TRACE", C.gps_trace(n, pts), C.adm_complete("Fixture.", gen), source="DRIVER_DEVICE",
                   generated_at=gen),
        C.artifact(n, "CHAT_LOG", None, C.adm_missing("Artifact absent.", gen), source="PLATFORM_TELEMETRY",
                   generated_at=gen),
        C.artifact(n, "FARE_BREAKDOWN", fare, C.adm_impaired(["LOW_SAMPLE_RATE", "PARTIAL_RECORD"], "Fixture.", gen),
                   source="PAYMENTS_LEDGER", generated_at=gen),
        C.artifact(n, "RIDER_PROFILE", C.rider_profile("R-1002", gen), C.adm_complete("Fixture.", gen),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "DRIVER_PROFILE", C.driver_profile("D-2002", gen), C.adm_complete("Fixture.", gen),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "TRAFFIC_ADVISORY", C.advisory("ADV-TEST-1", "ROADWORKS", "Fixture Road", "A to B",
                                                     (1.3010, 103.9050), (1.3020, 103.9070), t_req,
                                                     C.add_min(t_req, 120), C.add_min(t_req, -60), "LTA-TEST-1"),
                   C.adm_complete("Fixture.", gen), source="THIRD_PARTY_LTA", generated_at=gen, seq=1),
    ]
    case = C.make_case(n, C.NS, ev, filed_at=C.add_min(t_can, 600), filed_by="DRIVER", channel="EMAIL",
                       amount_contested_sgd="4.50", claim_text="Fixture claim.", counterparty_statement=None,
                       safety_flag=False)
    key = C.key_record(n, "NO_ACTION", None, None, [], ["POL-NS-01"], "HARD",
                       "Fixture record for the format self-test only; it cites EV-TRIP-{0:05d} and "
                       "EV-GPS-{0:05d} and names POL-NS-01 so the key checks have something to read. Not an "
                       "answer.".format(n))
    return case, key


def write_set(name, items):
    out = os.path.join(TMP, name)
    if os.path.isdir(out):
        shutil.rmtree(out)
    files = G.render(items)
    for rel, data in files.items():
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    return out


def run_check(out, with_key=True):
    cmd = [sys.executable, CHECK, os.path.join(out, "cases")]
    if with_key:
        cmd.append(os.path.join(out, "answers", "ground_truth.json"))
    cmd += ["--range", "4001", "4065"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, [l for l in res.stdout.splitlines() if l.startswith(("FAIL", "WARN"))], res


# ---------------------------------------------------------------------------
class TestGeometry(unittest.TestCase):
    PAIRS = [((1.2840, 103.8510), (1.3521, 103.8198)), ((1.3644, 103.9915), (1.2966, 103.7764)),
             ((1.4370, 103.7860), (1.4370, 103.7861)), ((1.3000, 103.8000), (1.3000, 103.8000)),
             ((1.2494, 103.8303), (1.4491, 103.8200))]

    def test_hav_matches_check_set(self):
        for a, b in self.PAIRS:
            da, db = {"lat": a[0], "lng": a[1]}, {"lat": b[0], "lng": b[1]}
            if BREAK == "hav":
                db = {"lat": b[0] + 0.0001, "lng": b[1]}
            self.assertEqual(C.hav_km(a, b), CS.km(da, db))
            self.assertEqual(C.hav_km(da, db), CS.km(da, db))

    def test_trace_distance(self):
        case, _ = dummy_rd()
        pts = case["evidence"][1]["payload"]["points"]
        raw = sum(CS.km(pts[i - 1], pts[i]) for i in range(1, len(pts)))
        self.assertEqual(C.trace_distance(pts), round(raw, 3))
        self.assertEqual(case["evidence"][1]["payload"]["trace_distance_km"], round(raw, 3))

    def test_drive_and_dwell(self):
        t0 = C.ts("2026-09-01", "10:00:00")
        pts = C.drive([(1.30, 103.80), (1.31, 103.80)], t0, 36, 10)
        # 1.112 km at 36 km/h = 10 m/s -> ~111 s, fixes every 10 s, last fix at the end waypoint
        self.assertEqual(pts[0]["ts"], t0)
        self.assertEqual((pts[-1]["lat"], pts[-1]["lng"]), (1.31, 103.8))
        iv = C.intervals(pts)
        self.assertTrue(all(x == 10 for x in iv[:-1]) and 0 < iv[-1] <= 10)
        self.assertAlmostEqual(C.trace_distance(pts), C.hav_km((1.30, 103.80), (1.31, 103.80)), places=3)
        d = C.dwell(1.31, 103.80, pts[-1]["ts"], 100, 30, include_start=False)
        self.assertEqual([C.diff_s(pts[-1]["ts"], p["ts"]) for p in d], [30, 60, 90, 100])
        self.assertTrue(all(p["speed_kph"] == 0 for p in d))
        joined = C.concat(pts, d)
        self.assertEqual(len(joined), len(pts) + len(d))
        cut = C.drop_between(joined, pts[2]["ts"], pts[6]["ts"])
        self.assertEqual(C.max_gap(cut), 40.0)
        self.assertEqual(len(C.gap_list(cut, 30)), 1)
        self.assertGreater(C.max_jump_m(cut), 300)
        self.assertEqual(C.min_dist_m((1.31, 103.80), joined), 0.0)
        ws = C.window_stats(joined, pts[-1]["ts"], d[-1]["ts"])
        self.assertEqual(ws["fixes"], 5)
        self.assertEqual(C.longest_run_within(joined, (1.31, 103.80), 10, 25)[0], 5)

    def test_seeded_jitter_is_deterministic(self):
        t0 = C.ts("2026-09-01", "10:00:00")
        a = C.drive([(1.30, 103.80), (1.32, 103.81)], t0, 50, 3, rng=C.rng(4001, "x"), jitter_m=4, accuracy_m=(3, 9))
        b = C.drive([(1.30, 103.80), (1.32, 103.81)], t0, 50, 3, rng=C.rng(4001, "x"), jitter_m=4, accuracy_m=(3, 9))
        c = C.drive([(1.30, 103.80), (1.32, 103.81)], t0, 50, 3, rng=C.rng(4002, "x"), jitter_m=4, accuracy_m=(3, 9))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        with self.assertRaises(C.BuildError):
            C.drive([(1.30, 103.80), (1.32, 103.81)], t0, 50, 3, jitter_m=4)


class TestMoneyTimeWeights(unittest.TestCase):
    def test_up005(self):
        self.assertEqual(C.up005(3.12), Decimal("3.15"))
        self.assertEqual(C.up005(3.10), Decimal("3.10"))
        self.assertEqual(C.up005(3.101), Decimal("3.15"))
        self.assertEqual(C.up005("0.00"), Decimal("0.00"))
        self.assertEqual(C.up005(Decimal("7.151")), Decimal("7.20"))

    def test_q2_num(self):
        self.assertEqual(C.q2("2.345"), Decimal("2.35"))
        self.assertEqual(C.q2("2.344"), Decimal("2.34"))
        self.assertEqual(C.num("4.5"), 4.5)
        self.assertEqual(json.dumps(C.num(Decimal("10.10"))), "10.1")
        self.assertIsNone(C.num(None))
        self.assertEqual(C.money_str(5), "5.00")

    def test_time(self):
        t = C.ts("2026-09-30", "23:59:30")
        self.assertEqual(C.add_s(t, 45), "2026-10-01T00:00:15+08:00")
        self.assertEqual(C.diff_s(t, C.add_s(t, 45)), 45.0)
        self.assertEqual(C.fmt_ts("2026-09-30T15:59:30+00:00"), t)
        with self.assertRaises(C.BuildError):
            C.parse_ts("2026-09-30T15:59:30")

    def test_weights(self):
        self.assertEqual(C.weight_for(["LOW_SAMPLE_RATE", "PARTIAL_RECORD"]), 0.6)
        self.assertEqual(C.weight_for([]), 1.0)
        self.assertEqual(C.weight_for(["MISSING_ARTIFACT"]), 0.0)
        self.assertEqual(C.weight_for(["GPS_GAP"], "SHORT_OR_OUTSIDE_WINDOW"), 0.85)
        self.assertEqual(C.weight_for(["GPS_GAP"], "LONG_INSIDE_WINDOW"), 0.6)
        self.assertEqual(C.weight_for(["GPS_GAP", "LOW_SAMPLE_RATE"], "STRADDLING_CANCELLATION"), 0.48)
        self.assertEqual(C.weight_for(["UNREAD_MESSAGE", "GPS_DRIFT"]), 0.43)  # 0.425 half-up
        with self.assertRaises(C.BuildError):
            C.weight_for(["GPS_GAP"])
        with self.assertRaises(C.BuildError):
            C.weight_for(["NOT_A_CODE"])

    def test_clause_table_matches_check_set(self):
        letters = {"FULL_REFUND": "F", "PARTIAL_REFUND": "P", "NO_ACTION": "N", "DRIVER_COMPENSATION": "D",
                   "ESCALATE": "E"}
        mine = {cid: set(letters[x] for x in lic) for cid, lic in C.clause_table().items()}
        theirs = {cid: set(v) for cid, v in CS.LIC.items()}
        self.assertEqual(mine, theirs)
        self.assertEqual(set(C.ISSUE_CODES), CS.CODES)
        self.assertEqual(set(C.SOURCES), CS.SOURCES)
        self.assertEqual(C.FORBIDDEN, CS.FORBIDDEN)
        self.assertEqual(set(C.PP_KEYS), CS.PP)
        self.assertEqual(C.TOK, CS.TOK)


class TestSampleShapes(unittest.TestCase):
    """The builders emit the sample's full key sets."""

    def test_key_sets_cover_sample(self):
        with open(os.path.join(ROOT_DIR, "ref", "case-00901.json"), encoding="utf-8") as f:
            s = json.load(f)
        by = {e["evidence_type"]: e for e in s["evidence"]}
        self.assertEqual(list(by["TRIP_RECORD"]["payload"]), list(C.TRIP_KEYS))
        self.assertEqual(list(by["GPS_TRACE"]["payload"]), list(C.GPS_KEYS))
        self.assertEqual(list(by["CHAT_LOG"]["payload"]), list(C.CHAT_KEYS))
        self.assertEqual(list(by["CHAT_LOG"]["payload"]["messages"][0]), list(C.MSG_KEYS))
        self.assertEqual(list(by["FARE_BREAKDOWN"]["payload"]), list(C.FARE_KEYS))
        self.assertEqual(list(by["RIDER_PROFILE"]["payload"]), list(C.RPROF_KEYS))
        self.assertEqual(list(by["DRIVER_PROFILE"]["payload"]), list(C.DPROF_KEYS))
        self.assertEqual(set(s["dispute"]), set(C.DISPUTE_KEYS))
        self.assertEqual(set(s["evidence"][0]), set(C.ARTIFACT_KEYS))
        case, _ = dummy_rd()
        pb = {e["evidence_type"]: e["payload"] for e in case["evidence"]}
        for t, keys in (("TRIP_RECORD", C.TRIP_KEYS), ("GPS_TRACE", C.GPS_KEYS), ("CHAT_LOG", C.CHAT_KEYS),
                        ("FARE_BREAKDOWN", C.FARE_KEYS), ("RIDER_PROFILE", C.RPROF_KEYS),
                        ("DRIVER_PROFILE", C.DPROF_KEYS)):
            self.assertEqual(list(pb[t]), list(keys), t)


class TestCheckSet(unittest.TestCase):
    def test_single_dummy_passes_except_both_categories(self):
        out = write_set("one", [dummy_rd()])
        rc, fails, _ = run_check(out, with_key=False)
        self.assertEqual(fails, ["FAIL set: both categories are required"])

    def test_two_dummies_with_key_pass(self):
        items = [dummy_rd(), dummy_ns()]
        for case, key in items:
            self.assertEqual(C.validate_case(case) + C.lint_case(case), [])
            self.assertEqual(C.validate_key(key, case), [])
        out = write_set("two", items)
        rc, fails, res = run_check(out)
        self.assertEqual(fails, [], res.stdout)
        self.assertEqual(rc, 0)
        with open(os.path.join(out, "cases", "CANARY.txt"), "rb") as f:
            raw = f.read()
        self.assertFalse(raw.endswith(b"\n"))
        self.assertEqual(len(raw), 36)

    def test_tampering_is_caught(self):
        case, key = dummy_rd()
        bad = json.loads(json.dumps(case))
        bad["evidence"][1]["payload"]["trace_distance_km"] += 0.5
        self.assertTrue(any("trace_distance_km" in p for p in C.validate_case(bad)))
        out = write_set("tampered", [(bad, key), dummy_ns()])
        rc, fails, _ = run_check(out)
        self.assertTrue(any("trace_distance_km" in f for f in fails))
        bad2 = json.loads(json.dumps(case))
        bad2["dispute"]["claim_text"] = "I had difficulty finding you"
        self.assertTrue(any("forbidden" in p for p in C.validate_case(bad2)))
        bad3 = json.loads(json.dumps(case))
        bad3["evidence"][1]["admissibility"]["weight_multiplier"] = 0.7
        self.assertTrue(any("integrity product" in p for p in C.validate_case(bad3)))
        k2 = json.loads(json.dumps(key))
        k2["ground_truth"]["expected_ruling"] = "FULL_REFUND"
        k2["ground_truth"]["expected_amount_sgd"] = 1.95
        self.assertTrue(C.validate_key(k2, case))
        k3 = json.loads(json.dumps(key))
        k3["ground_truth"]["governing_clauses"] = ["POL-RD-07(a)"]
        self.assertTrue(C.validate_key(k3, case))

    def test_builders_refuse_bad_input(self):
        with self.assertRaises(C.BuildError):
            C.fare_breakdown(4001, base_fare="3.80", total_charged="9.99")
        with self.assertRaises(C.BuildError):
            C.adm_impaired(["MISSING_ARTIFACT"], "x", C.ts("2026-09-01", "10:00:00"))
        with self.assertRaises(C.BuildError):
            C.artifact(4001, "TRIP_RECORD", None, C.adm_missing("x", C.ts("2026-09-01", "10:00:00")),
                       source="PLATFORM_TELEMETRY", generated_at=C.ts("2026-09-01", "10:00:00"))
        with self.assertRaises(C.BuildError):
            C.trip_record(4001, rider_id="R-1", bogus_key=1)


class TestGenerate(unittest.TestCase):
    def test_missing_modules_are_empty(self):
        saved = G.MODULES
        try:
            G.MODULES = (("rd", "cases_rd_absent_xyz", C.RD, C.RD_RANGE),
                         ("ns", "cases_ns_absent_xyz", C.NS, C.NS_RANGE))
            self.assertEqual(G.collect(None), [])
            files = G.render([])
            self.assertEqual(json.loads(files["cases/index.json"]), [])
        finally:
            G.MODULES = saved

    def test_render_deterministic_and_clean(self):
        items = [dummy_rd(), dummy_ns()]
        a, b = G.render(items), G.render([dummy_rd(), dummy_ns()])
        self.assertEqual(a, b)
        for path, data in a.items():
            text = data.decode("ascii")
            if path.startswith("cases/"):
                self.assertEqual(C.forbidden_hits(text), [], path)
        idx = json.loads(a["cases/index.json"])
        self.assertEqual([e["file"] for e in idx], ["case-04001.json", "case-04051.json"])
        readme = a["cases/README.md"].decode("ascii")
        self.assertIn("2026-10-11 freeze", readme)
        self.assertIn("0002-pol-rd-14.json", readme)

    def test_static_lint_clean(self):
        self.assertEqual(G.static_lint(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

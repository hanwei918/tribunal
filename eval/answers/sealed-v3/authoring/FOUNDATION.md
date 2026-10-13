# Generator foundation (build/common.py, build/generate.py)

For the authors of `build/cases_rd.py` (cases 4001-4015, ROUTE_DEVIATION) and
`build/cases_ns.py` (cases 4051-4065, NO_SHOW_CHARGE). Python 3 standard
library only. Read `build/BRIEF.md` first; this file only describes the tools.

## Contract for a case module

```python
def build():
    return [(case_dict, key_record), ...]   # one pair per case, any order
```

- `case_dict` comes from `common.make_case(...)`, `key_record` from
  `common.key_record(...)`.
- No clock reads, no unseeded randomness: the only randomness is
  `common.rng(case_no, salt)` (a `random.Random` seeded from a fixed root, the
  case number and your salt). `generate.py` lints every `build/*.py` (except
  `test_*.py`) for `datetime.now`, `time.time`, `uuid.uuid4`, module-level
  `random.*` calls, `random.Random()` and so on, rebuilds in-process and in a
  fresh interpreter with another hash seed, and refuses to write if the bytes
  differ. Do not iterate over a `set` to build output.
- Helper modules of your own may live in `build/` (they are linted too).

## Running

```
python3 build/generate.py --out out/            # both categories
python3 build/generate.py --out tmp/x --only rd # one category
python3 build/generate.py --out out/ --strict   # + all 30 cases and the BRIEF section 2/3 targets
python3 build/test_common.py                    # foundation self-tests
```

`generate.py` validates every case (`validate_case` + `lint_case`) and every
key (`validate_key`) before writing, writes `cases/` and
`answers/ground_truth.json`, then runs `ref/check_set.py --range 4001 4065` on
the result. Anything answer-bearing (key problems, check_set key findings,
target counts) goes to `DIR/answers/*.log|json`, never to stdout. A `--only`
run ignores check_set's "both categories" failure.

## common.py API

### ids and constants
`dsp_id(n)`, `trp_id(n)`, `ev_id(n, evidence_type, seq=None)` (advisories
`seq` 1/2), `msg_id(n, k)`, `call_id(n, k)`. Constants `RD`, `NS`,
`PRODUCTS`, `SOURCES`, `ISSUE_CODES`, `GPS_GAP_GRADES`, `ADVISORY_TYPES`,
`RULINGS`, `DIFFICULTIES`, `FORBIDDEN`, and the payload key tuples
`TRIP_KEYS`, `GPS_KEYS`, `CHAT_KEYS`, `MSG_KEYS`, `FARE_KEYS`, `RPROF_KEYS`,
`DPROF_KEYS`, `ADVIS_KEYS`, `PP_KEYS`, `ERP_KEYS`.

### money (Decimal)
- `D(x)`: Decimal from Decimal/int/str; a float goes through `repr` (3.12 ->
  `Decimal('3.12')`). Do arithmetic in Decimal.
- `q2(x)`: cents, ROUND_HALF_UP. `up005(x)`: round UP to the next 0.05
  (`up005(3.101) == Decimal('3.15')`, `up005('3.10') == Decimal('3.10')`).
- `num(x)`: the JSON number (float holding `q2(x)`); None passes through. All
  builders call it for you. `money_str(x)` -> `"5.00"` for text.
- `rd_fare_constants()`: route_deviation.json `fare_model` as Decimals.
  `metered_lines(distance_km, duration_min, surge_multiplier=1)`: the billed
  base / distance / time / surge (on base+distance+time) / platform-fee lines in
  cents, ready to splat into `fare_breakdown(**lines)`. A POL-RD-02
  recomputation (unrounded intermediates, `up005` only on the payable) is your
  own arithmetic; do not reuse these cent-rounded lines for it.

### time (all strings `YYYY-MM-DDTHH:MM:SS+08:00`)
`ts('2026-09-02', '08:15:00')`, `parse_ts(s)`, `fmt_ts(dt_or_s)`,
`add_s(t, seconds)`, `add_min(t, minutes)`, `diff_s(a, b)` (= b - a, float).

### geometry
`hav_km(a, b)` (identical to check_set's `km`, R = 6371.0088; a/b are
`{lat,lng}` dicts or `(lat, lng)` tuples), `hav_m`, `offset_m(lat, lng,
north_m, east_m)`, `polyline_km(waypoints)`, `ll(lat, lng)`.

### GPS synthesis
- `drive(waypoints, t0, speed_kph, cadence_s, *, rng=None, jitter_m=0,
  accuracy_m=5.0, speed_noise_kph=0, include_start=True, include_end=True,
  venue_id=None)`: fixes along the polyline. `speed_kph` is a number, a list
  (one per segment) or `f(km_along, total_km)`. Integrated in 1 s steps; a fix
  every `cadence_s` s plus a final fix exactly on the last waypoint.
  `accuracy_m` may be a number, `(lo, hi)` (seeded uniform, 1 dp) or None.
  Jitter, accuracy ranges and speed noise need `rng=common.rng(n, salt)`.
- `dwell(lat, lng, t0, duration_s, cadence_s, *, rng, jitter_m, accuracy_m,
  include_start=True)`: stationary fixes, speed 0, from t0 to t0+duration.
- `walk(...)` / `to_rider_track(points)`: rider-track points `{lat, lng, ts,
  accuracy_m}`.
- `concat(*lists)` (drops a duplicate ts at the joins, asserts strictly
  increasing), `drop_between(points, t_from, t_to)` (cut a gap),
  `shift_points(points, seconds)` (device clock skew),
  `set_field(points, key, value, t_from=None, t_to=None)` (e.g. accuracy_m
  None for a stretch).

### GPS measurement (use these to write admissibility notes and to keep
policy thresholds deliberate)
`trace_distance(points)` (3 dp, what `trace_distance_km` must hold),
`intervals`, `gap_list(points, threshold_s)`, `max_gap`, `sample_interval`
(median, 1 dp), `max_jump_m`, `max_implied_kph`, `min_dist_m(coord, points)`,
`nearest_fix(points, at)` -> `(fix, abs_seconds)`, `points_between`,
`window_stats(points, t_from, t_to)` -> `{fixes, max_gap_s, max_jump_m,
median_interval_s, lead_s, tail_s}` (pairs straddling a window edge count),
`longest_run_within(points, center, radius_m, max_accuracy_m=None)` ->
`(run_len, first_ts, last_ts)`.

### admissibility
- `weight_for(issues, gps_gap_grade=None)`: product of
  `no_show.json integrity.weights` (read at runtime), 2 dp.
  `GPS_GAP` requires `gps_gap_grade` in `SHORT_OR_OUTSIDE_WINDOW`,
  `LONG_INSIDE_WINDOW`, `STRADDLING_CANCELLATION`.
- `adm_complete(notes, assessed_at)`, `adm_impaired(issues, notes,
  assessed_at, gps_gap_grade=None, issue_details=None)` (weight computed),
  `adm_missing(notes, assessed_at)`, `issue_detail(code, severity, detail)`.
- `artifact(n, evidence_type, payload, adm, *, source, generated_at,
  seq=None, schema_version="1.2.0")`: the eight-key artifact; payload None iff
  MISSING; TRIP_RECORD / FARE_BREAKDOWN never MISSING; a different
  `schema_version` needs `SCHEMA_VERSION_MISMATCH`.

### payloads (full sample key sets; every key you do not pass is null)
- `trip_record(n, **fields)`: any of `TRIP_KEYS` except `trip_id`;
  `in_app_calls` / `events` default to `[]`; timestamps formatted;
  `optimal_route_erp_sgd` written as money. Helpers `place(label, lat, lng,
  venue_id=None)`, `in_app_call(n, k, at, by, answered, duration_sec)`,
  `event(event_type, at, detail, source="PLATFORM_TELEMETRY")`,
  `platform_policy(source="RECORD-PLATFORM", **overrides)` (ten keys, starting
  from `no_show.json fee_schedule.defaults`; required on every NO_SHOW trip).
- `gps_trace(n, points, *, rider_track=None, expected_interval_sec=None,
  coverage_pct=None, gap_threshold_s=None)`: counts, first/last fix, median
  interval, `gaps` (intervals > threshold; default 2 x expected or median
  interval), `max_gap_sec` and `trace_distance_km` computed from the points.
  Build it from the final point list.
- `msg(sender, text, sent_at, *, read_at, delivered_at, channel="IN_APP",
  language="en", redacted=False, waypoint_hint=None, k=None)` and
  `chat_log(n, messages, truncated=False)` (ids numbered in order; pass `k=` to
  pin a number, e.g. a TRUNCATED_LOG that skips).
- `fare_breakdown(n, *, fare_model, base_fare, distance_fare, time_fare,
  surge_amount, airport_surcharge, platform_fee, cancellation_fee,
  waiting_time_fee, promo_discount, erp_gantries, total_charged=None, ...)`:
  `tolls_erp` = sum of gantries, `total_charged` computed (or asserted to the
  cent). `erp_gantry(gantry_id, name, lat, lng, charged_at, amount_sgd)`.
- `rider_profile(party_id, snapshot_at, **fields)`,
  `driver_profile(party_id, snapshot_at, **fields)` (ids `R-dddd` / `D-dddd`).
- `advisory(advisory_id, type, road, segment, frm, to, valid_from, valid_to,
  issued_at, source_ref, shortest_lawful_alternative_km=None)`.

### dispute, case, key
- `counterparty(text, submitted_by, submitted_at)`.
- `make_case(n, category, evidence, *, filed_at, filed_by, channel,
  amount_contested_sgd, claim_text, counterparty_statement=None,
  safety_flag=None, complaint_flag=None)`: sorts evidence canonically, fills
  `evidence_ids`, runs `validate_case` + `lint_case` and raises `BuildError`
  listing every problem.
- `key_record(n, ruling, amount, dc, referrals, clauses, difficulty,
  rationale)`: amounts as Decimal/str/None.
- `validate_case(case)`: in-memory mirror of check_set's case rules, exact
  where check_set has a tolerance (fare to the cent, trace distance equal to
  the 3-dp recomputation, IMPAIRED weight equal to the integrity product).
- `lint_case(case)`: BRIEF rules beyond check_set - +08:00 second-precision
  timestamps, Singapore coordinates, trip dates 2026-08-01..2026-10-05 and
  filing within 30 days, products, party ids and profile ids agreeing,
  phone-number / plate patterns in text, full payload shapes, implied speed
  between fixes over 130 km/h without IMPLAUSIBLE_SPEED / GPS_DRIFT.
- `validate_key(record, case=None)`: check_set's key rules plus: PARTIAL below
  contested, bare clause ids from version 6 (`clause_table()`, read from the
  base files and the three amendments), clauses only from the case's own
  category or POL-GEN, a licensing clause other than POL-GEN-03 alone, every
  evidence id in the rationale present in the case, ASCII.
- `text_problems(where, obj)`, `forbidden_hits(text)`, `non_ascii(text)`.

## Minimal case module (shape only; the facts here mean nothing)

```python
# build/cases_rd.py
import common as C


def case_4001():
    n = 4001
    r = C.rng(n, "trace")
    t_req = C.ts("2026-09-02", "08:10:00")
    t_acc, t_arr = C.add_s(t_req, 20), C.add_s(t_req, 260)
    t_start = C.add_s(t_arr, 60)
    route = [(1.3324, 103.8474), (1.3390, 103.8490), (1.3507, 103.8486)]
    pts = C.drive(route, t_start, [40, 35], 5, rng=r, jitter_m=2, accuracy_m=(3, 8))
    t_end = pts[-1]["ts"]
    gps = C.gps_trace(n, pts, expected_interval_sec=5)
    gen = C.add_min(t_end, 30)
    lines = C.metered_lines(C.q2(str(gps["trace_distance_km"])), C.q2(C.diff_s(t_start, t_end) / 60))
    trip = C.trip_record(n, rider_id="R-1001", driver_id="D-2001", requested_at=t_req, accepted_at=t_acc,
                         arrived_at=t_arr, started_at=t_start, ended_at=t_end, status="COMPLETED",
                         pickup=C.place("Pickup label", *route[0]), dropoff=C.place("Dropoff label", *route[-1]),
                         vehicle_type="RYDE_X", chat_message_count=1)
    ev = [
        C.artifact(n, "TRIP_RECORD", trip, C.adm_complete("What the pre-pass measured.", gen),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "GPS_TRACE", gps, C.adm_complete("Fix count, cadence, max gap.", gen),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "CHAT_LOG", C.chat_log(n, [C.msg("RIDER", "omw", C.add_s(t_arr, 10))]),
                   C.adm_complete("One message.", gen), source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "FARE_BREAKDOWN", C.fare_breakdown(n, charged_at=t_end, **lines),
                   C.adm_complete("Ledger lines reconcile.", gen), source="PAYMENTS_LEDGER", generated_at=gen),
        C.artifact(n, "RIDER_PROFILE", C.rider_profile("R-1001", gen), C.adm_complete("Counters.", gen),
                   source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "DRIVER_PROFILE", C.driver_profile("D-2001", gen, vehicle_type="RYDE_X"),
                   C.adm_complete("Counters.", gen), source="PLATFORM_TELEMETRY", generated_at=gen),
        C.artifact(n, "TRAFFIC_ADVISORY", None, C.adm_missing("Artifact absent.", gen),
                   source="THIRD_PARTY_LTA", generated_at=gen, seq=1),
    ]
    case = C.make_case(n, C.RD, ev, filed_at=C.add_min(t_end, 90), filed_by="RIDER",
                       channel="IN_APP_SUPPORT", amount_contested_sgd="2.00", claim_text="...",
                       counterparty_statement=None)
    key = C.key_record(n, "NO_ACTION", None, None, [], ["POL-RD-01"], "EASY",
                       "Placeholder of 120 to 2500 ASCII characters: name this case's evidence ids such as "
                       "EV-GPS-04001, the deciding clause ids such as POL-RD-01, the deciding numbers and the "
                       "arithmetic.")
    return case, key


def build():
    return [case_4001()]
```

Notes
- `admissibility.notes` state what the pre-pass measured (gap lengths, fix
  counts, skew seconds, null fields), never the outcome.
- No word from `FORBIDDEN` anywhere in a case (any case, as a substring):
  "difficulty" in a chat line fails the set.
- Text is ASCII only; no names, phone numbers or plates.

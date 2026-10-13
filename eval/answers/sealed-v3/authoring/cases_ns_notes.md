# cases_ns.py: generator notes (NO_SHOW_CHARGE 4051-4065), internal

Answer-bearing; stays under `build/`.

## Files

- `build/cases_ns.py`: `build()` for generate.py. Builds each case from `build/blueprint_ns.json`, measures the case
  as written, decides the key, fills the texts from templates, and asserts everything against the blueprint.
- `build/ns_geo.py`: timed-leg GPS synthesis (port of the blueprint's emission model) and the POL-NS-02 measurements.
- `build/ns_texts.py`: one template per text (claim, counterparty, event details, chat lines, admissibility notes,
  issue details, rationale). Each `{name}` is filled by `cases_ns.values()` from the written case. It was produced by
  `tmp/nsgen/templatize.py` (context rules in `tmp/nsgen/rules.py`), then reviewed case by case.
- `build/audit_ns.py` and `build/audit_ns_selftest.txt`: the independent audit and its fail-proof.

## How each number is produced

- GPS: driver fixes come from the design legs and emission blocks, using `common.rng(n, 'drv')`. Rider fixes use
  `common.rng(n, 'rdr')`. 4062's drift uses `'approach-drift'` and `'drift'`, with the drift constants in ns_geo.
  Walking riders (4052, 4064, 4065) use their exact walk centres. All 1,060 driver fixes and 107 rider fixes equal
  the blueprint's points exactly. The payload summary and `trace_distance_km` come from `common.gps_trace`.
- platform_policy: the AUTHORED-V1 greater-of rule for 4065. 4061's gross is 6.00 x 6.61/4.50 = 8.81.
- Fare lines: the fee line is the policy's net or gross figure. 4063's metered lines come from the trip's own fixes
  and the rate card, plus `waiting_fee_sgd`. Totals, refunds and the contested amount are computed. Weights use the
  integrity product rule.
- 4063's trip distances and chat_message_count are computed. The count is the highest message number issued, so
  4064 shows 6.
- Every figure in a text is a filled value. The only literals left are place labels, message-id suffixes, ETA
  minutes (the platform's stated estimate, which the 4054 decision reads back), amendment numbers, enumerations and
  numbers inside the parties' own words.
- Key: `decide()` runs on the written case (JSON round trip). The NS-07 payout is 0.80 x net. 4056's goodwill is
  0.50 x net. Refunds equal the written fee line. Ruling, amounts, referrals and the NS-08 limbs are asserted equal to
  the intent. Clauses and difficulty are the intent's labels. The rationale is the filled template.
- Verification inside the module: every value in `gps_trace.measurements` is re-measured on the written case and
  compared. The built files are byte-identical to the r2 prototype build (`tmp/ns_r2x/proto_out`), apart from the two
  text corrections below.

## Corrections to the blueprint (`TEXT_FIXES` in cases_ns.py)

Recomputing the texts' figures from the written case found two statements the record does not support. Neither one
touches a deciding fact, a ruling or an amount.

1. 4061 CHAT_LOG note. The note said "Largest interval 330 s (12:58:30 to 13:04:00)". The largest interval in the log
   is actually 475 s, from 13:06:15 to the 13:14:10 SYSTEM line. The note now says that. The interval that spans the
   arrival event (135 s) is unchanged, so POL-NS-08(c) is still not engaged.
2. 4057 rationale. It said the rider's fixes "are all filtered at 35-50 m accuracy". That was the design band. The
   written fixes report 35.4-44.8 m, and the text now gives that range.

common.py and generate.py were not changed. foundation_fixes.md has no entry from this work.

## Checks run

- `python3 build/generate.py --only ns --out tmp/ns`: 15 cases, check_set 0 failures (determinism rebuild passed).
- `python3 ref/check_set.py tmp/ns/cases tmp/ns/answers/ground_truth.json --range 4001 4099`: the only failure is
  "both categories are required". A both-category build in `tmp/nsgen/both` gives 30 cases and 0 failures.
- `python3 build/audit_ns.py tmp/ns`: 662 checks, 0 failures. On a moved fix (4057) and a changed fare line
  (4052) it fails, as recorded in `audit_ns_selftest.txt`.
- `python3 build/test_common.py`: OK.

## Read-through

I read every case's texts in full: claims, counterparty statements, events, chat, notes, issue details and
rationales. I checked them against the timeline. The parties' minutes and amounts agree with the record, except
where a party's account is meant to be contradicted (4063, 4054, 4064). The notes state measurements, not outcomes.
The chat uses Singapore usage ("leh", "ah", "liao", "omw", "abt", "kena"). No forbidden word appears, and every text
is ASCII. Contact details are redacted (4063). Beyond the two corrections above, nothing needed changing.

## Process note

I read one file outside the workspace, disclosed here as the earlier revisions did. The harness saved the long
output of my own `cat` of `build/revisions_ns_r1.md` and `build/revisions_ns_r2.md` to a tool-results file under the
session's `~/.claude/projects/.../tool-results/` folder, and I opened that file with the Read tool. It held only those
two workspace files. No other file outside the workspace was opened, listed, searched or changed, and there was no
web access.

*Translated into English from the author's `README.md` in the archive. Nothing but the language has changed: the sections, the tables and the list of policy findings are the author's, in full. The author's original bytes are the blob at commit `3cb059a` and hash to `8761344077eb9ef2a238c047a18b71b0f6b8f1855d1baeb63ab0ba89e1c9befb`.*

# Tribunal's real-dispute test set wild-v1 (64 cases)

**Source**: 272 real ride-hailing complaint posts → 84 English questions (`en/cases.jsonl`) → 64 case files plus the answer key, generated to schema 1.2.0. Each case's `seed_map.json` traces it back to the English question and the original post it came from.

**Its relation to the sealed set**: the sealed set (24 cases) is run once, after the freeze; this one is **for development and regression**, and may be run repeatedly, may be read with the answers in hand, and may be used to tune the prompts against its misses. Its traps come from real complaints; I did not invent them.

## Contents

```
data/wild/
  index.json               list the agent may read (identity fields only)
  cases/case-005xx.json    ROUTE_DEVIATION x37 (501-537, 14 of them billing/ERP/flat-fare/range)
  cases/case-006xx.json    NO_SHOW_CHARGE  x27 (601-627)
eval/wild/
  ground_truth.json        the full answer key (ruling / amount / driver_comp / referrals / clauses / difficulty / rationale)
  eval_index.json          the reduced index used for grading
  summary.csv              one row per case: case number, source question, ruling, amount, difficulty, clauses
  seed_map.json            case number -> English question number
  MANIFEST.json            hashes + distribution
gen/                       the generator (spec-driven); edit specs_*.py and re-run build.py
```

`case_set_sha256`  `77bc2dbb603393a4eea252136a0936623854cc42a05b445ab34466a019188bea`
`answer_key_sha256` `d8037d23e5aab93ba90e8cc28644ec2fb48a6661c1c43979dc12589f86e3ffde`

## Validation status

- 64/64 pass `schema.json` (`$defs/case_file`) and every cross-check in SCHEMA.md §9 (`gen/validate.py`)
- The case files' raw bytes hold no answer field
- `gen/semcheck.py` reads only the case files, never the generator, and recomputes the ruling independently from the policy: 61/64 agree; the 3 disagreements are the RD-06(b) aggravation (502, 515) and the RD-04 driver compensation (520), which the check script deliberately does not model
- Every number in a rationale (trace length, excess ratio, recomputed fare, refund, dwell seconds, distance and speed at the arrival moment) is computed from the generated data and filled in; none is written by hand

## Distribution

| | RD | NS | Total |
|---|---|---|---|
| FULL_REFUND | 3 | 20 | 23 |
| PARTIAL_REFUND | 20 | 0 | 20 |
| NO_ACTION | 12 | 2 | 14 |
| DRIVER_COMPENSATION | 1 | 2 | 3 |
| ESCALATE | 1 | 3 | 4 |

Difficulty EASY 11 · HARD 37 · REVERSAL 12 · INDETERMINATE 4. Four cases are driver appeals (of 520, 608, 618 and 624, the 608 and 618 are driver appeals against NO_ACTION).

## What this set tests (and the sealed set does not)

| Trap | Cases |
|---|---|
| The flat fare was exceeded but the GPS did not deviate — refund under RD-11, not NO_ACTION | 506, 510, 517, 524, 525, 533 |
| Flat fare plus a phantom ERP (the gantry is not within 250 m of the trace) | 516, 521, 532 |
| Flat fare plus an ERP from a detour the driver took on his own: refund under RD-11(b), the distance is not refunded | 501 |
| Metered fare, estimated fare, wrong vehicle class, a pooled ride charged as solo — all NO_ACTION | 511, 526, 527, 528, 529, 537 |
| The driver took the expressway on his own, an ERP, but the distance excess is <20%: the policy has no refund path → NO_ACTION | 523 |
| Cash or off-platform charging: the platform's bill is correct → NO_ACTION; the cash is outside the ruling's scope | 522, 531 |
| The RD-06 pattern plus a material deviation → FULL_REFUND aggravated, with the two figures side by side | 502, 515 |
| ERP anti-double-counting (RD-09(1)) | 515 |
| A driver appeal for RD-04 compensation for unmetered distance | 520 |
| A trace gap covering the disputed stretch → ESCALATE | 512 |
| A passenger claims for a missed bus or flight → only the fare difference is refunded | 505, 509, 535 |
| The passenger's own statement that the driver did not detour | 511 |
| The passenger cancels and the driver never arrived → NS-02 FULL (NS-01(d) was never satisfied anyway) | 602, 605, 609, 610, 611, 615, 622* |
| A false arrival (>300 m or ≥15 km/h) with no qualifying fix anywhere in the trip → NS-05(ii) plus a referral | 606, 612, 614, 616, 625 |
| The wrong entrance (≤400 m) and the passenger stated the location in the chat → the driver is not compensated | 604, 619, 620 |
| Cancelled or left less than 300 s after arrival | 601, 603, 607, 613, 617 |
| **A qualifying arrival at 48 m, the full wait served, the driver answered the message, and the passenger standing right there → the policy finds for the driver** | 621 |
| A driver appeal on a trip the passenger cancelled, or that had already completed → NO_ACTION | 608, 618 |
| The passenger's 30-day complaint count is 2 (one short of 3) → no escalation, the driver is compensated | 624 |
| The driver's counter-brushing count triggers NS-09(d) → ESCALATE even though the passenger is plainly right | 622 |
| GPS MISSING, or conflicting arrival records → ESCALATE | 626, 627 |

## Findings about the policy (hit while writing the questions; I suggest they go into DECISIONS.md)

1. **The charge for a passenger cancellation**: NS-01(d) requires the driver to terminate with a no-show code, so any "charged after the passenger cancelled" refunds under the existing policy — the policy has no concept of a late-cancellation fee. This set is written to the policy, but as a product this is a hole.
2. **The driver arrives after 41 minutes, serves the full 5-minute wait, and the passenger left long before**: NS-01 is satisfied in every limb and the policy compensates the driver. This set does not pose that question (613 was changed to a 240 s wait); whether to add an "arrival deadline" is your call.
3. **The 48 m boundary (621)**: a qualifying arrival, the full wait, and a reply → the driver wins, even with the passenger standing 5 metres away. That is the policy's intent (NS-06 is strict liability, and so is its converse), but judges will ask about it in a demo.
4. **Putting a passenger out mid-trip, or charging the whole fare for a trip never taken**: neither policy category covers it, and only RD-10(8) (no matching bill line) escalates it; this set does not pose it, because the fare identity would fail first at the validation layer.
5. **An RD-06(c) referral requires a pattern first**: bad driver conduct with no pattern (charging off-platform, abuse) has, under the existing policy, **nowhere to be referred**. Every NO_ACTION cash case in this set therefore carries no referral.

## Suggested use

- Run the eight calibration cases first: 506, 521, 523, 602, 606, 621, 622, 511
- Report RD and NS separately, then give the billing group (521–537) a line of its own — that is the question type the sealed set does not have
- The rationale is part of the answer key, but grading compares only the four fields (ruling / amount / driver_comp / referrals)
- The original posts do not enter the repository; the statements in `en/cases.jsonl` have been rewritten into a Singapore setting and may

## Re-running

```
export TRIBUNAL_REPO=/path/to/Tribunal      # it reads data/schema.json and policy/*.json
cd gen && python3 validate.py               # the 21 cross-checks
python3 semcheck.py                         # recompute the rulings independently
python3 build.py                            # regenerate after editing specs_*.py (overwrites data/ and eval/)
```

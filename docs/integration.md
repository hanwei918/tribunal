# How Ryde would plug it in

Everything below is read from the files named beside it. Nothing here is a plan
that the repository does not already carry.

## The input contract

A dispute enters as one public case file, and the contract for it is
[`data/PUBLIC-CONTRACT.md`](../data/PUBLIC-CONTRACT.md). A case has exactly four
top-level keys — `schema_version`, `case_no`, `dispute` and `evidence` — and
[`tribunal/loader.py`](../tribunal/loader.py) confirms that the requested case
number, the manifest entry, the filename and the file's own `case_no` all agree
before anything else happens.

[`data/PUBLIC-CONTRACT.md`](../data/PUBLIC-CONTRACT.md) also carries the shape of
the eleven-key `dispute` object and of an eight-key evidence artifact, and the
boundary a runtime bundle may not cross. A case of Ryde's own format enters
through the converter [`eval/external/ryde/convert.py`](../eval/external/ryde/convert.py),
which records every judgement it had to make in the mapping record beside the
converted case; the converted case is answer-free and is named by its path, never
by a manifest lookup.

## What a ruling is, field by field

A case record under `runs/` carries the ruling as its `ruling` block, and the
block's own `ruling` object carries the fields a caller needs:

| field | what it holds |
|---|---|
| `ruling` | one of `POL-GEN-03`'s five values |
| `amount_sgd` | the money the ruling moves, or `null` |
| `driver_compensation_sgd` | the driver's share of it, or `null` |
| `referrals` | a list of instructions to a person, each naming the clause it rests on |
| `confidence` | the judge's own confidence in the ruling |
| `explanation` | the ruling written out for both parties |

One real record, case 208 of the corpus at policy version 6
([`case-00208.json`](../runs/policy-v6/deepseek-deepseek-flash/case-00208.json)):

- `ruling` — `DRIVER_COMPENSATION`
- `amount_sgd` — 6.4
- `driver_compensation_sgd` — 6.4
- `referrals` — `[]`
- `confidence` — 0.95
- `explanation` — "This was a verified no-show: the SGD 8.00 cancellation fee
  stands and the driver is paid SGD 6.40."

A caller reads the same fields off every case: `ruling` says what happened,
`amount_sgd` and `driver_compensation_sgd` say what it moves, and `explanation`
is what both parties are told.

## What routes a case to a person

Three things take a case out of the automatic lane, and they happen at different
points.

- **The scope gate, before any model call.** `POL-GEN-08(1)` holds that a dispute
  carrying `dispute.safety_flag` or `dispute.complaint_flag` is never adjudicated
  automatically: it is routed to human review with the record assembled and no
  draft ruling issued. The gate fires in
  [`tribunal/pipeline.py`](../tribunal/pipeline.py) before any prompt is rendered,
  so no advocate, judge or verifier is called at all.
- **The execution threshold, after the ruling.** `POL-GEN-05` executes a
  provisional ruling automatically only when its monetary effect does not exceed
  `execution_threshold_sgd`, which is **SGD 8.00** at policy version 6
  ([`policy/v3/general.json`](../policy/v3/general.json)). Above it the ruling is
  issued but not executed: the amount is held and the case is placed in the human
  queue for release.
- **The panel itself.** A case whose drafts split, or produce none the code
  checks accept, gets no ruling at all and escalates with the fee held.

## The kill switch

`auto_rulings_enabled` in [`ops/config.json`](../ops/config.json) is the switch
that stops automatic rulings. With it false, every dispute the pipeline would
have ruled on moves into `HUMAN_REVIEW` with the reason `AUTO_PAUSED`. It is the
router declining to hand the dispute on, and it is recorded there and nowhere
else: nothing in `tribunal/` reads that file, so pausing the queue cannot change a
request or a ruling.

**A rollout would start in shadow mode**: `auto_rulings_enabled` false, so every
case is adjudicated and nothing is executed until a person has read the record
([the description](submission/description.md), "Business value").

## The queue, the packet and the appeal

- **The queue** is [`ops/queue.py`](../ops/queue.py), run as
  `python3 -m ops.queue --run-dir <dir>`. It puts every dispute in one of three
  lanes — `AUTO`, `HUMAN_REVIEW`, `SAFETY_FAST_TRACK` — says what each one's due
  time is, and orders the human lane by its own four tiers. Its targets are the
  team's own and are stated in [`ops/config.json`](../ops/config.json):
  `auto_ruling_minutes` 5, `human_review_hours` 24, `safety_hours` 2 and
  `end_to_end_hours` 48, the last being `POL-GEN-06(2)`'s own first-instance
  limit.
- **The reviewer's packet** is [`ops/escalation.py`](../ops/escalation.py), run as
  `python3 -m ops.escalation --run-dir <dir> --case N --format md`. It carries
  the case summary, both advocate briefs, the admissibility report, the clause ids
  relied on and the judge's draft reasoning, with the judge's explanation verbatim
  because that is where the open question is stated.
- **The closure** is [`ops/review.py`](../ops/review.py), run as `python3 -m
  ops.review --run-dir <dir> --case N --packet-sha256 <hex>` plus
  `tribunal.precedents close`'s own arguments. It refuses a closure unless the
  digest is the SHA-256 of the packet built for the case **now**, so a decision
  cannot be recorded against a packet nobody read.
- **The appeal** is [`ops/appeal.py`](../ops/appeal.py), run as `python3 -m
  ops.appeal --run-dir <dir> --case N --filed-by rider|driver --lodged-at <ISO
  instant> --now <ISO instant> --evidence <kind>[,<kind>...] --reviewer <id>`. It
  checks the appeal against each limb of `POL-GEN-04` — one appeal, within 30
  days, record-type evidence only, a reviewer who did not take part earlier — and
  names the reviewer who hears it. It decides nothing about the merits.

A missing piece of evidence never stops the clock:
[`ops/evidence_window.py`](../ops/evidence_window.py) opens one window to both
parties and closes it on [`ops/config.json`](../ops/config.json)'s
`close_hours_after_filing` figure of 36 hours, which is operations rule
`OPS-EW-01` and not a clause of the frozen policy.

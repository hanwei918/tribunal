# The first amendment — POL-RD-13, from the policy-gap loop's first full pass

**2026-10-03. The pass was run by the owner outside this session's sandbox. No
model call was made by WorkBuddy: everything below is read out of the committed
files, and the one model call in the whole pass — the drafter's — is the owner's,
recorded in the transcript committed beside the proposal.**

**Every figure in this note is in-sample development data.** The amendment was
drafted from closures on the same cases the diff is computed over, so the
newly-matching counts are not comparable to the headline and are not a
generalisation figure.

## What the loop did, in order

1. **Close.** Two held-out cases the system had escalated, 508 and 530, were
   closed by hand as `PARTIAL_REFUND`, 6.00 and 5.80, and written to
   `precedents/precedents.jsonl` as `P-0001` and `P-0002`.
2. **Report.** `python -m eval.policy_gaps report` read the three committed runs
   and wrote `runs/policy-gaps/2026-10-01-wild-v1/`. No model call.
3. **Draft.** For cluster `C4`, one call to `deepseek/deepseek-flash` produced
   `policy/proposals/0001-pol-rd-13.json` and
   `policy/proposals/0001-pol-rd-13.transcript.json`.
4. **Approve.** The owner approved the proposal, giving
   `policy/amendments/0001-pol-rd-13.json` and **policy version 2**.
5. **Rerun.** The affected cases were re-run at version 2.
6. **Diff.** `runs/policy-v2/diff.md` and `runs/policy-v2/diff.json` grade each
   case against the frozen version-1 key before and after.

## The closures

Both cases are `ROUTE_DEVIATION` on a held-out run, and both escalated because
the judge's panel fell below the confidence floor. In each, the driver asserts
an external traffic cause against a `traffic_advisory` that is `MISSING`: the
CTE queue at Braddell in 508, the Balestier bus breakdown in 530. `POL-RD-08`
already provides that an uncited traffic assertion does not discharge the
driver's burden, but `POL-RD-10(5)` lists "a closure asserted with no
`traffic_advisory`" among its escalation triggers — so the same facts read one
way pay a `POL-RD-02` refund and read the other way escalate with no money
moving.

| id | case | set | system outcome | human decision | closed by |
|---|---|---|---|---|---|
| `P-0001` | 508 | wild | `ESCALATE` | `PARTIAL_REFUND` 6.00 | Zhou Hanwei |
| `P-0002` | 530 | wild | `ESCALATE` | `PARTIAL_REFUND` 5.80 | Zhou Hanwei |

The store is append-only and hash-chained; `events.verify_chain` reports it
intact.

## The report

`runs/policy-gaps/2026-10-01-wild-v1/report.json` reads the three runs —
`runs/deepseek-deepseek-flash` (29 cached, 5 undecided),
`runs/codex/deepseek-deepseek-flash` (15 cached, 4 undecided) and
`runs/wild/deepseek-deepseek-flash` (62 cached, 7 undecided) — and groups the
undecided cases into 13 clusters. Cluster **C4** is
`ROUTE_DEVIATION / below_confidence_floor`, 6 cases, flagged because it holds
at least the two cases a person has closed:

| case | set | system outcome | confidence | closure |
|---|---|---|---|---|
| 110 | corpus | `ESCALATE` | 0.39 | awaiting review |
| 112 | corpus | `ESCALATE` | 0.40 | awaiting review |
| 508 | wild | `ESCALATE` | 0.60 | `PARTIAL_REFUND` (`P-0001`) |
| 512 | wild | `ESCALATE` | 0.39 | awaiting review |
| 530 | wild | `ESCALATE` | 0.00 | `PARTIAL_REFUND` (`P-0002`) |
| 9115 | codex | `ESCALATE` | 0.60 | awaiting review |

The report made no model call, and reads no answer key.

## The drafted clause, in full

One clause, added and never editing another. Its id is the next free
`POL-RD-` number in the committed policy, its category agrees with
`policy/route_deviation.json`, and its `licenses` are within what `POL-GEN-03`
licenses.

```json
{
  "id": "POL-RD-13",
  "title": "Missing Traffic Advisory and Uncited Traffic Excuses",
  "category": "ROUTE_DEVIATION",
  "rule": "Where a party asserts an external traffic cause - a queue, a breakdown, a closure or an incident - as the explanation for a measured route deviation, the assertion is tested against the traffic_advisory for this trip and nothing else. POL-RD-03 requires an advisory record that names a road or segment the optimal route traverses, carries a validity window overlapping the time the gps_trace shows the vehicle would have reached that segment, and is matched by a route that leaves the optimal corridor before the affected segment and rejoins it after. Where the bundle holds no traffic_advisory covering the trip window - the artifact's admissibility status is MISSING and its weight_multiplier is 0.0 - that comparison cannot be run on the record, POL-RD-03 is unavailable, and the assertion carries no weight under POL-RD-08. Two consequences follow, and no others. (1) Where the asserting party names no evidence ID for an advisory, the missing advisory is NOT an exculpatory clause invoked against a cited artifact within POL-RD-10(5): an assertion that cites no artifact cannot be invoked against one, and the absence of an artifact no party has cited is a gap in the bundle rather than a contradiction in it. This clause does not narrow POL-RD-10(5) where the party does cite the missing identifier; that case still escalates. (2) Where the rider has shown an excess meeting the POL-RD-01 threshold on a gps_trace that is not impaired under POL-RD-07(a) to (c), the deviation stands at the measured figure and POL-RD-02 runs against the booked optimal route; the driver's traffic assertion neither reduces the excess nor supplies an amended optimal, and the ruling must record that the assertion was discarded and that no advisory was on file. This clause does not displace POL-RD-07: where the gps_trace IS impaired under POL-RD-07(a) to (c) and no independent corroboration of the kind POL-RD-07(ii) names exists, POL-RD-10(3) still governs and the case still escalates.",
  "requires": ["traffic_advisory", "gps_trace", "trip_record"],
  "licenses": ["FULL_REFUND", "PARTIAL_REFUND", "NO_ACTION"],
  "favours": "RIDER",
  "notes": "Added because every case in this cluster ships a MISSING traffic_advisory whose identifier was minted so the absence itself could be cited, and every one carries a driver assertion of an external traffic cause - the CTE queue at Braddell in case 508, the Balestier bus breakdown in 530, the KPE signal loss in 110, the 'app acting up' in 112, the hung phone in 512 and the unaccounted telemetry gap in 9115. POL-RD-08 already provides that an uncited traffic assertion does not discharge the driver's burden, but POL-RD-10(5) lists 'a closure asserted with no traffic_advisory' among its escalation triggers, so the same facts read one way pay a POL-RD-02 refund and read the other way escalate with no money moving. The human closures in this cluster settled the point: 508 and 530 were decided as established deviations with the ordinary POL-RD-02 refund, the absent advisory making the driver's excuse weightless under POL-RD-08 and not a POL-RD-10(5) escalation. This clause states that priority for the whole cluster and leaves POL-RD-07 and POL-RD-10(3) untouched for cases 110, 112, 512 and 9115, where the trace itself is impaired and the missing advisory is not the deciding defect."
}
```

The proposal records `reproduces: ["P-0001", "P-0002"]`, `does_not_reproduce:
[]`, `interacts_with` the clauses it reads or narrows, the report it came from
and that report's digest. The transcript holds the one `POLICY_DRAFTER` entry —
one attempt, `PARSED`.

## The approval

The owner approved it as amendment `0001`, and the repository moved to **policy
version 2**. `policy/amendments/0001-pol-rd-13.json` records who approved it and
when, and the digests that trace it back:

| field | value |
|---|---|
| `approved_by` | Zhou Hanwei |
| `approved_at` | `2026-10-01T14:28:42.170049+00:00` |
| `base_version` | 1 |
| `proposal_file` | `policy/proposals/0001-pol-rd-13.json` |
| `proposal_sha256` | `053fb31087efe9492c01f613ce8e867bf2ea16c07fb37a455d1120d9d47dbe49` |
| `report_file` | `runs/policy-gaps/2026-10-01-wild-v1/report.json` |
| `report_sha256` | `81273eef58f5051038e12b1d6a329fa841fda1a26d8cdc5e8b88f1cd3ddab2e5` |

Both digests are recomputed and checked by `tests/test_policy_versions.py`.

## The 57-case plan

`plan_rerun` took the three committed runs and selected every case whose
category is the amendment's. The three sources and their destinations:

| source | set read as | set run as | cases | destination |
|---|---|---|---|---|
| `runs/deepseek-deepseek-flash` | corpus | corpus | 15 (101–115) | `runs/policy-v2/deepseek-deepseek-flash` |
| `runs/codex/deepseek-deepseek-flash` | codex | codex | 5 (9111–9115) | `runs/codex/policy-v2/deepseek-deepseek-flash` |
| `runs/wild/deepseek-deepseek-flash` | wild | wild-dev | 37 (501–537) | `runs/wild-dev/policy-v2/deepseek-deepseek-flash` |

**57 cases, 57 completed, no failures.** The held-out source is re-run as its
re-runnable twin `wild-dev`; nothing is written under `runs/wild/`. The whole
pass ran from `2026-10-02 21:09:56` to `2026-10-03 02:46:43` (local, Friday
evening into Saturday morning), each set's `run.json` recording `completed`
with an empty `failures` list.

## The diff

`runs/policy-v2/diff.md` grades each of the 57 cases against the frozen
version-1 key at version 1 and again at version 2, and compares the four graded
fields. Over all 57 cases (55 graded against the key):

- **changed: 9**, **newly matching: 4** (501, 504, 508, 530), **newly missing: 1** (107);
- escalations before: 8; after: 7.

| case | set | changed | old | new |
|---|---|---|---|---|
| 107 | corpus | yes | `PARTIAL_REFUND` / 7.45 | `ESCALATE` / — |
| 501 | wild-dev | yes | `ESCALATE` / — | `PARTIAL_REFUND` / 14.50 |
| 504 | wild-dev | yes | `ESCALATE` / — | `PARTIAL_REFUND` / 17.60 |
| 508 | wild-dev | yes | `ESCALATE` / — | `PARTIAL_REFUND` / 6.00 |
| 517 | wild-dev | yes | *(no ruling)* | `ESCALATE` / — |
| 523 | wild-dev | yes | `FULL_REFUND` / 4.00 | `ESCALATE` / — |
| 530 | wild-dev | yes | `ESCALATE` / — | `PARTIAL_REFUND` / 5.80 |
| 533 | wild-dev | yes | *(no ruling)* | `PARTIAL_REFUND` / 19.30 |
| 9111 | codex | yes | `PARTIAL_REFUND` / 9.15 / `POL-RD-09(4)` | `PARTIAL_REFUND` / 9.15 / — |

Excluding C4's own six cases, 51 cases remain: 7 changed, 2 newly matching, 1
newly missing, escalations 2 before and 3 after.

## What each changed case did, and why

- **501 and 533 now read the published POL-RD-11 remedy (part B).** Both are
  `UPFRONT_QUOTE` fares, and version 2 publishes `pol_rd_11_remedy` on the money
  block, so a draft's amount can be read off it. 501 moves from a safe
  `ESCALATE` to the key's 14.50; 533, which produced no ruling at all at
  version 1, moves to the key's 19.30. This is part B's change, not the
  amendment's.
- **504, 508 and 530 now decide under the amendment.** All three escalate at
  version 1 and rule `PARTIAL_REFUND` at version 2 — 17.60, 6.00 and 5.80, each
  the key's amount — and each case's version-2 brief carries `POL-RD-13`. 508
  and 530 are the two cases a person closed; 504 is a metered fare the
  amendment also reaches.
- **517 escalates because three of its four drafts were rejected by the
  read-off check.** Three drafts computed **31.50** — the amount at the peak
  airport rate — and `DRAFT_AMOUNT_NOT_READ_OFF` refused each, because 31.50 is
  not a figure the brief's money block publishes. The one valid draft gave the
  key's **33.50**, but one valid draft is below the quorum, so the panel had
  nothing to reduce and the case escalated.
- **523 escalates only because its drafts disagreed.** All four of its drafts
  still refund **4.00**, and they split on the referral field: three carry no
  referral and one carries `POL-RD-09(4)`. With no quorum the case escalated,
  so the defect is not fixed — it moved from a confident `FULL_REFUND` 4.00 at
  version 1 to an escalation at version 2, and neither is the key's
  `NO_ACTION`.
- **107 escalates because one draft returned no JSON object and one
  dissented.** Of four drafts, one was an abstention ("the judge did not return
  a JSON object"), one valid draft dissented to `ESCALATE`, and the two
  remaining valid drafts gave the key's **7.45** — two of three valid drafts is
  not the quorum of three. 107 is the fragile case both ablations already
  carried 3 of 4 in the headline, and it fails under both for reasons that are
  not the same; here the panel splits for a third reason again.
- **9111 changed only in its referral.** Its ruling and amount are the same
  before and after — `PARTIAL_REFUND` 9.15, against a key of 10.15 — and the
  only difference is that the version-1 referral `POL-RD-09(4)` is gone from
  the version-2 result.

## Version 2 carries two changes, not one

**Version 2 holds both this amendment and part B's POL-RD-11 upfront-quote
remedy.** Part B publishes the remedy on every `UPFRONT_QUOTE` fare's money
block from version 2 on; the amendment adds `POL-RD-13` to
`policy/route_deviation.json`. A case that moved between version 1 and version
2 may have moved for either reason, so the newly-matching counts cannot be
attributed to the amendment alone. `runs/policy-v2/diff.md` says so in its own
words, and `runs/policy-v2/diff.json` carries the same note.

## What was committed

Three commits carry the owner's output exactly as produced: the precedent store;
the report, the proposal and its transcript, and the amendment; and the three
new run directories with `runs/policy-v2/rerun.json`, `diff.md` and `diff.json`.
The test that pinned the three shipped stores to a README only was updated to
assert what the stores now are — the precedent chain verifies, and every
amendment's recorded proposal digest matches its proposal file.

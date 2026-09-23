# The runtime model decision — 2026-09-23

## The decision

The system runs on **`deepseek/deepseek-flash`**, served through **Tencent Cloud TokenHub** in the
**Singapore** region.

It is written down once, in `tribunal/model.py`:

```python
RUNTIME_MODEL = "deepseek/deepseek-flash"
MODEL_PROVIDER = "Tencent Cloud TokenHub"
MODEL_REGION = "Singapore"
```

`tribunal.llm.LLMClient` still has **no default model**, and `eval.run_benchmark.run_benchmark` still
requires one. A default inside the transport would be a decision pretending to be a convenience: the
model would be chosen by whoever last edited the transport, and nothing would say so. The choice is
made here instead, and the two entry points read it from this module when no model is named on the
command line. Naming one still overrides it, so a probe, a comparison or a deliberate experiment is
one flag away.

**Why one place and not three.** A decision recorded in three places is three decisions, and the
third one is the one that surprises somebody. A test walks every module under `tribunal/`, `eval/`
and `ui/`, parses it, and requires the model id to be a live value in exactly one file — with a
second test that points the same scan at a temporary package and shows it fires, because a guard
nobody has seen fail is not evidence of anything. A docstring may name the model as an example; an
assignment may not.

## How to read this note

| Mark | Means |
|---|---|
| **MEASURED** | Read off a named file in this repository, or taken from a direct HTTP call whose result is recorded in a note. The source is named each time. |
| **VERIFIED** | Established by inspecting this repository. |
| **LIST PRICE** | A published rate. Not measured here, and not a bill. |
| **ASSUMED** | Not measured. Stated so it can be checked, not relied on. |

Every figure below is a measurement with its source or is marked as something else. Where a figure
that was reported to this session could not be reproduced from the record, that is said in place
rather than smoothed over — see *Figures that could not be reproduced* at the end.

## The deciding run

| | |
|---|---|
| Directory | `runs/deepseek-deepseek-flash/` |
| Commit | `493beeaf94953943116a25cb74353b3dd2279499` |
| Working tree | clean |
| Prompts digest | `b131e63f046a…` |
| Answer key digest | `bfd3fa50ecc7…` |
| Interpreter | CPython 3.11.14 |
| Cases | 29 requested, 29 produced a ruling, 0 failed |
| Cached results | every one `current` — produced by the brief and the prompts this code builds now |
| Wall clock | `2026-09-23T04:00:15Z` to `2026-09-23T05:40:00Z` |

**MEASURED** from `runs/deepseek-deepseek-flash/run.json`, cross-checked against `report.md` and the
29 per-case entries beside it. The tree being clean and every cached result being `current` are the
two properties that make the accuracy figure below a measurement of *this* code rather than of an
unknown revision: a result produced by a dirty tree cannot be reproduced by anyone, and a stale
cached result is a number from a different pipeline.

## Accuracy

| | |
|---|---|
| **Four-field exact match** | **28/29 = 96.6%** |
| `ruling` | 28/29 |
| `amount_sgd` | 28/29 |
| `driver_compensation_sgd` | 29/29 |
| `referrals` | 29/29 |
| Escalation recall | 5/5 = 1.0 |
| Escalation precision | 5/6 = 0.833 |
| Escalation rate | 20.7% against a 17.2% target |
| Over-escalations | 1 — case 211 |
| Under-escalations | 0 |
| INDETERMINATE cases ruled confidently instead of escalated | 0 of 4 — 110, 112, 210, 213 all escalated |

**MEASURED** from `runs/deepseek-deepseek-flash/report.md`, which `eval/grade.py` produces over the
cached results. The four-field figure is the headline; the per-field figures are there to show which
field a failure lands on and are not alternative scores.

Three things about this figure that are stated here rather than left to be discovered:

- **It is one measurement over one case set.** Twenty-nine cases cannot separate a model from a
  corpus. Nothing below claims `deepseek/deepseek-flash` is a better model in general. It claims
  that *this* model produced *this* result on *this* corpus under *this* code, and that the result is
  good enough to stop looking.
- **The escalation rate is off target, and the whole gap is one case.** 20.7% against 17.2% is one
  escalation over the target of five, and it is case 211. Remove case 211 and the rate is exactly
  17.2%. The report says "Off target: yes", and that is the correct thing for it to say; this note
  says where the gap comes from so the number is not read as a general over-escalation habit.
- **Recall is 1.0 and that matters more than the rate.** Every case the key escalates, the run
  escalated. The failure mode that would matter — deciding a case a human should have decided — did
  not occur, including on all four INDETERMINATE cases.

## Case 211 — the one disagreement, recorded and not chased

Case 211 is the only case where the four fields disagree with the key: the key says `PARTIAL_REFUND`
of `2.00` with no driver compensation; the run produced `ESCALATE` with `amount_sgd` null.

**It is a genuinely contested case, not a defect, and it is recorded as a disagreement rather than
added to a list of things to fix.** The reasons are specific.

Both readings agree on almost everything. Both read the GPS trace as impaired — a 168-second sampling
outage from 12:33:40 to 12:36:28 sits inside the 300-second waiting window, which engages POL-NS-08(b)
and discounts `EV-GPS-00211` to weight 0.39. Both read the arrival marker as genuine, so POL-NS-05
does not fire. Both read `MSG-00211-004`, the driver's message at 12:35:10, as showing him still
working the pickup. Both identify the same deciding fact: **where the vehicle was across the outage**,
which is exactly what the impaired trace cannot show and what the chat message does not carry. The
run's own explanation says so in as many words: *"The chat message at 12:35:10 shows the driver was
still working the pickup, but it says nothing about where he was, so it cannot carry that fact."*

They part on one point. POL-GEN-02 caps confidence at the weight of the artifacts carrying the
deciding fact, and the two readings take the cap differently:

- **The key takes the maximum** of the two weights — the chat at 1.00 and the trace at 0.39 — giving
  0.72, which clears the 0.70 floor, so POL-NS-09(a) does not fire and the case is decided as the
  split outcome POL-NS-08 describes: `PARTIAL_REFUND` of 2.00 of the 4.00 fee.
- **The run took the impaired artifact's weight**, 0.39, which is below the floor, so POL-NS-09
  required escalation and the fee was placed on hold for a human.

**The run's reading is not unreasonable, and that is the point.** If the deciding fact is carried
*solely* by an impaired artifact, capping confidence at the weight of that artifact is the
conservative reading of POL-NS-08's own rule that a claim resting on an impaired artifact cannot
alone support a ruling against the party it disfavours. The key's reading uses the chat to lift the
cap, and the chat cannot carry the deciding fact. This note does not resolve the tension; it records
that the corpus contains one case where the two readings diverge, that the divergence is a single
named point, and that the run erred toward **escalation** rather than inventing an answer.

**What was not done, and why.** The answer key was not changed, and the prompt was not loosened to
fit the run's output. Either would have converted a 28/29 into a 29/29 that measured nothing: the
first would make the key agree with a model, and the second would weaken a rule that produced the
correct answer on the other 28 cases. The disagreement stands in the record as what it is.

## What it cost

### The measured split

**MEASURED** by summing the `tokens` block of the 29 per-case entries in
`runs/deepseek-deepseek-flash/`:

| | tokens | share |
|---|---|---|
| Prompt (input) | 1,384,946 | 49.4% |
| Completion (output) | 1,419,115 | 50.6% |
| … of which reasoning | 1,289,843 | 90.9% of the output |
| Prompt tokens served from cache | 517,376 | — |
| **Billed total** | **2,804,061** | |

`reasoning_tokens` is a *breakdown* of `completion_tokens` on this provider, not a third quantity, so
it is not added to the total. `cached_tokens` is a breakdown of the prompt for the same reason. Both
are recorded because both are evidence: 91% of the output being reasoning is what a reasoning model
costs, and it is the single largest driver of the bill.

### The arithmetic

**LIST PRICE**, DeepSeek Flash off-peak: **CNY 1 per million input tokens, CNY 4 per million output
tokens**, with peak hours at **double**. Input and output are priced at 4:1, which is why the split
above is recorded rather than only the total.

| | |
|---|---|
| Off-peak, CNY | 1.384946 × 1 + 1.419115 × 4 = **CNY 7.06** |
| Off-peak, USD at 7.20 CNY/USD | **US$0.98** |
| Peak, USD | **US$1.96** |
| Per dispute, off-peak | **US$0.034** |

**The USD figures rest on an assumed exchange rate.** 7.20 CNY/USD is **ASSUMED** — a round working
rate, not a rate taken on the day. At 7.10 the off-peak figure is US$0.99; at 7.30 it is US$0.97. The
conclusion does not turn on it, but the number is not a bill.

**These are list-price equivalents of measured usage, not an amount charged.** Each model carries a
1,000,000-token free quota (**MEASURED** 2026-09-21, see
`docs/notes/2026-09-21-tokenhub-api-facts.md`), and this single run consumed 2,804,061 tokens, so any
statement about what was actually paid depends on the quota's state at the time. **The account Usage
page is the evidence for that, and it is not evidence this note can offer.**

### An earlier estimate was wrong, and how

An earlier working figure of **US$0.74 per run** was wrong, and the way it was wrong is worth
recording because the mistake is easy to repeat. It assumed a **70/30 input/output split**, which is
the usual shape for a chat workload. The real split is **49/50**, and output is the expensive half.

| | CNY | USD at 7.20 |
|---|---|---|
| 70/30 split assumed over 2,804,061 tokens | 5.33 | US$0.74 |
| 49.4/50.6 split measured | 7.06 | US$0.98 |

The estimate was **32% low**. On a reasoning model the output share rises because the reasoning
tokens are output tokens, so an estimate that assumes a chat-shaped split will understate a reasoning
workload specifically. The correct procedure is to sum the recorded split, which is what the table
above does.

### Peak and off-peak hours

**LIST PRICE** as published by the provider: peak is **Monday to Friday, 09:00–12:00 and
14:00–18:00 Singapore time**; everything else is off-peak. **Weekends are off-peak throughout**, and
so is the 12:00–14:00 gap between the two weekday peaks.

**The deciding run was entirely off-peak.** It ran `2026-09-23T04:00:15Z` to `05:40:00Z`, which is
12:00:15 to 13:40:00 Singapore time on a Wednesday — inside the midday gap, never entering either
peak window. So the US$0.98 figure is the off-peak price of the run and would have been US$1.96 had
the same run been made two hours later.

The window is recorded per invocation so this can be worked out afterwards rather than remembered:
`started_at` and `ended_at` are in `run.json`, and they travel into `invocations.json` as well, so
the window of an earlier invocation survives the next one overwriting `run.json`.

### How the figures came to be recorded at all

The run directory's invocation record previously carried **a single undifferentiated total**
(`spent_this_invocation`, `reused_from_cache`, `total_for_the_case_set`). A total cannot be costed —
the two halves are priced 4:1 — and it could not distinguish a case that produced a ruling from one
that failed after its calls had already been billed.

The invocation record now carries, per invocation:

- the **prompt and completion totals separately**, plus the reasoning and cached breakdowns;
- the split of what was **charged to the budget** (the completed cases, which is what the run has
  always stopped on) and of what was **consumed** (every token billed, the failed cases included).
  The two differ by the cost of the run's own failures, and keeping them apart is what stops a run
  looking cheap by having thrown answers away;
- the split of the tokens **reused from the cache**, so a re-run that consumes nothing does not erase
  what the results cost to produce;
- the window it ran in.

`TokenSplit` derives its total from the prompt and completion rather than storing one beside them, so
the total and the split cannot disagree, and `prompt + completion == consumed` is asserted by a test
rather than by convention.

## The alternatives

### `hy3` — rejected

**Rejected on output-contract failures, not on accuracy.** Four independent failures are recorded in
this repository:

1. **Non-determinism at `temperature: 0`, `seed: 42`.** Three consecutive identical requests produced
   three *different* completions, where `hy4-preview` and `deepseek/deepseek-flash` produced three
   byte-identical ones each. **MEASURED** 2026-09-21, in `docs/notes/2026-09-21-tokenhub-api-facts.md`.
   The consequence is the one that matters: **`seed` is not a determinism guarantee on this
   provider**, so a reproducible result requires pinning the model rather than the seed.
2. **A malformed 200 body with inconsistent quote escaping**, recorded verbatim as
   `{"ruling\":\"ALLOW`. **MEASURED** in the same note. This is why `LLMResult` carries an explicit
   parse outcome instead of letting a `JSONDecodeError` escape the transport.
3. **A wrong container on a real case.** On case 108 the advocate answered with a single
   claim-shaped object — keys `text`, `evidence_ids`, `clause_ids` — rather than the contract's
   shape, and the retry did the same. **MEASURED** in `runs/hy3/case-00108.transcript.json`. This one
   is partly attributable to the repository's own `json_object` defect at the time: the pipeline
   forced a top-level object while the prompt asked for an array, and the model obeyed the enforced
   constraint. See `docs/notes/2026-09-22-advocate-output-contract.md`.
4. **The case bundle echoed back.** On case 109 the advocate returned the case JSON —
   `case_no`, `dispute`, `evidence`, `schema_version` — which contains no claims in any wrapper.
   **MEASURED** in `runs/hy3/case-00109.transcript.json`. The contract note is explicit that **this
   one is not attributable to the `json_object` defect**: no reading of the prompt makes that a
   correct answer, so it is a separate model failure recorded under the same label.

A fifth failure is recorded but is a property of the run rather than of the model: case 109 also
failed on a `TimeoutError` at 120.1 s against the then-default 120-second timeout. **MEASURED** in
`docs/notes/2026-09-21-tokenhub-api-facts.md`.

**The limit of this comparison.** `runs/hy3/` produced **no ruling at all** — both cases it reached
failed at the advocate — so it offers no accuracy figure to compare against anything. It is rejected
on its ability to produce a well-formed answer, which is a precondition for measuring accuracy rather
than a result of measuring it.

### `hy4-preview` — rejected

**Rejected on latency and cost at equal observed accuracy.** The comparison rests on **one case**,
case 109, which is the only case both models completed under a configuration that was sound for both.

| Case 109 | `deepseek/deepseek-flash` | `hy4-preview` |
|---|---|---|
| Wall clock | 212.8 s | 978.8 s |
| Billed tokens | 98,156 | 142,247 |
| Calls made | 3 | 4 |
| Ruling produced | `DRIVER_COMPENSATION`, 3.15 / 3.15, no referrals | `DRIVER_COMPENSATION`, 3.15 / 3.15, no referrals |

**MEASURED** from `runs/deepseek-deepseek-flash/case-00109.json` and
`runs/hy4-preview/case-00109.json`. The answer key for case 109 is `DRIVER_COMPENSATION` with
`amount_sgd` 3.15 and `driver_compensation_sgd` 3.15 and no referrals, so **both produced the
identical correct ruling**, and the four graded fields are equal.

**A correction to that table, because it is not like for like.** `hy4-preview` made **four** calls on
this case, not three: its rider's first answer arrived in the wrong wrapper and was rejected, so a
retry was made. That wasted call is part of the invalidated configuration's cost, not a property of
the model. Comparing only the three accepted answers:

| Three accepted answers | `deepseek/deepseek-flash` | `hy4-preview` | ratio |
|---|---|---|---|
| Wall clock | 212.8 s | 761.8 s | 3.6× |
| Billed tokens | 98,156 | 108,054 | 1.10× |

So as observed `hy4-preview` took 4.6× the wall clock and 1.45× the tokens; on accepted answers only,
3.6× and 1.10×. Both are recorded because both are true and they answer different questions — what
the run cost, and what the model costs per answer.

**The limit of this comparison, stated plainly.** This is **ONE case**, and the case is one where the
two models agree. A single case where two models produce the same answer cannot show an accuracy
difference between them, and it does not: the choice rests on **latency and cost at equal observed
accuracy**, not on a demonstrated accuracy difference. A case where the models disagree would be
needed to make the accuracy claim, and no such case was run.

### What was not tried

No other model was benchmarked over the corpus. The corpus is 29 cases and one full run costs about
US$1; a second full run was affordable, and one was made (the earlier `97dbb9c` invocation in the same
directory, whose two case failures are what prompted the fixes recorded elsewhere). Beyond that, the
decision was taken on the evidence above rather than by sweeping the catalogue, and this note says so
rather than implying a wider comparison than was made.

## What this decision does not claim

- **It does not claim `deepseek/deepseek-flash` is the best available model.** It claims it is good
  enough to stop looking on this corpus, at this price, under this code.
- **It does not claim the accuracy figure generalises.** 28/29 is a figure over 29 cases, one run.
- **It does not claim the cost figures are a bill.** They are list-price equivalents of measured
  usage at an assumed exchange rate.
- **It does not claim the `hy4-preview` comparison measured accuracy.** One case, and one where both
  models agreed.
- **It does not resolve case 211.** The key's reading and the run's reading of the POL-GEN-02 cap
  both stand; the corpus contains one case where they diverge.

## Figures that could not be reproduced

Two figures were reported to this session for the `hy4-preview` comparison of case 109 that **do not
appear in the record and could not be re-derived from it**: a `deepseek/deepseek-flash` wall clock of
**187.2 s** and a token count of **89,706**.

The measured values are **212.8 s** and **98,156 tokens**, summed over the three calls in
`runs/deepseek-deepseek-flash/case-00109.transcript.json` (99.3 + 36.7 + 76.8 s; 38,115 + 23,338 +
36,703 tokens). No subset of those calls produces 187.2 s or 89,706 tokens either — the closest
subsets are 176.1 s / 74,818 tokens (rider and judge) and 136.0 s / 61,453 tokens (rider and driver).
The figures are recorded here as unreproducible rather than replaced silently, because a number that
enters a decision note without a source is exactly the kind of thing the rest of this note is built to
avoid.

## Overriding the decision

```sh
# the decided model
python -m tribunal.pipeline --case 208

# something else, for a probe or a comparison
python -m tribunal.pipeline --case 208 --model hy4-preview
python -m eval.run_benchmark --model hy4-preview --cases 101-115
```

The override is deliberately one flag. Changing the decision means changing `RUNTIME_MODEL` in
`tribunal/model.py` — one line, in one file, and the tests will tell you if you have introduced a
second place the value lives.

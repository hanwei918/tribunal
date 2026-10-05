# Tribunal

2026 Tencent Cloud AI Singapore Hackathon / Digital Native / Ryde / Newbee.

Official WorkBuddy project root: `/Users/hanweizhou/Desktop/Tribunal`.
Execution start: 2026-09-18; feature-freeze target: 10-10; submission deadline: 10-16 (the exact time is per the submission platform).

## What Tribunal is

Tribunal arbitrates a ride-hail dispute and writes down why. One brief is built
from the public case content and the loaded policy, and **two advocates argue from
that same brief under opposite stances** — the rider's and the driver's — so both
sides read byte-identical evidence and differ only in their instructions. A
**deterministic referee** then reads both claim sets and discards any claim that
cites no evidence id or no clause id, any citation that does not resolve, any
claim resting on impaired evidence without disclosing the impairment, and any
claim that uses a context-only profile field as a ground; it never decides the
merits. An **admissibility precheck** weights every artifact by the issue codes
the corpus attaches to it, so impaired evidence is carried into the case rather
than silently trusted. A **judge rules four times** on the same inputs and the
majority decides. Below the **confidence floor of 0.70**, or on a policy
escalation, the case gets no ruling at all: it goes to a **human reviewer with the
fee held** rather than collected or refunded.

## Results

Read this table from the top. The first block is the submission's claim; every
block below it is context that says what that claim is worth.

Two figures are **generalisation** figures, and each is its own. The held-out set
(`wild-v1`) is 64 cases derived from real complaints, prepared by their author as
a development set; nobody who changed the system opened them before the freeze
tagged `freeze-2026-09-30`, and they were run once from that tag. The second
sealed set (`wild-v2`) is 20 cases, run once on 2026-10-04 from a commit whose
`tribunal/`, `prompts/` and `policy/` trees equal those at the freeze tagged
`freeze-2026-10-03`. The corpus and the second set are **development** data the
system was built against, so a figure over them measures fit, not generalisation.
**The two sealed figures are never summed or pooled** — one figure over 64 cases
plus another over 20 is not a measurement of 84 cases — and neither sealed set is
ever produced by `--set all`. The second sealed set's run, its figures and its two
misses are read in `docs/notes/2026-10-04-the-second-sealed-run.md`.

| figure | value | read from | recompute with | model call |
|---|---|---|---|---|
| Held-out set (`wild-v1`) — four-field exact, of the cases that produced a ruling | 55/62 = 88.7% | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m eval.development_sets --report` | no |
| Held-out set (`wild-v1`) — four-field exact, over all 64 cases | 55/64 = 85.9% | `runs/wild/deepseek-deepseek-flash/`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — ruling alone, of the cases that produced a ruling | 56/62 = 90.3% | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m eval.development_sets --report` | no |
| Held-out set (`wild-v1`) — escalation precision | 3/7 = 0.429 | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — escalation recall | 3/4 = 0.75 | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — over-escalations | 501, 504, 508, 530 | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — under-escalation | 627 | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — cases with no ruling | 517, 533 | `runs/wild/deepseek-deepseek-flash/run.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Held-out set (`wild-v1`) — cases that differ from the key | 501, 504, 508, 523, 530, 622, 627 | `runs/wild/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — four-field exact, of the cases that produced a ruling | 18/20 = 90.0% | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m eval.sealed_report --set wild-v2` | no |
| Second sealed set (`wild-v2`) — four-field exact, over all 20 cases | 18/20 = 90.0% | `runs/wild-v2/deepseek-deepseek-flash/`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — ruling alone, of the cases that produced a ruling | 18/20 = 90.0% | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m eval.sealed_report --set wild-v2` | no |
| Second sealed set (`wild-v2`) — escalation precision | 4/5 = 0.8 | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — escalation recall | 4/5 = 0.8 | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — over-escalation | 702 | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — under-escalation | 716 | `runs/wild-v2/deepseek-deepseek-flash/case-*.json`, `eval/answers/wild-v2/ground_truth.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Second sealed set (`wild-v2`) — ROUTE_DEVIATION four-field exact | 10/12 = 83.3% | `runs/wild-v2/deepseek-deepseek-flash/`, `eval/answers/wild-v2/ground_truth.json`, `data/external/wild-v2/index.json` | `python3 -m eval.sealed_report --set wild-v2` | no |
| Second sealed set (`wild-v2`) — NO_SHOW_CHARGE four-field exact | 8/8 = 100.0% | `runs/wild-v2/deepseek-deepseek-flash/`, `eval/answers/wild-v2/ground_truth.json`, `data/external/wild-v2/index.json` | `python3 -m eval.sealed_report --set wild-v2` | no |
| Second sealed set (`wild-v2`) — cases with no ruling | none | `runs/wild-v2/deepseek-deepseek-flash/run.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Corpus — four-field exact (development) | 29/29 = 100.0% | `runs/deepseek-deepseek-flash/`, `eval/answers/ground_truth.json` | `python3 -m eval.development_sets --report` | no |
| Second set — four-field exact (development) | 14/15 = 93.3% | `runs/codex/deepseek-deepseek-flash/`, `eval/answers/codex/ground_truth.json` | `python3 -m eval.development_sets --report` | no |
| Ablation — admissibility precheck removed, both sets | 40/44 = 90.9% | `runs/ablation/admissibility/`, `runs/codex/ablation/admissibility/` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Ablation — admissibility removed, case 112 | DRIVER_COMPENSATION 1.80, unanimous | `runs/ablation/admissibility/deepseek-deepseek-flash/case-00112.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Ablation — clause notes removed, both sets | 41/44 = 93.2% | `runs/ablation/clause-notes/`, `runs/codex/ablation/clause-notes/` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Baseline — always ESCALATE, both sets | 7/44 = 15.9% | `runs/baselines/report.md`, `runs/baselines/baselines.json` | `python3 -m eval.baselines --set all` | no |
| Baseline — one draft, mean of the four, both sets | 42.25/44 = 96.0% | `runs/baselines/report.md`, `runs/baselines/baselines.json` | `python3 -m eval.baselines --set all` | no |
| Baseline — the carried vote, both sets | 43/44 = 97.7% | `runs/baselines/report.md`, `runs/baselines/baselines.json` | `python3 -m eval.baselines --set all` | no |
| Verifier — rulings the material rule changed | 0 of 42 | `runs/verify-recorded-drafts/deepseek-deepseek-flash/verify-recorded.json`, `runs/codex/verify-recorded-drafts/deepseek-deepseek-flash/verify-recorded.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Verifier — statements judged contradicted | 57 of 3,179 (15 material) | `runs/verify-recorded-drafts/*/deepseek-deepseek-flash/verify-recorded.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Verifier — cases carrying a material contradiction | 102, 107, 108, 110, 9102, 9104, 9113 | `runs/verify-recorded-drafts/*/deepseek-deepseek-flash/verify-recorded.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Verifier — the switch in every scored run | off, in all 8 | every scored run's `case-*.json`, each of which records its own `configuration`; the two development runs record none, in `run.json` or in their case files, and they predate the verifier (`a62ad0d`), so it could not have been on for them | `python3 -m unittest tests.test_readme_figures -v` | no |
| Sample case 901 — under the current pipeline | ESCALATE, confidence 0.6 | `runs/rerun-2026-09-29/external/ryde/case-00901.json` | `python3 -m unittest tests.test_readme_figures -v` | no |
| Sample case 901 — the organisers' stated expectation | Cancellation charge UPHELD | `eval/external/ryde/expected.json` | `python3 -m unittest tests.test_readme_figures -v` | no |

**Each sealed block is read from its own single run and its own freeze.** The
`wild-v1` rows are read from the run of 2026-09-30, made from the commit tagged
`freeze-2026-09-30`; the `wild-v2` rows are read from the run of 2026-10-04, made
from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03`. No `wild-v2` figure is added to a `wild-v1` figure or to any
development figure.

**Which policy version each block was measured at.** The corpus, the second
development set and `wild-v1` were all measured at **policy version 1**, the
three files in `policy/` exactly as they stood before amendment `0001`; the
`wild-v2` block is the one measured at **version 2**. The version-2 re-run of the
57 affected development cases is committed at `39a8a36` under `runs/policy-v2/`,
`runs/codex/policy-v2/` and `runs/wild-dev/policy-v2/`, with `rerun.json`,
`diff.json` and `diff.md`.

**About the second sealed set's provenance.** The set shares three of its eight
generator files with `wild-v1` — `core.py`, `places.py` and `wild.py` — and
`wild-v1` became development data on 2026-10-01, so 18/20 is read as an **upper
estimate** rather than as an expectation. Whether the set's author, OpenAI Codex,
could read this repository while preparing it is **not recorded**. One interrupted
attempt on 2026-10-03 at 14:14 partly called cases 701 and 702; its record was
deleted, and the owner ruled before the run that the attempt does not count under
the protocol. The run's own note is
`docs/notes/2026-10-04-the-second-sealed-run.md`.

**Every command above is read-only and makes no model call.** The three module
commands are `python3 -m eval.development_sets --report`, which prints each set's
row (cases, four-field exact, and the four fields separately) and its currency;
`python3 -m eval.baselines --set all`, which prints the baseline table; and
`python3 -m eval.sealed_report --set <set>`, which prints one sealed set's own
figures on both bases, per category, and its escalation counts. The
rest are recomputed by `tests/test_readme_figures.py`, which parses this table and
recomputes every row from the committed files and the frozen keys:

    python3 -m unittest tests.test_readme_figures -v

Every figure is its own subtest, so a failure names the figure, the value this
file states and the value the committed files hold. The module also fails if a
figure is dropped from the table or added to it without being checked, and if any
row's `model call` cell is not `no`.

**The runs themselves did make model calls, and none of them was made here — with
one exception that does not count.** Each run in the table below was made once by
the owner outside this sandbox and committed byte for byte as produced. The one
exception is the interrupted attempt on 2026-10-03 at 14:14, which partly called
cases 701 and 702 before it was stopped; its record was deleted, it is not a run
in the table, and the owner ruled before the run that it does not count under the
protocol. The commands that made them, and which of them were paid for, are:

| run | command | when |
|---|---|---|
| held-out set (`wild-v1`) | `python3 -m eval.development_sets --set wild --concurrency 2 --timeout 900` | once, 2026-09-30, from the commit tagged `freeze-2026-09-30` |
| second sealed set (`wild-v2`) | `TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900` | once, 2026-10-04, from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal those at `freeze-2026-10-03` |
| development sets | `python3 -m eval.run_benchmark`, `python3 -m eval.development_sets --set codex` | 2026-09-22 to 2026-09-24 |
| ablations | the same two with `--ablate admissibility` or `--ablate clause-notes` | 2026-09-29 |
| sample case | `python3 -m eval.run_benchmark --external data/external/ryde/case-00901.json --runs-dir runs/rerun-2026-09-29 --timeout 900` | 2026-09-29 |

## What went wrong on the held-out set

The held-out run is one of the submission's two generalisation figures and it is
reported as it came out, misses included. Three things are worth a reader's
attention.

**One miss pays money the policy does not authorise.** Case 523 is the dangerous
one: the key is `NO_ACTION`, and the run refunded 4.00 as a standalone
`POL-RD-09` pass-through "available whether or not a deviation exists" — which is
`POL-RD-09(4)`, the limb its own explanation had just ruled out. The policy gives
no route for a cash duplicate and the rider's cash is not in the pool. Every other
miss is a case that was escalated where the key decided, or decided where the key
escalated; this is the only one that moves money the policy does not move.
`docs/notes/2026-09-30-the-sealed-run.md`.

**Three escalations turn on one genuine ambiguity in the policy text.** Cases 504,
508 and 530 all read `POL-RD-10(5)` — "a closure asserted with no
traffic_advisory" — as "no advisory is present", and escalated. The keys read the
same sentence as "a closure is asserted that the record does not carry", apply
`POL-RD-08`'s rule that an assertion citing no evidence id carries no weight, and
decide on the merits. 508 makes the ambiguity explicit: its explanation concedes
the `POL-RD-08` point in terms and escalates anyway. This is the same borderline as
development case 105, so it is a policy-text question rather than a pipeline
defect. `docs/notes/2026-09-30-the-sealed-run.md`.

**Two cases produced no ruling, and the system was right about them.** In 517 and
533 the judge's drafts gave the key's own amount — 533's four drafts all gave
19.30, 517's three gave 33.50 against a fourth at 31.50 — and every draft was then
rejected by the draft check `DRAFT_AMOUNT_NOT_READ_OFF`, because the brief's money
block does not publish that figure. The read-off rule accepts a published figure
or the **sum** of two or three of them, never a **difference**, and an
upfront-quoted fare's remedy under `POL-RD-11(a)` is a difference by construction:
533's 19.30 is `51.30 − 29.00 − 3.00`. The money block was built around the
development sets, where 43 of 44 key amounts read off it, and the only two
upfront-quote route cases there both happened to land on a single published
figure — so this shape was never met before the held-out run. The same check was
**right** in 501, where it rejected three drafts that deducted an airport
surcharge of 6.00 the ledger never charged. This is a real defect in the draft
check and it is deliberately not fixed here: fixing it would change the system
that produced the figure, so the repair belongs to a later version measured on a
new held-out set. `docs/notes/2026-09-30-the-sealed-run.md`.

**Nothing in the answer key changed because of this run**, and nothing in
`tribunal/`, `prompts/` or `policy/` did either. The key is frozen; see
`START-HERE.md`. One case in the held-out key looks wrong — 622 differs from the
run only by a `POL-NS-07` referral the policy requires and the key omits — and it
is recorded rather than acted on, because editing the expected result so a run
scores better destroys the only independent measurement this project has.

**One thing the run did not settle.** The held-out set's own README, committed at
`eval/external/wild/README.md` — translated from the author's Chinese original,
whose sha256 the note records — calls this 64-case set a development and
regression set and names a different, 24-case set as the sealed one. The conflict
is recorded in full in `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md`
and is still the owner's to settle before 55/64 is reported as generalisation.

## How it works

`tribunal/pipeline.py` runs one case through a fixed sequence. Every stage is
deterministic except the three agents.

1. **Load.** `tribunal/loader.py` reads a case against the manifest at
   `data/index.json`, under the data contract in `data/PUBLIC-CONTRACT.md`.
2. **Prepass and facts.** `tribunal/prepass.py` reproduces the corpus's own
   `weight_multiplier` arithmetic from an artifact's issue codes, so the
   admissibility weights are derived rather than trusted. `tribunal/facts.py`
   turns the raw GPS trace — three quarters of a case's bytes — into the small
   numbers the policy thresholds on: excess distance, dwell, coverage.
3. **One brief.** `tribunal/brief.py` builds the evidence package once and
   canonicalises it once. The same bytes go to both advocates and to the judge,
   and the brief's sha256 is recorded on the result so a reader can confirm it.
4. **Two advocates, one brief, opposite stances.** `prompts/v1/advocate.system.md`
   is rendered twice, substituting `prompts/v1/stance.rider.md` and
   `prompts/v1/stance.driver.md` at the `{{STANCE}}` placeholder. `run_case`
   asserts that the two rendered prompts differ only inside that block, which is
   the project's central claim.
5. **The referee.** `tribunal/referee.py` is a deterministic citation referee,
   deliberately narrower than the judge. It discards a claim for citing no
   evidence id, citing no clause id, citing something that does not resolve,
   resting on impaired evidence without disclosing the impairment, or treating a
   context-only profile field as a ground. It never decides the merits.
6. **The judge, four times.** `prompts/v1/judge.system.md` is asked four times on
   the same inputs — three sampled, one with the parties' positions swapped — and
   the majority decides. A draft that fails a code check abstains, and a tie is an
   escalation. The drafts are reduced over all four graded fields together,
   because a panel that agreed on the label while disagreeing on the money has not
   agreed on anything.
7. **The floor, and the human.** `POL-RD-10` requires an escalation whenever the
   judge's confidence is below 0.70 or one of its listed conditions holds, and the
   case then goes to a human reviewer with the fee held rather than collected or
   refunded. `tribunal/transcript.py` records every call: what each agent was told
   and what it answered.

Two bounds are in force and they are not the same bound: 1200 s bounds one call
and 2400 s bounds one case, and both are checked before the work they bound. A
deadline is its own failure kind, `FAILURE_DEADLINE`, beside `TIMEOUT`, `TRANSPORT`
and `SHAPE`.

## Repository map

| path | what it holds |
|---|---|
| `data/` | The 29-case corpus (`data/cases/`), its manifest (`data/index.json`), the data contract (`data/PUBLIC-CONTRACT.md`), and the external sets under `data/external/`: the organisers' sample, the second development set (`codex/`, 15 cases) and the held-out set (`wild/`, 64 cases). |
| `policy/` | The policy the agents are briefed against, as three JSON files. `policy/amendments/` holds `0001-pol-rd-13` (approved), so the repository is at **policy version 2**, and the second sealed set was run at version 2. |
| `prompts/v1/` | The six prompts: the advocate template with its two stance blocks, the judge, the verifier and the policy drafter. |
| `tribunal/` | The pipeline — loader, prepass, facts, brief, referee, pipeline, transcript, money, events, llm, model, precedents, policy versions. |
| `eval/` | The benchmark and the measurement: the runner, the grader, the development-set runner, the baselines, the policy-gap loop, the verifier's measurement mode, and the event-log reader. `eval/answers/` holds the frozen keys. `eval/external/` holds answer-bearing source documents, which are **not** agent input. |
| `runs/` | The benchmark's own output, committed as produced. `runs/README.md` says which directory holds what and how to read one run directory. |
| `tests/` | The suite. Nothing in it makes a model call. |
| `ui/` | `ui/build.py` and the one committed page it builds. |
| `docs/` | `docs/notes/` — the dated decisions behind every number here; `docs/buddy-log/` — the WorkBuddy sessions. |
| `precedents/` | The precedent library: human closures of decided cases. Empty until a reviewer closes one. |
| `START-HERE.md` | The standing operating procedure for a session in this repository. Read it before changing anything. |

## The debate viewer

`ui/dist/index.html` is one self-contained page, built by `ui/build.py` from the
committed run in `runs/deepseek-deepseek-flash/`. Open it directly: it needs no
server and makes no network request of any kind, so it works from `file://` on a
machine with no internet. It carries the run's headline figures over all 29 cases,
one case stepped through in the order it was decided, and the stance proof — that
both advocates were handed byte-identical evidence and differed only in their
instructions. Rebuild it with `python -m ui.build`; the committed file is required
by test to equal a fresh build.

## The organisers' sample case

`eval/external/ryde/DISP-002.md` is the sample supplied to every team. It is
answer-bearing, so it is not agent input. `eval/external/ryde/convert.py`
converts it into this system's case format at `data/external/ryde/case-00901.json`,
recording every decision the conversion made — copied or judged, with reasons — in
`data/external/ryde/mapping.json`. It is deliberately absent from `data/index.json`,
so the 29-case corpus the benchmark reports is unchanged. Arbitrate it with

    python -m eval.run_benchmark --external data/external/ryde/case-00901.json

It runs into `runs/external/ryde/` and never into a model's run directory. It is
not scored: there is no answer-key entry for it, so the produced ruling is printed
beside the organisers' stated expectation, labelled as a stated expectation rather
than a verified answer. Under the current pipeline it escalates at confidence 0.6 —
the organisers state that the charge is upheld — and whether that is a
disagreement about the facts or about the policy's confidence floor is not
something either run settles. `docs/notes/2026-09-30-the-clause-notes-ablation-and-901.md`.

## Reading the record

`runs/deepseek-deepseek-flash/` holds the run the submission reports: per case a
result and a transcript, plus `run.json` and `invocations.json`. `run.json` and
`report.md` describe the **last** invocation and are overwritten by the next one;
`invocations.json` is the history and is the file that survives. Read a run's
`report.md` case count before comparing it with anything, because a four-case
replay leaves a four-case report beside a twenty-nine-case directory.
`runs/README.md` has the full account. `docs/notes/` holds the dated decisions
behind every number in this file.

## Running the tests

    python -m unittest discover -s tests -v

Nothing in the suite makes a model call and no credential is needed.
`tests/test_readme_figures.py` is the one that keeps this file honest: it parses
the results table above and recomputes every figure in it from the committed runs
and the frozen keys, failing when any of them differs.

## Where the WorkBuddy sessions are recorded

`docs/buddy-log/README.md` holds one row per session: the task, the files it
touched, what was verified and how, the screenshot, and the commit. The rows are
written after the fact and are not pre-filled.

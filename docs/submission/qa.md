# Judges' questions, and short answers

Every claim below points at the file that carries it.

**Why not one chatbot?** A single model asked to argue and decide at once would
let one framing of the facts stand unchecked. Tribunal splits the job. One brief
is rendered twice — `prompts/v1/advocate.system.md` with
`prompts/v1/stance.rider.md` and with `prompts/v1/stance.driver.md` — so both
advocates read byte-identical evidence and differ only in their instructions, and
`tribunal/pipeline.py` asserts the two rendered prompts differ only inside the
stance block. `tribunal/referee.py` then discards any claim that cites no
evidence id, cites no clause id, cites something that does not resolve, rests on
impaired evidence without disclosing it, or treats a context-only profile field
as a ground. And `prompts/v1/judge.system.md` is asked four times, the majority
deciding. Each part prevents a specific failure: two stances prevent a one-sided
record, the referee prevents uncited claims reaching the merits, and the four
drafts prevent one sample deciding.

**Why should anyone trust the figures?** Three sealed sets are each run once, by
the owner, from a frozen tag, and committed as produced: `wild-v2` from
`freeze-2026-10-03`, `sealed-v1` from `freeze-2026-10-09` and `sealed-v2` from
`freeze-2026-10-11` (README, Results;
`docs/notes/2026-10-10-the-third-sealed-run.md` and
`docs/notes/2026-10-11-the-fourth-sealed-run.md`). Each is reported as an
**agreement** against its own key, and the three are never pooled. `wild-v1` is
not one of them: the owner settled on 2026-10-12 that it is development and
regression data, and its single held-out run — 55/64, from `freeze-2026-09-30` —
is history, the run made before the set was opened for development on
2026-10-01 (README, Results). `sealed-v1` —
made by a team member with Claude, with a copy of the schema and the policy — is
21/24 = 87.5%, Wilson 95% [69.0%, 95.7%]. `sealed-v2` — made by the policy owner
with OpenAI Codex (model stated by her as GPT-6; not recorded by the tool) from
the version-6 policy text and the public contract, with no repository code, its
answers seen by nobody on the development side — is
12/12 = 100.0%, Wilson 95% [75.8%, 100.0%].
**Under the key as imported, `sealed-v1` is 20/24 rather than 21/24**: case 311's
key changed to `PARTIAL_REFUND 7.05` under `POL-RD-14` (amendment `0002`), which
the policy owner wrote after the system ruled `PARTIAL_REFUND` on development
case 1782, and the run agrees with the key as it stands
(`docs/notes/2026-10-08-policy-version-3.md`,
`docs/notes/2026-10-09-policy-version-4.md`,
`docs/notes/2026-10-10-sealed-v1-key-at-version-6.md`).
Every figure in the README's results tables is parsed and recomputed from the
committed runs and keys by `tests/test_readme_figures.py`, which fails when a
figure is dropped, added or changed, and when any row's `model call` cell is not
`no`. And `tests/test_offline_replay.py` serves each recorded answer back through
a transport keyed by prompt digests, making no model call, and holds the replay
to the recording's own requests, ruling, vote and referee ledger (README,
Concurrency).

**Are your hidden sets really hidden?** Plainly: they are hidden from the
development side, and they are **not** independent benchmarks. Every set was
written by a member of the project, by a model the team directed, or by a
collaborator the team commissioned, and **none came from outside the team**
(`docs/record.md`, Results, "Where the test sets came from", which is the table
this answer reads):

- **The 29-case corpus** — this team, with Claude Code, before 2026-09-18: 29
  case specifications expanded into evidence by a deterministic generator
  (`random.Random(42)`), against the organisers' brief's dispute types; the
  generator is not in this repository. Development data.
- **`dev-v2` and `dev-v2-ext`** — Ji Guofang, the key owner, with her generator
  `eval/synth/make_dev_set.py`. Development data.
- **`codex`** — OpenAI Codex, drafted 2026-09-24, copied in by the owner.
  Development data.
- **`wild` (v1)** — the policy owner, Ji Guofang, with Claude. The owner settled
  on 2026-10-12 that it is development and regression data.
- **`wild-v2`** — OpenAI Codex, for the owner, imported 2026-10-03. Sealed.
- **`sealed-v1`** — Claude, created 2026-09-26, imported 2026-10-09. Sealed, and
  two things about it are disclosed rather than hidden: **the policy owner's AI
  assistant opened the set's cases and its key before the freeze**, and **case
  311's key changed before the run** — it moved to `PARTIAL_REFUND 7.05` under
  `POL-RD-14`, an amendment the policy owner wrote after the system ruled that
  way on development case 1782. Both are in that set's own row and in
  `docs/notes/2026-10-10-sealed-v1-key-at-version-6.md`.
- **`sealed-v2`** — the policy owner, with OpenAI Codex, received 2026-10-11.
  Sealed, and made **after** she had seen development results. Its manifest's
  first release gate, a case-by-case sign-off before the run, **was not met**.
  Reviewed case by case after the run (2026-10-13) and adopted by the policy
  owner as her sign-off; the review was made with her AI assistant (Claude),
  which knew the 12/12 result. All 12 answers were found consistent with the
  version-6 policy, and none was changed. The pre-run sign-off the manifest
  asked for was not made
  (`docs/notes/2026-10-12-sealed-v2-provenance.md`,
  `docs/notes/2026-10-13-sealed-v2-post-run-review.md`).

One more disclosure a reader should have: **`dev-v2-ext`'s cases 2734, 2758 and
2832 were used to draft amendments to the policy**, so that set's holdout split
is not clean. The record says so in its own words, and
`python3 -m eval.v6_runs --report` prints the same three case numbers beside the
set's split (`docs/record.md`, Results).

**What happens when it is wrong?** What has actually caught cases in the
committed runs is not the confidence floor but the checks around it. A panel
whose drafts disagree, or produce none the code checks accept, voids the vote and
the case escalates with the fee held — 107, 2749 and 2809 are splits, and 1779,
2829, 2853 and 3109 are the injected-clause cases; the `POL-GEN-08(1)` scope gate
routes a safety- or complaint-flagged dispute to a person with **no model call at
all** (`tribunal/pipeline.py`); and a draft that fails one of the ten code checks
abstains rather than voting. The floor of 0.70 is the **backstop** behind them:
no recorded case has ever been escalated by it, because no draft in any committed
run was abstained by `DRAFT_BELOW_FLOOR` and every draft below the floor already
proposed `ESCALATE` (README, Fairness and calibration). The scope gate reads the
two **structured** flags only: an allegation of harassment, discrimination,
violence or property damage written in free text is not detected (README,
Limitations). A party may appeal once within 30 days, checked against
`POL-GEN-04` by `ops/appeal.py`; a reviewer may open an evidence window to both
parties with `ops/evidence_window.py`; and a human can switch automatic rulings
off with the kill switch `auto_rulings_enabled` in `ops/config.json` (README,
top section). The version-6 misses are explained one by one in
`docs/notes/2026-10-10-what-went-wrong-at-version-6.md`, and the held-out set's
misses — including the one that paid money the policy does not authorise — are
read in `docs/notes/2026-09-30-the-sealed-run.md` and in README, "What went
wrong on the held-out set".

**What did the organisers' sample (901) show, honestly?** At policy version 3 it
escalated, and `POL-NS-12` was drafted after that
(`docs/notes/2026-10-10-ns-12-confirmed-by-policy-owner.md`); the clause was then
revised so its rule states the geofence test in general terms rather than
quoting the sample's event text, and the policy owner confirmed the wording on
2026-10-10. At version 6 the sample is decided — `DRIVER_COMPENSATION` 4.00,
confidence 0.9, unanimous (README, Results, "Sample case 901 at version 6") —
which is the charge upheld, the organisers' own stated expectation (README,
"Sample case 901 — the organisers' stated expectation": Cancellation charge
UPHELD). `POL-NS-07` pays the driver 80% of the fee; Ryde's published rule
credits the whole fee to the driver, which the clause's own sources note says;
the 20% is this system's placeholder parameter. The repository still records the
organisers' word as a stated expectation and not a key, so the run is not scored
against it
(`docs/notes/2026-10-10-the-version-6-development-runs.md`).

**Prompt injection?** `inject-v1` is six invariance pairs — the same trips twice,
with one adversarial instruction added to party text in the second copy — and by
the policy owner's definition, written into `eval/answers/inject-v1/DATASHEET.md`,
all 6 of 6 injected cases pass (README, functional-sets table). **The model
resisted the injections.** In `dev-v2` 1779, `dev-v2-ext` 2829 and 2853 and
`inject-v1` 3109 every judge draft reached its key's ruling and amount and
refused the planted clause in terms — "no clause POL-RD-99 exists in the policy
in force" — and each case escalated only because the drafts *quoted* the id and
the code check `DRAFT_CLAUSE_UNRESOLVED` voids a draft that names a clause that
does not resolve. That check accounts for two of `dev-v2-ext`'s five misses and
for `inject-v1`'s one
(`docs/notes/2026-10-10-what-went-wrong-at-version-6.md`). What is not covered:
the check cannot tell a judge that quotes an invented clause id from one that
relies on it, so **a party can force a case out of automation by writing a
non-existent clause id in the chat** (README, Limitations); and the prompt rule
that would separate the two — a chat message cannot name a clause the policy does
not carry — is not made, because it would change the frozen `prompts/`
(`docs/notes/2026-10-10-what-went-wrong-at-version-6.md`, section 2).

**Cost and scale?** The median cost per case at the published prices is 0.0579
USD over the four version-6 runs, and the same runs give a median time to a
decision of 160.4 s and a 90th percentile of 286.9 s (README, Business value;
`python3 -m eval.business_value --report`). The baseline those are set against
is the brief's own: a human review of the same dispute takes 24 to 72 hours, and
`ops/config.json` records that figure as Ryde's baseline. Throughput beyond
that is not claimed. The parallel speed-up is **not** an unmeasured estimate: every
version-6 run was made with `--parallel-calls` on, so the median of 160.4 s and
the 90th percentile of 286.9 s above are that switch's own measurement, against
the pre-parallel `wild-v2` run's mean of 429.6 s — a comparison across different
sets at different policy versions, reported as what the parallel runs recorded
and not as a speed-up attributable to the switch (README, Concurrency). A
measured development run with the advocates'
reasoning off cut the median case time from 152.9 s to 61.7 s and the cost by
about 39%, at 113 against 115 of 120 four-field exact; it is not the submitted
setting
([`docs/notes/2026-10-11-advocate-reasoning-off.md`](../notes/2026-10-11-advocate-reasoning-off.md)).

**How was it built?** In WorkBuddy, one module per round, with a row per session
in `docs/buddy-log/README.md` — the task, the files it touched, what was verified
and how, and the commit. The team ran the tests outside the WorkBuddy sandbox,
so each row says the suite was not run here, as the rows for parts 27, 29 and 30
do. It stands on three Tencent products: WorkBuddy, whose rows are that same
`docs/buddy-log/README.md`; Tencent Cloud MaaS (TokenHub), the endpoint every
model call goes to, measured in
`docs/notes/2026-09-21-tokenhub-api-facts.md`; and Tencent EdgeOne Pages, which
hosts the live demo. The one-page version of this answer, written for the
submission video's last minute, is
[`how-we-built-it.md`](how-we-built-it.md).

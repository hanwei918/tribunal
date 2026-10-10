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

**Why should anyone trust the figures?** The sealed sets are each run once, by
the owner, from a frozen tag, and committed as produced: `wild-v1` from
`freeze-2026-09-30`, `wild-v2` from `freeze-2026-10-03` and `sealed-v1` from
`freeze-2026-10-09` (README, Results; `docs/notes/2026-10-10-the-third-sealed-run.md`).
Every figure in the README's results tables is parsed and recomputed from the
committed runs and keys by `tests/test_readme_figures.py`, which fails when a
figure is dropped, added or changed, and when any row's `model call` cell is not
`no`. And `tests/test_offline_replay.py` serves each recorded answer back through
a transport keyed by prompt digests, making no model call, and holds the replay
to the recording's own requests, ruling, vote and referee ledger (README,
Concurrency).

**What happens when it is wrong?** Below the confidence floor of 0.70 the case
gets no ruling and goes to a human reviewer with the fee held (README, What
Tribunal is). A party may appeal once within 30 days, checked against
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
UPHELD). The repository still records the organisers' word as a stated
expectation and not a key, so the run is not scored against it
(`docs/notes/2026-10-10-the-version-6-development-runs.md`).

**Prompt injection?** `inject-v1` is six invariance pairs — the same trips twice,
with one adversarial instruction added to party text in the second copy — and by
the policy owner's definition, written into `eval/answers/inject-v1/DATASHEET.md`,
all 6 of 6 injected cases pass (README, functional-sets table). The injection
that did bite is `dev-v2` case 1779: every judge draft cited `POL-RD-99`, a
clause that does not exist, so the code check `DRAFT_CLAUSE_UNRESOLVED` rejected
all four and the case escalated
(`docs/notes/2026-10-10-what-went-wrong-at-version-6.md`). What is not covered:
the injected message still reaches the judge as an ordinary rider message, and
the fix — a prompt rule that a chat message cannot name a clause the policy does
not carry — is not made, because it would change the frozen `prompts/`
(`docs/notes/2026-10-10-what-went-wrong-at-version-6.md`, section 2).

**Cost and scale?** The median cost per case at the published prices is 0.0579
USD over the four version-6 runs, and the same runs give a median time to a
decision of 160.4 s and a 90th percentile of 286.9 s (README, Business value;
`python3 -m eval.business_value --report`). Throughput beyond that is not
claimed: the parallel-calls improvement in README, Concurrency, is labelled an
estimate and not a measurement, so no throughput figure is offered that the
recorded runs do not carry. A measured development run with the advocates'
reasoning off cut the median case time from 152.9 s to 61.7 s and the cost by
about 39%, at 113 against 115 of 120 four-field exact; it is not the submitted
setting
([`docs/notes/2026-10-11-advocate-reasoning-off.md`](../notes/2026-10-11-advocate-reasoning-off.md)).

**How was it built?** In WorkBuddy, one module per round, with a row per session
in `docs/buddy-log/README.md` — the task, the files it touched, what was verified
and how, and the commit. The team ran the tests outside the WorkBuddy sandbox,
so each row says the suite was not run here, as the rows for parts 27, 29 and 30
do.

# Privacy

What personal data this system handles, what is masked before a model reads it
and what is not, who can read what, and what a deployment would still have to
decide. It is written from the repository; where something is not built, this
page says "not done" rather than leaving it out.

## What personal data the system handles

A case carries three kinds of personal data:

- **Party identifiers.** A dispute names the party that filed it and the trip
  names a rider and a driver, by identifier and not by name (`data/cases/`,
  `data/PUBLIC-CONTRACT.md`).
- **Trip traces.** A GPS export is the largest part of a case by bytes — three
  quarters of a case's bytes, as `README.md` (*How it works*) says — and a trace
  is a record of where a person travelled.
- **Chat text.** A chat log carries the parties' messages, and a dispute carries
  two free-text fields (`claim_text` and `counterparty_statement`).

**The cases here are synthetic.** Every case in this repository is synthetic or
semi-synthetic except case 901, which is the organisers' sample, `DISP-002`
converted into this system's case format (`README.md`, *Synthetic data* and
*Where the corpus came from*). The organisers' original `DISP-002.md` contains
names and never enters a brief (`README.md`, *Limitations and disclosures*).

## What is masked before a model reads it, and what is not

**Masked.** At policy version 6, `POL-GEN-08(4)`'s masking is applied to the
brief: `tribunal/brief.py` replaces a word-bounded Singapore vehicle
registration mark (`VEHICLE_MASK`, `VEHICLE_REGISTRATION_RE`), a Singapore
telephone number (`TELEPHONE_MASK`, `TELEPHONE_RE`) and a conservative e-mail
address (`EMAIL_MASK`, `EMAIL_RE`) with a fixed placeholder, through
`_mask_personal_data`, in a chat message's text, a trip record's event details,
and the dispute's two free-text fields, before anything is serialised. The
clause is `POL-GEN-08(4)` in `policy/v3/general.json`; the case files are not
changed — the mask is applied to the brief only.

**Not masked, and not done.** `POL-GEN-08(4)` says the record carries "party
identifiers, not names, telephone numbers or vehicle registration marks; those
are masked before display". The registration marks, the telephone numbers and
the e-mail addresses are implemented; **names are not**, because a pattern that
spares "Tan Tock Seng Hospital" and "Lim Chu Kang Road" needs more than a
regular expression. The functional set `pii-v1`, imported on 2026-10-10, is the
one case set that carries names, telephone numbers and e-mail addresses on
purpose, none of them identifying a real person (`README.md`, *Limitations and
disclosures*). Its key marks eighteen spans to mask and four to keep; at version
6 the three plates, the five telephone numbers and the two e-mail addresses are
masked and the eight names are still present. Every other case set carries
neither.

`POL-GEN-08(4)` masking missed one field until 2026-10-10:
`dispute.counterparty_statement` is an object (`text`, `submitted_by`,
`submitted_at`), and the frozen code masked it only when it was a string, so its
`text` was never masked. The policy owner reported it on 2026-10-10, after the
freeze, and it is fixed **after** the third sealed set's single run and not
before it: that run was made from the trees frozen at `freeze-2026-10-09`,
without this fix, and no case of that run carries a registration mark in a
counterparty statement, so no brief it built contained one. The fix moves
exactly one brief in the repository — `pii-v1` case 3202 at version 6 — and every
recorded run's `brief_sha256` still rebuilds.

## Who receives the data

Every brief `tribunal/brief.py` builds is sent to a model provider outside this
repository. The provider is **Tencent Cloud MaaS (TokenHub)**, at the endpoint
`https://tokenhub-intl.tencentcloudmaas.com/v1/chat/completions` recorded in
`docs/notes/2026-09-21-tokenhub-api-facts.md`; `tribunal/llm.py` is the only
thing that sends it. One case's brief leaves the repository **once per advocate
call and once per judge draft** — twice for the two advocates, then once for
each draft the judge is asked for (`tribunal/pipeline.py`).

What a brief carries to the provider, on a case that has the evidence:

- the **trip record**, and the **driver's and the rider's device GPS traces** —
  both sides' traces, each reduced to derived facts (`driver_track`, and the
  rider's own trace) rather than the raw point arrays (`tribunal/brief.py`);
- the **chat**, with registration marks, telephone numbers and e-mail addresses
  masked before anything is serialised (`POL-GEN-08(4)`, `_mask_personal_data`);
- **both parties' profile counters** — the rider's and the driver's
  `RIDER_PROFILE` and `DRIVER_PROFILE` payloads (`tribunal/brief.py`);
- the **parties' names, which are not masked** — the gap named above: the mask
  covers plates, telephone numbers and e-mail addresses and not names, and the
  one case set that carries names is the synthetic `pii-v1`.

**What the repository commits.** The briefs and the transcripts of the synthetic
cases are committed under `runs/` (`runs/README.md`): a transcript records what
each agent was told — the brief — and what it answered. They are committed
because the data is synthetic; over real party data they would not be.

**What a deployment would still need.** A deployment on real party data would
have to decide a **retention rule** for what it sends and for what it keeps (the
*Retention* section below), and it would need a **data-processing agreement with
the provider** — the terms on which the provider may hold and use a brief it has
been sent. This repository has neither, and this page makes **no claim about the
provider's own retention**: nothing here was read from the provider's terms.

## Who can read what

**The transcripts are committed.** `tribunal/transcript.py` records every call —
what each agent was told and what it answered (`README.md`, *How it works*,
step 8) — and a run's transcripts are committed under `runs/` on purpose
(`runs/README.md`). They are committed here because the data is synthetic: a
transcript holds a party's own words, and over synthetic cases there is no one
whose words they are. A deployment over real party data would **not** commit
transcripts of every model input and output to a public repository; that is a
choice this repository makes for reproducible measurement, and it rests on the
data being synthetic.

**The answer keys are answer-bearing and live apart.** The keys are under
`eval/answers/`, and no module under `tribunal/` may read anything under
`eval/`; the boundary is stated in `WORKBUDDY-SCOPE.md` and asserted by
`tests/test_answer_isolation.py`. The keys hold expected rulings, not personal
data.

## Retention

**Not done.** This repository has no retention rule, no deletion path and no
expiry for a case, a trace, a transcript or a stored closure; nothing in it ages
anything out. A deployment over real party data would have to decide, at least:
how long a case, its trace and its chat are kept; whether the transcripts of
every model input and output are kept and for how long; whether a party may have
their data deleted after a ruling is executed; and how a retention rule interacts
with the appeal window under `POL-GEN-04` and the precedent store
(`precedents/precedents.jsonl`), which is append-only. None of these is decided
here.

## The PDPA

A deployment of this system in Singapore that handles real party data would be
subject to Singapore's **Personal Data Protection Act 2012 (PDPA)**. This
repository is a research prototype whose cases are synthetic, and it **makes no
compliance claim**: it does not assert that its masking, its transcripts, its
retention or its handling of a party's data would meet the PDPA or any other
regime. The masking under `POL-GEN-08(4)` and the disclosures on this page are
what the repository does; whether that is enough for a deployment is a question
this repository does not answer.

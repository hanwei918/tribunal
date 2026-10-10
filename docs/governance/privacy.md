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

**Masked.** At policy version 6, `POL-GEN-08(4)`'s masking of vehicle
registration marks is applied to the brief: `tribunal/brief.py` replaces every
word-bounded match of the Singapore registration pattern with a fixed
placeholder (`VEHICLE_MASK`, `VEHICLE_REGISTRATION_RE`, `_mask_registrations`) in
a chat message's text, a trip record's event details, and the dispute's two
free-text fields, before anything is serialised. The clause is
`POL-GEN-08(4)` in `policy/v3/general.json`; the case files are not changed — the
mask is applied to the brief only.

**Not masked, and not done.** `POL-GEN-08(4)` says the record carries "party
identifiers, not names, telephone numbers or vehicle registration marks; those
are masked before display". Only the registration marks are implemented.
Names and telephone numbers are **not** masked, because none appears: no case
file in this repository contains a telephone number or a name (`README.md`,
*Limitations and disclosures*). The clause is therefore implemented for the one
identifier that does occur and is unimplemented for the two that do not, and
this page says so rather than implying a general redaction.

`POL-GEN-08(4)` masking misses one field:
`dispute.counterparty_statement` is an object (`text`, `submitted_by`,
`submitted_at`), and the frozen code masks it only when it is a string, so its
`text` is never masked. The policy owner reported it on 2026-10-10, after the
freeze. No brief built at version 6 is affected: none of the 254 cases in the
corpus, `dev-v2`, `dev-v2-ext`, 901 and sealed-v1 carries a registration mark
there, and no version-6 brief of any of them contains one. The fix waits until
the sealed run is committed.

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

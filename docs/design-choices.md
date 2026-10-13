# Where we departed from the brief, and why

Two stretch goals in the Ryde brief describe a system where a model collects
evidence and a model feeds risk signals to the judge. Tribunal builds both of
those, and departs from the brief in the same direction twice: the models that
decide a case never choose what they are shown.

## The Evidence Collection Agent

The brief's stretch goal reads, in its own words: the Evidence Collection Agent
"Autonomously orchestrates multi-modal data retrieval across all tools and APIs,
feeding structured evidence to the advocate agents". The repository quotes that
sentence at the head of [`ops/evidence.py`](../ops/evidence.py) and again at the
head of [`ops/sources.py`](../ops/sources.py).

**What Tribunal does instead.** Evidence collection is a deterministic service,
not a model. [`ops/sources.py`](../ops/sources.py) builds one index over a case
root and six adapters that answer key lookups against it;
[`ops/evidence.py`](../ops/evidence.py) is given **only the dispute object**, asks
those adapters for what the trip and the parties have, and returns the artifacts
in the order every case file files them.
[`tribunal/brief.py`](../tribunal/brief.py) then builds one brief from that, and
that one brief is handed **byte-identical** to both advocates.
`python3 -m ops.evidence --case N` runs the collector on its own.

**What that buys.** The brief's fingerprint is recorded per case — the run writes
`brief_sha256` on the result, and the case page shows it — so a reader can
confirm which brief a ruling was made from. And because there is one brief rather
than one per advocate, **a party cannot change what the other side's advocate
reads**: neither side can see evidence the other cannot, and neither can withhold
an artifact from the other's prompt.

**What it costs.** The system has no evidence the code does not already have.
`ops/evidence.py` does not read `dispute.evidence_ids`, because the list of
artifacts a case is supposed to have is what the collector is checked against and
not an instruction to it, so a source system that holds something the case file
does not will not be discovered. No model decides that a missing record is worth
chasing; that is what `ops/evidence_window.py` is for, and a person opens it.

## The Fraud & Bad-Faith Detection Agent

The brief's stretch goal reads: the Fraud & Bad-Faith Detection Agent "Feeds risk
signals to the Judge Agent". The record states the same difference in one line
([the full record](record.md), "Stretch goals"): "The brief asks for risk signals
to be fed to the judge. This system sends them to the human reviewer and to the
queue instead and **not to the judge**".

**What Tribunal does instead.** [`ops/risk.py`](../ops/risk.py) reports which of
five named tests a case trips, quotes the threshold sentence the policy states
for each, and rules on nothing. Its signals travel in the reviewer's packet,
built by [`ops/escalation.py`](../ops/escalation.py), and in the queue's
ordering. The judge is not shown them.
The reason is a clause rather than a preference: `POL-GEN-01` forbids a party
profile from establishing a fact about the trip or carrying an adverse finding
against either party, and `ops/risk.py`'s own docstring says its signals are "a
second reading of the same fields for a person to look at, not an input to a
ruling".

**What that buys.** A risk signal never moves a ruling by itself. The judge still
receives the profile counters the five tests read — they travel in the brief, and
the policy's own tests are applied to them — but the judgement about bad faith is
made by a person, on a packet that says what tripped and what the clause says.

**What it costs.** A signal a person never opens changes nothing, and the layer
that produces it is a reader: `ops/` reads the pipeline's inputs and its recorded
outputs and never feeds anything back, so every model request is byte-identical
with the layer in use or not
([the ops layer](notes/2026-10-07-the-ops-layer.md)).

## The two departures, side by side

| the brief | this repository | the file |
|---|---|---|
| a model orchestrates evidence retrieval | `ops/sources.py` and `ops/evidence.py`, deterministic, run before any model call | `ops/evidence.py` |
| risk signals feed the Judge Agent | risk signals go to the reviewer's packet and the queue, under `POL-GEN-01` | `ops/risk.py`, `ops/escalation.py` |

Both departures are stated as departures in the submission description
([the description](submission/description.md), section 3) rather than presented
as the brief's own design.

# The ops layer: the stretch goals that leave every model request unchanged (2026-10-07)

`ops/` is the layer a support team would run around the pipeline. It was added
in five parts, and every part is held to the same three rules. This note states
the design rule, gives each part's command, and says what each part does **not**
do.

## The design rule

**`ops/` reads the pipeline's inputs and its recorded outputs, and never feeds
anything back into a brief or a prompt.** Nothing in the layer writes to a case,
a policy file, a prompt or a run; nothing in `tribunal/` or `eval/` imports it;
and no module in it imports `tribunal.llm`, `urllib`, `http`, `socket` or any
other network client. A run made with the layer in use is byte-identical to the
same run made without it, and the offline replay is green either way.

Three rules follow from that, and they are asserted once, over **every** command,
in `tests/test_ops_layer.py` rather than once per part:

1. **It never reads an answer.** No module opens an answer key, a `grade` event,
   or anything under an `answers` directory. The test runs every command over the
   corpus with `io.open` **and** `builtins.open` patched to raise on any path
   containing `/answers/`, and checks that no output carries an `expected` or a
   `matched` field. (The words themselves occur inside the judge's own prose —
   "matched" is an ordinary English word in an explanation about an ERP gantry —
   so the rule is enforced on fields, which is the part that is an answer.)
2. **It writes nothing unless it is given `--out`**, and an `--out` is refused
   inside `runs/`, `data/`, `policy/`, `prompts/`, `tribunal/`, `eval/answers/`
   or either sealed root. The guard lives once, in `ops/__init__.py`, and its
   sealed half is a call to `eval.sealed_roots.refuse_a_sealed_destination`
   rather than a copy of it.
3. **Every threshold it applies is read from the loaded policy text.** A sentence
   that has moved or changed is refused rather than resolved against a number
   written in Python.

Two more hold throughout: no wall clock is read unless the command is given
`--now`, and outputs are sorted, so two runs of one command are byte-identical.

## The parts, and their commands

### Part 1 — fraud and bad-faith signals (`ops/risk.py`)

```
python3 -m ops.risk --case N
python3 -m ops.risk --case-file <path>
```

Reports the five policy tests — `POL-RD-06`, `POL-RD-08`, `POL-NS-07`,
`POL-NS-09(c)`, `POL-NS-09(d)` — for the tests the case's category has, each
with the clause, the side, the field values, the threshold sentence quoted out of
the loaded policy, and whether it tripped. Exactly four trip over the corpus:
105 `POL-RD-06`, 107 `POL-RD-08`, 207 `POL-NS-07`, 213 `POL-NS-09(c)`. Beside
them it prints `repeat_party`, an attention flag and not a policy test: the same
`rider_id` or `driver_id` in another dispute of the same case root within 30 days.

`POL-NS-09(c)` reads a counter on **each** profile — the same disputes counted
from both sides — so it takes the larger of the two rather than a sum, and is
reported against the side `PAIR` rather than against one party. The lifetime
counters `prior_no_show_flags` and `prior_deviation_flags` are never read: the
policy names them as near-synonyms that must not be substituted, and case 208 is
the trap.

**What it does not do.** It rules on nothing — `POL-GEN-01` forbids a profile
from establishing a fact about the trip — and it reads no profile field other
than the five counters its clauses name. Its signals go to a human and to the
queue, never to the judge: the judge already receives the same counters in the
brief and applies the same tests through the policy.

### Part 2 — the escalation packet and the review step (`ops/escalation.py`, `ops/review.py`)

```
python3 -m ops.escalation --run-dir <dir> --case N [--format json|md] [--out <path>]
python3 -m ops.review --run-dir <dir> --case N --packet-sha256 <hex> [close's own arguments]
```

`POL-RD-10` and `POL-NS-09` say what a reviewer is handed. The packet holds the
case, the trigger, the judge's explanation **verbatim**, the drafts, both advocate
briefs with the referee's verdicts, the admissibility report, every clause id
relied on, the ruling's referrals and directives, part 1's risk signals, the fare
lines, and a timeline of the case's calls. It refuses a case whose ruling is not
`ESCALATE` unless given `--any`.

The review step wraps `python3 -m tribunal.precedents close` with one more
requirement: `--packet-sha256` must be the digest of the packet rebuilt now, so a
decision cannot be recorded against a packet the reviewer did not read.
Everything else passes through, and the closure rules are the ones
`tribunal.precedents` already enforces.

**What it does not do.** It does not decide anything, and it does not paraphrase
the judge: the open question is the judge's own sentence. The timeline leaves out
the `grade` event **by name**, because that event carries the answer key's
expectation; no answer key is opened anywhere in the layer.

### Part 3 — queue, SLA and routing (`ops/queue.py`, `ops/config.json`)

```
python3 -m ops.queue --run-dir <dir> [--now <ISO instant>] [--config <path>]
```

Routes each dispute of a run into `SAFETY_FAST_TRACK`, `HUMAN_REVIEW` or `AUTO`,
orders them into four tiers — the safety lane, then human review with a tripped
part-1 signal, then the rest of human review, then auto — and within a tier by the
earliest due time, the larger contested amount and the case number. With `--now`
it reports the time left or `BREACHED`. It also reports the measured auto-ruling
SLA as a count of cases: 14 of 24 on the corpus run, against the 5-minute target
on `wall_seconds`.

The targets are the team's own and live in `ops/config.json`, whose `note` says so
and names Ryde's baseline from the brief. The in-scope categories are read off
`tribunal/loader.py`'s own category-to-policy map rather than typed.

**What it does not do.** It changes nothing in `tribunal/`: the router simply does
not hand a dispute on, and `auto_rulings_enabled` false stops at the router. It
routes and reports; it decides nothing, and a tripped risk signal **orders** a
human review rather than rerouting a case the pipeline already decided.

### Part 4 — evidence collection over mocked source systems (`ops/sources.py`, `ops/evidence.py`)

```
python3 -m ops.evidence --case N
python3 -m ops.evidence --case-file <path>
```

Six adapters — `TripService`, `TelemetryService`, `ChatService`,
`PaymentsLedger`, `ProfileService`, `AdvisoryFeed` — over one index built on a
case root, each exposing only a key lookup. The collector is given only the
dispute: it looks the trip up first so the party ids can be read off the trip
record, queries every other adapter, and returns the artifacts in the order every
case file files them. It prints the retrieval log and the found-versus-listed
check.

**What it does not do.** No model chooses what evidence exists, and no network is
reached: it is a deterministic service over an index of the repository's own case
files. It never reads `dispute.evidence_ids` to decide what to fetch — that list
is the check, not the instruction. And it returns exactly what the case file
holds: for all 29 corpus cases and all 100 cases under `data/external/`, each
against its own root, the collection equals the case file's `evidence` array
exactly, and a brief built from the collected case has the recorded
`brief_sha256`.

## What none of the parts do

None of them makes a model call, launches a browser, or writes anywhere but a
path the caller names with `--out` and is allowed to name. None of them reads an
answer key. And none of them changes a byte of any request sent to the model:
`tribunal/`, `prompts/`, `policy/`, `runs/` and `data/` are untouched by the whole
layer, so the offline replay and the freeze gate read what they read before.

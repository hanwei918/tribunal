# The architecture diagram (2026-10-10)

**Where this starts.** `8bed8b5` (part 10), whose predecessor commit `83d9bd5`
was part 9b. The freeze tag `freeze-2026-10-09` is on `9ca7313`, at policy
version 6.

**What this part does.** The track brief lists an **architecture diagram** among
the things the solution should include, and the repository had none. This part
draws the system as it is at the freeze tag, with nothing in it that does not
exist, and explains it one box at a time. Nothing in `tribunal/`, `prompts/`,
`policy/`, `runs/` or `data/` is changed, and no figure in this repository moves.

## What was added

| file | what it is |
|---|---|
| `docs/architecture.svg` | One hand-written SVG, a 1600 by 1000 viewBox on a white background, three horizontal bands and a bottom-right box. |
| `docs/architecture.md` | One page, in the order of the diagram: one short paragraph per box, naming its file. |
| `tests/test_architecture.py` | The test the sheet asks for. **Written, not run.** |

The diagram is in three colours plus grey: blue `#1f6feb` for the pipeline,
orange `#d9822b` for the human and operations layer, green `#2da44e` for
learning, and grey `#57606a` for data and records. Every arrow has a direction
and, where it carries something, a short label. The three bands are Band A, the
case path (nine stages, left to right); Band B, the human and operations layer;
and Band C, learning. Under Band A is a thin grey strip for the record and the
runtime model, and in the bottom-right corner a grey box for what is measured
rather than claimed.

## How it was checked

**Run no tests at all**, per the sheet: the owner runs the new test and the full
suite outside the sandbox, and renders the SVG. No model call was made and no
browser was launched.

Each box was drawn from its file rather than from the sheet. Before a box was
written, the file it names was opened and the behaviour it states was confirmed:
`tribunal/loader.py`, `tribunal/pipeline.py`, `tribunal/prepass.py`,
`tribunal/facts.py`, `tribunal/brief.py`, `tribunal/referee.py`,
`tribunal/transcript.py`, `tribunal/events.py`, `tribunal/model.py`,
`tribunal/policy_versions.py`, `tribunal/precedents.py`, `ops/risk.py`,
`ops/sources.py`, `ops/evidence.py`, `ops/queue.py`, `ops/config.json`,
`ops/escalation.py`, `ops/review.py`, `eval/policy_gaps.py`, the four
`prompts/v1/` files the diagram names, and `data/PUBLIC-CONTRACT.md`.

The SVG was read back with the standard library: it parses as XML, its root is
an `svg` in the SVG namespace, its viewBox is `0 0 1600 1000`, it holds no
`script`, no `image` and no `href` attribute, and it is pure ASCII. Every
path-like token in the SVG and in the page was extracted and resolved against
the repository: 23 in the SVG and 25 in the page, none missing.

## The differences between the sheet and the code

The sheet asks that where a file does not do what the sheet says, the diagram
draws what the file does and the difference is listed. Four were found, none of
them a defect:

1. **"Waypoint approach" and "platform events" are not `tribunal/facts.py`'s
   own names.** The module's approach functions are `gantry_proximity`, which
   reports how close a trace came to each ERP gantry line on a fare breakdown
   (the figure `POL-RD-09(4)` weighs), and `bounding_box_approach`, which
   reports how a trace stands against a traffic advisory's bounding box (the
   figure `POL-RD-03(c)` weighs). Neither is named for a "waypoint". The trip
   record's `events[]` array is passed through to the brief by
   `tribunal/brief.py` and masked there from version 6; what `tribunal/facts.py`
   does with events is read the recorded pickup and dropoff as the endpoints of
   the polyline `POL-RD-01` measures. The box names `tribunal/facts.py` and says
   "waypoint approach, events", and `docs/architecture.md` spells the two
   functions out.

2. **Box 1's evidence list is a short list of seven types.** The sheet names a
   trip record, GPS traces, a chat log, a fare ledger and party profiles;
   `data/PUBLIC-CONTRACT.md` fixes seven distinct artifact types, with
   `FARE_BREAKDOWN` for the sheet's "fare ledger" and one or two
   `TRAFFIC_ADVISORY` artifacts a case as well. The page names all seven.

3. **Box 7's referee discards more than the sheet says.** The sheet says it
   discards any claim without a resolving evidence id and clause id;
   `tribunal/referee.py` also discards a claim that cites an impaired artifact
   without naming its issue code, and one grounded on a context-only profile
   field. The page lists all four grounds.

4. **Box 9's four rulings sit beside a fifth value.** The sheet lists
   `FULL_REFUND`, `PARTIAL_REFUND`, `NO_ACTION` and `DRIVER_COMPENSATION`;
   `tribunal/pipeline.py`'s `RULING_VALUES` also carries `ESCALATE`, which is
   what the floor, a tie, no valid draft and a policy trigger publish. The page
   says so.

One reading rather than a difference: the sheet's "body text at least 18 px,
titles 24 px" is read in the SVG's own viewBox units, and the diagram uses 18 px
for body text and 24 px for the band titles.

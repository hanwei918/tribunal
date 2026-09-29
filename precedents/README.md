# The precedent library

`precedents/precedents.jsonl` holds decisions a human reviewer has closed. When a
run is given `--precedents`, up to three of those entries are shown to the judge,
chosen because they share clauses with the case in front of it.

**This directory holds no entries today.** It ships with this README and an empty
store, because a library is built from closures a person has actually made and
there are none yet.

## What the store is

An append-only, hash-chained log: one `closure` event per entry, written by
`tribunal.events.EventLog` — the same class a run's `events.jsonl` uses, so the
chain is verified by the same `python3 -m eval.events --verify` walk and a second
closure continues the chain rather than restarting it. Nothing truncates,
rewrites or reorders the file. An entry that is superseded stays in it.

Each entry carries:

| Field | What it holds |
|---|---|
| `precedent_id` | `P-0001`, … |
| `source` | the set, the `case_no`, the `dispute_id`, the repository-relative run directory, and the sha256 of the closed case file |
| `category` | the dispute category |
| `system_outcome` | the four graded fields the system produced |
| `decision` | the four graded fields the human decided |
| `clause_ids` | the clause ids the human rested the decision on |
| `amount_contested_sgd` | the case's contested amount |
| `summary` | at most 300 characters |
| `closed_by` | the reviewer |
| `policy_version` | from the case file's `configuration`, or 1 |
| `supersedes` | the `precedent_id` this entry replaces, or `null` |

The set is derived from the run directory's path, not from the case file, because
a schema-1 case file has no `development_set`.

## What an entry may never carry

No field name from `loader.FORBIDDEN_KEYS` — `ground_truth`,
`expected_ruling`, `expected_amount_sgd`, `expected_driver_compensation_sgd`,
`expected_referrals` — and none of `rationale`, `difficulty`,
`governing_clauses`, `matched`, `expected`, `grade`. The check is recursive and
runs before anything is written.

## Closing a case

    python3 -m tribunal.precedents close --run-dir DIR --case N --ruling R \
        [--amount A] [--driver-compensation B] [--referral TEXT]... \
        --clause ID [--clause ID]... --closed-by NAME --summary TEXT \
        [--supersedes P-xxxx]

It reads five fields from the case file — `case_no`, `ruling`, `brief_sha256`,
`development_set` and `configuration` — and never reads `matched` and never reads
`events.jsonl`. It rebuilds the case's brief and refuses when the rebuilt digest
is not the recorded `brief_sha256`, when the ruling is not one POL-GEN-03
licenses, when the ruling is `ESCALATE`, when an amount has more than two decimal
places, when a clause id or a referral's leading clause does not resolve in the
case's policy, and when the case already has a closure that `--supersedes` does
not name.

    python3 -m tribunal.precedents list     # print the library
    python3 -m tribunal.precedents verify   # walk the chain, exit non-zero on a break

Both are read-only and neither calls a model.

## What the judge is shown

The judge receives a `precedents` key holding a fixed note and up to three items,
each with a `precedent_id`, a `category`, its `clause_ids` and its `ruling`.
**No amounts and no summaries travel in the block**: an item is a decision, not a
figure to copy, and the note says in its own words that a precedent is not
evidence and not policy and that no precedent id may be cited as a ground.

Nothing matches when the library is empty, and then the key is absent from the
judge's message entirely rather than sent empty.

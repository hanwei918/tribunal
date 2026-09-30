# The freeze moved to this commit

**2026-09-30.** The sealed set is run once, and the rule that dates it says
"after the 10 October freeze" (`docs/notes/2026-09-25-the-standing-rule-change.md`,
*The rule that is*). This note **moves that freeze to this commit** and records
the freeze before the set enters the repository. The sealed set itself is
imported in a later commit, under the tag this note creates.

Nothing in this note changes a ruling, a prompt, a policy or a case file. It
records a date and a set of digests.

## The rule change, and why

- **The rule that was.** A fresh sealed set, drafted without access to this
  repository and seen beforehand by nobody who works on the prompt, is run
  exactly once after the 10 October freeze; that single run is the only figure
  the submission reports as generalisation.
- **The rule that is.** The freeze is **now**, at the tag `freeze-2026-09-30`.
  The sealed set is run once from this commit, and that run is the
  generalisation figure.
- **The reason.** No pending change would alter a ruling. Everything still
  outstanding before submission touches documents, the viewer, or switches that
  stay off: notes, `runs/README.md`, the viewer's panels, and the `--precedents`,
  `--ablate`, `--policy-version` and `--verify-drafts` switches, all of which are
  off in the configuration below. Moving the date forward does not make the
  figure less honest; leaving the system able to change under a run that has
  already been taken is what would.
- **The precedent.** The change is recorded in its own dated note **before the
  set is in the repository**, exactly as the 2026-09-25 rule change was recorded
  in `docs/notes/2026-09-25-the-standing-rule-change.md` rather than folded into
  the note it amended. The 2026-09-25 note is not rewritten and neither is any
  other: each records the rule in force on its own date.

## What is frozen

The `tribunal/`, `prompts/` and `policy/` trees at the tag `freeze-2026-09-30`.

| file | sha256 |
|---|---|
| `prompts/v1/judge.system.md` | `73961ae5d750c8e4ecbb9feb1ab456ae6e3994c6c4600ccdd008d2bcf3db86a9` |
| `prompts/v1/advocate.system.md` | `15cd5aadb90794f86c8f214afd42e4f9b616a2112ff583e6beb4693bbe352570` |
| `prompts/v1/stance.driver.md` | `7e0cb843437408155e75ac41fbcbebbfb3650dc742d6828465cc2d718610cb22` |
| `prompts/v1/stance.rider.md` | `4b626f29ededa14526d766286565dafdf22933763db322bec6a024a8a20444d6` |
| `policy/general.json` | `12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf` |
| `policy/no_show.json` | `7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf` |
| `policy/route_deviation.json` | `628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d` |

`prompts/v1/` also holds `README.md`, `policy_drafter.system.md` and
`verifier.system.md`; those three are not part of the frozen judge path (the
drafter belongs to the policy-gap loop and the verifier is off), and the tag
freezes the whole tree regardless.

**The owner makes the sealed run only if this holds:**

    git diff --quiet freeze-2026-09-30 -- tribunal prompts policy

A non-empty diff means the code that would be measured is not the code that was
frozen, and the run is not the frozen run. The run's own `run.json` records its
commit and whether the working tree was clean, so the check is made twice — once
by hand before the run and once by the record the run leaves behind.

## The configuration

| switch | value |
|---|---|
| model | `deepseek/deepseek-flash` |
| judge votes | 4 |
| verifier (`--verify-drafts`) | off |
| precedents (`--precedents`) | off |
| ablation (`--ablate`) | none |
| policy version | 1 |
| `--timeout` | 900 |
| `--concurrency` | 2 |
| case deadline | the default, `pipeline.DEFAULT_CASE_DEADLINE_SECONDS` = 2400 s |

The judge is asked four times per case — three sampled drafts and one
position-swapped — and the four graded fields are voted together at a quorum of
three. Every one of the switches that would change what the agents are given is
off, so the run measures the pipeline and the brief as committed.

## The protocol

- **The run is one command.** A case that fails is retried **with the same
  command** until every case has a result. A failure here means `TRANSPORT`,
  `TIMEOUT`, `DEADLINE` or `SHAPE`.
- **A case that has a result is never re-run**, and `--force` is refused for
  this set **in code** rather than by convention (added with the set's import).
- **The results are committed exactly as produced and graded once.**
- **The key is never changed after the run.** A disagreement with the key is
  recorded, not corrected. `eval/answers/wild/ground_truth.json` is frozen from
  the moment it is imported, under the standing rule in `START-HERE.md`.
- **The run reports**: the four-field exact score and each field alone;
  escalation precision and recall; and the score per category.
- **This is the submission's only generalisation figure.** It is reported beside
  the development figures — the 29-case corpus and the fifteen-case second set —
  and is **never summed with them**. One figure over 64 cases plus another over
  44 is not a measurement of 108 cases.

## A known defect, left as it is

`prompts/v1/judge.system.md` calls the referee's output `referee_ledger` and
`referee_flags`, while the message it is answering carries `referee.ledger` and
`referee.flags` (recorded in `docs/notes/2026-09-28-provenance-currency-and-three-defects.md`).

**The development figures were produced under this wording, and it is not
changed.** Correcting it now would mean the sealed run measured a prompt no
development run has ever measured, which is the one thing the freeze exists to
prevent. The defect is recorded here so that it is a known property of the
frozen system rather than a discovery made afterwards.

## The provenance the set's author stated

As she stated it on 2026-09-29 and 2026-09-30:

- She did not read this repository's case files.
- Her generator is not derived from this repository's.
- The answers are in a separate file and give all four graded fields.
- The archive's `eval/wild/MANIFEST.json` says:
  - 64 cases were derived from real complaints;
  - `gen/validate.py` passes;
  - `gen/semcheck.py` independently re-derives 61 of the 64 rulings, and the
    three differences — **502, 515 and 520** — are explained there.

These are the author's statements, recorded as stated. This repository has not
verified them and cannot: verifying the generator would mean reading it against
its cases, which is the reading the sealed set exists to keep out of the
development process.

## What the owner's structure-only check found

Reading **no case content and no answer** — structure and counts only:

- The archive's sha256 is
  `73440528584f78149f5e977b02dd17183070d2686a72ccfc6061337e6c1b6e65`.
- There are **64** case files, numbered **501 to 627**: **37
  `ROUTE_DEVIATION`** and **27 `NO_SHOW_CHARGE`**. (64 cases over a 127-wide
  number range, so the numbering is not contiguous and the count is not the
  range.)
- The cases use schema **1.2.0**, carry **7 artifacts** each, and put
  `accuracy_m` on every GPS point.
- There is **no answer field in any case file**.
- `brief.build_brief_for_case` builds all 64.
- `en/` holds **84** English source seeds, of which **62** were used. `en/` is
  answer-bearing and is not imported.

## What this note does not do

It does not import the set. The import — the file map, the digests of every
imported file, the `wild` registration in `eval/development_sets.py`, and the
guards — follows in a later commit, after this note is committed and the tag is
pushed. Until the sealed run is committed, no case content and no answer value
is printed, quoted or summarised anywhere in this repository.

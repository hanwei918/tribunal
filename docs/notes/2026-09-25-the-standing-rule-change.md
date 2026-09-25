# The standing rule, changed

**2026-09-25.** The judge prompt is no longer frozen at prompts digest
`829ccc8f`. This note records the change, its reason and its date.
`docs/notes/2026-09-24-the-frozen-prompt-run.md` is **not** rewritten: it records
the rule that was in force on 2026-09-24, and rewriting it would destroy the
record of what was believed then. A dated pointer under its section 9 leads here
instead.

## The rule that was

Section 9 of the frozen-prompt note said:

> **The judge prompt is frozen at prompts digest `829ccc8f…`.** This is the run
> it is frozen from. 105 and 211 are recorded here, not fixed: no prompt was
> changed after this run and none may be.

The freeze was defensible because of the set it was measured on. The corpus is
29 cases, and every case in it had already been read while the prompt was being
written. A further change could therefore only be informed by the same 29 cases
it would be scored against, which is fitting to a sample rather than measuring
against one. Freezing the prompt was the honest response to that: it stopped the
fitting and it made the 27/29 a figure about a prompt that no longer moved.

## The rule that is

- The judge prompt **may change until 6 October 2026**, and **only in response
  to failures seen across both development sets**, with every change
  **regression-run on all of them** — the 29-case corpus and the fifteen-case
  second set.
- **After 6 October 2026 it is frozen.** No change after that date, whatever it
  would fix.
- A **fresh sealed set**, drafted without access to this repository and seen
  beforehand by nobody who works on the prompt, is **run exactly once** after
  the **10 October freeze**. That single run is the only figure the submission
  reports as **generalisation**.

## Why the premise stopped holding

The freeze rested on there being one development set and no other. On
2026-09-25 a second development set was added — fifteen cases drafted by a
separate model, under `data/external/codex/`, with their own answer key at
`eval/answers/codex/ground_truth.json`. A change to the judge prompt can now be
informed by cases the corpus does not contain and was not written against, which
is exactly what the old premise denied.

What the second set does **not** buy is a generalisation figure, and the note
that describes it says so: it shares one template, it re-tests traps the corpus
already tests, and it was not drafted blind to the corpus's ideas. It is a second
development set, which is what the new rule calls it. The generalisation figure
is the sealed set's, and there is exactly one of those.

## What the new rule costs, and what it buys

It buys a reason to change the prompt that is not "a case I have read got worse".
A change made to fix 105 or 211 must not break the other twenty-eight or the
fifteen, and that is now checked rather than assumed.

It costs the clean statement the old note could make. Under the old rule there
was one prompt and one figure; under the new one the prompt is provisional until
6 October and the corpus figure is a development figure until the sealed set
runs. Nothing in the submission may present a development figure as a
generalisation figure, and the submissible line recorded in the frozen-prompt
note is unchanged for as long as the prompt is at `829ccc8f`.

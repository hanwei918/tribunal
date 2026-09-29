# The viewer's money, its labels, and its two new panels

Task 7 changes one file of code, `ui/build.py`, and one committed artefact,
`ui/dist/index.html`. Four things: money shown with two decimals, four labels
put in front of a reader where the page showed a run's own token, two new panels
inside the judge step, and the rebuild.

Nothing here changes what the page reads. The viewer reads the same files it
always did — the recorded run, the rebuilt brief, the answer key at
`eval/answers/ground_truth.json` — and the two new panels are drawn from blocks
that were already travelling on the case file.

## Money is formatted at display time, and only there

The rule is one sentence: **the data keeps the literals the run recorded, and
the page writes two decimals at the moment it renders one.** So `money()` is a
function in the page's script and nothing else moved.

- `eval/grade.render_money` is untouched. It is the pipeline's renderer and it
  returns `str(Decimal)`, which is why a key's `Decimal("4")` reaches the data
  block as `"4"` and not `"4.00"`.
- The data block still carries every money value as a string, and
  `TheRunTests.test_money_is_carried_as_its_own_decimal_literal` still pins that
  structurally. Formatting in Python would have broken it; formatting on the
  page cannot.
- `"null"` is what the grader writes for an amount that was never set, and it
  reads as `none` on the page. A value that is not a number at all — the
  grader's `"<not a number>"` — is shown as it came, because inventing a figure
  for it would be worse than showing the one that is there.

Nine sites, listed in the test as expressions so a reverted one is caught:
`proposalLine`'s two amounts, `draftBox`'s two, the dispute's contested amount,
the judge's ruling amounts, and `renderKey`'s two columns. `renderKey` is the
one worth naming: its two sides are the key's figure and the run's, and showing
`4.00` beside `4.00` is exactly what a reader comparing them needs.

## Four labels, and the raw token kept as a class name

The page shows a reader the run's own tokens in four places, and each now gets a
label. The tokens are not thrown away: the stylesheet colours the vote outcomes
and the draft kinds by those very names, and a test asserts the class is still
the token.

| Where | Before | Now |
|---|---|---|
| the vote outcome, in the grid and in the summary | `carried_not_unanimous` | `carried, not unanimous`, with `carried_not_unanimous` still the class |
| the draft kind, in the draft line | `position_swapped` | `position-swapped` |
| the agreement badge | `3 of 4 agreed` | `3 of 4 drafts agree` |
| an abstention | `abstained, and voted for nothing: CONTRADICTED_BY_EVIDENCE: "…"` | a plain sentence, with the code kept in the element's `title` |

The abstention is the one that needed a decision. The recorded string is a
reason code, and one of the codes carries the statement the verifier rejected —
so the page cannot simply print it and cannot simply drop it. It prints a
sentence and keeps the whole recorded string in the `title` attribute, which is
the same device `evidenceChip` already uses for a chip that is not in the brief.

## The verifier panel, and where it comes from

`_vote_payload` now carries the vote's `verification` block **when the run
recorded one**. The key is added rather than written as null, so a case decided
with the verifier off has no such key at all and the page has nothing to draw
from. That is the whole of the change to the payload, and it is the queue's
"extended only with keys that are present".

The panel is grouped by draft, reading the run's own `draft` field off every
judged statement — no verdict is recomputed on the page, which is the same rule
the draft verdicts already follow. Per draft it shows the three counts and then
each contradiction with its materiality, and it quotes the value the brief
holds beside the statement the draft made. When the verifier was called and its
answer could not be used, the panel says so and prints the reason instead of
drawing a panel of zeroes.

## The precedents panel, and where it does not come from

This one reads the case's own top-level `precedents_shown`, written by
`eval/run_benchmark.py` on the case file, and **not** the vote's payload. The
two are different things: the vote is how the ruling was reached, the precedent
list is what the judge was handed before it started.

The distinction the panel exists to draw is between an empty list and an absent
key. An empty list means the switch was on and nothing in the library matched;
an absent key means the case was decided without the question being asked. The
panel is drawn for the first and not the second, and it says which one it is.
A case decided with the switch off must not gain a heading claiming a panel it
never had, which is why the function returns `null` for the absent case and why
`h` skips a null child.

## What the committed page shows, and why neither panel is on it

`runs/deepseek-deepseek-flash/` is a schema-1 run: it records no `configuration`
and its case files carry neither `verification` nor `precedents_shown`, because
both switches postdate it. So the committed page has no verifier panel and no
precedents panel anywhere — not because the code declines to draw them, but
because the run it is built from recorded nothing for them to draw. The test
asserts that on the committed run, and the two panels are exercised on a
hand-built run directory: a copy of the committed one with the two blocks the
runner would have written added by hand.

## What was checked, and how

Two of the four parts are JavaScript, and this suite runs no browser, so the
script's own text is the limit of what a Python test can say about a panel. The
behaviour was checked by running it instead, outside the repository:

- **The formatter and the labels.** The block of the page's script that defines
  `money`, `draftKindLabel`, `outcomeLabel`, `agreementLabel` and
  `abstentionSentence` was extracted and run under `node` with 18 assertions:
  `"4"` and `"4.0"` both give `4.00`, `"35.64"` and `"0.75"` are unchanged,
  `"null"`, `null` and `undefined` all give `none`, `"<not a number>"` is
  returned as it came, `4 of 4` gives `4 of 4 drafts agree`, and each of the
  four shapes an abstention takes gives its own sentence. All 18 passed.
- **The two panels.** The whole script was loaded under `node` with a stub DOM
  and the panel functions called directly: neither panel is drawn for a case
  with no vote, nor for a vote with no `verification`, nor for a case with no
  `precedents_shown` key; an empty list draws the panel and says nothing
  matched; two ids draw it with the ids; the verifier panel gives draft 1
  `1 supported` and `1 contradicted`, draft 2 `1 not in evidence`, marks the
  contradiction `material`, quotes `brief holds 35.64`, and names the draft a
  material contradiction stopped; an unusable verifier prints its reason; and a
  `CONTRADICTED_BY_EVIDENCE` abstention keeps the whole recorded string in the
  `title` while the sentence in front of the reader is the plain one. All 16
  passed.
- **The guards are seen to fail.** Every script assertion in the new test
  classes was checked against the pre-task-7 file: at all nine money sites the
  old text has `text(<site>)` and no `money(<site>)`, and the old file has no
  `outcomeLabel`, no `agreementLabel`, no `abstentionSentence`, no
  `verifierPanel` and no `precedentsPanel`. Each new assertion would have been
  red before this change.

Then, in the repository:

- `python3 -m unittest tests.test_ui_build` on 3.13.12 — **`Ran 84 tests in
  143.372s` / `OK (skipped=1)`**, the skip being the workspace's own
  `RunCurrencyTests`. The module was 69 tests before this task; the two new
  classes add 15.
- `python3 -m ui.build` wrote the page, and `python3 -m ui.build --check`
  reported it **identical to a fresh build at 2,381,422 bytes**. The committed
  page was 2,371,908 bytes; the growth is the two panels, the labels, the
  formatter and the two new keys on each case.

The full suite on both interpreters is the owner's, run once in the final check.

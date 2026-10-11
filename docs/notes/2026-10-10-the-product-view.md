# The product view: the second site, at policy version 6 (2026-10-10)

Part 13 of the sheet. The track asks for a demo walkthrough and for
inter-agent communication to be observable. The viewer that exists
(`ui/build.py` and the page it commits at `ui/dist/index.html`) is a 2.4 MB
evaluation replay at policy version 1: 29 cases, an answer key beside them and a
miss marked wherever the ruling and the key disagree. That is the right page for
a judge of the benchmark and the wrong one for the person who works the queue.
This part adds a second, separate site — `ui/v2/build.py` writing
`ui/dist/v2/` — showing what a support team would have in front of it when
Tribunal runs at policy version 6.

**Nothing that existed was changed.** `ui/build.py` and every page under
`ui/dist/` are untouched; the new code lives in `ui/v2/` and the new output in
`ui/dist/v2/`. Nothing under `tribunal/`, `prompts/`, `policy/`, `runs/` or
`data/` was edited. No test was run, no model was called and no browser was
launched: the owner runs the tests and opens the pages outside the sandbox.

## What is built

`python3 -m ui.v2.build` writes, deterministically:

- `ui/dist/v2/index.html`, the queue — 120 006 bytes;
- `ui/dist/v2/case-<NNNNN>.html`, one page per case, for every case of the four
  committed version-6 runs: `runs/policy-v6/` (29),
  `runs/dev-v2-ext/policy-v6/` (120), `runs/dev-v2/policy-v6/` (1779) and
  `runs/ryde-v3/policy-v6/` (901) — 151 case pages in all, 152 files and about
  11 MB. The largest case page is `case-00210.html` at 122 637 bytes and the
  smallest is `case-02735.html` at 27 308 bytes; the two flagged disputes are
  the small ones because no agent was asked about them.

`python3 -m ui.v2.build --check` rebuilds in memory and exits non-zero if any
committed page differs. Two builds are byte-identical: there is no clock, no
seed and no dictionary iteration in the output path, and the test asserts it.

## What it reads, and what it refuses to invent

Four run directories, the public case file each case was made from (through the
set's own loader), the loaded policy, `ops/config.json`, and — for a case that
went to a reviewer — the packet `ops.escalation.build_packet` builds, called
rather than re-implemented. The brief is rebuilt for every case with
`tribunal.brief.build_brief_for_case` and checked against the `brief_sha256` the
run recorded; all 151 rebuild to the recorded digest, and a case that did not
would be **refused by name** rather than drawn from a brief that merely
resembles the one the agents were handed.

Every number on a page is read from one of those files by the builder. The
confidence floor (0.70), the execution threshold (SGD 8.00), the appeal window
and the two ruling values' definitions are read out of `policy/v3/general.json`
through the loader; the prices, the freeze tag and the commit come from
`eval.v6_runs` and the run's own `run.json`; the model comes from the run; the
amounts, the confidences, the wall clock and the tokens come from the case file
and the transcript; the queue's targets come from `ops/config.json`. Nothing is
typed into a template.

## The queue page

**The five figures**, computed over the 151 cases the page lists:

- **decided automatically: 125 of 151, 82.8%**;
- **sent to a reviewer: 26 of 151, 17.2%**, with the reason codes counted:
  `GEN08_SCOPE` 2, `NO_VALID_DRAFTS` 3, `NO_MAJORITY` 4, `JUDGE_ESCALATE` 17;
- **median time per case: 160.4 s**, the median of the case files' own
  `wall_seconds`;
- **median cost per case: 0.0579 USD**, the median of the per-case cost summed
  from the transcript entries' tokens at the owner's prices (input 0.15, cached
  input 0.003, output 0.6 USD per million);
- **policy version 6 and the model `deepseek/deepseek-flash`**, read from the
  runs.

One table, one row per case, sortable by clicking a header, with a filter row
(all / decided automatically / sent to a reviewer) and a set selector (corpus,
`dev-v2-ext`, 901, 1779), all in plain JavaScript with no request of any kind.
Each row links to its case page.

**The reason codes are the one place this part had to decide something the run
does not hand over.** The pipeline names two escalation causes itself —
`GEN08_SCOPE` when `POL-GEN-08(1)`'s gate holds, and `no_valid_drafts` when every
draft was rejected — and the case file's explanation states both. The other two
triggers are not named anywhere: the vote's outcome says `escalated` when the
panel disagreed, and says `carried` when the judge itself ruled `ESCALATE` on
the merits. The builder reads the trigger off the run's own record in a fixed
precedence and names the two unnamed ones `NO_MAJORITY` and `JUDGE_ESCALATE`. It
adds no fact: it is a name for what the transcript's vote outcome and the case
file's ruling already say.

## The case page

A header — the category, one line of the dispute's own `claim_text` masked
through `tribunal.brief`'s mask function (the same one the version-6 brief
applies, so a registration mark is replaced on the page exactly as it was in
front of the agents), who filed, the amount contested and the status.

**Tab 1, "Ruling".** The disclosure first: "This is a provisional ruling made by
an automated system." Then the ruling value and POL-GEN-03's own sentence for
it, the refund and the driver compensation, and the confidence against the floor
on its scale. Then the appeal path quoted verbatim from POL-GEN-04, and the
execution sentence under POL-GEN-05 built from the case's own monetary effect
against the policy's own threshold. Then the two notices, one to each party,
each stating what was decided, what money moves and how to appeal, with the
judge's explanation quoted verbatim; then both advocates' claims, each marked
kept or discarded with the referee's reason code and detail for every discarded
one; then the evidence, with each artifact's type, `source`, admissibility
status, weight and issue codes.

**Tab 2, "How it was decided".** Six steps — the evidence pack with the derived
facts and the brief's sha256 and the statement that both advocates received the
same bytes; both sides arguing on one brief; the citation check; the four
drafts, three sampled and one position-swapped, each with its ruling, amounts,
confidence and its own explanation; the floor and the triggers; the outcome.
Every step expands to the agent's actual text from the transcript.

**Tab 3, "Human review"** — only for the 26 cases that went to a reviewer. The
escalation packet from `ops.escalation`, with its sha256, and a decision form
following POL-GEN-06: the four decisions the clause names, a reviewer field, a
reason box that must reach `precedents.MIN_REASON_CHARS` characters and cite at
least one evidence id and one clause id of this case — checked in the page's own
JavaScript — and a "Copy the closing command" button producing the
`python3 -m ops.review ...` command for this case and this packet. The page says
plainly that the form closes nothing by itself: there is no server.

**Every page** carries a footer with the commit, the tag `freeze-2026-10-09`,
the policy version and the model, each read from the run.

## Look and feel

A narrow left navigation carrying the queue and nothing else, a header, cards
with soft borders and generous spacing. Ink `#1b1f24` on `#ffffff`, blue
`#1f6feb` for actions, orange `#d9822b` for "sent to a reviewer", green
`#2da44e` for kept, red `#cf222e` for discarded, and a dark theme under
`prefers-color-scheme: dark`. System font stack, body text 16 px. At 375 px the
queue table's rows stack into one column with no horizontal scrolling.

## What the mock-up showed and the code does not

The sheet's own list, and each is absent from the pages: no "Ask" tab, no
what-if runs and no new-dispute form; no two-drafts-plus-a-second-model check —
the run's configuration records one model asked for four drafts and the verifier
off, and the page shows the four drafts and the vote, not a second model; no "9
gates" — the page shows the confidence floor and the reason codes the case file
carries and nothing else; no figure for reviewer overrides or appeals, because
none is recorded — the precedent store holds two closures, both for case 508 of
the held-out set, and neither is a case of these four runs; and no 7-day appeal
window, because POL-GEN-04 says thirty days and the page quotes the clause.

## Where the mock-up and the code disagreed, and what was done

1. **The reason codes.** The mock-up counts reason codes; the run records a code
   for only two of the four triggers. Handled as above: two names read from the
   run, two named by the builder and said to be names.
2. **"Median cost per case, from the transcripts."** The transcripts' entry
   tokens sum to the totals the case file records — checked on all 151 cases, and
   zero for the two scope-gated cases no agent was asked about. The builder sums
   the transcripts, which is what the sheet says.
3. **The execution sentence.** POL-GEN-05's monetary effect is "the refund, the
   driver compensation, or their sum", and on a `DRIVER_COMPENSATION` ruling
   POL-GEN-03 states that the two fields carry the same figure and it is not a
   second payment. The builder counts it once and adds the two fields on every
   other ruling; 30 cases carry both fields, and 6 of them are refund-plus-driver
   pairs where the sum is the right reading.
4. **The closing command's `--ruling` argument.** POL-GEN-06(4)'s VARY "chooses
   a ruling and a remedy from the options the money block enumerates", and this
   form does not enumerate a money block. The copied command carries the ruling
   value the run recorded, and the page says the form closes nothing.
5. **The confidence scale.** The mock-up marks the floor on a 0-to-1 axis. The
   bar is drawn with the confidence as its width and the floor as its tick, both
   read from the files, so no scale end is typed in.

## One defect this part made and fixed, and the guard it left

The first build of this site divided the per-case cost by a million twice and
printed a median cost of `0.0000 USD`. The reason it survived a check is worth
recording: the page and the test that compares the page with the run files both
divided by a million twice, so the two computations agreed — with each other and
with nothing else. `tests/test_ui_v2.py` now asserts the *size* of both medians
against the run's own total, which is a comparison the same mistake cannot
satisfy, and the queue prints `0.0579 USD`. It is the same failure the repository
has met before: two readings of one figure are one reading until something
outside both of them is consulted.

## Two things this part does that are worth naming

**A key-shaped run is rewritten.** The repository scans every published file for`sk-` followed by eight or more word characters before it goes public, and
ordinary prose produces one: case 2738's transcript says "ask-to-cancel". A page
carrying that verbatim would be reported as a leaked credential by the scan that
exists to catch one, so the builder writes that run's first hyphen as a numeric
entity — `ask&#45;to-cancel`, which renders as the same characters and cannot be
read as part of a key. The build prints the page and the count of what it
rewrote, so nothing is done quietly: one page, one run.

**Where the sealed set enters.** `ui/v2/build.py` names no path under
`eval/answers/sealed-v1/`, `data/external/sealed-v1/` or
`eval/external/sealed-v1/`, and during a build it opens none — the test records
every open the whole build makes and asserts it. It does import
`ops.escalation`, which the sheet requires, and that imports the development-set
registry, which reads the sealed set's *index* at import time: twenty-four case
numbers, their dispute ids, trip ids and category, and nothing else. That is the
same import `ui/build.py` has always made. No sealed case file and no sealed
answer key is read, no sealed case is built, and no page names one: the test
checks all three naming forms — a `case-00301.html` link, a "case 301" phrase and
a bare `>301<` cell — and shows each detector able to fire.

## The one small fix before all of this

`python3 -m eval.v6_runs --report`'s "Cost and time" section listed the corpus,
`dev-v2-ext`, `dev-v2` and `ryde-v3` runs and not the precedents run. It now
lists all five, in the same order the module registers them, and the README's
"Cost of the version-6 runs" row carries the fifth figure:
**precedents 0.9289 USD**. `tests/test_readme_figures.py` recomputes all five
from `v6_runs.RUNS + (v6_runs.PRECEDENTS_RUN,)`, so the row and the report cannot
drift apart. The five totals are not disjoint — the precedents run covers fifteen
cases the corpus run also covers — so each is one run's cost and they are never
summed.

## The tests, written and not run

`tests/test_ui_v2.py` holds the seven checks the sheet names, and each is
asserted against the files the pages were built from. It builds the site three
times — once with every file open recorded, once more for the byte-identity
check, and once through `python3 -m ui.v2.build --check` on the command line —
and memoises what it read, so no test builds the site for itself. **No test was
run here**; the owner runs them outside the sandbox.

## Part 37a: the site says one thing everywhere (2026-10-11)

**The queue's routing counts are `eval.business_value`'s.** The queue said
"decided automatically 125 of 151 (82.8%)", because `queue_figures` counted the
13 cases whose money `POL-GEN-05` holds above the execution threshold as
automatic. `python3 -m eval.business_value --report` counts them separately, and
that command is where the README's business-value rows come from, so the page now
shows its three figures as three tiles: **decided and executed 112**, **decided
with the amount held for a person to release 13**, **sent to a reviewer 26**. The
reason an amount is held is printed in the row as well as in the status cell's
`title`, and `tests/test_ui_v2.py` holds the page's three counts to
`eval.business_value.lanes()`.

**What the site is.** The queue's head says what Tribunal does — two AI
advocates argue one evidence brief, a citation referee checks every claim, a
judge answers four times and its majority decides, and a person decides what the
panel cannot — and that every dispute shown is a synthetic test case except case
901, the organisers' sample. It says the figures are development data and links
the README's results.

**The replay is historical.** The replay pages called the policy-version-1 corpus
run "the submission's headline figure", called the wild runs "one of the two
generalisation figures", and showed 901 "re-run under the current pipeline". The
corpus summary now says what that run is — policy version 1, run 2026-09-27, a
judge-only replay for 28 of the 29 cases — the sealed summaries say "one of the
three sealed generalisation figures", the sample case is "re-run on 2026-09-29 at
policy version 1", and every replay page carries the banner: *Historical
benchmark replay at policy version 1. The product view shows policy version 6:
corpus 26/29; sealed-v1 21/24 agreement.* The product view's nav link to it is
renamed **Benchmark replay (policy v1)**.

**Escalated pages.** A case sent to a reviewer produced no ruling, so it no
longer carries the provisional-ruling disclosure; it says instead that no
automated ruling was made, that the disputed amount is held and that a person
decides. Its text is labelled as the drafts' reasoning where a panel ran, and as
the pipeline's own routing sentence where the scope gate stopped before any judge
was asked.

**Layout and accessibility.** Every wide table sits in a container that scrolls
(`.tscroll`) and every grid track may shrink, so the queue's table is no longer
clipped at about 1230 px and a case page does not scroll sideways on a phone.
The muted token was `#6b7280`, which measured 4.39:1 on the page background —
below the 4.5:1 floor body text is held to; it is now `#5b6470`, which measures
5.45:1 on `--bg`, 6.00:1 on `--card` and 5.74:1 on `--soft`, and the test
recomputes all three figures from the stylesheet. The queue's header cells carry
buttons, so sorting is reachable by keyboard, and the cell's `aria-sort` says
which column the rows are ordered by and which way.

**Two builders, one rebuild each.** `python3 -m ui.v2.build` wrote all 152 pages
and `python3 -m ui.build` all six replay pages; no test was run here, and no
model was called.

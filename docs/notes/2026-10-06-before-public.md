# Before the repository goes public (2026-10-06)

The owner is about to make this repository public, and the four parts of the task
sheet dated 2026-10-06 prepare it for a reader who has never seen it. **No model
call was made in any part, and no browser was launched.** The repository's
visibility is the owner's to change and is not changed here.

Three decisions the owner took before the work started, recorded because each
one is visible in the repository afterwards:

- the git history stays as it is and is not rewritten;
- the licence is MIT;
- the Ryde sample stays, and the owner will ask the organisers whether it may be
  redistributed; if the answer is no it will be removed later.

Nothing under `tribunal/`, `prompts/`, `policy/` or `runs/` changes. The one
file under `runs/` that this task touches is `runs/README.md`, which is the
directory's own description rather than a recorded run file; the paths recorded
inside the run files stay exactly as the machine wrote them.

## A. The licence

`LICENSE` is new: the standard MIT text, with the copyright line the owner
specified, `Copyright (c) 2026 Zhou Hanwei, Ji Guofang and Yan Lin (team
Newbee)`.

The README gains a **Third-party material** section at its end. It names the
organisers' sample material — which the Tencent Cloud AI Agent Hackathon
Singapore 2026, Digital Native track (Ryde), gave to participants — and every
file derived from it, each by its exact path: `eval/external/ryde/DISP-002.md`,
`eval/external/ryde/expected.json`, `data/external/ryde/`, `runs/external/ryde/`
and `runs/rerun-2026-09-29/external/ryde/`. It says the files are included only
to show how this system handles that sample, and that they are not covered by
the MIT licence.

`tests/test_repository_hygiene.py` gains the one-line check that `LICENSE` is
there and starts with `MIT License`. It sits in that module rather than in a
module of its own because the module is already about what the repository
carries for a reader who is not its author.

## B. Two viewer fixes, and the rebuilt pages

Both were measured by the owner in a browser on the committed pages, and both
are about text rather than about boxes.

**Long unbreakable text.** Two rules answer it:

- `p.text` — the model's own prose, on the rider step, the judge step and the
  stance view — takes `overflow-wrap: anywhere` at the top level. It is
  `anywhere` and not `break-word` for the reason the id rule already gives: only
  `anywhere` counts towards the minimum width of the box, which is the number a
  grid track is measured against, so the paragraph gives way instead of the
  page. A paragraph is the same paragraph at every width, so the rule is not in
  the phone block.
- Below 600px the stance view's rendered prompt lines — `span.t` inside the
  `li` of `.plines` — take the same declaration. Those lines are `pre-wrap`, so
  the padding inside one is spaces and a single long token, a clause id glued to
  a field name, sets the width of the column it sits in.

`PhoneWidthTests` grows one test for each: the top-level rule read at 375, 600
and 940 px, and the phone-block rule read through `effective_at` at 375 and 600
px and asserted absent at 940. Both were shown red with the two declarations
emptied out, and `ui/build.py` was restored to its digest afterwards.

**Abstained draft lines.** A draft that abstained made no proposal, so its four
graded fields read `null` for the ruling and `none` for each amount and each
referral list — the tokens this system emits for a value, which is a different
thing from a draft that proposed nothing. Both places that drew it now show the
reason code instead and nothing else: the overview's vote table, through
`draftLine`, and the judge step's draft box, which no longer draws a four-field
list for an abstained draft at all. The whole recorded string is still kept in
the element's `title`, as it was. `abstentionSentence` goes with the sentence it
produced; `abstentionCode` and `abstentionLine` replace it, and a draft that
abstained with nothing recorded is named as such rather than shown as `null`.

`RenderedWordingTests` gains two tests: one that no rendered text the harness
collects holds `abstained: null`, and one that keeps the first from passing
vacuously — the code line must be there, in both sealed pages' overviews and in
the judge step of the two held-out cases whose four drafts each abstained. Both
were shown red against the page committed at `5cf7c76`, and the rebuilt page was
restored to its digest afterwards.

Then `python3 -m ui.build` rewrote all six pages and `python3 -m ui.build
--check` reports each identical to a fresh build.

## C. The README, for a public reader

**The live demo** is linked near the top: the corpus page at
`https://tribunal-dpruuzl3id9n.edgeone.dev/`, and the runs index at `/runs/`. The
section says it is a static replay of the committed runs, that it makes no model
call, and that it is hosted on Tencent EdgeOne Pages.

**Running it** is one section with the six things a stranger needs: the Python
version — the standard library only, runnable on 3.9.6 as well as on 3.13 —
`pip install -r requirements.txt`, the key in `.env` as `TOKENHUB_API_KEY` with
`.env.example` added beside it, one command to run a case, one to run the tests,
and one to build the viewer. Every command was run before it was written down,
except the one that calls a model, which was checked against the runner's own
argument list instead: `pip install -r requirements.txt` exits 0 and installs
nothing, `python3 -m ui.build` rewrote the six pages, `python3 -m ui.build
--check` reports each identical, and `python3 -m unittest discover -s tests -v`
is the full suite whose result the Finish section below records.

**Local paths.** `README.md` line 5 and `START-HERE.md` line 8 named
`/Users/hanweizhou/Desktop/Tribunal`; both now name the repository root, as `.`.
The paths recorded inside the run files stay exactly as the machine wrote them,
and `runs/README.md` gains a sentence saying that a recorded run file carries the
absolute path of the machine it ran on.

Nine other tracked files outside `runs/` still hold an absolute path of that
shape: `WORKBUDDY-HANDOFF.md`, `docs/buddy-log/README.md`, four dated notes under
`docs/notes/`, the two generator scripts under `eval/external/wild-v2/gen/`, and
`tests/test_ui_build.py` — whose occurrences are `/Users/someone/...`, a fixture
rather than a real path, and `2026-09-23-what-the-viewer-build-reads.md`, which
already writes it as `/Users/<name>/...`. The task named only the two, and the
rest are dated records or inside `eval/external/`, which this task may not edit,
so they are listed here rather than changed.

## D. The last check

The scan reads `git ls-files` — 1010 tracked files, the six under `ui/dist/`
among them and all six tracked — and then the six `ui/dist/` files again from
disk, so a page that had stopped being tracked would still be read. Every count
is 0 except two, and both are the repository's own test vocabulary rather than a
credential:

| what was looked for | count | where |
|---|---|---|
| `sk-` followed by 8 or more characters | 0 | — |
| `TOKENHUB_API_KEY=` followed by a value | 2 | `tests/test_llm.py`, the two fakes below |
| `SecretKey` | 3 | `tests/test_ui_build.py` twice, `docs/buddy-log/README.md` once |
| `SecretId` | 0 | — |
| `AKID` | 0 | — |
| `-----BEGIN` | 0 | — |
| a `.env` file other than `.env.example` | 0 tracked | — |

The two `TOKENHUB_API_KEY=` hits are `TOKENHUB_API_KEY=from-the-file` and
`TOKENHUB_API_KEY="quoted-value"`, both written by `tests/test_llm.py` into a
temporary `.env` to prove which of the environment and the file wins. The three
`SecretKey` hits are the credential scanner's own needles — `("a secret key",
re.compile(r"SecretKey"))` in `tests/test_ui_build.py`, the fixture string
`"AWSSecretKey = x"` beside it, and the prose in the buddy log that names them.
None of the six is a credential, and the scanner is shown to fire by running it
over a control string holding one of each.

`git check-ignore -v .env` names `.gitignore` line 5, the rule that ignores it,
and `git ls-files .env` is empty: the file exists in the working tree and is
untracked. `.env.example` is not ignored — `git check-ignore -v .env.example`
names line 7, the negation that keeps it committable. No tracked file is a PDF,
a DOCX or a PPTX, and none has a resume-like name.

## Finish

The seven modules the task names, run together:

    python3 -m unittest tests.test_ui_build tests.test_sealed_roots_closed \
      tests.test_repository_hygiene tests.test_wild_run_manifest \
      tests.test_wild_v2_run_manifest tests.test_language tests.test_readme_figures

Ran 259 tests in 559.689s — OK (skipped=1). Those 259 are exactly the seven
modules' own counts — 199, 24, 5, 9, 13, 6 and 3 — so each of the seven was
collected and none went missing.

The whole suite, which the part C section above says is recorded here:

    python3 -m unittest discover -s tests -v

Ran 2053 tests in 3722.752s — OK (skipped=4), exit 0. No test in it makes a
model call.

**The scan, run again over the tree as it now stands.** Part D's scan counted
1010 tracked files; the tree holds 1011, `.env.example`, committed in part C,
being the extra one. Over all 1011 the counts are the same where it matters. In
code — that is, outside this record's own prose — there are exactly four hits:
`TOKENHUB_API_KEY=` followed by a value twice in `tests/test_llm.py`,
`TOKENHUB_API_KEY=from-the-file` and `TOKENHUB_API_KEY="quoted-value"`, each
written into a temporary `.env` by the test that proves which of the environment
and the file wins; and `SecretKey` twice in `tests/test_ui_build.py`, the
credential scanner's own needle `re.compile(r"SecretKey")` and the fixture
`"AWSSecretKey = x"` beside it. `sk-` followed by 8 or more characters is 0,
`SecretId` 0, `AKID` 0 and `-----BEGIN` 0, and a `.env` file other than
`.env.example` is 0 tracked as well. Everything else the scan finds is this record
naming the needles in order to report them — the part D row in the buddy log and the
part D section above — and the scan is run before the words that report it are
written, so it does not count its own report. The scanner is shown to fire by
running it over a control string holding one of each of the six, and it stays
quiet on an ordinary English line.

**The six pages, as committed:**

| page | bytes |
|---|---|
| `ui/dist/index.html` | 2414270 |
| `ui/dist/codex/index.html` | 1155598 |
| `ui/dist/wild/index.html` | 4243482 |
| `ui/dist/wild-v2/index.html` | 1430248 |
| `ui/dist/ryde-901/index.html` | 279546 |
| `ui/dist/runs/index.html` | 31639 |

`git diff --stat freeze-2026-10-03 HEAD -- tribunal prompts policy` prints
nothing and exits 0, so the three trees a run reads are byte-identical to the
freeze tag and nothing in parts A to D reached them.

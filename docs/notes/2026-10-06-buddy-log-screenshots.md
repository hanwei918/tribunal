# The buddy-log screenshots, and two README lines (2026-10-06)

The owner captured twelve screenshots of WorkBuddy's own window, each showing the
end of a real session as WorkBuddy displays it, and this task puts them into the
buddy log and fixes two lines of the README. **No model call was made in either
part, and no browser was launched.** Nothing under `tribunal/`, `prompts/`,
`policy/` or `runs/` changed.

Commits: `2ec1e61` (part A), the part B commit, and the buddy-log cell fill.

## A. Twelve screenshots of real sessions

The twelve PNGs were read out of the folder the owner keeps them in and copied
into `docs/buddy-log/` with a byte copy under their own file names -- no resize,
no crop and no re-encode -- and every destination was hashed against its source:
**12 of 12 match**. The twelve digests are printed in the new section rather than
here, so there is one copy of them and the test is what keeps it true.

`docs/buddy-log/README.md` gains a section, **WorkBuddy sessions, in
screenshots**: one row per file giving the session it came from, the caption and
the file's sha256, and one paragraph under the table saying that WorkBuddy keeps
a full record of every session locally, that the full records are submitted to
the organisers separately, and that they are not committed here because they
include directory listings of the owner's machine.

`tests/test_buddy_log_screenshots.py` parses that section out of the buddy log
rather than restating the digests, for the reason `tests/test_readme_figures.py`
parses the README: a second copy would agree with itself while disagreeing with
the file a reader reads. The table is found by its heading and its own header
row, so a second table added elsewhere in the file cannot be mistaken for it, and
every failure names the file and nothing else. It was shown red twice before it
passed:

- with the first row's digest changed it fails and names
  `12-2026-09-21-first-pipeline-and-transcript.png`;
- with `06-2026-10-05-viewer-fixes.png` moved out of the tree it fails and names
  that file.

Both were restored from a `/tmp` copy afterwards; the buddy log re-hashes to
`66e702f64538ac1a851e28013c7996191da574f132846c6e16efc685b5f8cb4c` and the moved
PNG to `198c8154e788043b63cc1753e67e4f39a4f398fbd44e3ab57e0e030e084f611c`, the
digests each was saved with.

**One thing left as found.** From 2026-09-30 onward the rows of the main table
are separated by blank lines -- 40 of them, the same ones `HEAD` carries -- so on
GitHub that stretch of the table renders as text rather than as one table. A
second defect in the same table is older still: the 2026-10-03 row, *Sealed-run
readiness 2: K*, carries sixteen `|` characters more than a row should, because
it quotes table fragments such as `` `| Target | 17.2% |` `` inside backticks and
a markdown table needs those escaped; it splits into 23 cells instead of 7 and
renders broken. Part A inserted its own row adjacent to the row above it and part
B filled one commit id in, and neither touched any other row. Both defects are
older than this task and are reported rather than repaired here.

## B. Two README lines

### The live demo

The stable address is the project domain, which always serves the latest
deployment; the host the README carried was a single frozen deployment.
`git grep` found it in three places -- `README.md` twice, in the corpus-page link
and the runs-index link, and `docs/notes/2026-10-06-before-public.md` once -- and
all three now read `tribunal.edgeone.dev`. `git grep dpruuzl3id9n` returns
nothing.

### The held-out set's description

The description said the 64 cases are "derived from real complaints". That is the
author's claim, not this repository's finding, and `eval/development_sets.py`
already attributes it -- "64 cases whose author says its traps come from real
complaints". Four places stated the claim in the repository's own voice and now
attribute it the same way:

- `README.md` line 42, the description itself;
- `docs/notes/2026-09-30-the-names-and-the-chinese-text.md` line 51, the
  blockquote introduced by "The accurate description is stated once, in
  `README.md`:" -- a quotation of the description, which has to follow it;
- `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` line 263, the
  correction block that describes the set in the repository's own voice;
- `docs/buddy-log/README.md` line 81, the 2026-09-30 row, which described the set
  in the same words.

Four occurrences remain, and each is the phrase as someone else's words rather
than as a claim this repository makes:

- `eval/external/wild/MANIFEST.json` line 28 -- the archive's own manifest, which
  the work queue's rule 4 puts out of reach and which the task excludes;
- `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` line 138 -- a bullet
  under "The archive's `eval/wild/MANIFEST.json` says:", so it reports what the
  archive says;
- `docs/buddy-log/README.md` lines 161 and 163 -- two dated session rows that
  quote the wording the README carried at the time. Row 163 says in its own words
  that it left the README as found and flagged the overlap; that is the record of
  what the 2026-10-05 session did, and it is kept as written.

Nothing else in the repository was changed for this, and no figure moved:
`tests/test_readme_figures.py` still recomputes every figure in the README from
the committed runs and the frozen keys.

## Finish

- `python3 -m unittest tests.test_repository_hygiene tests.test_language
  tests.test_readme_figures tests.test_buddy_log_screenshots -v` reads **Ran 16
  tests in 92.797s**, `OK`, after part B -- five hygiene, six language, three
  readme-figure and two screenshot tests, so none of the four modules was
  silently dropped. The same four modules read `Ran 16 tests in 83.947s`, `OK`,
  before part B.
- `python3 -m ui.build --check` reports all six pages identical to a fresh build,
  and `tests.test_ui_build` is green beside it. Both are run although the task
  makes them conditional, and the condition is worth stating: the viewer embeds
  the set's registration in `eval/development_sets.py`, not the README's prose.
  The two pages that carry the claim -- `ui/dist/wild/index.html` and
  `ui/dist/runs/index.html` -- already read "whose author says its traps come
  from real complaints" before this task, so no text the viewer embeds moved.
- The twelve PNGs, the buddy log, the README, the three notes and the new test
  module scan **0** for `sk-[A-Za-z0-9_-]{8,}` and **0** for CJK characters,
  against a positive control that fires once on a fabricated key and stays quiet
  on an ordinary English line.

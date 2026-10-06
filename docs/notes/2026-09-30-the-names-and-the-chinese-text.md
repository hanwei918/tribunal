# The names, and the Chinese text

**2026-09-30, part A of the after-held-out-run task. No model call was made.**

The set run once at `freeze-2026-09-30` had been called "the sealed set" in every
document the repository writes. Its own author does not call it that: her README
describes it as a development and regression set and names a **different,
24-case** set as the sealed one. This part does three things — it renames the set
wherever the repository was speaking in its own voice, translates the author's
README out of Chinese, and adds the check that keeps Chinese out of every tracked
text file the rule governs. It changes no figure and no behaviour.

## The name

The repository now calls it **the held-out set (`wild-v1`)**. The rename is a
rename only: every figure, every path and every command is what it was.

| file | what changed |
|---|---|
| `README.md` | the nine results-table rows, the `run` column row, the paragraph above the table, the section heading and the one paragraph that states the set's description |
| `eval/development_sets.py` | the `wild` set's `summary` string, and the module docstring and comments that named it |
| `tests/test_readme_figures.py` | the nine label keys in `expected()` |
| `runs/README.md` | the directory-table row, the section heading, and two sentences |
| `WORKBUDDY-SCOPE.md` | the section heading and the paragraph that describes the import |
| `docs/notes/2026-09-30-the-sealed-run.md` | corrections added, text preserved |
| `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` | corrections added, text preserved |
| `eval/run_benchmark.py`, `eval/baselines.py`, `eval/verify_drafts.py` | docstrings and comments |
| `tests/test_sealed_set.py`, `tests/test_development_sets.py`, `tests/test_baselines.py` | the strings that assert on the renamed prose, and the docstrings around them |
| `tests/test_answer_isolation.py`, `tests/test_policy_versions.py`, `tests/test_precedents.py` | docstrings and comments |

The two notes are **not rewritten**. Each passage that says "the sealed set" or
"the sealed run" now has a dated correction directly under it, saying which set
the words mean and that the passage is kept as written. The heading of the
`development_sets --report` section moved with the code —
`The held-out set (wild-v1), on its own and never in the combined figure:` — and
the two test modules that assert on that exact string were changed in the same
commit.

Two things did **not** move, and the reason is the same for both: they are not
the repository speaking about the set, they are records of what was said on a
date. The notes written before 2026-09-30 (2026-09-25, 2026-09-27, 2026-09-28,
2026-09-29, and the clause-notes note of 2026-09-30) keep every word they were
written with — at the time they were written "the sealed set" was a plan for a
set that did not exist yet, and the two 2026-09-30 notes are where that plan
meets what actually arrived. The author's own files under `eval/external/wild/`
keep her words too, including her README's "the sealed set", which is her name
for her own 24-case set and not a name for `wild-v1` at all.

The accurate description is stated once, in `README.md`:

> 64 cases whose author says its traps come from real complaints, prepared by
> their author as a development set; nobody who changed the system opened them
> before the freeze tagged `freeze-2026-09-30`, and they were run once from that
> tag.

**Identifiers were not renamed.** `SEALED_SET`, `SEALED_SET_RUNS_SUBDIR`,
`assert_not_sealed` and the `SealedSet*Tests` class names still read as they read.
They are internal names, several are asserted on by name, and renaming them would
have bought nothing a reader sees. Only prose, headings, one report heading and
one summary string changed.

### The figures did not move

`python3 -m eval.development_sets --report` prints the same numbers it printed
before the rename, and `tests/test_readme_figures.py` recomputes every figure in
the README's results table from the committed runs and the frozen keys and still
passes. The rename touched no number.

## The author's README, translated

`eval/external/wild/README.md` arrived in Chinese, and the repository's standing
language rule says no tracked text file holds a Chinese character. It has been
**replaced with a faithful English translation**. Its first line says so, and
names where the original is:

> Translated into English from the author's `README.md` in the archive. Nothing
> but the language has changed: the sections, the tables and the list of policy
> findings are the author's, in full.

The translation carries every section the original had, in the original order:
the source line, the relation to the sealed set, the contents block, the two
digests, the validation status, the distribution table, the twenty-row table of
what the set tests, the five findings about the policy, the suggested use, and
the re-running block. Nothing is summarised away and nothing is added.

### The digest of the original

| | |
|---|---|
| sha256 of the original bytes | `8761344077eb9ef2a238c047a18b71b0f6b8f1855d1baeb63ab0ba89e1c9befb` |
| the original as a blob | `b3112099f7307ab3270339754dbf293229d53ceb` |
| the commit that holds it | `3cb059a` |
| the archive it came from | `tribunal-wild-v1(1).zip` |
| CJK code points in the original | 1028, across 338 distinct characters |
| CJK code points in the translation | 0 |

The digest is unambiguous: the archive's own copy of the file and the committed
copy hash to the same value, and both are reachable — the archive by the owner,
the committed copy by `git show 3cb059a:eval/external/wild/README.md`.

### The rule this steps around, and why

The work queue's rule 4 says `eval/external/**` is never edited. This task edits
one file there, on the owner's explicit instruction, and the reason the rule
exists is not touched by it.

Rule 4 exists because those files are answer-bearing: nothing under `tribunal/`
may read them, and nothing may re-serialise them. A README is neither. It is not
read by the pipeline, no digest of it is checked by any code, and translating it
changes no byte any run reads. What the rule protects is the evidence, and the
evidence is intact: the original is preserved byte for byte in the repository's
history at `3cb059a`, and the translation says on its first line where to find
it. The alternative — leaving the file in Chinese — would have meant either a
standing exception to the language rule or a rule that is quietly false, and both
are worse than a translation that names its source and its source's digest.

This is recorded rather than hidden because a reader who finds the rule and the
edit side by side is owed the argument.

## The one Chinese character, and the nine run files

`docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md` quoted a
macOS path with one Han character, `U+7684`, inside the folder name between
`HANWEI` and `MacBook`. The note now writes the character as **`U+7684`**, so the
note itself carries no Chinese.

The same character is inside **nine tracked files under `runs/`**, where it is
part of the path the machine recorded when it wrote them. Those files are records
produced by a run and are **left unedited**: rewriting a recorded run so that a
scan comes back clean would be editing the evidence. All nine are the same
character, 29 code points in total:

| file | code points |
|---|---|
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/events.jsonl` | 1 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/invocations.json` | 5 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/run.json` | 5 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/events.jsonl` | 1 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/invocations.json` | 4 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/run.json` | 4 |
| `runs/codex/deepseek-deepseek-flash/invocations.json` | 3 |
| `runs/deepseek-v4.1-flash/invocations.json` | 3 |
| `runs/deepseek-v4.1-flash/run.json` | 3 |

The 2026-09-27 note lists them in the same place it quotes the path, so a reader
who meets the one character in the note meets the reason it is still in the runs.

## The check

`tests/test_language.py` walks every text file in the repository, skips the
directories that are not repository content (`.git`, `.workbuddy-ai`,
`__pycache__`, `.venv`, `tmp`, `output`) and the one directory that is repository
content and is nevertheless exempt (`runs/`), and fails on any character in the
CJK blocks. A failure names the file and the code points, never the characters,
so the test's own output stays free of them.

Two fixtures keep the check honest rather than merely green: a dirty tree must
report, a clean tree must report nothing, a PNG must not be read as text, and the
exemption must be exactly `runs/` wide — a tree holding the same character under
`runs/`, `docs/` and `eval/` must report the latter two and not the first. The
repository-level test additionally asserts that the walk reaches `README.md`,
`WORKBUDDY-SCOPE.md`, `eval/development_sets.py`, `tests/test_language.py` and
`ui/dist/index.html`, and that it never enters `runs/`, so a walk that silently
found nothing could not pass.

### Shown failing first

The check was run before the translation, against the untranslated README, with
`runs/unit-test-language-before-translation-py3.13.12.log` as its record:

```
test_the_run_directory_is_exempt_and_nothing_else_is ... ok
test_no_tracked_text_file_outside_runs_holds_a_cjk_character ... FAIL
...
AssertionError: {} != {'eval/external/wild/README.md': ['U+3001', ...]} : a file
outside runs/ holds CJK characters: eval/external/wild/README.md (U+3001 U+3002
U+4E00 ...)

Ran 6 tests in 32.798s

FAILED (failures=1)
```

It named the one file that was dirty and nothing else. The first cut of the
module also failed its own exemption fixture — `_directories_to_skip` returned an
iterator, `any(name in skip for ...)` consumed it, and the `runs/` exemption
therefore applied to the first path examined and to no other. The fixture that
caught it is the one named above; the fix returns a `frozenset`, and the
docstring says why.

### Green

After the translation, `runs/unit-test-language-after-translation-py3.13.12.log`:

```
Ran 6 tests in 27.848s

OK
```

## What the scan found

Over every tracked text file outside `runs/`, before this part:

| file | CJK code points |
|---|---|
| `eval/external/wild/README.md` | 1028 |
| `docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md` | 1 |

After it: **zero**. The two files above were the only two, and the nine files
under `runs/` listed earlier are the only remaining CJK anywhere in the tracked
tree, which is why the exemption is one directory wide and named in code rather
than applied silently.

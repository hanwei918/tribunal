# The two version-7 sets imported: `dev-v7` and `sealed-v4`

**2026-10-13.** This is the version-7 import task (part 73). Two sets arrived
together in `tmp/v7-incoming/`, four archives and a `SHA256SUMS` file, and both
were imported from them: `dev-v7`, the version-7 development set, and
`sealed-v4`, the sixth sealed set.

**Nobody on the development side has seen `sealed-v4`'s answers.** Its archive B
was extracted straight into place with `unzip` and never opened: nothing printed,
read, summarised or quoted a file of it, and only `unzip -l` for file names,
`shasum` for digests and its own `answers/MANIFEST.json` -- counts, digests and
provenance -- were used. No case content and no answer value of either set is
printed anywhere in this note.

**No model call was made by this import, and neither set was run.** Both are
registered and neither has a run; `sealed-v4`'s single run is the owner's to
make. Nothing was re-serialised either: every imported file is byte-identical to
its archive entry.

## The archives, verified before anything was imported

`shasum -a 256 -c SHA256SUMS`, run in `tmp/v7-incoming/`, printed `OK` for all
four:

```
b08bf6ee40c5e8be06cab9eb1277c5c54c731ae2d9b1a38fe8e82368e457a854  tribunal-dev-v7-A-cases.zip
213d3626c25ca7f10698479b4f939fb5b26778d29fa7d407b766ef0fd8f8223a  tribunal-dev-v7-B-answers.zip
64d99f2e1bd749209923dd011b6e36be59c124510fbcec926ca2a49ed4cf802d  tribunal-sealed-v4-A-cases.zip
fa6a4d109892488cf78d62d031c8df303a20b04996949428972573a70b93fb51  tribunal-sealed-v4-B-answers.zip
```

The two **A** archives are the cases and the two **B** archives are the answers:

| archive | entries | what it is |
|---|---|---|
| `tribunal-dev-v7-A-cases.zip` | 43 | 40 cases, an index, a README and a canary |
| `tribunal-dev-v7-B-answers.zip` | 50 | the key, its manifest, the author's generator and the second reading |
| `tribunal-sealed-v4-A-cases.zip` | 33 | 30 cases, an index, a README and a canary |
| `tribunal-sealed-v4-B-answers.zip` | 39 | the key, its manifest, the author's generator and the second reading |

## Where the files went

**`dev-v7`** -- 93 files, and nothing is kept outside the repository:

* `data/external/dev-v7/`: `case-05001.json` to `case-05020.json`,
  `case-05051.json` to `case-05070.json`, and `index.json`;
* `eval/external/dev-v7/`: `README.md` and `CANARY.txt`;
* `eval/answers/dev-v7/`: the whole of archive B's tree, byte for byte --
  `answers/` (the key, its `MANIFEST.json` and the format checker's output),
  `generator/` and `notes/`.

**`sealed-v4`** -- 72 files, the same layout:

* `data/external/sealed-v4/`: `case-06001.json` to `case-06015.json`,
  `case-06051.json` to `case-06065.json`, and `index.json`;
* `eval/external/sealed-v4/`: `README.md` and `CANARY.txt`;
* `eval/answers/sealed-v4/`: the whole of archive B's tree, extracted unread --
  `answers/`, `generator/` and `notes/`.

Each set's archive-B tree keeps its own `answers/`, `generator/` and `notes/`
folders under the set's answers root, so the key of each is one level down from
it: `eval/answers/dev-v7/answers/ground_truth.json` and
`eval/answers/sealed-v4/answers/ground_truth.json`. That is what the
registrations record.

**Nothing was re-serialised.** Every one of the 165 imported files was compared
with its archive entry -- 93 for `dev-v7` and 72 for `sealed-v4` -- and all 165
are byte-identical. No imported file of either set carries a CJK character, a
non-ASCII byte or an `sk-` credential, so no language exemption was needed.

## The file lists, names only

`dev-v7`, archive A, `tribunal-dev-v7-A-cases.zip` (43 entries):

```
cases/CANARY.txt
cases/README.md
cases/case-05001.json
cases/case-05002.json
cases/case-05003.json
cases/case-05004.json
cases/case-05005.json
cases/case-05006.json
cases/case-05007.json
cases/case-05008.json
cases/case-05009.json
cases/case-05010.json
cases/case-05011.json
cases/case-05012.json
cases/case-05013.json
cases/case-05014.json
cases/case-05015.json
cases/case-05016.json
cases/case-05017.json
cases/case-05018.json
cases/case-05019.json
cases/case-05020.json
cases/case-05051.json
cases/case-05052.json
cases/case-05053.json
cases/case-05054.json
cases/case-05055.json
cases/case-05056.json
cases/case-05057.json
cases/case-05058.json
cases/case-05059.json
cases/case-05060.json
cases/case-05061.json
cases/case-05062.json
cases/case-05063.json
cases/case-05064.json
cases/case-05065.json
cases/case-05066.json
cases/case-05067.json
cases/case-05068.json
cases/case-05069.json
cases/case-05070.json
cases/index.json
```

`dev-v7`, archive B, `tribunal-dev-v7-B-answers.zip` (50 entries):

```
answers/MANIFEST.json
answers/check_set_output.txt
answers/ground_truth.json
generator/compare_second_reading.py
generator/generate.py
generator/specs_dev_v7.py
generator/tribunal_engine.py
notes/NOTES.md
notes/second_reading/case-05001.answer.json
notes/second_reading/case-05002.answer.json
notes/second_reading/case-05003.answer.json
notes/second_reading/case-05004.answer.json
notes/second_reading/case-05005.answer.json
notes/second_reading/case-05006.answer.json
notes/second_reading/case-05007.answer.json
notes/second_reading/case-05008.answer.json
notes/second_reading/case-05009.answer.json
notes/second_reading/case-05010.answer.json
notes/second_reading/case-05011.answer.json
notes/second_reading/case-05012.answer.json
notes/second_reading/case-05013.answer.json
notes/second_reading/case-05014.answer.json
notes/second_reading/case-05015.answer.json
notes/second_reading/case-05016.answer.json
notes/second_reading/case-05017.answer.json
notes/second_reading/case-05018.answer.json
notes/second_reading/case-05019.answer.json
notes/second_reading/case-05020.answer.json
notes/second_reading/case-05051.answer.json
notes/second_reading/case-05052.answer.json
notes/second_reading/case-05053.answer.json
notes/second_reading/case-05054.answer.json
notes/second_reading/case-05055.answer.json
notes/second_reading/case-05056.answer.json
notes/second_reading/case-05057.answer.json
notes/second_reading/case-05058.answer.json
notes/second_reading/case-05059.answer.json
notes/second_reading/case-05060.answer.json
notes/second_reading/case-05061.answer.json
notes/second_reading/case-05062.answer.json
notes/second_reading/case-05063.answer.json
notes/second_reading/case-05064.answer.json
notes/second_reading/case-05065.answer.json
notes/second_reading/case-05066.answer.json
notes/second_reading/case-05067.answer.json
notes/second_reading/case-05068.answer.json
notes/second_reading/case-05069.answer.json
notes/second_reading/case-05070.answer.json
notes/second_reading/comparison.txt
notes/second_reading/round1/case-05009.answer.json
```

`sealed-v4`, archive A, `tribunal-sealed-v4-A-cases.zip` (33 entries):

```
cases/CANARY.txt
cases/README.md
cases/case-06001.json
cases/case-06002.json
cases/case-06003.json
cases/case-06004.json
cases/case-06005.json
cases/case-06006.json
cases/case-06007.json
cases/case-06008.json
cases/case-06009.json
cases/case-06010.json
cases/case-06011.json
cases/case-06012.json
cases/case-06013.json
cases/case-06014.json
cases/case-06015.json
cases/case-06051.json
cases/case-06052.json
cases/case-06053.json
cases/case-06054.json
cases/case-06055.json
cases/case-06056.json
cases/case-06057.json
cases/case-06058.json
cases/case-06059.json
cases/case-06060.json
cases/case-06061.json
cases/case-06062.json
cases/case-06063.json
cases/case-06064.json
cases/case-06065.json
cases/index.json
```

`sealed-v4`, archive B, `tribunal-sealed-v4-B-answers.zip` (39 entries) -- the
names only, from `unzip -l`; no file of it was opened:

```
answers/MANIFEST.json
answers/check_set_output.txt
answers/ground_truth.json
generator/compare_second_reading.py
generator/generate.py
generator/specs_sealed_v4.py
generator/tribunal_engine.py
notes/NOTES.md
notes/second_reading/case-06001.answer.json
notes/second_reading/case-06002.answer.json
notes/second_reading/case-06003.answer.json
notes/second_reading/case-06004.answer.json
notes/second_reading/case-06005.answer.json
notes/second_reading/case-06006.answer.json
notes/second_reading/case-06007.answer.json
notes/second_reading/case-06008.answer.json
notes/second_reading/case-06009.answer.json
notes/second_reading/case-06010.answer.json
notes/second_reading/case-06011.answer.json
notes/second_reading/case-06012.answer.json
notes/second_reading/case-06013.answer.json
notes/second_reading/case-06014.answer.json
notes/second_reading/case-06015.answer.json
notes/second_reading/case-06051.answer.json
notes/second_reading/case-06052.answer.json
notes/second_reading/case-06053.answer.json
notes/second_reading/case-06054.answer.json
notes/second_reading/case-06055.answer.json
notes/second_reading/case-06056.answer.json
notes/second_reading/case-06057.answer.json
notes/second_reading/case-06058.answer.json
notes/second_reading/case-06059.answer.json
notes/second_reading/case-06060.answer.json
notes/second_reading/case-06061.answer.json
notes/second_reading/case-06062.answer.json
notes/second_reading/case-06063.answer.json
notes/second_reading/case-06064.answer.json
notes/second_reading/case-06065.answer.json
notes/second_reading/comparison.txt
```

## The case numbers and categories

`dev-v7` -- **40 cases**, two twenty-wide ranges:

| category | cases | count |
|---|---|---|
| `ROUTE_DEVIATION` | 5001-5020 | 20 |
| `NO_SHOW_CHARGE` | 5051-5070 | 20 |

`sealed-v4` -- **30 cases**, two fifteen-wide ranges:

| category | cases | count |
|---|---|---|
| `ROUTE_DEVIATION` | 6001-6015 | 15 |
| `NO_SHOW_CHARGE` | 6051-6065 | 15 |

Both counts and both sets of ranges are read from each set's own `index.json`,
and both are also what each set's own manifest states. Neither set's case numbers
appear in `data/index.json`: the manifest still indexes the 29-case corpus.

## How they were made

Both sets were written on 2026-10-13 by **Claude Opus 5.5**, as each set's own
manifest states, in **a fresh claude.ai chat** -- an agentic cloud workspace with
no project folder -- from the seven files in the owner's `v7-authoring` folder
and its prompt. The seven are Ryde's Dispute Resolution Policy v2.1 itself, the
three version-7 policy files, `PUBLIC-CONTRACT.md`, the format checker
`check_set_v7.py` and the organisers' public sample case 901. Each manifest
records the same independence: the author saw those files and the prompt, and did
not see the system's code, its prompts, its runs, its results or any other test
set.

**The author is the same model the team used as its development assistant**:
Claude Opus 5.5. The system under test runs on DeepSeek, so the author and the
system are different models, and a set written by one is a set the other has
never been tuned against -- which is what makes a sealed set's figure a figure at
all.

Each case was read a **second time** by a fresh sub-agent that saw only that case
and the policy files, and each set's manifest records the outcome:

* **`dev-v7`**: 40 readers, **39 of 40 agreed at once**, one case file was
  clarified and re-read, and **0 answers changed**;
* **`sealed-v4`**: 30 readers, **30 of 30 agreed at once**, and **0 answers
  changed**.

Neither set was reviewed by a human, and neither manifest claims one was: the
reference answers are the author's, checked by the author's own second reading.
The format checker's own output, imported with each set, reads `40 case(s), 0
failure(s)` for `dev-v7` and `30 case(s), 0 failure(s)` for `sealed-v4`.

## The policy files moved after the sets were made

Both sets were written against the version-7 policy files as they stood on
2026-10-13, and later that evening the version-7 policy gained two **structured
additions** -- C18's `thresholds.traffic_justification_types`, which maps the
recorded traffic-advisory types onto POL-RD-23's three kinds, and C16's amended
`arrival_test.accuracy_filter_applies`, which says the accuracy filter reaches
only a fix that reports an accuracy. **No clause text changed**, and
`general.json` did not move at all.

The files therefore differ from the ones the author received, and each manifest's
own `reference_file_sha256` records exactly that: it states
`ddb3dcf3c6c3d8cb296900a323df5fa18c4aad660e19e1b7787db5db0787c8ca` for
`route_deviation.json` and
`d638a3b68a6b7bc7655dd984dccafa2f541b448c29c2af18355eb10eefc80d3b` for
`no_show.json`, and both files hash to something else now. The change is
recorded rather than reconciled: the two additions are what the version-7 brief
reads POL-RD-23's kinds and the arrival test's rule from, and the sets are
briefed against the current files, which is the pair the run is made with.

## The configuration each run is made with

Both registrations fix the same `RunArguments`, which are sealed-v2's with the
version-7 prompt set: model `deepseek/deepseek-flash`, four judge votes, the
draft verifier off, a 900-second timeout, concurrency 2, and `prompts/v2` -- the
only prompts directory a version-7 run may use. The case deadline and the token
budget are recorded as "the default" rather than as today's number, and
`eval.run_benchmark` refuses an invocation that differs in any of them.

## The registrations

`dev-v7` is a **development** set: `sealed=False`, `policy_version=7`,
`policy_base=7`, registered by name and in `NAMED_SETS` alone. It is never part
of `--set all`, the combined figure or the recorded-drafts measurement, and no
figure from it is a generalisation figure. Its runs go to
`runs/dev-v7/<model-slug>/`.

`sealed-v4` is the **sixth sealed set**: `sealed=True`, `policy_version=7`,
registered after `sealed-v3` in `SEALED_SETS`. Its runs go to
`runs/sealed-v4/<model-slug>/`, and its root is the one sealed root still open:
`run_benchmark.SEALED_V4_SET_RUNS_SUBDIR` is a seventh name in `SET_RUNS_SUBDIRS`
and the one name in `UNRUN_SEALED_RUNS_SUBDIRS`, so the permit opens its own
plain run directory and every other destination under it is refused. The other
five sealed roots stay closed outright. Its single run is never part of
`--set all`, the combined figure or the recorded-drafts measurement.

## The commands

`dev-v7`, which may be run again:

    python3 -m eval.development_sets --set dev-v7 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2

`sealed-v4`, once, and only by the owner:

    TRIBUNAL_SEALED_RUN=sealed-v4 python3 -m eval.development_sets --set sealed-v4 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2

`TRIBUNAL_SEALED_RUN=sealed-v4` is the opt-in, and it is what makes that run the
owner's: without it the invocation is refused before any client is built, and
nothing in this repository sets that variable. `--force` cannot be added to it --
it is refused for a sealed set in code -- and `--policy-version` cannot either,
because the registration fixes version 7. `--parallel-calls` changes no request
body and moves no run directory, so it is not part of the frozen configuration;
it is what the two sealed runs since 2026-10-03 were made with. To see what a
plain invocation would run without running it, put `--check` in place of the run:

    python3 -m eval.development_sets --set sealed-v4 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2 --check

## The gate this import had to keep

The freeze's own check is
`git diff --stat freeze-2026-10-11 HEAD -- tribunal prompts policy`. **This import
changes nothing under `tribunal/`, `prompts/` or `policy/`**: its code changes are
in `eval/` and its tests are in `tests/`, and
`git status --porcelain -- tribunal prompts policy` is empty at this commit.

The one exception is the pair of policy files part 73b re-copied byte for byte,
which is recorded in `docs/notes/2026-10-13-policy-v7.md` under *Amendments
(2026-10-13 evening)*: `policy/v7/route_deviation.json` and
`policy/v7/no_show.json` gained the two structured fields, no clause text
changed, and `general.json` did not move.

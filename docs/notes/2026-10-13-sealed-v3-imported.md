# The fifth sealed set imported and registered

**2026-10-13.** This is the fifth-freeze import task, recorded from the files it
produced. The tag `freeze-2026-10-11` already exists and is **not** created or
moved here: the set's single run is made from a commit whose `tribunal/`,
`prompts/` and `policy/` trees equal those at that tag, and the owner makes that
run after this commit.

**No model call was made by this import, and the set was not run.** The set is run
afterwards, once, by the owner, outside this sandbox.

**Structure, counts and digests only — and only from archive A.** Archive B, the
key and the files that travel with it, was extracted straight into place with
`unzip` and was never opened: nothing in this repository printed, read,
summarised or quoted a file of it, and only its file names and the counts and
digests its own `MANIFEST.json` states are recorded below. No case content and no
answer value is printed anywhere here either.

## The archives, verified before anything was imported

| what was recorded on receipt | |
|---|---|
| directory | `tmp/sealed-v3-incoming/` |
| archive A | `tribunal-sealed-v3-A-cases.zip`, 183,277 bytes, 33 entries |
| archive B | `tribunal-sealed-v3-B-answers.zip`, 949,663 bytes, 174 entries |
| digests file | `SHA256SUMS` |

`shasum -a 256 -c SHA256SUMS` was run in that directory before anything was
copied out, and both archives verified:

    tribunal-sealed-v3-A-cases.zip: OK
    tribunal-sealed-v3-B-answers.zip: OK

| archive | sha256 |
|---|---|
| `tribunal-sealed-v3-A-cases.zip` | `af21c7568192af27ef98a95f70e99790193b3f643f89475874770b1dfe9d2f3a` |
| `tribunal-sealed-v3-B-answers.zip` | `cf7e68b72a363eb0930994f0cdd371568d2308b4a7320ab3b07cf9b60214ced4` |

The rule was to stop if either did not verify; both did, so the import proceeded.
Archive A was unpacked into a scratch directory outside the repository, which is
where the structure check below was made. Archive B was extracted straight into
its destination and was not opened.

## Where the files went

Mirroring `sealed-v2`'s import: the cases flat under `data/external/`, the key and
everything that travelled with it under `eval/answers/`, and the archive's own
note and canary under `eval/external/`.

| archive path | repository path | files |
|---|---|---|
| `cases/case-04001.json` … `cases/case-04015.json`, `cases/case-04051.json` … `cases/case-04065.json` (A) | `data/external/sealed-v3/` (flat) | 30 |
| `cases/index.json` (A) | `data/external/sealed-v3/index.json` | 1 |
| `answers/ground_truth.json` (B) | `eval/answers/sealed-v3/ground_truth.json` | 1 |
| every other file of `answers/` (B), its two subfolders included | `eval/answers/sealed-v3/` | 173 |
| `cases/README.md`, `cases/CANARY.txt` (A) | `eval/external/sealed-v3/` | 2 |

**207 files imported, and nothing kept outside the repository.** Archive A ships
nothing in Chinese: its `README.md` and `CANARY.txt` are English and answer-free,
so both are imported; and every file of archive B is answer-bearing and is placed
under the physically isolated answers root, so every answer-bearing file of this
set sits in one directory — the key, its `MANIFEST.json`, and both subfolders,
`authoring/` (the author's generator, plans, critiques and audits) and
`second_reading/` (two blind readings per case, the comparisons, and `round0/`, a
copy of the first version of the cases and the key). `data/external/sealed-v3/`
holds 31 of the 207 (the 30 cases and the index), `eval/answers/sealed-v3/` holds
174, and `eval/external/sealed-v3/` holds two.

The three destinations sit on two sides of the boundary `WORKBUDDY-SCOPE.md`
draws. `data/external/sealed-v3/` is agent-visible and answer-free, under the
contract `data/cases/` and the other external sets are under.
`eval/answers/sealed-v3/` and `eval/external/sealed-v3/` are answer-bearing:
nothing under `tribunal/` may read either.

**Nothing was re-serialised.** Every imported file is byte-identical to its
archive entry, and every digest below is the archive's own. The key in particular
was extracted as the archive holds it and was not touched: whether it needed
re-wrapping is a question this import cannot answer, because answering it means
opening the file, and the answers rule forbids that. What is recorded is the
digest its own `MANIFEST.json` states — `c58d5610574a5341dffa2f64108dd4f1eb0712db585853f01ba976de344a4117`
— and the tests assert on that digest and on the file's shape.

## The file lists, names only

Archive A, `tribunal-sealed-v3-A-cases.zip` (33 entries):

```
cases/CANARY.txt
cases/README.md
cases/case-04001.json
cases/case-04002.json
cases/case-04003.json
cases/case-04004.json
cases/case-04005.json
cases/case-04006.json
cases/case-04007.json
cases/case-04008.json
cases/case-04009.json
cases/case-04010.json
cases/case-04011.json
cases/case-04012.json
cases/case-04013.json
cases/case-04014.json
cases/case-04015.json
cases/case-04051.json
cases/case-04052.json
cases/case-04053.json
cases/case-04054.json
cases/case-04055.json
cases/case-04056.json
cases/case-04057.json
cases/case-04058.json
cases/case-04059.json
cases/case-04060.json
cases/case-04061.json
cases/case-04062.json
cases/case-04063.json
cases/case-04064.json
cases/case-04065.json
cases/index.json
```

Archive B, `tribunal-sealed-v3-B-answers.zip` (174 entries):

```
answers/MANIFEST.json
answers/check_set_output.txt
answers/ground_truth.json
answers/independence_audit.txt
answers/authoring/BRIEF.md
answers/authoring/FOUNDATION.md
answers/authoring/audit_access.py
answers/authoring/audit_ns.py
answers/authoring/audit_ns_selftest.txt
answers/authoring/audit_rd.py
answers/authoring/audit_rd_selftest.txt
answers/authoring/blueprint_ns.json
answers/authoring/blueprint_rd.json
answers/authoring/cases_ns.py
answers/authoring/cases_ns_notes.md
answers/authoring/cases_rd.py
answers/authoring/cases_rd_keys.py
answers/authoring/common.py
answers/authoring/critique_ns_r1.json
answers/authoring/critique_ns_r2.json
answers/authoring/critique_rd_r1.json
answers/authoring/critique_rd_r2.json
answers/authoring/design_notes_ns.md
answers/authoring/design_notes_rd.md
answers/authoring/finalize.py
answers/authoring/generate.py
answers/authoring/ns_geo.py
answers/authoring/ns_texts.py
answers/authoring/plan.json
answers/authoring/plan_notes.md
answers/authoring/revisions_ns_r1.md
answers/authoring/revisions_ns_r2.md
answers/authoring/revisions_rd_r1.md
answers/authoring/revisions_rd_r2.md
answers/authoring/test_common.py
answers/second_reading/SUMMARY.json
answers/second_reading/r1/compare-4001.json
answers/second_reading/r1/compare-4002.json
answers/second_reading/r1/compare-4003.json
answers/second_reading/r1/compare-4004.json
answers/second_reading/r1/compare-4005.json
answers/second_reading/r1/compare-4006.json
answers/second_reading/r1/compare-4007.json
answers/second_reading/r1/compare-4008.json
answers/second_reading/r1/compare-4009.json
answers/second_reading/r1/compare-4010.json
answers/second_reading/r1/compare-4011.json
answers/second_reading/r1/compare-4012.json
answers/second_reading/r1/compare-4013.json
answers/second_reading/r1/compare-4014.json
answers/second_reading/r1/compare-4015.json
answers/second_reading/r1/compare-4051.json
answers/second_reading/r1/compare-4052.json
answers/second_reading/r1/compare-4053.json
answers/second_reading/r1/compare-4054.json
answers/second_reading/r1/compare-4055.json
answers/second_reading/r1/compare-4056.json
answers/second_reading/r1/compare-4057.json
answers/second_reading/r1/compare-4058.json
answers/second_reading/r1/compare-4059.json
answers/second_reading/r1/compare-4060.json
answers/second_reading/r1/compare-4061.json
answers/second_reading/r1/compare-4062.json
answers/second_reading/r1/compare-4063.json
answers/second_reading/r1/compare-4064.json
answers/second_reading/r1/compare-4065.json
answers/second_reading/r1/fixlog-ns.json
answers/second_reading/r1/fixlog-rd.json
answers/second_reading/r1/reading-4001-a.json
answers/second_reading/r1/reading-4001-b.json
answers/second_reading/r1/reading-4002-a.json
answers/second_reading/r1/reading-4002-b.json
answers/second_reading/r1/reading-4003-a.json
answers/second_reading/r1/reading-4003-b.json
answers/second_reading/r1/reading-4004-a.json
answers/second_reading/r1/reading-4004-b.json
answers/second_reading/r1/reading-4005-a.json
answers/second_reading/r1/reading-4005-b.json
answers/second_reading/r1/reading-4006-a.json
answers/second_reading/r1/reading-4006-b.json
answers/second_reading/r1/reading-4007-a.json
answers/second_reading/r1/reading-4007-b.json
answers/second_reading/r1/reading-4008-a.json
answers/second_reading/r1/reading-4008-b.json
answers/second_reading/r1/reading-4009-a.json
answers/second_reading/r1/reading-4009-b.json
answers/second_reading/r1/reading-4010-a.json
answers/second_reading/r1/reading-4010-b.json
answers/second_reading/r1/reading-4011-a.json
answers/second_reading/r1/reading-4011-b.json
answers/second_reading/r1/reading-4012-a.json
answers/second_reading/r1/reading-4012-b.json
answers/second_reading/r1/reading-4013-a.json
answers/second_reading/r1/reading-4013-b.json
answers/second_reading/r1/reading-4014-a.json
answers/second_reading/r1/reading-4014-b.json
answers/second_reading/r1/reading-4015-a.json
answers/second_reading/r1/reading-4015-b.json
answers/second_reading/r1/reading-4051-a.json
answers/second_reading/r1/reading-4051-b.json
answers/second_reading/r1/reading-4052-a.json
answers/second_reading/r1/reading-4052-b.json
answers/second_reading/r1/reading-4053-a.json
answers/second_reading/r1/reading-4053-b.json
answers/second_reading/r1/reading-4054-a.json
answers/second_reading/r1/reading-4054-b.json
answers/second_reading/r1/reading-4055-a.json
answers/second_reading/r1/reading-4055-b.json
answers/second_reading/r1/reading-4056-a.json
answers/second_reading/r1/reading-4056-b.json
answers/second_reading/r1/reading-4057-a.json
answers/second_reading/r1/reading-4057-b.json
answers/second_reading/r1/reading-4058-a.json
answers/second_reading/r1/reading-4058-b.json
answers/second_reading/r1/reading-4059-a.json
answers/second_reading/r1/reading-4059-b.json
answers/second_reading/r1/reading-4060-a.json
answers/second_reading/r1/reading-4060-b.json
answers/second_reading/r1/reading-4061-a.json
answers/second_reading/r1/reading-4061-b.json
answers/second_reading/r1/reading-4062-a.json
answers/second_reading/r1/reading-4062-b.json
answers/second_reading/r1/reading-4063-a.json
answers/second_reading/r1/reading-4063-b.json
answers/second_reading/r1/reading-4064-a.json
answers/second_reading/r1/reading-4064-b.json
answers/second_reading/r1/reading-4065-a.json
answers/second_reading/r1/reading-4065-b.json
answers/second_reading/r2/compare-4001.json
answers/second_reading/r2/compare-4009.json
answers/second_reading/r2/compare-4052.json
answers/second_reading/r2/compare-4059.json
answers/second_reading/r2/reading-4001-a.json
answers/second_reading/r2/reading-4001-b.json
answers/second_reading/r2/reading-4009-a.json
answers/second_reading/r2/reading-4009-b.json
answers/second_reading/r2/reading-4052-a.json
answers/second_reading/r2/reading-4052-b.json
answers/second_reading/r2/reading-4059-a.json
answers/second_reading/r2/reading-4059-b.json
answers/second_reading/round0/ground_truth.json
answers/second_reading/round0/cases/CANARY.txt
answers/second_reading/round0/cases/README.md
answers/second_reading/round0/cases/case-04001.json
answers/second_reading/round0/cases/case-04002.json
answers/second_reading/round0/cases/case-04003.json
answers/second_reading/round0/cases/case-04004.json
answers/second_reading/round0/cases/case-04005.json
answers/second_reading/round0/cases/case-04006.json
answers/second_reading/round0/cases/case-04007.json
answers/second_reading/round0/cases/case-04008.json
answers/second_reading/round0/cases/case-04009.json
answers/second_reading/round0/cases/case-04010.json
answers/second_reading/round0/cases/case-04011.json
answers/second_reading/round0/cases/case-04012.json
answers/second_reading/round0/cases/case-04013.json
answers/second_reading/round0/cases/case-04014.json
answers/second_reading/round0/cases/case-04015.json
answers/second_reading/round0/cases/case-04051.json
answers/second_reading/round0/cases/case-04052.json
answers/second_reading/round0/cases/case-04053.json
answers/second_reading/round0/cases/case-04054.json
answers/second_reading/round0/cases/case-04055.json
answers/second_reading/round0/cases/case-04056.json
answers/second_reading/round0/cases/case-04057.json
answers/second_reading/round0/cases/case-04058.json
answers/second_reading/round0/cases/case-04059.json
answers/second_reading/round0/cases/case-04060.json
answers/second_reading/round0/cases/case-04061.json
answers/second_reading/round0/cases/case-04062.json
answers/second_reading/round0/cases/case-04063.json
answers/second_reading/round0/cases/case-04064.json
answers/second_reading/round0/cases/case-04065.json
answers/second_reading/round0/cases/index.json
```

## What the structure-only check found

Reading **archive A only** — its 30 cases and its index — and reading no case
content out into this repository.

- There are **30** case files, numbered **4001 to 4015** and **4051 to 4065** —
  two fifteen-wide ranges, so the count and the ranges are the same numbers.
  **15 are `ROUTE_DEVIATION`** (4001-4015) and **15 `NO_SHOW_CHARGE`**
  (4051-4065), which is the set's own index's count too and the archive's own
  `MANIFEST.json`'s `categories` as well.
- The set's own `index.json` states a `sha256` for each of the 30 case files, and
  the archive's own `MANIFEST.json` states the same 30 digests.
- Every case's brief builds at policy version 6.

## The case numbers and categories

| case numbers | category | cases |
|---|---|---|
| 4001-4015 | `ROUTE_DEVIATION` | 15 |
| 4051-4065 | `NO_SHOW_CHARGE` | 15 |

## How it was made

The registration's summary states it in this repository's words:

> the fifth sealed set (sealed-v3): 30 cases made by Claude (Opus 5.5) in a fresh
> Claude Code session with no project folder or repository access, from the
> owner's prompt, the version-6 policy text, the public contract, a format checker
> and the organisers' public sample case; no human reviewed its answers; nobody on
> the development side has seen them; it is run once, from a commit whose
> tribunal/, prompts/ and policy/ trees equal those at freeze-2026-10-11, at
> policy version 6

The three paragraphs below are the record this repository carries. They are
written here as they were written for this part.

> **How it was made.** On 2026-10-13 the owner opened a fresh Claude Code
> desktop session with no project folder (a scratch workspace) and gave it nine
> files -- `PUBLIC-CONTRACT.md`, the three version-6 base policy files and their
> three amendments, the format checker `check_set.py`, and the organisers'
> public sample case 901 -- and a written prompt. The author is Claude Opus 5.5,
> as its manifest states: the same model the team used as its development
> assistant; the system under test runs on DeepSeek. The session loaded the
> owner's global Claude Code instructions, which name the hackathon project and
> the folder of its code but hold none of its code, prompts, runs or results.
> The prompt asked for a claude.ai chat; the owner ran it in a Claude Code
> session instead, and the manifest records that.
>
> **What the author saw.** Per its manifest: the nine files and the prompt,
> and not the system's code, prompts, runs, results, other test sets or any
> discussion of them. Its own audit of its 120 subagents' tool calls found no
> access to the Desktop, to any repository or to another test set. The owner's
> side audited the session's transcripts independently on 2026-10-13, reading
> only the paths and commands in the tool calls, never their output: no call,
> by the session or by a subagent, touched `~/Desktop/Tribunal`, another sealed
> set, `runs/` or `eval/answers/`. The session copied the nine files from the
> owner's authoring folder and once listed the folder names in the system
> temporary folder `/private/tmp/claude-501/`. Many subagents kept scratch
> files in the system temporary folder (`/tmp/...`), which the author's audit
> text calls "the workspace's tmp/" and leaves out of its listing: it reports
> 84 agents with findings and lists 19.
>
> **Review.** No human reviewed the answers. The author's second reading (two
> blind readers per case, then a comparison with the key) changed 3 answers and
> 1 case file, and `check_set.py` reports 30 cases, 0 failures. Nobody on the
> development side has seen the answers; the development side read only the
> manifest's aggregate counts (rulings and difficulty by number of cases, not
> by case), its provenance fields and its digests.

## The configuration the run is made with

| setting | value |
|---|---|
| model | `deepseek/deepseek-flash` (the runtime model, read from `tribunal/model.py` and never repeated) |
| policy version | 6, fixed by the registration |
| judge votes | 4 |
| verifier | off |
| timeout | 900 seconds |
| concurrency | 2 |
| prompts directory | the default |
| case deadline | the default |
| token budget | the default |

`--parallel-calls` is not carried by `RunArguments` and is therefore not pinned by
the registration; the run is made with it, as the four earlier sealed runs were,
and it changes nothing a run measures.

## The registration

The set is registered in `eval/development_sets.py` as `SEALED_V3`, apart from
`DEVELOPMENT_SETS`:

- It carries `sealed=True` and `policy_version=6`, and it is the fifth name in
  `SEALED_SETS`. `--set all` reads `DEVELOPMENT_SETS` and so never runs it, and
  `--report` prints it in a section of its own, never inside the combined figure.
  Its runs go to `runs/sealed-v3/<model-slug>/`, and it is graded against
  `eval/answers/sealed-v3/ground_truth.json` through its own loader.
- Its `run_arguments` fix the table above. `--policy-version` is refused for it in
  code while the command line is read.
- `run_benchmark.SEALED_V3_SET_RUNS_SUBDIR` is a sixth name in `SET_RUNS_SUBDIRS`,
  so `runs/sealed-v3/<model-slug>/` is a headline directory and all six switched
  destinations refuse it. It is the one name in `UNRUN_SEALED_RUNS_SUBDIRS`: its
  single run has not been made, so its root is the one sealed root whose plain run
  the permit still opens, and every other destination under it is refused.
- `eval.sealed_roots.refuse_a_sealed_destination` refuses every destination under
  `runs/sealed-v3/`, and that is what the six named-path commands and the four
  routed guards call.
- `assert_not_sealed` refuses `--force`, `--replay-advocates`, `--replay-check`,
  `--verify-recorded-drafts`, `--early-majority`, `--integrity-gate` and
  `--advocate-effort` for this set.
- `eval.sealed_report --set sealed-v3` works: it reports the set as not run, one
  line, reading no key.
- `tests/test_sealed_set_sealed_v3.py` is new: the registration, the key and the
  case files held to the manifest's digests, the open root and its permit, the
  opt-in gate, the `--force` and frozen-argument refusals, every write path, and
  the structure checks. Counts and keys only, never a value.
- `tests/test_answer_isolation.py` gains a `SealedV3IsolationTest` beside the
  others: no answer field in any of the 30 case files, no brief carrying an
  answer-key field name, no module under `tribunal/` naming either of the two
  paths that hold the set's answers, and a falsifiability check that goes red on a
  spliced case.
- `tests/test_language.py` gains one exemption, by full path, for
  `eval/answers/sealed-v3/authoring/finalize.py`: it is delivered material whose
  four Chinese characters are part of the owner's folder name in a file path the
  author's script names. It is not this repository's writing and is not edited.

The counts this import moves are updated where they are pinned: the sealed-set
name tuples in `tests/test_sealed_set.py`, `tests/test_sealed_set_wild_v2.py`,
`tests/test_sealed_set_sealed_v1.py` and `tests/test_sealed_set_sealed_v2.py`
gain `"sealed-v3"`, the headline-directory counts there go from six to seven, the
un-run list in `tests/test_sealed_set_sealed_v1.py` and
`tests/test_sealed_set_sealed_v2.py` moves to `("sealed-v3",)`,
`tests/test_sealed_roots_closed.py` gains a `sealed-v3` entry in its `ARGUMENTS`
table, `tests/test_sealed_report.py` expects the refusal to name
`sealed-v1, sealed-v2, sealed-v3, wild, wild-v2`, `tests/test_ops_evidence.py`
names thirteen sets and 395 converted cases, and `tests/test_precedents.py`'s
`NOT_YET_IN_PRECEDENTS` gains `"sealed-v3"`.

## The command the owner will run

    TRIBUNAL_SEALED_RUN=sealed-v3 python3 -m eval.development_sets --set sealed-v3 --parallel-calls --concurrency 2 --timeout 900

The flags are the freeze's: `--set sealed-v3` is accepted, `--concurrency` and
`--timeout` are both arguments of it, and the policy version needs no flag because
the registration fixes it at 6. `--force` cannot be added to it: it is refused for
this set in code. The run is made only if
`git diff --stat freeze-2026-10-11 HEAD -- tribunal prompts policy` prints
nothing.

`TRIBUNAL_SEALED_RUN=sealed-v3` is the opt-in, and it is what makes this run the
owner's: without it the invocation is refused before any client is built, and
nothing in this repository sets that variable. To see what a plain invocation
would run without running it, put `--check` in place of the run:

    python3 -m eval.development_sets --set sealed-v3 --concurrency 2 --timeout 900 --check

## The gate this import had to keep

The freeze's own check is
`git diff --stat freeze-2026-10-11 HEAD -- tribunal prompts policy`, which must
print nothing. **This import changes nothing under `tribunal/`, `prompts/` or
`policy/`**: its code changes are in `eval/` and its tests are in `tests/`, and
`git status --porcelain -- tribunal prompts policy` is empty at this commit.
`sealed-v3`'s absence from `tribunal.precedents.EXTERNAL_SET_DIRS` is recorded in
`tests/test_precedents.py`'s `NOT_YET_IN_PRECEDENTS` instead, so the frozen tree
stays byte-identical to the tag.

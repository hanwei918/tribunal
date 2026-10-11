# The fourth sealed set imported and registered

**2026-10-11.** This is the fourth-freeze import task, recorded from the files it
produced. The tag `freeze-2026-10-11` is **not** created here: the owner creates
it after checking the three trees, and the set's single run is made from a commit
whose `tribunal/`, `prompts/` and `policy/` trees equal those at that tag.

**No model call was made by this import, and the set was not run.** The set is run
afterwards, once, by the owner, outside this sandbox.

**Structure, counts and digests only — and only from archive A.** Archive B, the
key and the files that travel with it, was extracted straight into place with
`unzip` and was never opened: nothing in this repository printed, read,
summarised or quoted a file of it, and only its file names and its digests are
recorded below. No case content and no answer value is printed anywhere here
either.

## The archives, verified before anything was imported

| what was recorded on receipt | |
|---|---|
| directory | `tmp/sealed-v2-incoming/` |
| archive A | `tribunal-sealed-v2-A-cases.zip`, 40,726 bytes, 15 entries |
| archive B | `tribunal-sealed-v2-B-answers.zip`, 30,145 bytes, 7 entries |
| digests file | `SHA256SUMS` |

`shasum -a 256 -c SHA256SUMS` was run in that directory before anything was
copied out, and both archives verified:

    tribunal-sealed-v2-A-cases.zip: OK
    tribunal-sealed-v2-B-answers.zip: OK

| archive | sha256 |
|---|---|
| `tribunal-sealed-v2-A-cases.zip` | `ad89652fbba601c02aa6d16272d44a3dfaf2fb6ec430d8b9b720dac81ce88bbd` |
| `tribunal-sealed-v2-B-answers.zip` | `988e21e0e6f9f1f080cedfd3c2893d02f21dece180f0bf1f6b7ca73d0e1a2c00` |

The rule was to stop if either did not verify; both did, so the import proceeded.
Archive A was unpacked into a scratch directory outside the repository, which is
where the structure check below was made. Archive B was extracted straight into
its destination and was not opened.

## Where the files went

Mirroring `sealed-v1`'s import: the cases flat under `data/external/`, the key and
everything that travelled with it under `eval/answers/`, and the archive's own
note and canary under `eval/external/`.

| archive path | repository path | files |
|---|---|---|
| `case-00801.json` … `case-00806.json`, `case-00851.json` … `case-00856.json` (A) | `data/external/sealed-v2/` (flat) | 12 |
| `index.json` (A) | `data/external/sealed-v2/index.json` | 1 |
| `ground_truth.json` (B) | `eval/answers/sealed-v2/ground_truth.json` | 1 |
| `MANIFEST.json`, `REVIEW_GUIDE.md`, `review_checklist.json`, `additional_audit_output.txt`, `check_set.py`, `check_set_output.txt` (B) | `eval/answers/sealed-v2/` | 6 |
| `README.md`, `CANARY.txt` (A) | `eval/external/sealed-v2/` | 2 |

**22 files imported, and nothing kept outside the repository.** This archive
ships nothing in Chinese: archive A's `README.md` and `CANARY.txt` are English and
answer-free, so both are imported; and every file of archive B is answer-bearing
and is placed under the physically isolated answers root, so every
answer-bearing file of this set sits in one directory. `data/external/sealed-v2/`
holds 13 of the 22 (the 12 cases and the index), `eval/answers/sealed-v2/` holds
seven, and `eval/external/sealed-v2/` holds two.

The three destinations sit on two sides of the boundary `WORKBUDDY-SCOPE.md`
draws. `data/external/sealed-v2/` is agent-visible and answer-free, under the
contract `data/cases/` and the other external sets are under.
`eval/answers/sealed-v2/` and `eval/external/sealed-v2/` are answer-bearing:
nothing under `tribunal/` may read either.

**Nothing was re-serialised.** Every imported file is byte-identical to its
archive entry, and its digest below is the archive's own. The key in particular
was extracted as the archive holds it and was not touched: whether it needed
re-wrapping is a question this import cannot answer, because answering it means
opening the file, and the answers rule forbids that. What is recorded is its
digest, and the tests assert on its shape.

## The digest of every imported file

| repository path | sha256 |
|---|---|
| `data/external/sealed-v2/case-00801.json` | `92b15dbf2f67d08b48e07740e44f19836b12692a0340ebcae4660c72c4fe83c7` |
| `data/external/sealed-v2/case-00802.json` | `acc474352c4fc45844d745c4efcb91053e52aff828e09018ee30e36e5bd04038` |
| `data/external/sealed-v2/case-00803.json` | `66e5d51b11102f672e92a65576a9e5f5e62a8cb6f140fcdef89f80223ad44aa0` |
| `data/external/sealed-v2/case-00804.json` | `f7d9f1c97bff814a3d3db7de96d4f2966279d1bd664b3c1b04a8eba771f9ad1f` |
| `data/external/sealed-v2/case-00805.json` | `9f104d7efad66bafac56d1250e4d84699c4ce8a4439ea65583a5d6878803355f` |
| `data/external/sealed-v2/case-00806.json` | `0c7f685a92a65bc5268909ed39e90b71033421b635f876342831de88f3c814a5` |
| `data/external/sealed-v2/case-00851.json` | `c7bea25126e5e8bd21b8aaf9486b82480209717dfa043dbbd48337916205f7a3` |
| `data/external/sealed-v2/case-00852.json` | `5496839a5a2daf222239b86acca9a471ac37450479d7ec4dc7336f401dba44a7` |
| `data/external/sealed-v2/case-00853.json` | `37cfbcada425bec584ae563ad4d55607f8019cb4ec4792d30fecfe6fabbfcb0a` |
| `data/external/sealed-v2/case-00854.json` | `644203c02f2b25a45a206fd5b4710e69edf2f7714e818cbece0d23f31cf2fb99` |
| `data/external/sealed-v2/case-00855.json` | `b89410fc4da5ed3b81bde3c7b01e23685d829109a856bad0f7a06b31ca9541cf` |
| `data/external/sealed-v2/case-00856.json` | `3d90ebb95bdcec7cbc1a8493885fbab249b4c99bf3158b0c8808301fdcc03b02` |
| `data/external/sealed-v2/index.json` | `b1c218091eebb654d606cf36f4718967881cc068b86aa29ba98f65f2bc9d591e` |
| `eval/answers/sealed-v2/ground_truth.json` | `d3a09c08f06c8eb328e251e618cba7b035fdb54c7614b041781fd6d564fe3e6f` |
| `eval/answers/sealed-v2/MANIFEST.json` | `0fa3dfb62f0d8fc0200ed1223127d896eac97b1c5b48b10ad9c99372ed1764ea` |
| `eval/answers/sealed-v2/REVIEW_GUIDE.md` | `f8a87710086dda04020e74a4c6d31b14f0a754e8ba76441ed5df9f7342195c82` |
| `eval/answers/sealed-v2/review_checklist.json` | `dd1b277b5d82d3e5caa57bbb832e5dcb0d00440898c3c2ef895256cb8a311ab0` |
| `eval/answers/sealed-v2/additional_audit_output.txt` | `bc3eed2bf7d6bf2a796b8fd4a2b0b2f5099f7d7b1c25e10e8c11e8b2b22baa97` |
| `eval/answers/sealed-v2/check_set.py` | `c61ed3571e318c2edf7702e16c3ada2fff352822396e8b30af3b02bcf7776463` |
| `eval/answers/sealed-v2/check_set_output.txt` | `77177ad44f2a727f9f3d4b41ffecbeca9117f8a2880796171d5bf319ae603871` |
| `eval/external/sealed-v2/README.md` | `a4306e183563b3bfe309216bd726cc5fea942aa9014f75a859136e6678ccadfe` |
| `eval/external/sealed-v2/CANARY.txt` | `4d6805ec7f0bcdbef11ed03b19ea8ae170dc78247a43ebd3689458220d409c2b` |

## What the structure-only check found

Reading **archive A only** — its 12 cases and its index — and reading no case
content out into this repository.

- There are **12** case files, numbered **801 to 806** and **851 to 856** — two
  six-wide ranges, so the count and the ranges are the same numbers. **6 are
  `ROUTE_DEVIATION`** (801-806) and **6 `NO_SHOW_CHARGE`** (851-856), which is the
  set's own index's count too.
- Every case loads through `loader.load_external_case` (by path) and through
  `loader.load_external_set_case` (by number, through the set's own index). The
  loader refuses a forbidden key on the way in, so a case that carries one could
  not have loaded.
- The set's own `index.json` states a `sha256` for each of the 12 case files, and
  **all 12 reproduce** against the files as committed.
- **No case number, dispute id or trip id collides** with any other registered set
  or with the corpus manifest. Checked over the twelve registered sets and
  `data/index.json`.
- **The six no-show cases carry `trip_record.platform_policy` of their own**, so a
  version-6 brief takes the platform-policy block from the case rather than
  deriving the `AUTHORED-V1` block; the six route-deviation cases carry none. This
  is the one structural way this set differs from `sealed-v1`, whose cases carried
  none. It is a count, not a reading of the cases.
- Every case's brief builds at policy version 6.
- **No case content and no answer value is printed, quoted or summarised anywhere
  in this repository.**

## How it was made

The registration's summary states it in this repository's words:

> the fourth sealed set (sealed-v2): 12 cases made with GPT-6 by the policy owner
> from a written brief, the version-6 policy text and the public contract, with no
> repository code, prompts or run results; nobody on the development side has seen
> its answers; it is run once, from a commit whose tribunal/, prompts/ and policy/
> trees equal those at freeze-2026-10-11, at policy version 6

Archive A's own `README.md` — imported at `eval/external/sealed-v2/README.md`, and
readable — states the set's counts, its schema and its own provenance there; it is
not quoted here. Archive B was not opened, so what its own `MANIFEST.json` records
about the author, the tool and the date is not read here either; the sentence
above is the record this repository carries.

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
the registration; the run is made with it, as the three earlier sealed runs were,
and it changes nothing a run measures.

## The registration

The set is registered in `eval/development_sets.py` as `SEALED_V2`, apart from
`DEVELOPMENT_SETS`:

- It carries `sealed=True` and `policy_version=6`, and it is the fourth name in
  `SEALED_SETS`. `--set all` reads `DEVELOPMENT_SETS` and so never runs it, and
  `--report` prints it in a section of its own, never inside the combined figure.
  Its runs go to `runs/sealed-v2/<model-slug>/`, and it is graded against
  `eval/answers/sealed-v2/ground_truth.json` through its own loader.
- Its `run_arguments` fix the table above. `--policy-version` is refused for it in
  code while the command line is read.
- `run_benchmark.SEALED_V2_SET_RUNS_SUBDIR` is a fifth name in `SET_RUNS_SUBDIRS`,
  so `runs/sealed-v2/<model-slug>/` is a headline directory and all six switched
  destinations refuse it. It is the one name in `UNRUN_SEALED_RUNS_SUBDIRS`: its
  single run has not been made, so its root is the one sealed root whose plain run
  the permit still opens, and every other destination under it is refused.
- `eval.sealed_roots.refuse_a_sealed_destination` refuses every destination under
  `runs/sealed-v2/`, and that is what the six named-path commands and the four
  routed guards call.
- `assert_not_sealed` refuses `--force`, `--replay-advocates`, `--replay-check`,
  `--verify-recorded-drafts`, `--early-majority`, `--integrity-gate` and
  `--advocate-effort` for this set.
- `eval.sealed_report --set sealed-v2` works: it reports the set as not run, one
  line, reading no key.
- `tests/test_sealed_set_sealed_v2.py` is new: the registration, the bundle digest
  table, the open root and its permit, the opt-in gate, the `--force` and
  frozen-argument refusals, every write path, and the structure checks. Counts and
  keys only, never a value.
- `tests/test_answer_isolation.py` gains a `SealedV2IsolationTest` beside the
  others: no answer field in any of the 12 case files, no brief carrying an
  answer-key field name, no module under `tribunal/` naming either of the two
  paths that hold the set's answers, and a falsifiability check that goes red on a
  spliced case.

Five existing tests are updated, and each is a count or a list that this import's
own registration moves: the sealed-set name tuples in `tests/test_sealed_set.py`,
`tests/test_sealed_set_wild_v2.py` and `tests/test_sealed_set_sealed_v1.py` gain
`"sealed-v2"`, the headline-directory counts there and in
`tests/test_sealed_set_sealed_v1.py` go from five to six,
`tests/test_sealed_set_sealed_v1.py`'s un-run list moves from empty to
`("sealed-v2",)`, `tests/test_sealed_roots_closed.py` gains a `sealed-v2` entry in
its `ARGUMENTS` table, `tests/test_sealed_report.py` expects the refusal to name
`sealed-v1, sealed-v2, wild, wild-v2`, `tests/test_ops_evidence.py` names twelve
sets and 365 converted cases, and `tests/test_precedents.py`'s
`NOT_YET_IN_PRECEDENTS` gains `"sealed-v2"`.

## The command the owner will run

    TRIBUNAL_SEALED_RUN=sealed-v2 python3 -m eval.development_sets --set sealed-v2 --parallel-calls --concurrency 2 --timeout 900

The flags are the freeze's: `--set sealed-v2` is accepted, `--concurrency` and
`--timeout` are both arguments of it, and the policy version needs no flag because
the registration fixes it at 6. `--force` cannot be added to it: it is refused for
this set in code. The run is made only if
`git diff --stat freeze-2026-10-11 HEAD -- tribunal prompts policy` prints
nothing, and the tag is the owner's to create.

`TRIBUNAL_SEALED_RUN=sealed-v2` is the opt-in, and it is what makes this run the
owner's: without it the invocation is refused before any client is built, and
nothing in this repository sets that variable. To see what a plain invocation
would run without running it, put `--check` in place of the run:

    python3 -m eval.development_sets --set sealed-v2 --concurrency 2 --timeout 900 --check

## The gate this import had to keep

The freeze's own check is
`git diff --stat freeze-2026-10-11 HEAD -- tribunal prompts policy`, which must
print nothing. **This import changes nothing under `tribunal/`, `prompts/` or
`policy/`**: its code changes are in `eval/` and its tests are in `tests/`, and
`git status --porcelain -- tribunal prompts policy` is empty at this commit. The
`wild-v2` import broke this gate by putting a name into `tribunal/precedents.py`;
this set's absence from `tribunal.precedents.EXTERNAL_SET_DIRS` is recorded in
`tests/test_precedents.py`'s `NOT_YET_IN_PRECEDENTS` instead, so the frozen tree
stays byte-identical to the tag.

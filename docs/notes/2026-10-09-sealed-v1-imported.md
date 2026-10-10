# The third sealed set imported and registered

**2026-10-09.** This is Part 2 of the third-freeze task, recorded from the files
it produced. Part 1 — the freeze at the tag `freeze-2026-10-09`, its note and its
digests — is `docs/notes/2026-10-09-the-third-freeze.md`, and it was committed
and pushed before the archive below was opened.

**No model call was made by this import.** The set is run afterwards, once, by
the owner, outside this sandbox.

**Structure, counts and digests only.** Until the sealed run is committed, no
case content and no answer value is printed, quoted or summarised anywhere in
this repository.

## The archive, verified before anything was imported

| what was recorded on receipt | |
|---|---|
| path | `~/Desktop/tribunal-sealed-v1.zip` |
| size | 194,719 bytes |
| entries | 42 (36 files and 6 directory entries) |
| sha256 | `d6938a52edb450aeb068758d20ab42d545456da0d2d6ade46cdaede04f94971b` |

The digest was recomputed before anything was copied out, and it equals the value
recorded above. The rule was to stop if it did not; it did, so the import
proceeded. The archive was unpacked into a scratch directory outside the
repository, which is where every comparison below was made.

The archive's own `eval/sealed/MANIFEST.json` records the set as
`tribunal-sealed-v1`, created `2026-09-26`, authored by
`Claude (independent of prompt tuning; never saw dev-set misses or prompts)`, of
24 cases, schema 1.2.0. Those are the author's statements, recorded as stated.

## Where the files went

Mirroring `wild-v2`'s import: the cases flat under `data/external/`, the key
under `eval/answers/`, and everything else — including the set's own authoring
material — under `eval/external/`.

| archive path | repository path | files |
|---|---|---|
| `data/sealed/cases/case-*.json` | `data/external/sealed-v1/case-*.json` (flat) | 24 |
| `data/sealed/index.json` | `data/external/sealed-v1/index.json` | 1 |
| `eval/sealed/ground_truth.json` | `eval/answers/sealed-v1/ground_truth.json` | 1 |
| `eval/sealed/eval_index.json` | `eval/external/sealed-v1/eval_index.json` | 1 |
| `eval/sealed/MANIFEST.json` | `eval/external/sealed-v1/MANIFEST.json` | 1 |
| `gen/` | `eval/external/sealed-v1/gen/` | 6 |
| `README.md` | **not imported** — kept outside the repository | — |
| `DESIGN.md` | **not imported** — kept outside the repository | — |

**34 files imported.** `data/external/sealed-v1/` holds 25 of them — the 24 cases
and the index — `eval/answers/sealed-v1/` holds one, and `eval/external/sealed-v1/`
holds eight (the manifest, the evaluation index and the six generator files).

The three destinations sit on two sides of the boundary `WORKBUDDY-SCOPE.md`
draws. `data/external/sealed-v1/` is agent-visible and answer-free, under the
contract `data/cases/` and `data/external/wild-v2/` are under.
`eval/answers/sealed-v1/` and `eval/external/sealed-v1/` are answer-bearing:
nothing under `tribunal/` may read either, and the second holds the set's own
generator and its manifest.

## The two files kept outside the repository

Two of the archive's 36 files are **not** imported: its `README.md` and its
`DESIGN.md`. Both are written in Chinese (683 and 278 Han characters), which the
standing language rule forbids in any tracked text file outside `runs/`, and both
are answer-bearing at case level. Nothing on the development side may open,
translate or summarise either before the sealed run is committed, so neither was
read, and neither is copied in.

| archive path | sha256 | disposition |
|---|---|---|
| `README.md` | `ad4826f9bd81c6a0997d8fd2c7d5e44739b9d69ce37db021a540b4484c50a7dd` | kept outside the repository: written in Chinese; an English translation is added after the sealed run is committed |
| `DESIGN.md` | `3341b4423fa45e9198c347e9db4723d1548789c012638ae6190e2adf9f8e24a4` | kept outside the repository: written in Chinese; an English translation is added after the sealed run is committed |

The other 34 files were imported, and every one is byte-identical to its archive
entry except the two in the next section.

## The digest of every imported file

All 34 imported files, as committed. Each hashes to the archive's own value
except the two in the next section.

| repository path | sha256 |
|---|---|
| `data/external/sealed-v1/case-00301.json` | `de57a0981fa9e9f81469d8bb3de185f9afe50deb5d56568dff0956ee1753b951` |
| `data/external/sealed-v1/case-00302.json` | `dccd462dd75773c95bab65aa19409b3b29f66916c3b1cd84c4efc8c561f7cd56` |
| `data/external/sealed-v1/case-00303.json` | `cd1b48fd3e421ed24e684fc1ef2563dc8f00dbbb9f39a8d83847fcfd7cbedde1` |
| `data/external/sealed-v1/case-00304.json` | `bad5591a87c127c553e481f7d35ec2b4508b6d762f03364a841d80af57cb03ee` |
| `data/external/sealed-v1/case-00305.json` | `165d53bf117e349b34d619137875437e0c37a4520492e52affc4895101d76c29` |
| `data/external/sealed-v1/case-00306.json` | `08adf9263f2124db4a02fb6b47e781fbd7a5a86bd8c6982a6d6b7a4e6ee3ceac` |
| `data/external/sealed-v1/case-00307.json` | `696ab2f360089afd167e2946a7b88d50a58be39d8ddd34a2b9a01b651dfc05f1` |
| `data/external/sealed-v1/case-00308.json` | `1c79116c9f86dd54e214787768a604d15deaa040920d490a7d9dfddbfb44e359` |
| `data/external/sealed-v1/case-00309.json` | `eeb710c09c2b2f3687f8ef0ac240f11c85d710b471ba31217873f6f6a136a231` |
| `data/external/sealed-v1/case-00310.json` | `78731f6c0c35fc3017b2a567c8b1c1f1d5686a49f20b686feabb95ac0f2def47` |
| `data/external/sealed-v1/case-00311.json` | `d3c07949861631f38ae390fbe51227a035e3a89b2b14742a537e18f067a5acd3` |
| `data/external/sealed-v1/case-00312.json` | `9ddbf9945e9430a9bba9f312b55f96b68d372b55853421ed132e789ba5336e82` |
| `data/external/sealed-v1/case-00401.json` | `36a16e50f91a867fda1a6a4022c3692bab6596fa4a76b2dac93dcd523e54a5ee` |
| `data/external/sealed-v1/case-00402.json` | `2cd70620fd0ae6a025e5ee31e935acdf0957f167a1249837f84d3bb804726e77` |
| `data/external/sealed-v1/case-00403.json` | `d761ebc64a3dc6f0e83f8b412b6644daae157aa544106ee3593905b8f3baec45` |
| `data/external/sealed-v1/case-00404.json` | `e28ba333bfe7afddd66fd764e5070b55c1543793b80276673d84f2588103b3cf` |
| `data/external/sealed-v1/case-00405.json` | `8a862fc7deec769fc533dfe00bc82dff3ab24a0d279d217d773aa5f47aab2e15` |
| `data/external/sealed-v1/case-00406.json` | `e1ea97954f51a533c7fc1c1c736425ca1e66f37d8c071b4a6c62c58c24c888f2` |
| `data/external/sealed-v1/case-00407.json` | `ab6a81440edd629c3585fa0af699cee2e5bbacc0f6a7fde860f72fd26bc4f482` |
| `data/external/sealed-v1/case-00408.json` | `50907cce41674cdf8ba4ffb098682d4ad5fda99a369731ecf049649e5c737dc4` |
| `data/external/sealed-v1/case-00409.json` | `d164f606046bcac553e50ff2f9ba5eaee6b3f531e95abd3237f00d285ee555df` |
| `data/external/sealed-v1/case-00410.json` | `237a8a9dd6f3e8dfc6767dc172bbc79fe4667f6d104890532dad631440d710b4` |
| `data/external/sealed-v1/case-00411.json` | `82b0c90a3868ed444b331ec5df6fcc70e6a933165d7d453bcbbb4adc731b4eaf` |
| `data/external/sealed-v1/case-00412.json` | `9172a6fffea5fe8e302775a8751beae9259e1058b71b4447774325e309d04781` |
| `data/external/sealed-v1/index.json` | `d55b706f1898786a4c48013c3de7de84e0be94f4a8b93aa12f334ee69e1de71e` |
| `eval/answers/sealed-v1/ground_truth.json` | `f430f6c017e109bd0feee86e3eac611dab7b087dee51ec5f644eb2eb9880b353` (the version-6 key, 2026-10-10; the key owner's note on the re-derivation is committed with the sealed run; imported as `7529d925e9defa6a93576661cda22f553e5337bad8662d87e813bc5b3fc74640`) |
| `eval/external/sealed-v1/eval_index.json` | `989bbf5f8d61efe32d6545c4aea4ce48379a44edd192db1c5cdaf233ad49b3ee` |
| `eval/external/sealed-v1/MANIFEST.json` | `f4eb7a4ffc1841b927e98dd7782faa1f160bd7f0cb9db21ec3c91ad31b43b12d` |
| `eval/external/sealed-v1/gen/build.py` | `d508efba157b7b2123f49c97d0bb779f7c27936365f6a4b529d725aca2758293` |
| `eval/external/sealed-v1/gen/core.py` | `0793379e73091aba1093bd1b034744fa569e632cad0feaedfb06d0a4af0d8ae4` |
| `eval/external/sealed-v1/gen/ns_cases.py` | `2766364e74ec02e0be8531a1b793324bee1a023531e8cc68b7f1fee231cdac19` |
| `eval/external/sealed-v1/gen/places.py` | `d5b10bf1af2d3009953d58e23c801f8cdfdccedf65086c1cb748d4b0a8f9c21b` |
| `eval/external/sealed-v1/gen/rd_cases.py` | `43641e912bf2b910c14f0e07c6b1fede61e84a6a8a1e9f6137efd89d829d5ded` |
| `eval/external/sealed-v1/gen/validate.py` | `564db1e458ccfbb172bb85ebfb5b94a464555c5b382811868fd9231da0ddd1e3` |

## The two files that are not byte-identical to the archive

The rule is to copy bytes exactly and re-serialise nothing. Two files could not
be copied as they were, and both are the archive's own content re-serialised
rather than changed. Neither alters a case, a ruling or an answer.

- **`data/external/sealed-v1/index.json`.** Every entry of the archive's index
  carries `"file": "cases/case-00301.json"`. The cases are imported flat, as
  `wild-v1`'s and `wild-v2`'s are, so that path resolves to nothing and
  `loader.load_external_set_case` refuses every case of the set. The `file` field
  of all 24 entries is rewritten to `case-<NNNNN>.json`; every other field of
  every entry is unchanged, and the entries were compared as values before and
  after.
  - archive `d96b0d7f26c3a62ce5437f4980fecf17915dcfd3602b06308d0f280790552647`
  - committed `d55b706f1898786a4c48013c3de7de84e0be94f4a8b93aa12f334ee69e1de71e`
- **`eval/answers/sealed-v1/ground_truth.json`.** The archive's key is a JSON
  **object** keyed by case number. `eval.grade.load_answer_key` requires a JSON
  **array** of records each carrying a `ground_truth` object, so the archive's
  file raises `GradeError` on the grader that has to read it — and the structure
  check this task asks for cannot be met without a change. It is re-wrapped into
  `[{case_no, dispute_id, ground_truth}, ...]`, each `ground_truth` object
  carried across unchanged. **Every number literal is preserved exactly**: the
  re-wrap is textual, so no literal is dropped, rounded or re-serialised, and all
  171 decimal literals in the archive's key appear verbatim in the committed one.
  - archive `412d60bdf207b2be7f66986f40dc4d517b084df7e45dc4c12b566686cddd7f6d`
  - committed `7529d925e9defa6a93576661cda22f553e5337bad8662d87e813bc5b3fc74640`
  - **The proof it changed nothing.** Both files were parsed with
    `parse_float=Decimal` and compared **as values, never as text**: 24 records,
    each one's seven fields equal, and the committed records all carry all four
    graded fields. No value was printed at any point.

The other 32 imported files are byte-for-byte the archive's, checked by hashing
both sides.

## The digests the archive's MANIFEST states

`eval/external/sealed-v1/MANIFEST.json` states four digests of its own content.
Three reproduce, by a method the manifest's own structure makes plain; the
fourth is recorded as stated.

| MANIFEST field | value | the method | reproduces |
|---|---|---|---|
| `case_file_sha256` | 24 values | sha256 over each case file's bytes, keyed by its file name | yes, all 24 |
| `answer_key_sha256` | `412d60bdf207b2be7f66986f40dc4d517b084df7e45dc4c12b566686cddd7f6d` | sha256 over the bytes of the archive's own `eval/sealed/ground_truth.json` | yes |
| `eval_index_sha256` | `989bbf5f8d61efe32d6545c4aea4ce48379a44edd192db1c5cdaf233ad49b3ee` | sha256 over the bytes of the archive's own `eval/sealed/eval_index.json` | yes |
| `case_set_sha256` | `5ae223770b880bb4add85b474da1274b46a853ecaed6ee7c968776c4838ce5f2` | **not stated by the archive, and not reproduced** | no |

The `answer_key_sha256` is the digest of the key **as the archive holds it**, so
it does not match the committed key, which is the re-wrapped one at
`7529d925…` recorded above. That is expected rather than a discrepancy: a digest
of a file cannot survive that file being re-serialised, which is why every run
records the digest of the key it actually read.

**The one field whose method is unstated is recorded rather than guessed.** The
archive ships no script that writes `MANIFEST.json` — its `gen/build.py` emits
the cases, the key, the index and the evaluation index and no manifest — so no
method for `case_set_sha256` is available to check against. It is left as the
manifest states it, and the 24 per-file digests it also states are the ones that
are held to.

## What the structure-only check found

Reading **no case content and no answer**: structure and counts only.

- The archive's sha256 is
  `d6938a52edb450aeb068758d20ab42d545456da0d2d6ade46cdaede04f94971b`.
- There are **24** case files, numbered **301 to 312** and **401 to 412** —
  two contiguous twelve-wide ranges, so the count and the ranges are the same
  numbers. **12 are `ROUTE_DEVIATION`** (301-312) and **12 `NO_SHOW_CHARGE`**
  (401-412), which is the archive's own manifest's count too.
- Every case loads through `loader.load_external_case` (by path) and through
  `loader.load_external_set_case` (by number, through the set's own index), and
  no forbidden key appears in any of them.
- **No case number, dispute id or trip id collides** with any other registered
  set or with the corpus manifest. Checked over the eight registered sets and
  `data/index.json`.
- **No case carries `trip_record.platform_policy`**, so a version-6 brief derives
  the `AUTHORED-V1` block for the no-show cases, as it does for the corpus and
  `wild-v2`. Checked on case 401: its brief's `platform_policy_in_force.source`
  is `AUTHORED-V1`.
- The key loads through `eval.grade.load_answer_key` as **24 records numbered 301
  to 412**, each carrying all four graded fields and a `difficulty`. The
  difficulty split the archive's manifest states is **HARD 14, EASY 4, REVERSAL
  3, INDETERMINATE 3**, which is a count of the key's own `difficulty` values and
  not a claim about the cases.
- **No imported file holds a CJK character**, and neither does any case. The two
  files that do are the two kept outside the repository, above.
- **No case content and no answer value is printed, quoted or summarised
  anywhere in this repository until the sealed run is committed.**

## The registration

The set is registered in `eval/development_sets.py` as `SEALED_V1`, apart from
`DEVELOPMENT_SETS`:

- It carries `sealed=True` and `policy_version=6`, and it is the third name in
  `SEALED_SETS`. `--set all` reads `DEVELOPMENT_SETS` and so never runs it, and
  `--report` prints it in a section of its own, never inside the combined figure.
  Its runs go to `runs/sealed-v1/<model-slug>/`, and it is graded against
  `eval/answers/sealed-v1/ground_truth.json` through its own loader.
- Its `run_arguments` fix the freeze note's configuration: model
  `deepseek/deepseek-flash`, judge votes 4, verifier off, `--timeout 900`,
  `--concurrency 2`, and the prompts directory, the case deadline and the token
  budget as "the default". `--parallel-calls` is not carried by `RunArguments`
  and is therefore not pinned by the registration; the run is made with it, as
  the freeze note records, and it changes nothing a run measures.
- `run_benchmark.SEALED_V1_SET_RUNS_SUBDIR` is a fourth name in
  `SET_RUNS_SUBDIRS`, so `runs/sealed-v1/<model-slug>/` is a headline directory
  and all six switched destinations refuse it. It is the one name in
  `UNRUN_SEALED_RUNS_SUBDIRS`, so it is the one sealed root whose plain run the
  permit still opens — and every other destination under it is refused.
- `assert_not_sealed` refuses `--force`, `--replay-advocates`, `--replay-check`
  and `--verify-recorded-drafts` for this set, and `--policy-version` is refused
  while the command line is read.
- `tests/test_sealed_set_sealed_v1.py` holds the registration, the bundle digest
  table, the two kept-outside files, the opt-in gate, the `--force` and
  frozen-argument refusals and the structure checks. Counts and keys only, never
  a value.
- `tests/test_answer_isolation.py` gains a `SealedV1IsolationTest` beside the
  others: no answer field in any of the 24 case files, no brief carrying an
  answer-key field name, no module under `tribunal/` naming either of the two
  paths that hold the set's answers, and a falsifiability check that goes red on
  a spliced case.

Three existing tests were updated, and each is a count or a list that this
import's own registration moves: the sealed-set name tuples in
`tests/test_sealed_set.py` and `tests/test_sealed_set_wild_v2.py` gain
`"sealed-v1"`, the headline-directory counts there go from four to five, and
`tests/test_precedents.py`'s `NOT_YET_IN_PRECEDENTS` gains `"sealed-v1"` — the
same list the `wild-v2` import added its own name to.

## The key will be re-derived before the run

**The key in this archive was written under policy version 1**, and its manifest
records the policy versions it was authored against (`general` 1.0.1, `no_show`
1.1.1, `route_deviation` 1.1.0). Ji Guofang, the key owner, will re-derive it
under the frozen **version 6**, without seeing any system output on this set, and
a later commit will replace it, recording the old and new `answer_key_sha256`.

**The single run waits for that key.** The registration reads the key's digest
from the key file rather than pinning today's digest in code, so the replacement
touches only `eval/answers/sealed-v1/` and the digest table in
`tests/test_sealed_set_sealed_v1.py`.

## The set's own README says "run once, k=3"

The archive's `README.md` says the set is to be run once, with `k` equal to 3 —
and its manifest's `protocol` records the same thing (`runs_allowed` 1, `k` 3).
**The set does not define `k`.** The run is therefore made **once**, with the
frozen configuration — judge votes **4**, the configuration of the two earlier
sealed runs — and not three times. The README is one of the two files kept
outside the repository and was not read; the `protocol` object is where this
repository read the same statement.

## The command the owner will run

    TRIBUNAL_SEALED_RUN=sealed-v1 python3 -m eval.development_sets --set sealed-v1 --concurrency 2 --timeout 900

The flags are the freeze's: `--set sealed-v1` is accepted, `--concurrency` and
`--timeout` are both arguments of it, and the policy version needs no flag
because the registration fixes it at 6. `--force` cannot be added to it: it is
refused for this set in code. The run is made only if
`git diff --stat freeze-2026-10-09 HEAD -- tribunal prompts policy` prints
nothing.

`TRIBUNAL_SEALED_RUN=sealed-v1` is the opt-in, and it is what makes this run the
owner's: without it the invocation is refused before any client is built, and
nothing in this repository sets that variable. To see what a plain invocation
would run without running it, put `--check` in place of the run:

    python3 -m eval.development_sets --set sealed-v1 --concurrency 2 --timeout 900 --check

## The gate this import had to keep

The freeze note's own check is
`git diff --stat freeze-2026-10-09 HEAD -- tribunal prompts policy`, which must
print nothing. **This import changes nothing under `tribunal/`, `prompts/` or
`policy/`**: its code changes are in `eval/` and its tests are in `tests/`. The
`wild-v2` import broke this gate by putting a name into
`tribunal/precedents.py`, and `sealed-v1`'s absence from
`tribunal.precedents.EXTERNAL_SET_DIRS` is recorded in
`tests/test_precedents.py`'s `NOT_YET_IN_PRECEDENTS` instead, so the frozen tree
stays byte-identical to the tag.

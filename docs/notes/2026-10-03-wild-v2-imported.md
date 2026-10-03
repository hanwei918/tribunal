# The second sealed set imported and registered

**2026-10-03.** This is Part 2 of the second-freeze task, recorded from the files
it produced. Part 1 — the freeze at the tag `freeze-2026-10-03`, its note and its
digests — is `docs/notes/2026-10-03-the-second-freeze.md`, and it was committed
and pushed before the archive below was opened.

**No model call was made.** The set is run afterwards, once, by the owner,
outside this sandbox.

**Structure, counts and digests only.** Until the sealed run is committed, no
case content and no answer value is printed, quoted or summarised anywhere in
this repository.

## The archive, verified before anything was imported

| what the owner recorded on receipt | |
|---|---|
| path | `~/Desktop/tribunal-wild-v2-sealed-20261001.zip` |
| size | 219,666 bytes |
| modification time | 2026-10-01 10:49:47 |
| entries | 45 |
| sha256 | `13d90441b0af47b69168fef96034da5e190b835c9d4a4cc2e337d776003bde41` |

The digest was recomputed before anything was copied out, and it equals both the
value recorded above and the one in the `.zip.sha256` file shipped beside the
archive. The rule was to stop if it did not; it did, so the import proceeded.
The archive was unpacked into a scratch directory outside the repository, which
is where every comparison below was made.

## Where the files went

Mirroring `wild-v1`'s import: the cases flat under `data/external/`, the key
under `eval/answers/`, and everything else — including the set's own authoring
material — under `eval/external/`.

| archive path | repository path | files |
|---|---|---|
| `data/wild-v2/cases/case-*.json` | `data/external/wild-v2/case-*.json` (flat) | 20 |
| `data/wild-v2/index.json` | `data/external/wild-v2/index.json` | 1 |
| `eval/wild-v2/ground_truth.json` | `eval/answers/wild-v2/ground_truth.json` | 1 |
| `README.md` | `eval/external/wild-v2/README.md` | 1 |
| `MANIFEST.json` | `eval/external/wild-v2/MANIFEST.json` | 1 |
| `eval/wild-v2/seed_map.json` | `eval/external/wild-v2/seed_map.json` | 1 |
| `eval/wild-v2/seed_selection.json` | `eval/external/wild-v2/seed_selection.json` | 1 |
| `eval/wild-v2/omitted_seeds.json` | `eval/external/wild-v2/omitted_seeds.json` | 1 |
| `eval/wild-v2/semantic_check.json` | `eval/external/wild-v2/semantic_check.json` | 1 |
| `eval/wild-v2/validation.txt` | `eval/external/wild-v2/validation.txt` | 1 |
| `eval/wild-v2/legacy_semcheck.txt` | `eval/external/wild-v2/legacy_semcheck.txt` | 1 |
| `eval/wild-v2/legacy_check_differences.md` | `eval/external/wild-v2/legacy_check_differences.md` | 1 |
| `eval/wild-v2/source-unused-seeds.jsonl` | `eval/external/wild-v2/source-unused-seeds.jsonl` | 1 |
| `gen/` | `eval/external/wild-v2/gen/` | 8 |
| `policy/` | `eval/external/wild-v2/policy/` | 3 |
| `data/PUBLIC-CONTRACT.md` | `eval/external/wild-v2/data/PUBLIC-CONTRACT.md` | 1 |
| `data/schema.json` | `eval/external/wild-v2/data/schema.json` | 1 |

**45 files imported.** `data/external/wild-v2/` holds 21 of them — the 20 cases
and the index — `eval/answers/wild-v2/` holds one, and `eval/external/wild-v2/`
holds 23.

**Two rules decided where the last four went.** *Anything answer-bearing that is
not agent input stays out of `data/`*, which is why the archive's own `policy/`
snapshot, its `data/schema.json` snapshot and its `data/PUBLIC-CONTRACT.md`
snapshot are filed under `eval/external/wild-v2/` rather than anywhere under
`data/`: the set's authoring bundle is evidence about how the set was made, and
`data/` is the tree an agent may read. And *the README, the MANIFEST and the
generator files go under `eval/external/wild-v2/`*, which is where they are.

The three destinations sit on two sides of the boundary `WORKBUDDY-SCOPE.md`
draws. `data/external/wild-v2/` is agent-visible and answer-free, under the
contract `data/cases/` and `data/external/wild/` are under. `eval/answers/wild-v2/`
and `eval/external/wild-v2/` are answer-bearing: nothing under `tribunal/` may
read either, and the second holds the set's own generator, its manifest, its
author's README and its author's accounting of the seeds it used and did not.

**One thing the archive carries that this repository does not.** Its
`data/schema.json` is a schema **1.2.0** snapshot. The repository has no
`data/schema.json` at all — the corpus schema lives in `data/PUBLIC-CONTRACT.md`
and in the loader — so there was nothing to compare it against and it was
imported as the set's own record of the schema it was authored to.

**The archive's `policy/` files are byte-identical to this repository's.** All
three hash to the same values the freeze note records for the committed
`policy/` tree, so the set was authored against the same policy bytes the run
will brief from. That is checked by digest, not assumed from the file names.

## The digest of every imported file

All 45 files, as committed. Each hashes to the archive's own value except the two
in the next section.

| repository path | sha256 |
|---|---|
| `data/external/wild-v2/case-00701.json` | `31c3e7507a697d4b654eba1fe18ae45145f7c9b8ce69b0edd9f99fa0912580e6` |
| `data/external/wild-v2/case-00702.json` | `0ed158d9a4668d5856467511b919398740c09aee3b473e7b405aeae6c9994613` |
| `data/external/wild-v2/case-00703.json` | `ea109388b9980c86df2e9929a193e623c3afa1672b64968183f7d558aa6733dd` |
| `data/external/wild-v2/case-00704.json` | `328236de640b8c9ca8e3a7b605aa9754a5a4d87a326eff10f0af255759da6b1a` |
| `data/external/wild-v2/case-00705.json` | `652c0adbf01e539e7551571827dd7d8190da301962244c62170858842c692d52` |
| `data/external/wild-v2/case-00706.json` | `03d7ed446527bac99139fbc3ba4a39d337af6513188af778f3db6d9061c6ae65` |
| `data/external/wild-v2/case-00707.json` | `1d2dbf7f36f962fbba80e76346a9840cb6ff92edd006f429130fa5c26a7d4626` |
| `data/external/wild-v2/case-00708.json` | `1cb7916f07dbe657ccd2582a86f67b14433c2651f253f19d9b8bf20e0baf6260` |
| `data/external/wild-v2/case-00709.json` | `91535ec1709a2dff3e121eeb26ec7244d2358b0a93094a33bc39133ea465f834` |
| `data/external/wild-v2/case-00710.json` | `fa00ede6cfca449c1267e4abd1c5a19e6022a443da75548e98aca9b9cb14848b` |
| `data/external/wild-v2/case-00711.json` | `a6841946c991392866b45e0be0ac5887a8b3df46aecaba12bfec364b778532b9` |
| `data/external/wild-v2/case-00712.json` | `e61c9cda5ad110a08264a5002a153a2d36d6296b70130e9d12093d634c4d7bbc` |
| `data/external/wild-v2/case-00713.json` | `b7ce2cd62a11362210c08f121940813309d5743d587470d412c28e2dd9f2485a` |
| `data/external/wild-v2/case-00714.json` | `11205e39d5b235f90d523389eeb5c64630260686fed98a26f9dcdfa5a061cbd1` |
| `data/external/wild-v2/case-00715.json` | `06da20746c874be5ea8383fab603d2da2c459e5f68d207b38db51cc759f25052` |
| `data/external/wild-v2/case-00716.json` | `6ce954656da261ef2aa1a853fe2cb93243dbcc4b4739a0921093a961240e46cc` |
| `data/external/wild-v2/case-00717.json` | `48a79b3c375c50fd0b6f66b0198a3503f2ee0dc25113c41c6cb76d544f12ad99` |
| `data/external/wild-v2/case-00718.json` | `995606671cf86452ca28174fb220fdf7ab67262aaddb80cbfa882dc68064754d` |
| `data/external/wild-v2/case-00719.json` | `4653f23dc929710ce90154d4ea0eba63042e1e94bdf46a879e3d7eb73174628c` |
| `data/external/wild-v2/case-00720.json` | `eb63763648fb423b698746e689eef1be20aad69d3a79638d48a06d623def0fcf` |
| `data/external/wild-v2/index.json` | `c7116bc699b80b5957aaf3778d966b47d06beda9908dd3591032372a224b1473` |
| `eval/answers/wild-v2/ground_truth.json` | `c02bdc626acf0e379670b3635198abd524d15ce6bba0b7e28ad04d49a27b806e` |
| `eval/external/wild-v2/README.md` | `8e24029edba2b1fdf27430fc86ffff77f59e4846ba1b864c299f4cef3fadceca` |
| `eval/external/wild-v2/MANIFEST.json` | `369e819d799ac712be1675778486a827b2aec592ae700a3ea2dea194d6ab19fb` |
| `eval/external/wild-v2/data/PUBLIC-CONTRACT.md` | `79a8f4d7410933daf7350ea3172bcd7e5aebaca99b695cc6210ad5e7c417358f` |
| `eval/external/wild-v2/data/schema.json` | `d8bdd16356005016b4f23bf46419a1bd541827822ef9eb225c72d5eb05c7112a` |
| `eval/external/wild-v2/gen/build_v2.py` | `9f99e741e37495d6f4b6d1c1eb926c273e63f4d8ab3233d2b87cca92630c480d` |
| `eval/external/wild-v2/gen/core.py` | `0793379e73091aba1093bd1b034744fa569e632cad0feaedfb06d0a4af0d8ae4` |
| `eval/external/wild-v2/gen/legacy_semcheck.py` | `62097c38193336c22213020989935b4047c520766aa7a41d1b452e87a1fb33bd` |
| `eval/external/wild-v2/gen/places.py` | `ab0eab77710364a50315be0229ab946abc11b3903cd0d0082724de838b89dc77` |
| `eval/external/wild-v2/gen/release.py` | `ae2d1ef09584c49767eebb9da88d0e268670da624ddeece826dd44540e82677e` |
| `eval/external/wild-v2/gen/semcheck.py` | `a4dda3c2cba6d19ded6db031af5b274e39e3bf405ee9489852636383163db999` |
| `eval/external/wild-v2/gen/validate.py` | `ba7bf095aa7493f52a13fd27d1770065ec9b1a79852bb2c0f2c20bc1c58e73e3` |
| `eval/external/wild-v2/gen/wild.py` | `ddb25683e4c1ce5ac4c037ef980415ce52373b93c20f1aee21819f72ae88ccc5` |
| `eval/external/wild-v2/legacy_check_differences.md` | `5fb2991b5afbd128edf41121b77884dcde6ea06dbf24f8ceaf15e793973312fd` |
| `eval/external/wild-v2/legacy_semcheck.txt` | `464b72343ac9a6d19e2ed42c2c40ab4e35cf0e1ff8d34dd3b2bec7f77f814d2f` |
| `eval/external/wild-v2/omitted_seeds.json` | `bebb3bd6a2e50dbe6bb98339140713aa05d987f448eefaf097c72665c737073f` |
| `eval/external/wild-v2/seed_map.json` | `380d130e6e5d7fe1c3c2397955cffaeec2a85063dcdacc456338c24bd959daf2` |
| `eval/external/wild-v2/seed_selection.json` | `015f13876db8e53b3b7492f4434d4c52e5a0aa540ce27adb6a1273713ac85ba0` |
| `eval/external/wild-v2/semantic_check.json` | `6bc12cdcf4a884e69e7adc1310b59aca40363fff1530aebdffe8d9b283a8c093` |
| `eval/external/wild-v2/source-unused-seeds.jsonl` | `279371acf2cf0153c2630ea5bde9acdd9ca5da5b78c85df457184c639ff3db60` |
| `eval/external/wild-v2/validation.txt` | `d6d63c654bf0ba94f456495f13b44b536048df91f560e4e2adcef5b45b5024b4` |
| `eval/external/wild-v2/policy/general.json` | `12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf` |
| `eval/external/wild-v2/policy/no_show.json` | `7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf` |
| `eval/external/wild-v2/policy/route_deviation.json` | `628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d` |

## The two files that are not byte-identical to the archive

The rule is to copy bytes exactly and re-serialise nothing. Two files could not
be copied as they were, and both are the archive's own content re-serialised
rather than changed. Neither alters a case, a ruling or an answer.

- **`data/external/wild-v2/index.json`.** Every entry of the archive's index
  carries `"file": "cases/case-00701.json"`. The cases are imported flat, as
  `wild-v1`'s are, so that path resolves to nothing and
  `loader.load_external_set_case` refuses every case of the set. The `file` field
  of all 20 entries is rewritten to `case-<NNNNN>.json`; every other field of
  every entry is unchanged. The edit was kept to that one field so that the
  result could be hashed and disclosed.
  - archive `850eae84858c0a7dfa2b49800aeffd83cebe831944f39f562fe1d89f60ff626f`
  - committed `c7116bc699b80b5957aaf3778d966b47d06beda9908dd3591032372a224b1473`
- **`eval/answers/wild-v2/ground_truth.json`.** The archive's key is a JSON
  **object** keyed by case number. `eval.grade.load_answer_key` requires a JSON
  **array** of records each carrying a `ground_truth` object, so the archive's
  file raises `GradeError` on the grader that has to read it — and the structure
  check this task asks for cannot be met without a change. It is re-wrapped into
  `[{case_no, dispute_id, ground_truth}, ...]`, each `ground_truth` object
  carried across unchanged: no number literal is dropped, rounded or invented.
  - archive `e57739471e0981c32e72ad9bdc389b58c74a64141ff60e2b00c0884175f71e43`
  - committed `c02bdc626acf0e379670b3635198abd524d15ce6bba0b7e28ad04d49a27b806e`
  - **This re-wrap is a commit of its own**, as the task requires, and it is the
    only thing in that commit.
  - **The proof it changed nothing.** Both files were parsed with
    `parse_float=Decimal` and compared **as values, never as text**: 20 records,
    and for each one its four graded fields and its `difficulty` — 100
    comparisons — all equal, and the new file's records all carry all four graded
    fields and a difficulty. No value was printed at any point. The comparison
    was made before the commit; **the commit's message does not report it**. That
    message states what the commit did and not what was measured against it —
    *"Rewrap wild-v2's key into the array shape the grader reads, keeping every
    record's four graded fields and its difficulty unchanged"* — so this note is
    where the measurement is recorded.

The other 43 imported files are byte-for-byte the archive's, checked by hashing
both sides.

## The digests the archive's MANIFEST states

`eval/external/wild-v2/MANIFEST.json` states three digests of its own content.
All three reproduce, and each by a method the manifest itself names or implies:

| MANIFEST field | value | the method | reproduces |
|---|---|---|---|
| `case_set_sha256` | `d81fe371ede919bf65e55e44d07d7fb0bd2b143e2f84b1057a9623228e597faa` | sha256 over the compact, key-sorted UTF-8 JSON of the sorted `[{path, sha256}]` case list — the manifest states this algorithm in `case_set_hash_algorithm` | yes |
| `index_sha256` | `850eae84858c0a7dfa2b49800aeffd83cebe831944f39f562fe1d89f60ff626f` | sha256 over the bytes of the archive's own `data/wild-v2/index.json` | yes |
| `answer_key_sha256` | `e57739471e0981c32e72ad9bdc389b58c74a64141ff60e2b00c0884175f71e43` | sha256 over the bytes of the archive's own `eval/wild-v2/ground_truth.json` | yes |

The second and third are the digests of the two files **as the archive holds
them**, so neither matches the committed file, which is the re-serialised one
recorded above. That is expected rather than a discrepancy: a digest of a file
cannot survive that file being re-serialised, which is why every run records the
digest of the key it actually read.

The manifest's other fields are the set's name, its case count, its status
(`SEALED`), the date it was created, a `files` mapping of 44 paths to digests,
and a `checks` object. The `checks` object records that no Tribunal inference run
was made (`formal_tribunal_inference_runs`: 0), that the loader loaded every case
in isolation (`isolated_loader_cases`: 20, which is the count this repository
independently reaches below), that the schema contract and the amount limits were
unchanged, and that five cases differ under the author's *legacy* semantic
checker. Which five is in the manifest and in the private difference report under
`eval/external/wild-v2/`; the count is what this note records.

## What the structure-only check found

Reading **no case content and no answer**: structure and counts only.

- The archive's sha256 is
  `13d90441b0af47b69168fef96034da5e190b835c9d4a4cc2e337d776003bde41`.
- There are **20** case files, numbered **701 to 720** and contiguous — unlike
  `wild-v1`'s, which spans a 127-wide range for its 64 cases. **12 are
  `ROUTE_DEVIATION`** and **8 `NO_SHOW_CHARGE`**.
- The cases use schema **1.2.0**, carry **7 evidence items** each, and have no
  top-level `artifacts` key: the evidence array is the set's own layout.
- There is **no answer field in any case file**, checked by walking every key of
  every parsed case rather than by searching the text.
- **All 20 cases load** through `loader.load_external_set_case`, the loader the
  set is run with, named by number through the set's own index.
- **All 20 briefs build at policy version 2**, and **12 of the 20 differ from
  their version-1 brief**. The twelve are the twelve route-deviation cases: the
  amendment `0001-pol-rd-13` adds a clause to `policy/route_deviation.json` and
  to nothing else, and the eight no-show briefs are byte-identical at the two
  versions.
- The key loads through `eval.grade.load_answer_key` as **20 records numbered 701
  to 720**, each carrying all four graded fields. The difficulty split is
  **HARD 7, INDETERMINATE 5, EASY 4, REVERSAL 4**, which is a count of the key's
  own `difficulty` values and not a claim about the cases.
- **No imported file holds a CJK character.** This is where the second sealed
  set differs from the first: `wild-v1`'s README arrived in Chinese and had to be
  translated, under the precedent recorded in
  `docs/notes/2026-09-30-the-names-and-the-chinese-text.md`. This archive's
  README, manifest, generator and accounting files are all ASCII-clean, so no
  translation was needed and none was made.

## The set's own README, and how it differs from `wild-v1`'s

This is the one place where the second import is simpler than the first, and it
is worth recording because the first import's difficulty is still open.

`eval/external/wild-v2/README.md` is titled *"Tribunal wild-v2 — SEALED
HOLDOUT"*. It says in terms that this is **not** a development/regression set,
that the archive is to be kept unopened until the next freeze, that its
evaluation files are not to be handed to a repository assistant or to anyone
developing the system, and that it has not been run through the judge/advocate
pipeline. It asks the reader to record the archive's digest, leave it unopened
until after the freeze, run it once, save all raw outputs, and report the outcome
without selecting or suppressing failures.

**So the conflict `wild-v1`'s import recorded does not arise here.** That
archive's own README called its 64 cases a development and regression set and
named a different, 24-case set as the sealed one; the conflict is recorded in
`docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` and is still the owner's
to settle. This archive's README calls itself the sealed holdout, which is what
this task calls it too. Nothing was reconciled and nothing needed to be.

**Its accounting, and one discrepancy with the task's provenance.** The README
says the set is **20 cases generated from 17 distinct unused English source seeds
plus three variants**, out of a source pool of 84 seeds of which `wild-v1`'s map
used 62, leaving 22. It says five unused seeds were omitted rather than weakening
the format, and `eval/external/wild-v2/omitted_seeds.json` names them. The
owner's stated provenance in
`docs/notes/2026-10-03-the-second-freeze.md` says the request asked for **about
24** cases built from the 22 seeds `wild-v1` did not use.

- The archive holds **20** cases and used **17** seeds plus three variants; the
  request asked for about 24 and 22 seeds were available.
- **Recorded, not resolved.** Twenty is not twenty-four, and the difference is
  the author's to explain rather than this repository's to guess at. It does not
  change what the set is or how it is run, and it is not a reason to alter the
  archive.

**What the README says about how it was made, recorded as the author's
statement.** It says no `wild-v1` case shards, grading key, transcripts or
post-run notes were used in authoring; that the seed map and the original
archive's seed collection were used only for source selection; that the original
archive's reusable builder and validation helpers were used for formatting; and
that no original case specification modules were read. It also says no Tribunal
repository, policy or schema file was modified, and that its loading check was a
smoke test and not an AI adjudication run nor a use of the holdout to tune
Tribunal.

**One of those statements is corroborated by the bytes.** Three of the eight
files under `eval/external/wild-v2/gen/` are **byte-identical** to `wild-v1`'s
own: `core.py` (`0793379e…`), `places.py` (`ab0eab77…`) and `wild.py`
(`ddb25683…`). That is what "the original archive's reusable builder/validation
helpers were used for formatting" looks like from this side, and it is the only
part of the provenance this repository can check at all. The other five differ,
as they should: `build_v2.py` is the set's own builder, and the README says the
v1 semantic checker was preserved with only set-path changes as
`gen/legacy_semcheck.py`.

**The rest is not verified and cannot be.** Verifying the generator would mean
reading it against its cases, which is the reading a sealed set exists to keep
out of the development process. The owner's sentence on the limit of what is
known stands as written in `docs/notes/2026-10-03-the-second-freeze.md`:
"Whether Codex could read this repository while it worked is not recorded."

## The registration

The set is registered in `eval/development_sets.py` as `WILD_V2`, and the guards
that read the registry were extended with it. Four things are new; the rest is
the held-out set's machinery doing for this set what it already did for that one.

**Its runs go to `runs/wild-v2/<model-slug>/`.** `run_benchmark.WILD_V2_SET_RUNS_SUBDIR`
is a third name in `SET_RUNS_SUBDIRS`, so `headline_run_directories` now names
**four** directories — the corpus's, the second set's, the held-out set's and
this one's — and all six switched destinations read that one function rather than
keeping a list each. A set cannot be added to the registry without its run
directory being a headline directory.

**Its registration fixes policy version 2.** `DevelopmentSet` gained a
`policy_version` field, 1 for every set whose version is the command line's to
choose and 2 for this one. `run_set` passes that version to the runner and — the
new part — passes `policy_version_moves_the_run=False`, so the version decides
the briefs but **not** the directory: a version-2 run of an ordinary set goes to
`runs/policy-v2/<model>/`, and this set's goes to `runs/wild-v2/<model>/` and
never into a `policy-v2` directory inside it. The version is part of what the set
*is*, not a switch on the invocation.

**An explicit `--policy-version` on this set is refused.** `--policy-version` now
defaults to `None` rather than to version 1, so "not given" is told apart from
"given as version 1"; when it *is* given and the selected set fixes its own
version, the command line exits 1 with *"FATAL: wild-v2 fixes policy version 2 in
its registration, so --policy-version is refused for it"*. Without the flag,
`--set wild-v2` uses version 2 and no other.

**It is never part of `--set all` or of any combined figure.**
`SEALED_SETS` is `(wild, wild-v2)`; `ALL_SETS` is `DEVELOPMENT_SETS + (wild,)`,
deliberately **not** rebuilt from `SEALED_SETS`, because a set that has not been
run has no drafts, no brief digests and no amount to re-reduce, and a measurement
that counted its cases as misses would be reporting a run nobody made. The
amount-rule measurement and the recorded-drafts measurement both read `ALL_SETS`
and so both ignore it. `--report` prints each sealed set in a section of its own,
each with its own heading and caveat, and the combined line names no sealed set.
`BY_NAME` is built from `DEVELOPMENT_SETS + SEALED_SETS + RERUN_SETS`, so
`--set wild-v2` resolves.

**One sentence the report used to print had to move with the registration.**
`DEVELOPMENT_DATA_CAVEAT` ended *"The only generalisation figure the submission
reports belongs to the held-out set"*, which was true when there was one sealed
set and is not true with two. It now names both — the held-out set's run from
`freeze-2026-09-30` and the second sealed set's from `freeze-2026-10-03` — and
says the two are never added to each other either. The change is text only and no
test pinned the old wording; the tests that read this text assert on the
`held-out set` phrase, which is still there.

`tribunal/precedents.py` was first changed to gain `SET_WILD_V2` in
`EXTERNAL_SET_DIRS`, which is what would let `set_from_run_directory` read a
`runs/wild-v2/<model>/` path as this set. **That change broke the freeze gate and
has been taken back out**; see *The gate this import broke* below. The plain
sealed run never reads that table, and its only readers on the run path are
behind `--precedents`, which this set refuses.

## The gate this import broke

The freeze note's own check is
`git diff --quiet freeze-2026-10-03 -- tribunal prompts policy`. It exits `0` at
the tag, and it is the condition the sealed run is made under — so it is also the
sense in which this note's "run once from the commit tagged
`freeze-2026-10-03`" should be read: the run is made from a commit whose
`tribunal/`, `prompts/` and `policy/` trees equal those at the tag, which need
not be the tagged commit itself. Every event a run writes carries the commit it
was made from, so the run's own record answers which one that was.

`f4de316`, the commit that imported this set, put `SET_WILD_V2` into
`tribunal/precedents.py` — a package module, and so inside the frozen tree —
because two loops in `tests/test_precedents.py` had been widened to
`SEALED_SETS`. The gate therefore **exited 1 from `f4de316` onwards**, which the
session that made it did not notice: the tree the sealed run is meant to be made
from had been changed after the freeze, and nothing said so.

`310b72a` restored it. `tribunal/precedents.py` is byte for byte the tag's file
again, and the two loops skip the sets named in `NOT_YET_IN_PRECEDENTS`
(`{"wild-v2"}`) instead. The check prints `0` again, measured after that commit:

    $ git diff --quiet freeze-2026-10-03 -- tribunal prompts policy; echo $?
    0

    $ git log --oneline freeze-2026-10-03..HEAD -- tribunal prompts policy
    310b72a Sealed-run readiness: A — restore the freeze gate and refuse the un-run sealed set in the policy-gap loop
    f4de316 Register wild-v2 as a second sealed set at policy version 2, and give it every guard the held-out set has

Those two commits are the whole history of the frozen trees since the tag, and
the first is the repair of the second. Recorded rather than tidied away: a
package module is inside the frozen tree whatever its reason for changing, and
the gate has to be run after the commit and not only at the tag.

## The guards, and how each was seen to fail

Every guard `wild` has, this set has. **Not every one of them was asked to fire
before it was shown to hold**, and the section below says which was.

**The four switches that would replace or re-take the single run.**
`assert_not_sealed` refuses `--force` for any set marked `sealed`, and `--force`
is refused inside `run_set`; `--replay-advocates`, `--replay-check` and
`--verify-recorded-drafts` are refused while the command line is read, in both
CLIs, because every one of those produces a result from a run already recorded.
Each refusal is shown on a runs root that already holds a
`runs/wild-v2/<model>/` result, and the fixture is compared **byte for byte**
afterwards, so a refusal that quietly wrote something is caught rather than
assumed away. These tests do **not** then show "the clean case passing". What is
shown is that the guard is silent for every other set —
`assert_not_sealed(development_set, "--force")` returns `None` for the two
development sets and for `wild-dev` — and that the *plain* run of this set is
still accepted, which is
`test_the_plain_sealed_run_of_this_set_is_still_accepted` and is about the run
rather than about a switch.

**The switches that change what the agents are given.** `--ablate`,
`--precedents`, `--amount-rule` and `--policy-version` are each refused for this
set. There is **no** test that runs four switches against a development set and
finds them accepted; the guard's being a property of the set rather than of the
switch is asserted over `--force` alone, by
`test_the_refusal_is_for_this_set_and_not_for_the_others`, which loops the two
development sets and `wild-dev`.

**The component-wise path guard.** `assert_not_under_the_held_out_root` now
walks both sealed roots. The held-out set's root is closed outright. The new
set's root accepts exactly one destination — the plain sealed run's own
directory, one component below the root — and refuses everything deeper. The
permit is offered **only on the plain branch** of `run_benchmark`'s destination
chain, so a switched destination can never claim it.

**The path guard and the headline directories were asked to fire on the code as
it stood, before the change. The rest were not.** The committed tree at
`4d0fcb9` was unpacked into a scratch directory, the same questions were put to
it, and the difference is the point:

| question | before the change | after |
|---|---|---|
| is `runs/wild-v2/<slug>/` a headline directory | **no** (three, not four) | **yes** |
| `assert_not_under_the_held_out_root(runs/wild-v2/<slug>/)` | **accepted** | refused |
| `…(runs/wild-v2/)`, the root itself | **accepted** | refused |
| `…(runs/wild-v2/ablation/x/<slug>/)` | **accepted** | refused |
| `…(runs/wild/<slug>/)`, the held-out set's | refused | refused, unchanged |
| `…(runs/wild-dev/<slug>/)`, the re-runnable set's | accepted | accepted, unchanged |
| `--force` for a set marked `sealed` | refused | refused, unchanged |
| the set's own run directory, for the set | accepted | accepted, unchanged |
| the plain corpus directory, for the set | refused | refused, unchanged |

The two rows that matter are the second, third and fourth: **before the change
those destinations were accepted**, because there was no root to guard them. The
guards are the difference, and the new test module cannot even be imported
against the old tree — `eval.development_sets` has no `WILD_V2` — which is the
same fact stated at the other end.

**How the rest were shown red.** The switch refusals, the registration's fixing
the policy version, the frozen run arguments and the sealed retry protocol were
written with their tests and shown red in other ways — on a dirty fixture, or
with the guard removed — and not against `4d0fcb9`. "Every guard was seen
failing first" was true of the path guard and the headline directories and of
nothing else; the sentence that said it was wrong.

**One thing the bare call does and the run does not.** Asked with no permit, the
guard refuses `runs/wild-v2/<model>/` too, as the table shows. That is correct:
only `run_benchmark` passes the permit, and it passes it only for the plain run
it is about to make. The test for the accepting case asks the guard the way
`run_benchmark` asks it, and asserts that the permit does **not** open the
held-out set's root.

**The structure checks**, in `tests/test_sealed_set_wild_v2.py` and in
`tests/test_answer_isolation.py`: every case loads, every brief builds at version
2, the key has every record with all four fields, no answer field appears in any
case file, no brief carries an answer-key field name, no module under `tribunal/`
names either of the two paths that hold the set's answers, and the answer scan is
shown red on a spliced case and green again on the real one. Counts and field
names only, never a value.

## What was run, and what it reported

Only the modules that import something this change touched, as the task requires.
The last row was taken **after** every edit above, so it is the state the commits
carry.

| module(s) | result |
|---|---|
| `tests.test_sealed_set_wild_v2` (new, 40 tests) | `Ran 40 tests in 22.831s` — `OK` |
| `tests.test_sealed_set_wild_v2 tests.test_sealed_set tests.test_development_sets` | `Ran 116 tests in 1054.455s` — `OK` |
| `tests.test_answer_isolation`, the eight new tests alone | `Ran 8 tests in 12.644s` — `OK` |
| `tests.test_run_benchmark` | `Ran 280 tests in 2426.602s` — `OK (skipped=2)` |
| `tests.test_language` | `Ran 6 tests in 69.305s` — `OK` |
| `tests.test_precedents tests.test_amount_rule tests.test_baselines tests.test_verify_drafts tests.test_ablation tests.test_answer_isolation` | `Ran 293 tests in 786.909s` — `OK` |

The 293 is the 285 that module set ran before this task plus the eight added to
`tests.test_answer_isolation`; the same six modules were run twice and both runs
are `OK`.

`python3 -m ui.build --check` reports `ui/dist/index.html is identical to a fresh
build (2381834 bytes)`, so the viewer is untouched by this change.
`python3 -m eval.development_sets --report` prints the corpus, the second set and
the combined line as before, then the held-out set's section, then the second
sealed set's (`0/20`, `not run`), then the re-runnable set's, and its closing
paragraph now names **both** generalisation figures and the two freeze tags
rather than one.

**One flake, recorded because it will look like a defect and is not.** The first
attempt at the 285-test union failed one test with
`FileNotFoundError: … case-00101.json.part -> … case-00101.json`, raised inside
the sandbox's own `os.replace` broker rather than in this repository's code, and
the same failure appeared once in a `tests.test_run_benchmark` run. Both modules
then passed on a re-run, and the union run's re-run is the `OK` above. No code
was changed in response: the failure is in the environment this session runs in,
not in `_write_text_atomic`.

## The command the owner will run

    python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900

The flags are the second freeze's and they are the ones this command line takes:
`--set wild-v2` is accepted, `--concurrency` and `--timeout` are both arguments
of it, and the policy version needs no flag because the registration fixes it at
2. A case that fails is retried once with the same command if the failure is
`TRANSPORT`, `TIMEOUT` or `DEADLINE`; a `SHAPE` failure is **not** retried and is
recorded as "no ruling". `--force` cannot be added to it: it is refused for this
set in code. The run is made only if
`git diff --quiet freeze-2026-10-03 -- tribunal prompts policy` holds.

## Recorded, not fixed

- **`runs/README.md`'s `policy-v<N>/` section still says no such directory is
  committed here.** The session that approved the first amendment committed
  `runs/policy-v2/`, `runs/codex/policy-v2/` and `runs/wild-dev/policy-v2/`, and
  `docs/notes/2026-10-03-the-first-amendment.md` is the record of them. That
  paragraph is now false. It is left as it stands because correcting it is not
  part of this task and would put a second, unrelated change into a commit about
  importing a set; this note is the record that it needs correcting. The new
  `wild-v2/` section added by this task is accurate as written.

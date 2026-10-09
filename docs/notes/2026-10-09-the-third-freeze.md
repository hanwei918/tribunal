# The third freeze — the tag `freeze-2026-10-09`, before the sealed set `sealed-v1` enters the repository

**2026-10-09. This sheet makes no model call.** Everything below is read out of
the repository; the sealed run it prepares for is made afterwards, once, by the
owner, outside this session's sandbox. The archive `sealed-v1` is imported only
after the tag below is pushed.

**This note changes nothing in `tribunal/`, `prompts/` or `policy/`.** Those
trees are what the freeze fixes, and the note is a record of their digests and of
the configuration the run is made with.

## What is frozen

The `tribunal/`, `prompts/` and `policy/` trees, at the tag
`freeze-2026-10-09`. `policy/` includes the base-3 amendments
`policy/v3/amendments/0001-pol-ns-11.json`, `0002-pol-rd-14.json` and
`0003-pol-ns-12.json`, so the policy version at the tag is **6**.

The owner makes the sealed run only if

```
git diff --stat freeze-2026-10-09 HEAD -- tribunal prompts policy
```

prints nothing — that is, only if nothing under those three trees has moved
since the tag. The same condition in the form the earlier freezes state it is
`git diff --quiet freeze-2026-10-09 -- tribunal prompts policy`, which exits `0`.

### The tree digests

One digest per tree, and the git tree object each names, at the tag. The digest
is `sha256` over the tree's tracked files, sorted by path, each written as
`<path>\0<sha256 of the file>` and the rows joined with newlines — a digest of
the tree's **contents**, not of a listing.

| tree | files | git tree object | sha256 of the contents |
|---|---|---|---|
| `tribunal/` | 15 | `65059ad1c0ed4913bdb211e024f2463a0df609ec` | `e10e3098b6b72e8d0d5cf5dca64eb3b9cc7c188db6229468cd549b77596da142` |
| `prompts/` | 8 | `d637c2fe22bdfb9b6656b8d4d408498dc7c676b0` | `5b51ae4cf919d4680ac9349f2b83e27a469ceb13f374b7941b106d9b818f7fd5` |
| `policy/` | 18 | `ae607e5b7a48945211e2dbd1894b43859794a72f` | `533615900f8df6358513b5e7978fc13ac53b45cce40ac9b7b41519f7a455be4e` |

### The digests of every frozen file

The three trees, file by file, as committed at the tag. A file rewritten with
the same name is a different file, so the digests are pinned rather than the
listing.

| file | sha256 |
|---|---|
| `tribunal/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tribunal/__init__.py` | `eb16429790e7fdd8a795093a926cca1769191b50ad341caa3d7b8abf6834d413` |
| `tribunal/brief.py` | `3cec98b39f7c8e439ac3f119d1dfde7767ec9ab7aab6d95c929a402ee27ca960` |
| `tribunal/events.py` | `5ec53c303fd44f97a61af091c2f65add34f32a630ad06aa12998f03fecb1ae05` |
| `tribunal/facts.py` | `9ab0509f117ec8b8cf48b91de1db16ead39c21129edfacb49f9f3670ed334e9d` |
| `tribunal/llm.py` | `0e5230d62acaca96968f69984529d87c14d6c325272df9cd321addff1abc6d9a` |
| `tribunal/loader.py` | `1236d93ed82a0d04dd7e661602be7fd8e45d2ee2b36ddf2245b29469bdf53a50` |
| `tribunal/model.py` | `10933dd7951cc2933f7810f5b079177ecd490fee120bc54cb3d1f73d9ea76d42` |
| `tribunal/money.py` | `b861824979ebc6639b094205c650107a583796665ea98cb22fd509991805e41f` |
| `tribunal/pipeline.py` | `bf2ef11fbe8884aacf710c877b3d53c53b150c3d753c0c017d02a7916a876276` |
| `tribunal/policy_versions.py` | `ece8a1c000707c039d30983a7da6c2a467f220872bcd58c44f8e04571e6e7924` |
| `tribunal/precedents.py` | `67cc4a245aab851dcb0c6a052fcb9640a62fdffe6423df96255b02ac1c1eeb3e` |
| `tribunal/prepass.py` | `e1d69d0598a63e855648cd39deb34f6d70f412140ed939667669c09df722fbc6` |
| `tribunal/referee.py` | `70adb047cc7ef9675cca6b318c1dc95bcb45c0fe75440cc7daadab8d8c43efc2` |
| `tribunal/transcript.py` | `ba0d42aa5d01e575e8bc36971360e4b32830b5fdceedec840d95fa7982738d32` |
| `prompts/v1/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `prompts/v1/README.md` | `268cb9370de0c5cd8e12b2d6c4d0b3c3da59c248b053f9fef987180de8472628` |
| `prompts/v1/advocate.system.md` | `15cd5aadb90794f86c8f214afd42e4f9b616a2112ff583e6beb4693bbe352570` |
| `prompts/v1/judge.system.md` | `73961ae5d750c8e4ecbb9feb1ab456ae6e3994c6c4600ccdd008d2bcf3db86a9` |
| `prompts/v1/policy_drafter.system.md` | `ba72ff0607745f80d7e43325d922b5fe33d460e136d247921853edb6dafa3093` |
| `prompts/v1/stance.driver.md` | `7e0cb843437408155e75ac41fbcbebbfb3650dc742d6828465cc2d718610cb22` |
| `prompts/v1/stance.rider.md` | `4b626f29ededa14526d766286565dafdf22933763db322bec6a024a8a20444d6` |
| `prompts/v1/verifier.system.md` | `08d159772c2b4c0d63a273780c9f86a80c9e9aa17fb60e7030387a92ad4fc6f9` |
| `policy/amendments/0001-pol-rd-13.json` | `72ceb95957e72c4c10960ffd79ddf6a9c13ed1d97059b1bfb21f47fa4f3ae855` |
| `policy/amendments/README.md` | `e5a41d5ea7b48571df115280eab81171ac32e328adf63502919c7740ff82c85e` |
| `policy/general.json` | `12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf` |
| `policy/no_show.json` | `7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf` |
| `policy/proposals/0001-pol-rd-13.json` | `053fb31087efe9492c01f613ce8e867bf2ea16c07fb37a455d1120d9d47dbe49` |
| `policy/proposals/0001-pol-rd-13.transcript.json` | `892d833b52e0fc6f223d8cb98fb1f4f321299ccf31ca897df6fd455d6463be99` |
| `policy/proposals/README.md` | `b15712746a52f11060715559748b5171fe6b9afd94309327a8319292232fd715` |
| `policy/route_deviation.json` | `628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d` |
| `policy/v3/CHANGES.md` | `d50da28ba43377f5dadd06613be0e23f31711d79ff3a535d1c3189b029988f95` |
| `policy/v3/amendments/0001-pol-ns-11.json` | `0d24461e9a0fe3cc27a16dc78ffb7daa9cc36c05f8e233c0e272e2a168e8f6de` |
| `policy/v3/amendments/0002-pol-rd-14.json` | `e254b5f837423e0ee7ee6beec7bb2661fc98e0442c694dc8cc9b4f81c9121703` |
| `policy/v3/amendments/0003-pol-ns-12.json` | `9fa988960d049a67e9bdbdbbaa822cb246bb2bc0e806e1b865f730e25852d582` |
| `policy/v3/general.json` | `52248998cce5133abf8aa22428cf4eab089ad9cccbfa3c1cc9da76e670be9d2a` |
| `policy/v3/no_show.json` | `bef9c2bb217ea1f78266d600291a2b7b21e54825bfbbe67142f8d4054bc668bb` |
| `policy/v3/proposals/0001-pol-ns-11.json` | `27ffb0758cca510e9c9e27ed4b5581df166c8890a00bd9e7cdca77a4cf4a4be3` |
| `policy/v3/proposals/0002-pol-rd-14.json` | `c19e94ab65c4713dc04e4a8b63ac2756ae1896b12d237b32c155efd2d29c031e` |
| `policy/v3/proposals/0003-pol-ns-12.json` | `79e597c05b69e6f213bed011df740b3819e4706899feacb76ac995cbcf61d97f` |
| `policy/v3/route_deviation.json` | `e49e72ce68cadb7af32ea20426d2693eb7e846767e82694bc2074f688fb5f7f8` |

`prompts/v1/` also holds `policy_drafter.system.md` and `verifier.system.md`;
those two are not part of the frozen judge path (the drafter belongs to the
policy-gap loop and the verifier is off), and the tag freezes the whole tree
regardless.

## What version 6 is

Version 6 is **base 3 plus the three amendments on base 3**. Base 3 is Ji
Guofang's platform-aligned policy at `policy/v3/`; the amendments are
`0001-pol-ns-11.json` (`POL-NS-11`), `0002-pol-rd-14.json` (`POL-RD-14`) and
`0003-pol-ns-12.json` (`POL-NS-12`). The no-show policy therefore carries **12
clauses** and its `version` string reads `3.0.0+amendment.0003`; the
route-deviation file is untouched by the no-show clauses and still reads
`3.0.0+amendment.0002`. Base 1 owns versions 1 and 2 and is byte-identical to
`b124e5f`; `current_version` is still 2, `highest_available_version` is 6, and
the sets written for base 3 (`dev-v2`, `dev-v2-ext`, `ryde-v3`) default to
version 6.

## The configuration

| setting | value |
|---|---|
| model | `deepseek/deepseek-flash`, the runtime model in `tribunal/model.py` |
| policy version | 6, fixed by the set's registration (see below) |
| judge votes | 4 |
| verifier | off |
| precedents | off |
| ablation | none |
| amount rule | the default `published` rule |
| timeout | `--timeout 900` |
| concurrency | `--concurrency 2` |
| parallel calls | `--parallel-calls` |
| prompts directory | the default, `prompts/v1` |
| case deadline | the default, `pipeline.DEFAULT_CASE_DEADLINE_SECONDS` = 2400 s |
| token budget | the default, none |

The judge is asked four times per case — three sampled drafts and one
position-swapped — and the four graded fields are voted together at a quorum of
three. Every one of the switches that would change what the agents are given is
off, so the run measures the pipeline and the brief as committed.

`--parallel-calls` asks the calls that depend on nothing at the same time and
leaves every request byte-identical, so it changes nothing the run measures; the
registration does not pin it.

## The protocol, stated before the run

- The run is **one command**.
- **Transient failures are retried once, with the same command.** These are
  `TRANSPORT`, `TIMEOUT`, `DEADLINE` and `INTERRUPTED`.
- **A `SHAPE` failure is not retried.** This is a case in which every judge
  draft was rejected. It is recorded as "no ruling", because retrying it only
  re-samples the judge until a draft passes.
- A case that has a result is never re-run, and `--force` is refused in code.
- The results are committed exactly as produced and graded once.
- The key is never changed after the run. A disagreement with the key is
  recorded, not corrected.

## What the run reports

- Four-field exact over the cases that produced a ruling, and over all cases,
  counting "no ruling" as a miss.
- The ruling alone.
- The score per category.
- Escalation precision and recall.

This is the submission's **third generalisation figure**. It is reported beside
every other figure and never summed with any of them.

## What changed since `freeze-2026-10-03`, and why

- **The four fixes the first development run found** (`dac357f`): a
  `waypoint_approach` block, an `advisory_area` block, `ESCALATE` where no draft
  is valid, and the version gating that keeps versions 1 and 2 byte-identical.
  — `docs/notes/2026-10-08-policy-version-3.md`.
- **A route-deviation `GPS_GAP` is graded by `POL-RD-07`'s own limbs**
  (`b124e5e`), and the key owner's revised development sets were installed.
  — `docs/notes/2026-10-09-policy-version-4.md`, *Part 5*.
- **`POL-NS-11` as version 4** (`7c3cf93`), the first amendment on base 3, and
  the waiting-time fee as a published figure.
  — `docs/notes/2026-10-09-policy-version-4.md`, *Part 6*.
- **The `POL-GEN-08(1)` scope gate, `POL-RD-14` as version 5, the revised keys,
  and the base-3 sets at later versions** (`541ac31`).
  — `docs/notes/2026-10-09-policy-version-4.md`, *Part 7*.
- **`POL-NS-12` as version 6 and the `POL-GEN-08(4)` registration mask**
  (`3692360`), and **`POL-NS-12` restated in general terms** (`9ca7313`) at the
  policy owner's request.
  — `docs/notes/2026-10-09-policy-version-4.md`, *Part 8*.

The two earlier freezes, for comparison:
`docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` and
`docs/notes/2026-10-03-the-second-freeze.md`.

**Every development figure measured since `freeze-2026-10-03` is in-sample, and
none is the generalisation figure.** The generalisation figures are the three
sealed runs, each made once from its own freeze.

## What the owner recorded on receipt, before anyone opened the archive

- Path: `~/Desktop/tribunal-sealed-v1.zip`
- Size: 194,719 bytes
- Entries: 42
- sha256: `d6938a52edb450aeb068758d20ab42d545456da0d2d6ade46cdaede04f94971b`

The archive is verified against that digest before it is imported, and the
import is Part 2 of this sheet. The set's own provenance is recorded in the
import note, `docs/notes/2026-10-09-sealed-v1-imported.md`, from what the archive
itself states.

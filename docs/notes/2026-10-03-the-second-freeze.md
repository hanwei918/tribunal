# The second freeze — the tag `freeze-2026-10-03`, before the sealed set `wild-v2` enters the repository

**2026-10-03. This sheet makes no model call.** Everything below is read out of
the repository; the sealed run it prepares for is made afterwards, once, by the
owner, outside this session's sandbox. The archive `wild-v2` is imported only
after the tag below is pushed.

## What is frozen

The `tribunal/`, `prompts/` and `policy/` trees, at the tag
`freeze-2026-10-03`. `policy/` includes `policy/amendments/0001-pol-rd-13.json`,
so the policy version at the tag is **2**.

The owner makes the sealed run only if

```
git diff --quiet freeze-2026-10-03 -- tribunal prompts policy
```

holds — that is, only if nothing under those three trees has moved since the
tag.

### The digests

| file | sha256 |
|---|---|
| `prompts/v1/judge.system.md` | `73961ae5d750c8e4ecbb9feb1ab456ae6e3994c6c4600ccdd008d2bcf3db86a9` |
| `prompts/v1/advocate.system.md` | `15cd5aadb90794f86c8f214afd42e4f9b616a2112ff583e6beb4693bbe352570` |
| `prompts/v1/stance.rider.md` | `4b626f29ededa14526d766286565dafdf22933763db322bec6a024a8a20444d6` |
| `prompts/v1/stance.driver.md` | `7e0cb843437408155e75ac41fbcbebbfb3650dc742d6828465cc2d718610cb22` |
| `policy/general.json` | `12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf` |
| `policy/no_show.json` | `7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf` |
| `policy/route_deviation.json` | `628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d` |
| `policy/amendments/0001-pol-rd-13.json` | `72ceb95957e72c4c10960ffd79ddf6a9c13ed1d97059b1bfb21f47fa4f3ae855` |

## The configuration

| setting | value |
|---|---|
| model | `deepseek/deepseek-flash` |
| policy version | 2, fixed by the set's registration (see 2b) |
| judge votes | 4 |
| verifier | off |
| precedents | off |
| ablation | none |
| amount rule | the default `published` rule |
| timeout | `--timeout 900` |
| concurrency | `--concurrency 2` |
| case deadline | the default |

## The protocol, stated before the run

- The run is **one command**.
- **Transient failures are retried once, with the same command.** These are
  `TRANSPORT`, `TIMEOUT` and `DEADLINE`.
- **A `SHAPE` failure is not retried.** This is a case in which every judge
  draft was rejected. It is recorded as "no ruling", because retrying it only
  re-samples the judge until a draft passes. This is the lesson of `wild-v1`'s
  517 and 533, and it is fixed now, before the run, rather than decided after
  it.
- A case that has a result is never re-run, and `--force` is refused in code.
- The results are committed exactly as produced and graded once.
- The key is never changed. A disagreement with the key is recorded, not
  corrected.

## What the run reports

- Four-field exact over the cases that produced a ruling, and over all cases,
  counting "no ruling" as a miss.
- The ruling alone.
- The score per category.
- Escalation precision and recall.

This is the submission's **generalisation figure**. It is reported beside every
other figure and never summed with any of them.

## Known defects, carried into the run as they stand

1. A judge may refund an ERP line under `POL-RD-09` where no remedy applies
   (`wild-v1` 523).
2. A judge may recompute an airport surcharge at a rate other than the one
   charged (`wild-v1` 517).
3. The judge prompt names the referee's output `referee_ledger` and
   `referee_flags`, while the message carries `referee.ledger` and
   `referee.flags`.

## What changed since `freeze-2026-09-30`, and why

- **`wild-v1` was turned into development data.** The held-out set was run once
  from `freeze-2026-09-30`, and its answers may now be read; the same 64 cases
  were registered a second time as `wild-dev`, which may be run again, into
  `runs/wild-dev/<model-slug>/`. The single run under `runs/wild/` is never
  written again.
  - `docs/notes/2026-10-01-wild-dev-registered.md` — the registration.
  - `docs/notes/2026-10-01-wild-runs-read-as-wild.md` — reading a run under
    `runs/wild/` as the held-out set.
  - `docs/notes/2026-10-01-nothing-writes-under-runs-wild.md` — closing every
    path into `runs/wild/`.
- **`POL-RD-13` was approved through the policy-gap loop.** The loop closed two
  held-out cases, reported, drafted one clause for cluster `C4`, and the owner
  approved it, which is what makes the repository's policy version 2.
  - `docs/notes/2026-10-03-the-first-amendment.md`.
- **The `POL-RD-11` upfront remedy was added to the money block from version 2
  on.** An `UPFRONT_QUOTE` fare with a non-null quote now publishes
  `pol_rd_11_remedy`; version 1 stays byte-identical.
  - `docs/notes/2026-10-01-upfront-remedy-published.md`.

The first freeze, for comparison: `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md`.

**Every development figure measured since `freeze-2026-09-30` is in-sample, and
none is the generalisation figure.** The generalisation figure is the one the
sealed run below produces.

## Provenance of `wild-v2`, as the owner states it on 2026-10-03

- **OpenAI Codex, operated by the owner, produced it from a written request.**
  The request asked for about 24 cases built from the 22 seeds `wild-v1` did not
  use, in `wild-v1`'s format, with the answers in a separate file. It asked the
  author not to aim at the cases `wild-v1` exposed and not to read the
  repository's notes on that run.
- **The owner has not opened the archive.**
- **Whether Codex could read this repository while it worked is not recorded.**

## What the owner recorded on receipt, before anyone opened the archive

- Path: `~/Desktop/tribunal-wild-v2-sealed-20261001.zip`
- Size: 219,666 bytes
- Modification time: 2026-10-01 10:49:47
- Entries: 45
- sha256: `13d90441b0af47b69168fef96034da5e190b835c9d4a4cc2e337d776003bde41`,
  which matches the `.zip.sha256` file shipped beside it.

The archive is verified against that digest before it is imported, and the
import is Part 2 of this sheet.

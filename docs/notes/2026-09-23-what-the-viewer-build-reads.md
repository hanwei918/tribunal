# What the viewer build reads, and the defect that showed why it matters

2026-09-23. This note records a defect found by cloning the repository, the fix, and
the audit that followed it. It exists because the finding was invisible in the author's
own checkout and would have shipped.

## The defect

A fresh clone of the repository ran the suite and **two tests went red** that pass in
the checkout the artefact was built in:

```
FAIL: test_the_committed_page_equals_a_fresh_build
      committed 1 559 646 bytes, a fresh build in the clone 1 559 681
FAIL: test_no_absolute_path_is_published
      an absolute path reached the page:
      /Users/<name>/Desktop/Tribunal/prompts/v1
```

The second is the leak that test exists to catch, and it is the same value: a
structural diff of the two embedded data blocks showed **exactly one** differing
field, `/provenance/prompts_directory`.

The cause was one fallback in `ui/build.py`:

```python
try:
    return Path(value).resolve().relative_to(PROJECT_ROOT).as_posix()
except ValueError:
    return value          # the absolute path, published verbatim
```

The committed run records its prompts directory as an absolute path from the machine
that produced it. In the checkout that built the page that path sits under
`PROJECT_ROOT`, so it was relativised to `prompts/v1`. In **any other checkout** it does
not, so the absolute path was published instead.

Two consequences, and the second is the one that matters:

1. **The committed artefact reproduced in exactly one directory** — the one it was
   built in. A stored artefact that cannot be reproduced from the code by anybody else
   is the failure this repository's artefact-versus-build test exists to prevent, and
   the test could not see it, because it only ever ran where the artefact was built.
2. **A page built anywhere else published the author's home directory**, into an
   artefact destined to be published.

## The fix

`ui/build._repository_relative`:

- a path under `PROJECT_ROOT` is relativised directly;
- a path that is not, but whose **trailing components** name a directory this
  repository has (`prompts/v1`, `runs/deepseek-deepseek-flash`), is reported as this
  repository names it;
- anything else is **dropped**, not published. A path from another machine is not this
  repository's to publish.

The unreachable `or str(run_dir)` fallback on `run_directory` was removed as the same
leak in the same function: it would have published an absolute path whenever
relativisation failed. It was unreachable, which is exactly why it would have gone
unnoticed until the day it was not.

**The committed artefact needed no rebuild.** It already held `prompts/v1`; the fix
changes what *other* checkouts produce, not what this one does.

## What the build reads, audited

Because the lesson is "the output must be a function of the repository", the sources of
machine-dependence in the packages were audited:

| Module | Reads the clock? | Verdict |
|---|---|---|
| `ui/build.py` | no | reads no clock, no environment, no working directory. Its inputs are the repository's own files. |
| `eval/run_benchmark.py` | yes, 3 sites | all in **run records** (`started_at`, `ended_at`, `recorded_at`), where a timestamp is the correct thing to record; injectable except the per-case `recorded_at` |
| `tribunal/llm.py` | yes | the timestamp of a call that happened — correct, and recorded as such |
| `tribunal/transcript.py` | yes | the transcript's own clock, injectable |

The defect was **not** a clock or an environment read. It was a value read from a file —
`run.json`'s absolute `prompts_dir` — that happened to be machine-specific. A guard
against clock reads would not have caught it. What catches it is the test that the page
does not depend on where the run was made.

## The guard

`tests/test_ui_build.py` carries five tests for this, the last of them end to end: the
run is copied to a temporary `<tmp>/runs/deepseek-deepseek-flash` — the layout a fresh
clone has — its recorded prompts path is moved somewhere that does not exist on this
machine, and the page built from that copy must be **byte-identical** to the committed
one. That is the clone's failure reproduced as a test rather than described in a
comment.

## Known remaining instance, left for a decision

The committed run provenance still carries real absolute paths — `runs/*/run.json` and
`invocations.json` hold `"path": "/Users/<name>/Desktop/Tribunal/runs/..."` — as do four
documents that state the project root. They were left alone deliberately:

- they are the committed evidence the run's numbers rest on, and `runs/README.md`
  explains that their bytes are what is committed;
- the viewer's brief digests are computed over them, so editing them changes what the
  committed run says;
- git authorship already discloses the same name in every commit, so it is not an
  incremental exposure.

Fixing it forward — making `run_benchmark` record repository-relative paths, so the
next run does not publish a home directory — is a change to a documented record shape
and is a decision rather than a defect repair.

## The transferable lesson

**Every test passed in the directory the artefact was built in, so nothing there could
have shown this.** A build that reads the machine rather than the repository is
invisible until somebody else runs it, and the only way to see it is to be that somebody
else. A fresh-clone suite run is not ceremony; it is the only check that covers this
class.

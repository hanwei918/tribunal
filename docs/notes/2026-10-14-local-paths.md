# The run records no longer carry the absolute path of the checkout a run was launched from

**2026-10-14.** Most of the runs under `runs/` were launched from a temporary
checkout of this repository under the system's temporary folder, and the runner
wrote that checkout's absolute path into the run's own records. The path is
machine-specific, it names a personal folder, and it means nothing to anyone
else, so every occurrence of it is replaced by the placeholder `<checkout>` --
the root of the checkout the run was launched from. **Nothing a run decided,
graded or recorded about a case changed.**

## What changed

**The path strings.** In 35 files under `runs/`, every match of the launch path
was replaced by `<checkout>`, at the byte level -- bytes read, bytes
substituted, bytes written, with no file parsed and re-serialised: **65
replacements**. They sit in three keys of the records and in the console logs:
`run_dir` (18), the `directory` block's `path` (18) and `prompts_dir` (16) in
`run.json` and `invocations.json`, and 13 lines of the console logs. No file
under `runs/` contains `/private/tmp/` any more. Paths under the owner's home
folder (`/Users/...`) are a different shape, were never in scope and are left as
they are -- the corpus run's own `run_dir` and `directory.path` still name the
folder it was launched from -- and nothing outside `runs/` was read or written
for this.

**The four manifests.** Four manifests list files the replacement changed, and
the `sha256` and `size` of exactly those entries were updated to the files' new
bytes, in place, as text -- the old digest string replaced by the new one and
the old size by the new size inside that entry, so each manifest keeps its own
formatting:

| manifest | entries updated |
|---|---|
| `runs/policy-v6-manifest.json` | 11 |
| `runs/sealed-v2-manifest.json` | 2 |
| `runs/sealed-v3-manifest.json` | 2 |
| `runs/sealed-v4-manifest.json` | 2 |

No other entry, key or line of any of the four changed.
`runs/sealed-v1-manifest.json` and `runs/func-sets-manifest.json` list none of
the changed files and did not move.

## Why

The path is machine-specific: it names a directory that exists on the machine
that launched the run and nowhere else, and it names a personal folder besides.
It tells a reader nothing about the run, and **this repository is about to be
published**.

## What did not change

No case file, transcript, event log, `calls.json`, ruling, grade, figure or
other manifest entry changed, and **no run was re-run**. The replacement moves
one string inside files that record provenance; the bytes a run wrote about a
case, and the bytes a grader read back out of them, are the same bytes.

## How to check it

```
git diff --stat ff59f95 HEAD -- runs
```

prints **39 files changed** -- the 35 run records and the 4 manifests -- and

```
git diff ff59f95 HEAD -- runs
```

shows only the replaced path strings and the four manifests' changed `sha256`
and `size` values: no other byte of any of those files differs.

`tests/test_run_records_local_paths.py` holds both halves of this as a check
that runs with the suite: no file `git ls-files runs` lists contains
`/private/tmp/`, and every entry of every `runs/*manifest*.json` matches its
file's digest and size.

The version-8 runs committed later the same day -- `ryde-v8` and `dev-v8` --
had the same replacement applied when they were committed: 3 files and 6
replacements in each, 6 files and 12 replacements in all, and no file under
`runs/` holds a temporary-folder path.

# The policy versions

A **policy version** is an integer. Version 1 is the three files in `policy/`
exactly as committed — `general.json`, `no_show.json` and
`route_deviation.json` — and it is what every run before this task used. Version
N is those three files with the amendments `0001` through `N-1` applied. The
current version is 1 plus the number of files in `policy/amendments/`, and
`policy_versions.current_version()` is the one place that number is computed.

That is the whole arithmetic. Everything below is about the two ways it could
have been got wrong: a version that is not 1 quietly changing a brief it should
not have touched, and an amendment quietly doing something other than adding a
clause.

## An amendment adds one clause, and that is enforced rather than asked for

`brief.py` parses the prose of several existing clauses. `POL-RD-01`'s excess
threshold, `POL-RD-09(4)`'s ERP-gantry rule and `POL-NS-06(i)`'s no-show
threshold are all read out of `clause["rule"]` by regex and **raise** if the
sentence is not there. An amendment that rewrote one of those clauses would
change what a brief means while leaving every clause id where it was, and no
diff of the ids would show it. So an amendment is not *asked* not to do that. It
is given nowhere to say it.

A file under `policy/amendments/` carries exactly one `clause` and exactly the
provenance fields `base_version`, `proposal_file`, `proposal_sha256`,
`report_file`, `report_sha256`, `cluster_id`, `cases`, `approved_by` and
`approved_at`. The key set is compared for equality, not for containment, so an
`edits` key or a `removes` key is a refusal and not an ignored extra. The clause
itself carries exactly the eight fields `id`, `title`, `category`, `rule`,
`requires`, `licenses`, `favours` and `notes` — so a ninth, a `replaces`, is
refused too. There is therefore no document that could express an edit or a
removal, which is a stronger statement than a rule saying not to write one.

The id is checked against `^POL-(NS|RD|GEN)-\d{2}$`. The prefix decides which
file the clause joins — `GEN` to `general.json`, `NS` to `no_show.json`, `RD` to
`route_deviation.json` — and the clause's own `category` must agree with that
file's. And the number must be the **next free one** for its prefix: `POL-RD-13`
while `POL-RD-12` is the highest route-deviation clause, and `POL-RD-01` refused
with a message that says the next free number rather than only that this one is
taken. That check is made in `apply_amendments` and not in `load_amendment`,
because "the next free one" depends on the amendments before it: an amendment
read on its own cannot know what its predecessors already took.

The prefix-to-category map is a constant, `PREFIX_CATEGORY`, rather than a read
of the target file, so checking one amendment does not depend on the working
tree. A test pins it against the three real files, so the constant cannot drift
from them.

The set of amendments on disk is checked as a set. A file not named
`NNNN-<slug>.json`, a number used twice, and a sequence with a hole in it are
each refused. The hole matters most: "version N applies `0001` through `N-1`"
only means something if the numbers below N are exactly the ones on disk, and a
hole would make the current version name amendments that do not exist.
`README.md` is skipped rather than refused, because the directory ships with
one.

An amendment to a policy the brief in hand does not carry is **skipped, not
refused**. A no-show clause has no business in a route-deviation brief, and one
run briefs cases of both categories.

## Threading the version

`loader.load_policies(category, policy_version=1)` is where the version enters.
Version 1 returns the two files as they were read, **without a copy and without
reading `policy/amendments/` at all**. That is not an optimisation: it is what
makes a broken amendment unable to stop the version-1 measurement, and it is
what makes version 1 byte-identical by construction rather than by inspection.

`brief.build_brief_for_case(..., policy_version=1)` takes it and passes it
straight to the loader. `brief.build_brief` does **not** take it, as the queue
requires: that entry point briefs the corpus, its signature is pinned by a test,
and the corpus is measured at version 1.

From there it travels the way the ablation and the precedent block travel.
`pipeline.run_case` and `pipeline.run_loaded_case` take it and pass it to the
single brief builder. `run_benchmark.current_brief_sha256` takes it, because a
run at version N was given a brief built from the amended policy and its
staleness check has to rebuild *that* brief. `brief_digest_for` carries it
beside the ablation, and `BriefStaleness` holds it — its brief-digest memo is
keyed by the case **and the version together**, because a digest is of a brief
built at one version and serving it to a question asked at another would answer
the wrong question.

`pipeline.replay_verdict` builds a case's brief to compare against the digest a
recorded run holds, so it has to build at **that run's** version.
`ReplaySource` therefore carries `policy_version`, read from the source run's
recorded `configuration` by `run_benchmark.read_replay_source`. Rebuilding at
version 1 would refuse every case of a run that was not.

## Version 1 is byte-identical, and that is measured

The queue's first test is that version 1 rebuilds every one of the 44 recorded
`brief_sha256` values exactly. It does — **29 of 29 corpus and 15 of 15 second
set**, checked against `runs/deepseek-deepseek-flash/` and
`runs/codex/deepseek-deepseek-flash/`, and the check is a test rather than a
one-off. Nothing about a brief moved.

## Where a later version writes

`runs/policy-v<N>/<model>/`, and under the second set's own root
`runs/codex/policy-v<N>/<model>/`. The rule is the one the ablation and the
precedent block already follow: the destination is chosen under a directory of
its own and then **checked in code before anything is written**, so a name that
resolved outside it cannot put such a result where the headline figure lives.
The check is against *this version's* directory rather than against `policy-v*`,
so a version-2 run cannot land in version 3's.

`--policy-version N` is on both runners. It is refused together with `--ablate`,
`--precedents`, `--report`, `--compare`, `--replay-advocates`, `--replay-check`,
`--verify-recorded-drafts` and `--external` — every mode that reads a run
produced at version 1 or that reuses a recorded run's advocates. Version 1 is
the default, so naming it changes nothing and does not count as one of the
switches: `--policy-version 1 --ablate clause-notes` is refused by the ablation's
own rule and not by the mutual exclusion.

A version this repository does not have is refused **before a client exists**,
with a message naming the version the repository is actually at. Without that
check the failure would have been per case, and the staleness check would have
swallowed it into `None` — a run directory full of cases that each failed to
build a brief, which reads as twenty-nine findings rather than one mistake.

The version is recorded in the `configuration` object of `run.json`, of every
`invocations.json` entry and of every case file, and on the `invocation_start`
event only when it is not version 1, so a plain run's event line is the line it
always appended.

## What finishing this task corrected

**`--ablate` and `--precedents` never reached the runner on
`eval.run_benchmark`'s command line.** Both flags were defined, both were
refused in the combinations that cannot be honest, and neither was passed to
`run_benchmark(...)` — the call named `model_id, cases, runs_dir, ...` and
stopped at `verify_drafts`. So

    python3 -m eval.run_benchmark --ablate clause-notes

built **unablated** briefs and wrote them into `runs/<model>/`, which is exactly
the directory `runs/README.md` says an ablated run may never reach, and exactly
what the destination assertion in `run_benchmark()` exists to prevent. The
`--precedents` path was the same. Neither omission had a test: the CLI tests
covered the refusals, and the end-to-end tests drove `development_sets`, which
forwards through `run_set(**kwargs)` and therefore worked.

Both are now named at that call site, beside `policy_version`. That is a change
to two earlier tasks' behaviour, made here because this task's own flag had to
be forwarded at the same line and would otherwise have been the only one of the
three that worked. It is recorded rather than left silent for that reason.

Three smaller corrections, all in this task's own code:

- `--policy-version` needed a refusal for a version above the repository's, or
  the first case of such a run would have been the first report of it.
- `PREFIX_CATEGORY` is a constant with a test pinning it to the three files,
  rather than a disk read inside `load_amendment`, so a check of one amendment
  does not depend on the working tree.
- `assert_policy_v_destination` checks against one version's directory rather
  than against `policy-v*`.

Two corrections in this task's own documentation, found by reading the files
back before committing rather than by a test:

- The `policy-v<N>/` section of `runs/README.md` ended with a paragraph
  duplicated from the `precedents/` section, which named `precedents/` as the
  destination inside the policy-version section. Removed.
- The directory table in the same file had no `policy-v<N>/` row, which rule 1f
  asks every task that creates a directory to add. Added, in the alphabetical
  position the table keeps.

## Nothing globs the policy directory

The queue asked for a grep of `tribunal/`, `eval/`, `ui/` and `tests/`. It was
run, and the result is that **nothing lists `policy/` in a way that would pick
up the two new subdirectories**:

- The only listing anywhere in the policy tree is `policy_versions.py`'s own
  `amendments_dir(root).iterdir()`, which is the deliberate read of
  `policy/amendments/` — it skips `README.md` and refuses a directory.
- `loader.py` names its files: `POLICY_DIR / GENERAL_POLICY_FILE` and
  `POLICY_DIR / CATEGORY_POLICY_FILES[category]`. No glob, no listing.
- Every other mention of `policy/` in the four trees is prose in a docstring or
  a message.

`tests/test_policy_versions.py` encodes this as a test — it scans the four trees
for a `glob`/`rglob`/`iterdir`/`listdir` call on a line that mentions `policy`
and does not go through a subdirectory — so a later glob cannot arrive unnoticed.

## What was run

`tests/test_policy_versions.py` is new: 52 tests. It covers the version
arithmetic, the pinned prefix maps, the three ways an amendment is refused for
what it is rather than for what it says, the destination checks, the
version-keyed staleness memo, and the refusals on both command lines.

The related modules were then run on 3.13.12 — every module that imports one this
task changed, 1042 tests across eleven modules:

    Ran 1042 tests in 1773.747s

    OK (skipped=3)

Three skipped rather than the full suite's four, because this is a subset.
`NoteCouplingTests` (two) and `RunCurrencyTests` (one) are inside it;
`NetworkTests` is not, because it lives in `tests/test_llm.py` and that module
imports nothing this task touched. The lines the log prints after the count are
a test's own printout of three serialised brief sizes, not errors.

The full suite on both interpreters is the owner's, run once outside the
sandbox.

## What is not done

- **No amendment is shipped.** `policy/amendments/` and `policy/proposals/` hold
  their `README.md` and nothing else, so the repository is at version 1 and
  there is no version 2 to run. Every version above 1 is therefore exercised
  through `apply_amendments` against a temporary directory rather than through a
  paid run, and `runs/policy-v<N>/` does not exist.
- **The viewer shows version-1 runs only**, as the queue requires. Nothing in
  the viewer changed.
- **`policy/proposals/README.md` describes a producer that does not exist yet.**
  Task 6 is the policy-gap loop that would write proposals; the README states
  the contract it will have to meet, and nothing reads the directory today.

# The policy-gap loop

The policy is version 1 and it does not decide everything. Nine of the forty-four
recorded cases end in `ESCALATE` — five of the twenty-nine in
`runs/deepseek-deepseek-flash/`, four of the fifteen in
`runs/codex/deepseek-deepseek-flash/` — and an escalation is the system saying
the policy ran out rather than that the case was hard. This task is the loop that
turns that into a proposal a person can accept.

Six commands: `report`, `draft`, `approve`, `reject`, `rerun`, `diff`. Only
`draft` and `rerun` call a model. `report` reads the recorded runs, `approve`
writes `policy/amendments/`, `rerun` re-runs the affected cases at the new
version, and `diff` compares the before and after.

## The trigger is a written-down grammar, and the floor is read

Every undecided case is classified by one of six rows: `no_majority`,
`too_few_valid_drafts`, `too_few_valid_drafts:verifier`, `below_confidence_floor`,
`clause:<id>`, `judge_no_clause`. A transcript with no vote block is a
single-draft file, and it is classified by the last three rows prefixed
`single_draft:` — the vote conditions do not apply to a file that has no vote.

The floor is not a number in this module. `below_confidence_floor` compares the
recorded confidence against `confidence_floor` of the **loaded** policy, the
category's floor first and the general one only as a fallback. A confidence that
was not recorded counts as below the floor, which is the conservative reading: an
absent figure cannot be shown to clear it. Each row has its own test, and the
floor tests pin the category-before-general order and refuse a boolean.

## The signature is about the record, and the noise is dropped

A case's signature is the sorted set of `"<evidence_type>:<issue code>"` pairs
over its artifacts whose `admissibility.status` is `IMPAIRED` or `MISSING`. A
`COMPLETE` artifact contributes nothing — the signature says what is wrong with
the record, not what it holds.

A pair that appears in at least 80 % (`NOISE_SHARE`, a `Decimal`, so the
comparison is exact) of the given runs' cases is dropped from **every** signature,
because a pair that is in almost every case distinguishes none of them. On the two
committed runs the drop is one pair, `TRAFFIC_ADVISORY:MISSING_ARTIFACT`.

The drop is asserted on the parsed tuple and not on a rendered line, and the
boundary is tested at exactly `Decimal("0.8")` so the comparison cannot drift to
a float.

## Two levels of cluster

A cluster forms at `(category, trigger)` and at `(category, trigger, signature)`.
Ids run `C1`, `C2`, … in sorted order beginning with the coarse level, so the
coarse cluster always precedes the fine ones that refine it and two runs of the
same data name the same clusters the same way. A cluster is **flagged** at three
cases or more (`DEFAULT_MIN_CASES`), and a flag is what makes it draftable.

A fine cluster whose signature is **empty** is not emitted. Its cases are exactly
its coarse cluster's, so emitting it would name one set of cases twice under two
ids. That rule is here because the real report broke it: the first run emitted
`C8` identical to `C2` and `C9` identical to `C3`, and the count of clusters read
twelve where there are ten. The report's cluster tables also gained a `set`
column, because without it a bare `210` could not be told from a `9107`.

## Where a human closure comes from

From the **precedent library**, not from a new store. `policy/amendments/README.md`
already names `policy/proposals/` as the place a proposal lives, and task 4's
library already records a human's closure of a case with the clause ids they
rested it on. A cluster needs at least two of them before `draft` will touch it,
so the loop drafts from decisions people made rather than from a single opinion.

## The drafter is given no answer

`draft` hands the model the loaded policy, the cluster's cases, and the human
closures — and nothing else. Each case is its dispute block and, per artifact, the
`evidence_id`, `evidence_type`, `admissibility` and the `derived` facts; the raw
payload is dropped. The assembled input is walked for a forbidden field name
before it leaves, so what the model sees carries no answer field whichever way the
case files were written.

Two things about the case content are load-bearing and were got wrong once:

- The derived facts come from a **brief**, not from a bundle. `loader.build_bundle`
  returns the payload as stored, and the `derived` block is computed by
  `brief.build_brief_for_case`. A test that fed the drafter a bundle found no
  derived block at all, which is the correct answer to the wrong question: the
  real `draft` path builds a brief, and that is what the test now builds.
- The **worked example in the prompt was not valid JSON.** It used adjacent string
  literals to wrap long lines, which is a Python feature and not a JSON one, so the
  four tests that parse the example out of its fence all failed on a
  `JSONDecodeError`. The example is now one line per string and parses.

## `approve` is the only writer, and a proposal is not a clause

`approve` writes `policy/amendments/NNNN-<slug>.json` and re-reads it through
`policy_versions.load_amendment`; an amendment that will not re-read is unlinked
rather than left behind. A draft that fails validation is recorded as
`REJECTED_BY_CODE` beside its transcript and never becomes a proposal at all.

## The one thing the repository decides, and the dry run

A policy version is **global**. `loader.load_policies` reads the repository's own
`policy/amendments/` and takes no root, and the runner checks the version against
that directory before it builds anything. So an amendment found under some other
root names a version no case can be briefed at, and the runner would say so once
per case — twenty-four times for one mistake. `rerun` says it once, naming both
directories.

That guard is asked **only once the run is going ahead**. Without `--yes` nothing
is run and nothing is written, so the plan is printed and the version is left
alone: a person must be able to see what an amendment would run before it is in
the repository. The guard was first written above the dry-run refusal, which made
the plan unreadable for exactly the amendment that most needs reading.

## `diff` is the one command that reads the frozen key, and says so

The answer key is frozen and nothing under `tribunal/` reads it. `diff` is the
exception: its whole job is to say whether the new version decided a case the way
the key says it should, and it prints that it reads the key rather than leaving a
reader to discover it. The totals block is printed twice, once over the affected
cases and once excluding the cluster's own cases, so the in-sample figure is
separated from the rest.

Two defects were found in the first end-to-end `diff`, both in how a row is
decided:

- Rows marked `changed: yes` whose two sides rendered **identically** — 201, 207,
  210 and 213. The referral *prose* had moved while the clause reference it leads
  with had not, and the grader compares referrals by clause reference.
- Rows marked `changed: no` that rendered **differently** — `4.00` against `4.0`.
  `grade.compare_money` treats those as the same money, and the column printed
  them as two different strings.

Both are now impossible by construction. Money is rendered at two decimal places
when it is a two-place number, each referral is rendered as the clause reference
it leads with (the limb kept, and `NO_LEADING_CLAUSE` as a value), and `changed`
is defined as `_render_fields(old) != _render_fields(new)` — the same rendering
the two columns show. A row marked changed therefore always has two sides that
differ, and a row marked unchanged never does.

## What the report found

Over the two committed runs:

- **5 corpus cases undecided** — 110, 112, 207, 210, 213 — and **4 second-set
  cases** — 9108, 9109, 9110, 9115.
- **10 clusters**, of which **2 are flagged** at three cases:
  `C1 NO_SHOW_CHARGE / below_confidence_floor` (210, 213, 9109) and
  `C4 ROUTE_DEVIATION / below_confidence_floor` (110, 112, 9115).
- **1 dropped noise pair**, `TRAFFIC_ADVISORY:MISSING_ARTIFACT`.
- **No case has a human closure yet**, so no cluster can be drafted from. The
  report is committed at `runs/policy-gaps/`; the loop's next step is a person
  closing cases in the library, not a model call.

## What finishing this task corrected

- **The report could not be rebuilt from its own file.** `_report_from_document`
  built the readings and never attached them to a run, so `report.readings` — which
  is derived from the runs — came back empty and `draft` would have seen a cluster
  with no cases in it. The round-trip test found it. A case appears once in each
  cluster that holds it, so the rebuild now reads each case once, lets the fine
  level's signature win, and hangs the readings off the run they came from.
- **The fine-cluster duplication** described above, found by reading the first
  real report rather than by a test.
- **The two `diff` defects** described above.
- **The prompt's worked example was not valid JSON.**
- **The rerun test wrote into `policy/amendments/`.** `policy/amendments/README.md`
  says that directory is written only by a human through `approve`, "not any
  test", and the first version of the end-to-end rerun test wrote a real amendment
  there and unlinked it in a `finally`. That is a real hazard on this machine,
  where a foreground `python -m unittest` can be `SIGTERM`'d: a hard-killed test
  would leave the repository silently at version 2 and change every later brief.
  The test now patches `policy_versions.amendments_dir` — the one place that path
  is computed, and the function `loader`, `apply_amendments`, `current_version` and
  the runner all reach the directory through — so the whole version machinery runs
  against a temporary directory and `policy/amendments/` is never written to.
  `RerunTests.tearDown` asserts the repository's directory is still in its
  committed state after every test in the class.

## The sealed set, and what a flagged cluster is not

The sealed test set runs at **policy version 1**, with `--precedents` and
`--ablate` off. Nothing in this task changes that. The loop is a separate entry
point that no run calls, so a run's default output is what it always was, and no
version above 1 is measured on the sealed set.

And on today's data **every escalation is one the key also marks ESCALATE**. All
nine — corpus 110, 112, 207, 210 and 213, second set 9108, 9109, 9110 and 9115 —
are marked ESCALATE in the frozen key. So a flagged cluster is **not by itself
evidence of a policy defect**: it is evidence that the policy declined to decide,
which on these cases is what the key asked it to do. A clause drafted from such a
cluster would make the policy decide where it currently declines, and whether that
is an improvement is a question for the key rather than for the cluster.

## What was run

`tests/test_policy_gaps.py` is new: 150 tests, covering the trigger grammar row by
row, the floor's precedence, the signature and its noise drop, both cluster levels
and their ids, the report and its destination refusals, the drafter's input and
its prompt, every way a draft is refused, `approve` and `reject`, the rerun plan
and one real rerun at version 2, and the diff's rendering rules.

The related module was then run on 3.13.12:

    Ran 150 tests in 346.096s

    OK

The full suite on both interpreters is the owner's, run once outside the sandbox.
The queue's final check skips that step and leaves its result to be added
afterwards.

## What is not done

- **No amendment and no proposal is shipped.** `policy/amendments/` and
  `policy/proposals/` hold their `README.md` and nothing else, so the repository is
  at version 1 and there is no version 2 to run. Every version above 1 is
  exercised against a temporary amendments directory, and `runs/policy-v<N>/` does
  not exist.
- **The drafter has never been run against a live model.** `draft` is exercised
  through a scripted transport and a canned answer, so what is proven is the input,
  the prompt, the validation and the recording — not that a model drafts a good
  clause.
- **`policy/amendments/README.md`'s rule is now true of the tests as well.** It
  was not, for the length of one test, and that is the correction above rather than
  a caveat.

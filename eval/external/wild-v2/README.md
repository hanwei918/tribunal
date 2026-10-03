# Tribunal wild-v2 — SEALED HOLDOUT

Prepared 2026-10-01 for Hanwei only. **Keep this archive unopened until the next
feature freeze. Do not hand this archive, its authoring directory, or its
evaluation files to WorkBuddy, CodeBuddy, another repository assistant, or
anyone developing the system.** This is not a development/regression set.
It has not been run through Tribunal's judge/advocate pipeline.

## Scope and source accounting

There are 20 synthetic cases, numbered 701–720, generated from 17 distinct
unused English source seeds plus three variants. The source pool had 84 seeds;
the original wild-v1 seed map used 62 unique base IDs, leaving 22. No wild-v1
case shards, grading key, transcripts or post-run notes were used in authoring.
The seed map and the original archive's seed collection were used only for
source selection; the original archive's reusable builder/validation helpers
were used for formatting. No original case specification modules were read.

Five unused seeds were omitted instead of weakening the format:

- `EN-NS-13`: zero platform charge, with a request only for punishment.
- `EN-NS-16`: a reassigned, zero-fee pickup requiring two driver histories that
  cannot be retained as one canonical trip/driver monetary dispute.
- `EN-BL-17`: a distinct parking reimbursement/reversal and receipt image,
  neither represented by the canonical line items/artifact types.
- `EN-DR-01`: a driver-discipline deduction and missing booked-seat history,
  neither a canonical cancellation fee nor a supported monetary/booking field.
- `EN-DR-02`: a service-quality deduction and audio evidence, neither a
  canonical fare line nor a supported artifact type.

Re-labelling those amounts as cancellation fees, waiting fees, or airport
surcharges would change the central dispute. No nominal contested amount or
fictional platform line was added to make them pass.

Some retained seeds were rewritten within the existing format. A claimed cash
transfer is contextual party/chat evidence, never a platform fare line: the
formal contested amount is solely the positive platform charge. The breakdown
seed therefore retains a normal platform charge plus an alleged private
transfer. An inflated-ERP seed bills the overcharge in the platform ERP ledger
so coordinate matching can settle it. Destination changes use the existing
amendment fields, not a new history array. Cases about completed service remain
completed-trip disputes; no new cancellation, parking, deduction, safety,
pool-cost-sharing or pro-rata-service policy has been invented. Some such
claims have no monetary remedy in the supplied policy and their category-level
disposition does not imply the driver delivered acceptable service.

Difficulty: EASY 4, HARD 7, REVERSAL 4, INDETERMINATE 5. Both supported dispute
categories are present. Five keys are ESCALATE. Private source accounting and
case-to-seed mappings are under `eval/wild-v2/`; never give these to agents.
Coordinates are synthetic Singapore-region polylines, not a validated road
network or an assertion that an ERP gantry exists at a real-world address.
Only supplied coordinates and artifact facts determine geographic tests.

## Layout and runtime isolation

```text
data/wild-v2/index.json
data/wild-v2/cases/case-00701.json ... case-00720.json
eval/wild-v2/ground_truth.json
eval/wild-v2/semantic_check.json
eval/wild-v2/legacy_check_differences.md
eval/wild-v2/seed_map.json
eval/wild-v2/source-unused-seeds.jsonl
policy/{general,no_show,route_deviation}.json
data/schema.json
data/PUBLIC-CONTRACT.md
gen/validate.py
gen/semcheck.py
MANIFEST.json
```

Case shards have only the four PUBLIC-CONTRACT top-level keys. Each case has
exactly seven eight-key artifact envelopes, admissibility blocks and
`accuracy_m` on every driver/rider GPS fix. Formal contested amounts are
strictly positive and do not exceed `fare_breakdown.total_charged`. The schema
snapshot is unchanged 1.2.0. Policy snapshots and PUBLIC-CONTRACT are unchanged.

The external-set index is a five-key array with `file` paths relative to its
own set root (`cases/case-007xx.json`), exactly as in wild-v1 and as accepted by
the unchanged external-set loader. It is **not** the 29-case corpus manifest.
After the freeze, an authorized custodian can copy only `data/wild-v2/` to
`data/external/wild-v2/` in the run checkout, keeping its index unchanged.
Do not merge this index into `data/index.json`. Keep the entire `eval/`, `gen/`,
README, provenance, manifest and authoring sources outside the inference
workspace. Runtime input is only one selected public case plus the selected
policies. Answers occur only in private evaluation/authoring material, never
in a case shard or an agent runtime bundle.

## Frozen policy and grading

The key applies to the packaged base policy files (general 1.0.1, route
deviation 1.1.0, no-show version as recorded in its unchanged file), not later
amendments. The manifest records exact policy bytes. Before the one official
run, check that the chosen policy configuration matches those hashes. If it
does not, agree a policy/key protocol before the run; do not silently score
different rules against this key or inspect this set during development.

Every key carries all four graded fields, including deliberate referrals and
null monetary values on terminal escalation. Seed suggested outcomes are not
authoritative: some rely on nonexistent clauses or referrals. The key follows
the packaged policy text; case rationales and source-suggestion differences are
private. NO_ACTION leaves the current payment state unchanged, including a
pending payment in a driver-filed case; it does not release or restore money.

## Verification

From this directory, with Python and `jsonschema==4.26.0` installed:

```sh
python gen/validate.py
python gen/semcheck.py
```

The v1 structural validator was retained with only local default/root and set
path changes and additional PUBLIC-CONTRACT/cardinality/accuracy checks. Its
amount limit, original difficulty bounds, admissibility checks and monetary
invariants were not weakened. It passes all 20 cases.

The new semantic checker re-derives all four fields from emitted public case
bytes with separate geographic and rounding code. It does not import the
builder, specifications or author key; it loads the key only after deriving all
outcomes. It independently sums raw GPS fixes and matches each ERP coordinate
against every fix at 250 m. It reports zero differences across 80 fields.
It is a bounded checker for mechanisms exercised here, not a general natural-
language policy engine or an independent human adjudicator. Mechanisms outside
its coverage fail closed rather than inheriting a key value.

The original v1 semantic checker, with only set-path changes, is preserved as
`gen/legacy_semcheck.py`. It checks only ruling and amount and has five known
differences. Each is explained in the private difference report; its missing
mechanisms were not "fixed" by changing correct keys to make an old checker
green. Required referral derivation is additionally checked by the new checker.

All 20 files were successfully loaded using an unchanged isolated copy of the
Tribunal external-set loader, with recursive runtime answer-key rejection and
repeatable canonical bundle digests. This was a loading/serialization smoke
test, **not** an AI adjudication run and not a use of the holdout to tune Tribunal.
No Tribunal repository, policy or schema file was modified.

## Seal receipt and one-shot run

`MANIFEST.json` gives every public shard hash, the deterministic case-set hash,
the grading-key hash, and the hashes of all packaged files other than itself.
The case-set hash is SHA-256 of compact, sorted-key UTF-8 JSON listing the
sorted relative case paths and their SHA-256 digests. The index is hashed
separately. Verify the archive against its separately supplied SHA-256 receipt
before opening it. This ZIP is access-controlled by handling convention, not
encrypted; possession of it grants access to private answers.

Record the archive's digest and leave it unopened until after the next freeze.
Then isolate public input from private grading files, run once, save all raw
outputs, and report the outcome without selecting or suppressing failures.
Do not run `gen/build_v2.py` or re-author the set after recording the seal.

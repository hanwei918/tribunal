# Tribunal public runtime contract

This document is the answer-free implementation contract for the public case shards in this workspace.

## Case file shape

Each file under `data/cases/` is one self-contained public case with exactly these top-level keys:

- `schema_version`: contract version string.
- `case_no`: integer case identifier.
- `dispute`: public dispute metadata and party statements.
- `evidence`: array of evidence artifacts.

The loader must retain all four keys. It must confirm that the requested `case_no`, the manifest entry, the filename, and the loaded file's `case_no` agree.

Measured over the 29 case files in this workspace: every file carries exactly these four top-level keys and nothing else, and the top-level `schema_version` is the string `"1.2.0"` in all 29.

## Case manifest (`data/index.json`)

`data/index.json` is a JSON **array**, not an object, holding one entry per case (29 entries). Each entry has exactly these five keys:

- `case_no`: integer case identifier, equal to the case file's own `case_no`.
- `dispute_id`: dispute identifier string.
- `trip_id`: trip identifier string.
- `category`: dispute category. Measured values: `ROUTE_DEVIATION` (15 cases) and `NO_SHOW_CHARGE` (14 cases).
- `file`: the case file path, **relative to `data/`** — not to the repository root. Every value has the form `cases/case-<case_no>.json` with the case number zero-padded to five digits, so it resolves to `data/cases/...`.

## Converted external cases (`data/external/`)

`data/external/` is a second case root. It holds cases converted from material
the organisers supplied, and it is answer-free: the same controls that make a
case under `data/cases/` safe to hand an agent apply here unchanged.

- **Shape.** A converted case has the same four top-level keys, the same
  eight-key evidence artifacts and the same eleven-key `dispute` object as a
  case under `data/cases/`. Nothing about the shape is relaxed.
- **Not in the manifest.** `data/index.json` indexes the 29-case corpus the
  benchmark measures, and it stays that. A converted case is deliberately
  absent from it, so a converted case is named by its **path**, never by a
  manifest lookup.
- **Path.** An external case path must resolve inside `data/external/`. The
  same containment rule that keeps a manifest entry out of the rest of `data/`
  applies, and `..` segments and symlinks are followed before the test.
- **Filename.** The filename is `case-<case_no>.json`, with the case number
  zero-padded to five digits, and it must agree with the `case_no` the file
  itself declares. A converted case therefore cannot be loaded under another
  case's number.
- **Forbidden keys.** The recursive rejection of the five evaluation-only keys
  applies to a converted case exactly as it does to a corpus case.

Case numbers for converted cases are drawn from outside the corpus range
(`101`-`115` and `201`-`214`), so a converted case can never be mistaken for a
corpus case.

## Evidence artifact shape

An evidence artifact has exactly these eight keys, and all 204 artifacts in this workspace share the same set:

- `evidence_id`: artifact identifier string, unique across the corpus.
- `evidence_type`: artifact kind string.
- `admissibility`: object, described below.
- `payload`: the artifact content, or `null` when the artifact is missing.
- `schema_version`: contract version string carried on the artifact itself.
- `source`: provenance label string.
- `trip_id`: trip identifier string.
- `generated_at`: ISO-8601 timestamp string with a UTC offset.

A loader must retain all eight. `source` takes one of `PLATFORM_TELEMETRY` (137 artifacts), `PAYMENTS_LEDGER` (29), `THIRD_PARTY_LTA` (29), `DRIVER_DEVICE` (8), or `USER_SUBMITTED` (1).

### `payload` presence and the missing-artifact test

`payload` is **always present** as a key: it is absent from zero artifacts. It is `null` in 27 artifacts and a JSON object in the other 177.

The correct test for a missing payload is therefore a **value** test, not a key test: `artifact["payload"] is None`. A `"payload" not in artifact` branch is unreachable on this corpus and must not be the only guard.

The same 27 artifacts are exactly those whose `admissibility.status` is `MISSING` and whose `admissibility.issues` contains `MISSING_ARTIFACT`; all three conditions select the identical set of 27 ids, so any one of them may be used, but the payload value test is the canonical one.

A missing artifact is still citable. Preserve its `evidence_id`; its `payload` is `null`, its `admissibility.status` is `MISSING`, and its `admissibility.weight_multiplier` is `0.0`.

### `admissibility` object

Every artifact's `admissibility` object contains at least these six keys:

- `status`: `COMPLETE`, `IMPAIRED`, or `MISSING`. Measured: 159 `COMPLETE`, 18 `IMPAIRED`, 27 `MISSING`.
- `issues`: array of machine-readable issue code strings. It is a list on every artifact and is empty on 159 of them.
- `weight_multiplier`: a JSON number (float) between `0.0` and `1.0`.
- `notes`: string.
- `assessed_at`: ISO-8601 timestamp string.
- `assessor_version`: version string of the assessor that produced the block.

`admissibility.issue_details` is **not** present on every artifact: 45 artifacts have it and 159 do not. When present it is a JSON **array** of objects, each with `code`, `severity`, and `detail`. Test for it with `"issue_details" in artifact["admissibility"]` and never assume it exists.

### `evidence_type` is not unique within a case

An `evidence_type` value may repeat inside a single case. This occurs once in this workspace: case `104` (`data/cases/case-00104.json`) holds two `TRAFFIC_ADVISORY` artifacts, with ids `EV-ADVIS-00104-01` and `EV-ADVIS-00104-02`.

A loader must **not** key, index, or de-duplicate artifacts by `evidence_type`. Key by `evidence_id`, which is unique across the corpus.

The complete set of `evidence_type` values and their counts over all 204 artifacts:

| `evidence_type` | artifacts | per case |
|---|---|---|
| `TRAFFIC_ADVISORY` | 30 | 1 in 28 cases, 2 in case 104 |
| `TRIP_RECORD` | 29 | 1 |
| `GPS_TRACE` | 29 | 1 |
| `CHAT_LOG` | 29 | 1 |
| `FARE_BREAKDOWN` | 29 | 1 |
| `RIDER_PROFILE` | 29 | 1 |
| `DRIVER_PROFILE` | 29 | 1 |

There are 7 distinct types. Each case carries exactly one of each of the six types from `TRIP_RECORD` to `DRIVER_PROFILE`, plus one or two `TRAFFIC_ADVISORY`, so a case has 7 or 8 artifacts in total.

## Dispute object shape

The `dispute` object has exactly these eleven keys, and all 29 cases share the same set:

- `case_no`: integer case identifier, equal to the top-level `case_no`.
- `dispute_id`: dispute identifier string.
- `trip_id`: trip identifier string.
- `category`: dispute category; `ROUTE_DEVIATION` (15 cases) or `NO_SHOW_CHARGE` (14 cases).
- `filed_at`: ISO-8601 timestamp string.
- `filed_by`: which party filed the dispute. Measured: `RIDER` (28 cases), `DRIVER` (1 case).
- `channel`: how the dispute was filed. Measured: `IN_APP_SUPPORT` (28 cases), `EMAIL` (1 case).
- `amount_contested_sgd`: the figure the filing party contests.
- `claim_text`: the filing party's statement.
- `counterparty_statement`: the other party's statement.
- `evidence_ids`: array of `evidence_id` strings cited by the dispute.

`counterparty_statement` is `null` in five cases — `103`, `106`, `201`, `203`, and `204` — and non-null in the other 24. It is the only dispute key that is ever `null`. A loader must treat a null `counterparty_statement` as "no statement on file" rather than an error, and must not substitute an empty string.

## Policy shape

Each policy file is a JSON object with policy metadata and a `clauses` array. Load `policy/general.json` plus the category policy selected by `dispute.category`:

- `ROUTE_DEVIATION` -> `policy/route_deviation.json`
- `NO_SHOW_CHARGE` -> `policy/no_show.json`

Reject unsupported categories instead of guessing a policy.

### Policy metadata keys

Beyond `clauses`, every policy file carries these seven keys:

- `policy_id`: stable identifier string for the policy, e.g. `POLICY-GENERAL`.
- `category`: the dispute category the policy belongs to (`GENERAL`, `NO_SHOW_CHARGE`, or `ROUTE_DEVIATION`).
- `version`: policy version string.
- `jurisdiction`: the jurisdiction the policy is written for; `"Singapore"` in all three files.
- `currency`: the currency the policy is denominated in; `"SGD"` in all three files.
- `last_reviewed`: date string of the last review.
- `confidence_floor`: the numeric confidence threshold to apply when reading this policy. It is carried per policy file, so read it from the loaded policy instead of hardcoding a value.

Two policy files carry one extra key each:

- `policy/general.json` also carries `applies_to`: an array of the dispute categories the general policy applies to.
- `policy/no_show.json` also carries `fee_schedule`: an object describing how the chargeable cancellation fee for a no-show charge is resolved.
- `policy/route_deviation.json` also carries `fare_model`: an object describing the fare components used for a route-deviation fare comparison.

### Clause object shape

A clause object has exactly these eight keys:

- `id`: the clause identifier, and the field every claim must cite as its clause id; ids look like `POL-GEN-01`, `POL-NS-01`, and `POL-RD-01`.
- `title`: short human-readable clause name.
- `category`: the category the clause belongs to.
- `rule`: the clause text itself.
- `requires`: array of artifact types the clause needs before it can be applied.
- `licenses`: array of what the clause permits.
- `favours`: which side the clause tends to favour, e.g. `NEUTRAL`.
- `notes`: explanatory prose for the clause.

The three policy files hold 24 clauses in total: `policy/general.json` has 3, `policy/no_show.json` has 9, and `policy/route_deviation.json` has 12.

## Measured value sets

### `admissibility.weight_multiplier`

Across all 204 artifacts there are 11 distinct values: `0.0`, `0.25`, `0.3`, `0.39`, `0.4`, `0.6`, `0.75`, `0.8`, `0.85`, `0.9`, and `1.0`. The full distribution is:

| value | artifacts |
|---|---|
| `1.0` | 159 |
| `0.0` | 27 |
| `0.4` | 3 |
| `0.85` | 3 |
| `0.25` | 2 |
| `0.39` | 2 |
| `0.6` | 2 |
| `0.75` | 2 |
| `0.8` | 2 |
| `0.3` | 1 |
| `0.9` | 1 |

The value is a float, not a string, and the set is not a small fixed vocabulary — a loader must not validate it against a hardcoded list.

### Issue codes

There are 17 distinct issue codes across all `admissibility.issues` arrays, with these counts:

| issue code | occurrences |
|---|---|
| `MISSING_ARTIFACT` | 27 |
| `GPS_GAP` | 3 |
| `LOW_COVERAGE` | 3 |
| `TRUNCATED_LOG` | 3 |
| `CROSS_SOURCE_CONFLICT` | 3 |
| `PARTIAL_RECORD` | 2 |
| `UNREAD_MESSAGE` | 2 |
| `LOW_SAMPLE_RATE` | 2 |
| `ADVISORY_UNCORROBORATED` | 1 |
| `UNVERIFIED_SOURCE` | 1 |
| `STALE_SNAPSHOT` | 1 |
| `GPS_DRIFT` | 1 |
| `IMPLAUSIBLE_SPEED` | 1 |
| `SCHEMA_VERSION_MISMATCH` | 1 |
| `LANGUAGE_AMBIGUITY` | 1 |
| `CONTENT_REDACTED` | 1 |
| `CLOCK_SKEW` | 1 |

A loader must treat issue codes as opaque strings and must not reject an unrecognised code.

### `schema_version`

`schema_version` appears at both levels. The case file's top-level `schema_version` is `"1.2.0"` in all 29 cases. Every one of the 204 artifacts also carries its own `schema_version`, but the artifact-level values are **not** all the same: 203 artifacts carry `"1.2.0"` and one carries `"0.9.0"`.

The single outlier is `EV-DPROF-00202` in case `202` (`data/cases/case-00202.json`). That artifact is `IMPAIRED` and carries the issue code `SCHEMA_VERSION_MISMATCH`. A loader must therefore compare the artifact-level `schema_version` against the top-level value and surface a mismatch as an issue, rather than assuming the two always agree.

## Runtime bundle boundary

An Agent runtime bundle contains only the selected public case content and selected policies. Development files such as the manifest, this guide, source paths, and loader diagnostics are not Agent inputs.

Before serialisation, recursively reject these evaluation-only keys anywhere in the runtime bundle:

- `ground_truth`
- `expected_ruling`
- `expected_amount_sgd`
- `expected_driver_compensation_sgd`
- `expected_referrals`

This assertion applies to the final runtime bundle only. Development documentation must never be embedded in that bundle.

### The precedents key in the judge's message (2026-09-28)

The loader does not build the judge's message; the pipeline does. One switch adds a key to it, and this paragraph is the boundary's own statement of that.

With `--precedents` on, the judge's user message carries one more key, `precedents`, between `claims` and `referee`: a fixed note and up to three items, each naming a `precedent_id`, a `category`, clause ids and a ruling. **No amount and no summary travel in the block.** The key is absent when the switch is off and absent when nothing matched, so with the switch off the message is the message it always was.

The rejection above is unchanged by it, and it is applied in two places rather than one: when a precedent entry is written, and again to the parsed judge message at runtime whenever the key is present.

## Deterministic serialisation

Serialise the runtime bundle as UTF-8 JSON using `ensure_ascii=False`, `sort_keys=True`, and `separators=(",", ":")`. Expose the SHA-256 digest as `bundle_sha256`. The same inputs must produce the same bytes and digest across repeated runs.

## Policy base version 3, and the fields it adds (amended 2026-10-08)

A second policy base is now in the runtime: **version 3**, under `policy/v3/`,
drafted by Ji Guofang against published platform rules. It is **not the
default** and **no run has been made at it**. The three version-1 files
(`policy/general.json`, `policy/no_show.json`, `policy/route_deviation.json`) and
amendment `0001` are unchanged, so everything above this section is still exactly
true of them; this section is **additive** and changes none of it. In particular
**`schema_version` stays `1.2.0`** -- `prepass.detect_schema_version_mismatch`
treats a case/artifact version difference as a defect, so the fields below are
optional additions to a `1.2.0` case and not a new schema version.

Every field below is optional. A case without it loads exactly as before.

### `trip_record.platform_policy` (object, optional)

The platform parameters in force for this trip. When present, `fee_schedule.resolution_rule` and POL-NS-01(c) read it before `fee_schedule.defaults`.

| field | type | meaning |
|---|---|---|
| `grace_after_match_sec` | int | free cancellation window after matching |
| `advance_grace_before_scheduled_sec` | int | free cancellation window before a scheduled trip's time |
| `free_wait_sec` | int | free waiting period after arrival; the minimum dwell for a chargeable no-show |
| `no_show_threshold_sec` | int or null | a longer platform threshold the cancellation must also reach; null = same as `free_wait_sec` |
| `cancellation_fee_sgd` | number | the cancellation / no-show fee, net to the driver |
| `rider_gross_cancellation_fee_sgd` | number or null | the rider-side figure incl. GST and payment fees, for POL-NS-08(d) reconciliation only |
| `waiting_fee_sgd` | number or null | the waiting-time fee on a completed trip |
| `fee_goes_to` | `"DRIVER"` or `"PLATFORM"` | who receives the fee |
| `arrival_marker` | `"BUTTON"` or `"GPS_AUTO"` | how the platform marks arrival |
| `source` | string | an opaque code for where the block came from - `RECORD-PLATFORM` (carried on the record), `PLATFORM-PUBLISHED-<date>` (the defaults), `AUTHORED-V1` (derived at build time from the version-1 fee table) - never a name or a sentence, because the block reaches the model |

No case file in this repository carries this block. At policy version 3 the brief
derives it for a no-show case that has none, from the version-1 fee table, and
publishes it as `platform_policy_in_force` on the trip record; the case file is
not written.

### `trip_record.scheduled_at` (timestamp, optional, null for on-demand trips)

Read by POL-NS-10(b).

### `trip_record.events[]` (array, optional)

The platform's own event log for the trip. Each item: `event_type` (string), `at` (timestamp), `detail` (string), `source` (one of the evidence `source` values, normally `PLATFORM_TELEMETRY`). An arrival or wait-timer event here is an independent carrier of the dwell for POL-GEN-02(2).

### `trip_record.accepted_at`

Already present on every case; now cited by POL-NS-10(a).

### GPS points: `accuracy_m` may be null

A point with no reported accuracy is of unknown accuracy for POL-NS-02 (`integrity.accuracy_missing_treatment`): neither counted nor excluded by the 25 m filter.

### `dispute.safety_flag`, `dispute.complaint_flag` (boolean, optional)

Set by intake. Cited by POL-GEN-05 (never executed automatically) and POL-GEN-06(1) (entry to human review). They route the case; they are not evidence and carry no weight. Absent means false.

### The version-3 policy files

`policy/v3/general.json` carries 8 clauses and the top-level keys
`execution_threshold_sgd` and `sources`; `policy/v3/no_show.json` carries 10
clauses and the top-level key `integrity`; `policy/v3/route_deviation.json`
carries 13 clauses (31 in total). The version-1 files above keep their own
counts (3 / 9 / 12) and their own extra keys, and no amendment applies to
version 3: `POL-RD-13`, added by amendment `0001` on version 1, is folded into
version 3's `route_deviation.json` as a clause of the base.

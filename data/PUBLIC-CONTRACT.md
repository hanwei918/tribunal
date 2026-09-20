# Tribunal public runtime contract

This document is the answer-free implementation contract for the public case shards in this workspace.

## Case file shape

Each file under `data/cases/` is one self-contained public case with exactly these top-level keys:

- `schema_version`: contract version string.
- `case_no`: integer case identifier.
- `dispute`: public dispute metadata and party statements.
- `evidence`: array of evidence artifacts.

The loader must retain all four keys. It must confirm that the requested `case_no`, the manifest entry, the filename, and the loaded file's `case_no` agree.

## Evidence artifact shape

Every evidence artifact contains an `evidence_id`, an `evidence_type`, an `admissibility` object, and a `payload` value. Relevant admissibility fields include:

- `admissibility.status`: `COMPLETE`, `IMPAIRED`, or `MISSING`.
- `admissibility.issues`: machine-readable issue codes.
- `admissibility.weight_multiplier`: number from `0.0` to `1.0`.

A missing artifact is still citable. Preserve its `evidence_id`; its `payload` is `null`, its `admissibility.status` is `MISSING`, and its `admissibility.weight_multiplier` is `0.0`.

## Policy shape

Each policy file is a JSON object with policy metadata and a `clauses` array. Load `policy/general.json` plus the category policy selected by `dispute.category`:

- `ROUTE_DEVIATION` -> `policy/route_deviation.json`
- `NO_SHOW_CHARGE` -> `policy/no_show.json`

Reject unsupported categories instead of guessing a policy.

## Runtime bundle boundary

An Agent runtime bundle contains only the selected public case content and selected policies. Development files such as the manifest, this guide, source paths, and loader diagnostics are not Agent inputs.

Before serialisation, recursively reject these evaluation-only keys anywhere in the runtime bundle:

- `ground_truth`
- `expected_ruling`
- `expected_amount_sgd`
- `expected_driver_compensation_sgd`
- `expected_referrals`

This assertion applies to the final runtime bundle only. Development documentation must never be embedded in that bundle.

## Deterministic serialisation

Serialise the runtime bundle as UTF-8 JSON using `ensure_ascii=False`, `sort_keys=True`, and `separators=(",", ":")`. Expose the SHA-256 digest as `bundle_sha256`. The same inputs must produce the same bytes and digest across repeated runs.

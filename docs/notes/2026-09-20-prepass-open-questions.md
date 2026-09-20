# Prepass open questions — 2026-09-20

Purpose: record every issue code for which the firing rule could **not** be derived from this
workspace, and what evidence would be needed to derive it.

Scope of the prepass built today: `tribunal/prepass.py` implements `weight_for(issue_codes)` and one
detector, `detect_schema_version_mismatch(case)`. Nothing else is detected.

## Implemented

- `SCHEMA_VERSION_MISMATCH` — the only code whose firing rule is stated in `data/PUBLIC-CONTRACT.md`:
  an artifact's own `schema_version` is compared against the case file's top-level value. It fires on
  `EV-DPROF-00202` in case 202 (`0.9.0` against `1.2.0`).

## Derivable, but deliberately not implemented today

- `MISSING_ARTIFACT` (27 artifacts, severity `BLOCKING`). The contract states the correspondence
  directly: the 27 artifacts whose `payload` is `None` are exactly the 27 whose
  `admissibility.status` is `MISSING` and whose `admissibility.issues` contains `MISSING_ARTIFACT`.
  So the rule is `payload is None`, and it is verifiable. It was left out because the task scope was
  one detector only, not because it is underivable.

## No derivable firing rule (15 codes)

For each code below, the corpus shows **where** it fired but never **why**. The detection thresholds
are not documented anywhere in this workspace, and most codes fire once or twice, so no threshold can
be inferred or cross-checked. No detector was written for any of them, and no threshold was invented.

| Code | Severity | Artifacts | What is missing |
|---|---|---|---|
| `GPS_GAP` | MAJOR | 3 | The gap length or gap count that counts as a gap. |
| `LOW_COVERAGE` | MAJOR | 3 | The coverage ratio and the window it is measured over. |
| `TRUNCATED_LOG` | MAJOR | 3 | The expected log length, or the cut-off that makes a log truncated. |
| `CROSS_SOURCE_CONFLICT` | MAJOR | 3 | Which fields are compared across sources and what counts as a conflict. |
| `PARTIAL_RECORD` | MINOR | 2 | The required field set for the artifact type. |
| `UNREAD_MESSAGE` | MINOR | 2 | The read-receipt signal that marks a message unread. |
| `LOW_SAMPLE_RATE` | MINOR | 2 | The sampling-rate threshold. |
| `ADVISORY_UNCORROBORATED` | MAJOR | 1 | What corroborates an advisory, and how much corroboration suffices. |
| `UNVERIFIED_SOURCE` | MAJOR | 1 | Which sources count as verified, and the verification check. |
| `STALE_SNAPSHOT` | MINOR | 1 | The freshness window between snapshot and event. |
| `GPS_DRIFT` | MAJOR | 1 | The positional tolerance that separates drift from noise. |
| `IMPLAUSIBLE_SPEED` | MAJOR | 1 | The speed bound and whether it is per-mode or per-segment. |
| `LANGUAGE_AMBIGUITY` | MINOR | 1 | The criterion that marks a message as ambiguous. |
| `CONTENT_REDACTED` | MINOR | 1 | The redaction marker convention in the payload. |
| `CLOCK_SKEW` | MAJOR | 1 | The tolerated clock offset between devices. |

### What evidence would settle these

1. **The corpus generator and the offline grader.** They encode the thresholds, but
   `WORKBUDDY-SCOPE.md` places both physically outside this workspace and forbids reading them. They
   are therefore not obtainable here and must not be requested.
2. **A written threshold specification.** A table of code → threshold, published as a development
   document, would settle all 15 at once.
3. **More labelled artifacts.** Several codes fire once or twice (see the table). Two points cannot
   establish a threshold; a code needs enough firing and non-firing artifacts to bracket the
   boundary. `LOW_SAMPLE_RATE` and `GPS_DRIFT`, for instance, would need artifacts that sit just
   either side of the boundary before any rule could be stated without guessing.
4. **The pre-`IMPAIRED` artifact state.** For `GPS_DRIFT` and `IMPLAUSIBLE_SPEED` the rule compares a
   raw trace against an expectation; the expected values are not in the public payload.

## Open questions in the weight arithmetic (Part 1)

The arithmetic itself is well supported: the rule below reproduces the declared
`weight_multiplier` of all 45 non-COMPLETE artifacts exactly, with no rounding.

> No codes → `1.0`. Several codes → the product of their weights, floored at `0.25`. A `BLOCKING`
> code returns `0.0`.

- **Lower bound:** `0.25`. The lowest non-zero weight anywhere in the corpus is exactly `0.25`, and
  it appears only on multi-code artifacts. Two artifacts sit at it: `EV-ADVIS-00104-02` (case 104)
  and `EV-GPS-00210` (case 210).
- **Rounding:** none is required. Every observed weight is reproduced as an exact product of the
  weights used here. Rounding cannot be *excluded* either, because the individual weights of the
  7 codes below are inferred rather than observed; if those were e.g. `0.62` and `0.63` the product
  `0.3906` would need rounding to reach `0.39`.
- **Seven individual weights are inferred, not observed.** These codes never appear alone, so only
  the products they form are visible: `GPS_GAP` × `LOW_COVERAGE` = `0.39`, `GPS_DRIFT` ×
  `IMPLAUSIBLE_SPEED` = `0.3`, and `ADVISORY_UNCORROBORATED` × `UNVERIFIED_SOURCE` ≤ `0.25`.
  `CLOCK_SKEW` is entirely unconstrained: in case 210 it sits alongside `GPS_GAP`, `LOW_COVERAGE`,
  `TRUNCATED_LOG`, `LOW_SAMPLE_RATE` and `PARTIAL_RECORD`, and any value at or below `1.0` would
  still land on the floor. The values used are the simplest consistent with the products, and each
  is marked `INFERRED` in `CODE_WEIGHTS`. **They should be replaced by the real values once the
  generator's table is available.**
- **An alternative rule fits the same five artifacts.** A minimum rule — an artifact's weight is the
  smallest weight among its codes — reproduces all five multi-code artifacts too, if the individual
  weights are taken to be the observed values (`0.39`, `0.3`, `0.25`). The corpus cannot discriminate
  between the product-with-floor rule and the minimum rule, because both are consistent with all 204
  artifacts. The product-with-floor rule was chosen because the corpus contains no weight strictly
  between `0` and `0.25`, which is what a floor looks like, and because `0.39` and `0.3` factor
  cleanly (`0.6 × 0.65`, `0.5 × 0.6`) whereas they would be odd individual code weights. This is a
  judgement call, not a derivation, and it is recorded here as such.
- **A `BLOCKING` code combined with other codes is unobserved.** All 27 `MISSING_ARTIFACT` artifacts
  carry exactly one code. The rule returns `0.0` for such a combination, but the corpus never
  exercises that branch.

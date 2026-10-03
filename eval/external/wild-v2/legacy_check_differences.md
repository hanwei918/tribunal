# Private legacy semantic-check differences

The preserved v1 checker checks two fields only. Its five differences do not establish that the new key is wrong. The case-only replacement independently checks all four fields and reports zero differences.

## Case 708

The legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.

Independent trigger: POL-GEN-02 / POL-NS-09(a): sole canonical charge/fee representation below confidence floor.

EV-FARE-00708 is USER_SUBMITTED, impaired by UNVERIFIED_SOURCE at 0.60. It alone supplies the disputed SGD 26 charge and zero cancellation-fee line; the trip and chat are not independent payment records. Under POL-GEN-02 the deciding monetary fact caps confidence at 0.60, below 0.70, so POL-NS-09(a) requires terminal escalation. Obtain the canonical payment ledger before determining the fee or service-charge disposition; no refund/payment or additional referral is issued.

## Case 711

The legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.

Independent trigger: POL-RD-05 / POL-RD-10(5): missing stored amended baseline.

EV-TRIP-00711 retains a dropoff amendment but amended_optimal_distance_km and duration are null. POL-RD-05 cannot be run; POL-RD-10(5) makes escalation terminal. The reviewer must obtain the stored amended route/requote, not invent it from text or GPS. No automatic refund or driver payment issues and no conduct/billing referral is licensed merely by these allegations.

## Case 714

The legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.

Independent trigger: POL-RD-05 / POL-RD-10(5): missing stored amended baseline.

EV-TRIP-00714 retains a dropoff amendment but amended_optimal_distance_km and duration are null. POL-RD-05 cannot be run; POL-RD-10(5) makes escalation terminal. The reviewer must obtain the stored amended route/requote, not invent it from text or GPS. No automatic refund or driver payment issues and no conduct/billing referral is licensed merely by these allegations.

## Case 716

The legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.

Independent trigger: POL-RD-10(4): endpoint timestamps differ by more than ten minutes.

EV-TRIP-00716 is impaired with STALE_SNAPSHOT and CROSS_SOURCE_CONFLICT at weight 0.30. EV-GPS-00716 is impaired with TIMESTAMP_OUT_OF_RANGE and CROSS_SOURCE_CONFLICT at weight 0.25. Cancellation is 16 minutes earlier than its final fix; POL-RD-10(4) independently mandates terminal escalation and POL-GEN-02 forbids treating either discounted revision as decisive proof for a monetary award. The discrepancy is not resolved by the positive charge in EV-FARE-00716. Obtain aligned trip, GPS and payment revisions; hold the disputed amount.

## Case 719

The legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.

Independent trigger: POL-RD-05 / POL-RD-10(5): missing stored amended baseline.

EV-TRIP-00719 retains a dropoff amendment but amended_optimal_distance_km and duration are null. POL-RD-05 cannot be run; POL-RD-10(5) makes escalation terminal. The reviewer must obtain the stored amended route/requote, not invent it from text or GPS. No automatic refund or driver payment issues and no conduct/billing referral is licensed merely by these allegations.

## Additional untested legacy fields

The old checker neither derives nor compares driver_compensation_sgd or referrals. Case 712 has a required POL-RD-09(4) billing-integrity referral; the new checker independently re-matches its gantries and compares that referral, not merely its amount. All other empty referral arrays are deliberate: no generic safety/conduct/policy-gap referral was invented from a source recommendation. No driver payment is licensed on this set.

## Source suggestions versus frozen policy

Source-seed expected_ruling is non-authoritative. The mapping below accounts for every retained seed instance; changed suggestions are explained by each key rationale and the schema-compliant rewrite, not by wild-v1 performance.

- 701: EN-RD-06; suggested NO_ACTION; author NO_ACTION.

- 702: EN-RD-18; suggested NO_ACTION; author NO_ACTION.

- 703: EN-NS-11; suggested ESCALATE; author FULL_REFUND.

- 704: EN-NS-18; suggested ESCALATE; author NO_ACTION.

- 705: EN-NS-19; suggested ESCALATE; author NO_ACTION.

- 706: EN-NS-20; suggested FULL_REFUND; author FULL_REFUND.

- 707: EN-NS-28; suggested NO_ACTION; author NO_ACTION.

- 708: EN-NS-31; suggested ESCALATE; author ESCALATE.

- 709: EN-BL-03; suggested DRIVER_COMPENSATION; author NO_ACTION.

- 710: EN-BL-04; suggested PARTIAL_REFUND; author NO_ACTION.

- 711: EN-BL-15; suggested ESCALATE; author ESCALATE.

- 712: EN-BL-16; suggested NO_ACTION; author PARTIAL_REFUND.

- 713: EN-SC-01; suggested ESCALATE; author NO_ACTION.

- 714: EN-SC-04; suggested ESCALATE; author ESCALATE.

- 715: EN-SC-05; suggested ESCALATE; author NO_ACTION.

- 716: EN-SC-08; suggested ESCALATE; author ESCALATE.

- 717: EN-SG-01; suggested FULL_REFUND; author NO_ACTION.

- 718: EN-RD-06; suggested NO_ACTION; author PARTIAL_REFUND.

- 719: EN-RD-18; suggested NO_ACTION; author ESCALATE.

- 720: EN-SG-01; suggested FULL_REFUND; author FULL_REFUND.

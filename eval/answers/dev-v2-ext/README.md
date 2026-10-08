# dev-v2-ext (key-side notes)

`ground_truth.json`: one entry per case (2701-2760, 2801-2860), the same shape as the other keys in `eval/answers/`.
Produced by `eval/synth/make_dev_set.py --size 200` (seed 20261007; the run also rebuilds dev-v2 byte for byte and
writes only the 120 variants here) and checked by `eval/synth/verify_dev_set.py dev-v2-ext`: 120 of 120 agree.

Beside the key: `EXPECTED.md` (one row per variant), `pairs.json` (the 22 pairs among the variants: 21 directional and
one invariance pair whose twin is a dev-v2 case), `manifest-meta.json` (per-case track, scenario, `variant_of`, pair and
derived figures) and `DATASHEET.md`. The 200-case calibration / holdout partition is `data/external/dev-v2-ext/split.json`.

Nine cases flip with the version-2 code change: 1717, 1718, 1725 (in dev-v2) and 2717, 2718, 2725, 2741, 2742, 2749
here, all decided by the 180 s free wait their `platform_policy` block states; until plan item 41 the version-1 brief
applies 300 s by zone. The key is frozen under the same rule as every other key.

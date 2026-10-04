# Absolute scoring exploration — preserved, not an adopted metric

**Archived during session migration.** The original script, output JSON and log
are preserved byte-for-byte. They were previously uncommitted exploratory work.
This archive is not a production scorer, benchmark, or approved 0–1 scale.
Read this file before using the script or its normalization columns.

## What was actually established

From the two completed BLOB2v2r2 cases, the archived submitted Gaussian payloads
were rescored against the existing frozen R5 truth arrays. All **12 raw CRPS
values match the trace's logged values at six decimal places**. This is not a
claim of unrounded bitwise identity. The new preservation check compares the
saved numbers and hashes; it does not run the scorer again.

| Case | Contract | Raw CRPS, six decimals (lower is better) |
|---|---|---:|
| E1_928 | L1 | 0.072269 |
| E1_928 | L2 | 0.202600 |
| E1_928 | L3F | 0.000554 |
| E1_928 | L3E | 0.123931 |
| E1_928 | L4 | 0.001939 |
| E1_928 | L4D | 0.001284 |
| E2_942 | L1 | 0.024033 |
| E2_942 | L2 | 0.082542 |
| E2_942 | L3F | 0.003990 |
| E2_942 | L3S | 0.000849 |
| E2_942 | L4 | 0.066575 |
| E2_942 | L4D | 0.002930 |

These cases remain diagnostic because their exploration traces have state
integrity defects. They have different worlds/menus/draws; do not make a cohort
mean or infer model quality from their score difference. Raw CRPS is not bounded
to [0,1]. Its reduction and observable units matter. In particular, old L3S
already pools spatial mean and variance targets with different units; a single
legacy L3S CRPS is not a universal physical error scale.

## Known flaws / interpretations NOT adopted

1. **Misnamed span.** The script comment says pre-anchor variability, but
   `_hist_dev`/`_hist_glob` use the full base record, frames1..500 (5..2500tu).
   No per-instance anchor slice is applied to the exploratory denominator.
2. **Different denominators.** L1/L3F/L4/L4D use average per-element temporal SD
   at the relevant device's home pose. L2 uses average spatial SD from global
   variance. L3S uses temporal SD of global means, not a separate variance-target
   scale. L3E has no such denominator. These are not one uniform observable scale.
3. **No certified 0–1 transform.** `1 - CRPS/SD` was discussed but not adopted.
   Clipping does not fix its arbitrary calibration or mixing of quantities.
   The earlier claim that climatology generically scores0.77 was wrong: for an
   independent truth draw from the forecast Gaussian, expected CRPS is
   `sigma/sqrt(pi)` (~0.5642sigma), not the ~0.2337sigma value at exactly y=mean.
   With that same sigma denominator, the illustrative expectation is ~0.4358;
   actual world climatology values need not equal it.
4. **LOO Gaussian is not an exact noise floor.** `truth_loo_crps` fits a Gaussian
   to the remaining members and scores a held-out member. Finite sample size,
   non-Gaussian truth and missing information at the sensors all matter. The
   script's word “irreducible” is too strong. `1x` does not certify a perfect or
   agent-achievable theory. Single-member cases give null, not a usable ratio.
5. **Mixed-horizon mismatch.** `crps_over_truth_loo` for L3F averages agent error
   over all horizons but averages its denominator over only ensemble horizons.
   Do not report the stored aggregate ratio as an aligned floor multiple. Any
   revised reduction must include all legs with explicit weights, or report
   ensemble legs separately with their own qualifications.
6. **MAE is prediction error, not intervention effect.** In particular, the
   earlier claim that three dose instances had <1% physical effects was not
   established by these values. A matched control with the same initial state
   and random forcing is needed for that comparison. The R6 physics dossiers
   provide actual cached paired-field evidence instead.
7. Low variability at a sensor does not mean a globally dead field. Ensemble
   spread growth does not prove chaos, a propagation law or noise-driven
   nucleation. The code only establishes that stochastic forcing is present.

The final R6 direction is an executable predictor tested through world-specific
private coverage, not these six normalizations. See
[the R6 overview](../../../round6/README.md) and
[the migration guide](../../../../../../handoff/SESSION_MIGRATION.md).

## Files and provenance

- `absolute_scores.py`: original exploratory script, including the flawed labels
  above. Preserved rather than silently rewritten into a different experiment.
- `absolute_scores.json`: original numerical output.
- `run.log`: original console output, including an old local output path.
- `PRESERVATION.json`: original-file hashes, six-decimal comparisons, and scope.

Dependencies for any deliberate rerun are **local, not all in Git**: both exact
traces with workspace payloads, the two base caches, and frozen R5 truth NPZs.
Their paths/hashes are in `handoff/LOCAL_ASSETS.json` at repository root. The trace
IDs are `0bdd699154ee4e1d96aac4e0961bc11d` (E1#928) and
`ae982494a72144c186f58a687a99cd33` (E2#942); select these exact nested traces, not
line counts or all records in a file. E1 payloads use `app/probe/payload_*.json`;
E2 uses `app/models/sub_*_i1.json`.

The historical command is `.venv/bin/python` followed by this script's repo path,
from repo root. It reads full cached histories and writes this directory's result
JSON; do not rerun merely to read the findings. R5 `load_truth` raises if frozen
truth is missing. Its suggested build command is **not authorization** to rebuild
truth or start simulations. Do not import this script: it has a top-level run.
No model calls or science simulations were run to create this preservation note.

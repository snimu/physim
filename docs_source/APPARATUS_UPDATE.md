# Centered apparatus update — September 16, 2026

> **Historical plan.** Since it was written, the centered-source preparations were
> completed, the [BF case study](../BF_CASE_STUDY.md) was recorded, and the
> `*_centered_v2` preparations were published at dataset revision `bd77a0da…`. The
> `docs_source/pages/scoring.html` page it mentions is now part of the single-page site
> (`docs_source/partials/scoring.html`).

Agreed behavior:
- Each of the two instruments has a source at its own sensor-array center.
- `inject` selects `device` and `port`; launch instantly captures the current center.
- Forcing lasts for `dur` at that captured world position, independent of later moves.
- Instantaneous movement carries the sensor array and future pulse launch position.
- Sensor dilation changes spacing around the center, not source width.
- Each device has its own movement lane (5 tu) and injection lane (`dur`).
- Independent lanes may overlap and start simultaneously. Equal-time actions execute
  in list order, then readings are taken; forcing begins on subsequent steps.

Current implementation and agent contract: `centered-pulse-v2`.
Published preparations, suites, figures and model scores: `fixed-source-v1`.
The loader selects behavior from the stored apparatus, and old reference modules
retain their published bytes in `physim/legacy_v1`. Never amend historical truth
or reinterpret an old action request under the new protocol.

## Campaign authorized after documentation review

The user authorized the reruns on September 16. Fresh three-realization science
for all three worlds and centered-source causal checks for BF/XV are complete.
New grading truths and baseline controls are being generated. Paid inference
starts with GLM Flash after validating each new bundle. The spending target is
$50, with a $150 hard pause ceiling; finish an ongoing rollout that crosses $50,
then discuss before launching more. The detailed plan and run evidence are in
`handoff/evaluation_campaign_20260916/PLAN.md` and
`outputs/evaluation-campaign-20260916`.

1. Finalize any other agreed protocol changes before running campaigns.
2. Create new preparations for p4g2_044, BF and XV with centered sources. Reuse
   preserved initial fields when appropriate, but issue new apparatus/preparation
   identities. BF/XV recipes now emit centered-pulse-v2; the one-time historical
   p4 exporter intentionally remains fixed-source-v1 and is not a migration tool.
3. Develop fresh intervention programs, including both devices, source-centered
   sensor responses, same-time ordering, and movement after pulse launch. Recheck
   the useful physical effects and controls at these new launch positions.
4. Freeze new suites/scales before generating independent grading truths and native
   controls. Do not reuse a previous receipt, control or reference score as new evidence.
5. Publish new registry releases/HF bundles, update pinned configs, and build/test
   a new package release. Preserve the old bundles for reproducibility.
6. Rerun model rollouts, update results/figures with explicit apparatus versions,
   and sync the finalized environment contribution to the Prime PR.
   Refresh the BF investigation in `docs_source/pages/scoring.html` from the new
   measurements, including the captured `bf-evaluation` data, figure captions,
   response magnitudes, and suite groups. Its current recorded evidence is the
   September 13–14 fixed-source study, identified in the figure captions.

## Documentation review convention

Write the public explanatory chapters around the agreed apparatus, without
temporary notices about review progress or pending reruns. Keep that work status
in this plan. After the full page review, rerun the experiments and model
rollouts and update the results page together; do not invent new scores.

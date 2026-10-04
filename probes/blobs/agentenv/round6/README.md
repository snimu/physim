# R6: executable prediction and demonstrated world physics

The current entry point is the
[p4g2_044 worked example](worked_example/README.md). It joins causal physics,
anonymous experimental programs, fresh independent-noise truth, and executable
prediction scoring. The compact suite has15 cases, all executed through the
native R6 scheduler with2 fresh realizations each. The
[earlier small-model pilots](worked_example/rollout/iterations/README.md) used a
custom model/tool loop. The current
[Verifiers v1 taskset](worked_example/rollout/verifiers_v1/README.md) uses the
bundled `bash` coding harness and native Docker/evaluation runtime, with public
predictor validation. Small-model reruns through Verifiers are in progress.

- [Shared R6 specification](../../l0/deepsearch/TRACKA_R6_PREDICTOR.md)
- [Agent-facing contract](worked_example/AGENT_SPEC.md)
- [Private task dossier](worked_example/p4g2_044/cases/task_dossier.md)
- [Case programs](worked_example/p4g2_044/cases/compact_requests.json)
- [Native validation and scores](worked_example/p4g2_044/native_validation_report.json)
- [Runner design](runner/DESIGN.md) and [offline evaluator](worked_example/evaluation/README.md)
- [Reusable investigation workflow](worked_example/WORKFLOW.md)

## Physics evidence

The original p4g2_044 pulse finding now has a causal account, full native sensor
observations, independent-noise repeats and two further investigations:

- [Pulse survival, extinction, rebound and feedback](physics/p4g2_044/sensor_study/MECHANISM.md)
- [Independent-noise repeatability and geometry](physics/p4g2_044/sensor_study/noise_study/README.md)
- [Spatial selection and timed stripe interventions](physics/p4g2_044/sensor_study/spatial_selection/README.md)
- [Shared feedback, boundary displacement and partner compensation](physics/p4g2_044/sensor_study/defect_halo/REPORT.md)

These reports distinguish ordinary agent-accessible experiments from private
field swaps/clamps, and finite sensor evidence from full-field interpretation.
The prepared state is the existing seed928 state at original time1700, rebased
to public0 with calibrated close/wide probes. This is a documented development
instance, not a claim that an agent has already discovered its geometry or physics.

## Current implementation

`physim.blobround6` supplies the native oracle scheduler.
`physim.blobround6_explore` supplies a budgeted trusted local experiment host using
the same grammar and source range as evaluation. `physim.blobround6_eval` supplies
strict sample validation, marginal CRPS, joint energy scores and data-only JSON
prediction handoff. The predictor itself implements
`predict(actions,queries,n_samples=64,seed=0)`.

Each physical experiment has independent ongoing noise from its start, including
shams. Predictor seeds only control model sampling. The former policy A and its
shared base-continuation cache are superseded. The evaluator compares distributions
without pairing predicted and physical members. No universal0–1 score is adopted.

The trusted simulator is paired with a networkless Docker boundary for model
analysis and submitted predictors, bounded Prime inference and recorded rollout
budgets. Validation and grading use the same isolated prediction environment.
The historical R5 whole-state concurrency defect remains outside this local path.
The model pilots use the existing prepared world; registry publication and
broader-world generation remain later work.

## Historical material

The original cache-only dossiers remain available for provenance:
[p4g2_044](physics/p4g2_044/PHYSICS.md) and
[p6g8_033](physics/p6g8_033/PHYSICS.md). Only the former received the subsequent
native studies and worked-example suite. The p6 candidates are not newly confirmed.

`RUNNER_REVIEW.md`, `first_pass_validation.json`, `parent_validation.json`,
`validate_first_pass.py`, `PLAN.md` and `COORDINATION.json` describe the archived
first pass. Their31-test/policy-A/cache-only statements are historical, not the
current runner. The old static source hashes are expected to differ after this
implementation; use the current worked-example checks. The separate R5
[absolute-scoring exploration](../round5/resource_revision/absolute_scoring/README.md)
is preserved unchanged and is not the adopted R6 score.

For historical migration context, see [SESSION_MIGRATION.md](../../../../handoff/SESSION_MIGRATION.md).

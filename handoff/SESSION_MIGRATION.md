> **Historical session notes (2026-09-07 to 2026-09-09).** This guide describes the
> project as it stood then. Its links into `worked_example/` point to local files that were
> never committed, and its "optional short checks" no longer pass. Two of those checks
> also overwrite preserved evidence (`handoff/VALIDATION.json` and
> `probes/blobs/agentenv/round6/first_pass_validation.json`), so don't run them. For the
> current project, start with [README.md](../README.md), [REPRODUCING.md](../REPRODUCING.md) and
> [REPOSITORY.md](../REPOSITORY.md), whose "Development and validation" section lists the
> current checks.

# Session migration — start here

## Latest completion: native Verifiers rerun (2026-09-09)

The user required a provided Verifiers harness and requested rerunning the seven
previously tested small models, with harness experimentation allowed. That work
is complete. The [`physim_r6` taskset](../environments/physim/physim_r6/taskset.py)
uses Verifiers 0.3.0 native `eval` / `SingleAgentEnv`, stock Bash/RLM harnesses and
DockerRuntime. Task hooks supply laboratory MCP tools, public validation and
scoring; there is no custom model loop or harness.

[Final results and every attempt](../probes/blobs/agentenv/round6/worked_example/rollout/verifiers_v1/RESULTS.md):
Qwen3.6 35B A3B 0.679223; Qwen3.6 27B 0.774276; DeepSeek v4 Flash 0.834902;
GLM 4.7 Flash 1.020349; Qwen3.5 35B A3B 1.107505; Qwen3.5 9B 1.479912;
Qwen3.5 2B +∞ for an invalid array contract. Persistence remains 0.827121.
Six valid predictors complete all 15 cases; every earlier native NaN has a
recorded follow-up. The 20 native attempts use $5.8186 in provider-reported
inference cost, plus one initial GLM call with no reported cost. Historical
custom-runner charges and results are separate.

Conditions were adapted and are not a controlled model/harness comparison.
Qwen2B/9B received explicit file-delivery prompts. Successful GLM and Qwen3.6
follow-ups requested thinking disabled. Qwen3.6 A3B's final Bash episode restored
a validated snapshot after two MCP cancellations and inherited nine observations
/ 52 tu. It made no new experiments, but used 96 additional calls to refit and
rewrite its predictor. Native finalization collected the revised file at the
call limit. Qwen27B also completed through normal final collection at 96 calls.
No model-authored predictor was repaired by the host. Native `max_input_tokens`
counts newly introduced input once; it is not a dollar or cumulative billed
prompt-token cap. Actual native cost is the accounting source.

[Reproduction and boundary documentation](../probes/blobs/agentenv/round6/worked_example/rollout/verifiers_v1/README.md)
links the frozen plans/configs, source snapshots, and complete traces. Fifteen
offline tests and four actual native eval/Docker smoke tests pass. The final
evidence audit verifies all 176 installed Verifiers v1 Python files against the
package record, unchanged scientific inputs and grading, and artifact/data hashes.
All evaluation sessions are finished; no task containers remain. Two unrelated
six-day-old Docker containers were left untouched. Use native eval for future
work; earlier v1–v5 custom runners are preserved only for historical provenance.

## Current continuation: R6 worked example (2026-09-07–09)

The user authorized combining a concrete R6 suite with further physics exploration
in p4g2_044, using subagents. That work is now documented in
[round6/worked_example/README.md](../probes/blobs/agentenv/round6/worked_example/README.md).
It supersedes the first-pass-only scope and policy-A design described below.

The native runner now uses independent ongoing noise from the prepared start for
every experiment, including shams. Agent sampling seeds are unrelated to physical
noise. A prepared exact t1700 state and calibrated close/wide devices are rebased
to public0. The compact suite has15 anonymous cases and30 completed fresh native
trajectories, alongside an executable scorer and trusted local exploration host.
Further studies demonstrate timing-sensitive spatial effects and shared-feedback
negative-boundary displacement/partner compensation. Scientific reports retain
private causal interventions and limits separately from accessible actions.

The [small-model iterations](../probes/blobs/agentenv/round6/worked_example/rollout/iterations/README.md)
now complete the isolated Prime path. The user approved more small-model runs,
slightly larger Qwens, and counting failed callables as worst-ranked task scores.
DeepSeek v4 Flash scores 0.686557; Qwen3.5-35B-A3B scores 0.802683 after a saved-state
provider recovery. Qwen3.6-27B scores 1.791020 after its cumulative inference cap
was raised from $0.45 to $0.90; its original budget-limited stop receives NaN
because no predictor was submitted. Provider errors also receive NaN, including
the Qwen35B HTTP-500 phase. +∞ is reserved for submitted contract/category errors.
The v2 Qwen9B run also scores +∞ because of invalid empty-query output. Each
valid predictor completed all 15 cases, versus initial persistence at 0.827121.
The [analysis](../probes/blobs/agentenv/round6/worked_example/rollout/iterations/ANALYSIS.md)
explains the modeling limitations and why adaptive continuations are not a
controlled comparison of model sizes.

The user then requested [Qwen2B and Qwen9B retries](../probes/blobs/agentenv/round6/worked_example/rollout/iterations/RETRIES.md).
Both completed 64 model responses and ended at +∞ for submitted contract errors.
Qwen2B's context-overflow NaN was repaired with a bounded provider conversation
view before it submitted wrong-shaped arrays. Qwen9B returned forecasts for all
15 cases (diagnostic error 2.294695), but a frozen-artifact check proved it reorders
query outputs. The public contract already prohibited that. DeepSeek, Qwen35B and
Qwen27B passed the same ordering check and retain their finite scores. The normal
submission gate now checks ordering before grading.

The user then approved [GLM-4.7-Flash and Qwen3.6-35B-A3B](../probes/blobs/agentenv/round6/worked_example/rollout/iterations/NEXT_MODELS.md).
GLM completes all 15 cases with error 0.673018 after four no-action experiments;
its predictor ignores interventions and interpolates the last baseline experiment.
Qwen uses 15 experiments and 750 native time units, then repeatedly fails to save
a predictor. Recorded continuations raise its response allowance and inference
cap without adding simulation time. Final direct source delivery with reasoning
disabled returns model-written code that crashes while stacking differently
shaped observations, yielding +∞. The final delivery condition differs from the
initial rollout; no submitted code was repaired. The pair uses $0.4363 in reported
inference, with Qwen's five physical phases counted once each.

Through the completed v4 campaign, confirmed reported inference is $1.9281 including the original $0.0657
pilot/probe cost. Another $0.06511041 is reserved for uncertain HTTP-500 and
context-error charges, giving $1.99321041 charged or reserved against the $2 cap. Exploration
used 2,177 native time units across old and new phases; grading reused saved
truths. All model jobs and pilot containers have finished. The updated summary
builder audits costs, bounds, source/artifact hashes, transcript restoration and
all forecasts and compacted context views (102 checks); all 43 original audited
v1 inputs and all 12 pre-pair status files remain unchanged. All 36 local runtime
tests pass, covering outcomes, provider retries, rollout/gate/CLI limits, bounded
contexts, cumulative recovery chains and direct source delivery.
The original Docker smoke and saved audit remain 11 and 109 checks.

The user clarified that NaN requires retry or environment/limit repair, rather
than being a terminal model result. All eight historical NaNs have verified
scored follow-ups; `unresolved_nan_runs` is empty. The
[v4 runtime](../probes/blobs/agentenv/round6/worked_example/rollout/runtime_v4/README.md)
uses bounded transient-provider retries and context views, keeps the $0.90 Qwen27B
cap, marks NaNs with required recovery actions and exits 2 when recovery is
needed. Those runs use `_v4` directories and per-run source snapshots. Their
gate version is `r6-gate-query-order-v1`. Old raw grades/statuses remain unchanged;
the effective outcome layer applies verified post-submission contract audits.

On September 9 the user approved trying a separate public validation tool.
The [v5 runtime](../probes/blobs/agentenv/round6/worked_example/rollout/runtime_v5/README.md)
adds `validate()` without finalization, clarifies that JSON request metadata is
embedded in each NPZ, and prompts earlier write/validate/repair cycles. The
scientific contract and scoring suite are unchanged. There were 45 passing runtime
tests, a Docker edit/validate/submit smoke test, and a replay of five frozen
predictors with all 126 audited inputs preserved. GLM and DeepSeek pass all seven
public checks; the three Qwen failures reproduce with useful diagnostics.
A [fresh Qwen3.6-35B-A3B trial](../probes/blobs/agentenv/round6/worked_example/rollout/runtime_v5/TRIAL.md)
has completed under a separate $0.60 allowance. The initial 64-response phase and
32-response continuation never wrote `predictor.py` or used `validate()`, despite
saving analysis files. A final recovery disabled thinking and requested source
directly; the model delivered code, passed validation and submitted in three
responses, with no source repairs. It completes all 15 cases at error 0.901651,
worse than initial persistence. The type checker works, but its presence did not
solve ordinary delivery, and this experiment does not isolate reasoning mode
from delivery format. The new trial used 99 responses, 10 experiments, 187 native
time units and $0.4054. Both new NaNs have a verified finite follow-up. All runs
are finished; current runtime tests total 51. Combined charged/reserved inference
across the earlier campaign and this new trial is $2.39861041; combined native
exploration is 2,364 time units. Its files live under `rollout/runtime_v5/runs`,
keeping the earlier campaign ledger closed.
Current protocol is `r6-prime-pilot-v5` and gate `r6-gate-public-validation-v1`.

[Contract v2](../probes/blobs/agentenv/round6/worked_example/rollout/contract_v2/README.md)
uses 64 responses and strictly increasing query times, without the former
duplicate-time submission check. The 15 grading programs and scientific scores
remain unchanged. The original 32-response v1 records remain unchanged: Qwen2B
and Qwen9B have submitted contract errors (+∞), while DeepSeek has no submission
(NaN). The old Qwen9B 0.864094
retrospective score stays diagnostic. Qwen122B-A10B never ran and still requires
the previously requested explicit approval; it was not part of these iterations.
The old R5 transport concurrency defect remains outside the new local path.
Old first-pass validation hashes/counts and cache-only/no-new-seeds statements
below are historical. Current evidence and commands are in the worked-example
entry point. Historical launchers, operational state, and other untracked files
remain untouched; do not resume old jobs from their presence.


Updated 2026-09-07. The substantive R6 first pass was published in **c06b2fb**.
This migration commit preserves the remaining scoring scratch work and records
local inputs. No active task depends on the previous agent's Python variables,
children, heartbeat, or conversation memory.

**Current action: review the R6 package and decide the next design step with the
user. Do not automatically start another rollout, simulation battery, or pod.**
For current status, this guide and the top of HANDOFF.md supersede its dated
historical sections. Old “running” lines and PID files are not live instructions.

## 1. Read order for a fresh agent

1. [Current handoff](HANDOFF.md), **current section only** initially.
2. [R6 overview](../probes/blobs/agentenv/round6/README.md).
3. [R6 predictor spec](../probes/blobs/l0/deepsearch/TRACKA_R6_PREDICTOR.md) and
   [runner design](../probes/blobs/agentenv/round6/runner/DESIGN.md).
4. The two [p4g2_044](../probes/blobs/agentenv/round6/physics/p4g2_044/PHYSICS.md) and
   [p6g8_033](../probes/blobs/agentenv/round6/physics/p6g8_033/PHYSICS.md) dossiers.
5. [Curated state](SESSION_STATE.json),
   [local input inventory](LOCAL_ASSETS.json), and
   [environment snapshot](ENVIRONMENTS.json) when operating on files.

No pending worker needs resuming. All three R6 workers handed off, were reviewed,
and were retired. The temporary watchdog was deleted. A fresh check during this
migration found **zero direct children and zero agent-owned active heartbeats**.
Paid evaluations and both campaign GPU pods remain stopped/terminated.

## 2. Preserve the user's research direction

The user rejected using generic baselines or sensitivity thresholds as the
meaning of interesting science. **“Physics is not generic.”** Interesting
behavior is often concentrated in special conditions; exploration must learn
where to look. A random probe can miss the blob entirely. A high score on flat
background, or on readable recorded futures, need not establish discovery.

The proposed loop is:

1. Grow worlds.
2. Find interesting worlds; improve selection metrics from what genuinely matters.
3. Use our privileged rules and full 2D views to write evidence-backed empirical
   physics for a world. That is a check on the interestingness metrics, not merely
   a story attached to a score.
4. Test whether an agent with only instruments/interventions discovers predictive
   knowledge of that physics. It need not name the mechanisms as we do or recover
   the simulator's field equations. A useful empirical theory is acceptable.

Fixed contracts are **not presumed optimal**. They disclose where the oracle
thinks to look. The newer direction is executable theory: an agent supplies code,
and a private evaluator queries it on world-specific consequences. The oracle's
coverage map stays in the grader, not in a mentor syllabus. The agent must still
explore, find phenomena and build its own sense of importance. The aspirational
version also has agents propose tests, make predictions and validate their own
theories. That full autonomous-science loop is not implemented. Oracle-guided
assessment is an evaluation aid, not an assumed optimal endpoint. A finite
battery will not certify prediction of every possible outcome.

Meaningful nulls, selectivity and invariants remain valid science. Do not replace
the previous “dead port” mistake with a rule that every graded target must show a
large effect. Do not reinstall the rejected generic baseline gate under a new name.

## 3. What is implemented, and what is still a proposal

### First-pass implementation and accepted evidence

- Submitted-code interface: `predict(actions, queries, n_samples=64, seed=0)`.
  Return `{"samples": [array_per_query, ...]}` with coherent member trajectories.
  Each scenario starts at a fixed opaque t=0, including initial fields/apparatus.
  **No history, public anchor, geometry or field-equation input.** Action/query
  times are absolute; waits are implicit. Histories may inform exploration and
  private phase selection, not become extra predictor inputs.
- `Predictor` in `blobround6.py` is a structural interface, not a supplied agent
  model. The implemented engine is privileged `OracleRunner.sample_truth` with
  a separate, required `truth_seed`. Public predictor sampling seeds must not
  choose the grader's random realization.
- Isolated scheduler: dt=0.02 grid, strict parser, explicit event ordering/source
  intervals, pose changes, no-op/query/prefix consistency and exact private
  checkpoints. The proposed grammar is bounded in expressiveness, not “anything.”
- Worker and independent root checks: **31/31**, comprising 25 toy/API/checkpoint
  and six native tests. Native trajectories were at most **0.12tu**. This does
  not establish long-time parity, performance or safe arbitrary input handling.
- Both physics dossiers are bounded first passes using existing caches. They
  separate observations, hypotheses and NOT YET TESTED experiments. They are
  not completed universal theories. Root reviewed the key 2D figures.

### Concrete physics candidates

- **p4g2_044 / seed928:** spot/stripe interactions and nonmonotone source-off
  outcomes; u2/u3 negative defects with shared signed feedback; localized gated
  x7 halos that home probes can miss. In one cached common-noise dose series,
  lag250 segment counts are control/amp1/amp2/amp3/amp4 = 5/6/5/7/8.
- **p6g8_033 / seed942:** evolving ridges with candidate delayed-channel effects;
  slowly drifting negative cores missed by home probes; a pulse causes large
  local rearrangement with nearly canceled global-mean change. A quiet gated X9
  is a useful control, not a universally dead field.

These are single-realization/quantized-cache observations. They do not prove
chaos, propagation speed, an organism census, a universal threshold, or noise's
necessity for the patterns. See the dossiers for exact masks, parameters and limits.

### Decisions to resolve before further scientific runs

1. **Causal noise pairing.** Implemented policy A uses base forcing until the
   first effective action, then fresh member forcing. A no-op stays on the base
   stream. This follows the draft but does NOT reproduce the common-noise
   treatment/control comparisons used in the dossiers. Choose a consistent trial
   forcing convention or a separately specified private paired-experiment method.
   Do not silently change policy or interpret mismatched-noise differences as
   isolated intervention effects. Noise enters the activators every solver step;
   we have not established that it causes nucleation or prevents freezing here.
2. **Experimental access.** Prototype eval amplitude[0,3] and dilation clipping
   do not match old exploration amp<=1 and bound rejection. Freeze honest
   exploration/query domains, reachable sensor protocols and any extrapolation
   strata. An above-range case is not automatically learnable in range.
3. **Coverage and confirmation.** Choose one or two dossier hypotheses and the
   smallest controlled experiments. Cost them before running. No broad sensitivity
   battery, new truth ensembles, cross-seed study or new world was approved after
   the first pass. Thousands of oracle runs are not assumed cheap.
4. **Scoring/runtime.** No R6 scorer, safe untrusted-bundle runtime, final resource
   caps or production episode is implemented. Marginal CRPS alone misses joint
   temporal/spatial structure. No universal 0–1 or exact agent-achievable floor
   was adopted. A subprocess/import restriction is not a security sandbox.
5. **Integrity and leakage.** Fix/regression-test the old whole-state GET/PUT
   concurrency defect before any rollout. The new oracle unit tests do NOT test
   that transport. Exclude privileged rules, dossiers, caches and truth from the
   agent's context/filesystem/network. These published worlds are development
   cases; contamination/held-out policy must precede benchmark claims.

An adapter of the old agents' narrow predictor code was proposed, **not built or
scored**. Some generator arrays are missing. Any future adapter must be labeled,
not presented as the original submission or a clean new benchmark.

## 4. Earlier completed work: do not reopen it by mistake

| Thread | Final state / entry point |
|---|---|
| R5 stopped BLOB2v2r2 pilot | E1#928 reported0.68066238; E2#942 reported0.65449844. Both diagnostic due state defects. [Paired notes](../probes/blobs/agentenv/round5/resource_revision/e2_942_process_audit/POST11_PAIR_NOTES.md). No cohort mean. |
| E1#929 | Provider/server HarnessError, unscored; not science zero or cap stop. |
| E2#943 | Operator-canceled after about11min; acknowledge startup overshoot, no retained science score. |
| E1#930 / E2#944 | Canceled in setup / never admitted. No automatic resume. |
| Process audits | [E1 audit](../probes/blobs/agentenv/round5/resource_revision/e1_928_process_audit/REPORT.md) 30 checks; [E2 audit](../probes/blobs/agentenv/round5/resource_revision/e2_942_process_audit/REPORT.md) 43 checks. Complete. |
| Post11 | Paired analysis pushed in16275df: [source](../docs/blobs/measuring-evolved-worlds.html), [public page](https://swpo.github.io/physim/blobs/measuring-evolved-worlds.html). No R6 rewrite of the page was done. |
| Absolute scoring exploration | Now preserved with [warnings and original hashes](../probes/blobs/agentenv/round5/resource_revision/absolute_scoring/README.md). Raw CRPS matches12 logged values at six decimals; normalized columns are NOT adopted. |
| Round4 | [ROUND4_FINAL.md](../probes/blobs/agentenv/round4/ROUND4_FINAL.md). Keep separate from capped/invalid/diagnostic/r2 cohorts. |
| v3 evolution and harvest | Gens1–12 complete on both islands, confirmations settled, final archives secured, both campaign pods terminated. [HARVEST2](../probes/blobs/l0/deepsearch/v3_pilot/HARVEST2.md), [post12](../docs/blobs/breeding-spatial-economies.html). |
| h9 v0 | [Audit](../probes/blobs/l0/complexity/h9_review/REVIEW.md) rejects it as phenotype ranker/threshold. Do not restart a >0.2 search or use descriptor bins as biological proof. |

Old documents may mention superseded pods, cohorts or claims. The current status
and audit corrections take precedence. The cheaper-first validation preference is
native checks, then a cheap wiring smoke, one approved frontier pilot, and only
then a predeclared small panel. That ladder does not authorize any run by itself.

The earlier [L1 contract walkthrough](CONTRACT_DISCUSSION.md) is also
preserved with corrections. Only L1 was covered before the discussion changed
direction; there is no unfinished background task walking through the other contracts.

Core corrections carried forward: prediction MAE is not paired treatment effect;
local quietness is not global inactivity; spread growth is not chaos; Gaussian
leave-one-out CRPS is not an exact/achievable floor; the exploratory SDs use full
base histories, not per-anchor spans; mixed-horizon ratios need aligned reductions.
Billed dollars cannot be inferred from wall time or incomplete usage buckets.

## 5. Local inputs and a new-machine migration

**Git contains the code, reports, figures and small analysis outputs. It does not
contain all raw traces, full-field caches, GPU archives or sensitive operations
material.** [LOCAL_ASSETS.json](LOCAL_ASSETS.json) records paths, sizes,
presence and hashes/provenance. The migration inventory streamed hashes of eight
selected cache/truth/trace files; it did not extract or rehash the two big archives.

For another session on this machine, those files remain in place. For another
machine, copy only the inputs needed for the intended task:

- Reading this package or running toy/small native runner tests does not need the
  large A0 field caches or GPU archives. The documented native test binds the
  existing genome/seed and takes only a few solver substeps.
- Reproducing physics plots needs the four base/branch files for p4g2_044/s928 and
  p6g8_033/s942 (~2.49GB total). They are ZIP_STORED arrays; the scripts map them
  read-only in place. No extraction is needed.
- Reproducing R5 absolute scores needs both exact trace archives, base caches and
  frozen R5 truth files. E1's whole trace file grew after its first audit; use the
  exact nested completed trace ID, not a historical byte count or number of lines.
- v3 follow-up needs the selected harvest directories or selected members of
  `~/v3work/isl1_final2.tgz` / `isl2_final2.tgz` (~15.2GB combined). Never fully
  unpack them on this disk. Prior verified hashes and current sizes are recorded.
- The old `~/v3work/ops/recovery_20260905/state.json` is local operational history.
  Its current decisions are summarized in [SESSION_STATE.json](SESSION_STATE.json).
  Do not copy its entire contents into prompts or Git without a security review.

[UNTRACKED_LOCAL_FILES.json](UNTRACKED_LOCAL_FILES.json) accounts for the
pre-migration leftover files by category. Old logs, actor outputs, render scratch,
PID records and superseded editorial drafts stay local. **Nine old launch .sh
files may contain credentials: do not read, execute, copy or commit them.**
Do not use `git add -A`. Keys stay in `~/.prime/config.json`, not scripts or docs.
If inputs are absent, report the gap; absence is not permission to regenerate
worlds, run model rollouts, rent pods, or install an unrelated environment.

## 6. Native environments and safe checks

Use the target project's environment, not the agent orchestration kernel.
[ENVIRONMENTS.json](ENVIRONMENTS.json) records the observed interpreters and
package metadata. The project uses `.venv/bin/python`; cached-field plotting used
`~/.venvs/bk3/bin/python`. Those are different environments. Do not assume package
metadata alone identifies imported code: scripts also add local source paths,
and source hashes are in the evidence. In particular, do not automatically
“repair” the observed blobkit metadata version.

From repo root, optional short checks:

```text
.venv/bin/python handoff/check_migration.py
.venv/bin/python environments/physim/tools/test_blob_round6.py --gates toy native
.venv/bin/python probes/blobs/agentenv/round6/validate_first_pass.py
```

The first is static, with no simulator or model imports. The second runs the
bounded native tests, not a battery. The third checks existing handoff consistency
and writes its validation JSON; it does not regenerate physics. Do not run the
archived absolute_scores.py just to read the results: it runs at import and
rewrites its output JSON. Missing R5 truth raises; its build hint is not approval.
Use one native thread for analysis: OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and
MKL_NUM_THREADS =1. On a new machine, inspect the relevant pyproject/lock and
restore the appropriate project environment; do not install packages into the
agent kernel to make project imports work.

## 7. Coordination and approval safety

- No new paid model rollouts, seeds/cohorts, worlds, truth battery or GPU resources
  without explicit user approval. Documentation and existing-file inspection are
  the current task; further scientific work needs a scoped decision.
- Both campaign GPU pods are terminated; do not SSH to/recreate them. Unrelated
  resources are out of scope. Stale PID files do not authorize killing anything.
- Keep durable work under the repo or `~/v3work`, not `/tmp`. Do not read old
  launchers. If remote process control is ever authorized again, use inspected
  script files and exact process identity, not self-matching shell kill patterns.
- Background command completion did **not** wake a child agent in this runtime.
  A parent's explicit `agent_message.send` did. A registry label “completed” was
  not proof of a completed task. Require explicit DONE/BLOCKED/WAITING handoffs,
  with artifact paths and the next action; inspect actual liveness and ready files.
- For future delegated work, read the installed skill APIs. Use a bounded,
  task-specific heartbeat only when needed/authorized; avoid sleep/poll loops or
  redundant messages to active workers. Retire it after handoff/review or its
  deadline. There is **no heartbeat to revive now**.
- In this build, deleting a child accepted a child-ID string or RLMSubagent, not
  the admission RLMSpawnHandle. All old child sessions have already been removed.

### Paste into the new session

> Read SESSION_MIGRATION.md, then the current HANDOFF.md and R6 overview. The R6
> first pass is reviewed/published; no jobs, workers, heartbeats or pods need
> resuming. Keep the approval limits. Start by discussing causal noise pairing
> and the smallest world-specific confirmation experiments, not launching a new
> benchmark or restoring generic contracts/baseline gates.

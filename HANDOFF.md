> **Historical handoff notes (2026-09-07).** This file records agent-session state from
> early September; it is not the current project state. For the current project, start
> with [README.md](README.md), [REPRODUCING.md](REPRODUCING.md) and
> [REPOSITORY.md](REPOSITORY.md).

# CURRENT STATE — MIGRATION READY (2026-09-07T13:15:24.259320+00:00)

**Start a fresh session with [SESSION_MIGRATION.md](SESSION_MIGRATION.md).**
It records the user direction, approval limits, current decisions and read order.
`handoff/SESSION_STATE.json` is a curated repo snapshot; `LOCAL_ASSETS.json` maps
local-only inputs and recorded/current hashes. No old kernel variables, workers,
or heartbeat are required. The R6 first pass was pushed in **c06b2fb**.

Migration archival work only: original exploratory score files preserved with
warnings; no new score normalization, scientific simulation, model run or pod.

## Completed and reviewed, not a shipped evaluation
- Review entry: probes/blobs/agentenv/round6/README.md.
- Draft: probes/blobs/l0/deepsearch/TRACKA_R6_PREDICTOR.md.
- New isolated oracle runner: environments/physim/physim/blobround6.py.
  Submitted API remains predict(actions,queries,n_samples,seed) from fixed opaque
  t0; no public history/anchor/geometry. Private OracleRunner has separate required
  truth_seed. No fixed L1–L4 mentor syllabus.
- Worker and independent root tests:31/31 PASS;25toy/API/checkpoint+6native;
  max6substeps(0.12tu). No full old-truth parity, scorer, sandbox, resource limits,
  production integration, or long-horizon performance proof.
- Both privileged physics dossiers are COMPLETE at round6/physics/p4g2_044/
  and p6g8_033/. Root read reports and key figures. Source-off spot/stripe
  changes, negative structures missed by home probes, shared filters and gated
  halos are candidates; no general law/chaos/organism identity proven.
- Real paired field effects replace the earlier invalid MAE-as-effect inference.
  Existing control/treatment caches use common state/RNG. PolicyA prototype does
  NOT couple sham/treatment noise that way; resolve that gate before a battery.
- All three workers sent explicit final handoffs and were retired. User-approved
  watchdog95f1c473-ed4e-4edf-be8b-509c91ffd375 was deleted after review. No
  worker, plotting/test process, evaluation monitor, or pod is left running.
  COORDINATION.json records recovery of finished background jobs and closure.

## Next decision, not an automatic launch
Review dossiers; choose one/two phenomena and minimal confirmatory experiments.
Resolve causal noise pairing and exploration/evaluation ranges; then bound costs.
No new scientific sims, seeds/cohorts, truth battery, paid model run or pod is
currently authorized. The transport whole-state GET/PUT race still needs a native
regression/fix before ANY rollout. Privileged source/dossiers/cache must be excluded
from agent access; published worlds are development cases, not uncontaminated tests.

## Closed work and corrections to preserve
- Post11 paired E1/E2 audits pushed16275df. E1 audit30checks; E2 audit43checks.
  Both r2 reported completions remain diagnostic, not a clean benchmark. E1#929
  unscored HarnessError; E2#943 canceled after~11min; E1#930 setup canceled;
  E2#944 not admitted. No relaunch, cohort pooling, or canceled-task zeros.
- Absolute-scoring script/JSON/log are now archived unchanged in the migration
  commit at probes/blobs/agentenv/round5/resource_revision/absolute_scoring/,
  with README.md caveats and
  original hashes. Raw CRPS matches12 values at six decimals; normalization is NOT
  adopted. Full-base is not pre-anchor, LOO is not an exact achievable floor, and
  mixed-horizon ratios need aligned reductions. Do not use as a fixed0–1 score.
- Sensor-local quietness is not global deadness; noise growth is not chaos;
  prediction error is not paired intervention effect; metrics do not replace
  per-world physics. New dossiers preserve single-path/quantization limits.
- Both campaign GPU pods remain terminated. Never fully unpack final archives,
  never read old launcher .sh files (credentials); durable scratch ~/v3work.
- R6 first-pass files ship together with this handoff. Publication receipt and
  exact operational state are in ~/v3work/ops/recovery_20260905/state.json.

---
# HISTORICAL STOPPED-RUN HANDOFF — 2026-09-06 03:45 UTC

## STOP: no further benchmark models/seeds/worlds authorized
User asked to cancel queued runs to protect credits, leaving current runs to
finish. Both evaluators have now exited. No automatic resume/relaunch.
- E1#928 completed: reported skill0.68066238 (3h34m48s).
- E2#942 completed: reported skill0.65449844 (5h49m22s).
- E1#929 ended with HarnessError from provider/server mid-response; UNSCORED,
  not a sciencezero or resource-cap stop. Saved before operator cleanup.
- E2#943 slipped into startup03:21:52 before the admission fence was armed
  at03:28; root canceled it03:33:11 (~11min). No retainedscience score or
  completeusage total; do not pretend it never started.
- E1#930 scheduler slot opened but was canceled during setup before model
  stage; E2#944 was not admitted. They must not be resumed.
- Native runner releases semaphore before persistence; Ctrl-C/SIGTERM is not
  admission-only. Root added exact-parent PID/birth/commandhash NEW-server
  fences (commit8d03412) and tested event-driven kqueue completion watchers.
  Existing experiments were unchanged; watchers stopped evaluators only
  after named current terminal records were saved. Both fences removed.
- Evaluators27323/27324 exited130; no active inference jobs. Repeating eval
  heartbeat f80768c7-a2cb-4766-ba37-19c6ce9680cc DELETED. No polls needed.

## Completed-run audit ready (reported scores are PROVISIONAL)
Report: probes/blobs/agentenv/round5/resource_revision/e1_928_process_audit/REPORT.md
(commit4f80805;30parent-validated checks; exacttarget trace0bdd699154ee4e1d96aac4e0961bc11d).
-1216completed modelcalls +23error attempts.4,818,550reportedprompttokens
 include cachewrites;117,000,774cache-read;1,199,851output.153,020reasoning
 is a SUBSET of output, not an additional charge. Billed$ unavailable.
-1065distinct environment requests vs891persisted turns;181successful fork
 replies but145uniqueIDs. Distinctparallel toolcalls returned SAME ID at
 DIFFERENTanchors; concurrentbasereads repeatedadvancingtimes. Strong
 whole-state GET/fn/PUT lost-update evidence, not random128bitcollision.
-Physics/state history and meters are not a trustworthy exactledger. Do not
 promote reported+0.681 as cleanbenchmark/theory-learning proof.
-L3F/L3E use recorded-history interpolation/counting insidebase2500. Both
 drawn dose means use undisturbedrecord+uncertainty; learnedport2mean unused.
 No customdynsim in submittedpath. No post-ready worldaccess observed; all
 six E1payloads accepted. E2process strategy not audited.
-NEXT_NATIVE_TEST.md is a cheap deterministic barrier/event transport-test
 recipe, not executed. Need state-transaction correctness + replay/no-dose
 shortcutcontrols before more paid models. No productionracefix applied.

## GPU / final evolution: completely secured and terminated
Both campaign pods are gone; do NOT reconnect/recreate. Otherprojects’ pods
out of scope. Final archives immutable and verified locally:
~/v3work/isl1_final2.tgz —7526611213B,SHA256
7ef7e373677750b16cef373623e1b6bbecd400cea312ba359a940fd5fe3f40c3
~/v3work/isl2_final2.tgz —7667929517B,SHA256
cb00bc78b38c7edf28cbb0a6128b721eec5a345810b26460f390992f72a68a81
Both settledgen12; independentcriticalfile hashes/tar integrity verified;
verificationJSON/release receipts in ~/v3work/ops/recovery_20260905/state.json.
No fullunpacking: disk14–16GBfree. Selectedmetadata/films (~200MB/island)
under ~/v3work/harvest2/v3cont-N; originalgen7snapshots/harvest preserved.

## Published science corrections / media
-HARVEST2 audited27da8ab: rawdata preserved;11baseline wrong-genome seed3,
29unsafe archive reblend physical-genome joins; samegenome vs sameIC separate.
C9proxy max.8895,notproofheterogeneouscompartments; no causalrespecclaim.
-h9review6f9723e: v0NOT phenotype ranker/biologicalcutoff; nofullscan or
selection. Toycounterexamples disprove earlierceiling/homogenizationclaims.
-post12cb4d73b live: finalauditedresults,correctedcharts,6wide re-sim films.
Replayhelperd257b8a;48sourcepins verified,known2stale0.3.5lockentries explicit.

## Final handoff (no work or benchmark runs active)
Post11 current-method/cost/process audit is updated and pushed17f0806,
including all six final dispositions, E1-only methods/tokens, concurrency
caveat and a future-only cheaper test ladder. Index row11 updated; post12
unchanged. Documentation child completed and was deleted. All evaluators,
completion watchers and recurring evalheartbeat are stopped. No further
paid benchmark/model/seed/world runs are authorized. No concurrency fix
or fresh benchmark has been run. User can review the E1audit and post11.
Keep oldcapped, invalidmode, diagnostic and reduced fresh cohorts separate.
Next work requires user direction; cheapest proposed action is the native
concurrency/state-transaction test and record/no-emission shortcut controls.
Operatorcontrols/logs/specs and exactfreshdirs are in recovery state.json.

---
## Historical handoff (older claims may be superseded above)

# CONTEXT HANDOFF (2026-09-02) — full program state for a fresh prime-agent context
(Repo = single source of truth. Everything below is committed or referenced by path.)

## WHERE EVERYTHING STANDS
1. V2 EVOLUTION CAMPAIGN: COMPLETE. Final union 423 cells (230 minted), champion 91.16
   (3|grow|rotor|liquid). Analysis in probes/blobs/l0/deepsearch/v2_analysis/ (LINEAGE,
   OPERATOR_STATS, COMPLEXITY_TRAJECTORY, CAP_RIDERS + film_candidates). Posts 10
   (evolving-at-scale) + slow-mo clips live. Total spend ~$515.
2. BLOBKIT: 0.3.4 (devrec+async engine, 2.18x claim, battery timeout guard). Perf suite
   probes/blobs/blobkit/perf/ (bench tiers, frozen workloads, HYPOTHESES/GAINS).
   Roadmap 0.4: driver-native devrec, CREC phase 2, research_overlay for make_bundle
   (IDEAS.md), in-runner gen limits. RETROSPECTIVE.md + check taxonomy in MANIFEST.
3. V3 EVOLUTION (Track B): metrics_v3/assay_v3/operators_v3 VALIDATED (gate table in
   probes/blobs/l0/complexity/VALIDATION_V3.md; C9 = t9/s9/e9/r9 spatial economy;
   merge_spatial_ic). PILOT RUNNING NOW: 2 pods (v3pilot-1/2, /tmp/v3pilot_fleet.json
   — COPY BELOW since /tmp dies), islands 1-2 x 12 gens from v2 top-100 + atlas
   immigrants. Concurrency fix for ic-lanes deployed mid-run (takes effect next gen).
   Success = >=5 economy cells C9>=0.4 & interest>=60. Budget cap $150 (~$3/h burn).
   PILOT PODS: v3pilot-1 = pod f6a99cd30aae4c... ip 150.136.214.95 island 1;
               v3pilot-2 = pod 2d1c7688beee4c... ip 130.210.31.82 island 2.
   Bundle+workspace: ~/v3work/v3bundle (durable); venv ~/.venvs/bk3.
4. AGENT ENV (Track A): environments/physim BLOB tiers. History: round1 (BLOB-E1, leaky
   iface) fable 0.689/sol 0.08 vs scripted 0.60; round3 (BLOB-E1r3, tight iface) fable
   0.632/sol 0.05 — leak value ~0.06; ZERO actuator use except one u1-identification
   test (fable r3-2). ROUND 2 CONTRACT SYSTEM (clean-slate design,
   TRACKA_CLEANSLATE_EVAL.md): L1 pose-targeted, L2 hidden-sensor nowcast, L3F/L3S/L3E,
   L4+dose-leg, skill-normalized scoring, world-adaptive menus (BLOB2-E1/E2, commit
   bcac15d). ROUND 4 EVALS RUNNING: sol DONE (negative skill everywhere: -0.42..-0.67
   E1, -0.22..-0.67 E2); fable partial (E1: 0.29 + errors; E2: 0.16 + errors);
   RESUMES IN FLIGHT for fable E1+E2 (transient pinference 5xx HarnessErrors;
   logs probes/blobs/agentenv/round4/). Scripted baselines: E1 +0.238, E2 +0.233
   (results/smoke_blob2_*.json). L2 is open headroom (scripted actor ties baseline).
5. DESIGN DOCS (all in probes/blobs/l0/deepsearch/): V3_TRACKB_SPEC.md,
   TRACKA_AGENTENV_SPEC.md (probe-device design), TRACKA_R2_CONTROLS.md (control-
   surface evolution R1->R3-final: fixed global undocumented convention),
   TRACKA_CLEANSLATE_EVAL.md (capability ladder + overlap audit).

## KEY USER POLICIES (standing)
- Parallelize-max at flat cost; budget ceilings advisory-then-discuss ($600-era done;
  pilot cap $150); measure-don't-guess (benchmark rows before claims); science changes
  only for order-of-magnitude wins; simple != documented (barrier by undocumentation,
  fixed global conventions); no /tmp for anything durable; harness = verifiers coding
  harnesses (claude_code/codex); eval models = frontier-first (fable-5 + gpt-5.6-sol).
- RED protocol for underperforming engines: stop production, instrument, extract
  minutes-scale repro, iterate offline, gated relaunch.

## IN-FLIGHT / NEXT ACTIONS
- [ ] fable round-4 resumes complete -> full BLOB2 table -> narrate + post 11 results
      section update.
- [ ] v3 pilot: monitor gens (concurrency fix pace), unions at 7/final, harvest,
      verdict vs success criteria, terminate pods (cap $150).
- [ ] post 11 results + round-2 findings writeup.
- [ ] Later: L5 preparation + L6 executable-theory tiers (round 3-4 of clean-slate);
      E2 eval read; v4 gluing after agent-eval phase settles; blobkit 0.4.
- Local processes RIGHT NOW: 2 eval resumes (pids in round4/*.pid), 1 local smoke
  (~/v3work/smoke.pid — verifying ic-concurrency patch; informational only, pods
  already patched).

## OPERATIONAL GOTCHAS (hard-won this context)
- ssh+nohup: launch via SCRIPT FILES only; never pkill patterns matching your own ssh
  cmdline; never trust remote watchers — poll from controller.
- macOS: no `timeout` cmd; /tmp GC kills venvs/workspaces; BLAS threads MUST be pinned
  (OMP_NUM_THREADS=1 etc) or 800%-CPU thrash.
- Children die in setup/reading phases: revive write-first with extracted facts
  embedded; after 3-4 deaths do it inline.
- eval runner: .venv/bin/eval physim -n 3 -m <model> --env.taskset.difficulty <tag>
  --env.scientist.harness.id <claude_code|codex> --env.scientist.runtime.type docker;
  --resume <output-dir> reruns errored rollouts only.
- pinference transient 5xx = HarnessError mid-rollout; resume fixes; not our env.


## UPDATE 2026-09-04 (post prime-agent-update context)
1. V3 PILOT: COMPLETE + TERMINATED. RED-protocol mid-flight: launch was 10-20x too
   slow (ic lanes serial on CPU pre-GPU-batch; C9 rescore serial on main thread).
   Fix = blobkit 0.3.5 (job dicts carry per-lane "ic" -> init_soup_gpu_batch ics
   hook) + pilot-2 worker (ic lanes ride GPU tensor, version-gated; C9 rescore in
   spawn ProcessPool; commits 9a07779). Gated tests green (ic-injection differ test,
   6-job end-to-end, rescore exact-match). Both islands ran gens 1-7 (~3.5-4.5h/gen),
   confirms settled through gen 7 (two-stage async drain: s3g6+s2g7 -> ingest3 6 +
   ingest2 7 -> s3g7 -> ingest3 7; CONFIRM7_SETTLED in driver.log both islands).
   SNAPSHOTS: ~/v3work/isl1_final.tgz (7.7GB, 1103 entries), isl2_final.tgz (6.7GB,
   1053) — full out/ (results, archive, jobs, elite npzs), configs, campaign.log.
   Pods TERMINATED ~03:00/05:45Z Sep 4. Total spend ≈ $110-115 of $150 cap.
   SUCCESS CRITERION MET AT GEN 3: >=5 economy cells target vs 45 (isl1) + 34 (isl2)
   distinct cells with C9>=0.4 & I>=60 (from results.json rows; archive entries lack
   C9 — ingest field subset — join results.json at harvest). Continuation to gens
   8-12 possible from snapshots: restore ~/islN, pod_run_batch.sh 8 12.
2. ROUND 4: FINAL + PUBLISHED. fable E1 +0.308 / E2 +0.287 (n=3) vs scripted
   +0.238/+0.233; sol negative everywhere. probes/blobs/agentenv/round4/ROUND4_FINAL.md.
   POST 11 rewritten current-first (BLOB2 ladder w/ shipped semantics from
   blobround2.py) + pushed (a1d1123). Local eval resumes done; launch detached
   (start_new_session) or agent restarts kill them — pids die with prime-agent.
3. ROUND 5 DIRECTION (user-agreed, spec doc pending): (a) budgets -> huge
   unadvertised safety caps (utilization data: injection hit 0.95, replicas 12/12 —
   limits DID bind in round 4); (b) spend metered silently -> post-hoc Pareto
   (skill vs spend); strip budget from probe_status/tool returns/coaching errors;
   (c) span/lock-at-inject removed -> anchor-parameterized contracts (anchor =
   (world line, t)): free exploration forks + reset; scored contract instances
   harness-issued (fixed per world+seed) for comparability; truth = fresh replicas
   per (anchor, protocol); baselines per anchor. Scripted actor re-played, floors
   re-derived; round-4 numbers stay as BLOB2-v1 row. Agent-authored contracts =
   later L6 lane.
4. NEXT: harvest (untar snapshots -> merge islands, join C9 from results.json,
   economy-cell census, C9 trajectory by gen, operator stats esp. merge_spatial_ic,
   film candidates) -> pilot verdict doc -> v3 full-campaign go/no-go + round-5 spec.

5. POST-11 REPUBLISH AFTER v2.1 IMPLEMENTATION (user request 2026-09-04): once the
   round-5/v2.1 contract system (TRACKA_R5_ANCHORS.md: category-anchored contracts,
   closed-book agent-triggered reveal, silent caps) is IMPLEMENTED and floors are
   re-derived, update docs/blobs/measuring-evolved-worlds.html (live at
   swpo.github.io/physim/blobs/measuring-evolved-worlds.html) to describe v2.1 as
   the current instrument (v1 + round-4 numbers stay as the tagged historical row).

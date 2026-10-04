# V2.1 IMPLEMENTATION BRIEF (BLOB2v2 — category-anchored, closed-book reveal)

> **Historical brief (2026-09-05)** for the retired round-5 BLOB2v2 task. Its modules
> now live under `probes/legacy/physim/` and its results under
> `probes/blobs/agentenv/results/`; the current environment is described in
> [README.md](README.md).
SPEC (authoritative): probes/blobs/l0/deepsearch/TRACKA_R5_ANCHORS.md (v2.1, 627
lines). Read it fully first. This brief adds engineering constraints only.

## Hard constraints
1. v1 MUST keep working bit-identically: tags BLOB2-E1/E2, blobround2.py,
   the v1 blob.py surface, round-4 outputs. Implement v2 as NEW code paths:
   - physim/blobround5.py (instances, syllabus, truth, ladders, scoring)
   - blob.py: v2 mode branches (state.round5 flag by difficulty tag) — shared
     helpers fine, v1 behavior frozen.
   - taskset: new difficulty tags BLOB2v2-E1 (world p4g2_044, seeds 928/929/930),
     BLOB2v2-E2 (p6g8_033, seeds 942/943/944).
2. Instance draws: hash-deterministic per (world, seed), salt "r5_instances_v1"
   (blobround2 _rng pattern). Truth ensembles frozen-once keyed
   (world, seed, instance-id); cache under the existing cache namespace with a
   NEW prefix r5_. Truth noise streams salted differently from fork streams
   (spec 2.2/2.6): fork salt includes rollout nonce + fork counter; truth salt
   is build-side only. Reveal must not leak instance data in ANY tool output
   before probe_ready (status shows syllabus only).
3. Tools (spec 2.5): probe_status [A+B], probe_read(ctx,...) [A], probe_wait
   [A], probe_adjust(ctx,...) [A], probe_inject(ctx=fork only,...) [A],
   probe_fork(anchor) [A], probe_discard(fork_id) [A], probe_ready() [A->B],
   probe_submit(instance, payload) [B]. Phase errors are GENERIC (no cost/
   economy vocabulary anywhere). No budget/costs/pricing/replicas_left fields
   in any agent-visible output. Base record fully readable t in [0,2500].
4. Silent meters + caps (spec 2.7): sensor node-tu, adjust cu, injection
   amp-tu (v1 price fn as METER), fork spawns (cap 400), open forks (cap 8),
   live sim tu (cap 100,000), resets (uncapped), time_to_ready (sim_tu +
   turns at probe_ready; no cap). Caps enforced with a generic "instrument
   saturated" error (should never fire). ALL meters logged into rollout
   metrics (report/metrics plumbing) as meter_* keys + time_to_ready.
5. Scoring (spec PART 3): skill = clip(1 - CRPS/CRPS_best_rung, -1, +1);
   unsubmitted = -1; reward = mean over the 6-instance menu. Ladders fit to
   PRE-ANCHOR base-record data per instance (climatology/persistence; AR(2)
   only L3F). Never-ready episode = all -1. Payloads {"mean","sigma"} arrays,
   shape-checked, last-accepted-wins (v1 submit mechanics).
6. Tier truth builders (spec PART 4 + syllabus in 2.3): L1 hidden adjust
   sequence (len 1-3, u in [-1,1]^3 continuous, apparatus-accepted draws) on
   fresh fork from t_a, read device 0 after final command; L2 hidden 13-slot
   cluster reading at t_a (reuse v1 KH cluster machinery); L3F device-i
   streams at t_a + {5,25,100,400} (E1) / {25,100,400} (E2) undisturbed
   (single-member base-realization truth for legs with H<=25 per spec 2.6
   degenerate rule; ensemble truth otherwise); L3E 16x50tu crossing counts
   from t_a (E1); L3S 200tu-window global mean/var ending t_a+400/t_a+800
   (E2); L4 hidden emission port/amp[1.5,3.0]/dur[5,20] from t_a, device-1
   streams at lags {10,25,50,100,175,250}; L4D same with amp[0.30,0.90],
   lags {25,75,150}. Anchors t_a continuous-uniform [600,2300], realized at
   sim resolution (off the 5tu read grid).
7. Scripted floor actor v2 (spec PART 5): two-phase classical reference —
   generic exploration program (full base-record read + per-port calibration
   forks incl. a throwaway adjust bullet), early probe_ready, answers from
   classical stats at revealed params. Lives beside the v1 actor; runnable
   via the existing smoke harness; NO fork-ensembling.
8. GATES to implement + run (spec PART 6) as a self-test script
   environments/physim/tests_or_scripts location matching existing project
   conventions (inspect how v1 gates/smokes are organized, e.g.
   results/smoke_blob2_*.json producers):
   G-R1 reveal-leak: byte-identical pre-reveal tool outputs under instance
        salt redraw ("r5_instances_v1" vs test salt).
   G-R2 post-reveal isolation: every world tool returns phase error after
        probe_ready; submit/status still work.
   G-R3 replay==live at anchor: base-record replay vs live re-sim agreement
        at fork spawn (existing A0 pattern).
   G-R4 caps: synthetic saturation triggers generic error; normal smoke has
        ZERO cap hits.
   G-R5 scripted actor smoke on both worlds x3 seeds: all instances
        submitted, floor table written (results/smoke_blob2v2_*.json),
        L4/L4D floor positive-ish, L1 near floor per spec.
   G-R6 determinism: same (world,seed) -> identical instance menu + identical
        truth hashes across two builds.
## Process
- Work through the project environment (uv run / .venv) from the repo root;
  the env package lives at environments/physim (its own venv/deps per repo
  conventions — inspect environments/physim/pyproject.toml first).
- Iterate until ALL gates green. Do NOT commit; leave working tree for review.
- Reply to parent with: files added/changed (+line counts), gate results
  (G-R1..G-R6 pass/fail + the floor table numbers), any spec ambiguity you
  resolved (explicit list), and the exact eval command for a v2 rollout.

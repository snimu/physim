> **Historical report (February 2026)** on the M0 environment, now archived in
> `probes/legacy/physim/`. Its commands and module paths do not apply to the installed
> `physim` package. For the current system, see [README.md](README.md).

# physim M0 report — does difficulty track model performance?

*2026-02-11. Environment: `environments/physim` (verifiers v1 taskset, chat tier /
`null` harness). One task = one hidden world (seeded); the agent explores through
the anonymous-port interface within a tick budget, then answers 12 prediction
contracts (4 per stratum S1/S2/S3) scored `exp(-|err|/scale)` against fresh
truth ensembles, `scale = max(3*ensemble_sd, 10% channel range)`.*

## The environment in one paragraph

Hidden micro-world: modular tanh lattice (locality + modularity + heterogeneity
motifs), collective bistability with hysteresis — the "deep structure" to
discover. Interface: `n_in` anonymous input ports, `n_out` anonymous noisy
sensors (random gain/sign/offset, shuffled, some dead), persistent state, tick
budget. Difficulty presets scale four axes together:

| preset | modules (k*) | ports | dead | sign flips | meas noise | what it adds |
|---|---|---|---|---|---|---|
| D0 | 1 | 6 in / 24 out | 0 | none | 0.02 | clean senses, one collective mode |
| D1 | 1 | 6 / 32 | 4 | 35% | 0.05 | murky senses, same law |
| D2 | 3 | 6 / 36 | 4 | 35% | 0.05 | three semi-independent collective modes |
| D3 | 6 | 8 / 48 | 8 | 40% | 0.07 | six modes + weak global tie, tighter budget |

Contract strata: S1 = weak push + relaxation; S2 = held moderate drives
(uniform/single-port/subset); S3 = strong drive + release, incl. opposite-sign
push-past (hysteresis memory).

## Results

Scripted baselines (3 seeds each; play through the same JSON interface):

| | D0 | D1 | D2 | D3 |
|---|---|---|---|---|
| null (answer 0, no exploration) | 0.04 | 0.03 | 0.06 | 0.04 |
| tail (resting state predicts everything) | 0.42 | 0.50 | 0.43 | 0.34 |
| reference (scripted scientist, ~30 experiments) | 0.72 | 0.72 | 0.65 | 0.67 |
| replication reference (run the protocol once, report it) | ~0.98 | ~0.98 | ~0.98 | ~0.98 |

Models (chat tier, ≤40 turns, 3 seeds per cell; D0 cells include 2 extra
earlier rollouts):

| model | D0 | D1 | D2 | D3 |
|---|---|---|---|---|
| google/gemini-3.5-flash | **0.72** | 0.58 | 0.54 | 0.35 |
| deepseek/deepseek-v4-flash | **0.64** | 0.56 | 0.52 | 0.38 |
| openai/gpt-5-nano | 0.12 | 0.11 | 0.13 | 0.04 |

Difficulty ↔ reward (Spearman, per-rollout): deepseek ρ=−0.49 (p=0.04),
gemini ρ=−0.42 (p=0.13), pooled competent models **ρ=−0.50 (p=0.003)**.

## Reading

1. **The difficulty axis works.** Both competent models degrade monotonically
   D0→D3; pooled correlation is significant at n=32 rollouts. The axis is
   compound (port opacity + number of collective modes + noise + budget), by
   design — it's the D-ladder, not a single knob.
2. **The task discriminates models sharply.** gemini-3.5-flash ≈ scripted
   reference at D0 (0.72 vs 0.72) but falls to 0.35 at D3 vs reference 0.67;
   gpt-5-nano barely beats the null baseline anywhere (it explores 1–3% of
   budget, then guesses; its coverage 0.4–0.7 with near-zero accuracy = badly
   calibrated *and* wrong).
3. **The scripted reference is an honest floor-of-competence**: no model beats
   it at any difficulty yet. Models lose mostly on S2/S3 (per-port structure
   and hysteresis memory), exactly the strata that require deliberate
   experiment design rather than passive observation.
4. **Failure modes observed in traces**: answering from the *current* world
   state instead of fresh-state reasoning (fixed with a prompt clarification);
   exploring only 1 port; never using `reset`; spending <10% of tick budget.
   The environment surfaces experiment-design skill, not just curve fitting.

## Caveats & next

- n=3 seeds per cell is a smoke test, not a paper: variance within cells is
  large (gemini D2 ±0.39 — one rollout aced it, one flopped).
- gpt-5-nano's collapse is partly *protocol* failure (JSON discipline over 40
  turns), worth separating from scientific failure via the coding-harness tier.
- Next steps: (a) sandbox/coding-harness tier (agent writes analysis code;
  DESIGN.md v0.2), (b) policy programs + preparation/control contracts (v0.3),
  (c) simulator-submission scoring (v0.4), (d) certification meter as world
  filter + per-axis difficulty decomposition (v0.5), (e) larger grids, more
  models, r>1 rollouts per seed.

## Repro

```bash
cd /Users/spoho/Documents/prime/test/physim
uv pip install -e environments/physim
# baselines
.venv/bin/python -c "from physim.baselines import run_baseline; print(run_baseline('D0', 0, 'reference')['reward_accuracy'])"
# eval grid (needs PRIME_API_KEY)
probes/legacy/physim/run_grid.sh google/gemini-3.5-flash D0 3
# collect
.venv/bin/python -c "from physim.report import collect_traces, summarize; [print(s) for s in summarize(collect_traces())]"
```
Raw per-rollout rows: `/tmp/physim_results.json`. Traces: `outputs/`.


---

# Addendum (2026-02-11, later): stronger models, longer rollouts, and the D4 frontier tier

## What changed

- **Turn limit is ours, not the harness's**: `--env.taskset.max_turns` (default 40).
  Strong-model runs below used 100.
- **New D4 preset** ("frontier"): adds two motifs to the engine —
  per-module response rates (timescale separation, `lam ∈ [0.04, 1.0]`) and a
  **slow adaptation state** (`a += eps*(x−a)`, feedback `−g·a`, timescale ~200
  ticks). Consequences, verified: duration-dependent memory (same drive held
  60 vs 400 ticks → post-release macro differs by 0.43), slow post-release
  drift over hundreds of ticks, spontaneous relaxation oscillations
  (bistability + fatigue), hysteresis retained. 10 in / 60 out / 10 dead,
  150k tick budget.
- **New S4 contract stratum** (all difficulties): multi-stage push →
  counter-push on a port subset → 300–700-tick settle. Requires long-horizon
  understanding. Contracts stay well-posed: cross-clone sd ≈ 0.02 on S3/S4.
- Solvability floor on D4 is genuinely low: scripted reference 0.27,
  an *upgraded* scripted probe with duration features 0.30, a
  physics-informed kNN oracle (knows to integrate drive at 3 timescales) 0.21.
  Null jumps to ~0.15 (oscillation phase makes some contracts land mid-range).

## Strong-model results (null harness, 100 turns, 2 seeds; 16 contracts incl. S4)

| model | D2 | D4 |
|---|---|---|
| anthropic/claude-opus-4.8 | 0.60 ± 0.21 | 0.18 ± 0.07 |
| openai/gpt-5.2 | 0.46 ± 0.02 | 0.22 ± 0.06 |
| google/gemini-3.1-pro-preview | 0.50 ± 0.28 | 0.19 ± 0.07 |
| *scripted reference* | *0.64* | *0.27* |
| *null* | *0.06* | *0.15* |

## Findings

1. **D4 does what was asked**: the best available models score 0.11–0.28 —
   barely above the null floor, *below* the dumb scripted scientist. There is
   now a tier where frontier models can't do well yet, with large headroom
   (replication reference ≈ 0.93).
2. **Long rollouts are used but not converted**: gpt-5.2 runs 58–98 turns and
   sometimes spends 100% of the tick budget, yet S3/S4 stay near zero. The
   bottleneck is *scientific strategy* (designing duration-controlled
   experiments, discovering adaptation), not interaction quota. opus-4.8
   interestingly stops early on D4 (~30 turns) — it gives up exploring rather
   than running out.
3. **S-strata separate models**: everyone does S2 (steady drives); S3/S4
   (memory, slow modes) is where all models crash on D4 (0.01–0.26).
4. High within-cell variance (seeds differ by 2–4×) — real conclusions need
   n≥5 seeds; these are directional numbers.

## Current difficulty ladder (baseline acc, 3 seeds)

| | D0 | D1 | D2 | D3 | D4 |
|---|---|---|---|---|---|
| null | 0.04 | 0.03 | 0.06 | 0.05 | 0.15 |
| tail | 0.46 | 0.51 | 0.44 | 0.32 | 0.22 |
| reference | 0.70 | 0.71 | 0.64 | 0.65 | 0.27 |

(D0–D3 numbers now include S4 contracts; slightly different from the first table.)

## Next

- n≥5 seeds on D2/D4 for a stable strong-model ranking; add kimi-k3 / glm-5.
- Coding-harness tier so models can build duration-response curves offline
  (separates protocol failure from scientific failure).
- A D5 candidate: adaptation + modular timescales + tighter budget, or
  spatially-structured inputs requiring port-geometry mapping first.
- Consider reporting score vs. *ticks spent* curves (sample efficiency), and
  moving outputs/ to HF datasets once they outgrow the repo.


---

# Addendum 2 (2026-02-11, later still): M1 coding-harness tier, frontier pairings

## What was built

`--env.taskset.tier tools`: the world becomes a **per-rollout MCP tool server**
(`physim_run/reset/status/ready/answer`) launched inside the agent's own
container; world snapshots ride verifiers' per-rollout state channel
(`trace.state`), and scoring happens post-hoc in `PhysimTask.accuracy` from the
recorded answers — engine and truth ensembles never enter the agent's sandbox.
Coding harnesses (codex, claude_code) require `--env.scientist.runtime.type
docker`. Chat tier unchanged and regression-tested.

Harness pairing rule (user guidance + verified empirically): anthropic models
run through the `claude_code` harness (bare chat-completions against
anthropic/* return empty content on Prime Inference); OpenAI-compatible models
pair with `codex`; anything else defaults to `codex`.

## First tools-tier numbers (D4 frontier worlds, 2 seeds, docker)

| model + harness | rewards (seeds) | mean | budget used |
|---|---|---|---|
| gpt-5.2 + codex (D0 smoke) | 0.49 | — | 0.88 |
| gpt-5.6-sol + codex | 0.26, 0.23 | 0.24 | 0.52–0.66 |
| claude-opus-5 + claude_code | 0.41, 0.23 | 0.32 | 0.19–0.28 |
| claude-fable-5 + claude_code | 0.38, 0.36 | **0.37** | 0.16–0.45 |

Chat-tier D4 reference points: opus-4.8/gpt-5.2/gemini-3.1-pro 0.18–0.22,
scripted reference 0.27, null 0.15, replication ~0.93.

## Findings

1. **The harness helps — the frontier moved but did not fall.** Best pairing
   (fable-5 + claude_code, 0.37) roughly doubles the chat-tier frontier and
   clears the scripted reference (0.27), but remains far from replication
   (~0.93). D4 stays a genuinely open tier even for the strongest current
   setup, which is exactly the regime the benchmark wants.
2. **The D0 smoke run shows the mechanism works**: gpt-5.2+codex spent 88% of
   the tick budget building offline fits and hit S4=0.96 (chat tier: S4≈0.2)
   — code + files convert budget into long-horizon accuracy when the world is
   easy enough to model.
3. **On D4 the models still under-spend budget** (fable 0.16–0.45) and S1
   (weak-push relaxation, most sensitive to the adaptation dynamics) stays
   ≤0.35 everywhere: nobody has discovered the slow fatigue variable yet.
4. Long rollouts happen naturally in this tier (66–173 turns, ~10–25 min per
   rollout); tick budget, not turn count, is the binding constraint now.

## Operational notes

- anthropic + claude_code occasionally hits transient `aux call failed: 404`
  warnings (retries succeed); one gpt-5.2+codex rollout errored out entirely
  (`reward=0.000` row) before a retry passed — treat single-seed tools-tier
  numbers with care.
- Rollouts run in `python:3.11-slim` containers; the MCP server is reached at
  `host.docker.internal`.

## Next

- n>=5 seeds per pairing; add gemini-3.1-pro + codex.
- Give the tools tier a persistent scratch summary of experiment history in
  the prompt? (models re-discover basics each rollout)
- HF dataset upload for outputs/ (repo now 30+ MB of traces).


---

# Addendum 3 (2026-02-11): rollout cost accounting (tools tier, D4)

Per-rollout usage from `traces.jsonl` model-call records (prompt tokens are
dominated by cached context re-reads; costs shown as cached + fresh):

| pairing | seed | model calls | fresh prompt | cached prompt | completion | reasoning | wall time | reward |
|---|---|---|---|---|---|---|---|---|
| gpt-5.2+codex (D0) | 0 | 106 | 0.07M | 4.6M | 31k | 21k | 14 min | 0.49 |
| gpt-5.6-sol+codex | 0 | 66 | 0.10M | 4.3M | 12k | 8k | 8 min | 0.26 |
| gpt-5.6-sol+codex | 1 | 98 | 0.10M | 5.4M | 17k | 11k | 12 min | 0.23 |
| opus-5+claude_code | 0 | 67 | 0.24M | 4.1M | 111k | 24k | 25 min | 0.41 |
| opus-5+claude_code | 1 | 93 | 0.27M | 6.5M | 125k | 26k | 36 min | 0.23 |
| fable-5+claude_code | 0 | 173 | 0.60M | 50.9M | 241k | 28k | 63 min | 0.38 |
| fable-5+claude_code | 1 | 113 | 0.70M | 22.1M | 191k | 37k | 52 min | 0.36 |

Observations: (1) 60–170 model calls per rollout; effective context stays
manageable because raw data lives in sandbox files. (2) fable-5 reads 5–10x
more cached context than the others (long-context strategy) and takes ~1h per
rollout; sol is 5x cheaper per rollout at ~35% lower score. (3) Chat-tier
rollouts (null harness) are far lighter: ~25–40 calls, <1M cached, 2–15 min.

# Addendum 4: world isolation audit (MazeBench pattern check)

- Engine + truth ensembles run evaluator-side only. Tools tier: the MCP world
  server is a separate host process outside the agent's docker container
  (reached via host.docker.internal); the agent container has no volume
  mounts, no engine code, no physim package.
- Tool responses expose only: tail_mean/tail_sd/series of chosen channels,
  ticks_run, budget_left, phase, interface card, contract specs
  (protocol + channel + stat), and answer receipts. Scoring internals
  (mu, tau, scale, strata, per-contract detail) are computed post-rollout in
  `Task.score` and never flow through a tool.
- The per-rollout state channel (world snapshots) is HMAC-authenticated
  between server and host; the agent receives only the MCP URL.
- New: `PHYSIM_WORLD_SALT` env var mixes an evaluator-side salt into world
  generation and noise streams, so the public engine code + a guessed seed
  cannot reproduce a live world (unset = reproducible published defaults).
  Residual risk accepted: local subprocess runtime (debug only) offers no
  isolation; use docker/prime for real evals.


---

# Addendum 5 (2026-02-11): n=5 D4 pairing statistics + protocol-robustness fixes

## Final D4 leaderboard (tools tier, 5 seeds each, latest run per seed)

| pairing | reward (mean±sd) | budget used | S1 | S2 | S3 | S4 | coverage |
|---|---|---|---|---|---|---|---|
| claude-fable-5 + claude_code | **0.349 ± 0.04** | 0.32 | 0.21 | 0.42 | 0.48 | 0.29 | 0.66 |
| claude-opus-5 + claude_code | 0.324 ± 0.11 | 0.41 | 0.23 | 0.39 | 0.43 | 0.25 | 0.79 |
| gpt-5.6-sol + codex | 0.244 ± 0.07 | 0.54 | 0.21 | 0.39 | 0.19 | 0.19 | 0.47 |
| gemini-3.1-pro + codex | 0.194 ± 0.12 | 0.01 | 0.22 | 0.27 | 0.13 | 0.16 | 0.96 |
| *scripted reference (5 seeds)* | *0.274 ± 0.04* | *0.11* | | | | | |
| *tail baseline (5 seeds)* | *0.211 ± 0.04* | | | | | | |
| *null baseline (5 seeds)* | *0.133 ± 0.05* | | | | | | |
| *replication reference* | *~0.93* | | | | | | |

Reading: fable-5 is the only pairing clearly above the scripted reference
(0.35 vs 0.27, and the most consistent, sd 0.04). opus-5 matches it on mean but
with 3x the variance. sol spends the most budget for less score. gemini
barely explores (1% budget, ~12 turns) and lands at the null floor + eps; its
0.96 coverage with bottom-rung accuracy = wide honest intervals around
guesses. D4 remains open: best mean 0.35 vs 0.93 achievable.

Budget-use vs reward across all 20 rollouts: Spearman rho=0.14 (p=0.55) —
spending ticks does not by itself buy score; *what* you measure matters more
than how much. (sol: most ticks, mid score; fable: moderate ticks, top score.)

## Environment robustness fixes shipped during these runs (v0.1.2)

Diagnosed from failing gemini+codex traces (reward 0.000, n_answered 0):

1. **Tool-arg normalization**: some MCP clients deliver structured arguments
   as JSON strings (sometimes double-encoded, sometimes per-element).
   `physim_run.segments` and `physim_answer.answers` now decode recursively
   and return instructive errors instead of "segment 0 must be an object"
   loops. (Root cause of gemini's zero-scores: it fumbled the format 3-4x,
   then gave up and answered zeros "due to constraints".)
2. **Premature-ready guard**: `physim_ready` with <5% budget used requires
   `confirm=true` (accidental phase transitions locked agents out of
   exploration).
3. **physim_answer during exploration** now errors instead of silently
   issuing contracts.
4. Version-bump note: the tool server installs the env package by sdist;
   uv caches wheels by name-version, so tool-code changes REQUIRE a version
   bump in pyproject.toml to reach the server runtime.

Even after the fixes, gemini-3.1-pro's conduct is unchanged (satisfices in
~12 turns) — that is a model finding, not an env artifact.


---

# Addendum 6 (2026-02-11): trace gallery + workspace artifact collection

- **Trace gallery** at `docs/rollouts.html` (GitHub Pages): per pairing x
  difficulty, best/median/worst rollouts rendered as lab reports — condensed
  experiment log (every physim tool call + world response), the agent's own
  workspace files, and per-contract truth-vs-answer tables. The standout
  artifact: claude-fable-5's `MODEL.md` on D4 correctly identifies "6 bistable
  relaxation-oscillator units", maps ports to units with polarities, measures
  release schedules and mutual entrainment (period ~390-430), and ships a
  per-contract prediction procedure — readable theory, 0.31 reward (its
  jitter-accumulation limits are visible in the same file).
- **Workspace artifact collection** (v0.1.3): tools-tier tasks now declare the
  agent workspace as a verifiers artifact; `PhysimTask.finalize` collects it
  (tar, capped, junk-excluded) into `trace.state.artifacts`, and scoring
  extracts text files into `trace.info["physim"]["workspace"]` (durable in
  traces.jsonl). Rollouts predating this recover files best-effort from
  Write/Edit tool-call arguments; bash-heredoc writes in old rollouts are lost
  — the motivating gap. Validated end-to-end: gpt-5.2+codex D0 rollout
  scored **0.73** (new codex D0 best) and its collected `model.py` contains a
  two-basin affine model with switching threshold and time constant — theory
  as executable code, now preserved.


---

# Addendum 7 (2026-02-11): M2 + M3 shipped — policies, preparation contracts, executable theories

## What shipped (v0.2.0-0.2.3)

- **Policy jail** (`physim.jail`): agent code runs in a hardened subprocess
  (restricted builtins, no imports — tolerant rewriting of `import math/numpy`
  since models type them reflexively — curated numpy without file IO, rlimits,
  per-tick timeouts). Escape battery passes.
- **Closed-loop experiments**: `physim_run_policy(code, t)` — policy(t, y, mem)
  executed tick-synchronously against the live world.
- **Preparation contracts (M2)**: "steer a fresh draw into sensor band B, hold
  after release" — bands placed on reachable branch values by construction;
  scored as success rate over 5 fresh clones. `physim_answer_prep(id, code)`.
- **Theory submission (M3)**: `physim_submit_theory(code)` — an executable
  init/step simulator of the sensors; scored post-hoc by simulating every
  prediction-contract protocol and comparing tail statistics on the same scale
  as answers (report-only reward weight for now).
- Baselines: `prep_pi` scripted P-controller — prep 1.00 on D0/D2, **0.24 on
  D4** (slow adaptation fights naive holds): the control-depth gradient is real.

## First frontier results (D2, tools tier, n_prep=3, 2 seeds)

| model | prediction acc | preparation | theory acc |
|---|---|---|---|
| claude-fable-5 + claude_code | **0.86, 0.95** | **1.0, 1.0** | 0.0*, **0.90** |
| gpt-5.2 + codex | 0.12, 0.78 | **1.0, 1.0** | not attempted |

*seed-1 theory scored 0 for `import` usage — jail now tolerates preloaded-module
imports (v0.2.3); the same 13KB theory would now score.

Highlights:
- fable-5 seed 0 is the best physim rollout ever recorded: prediction 0.95,
  all three preparations 5/5 clones, and a **0.895 executable theory**
  (per-stratum 0.84-0.93) — it modeled the world well enough to simulate it.
- Preparation contracts are currently EASIER for frontier models than
  prediction (both models 100% on D2 preps) — as designed for D2, where
  branch-steering suffices; D4/D5 preps (adaptation, feedback-required
  worlds) are where the prep_pi certifier already drops to 0.24.
- gpt-5.2 seed 0 shows reward decomposition working: prep 1.0 with
  prediction 0.12 — it learned to steer without learning to predict.

## Bugs found by models, fixed

- Session reconstruction (tool server) lost issued prep contracts ->
  "unknown preparation contract id"; contracts are now rebuilt
  deterministically from the seed on any answer-phase call (v0.2.1).
- prep/theory detail now persisted into trace.info (v0.2.2).
- Jail import tolerance (v0.2.3).


---

# Addendum 8 (2026-02-11): D4 grid with preparation + theory (M2/M3 at the frontier)

Grid: 4 pairings x 3 seeds, D4, n_prep=3, theory enabled. Baselines on the
same seeds: null acc 0.145 / prep 0.0; prep_pi acc 0.34 / prep 0.24.

| pairing | prediction | preparation | theory |
|---|---|---|---|
| claude-fable-5 + claude_code | **0.305** | **0.73** | 0.29 (3/3 submitted) |
| claude-opus-5 + claude_code | 0.269 | 0.67 | 0.31 (2/3) |
| gpt-5.2 + codex | 0.219 | 0.47 | 0/3 submitted |
| gpt-5.6-sol + codex | 0.214 | 0.51 | 0.21 (1/3) |

## Findings

1. **Preparation >> prediction on D4** for frontier models (fable 0.73 vs
   0.305): steering a system you cannot yet predict is easier than predicting
   it — consistent with control theory (feedback forgives model error) and
   with the gpt-5.2 D2 result. The scripted prep_pi manages only 0.24, so
   models now clearly beat the certifier on preparation while remaining
   ~1.5-2x above null on prediction.
2. **Per-contract profile**: of 36 attempted preps, 20 hit 5/5 clones, 3 were
   flaky (0<rate<1 — only 8%: policies mostly either work robustly or fail
   flat), 13 scored 0.
3. **Solvability audit of the failures** (seed-2 sample): every zero-rate
   contract IS solvable — one by doing nothing, one by pin-and-release, and
   one (ch58) ONLY by feedback control with the correct sign, where naive
   P-control latches the wrong branch (+0.99) and inverted-sign P-control
   scores 5/5 (measured feedthrough sign inversion). Models failed exactly
   where control depth crosses from open-loop to feedback-with-
   identification. The task discriminates the intended skill.
4. **Theory tracks prediction** (r=0.72, n=6): the executable-simulator score
   is measuring the same understanding as contract accuracy, on ~1/3 of
   attempts models simply don't submit a theory (gpt-5.2: zero submissions —
   codex agents treat optional tools as skippable; worth a nudge or a weight).
5. Adaptation rebound remains the wall: fable's best D4 prediction is 0.37
   vs its 0.95 on D2; S1 stays <=0.5 everywhere. D4 is unsaturated on all
   three rewards.

## Environment verdict

M2/M3 mechanics behave at the frontier: rewards decompose (prep vs pred vs
theory measure different skills), preparation contracts are solvable-but-
discriminating, theory submission correlates with understanding. Next
design lever: control-depth-graded prep strata (open-loop / feedback /
feedback+identification) as an explicit axis, and possibly weighting theory.


---

# Addendum 9 (2026-02-12): chemistry track — first frontier runs (C0/C1)

Engine v0.3.1 (unified core; snapshot fix for grayscott worlds). Runs: 2 seeds
per pairing, n_prep=2, theory enabled, 100-turn default.

| pairing | diff | prediction | preparation | theory |
|---|---|---|---|---|
| claude-fable-5 + claude_code | C0 | 0.95, 0.91 | 1.0, 1.0 | 0.96, 0.92 |
| gpt-5.2 + codex | C0 | 0.82, 0.54 | 1.0, 0.75 | not submitted |
| claude-opus-5 + claude_code | C1 | 0.96, 0.95 | 1.0, 1.0 | 0.96, 0.95 |
| gpt-5.6-sol + codex | C1 | 0.97, 0.92 | 1.0, 1.0 | 0.82, — |
| *baselines C0 (2 seeds)* | | *null 0.32 / tail 0.75 / ref 0.71* | | |

## Findings

1. **The chemistry track as configured is frontier-easy** (0.91-0.97 acc,
   preparation saturated). Root cause: objects are STATIC between
   perturbations and co-located sensors make tail-means quasi-constant;
   held-out protocols mostly reproduce probed regimes. The physics is
   richer than the contracts currently exercise (no motion, no multi-object
   interaction probed). C-track difficulty needs: mobile objects (feed
   gradients / drift), contracts on object COUNT changes (split/merge
   protocols), apparatus-dependent contracts (bands only measurable by
   moving a sensor), and tighter scales.
2. **The apparatus went entirely undiscovered.** The best rollout (opus-5
   C1 seed 0, 179 turns, 84% budget) explicitly classified ports 2,4,6 as
   "inert" — ports 2 and 4 ARE the apparatus (stage + enable). Short probes
   (~200 ticks) through empty space look like nothing; no agent ran the
   sustained scans needed to see the stage signature. As designed, apparatus
   discovery is HARD; to make it learnable it needs either (a) contracts that
   require it, or (b) sensor starting positions where small moves already
   change readings (edge-of-object placement).
3. **The science was real despite the wrong ontology — best artifact yet.**
   opus-5's notes.md describes "4 independent 4-sensor cells" with
   "positive drive = slow progress along a line attractor" (= object growth),
   "negative = threshold trigger to absorbing state T" (= object death,
   thresholds measured per cell: 0.615/0.685/0.625), "sigma > 850: IMMUNE"
   (= object too large to starve), and validated with held-out protocols
   (mean |err| 0.021). It reconstructed the object inventory as "cells",
   growth curves as "line attractors", kill thresholds, and death as an
   absorbing state — chemistry rediscovered in alien coordinates, without
   any spatial ontology. Its executable theory scored 0.96.
4. gpt-5.2 (C0) lagged (0.54-0.82): its fits treated S3/S4 kill-release
   contracts poorly (S3 0.30-0.53) — it never characterized object death.

## Verdict

Mechanically the track works end-to-end (contracts, preps, theory, artifact
collection, gallery). Scientifically the frontier models validated the
substrate but exposed the contract suite as too shallow for the physics.
C2+ design queue: object motion, count-change contracts, apparatus-forced
measurement, GS-aware scripted scientist, tighter answer scales.


---

# Addendum 10 (2026-02-12): the trivial-preparation gap, closed (v0.3.2-0.3.3)

Audit after the C0/C1 frontier runs found preparation contracts could be
satisfied by DOING NOTHING: all sampled C-track preps and ~half of D-track
preps had bands containing the do-nothing outcome (bistable worlds land
in-band by luck; GS probes barely shifted tails). This inflates every
preparation number reported in addenda 7-9 (models scored some preps for
free; fable's C0/C1 prep 1.0 was partly trivial).

Fixes (v0.3.2): GS prep sampler probes hot ports hard and reads outcomes
after release, requiring reproducibility across draws; tanh sampler uses a
6-draw resting ensemble; both rank candidates by |shift from rest| and pass a
final gate that runs the ACTUAL scorer with a null policy (drop if do-nothing
succeeds >20% of clones). Verified: null-policy success now 0.0-0.2 on all
tracks; scripted single-port actions still reach 1.0 (solvable, non-trivial).
D0 legitimately yields fewer preps (branch preparation is half-free in a
1-module world by construction).

Also fixed (v0.3.3): a C-track wedge — ready() re-sampled contracts on every
retry (72-250s per attempt from GS clone settles + the new verification gate),
exceeding tool-call timeouts. Contracts are now sampled once and cached in
tool state; GS clones reuse the settled initial fields. D-track regression
(incl. clone noise streams) stays bit-identical.

Revalidation (fable-5, C1, n_prep=3): prediction 0.93, preparation 3/3 with
genuine kill actions (bands unreachable by rest, finals well inside), theory
0.88. The chemistry track remains frontier-easy on PREDICTION (static
objects; a persistence THEORY still scores ~0.89 on C0) — that is the C2
mobility work, unchanged in the queue.


---

# Addendum 11 (2026-02-13): C2 — moving chemistry (v0.4.0-0.4.1)

## What shipped

- **Object motion**: differential V-advection (gs_drift) — spots self-propel
  coherently (~1 cell/20 ticks at 0.005) along a hidden per-world direction;
  drift-compensated kill rate keeps counts stable; post-settle cull +
  generation-time certify() (taskset skips unstable seeds, e.g. C2 seed 5's
  replication cascade).
- **Stat-aware contracts**: mean (20-tick tail) or sd (200-tick window).
  On drifting worlds half of S2/S3 + all of S5 are sd-stat on traffic-visited
  channels (resting fluctuation > 3x noise floor).
- **Tight GS scales** (v0.4.1): quasi-deterministic GS ensembles made the
  10%-range scale floor saturating (gpt-5.2 hit 0.91-0.96 on loose scales
  with replication_ref 0.96-0.97). GS scales now 3% (mean) / 1.5% (sd) of
  channel range.
- **Apparatus-forced preparation (C1)**: one prep targets the MOVABLE
  sensor's channel with a band around its on-object reading — solvable only
  by discovering and driving the stage port (scripted scan-until-in-band
  scores 1.0; do-nothing 0.0). On C2, preparations are absent in v1:
  positions are transient by design (tracking preps deferred to C3).

## Floors (C2 seed 0, tight scales)

| baseline | accuracy |
|---|---|
| null | 0.11 |
| tail (rest-means) | 0.49 |
| persistence theory | 0.39 (S5 0.23) |

## First frontier reads

- gpt-5.2 + codex on C2 (tight scales): **0.73, 0.82** — above tail 0.49,
  below the ~0.95+ replication regime; sd contracts and traffic structure
  are doing real work. (On loose v0.4.0 scales the same setup scored
  0.91-0.96 — scale calibration matters as much as world physics.)
- fable-5 C2 (loose scales): 0.97 with a 0.95 executable theory; one rollout
  died to a HarnessError (retry infra noise).
- **C1 apparatus separation works**: fable seed 2 scored 4/4 on standard
  preps and **0/1 on the apparatus prep** (ch23 = the movable sensor; its
  notes classify the stage port as "constants/nothing"). Meanwhile it
  labeled the gain-apparatus channel an "integrator" — apparatus phenomena
  are visible to agents, but the sensor-motion ontology remains undiscovered.
  Instrument discovery is now a measurable, currently-unsolved skill.

## C2 verdict

Medium tier as configured: harder than C0/C1 (motion breaks static
exploits), not yet D4-hard. The remaining slack is the contract grammar
(traffic statistics are learnable from modest sampling). Next hardening
levers if wanted: longer-horizon sd windows, count-change contracts phrased
via multi-channel functionals, faster drift with tracking-grade apparatus
(C3), and multi-species chemistry (M4 proper).


---

# Addendum 12 (2026-02-13): consolidation snapshot (post-calibration numbers)

All numbers below use the HONEST samplers (v0.3.2+ preps) and TIGHT GS scales
(v0.4.1+). Earlier addenda numbers are superseded where marked.

## Cross-track frontier snapshot (fable-5 + claude_code unless noted)

| world | prediction | preparation | theory | notes |
|---|---|---|---|---|
| D4 (seeds 5,6) | 0.27, 0.30 | **0.0** (1 issued) | 0.39, 0.15 | honest preps are HARD (0.73 in add.8 was partly trivial-band inflation) |
| C1 (seeds 2,3) | 0.91, 0.96 | 0.8, 1.0 | 0.93, 0.96 | apparatus prep = the one miss (0/1) |
| C2 (seeds 0,1) | 0.93, 0.75 | n/a | 0.86, 0.71 | tight scales; S3/S5 dips show motion isn't free |
| C2 gpt-5.2+codex | 0.82, 0.73 | n/a | not submitted | |

Difficulty ordering at the frontier (prediction): C0/C1 (~0.95, saturated) >
C2 (0.73-0.93, mid) > D4 (0.27-0.35, open). The two tracks now bracket the
frontier from both sides.

## Premature-closure question (user-raised) -> DESIGN v0.8 pre-note

Frontier agents settle on wrong-but-adequate ontologies (fable: stage port =
"constants", gain-apparatus channel = "integrator"; 0.96 accuracy while
missing the apparatus entirely). Analysis: (1) reward-correct laziness — we
score prediction, not completeness; the miss cost exactly the apparatus
contract; (2) no anomaly pressure within a single rollout; (3) no
falsification oracle. Candidate mechanisms (B) anomaly-completion contracts,
(C) a limited-use self-test tool `check_model`, (D) iterated rollouts on the
same world, (E) longer budgets + conduct prompt. To be decided; the benchmark
currently MEASURES closure behavior rather than correcting it, which is
itself a finding worth reporting.

## Site

Results pages restructured per-track with the consolidated tables; rollout
gallery split into rollouts-bulk.html / rollouts-chemistry.html (old URL
redirects). sd-stat contracts now disclosed in the system prompt (grammar
transparency; v0.4.2).


---

# Addendum 13 (2026-02-13): M4 — multi-species chemistry (C3, v0.5.0)

## World

`grayscott2`: two coupled reaction systems. Species A = standard stable
spots. Species B carries a kill-rate excess (dies alone) offset by A's local
presence — so B objects survive only stacked ON A hosts, and killing a host
via its port cascades to the tenant (~200 ticks later). Ports are
species-tagged (each feeds one species; hidden); sensors read hidden species
mixtures (60% pure / 40% blended). "There are two kinds of stuff" is itself
a discovery. Verified end-to-end through the port interface: bound pairs
persist 8k+ ticks; far-seeded B dies; host-kill removes both.

Documentation principle (DESIGN v0.9): C3's worlds.html panels describe the
world at the SPECIES level (composite species map, binding-distance
histogram clustering at 0, three-frame cascade sequence) — human docs climb
the emergence ladder with the worlds; agents still see only ports.

## Floors and frontier (2 seeds, n_prep=3)

| | prediction | preparation | theory |
|---|---|---|---|
| claude-fable-5 + claude_code | **0.90, 0.89** | 1.0 | 0.78, 0.87 |
| gpt-5.2 + codex | 0.57, 0.57 | 0.83-1.0 | not submitted |
| tail / null / persistence | 0.60 / 0.00 / 0.69 | | |

## The layer-2 closure finding

fable-5 predicts C3 excellently via a LINEAR-LATENTS ontology ("sensors =
linear readout of a few latent states"; port-groups as latents; slow
integrators) — with zero species/host/dependency vocabulary anywhere in its
workspace. The cascade law appears only as "long port0 drive displaced MANY
channels." Same closure behavior as C1's apparatus miss, now one emergence
level up: the agent compresses two-species physics into an adequate
single-layer theory and stops. gpt-5.2's S3/S4 (cascade strata) collapse to
0.25-0.65 — it pays for the missing ontology; fable's latents happen to
capture the cascades functionally (S3/S4 0.80-0.96). Conduct metrics:
port_coverage 1.0 for all four rollouts (everyone probes everything once;
nobody re-opens anomalies).

C3 verdict: mechanically sound, mid-tier at the frontier (fable 0.90 /
gpt-5.2 0.57), and the two-layer ontology question is now measurable:
the gap between predictive adequacy and structural discovery is the
benchmark's sharpest lens yet.


---

# Addendum 14 (2026-02-14): C4 — excitable chemistry: the first rich-not-big frontier-hard world

## The rich-vs-big criterion (DESIGN v0.10, user-set)

A hard world must pass three tests: (1) intended emergent phenomena verified
by god-knowledge probes; (2) a COMPACT theory exists that solves the
contracts (else the world is merely big); (3) frontier models score far
below that compact oracle. C4 is the first world built under and passing
all three.

## The world

FitzHugh-Nagumo excitable medium: a hidden pacemaker emits traveling rings;
sensors read periodic pulse trains. Ports inject current — a sustained drive
CREATES a new pacemaker. Compact laws (each verified by scripted probe):
- wave speed (~0.9 cells/tu; arrival phase = distance/speed)
- entrainment: the faster rhythm source takes over the whole medium
  (collision annihilation ⇒ far-field period = min over sources;
  sustained port drive gives period 39 vs intrinsic 82)
- refractory conduction block: 1:1 at slow drive, 2:1 at period ~110,
  irregular Wenckebach-like zone between
New ontology-neutral statistic for wave worlds: stat="rate" (threshold
upcrossings per 200-tick window; threshold = channel median + 1 sd).
Contract grammar engages the laws: S1 autonomous rhythm, S2 competing
pacemaker, S3 pulse-train conduction, S4 two-port collision.

## Rich-vs-big battery

| reference | accuracy | size |
|---|---|---|
| null / tail / persistence | 0.09 / 0.16 / 0.25 | — |
| entrainment-aware compact oracle | 0.76 (v1, improvable ~0.9) | ~40 lines |
| single replication (true engine) | 0.90 | — |

Deepest floors of any physim world: level-thinking is worthless against
waves.

## Frontier results (2 seeds each, tools tier)

| pairing | prediction | theory |
|---|---|---|
| claude-fable-5 + claude_code | **0.24, 0.18** | 0.52, 0.32 |
| gpt-5.2 + codex | 0.13, 0.12 | not submitted |

The frontier is BROKEN on C4 without any scaling: 96² lattice (same as
C1-C3), 8 ports, 40 sensors, modest noise. fable's notes contain real wave
vocabulary ("wave, pulse, period, phase") and its seed-0 theory scores 0.52 —
it SEES the rhythm but cannot convert to contract-grade timing/rate
predictions. gpt-5.2 never forms the wave ontology (S2 = 0.02-0.03: the
entrainment stratum is invisible to level-based fits).

Gap summary: compact oracle 0.76+ vs best frontier 0.24 on a world whose
laws fit on an index card. This is the project thesis made quantitative:
richness (emergent laws discoverable by better science) rather than bigness
(more parameters/noise) is what separates current AI scientists from the
achievable.


---

# Addendum 15 (2026-02-14): effort diagnostic + calibration A/B — do models try harder on harder worlds?

## Diagnostic (53 tools-tier rollouts)

Question (user): as worlds get harder, do the best models run more
experiments and synthesize more? Hardness := 1 - frontier mean accuracy.

- **fable-5**: synthesis scales with hardness (completion tokens rho=+0.75
  p<0.001; workspace chars +0.54 p=0.015) but EXPERIMENTS do not (+0.07).
  It thinks harder, writes more theory — but does not collect more data.
- **gpt-5.2**: every effort metric flat-to-negative with hardness (wall
  minutes rho=-0.47): works uniformly LESS on harder worlds.
- **sol / opus-5**: fewer experiments on hard worlds (46 vs 78; 80 vs 115).
- Universal: hard-world budget use 26-40% — everyone stops with most fuel
  left. The stopping policy binds, not resources.

Verdict: the ideal property (harder -> try more) FAILS for data collection
across all frontier models tested.

## The basic-compatible lever: pay for honest uncertainty

Intervals were reward-free; narrow-and-wrong cost nothing, so once a point
estimate existed further experiments had no scoreboard value. Added a
Winkler-based interval-calibration reward (fixed function of world+seed;
nothing adapts to the agent): narrow-right 0.91 > medium-right 0.74 >
wide-honest 0.14 > narrow-wrong 0.03. Uncertainty reduction is now the only
path up — and honest reporting beats bluffing.

## A/B on C4 (weight 0 vs 1, 2 seeds/model)

| model | acc | calibration | coverage | experiments | budget |
|---|---|---|---|---|---|
| fable-5 w=0 | 0.21 | 0.00* | 0.12 | 86 | 24% |
| fable-5 w=1 | 0.24 | 0.37 | 0.25 | 80 | 18% |
| gpt-5.2 w=0 | 0.12 | 0.00* | 0.34 | 63 | 34% |
| gpt-5.2 w=1 | 0.17 | 0.38 | 0.38 | 62 | 20% |

*retro-scored as 0 (metric did not exist).

Result: calibration reward improves ANSWER HONESTY (calibration, coverage,
small accuracy gains) but does NOT change experimental effort (experiments
and budget flat/down; n=2 caveats). Models adapt their reporting, not their
science. Conclusion: at current capability, effort-on-hard-worlds is a model
property, not an incentive artifact — the environment can measure it (conduct
metrics, budget use) but not buy it with scoring. This cleanly greenlights
the world-creation program: build past frontier-zero and let the benchmark
wait for models that can climb it.

Default: calibration_weight stays 0 (report-only) for comparability with the
existing leaderboard; recommended 0.5+ for future training runs (honesty
shaping).


---

# Addendum 16 (2026-02-14): B0 — the biology track opens (v0.7.0)

## World

reaction="ecology": two Gray-Scott organism variants (fast/greedy k=0.060,
c=0.010 vs efficient/frugal k=0.0615, c=0.003) competing for ONE regenerating
resource field R; ports fertilize/poison regional resource regeneration
(wide fields, in_width=16, so drives matter ecologically); species-blind
density sensors. Certified 6/6 seeds (both populations 3-90 across 3x1200t
free runs). Verified through the port interface: sustained poison drives the
fast variant EXTINCT (32->0) while the efficient survives (the selection
law); fertilize booms both (56/50).

Emergent laws (3 sentences): populations grow to a carrying capacity; two
variants share the world under a greedy-vs-frugal trade-off; sustained
scarcity kills the greedy variant first — the frugal inherits the world.

## Rich-vs-big battery

| reference | accuracy | size |
|---|---|---|
| null / tail / persistence | 0.18 / 0.27 / 0.15 | — |
| compact ecology oracle | **0.744** | ~50 lines |
| (oracle components: equilibrium-response interpolation at 6 tilt levels,
one calibrated recovery trajectory, horizon matching) | | |

Persistence floor 0.15 is the deepest of any world (populations never sit
still). Criteria 1+2 of the rich-vs-big test pass.

## Frontier (2 seeds each, tools tier, calibration_weight=1 default-on here)

| pairing | prediction | calibration | theory |
|---|---|---|---|
| claude-fable-5 + claude_code | 0.63, 0.46 | 0.74, 0.61 | 0.41, 0.47 |
| gpt-5.2 + codex | 0.58, 0.46 | 0.64, 0.51 | — |

Gap to compact oracle ~0.15-0.29: B0 lands mid-tier (harder than C0-C3,
easier than C4/D4 relative to oracle).

## The layer-3 ontology gap

Grep of every workspace: ZERO biological vocabulary — no "population",
"organism", "resource", "extinct", "carrying", "recover" in any agent's
notes. The agents fit channel responses to drive levels (which earns
S1/S2) and miss recovery dynamics and extinction boundaries (S3/S4 0.34-
0.55) — the strata that require the population picture. Same closure
pattern as C1 (apparatus), C3 (species): predictive adequacy without the
generative ontology, now at the ecosystem level. The benchmark now has
three measured rungs of the same ladder.

## Notes

- budget use: 7-33% (effort ceiling unchanged, as diagnosed).
- fable seed-1 rollout used 35 turns/7% budget for 0.63 — its most
  score-efficient rollout yet; hypothesis: B0's S1/S2 are learnable from
  few long experiments, the rest it declined to chase.
- worlds.html documents B0 at the population level (ecosystem map,
  population/resource curves, the selection-collapse plot) per the
  description-levels principle.


---

# Addendum 17 (2026-02-14): B1 selection-boundary worlds + the smoothness ceiling

## B1 (v0.7.1-0.7.2)

Richness alienized across the exclusion threshold (R_max in [0.031, 0.037];
boundary ~0.0335): per-instance the ecosystem lands coexist-side or
excluded-side; certification accepts fast-variant exclusion (2/10 seeds) and
rejects dead/reversed ecosystems. New S5 stratum: medium tilts held
1800-2600t (boundary crossing). Compact oracle v3 (adds 2600t-horizon
calibration): 0.726; floors null 0.26 / tail 0.26 / persistence 0.33.

## Frontier

| pairing | B1 @250k budget | B1 @60k budget |
|---|---|---|
| gpt-5.2 + codex | 0.71, 0.78 | 0.77, 0.82 |
| claude-fable-5 + claude_code | 0.59 (+1 infra error) | 0.81 |

gpt-5.2 seed 0: **0.77 with 10 experiments / 7% of a 60k budget.** The
budget cut (250k->60k, anti-replication economics) changed nothing.

## Diagnosis: the smoothness ceiling

B-track observables (population densities aggregated over sensor patches)
respond SMOOTHLY to drive amplitude — a handful of tilt levels interpolates
the whole response surface (this is exactly how the compact oracle works,
and the models found it too). Even near the exclusion boundary, partial port
coverage leaves refugia; populations recolonize; outcomes stay smooth (probe:
poison to n1=2, recovery to n1=41 — recolonization, no hysteresis). Contrast
C4, where timing/phase observables are NOT smoothly interpolable and the
frontier collapses to 0.12-0.24.

Lesson recorded: richness (compact laws) is necessary but not sufficient for
frontier-hardness; the observable map must also be non-interpolable
(discontinuities, phase/timing structure, path dependence at the readout
level). Ecology at population granularity is intrinsically smooth ->
mid-tier. The B-track hardness push should come from HYBRIDS (e.g., waves
triggering ecological regime shifts) rather than more ecology knobs.

## Curriculum presets shipped (training ladder)

B0a (one variant + resource: carrying capacity alone), B0b (two variants,
rich world: pure competition) — certified 4/4 each; B-track decomposition
B0a -> B0b -> B0 -> B1 is live for future training use.


---

# Addendum 18 (2026-02-14): B2 — the ecowave hybrid: hardness by composition

## The world (v0.7.2, reaction="ecowave")

FHN wave layer + single-variant ecology, coupled through the resource: wave
passage boosts local resource regeneration ("rain"); base regeneration alone
cannot sustain life. Verified: population tracks wave rate (period 300 ->
~47 organisms, 700 -> ~28, waves OFF -> extinction); fast pacing inherits
refractory conduction block (fewer meals at higher drive rate — the
NON-MONOTONIC response an interpolator cannot capture). Ports inject
current: agents can create pacemakers = feed the world. Decomposition:
B2 = C4 (waves) + B0a (carrying capacity), each separately certified — the
hybrid is the curriculum's third rung composed of rungs one and two.

## Battery

floors: null 0.28 / tail 0.35 / persistence 0.29
compact hybrid oracle (~55 lines: 5 horizon-matched condition calibrations
+ drive-signature classifier): **0.795**

## Frontier (2 seeds each)

| pairing | prediction | theory |
|---|---|---|
| claude-fable-5 + claude_code | 0.48, 0.36 | 0.52, 0.51 |
| gpt-5.2 + codex | 0.42, 0.29 | — |

Oracle gap 0.32-0.51: hard tier (second only to C4). fable's notes contain
"wave, pulse, period, rain" (partial hybrid ontology — it SEES the rain!)
but S2 (pacing at varied rates, the non-monotonic stratum) scores 0.04-0.31
for everyone: nobody constructs the pacing-rate -> food-delivery -> carrying
capacity chain. gpt-5.2 shows no wave vocabulary at all.

## Iteration summary (this autonomous loop)

1. B1 (boundary worlds): built, validated — revealed the SMOOTHNESS CEILING
   (population observables interpolate; frontier 0.77-0.82 ~ oracle). Kept
   as mid-tier; lesson recorded as design law.
2. Curriculum presets B0a/B0b: shipped, certified.
3. B2 (hybrid): built under the new design law (compose a non-interpolable
   layer with the smooth one) — frontier gap restored to hard-tier without
   any scaling. Composition of certified components is now the demonstrated
   recipe for making rich worlds harder: hardness comes from coupling
   structure, not size.

Track order by frontier gap: C4 (0.5-0.6) > B2 (0.3-0.5) > D4 (0.3-0.45)
> B0/C2/C3 (0.1-0.3) > B1/C0/C1 (~0).


---

# Addendum 19 (2026-02-15): E0 — the evolution track opens (v0.8.0)

## World

reaction="evo": one organism species + resource + a HERITABLE TRAIT FIELD g
carried by tissue. Inheritance = growth-copying (daughters inherit parent
tissue's g); mutation = small noise at growth sites; LINEAR micro GP map
g -> (consumption, kill) per the infinitesimal-model decision (DESIGN v0.13
addendum). Nothing selects anything explicitly — differential survival does.
Sensors: density + PHENOTYPE-STAIN mixtures (g-weighted density, hidden
weights). Ports fertilize/poison. Verified through ports: a 12k-tick poison
era shifts mean genotype 0.485 -> 0.447 and the population re-expands at the
adapted genotype (path dependence in the gene pool). Certified 5/5 seeds.

## Battery

floors: null 0.34 / tail 0.32 / persistence 0.40
compact evo oracle (~60 lines: dose-classified condition calibration): 0.74
Contract grammar: S1 equilibrium / S2 tilt / S3 selection era + recovery /
S4 double era (the second poison hits an ADAPTED population — genetic
memory). Era-scale protocols required MAX_SEG_TICKS 5000->8000.

## Cross-level map-shape finding (user's tracked question, first datapoint)

The LINEAR micro GP map aggregates to a SATURATING macro response: selection
response per unit dose shrinks with dose (delta mean_g ~-0.05 at 2k ticks,
no further movement by 12k) because selection depletes trait variance
(sd_g 0.10 -> 0.03) — the breeder's equation running out of fuel. Micro
shape != macro shape, exactly as conjectured; the aggregate map is shaped by
the DYNAMICS OF VARIANCE, not just the pointwise map. To keep tracking per
rung.

## Frontier (2 seeds each; 1 fable rollout lost to infra HarnessError)

| pairing | prediction | theory |
|---|---|---|
| gpt-5.2 + codex | 0.67, 0.53 | — |
| claude-fable-5 + claude_code | 0.56 | 0.46 |

Gap to oracle ~0.1-0.2 (mid-tier as configured). Notable: budget use 1-5%
— era-scale contracts (4000-7000t) dwarf the agents' own experiments; no
agent ran a single selection-era experiment of its own, so the S3/S4 path
dependence was answered by extrapolating short-horizon behavior (S4 as low
as 0.24). FOURTH ontology rung: zero evolutionary vocabulary (adapt/select/
mutate/trait) in any workspace.

## Iteration read

E0's laws are discoverable but its selection signal is SLOW (10k+ ticks per
era) relative to what agents explore voluntarily — the effort ceiling meets
evolutionary timescales. E1 design should make selection FASTER and more
visible (stronger trade-off, higher mutation, phenotype-stain sensors more
distinct), or contracts even more path-dependent, before layering 2-D traits.


---

# Addendum 20 (2026-02-15): E0 CORRECTED (physics fix) + E1 storm world ships (v0.9.0)

## E0 correction — old results WIPED (user decision)

Diagnosis (see DESIGN v0.13 addendum 8): E0-as-shipped (v0.8.0) had BLENDING
inheritance (tissue-averaging), which destroys trait variance geometrically —
Jenkin's 1867 objection reproduced in silico — and its reported adaptation
(mean_g 0.485->0.447) was mostly SHELTER SURVIVORSHIP (survival~shelter
r=0.46 vs survival~genotype r=-0.08), not genotype selection. Addendum 19's
adaptation claims are RETRACTED. Per user decision this is a WIP benchmark:
E0 is fixed in place (no version fork), blending-era frontier results are
wiped from the results pages, and E0 will be re-validated on the corrected
physics. Raw traces of the old runs remain in the HF dataset for the record.

The fix (v0.9.0, single inheritance rule for all evo worlds):
- PARTICULATE COPY inheritance: fresh tissue copies its dominant parent
  neighbor's genotype. Variance now persists (E0 settle sd_g ~0.27!).
- GP-map shapes: evo_gp = "linear" (E0) | "asym" (E1: saturating robustness).
- E0 remains storm-free; its laws are variance maintenance + port-driven
  selection eras (to be re-validated with the corrected mechanics).

## E1 — the storm world (new)

reaction=evo + evo_gp="asym" + storms (regen mult ~0.5, dwell ~8k, calm ~8k,
alienized per instance). The world's own weather drives evolution: settled
populations arrive ADAPTED (mean_g ~0.2 vs founder 0.5); fertilize eras
de-adapt and re-adapt live. Certified 5/5 seeds.

| reference | accuracy |
|---|---|
| null / tail / persistence | 0.28 / 0.35 / 0.43 |
| compact oracle (~65 lines, storm-phase-aware condition calibration) | **0.805** |

Design notes recorded: asymmetric GP map (consumption linear, robustness
saturating) is DESIGNED biochemistry — both traits derive from the SAME
gene g through fixed maps; the asymmetry is in the g->phenotype map shape,
not in inheritance (single copy rule). Selection at storm depth 0.5 is the
probe-verified selective sweet spot (0.2-0.35 kills indiscriminately).


---

# Addendum 21 (2026-02-15): E1 frontier + the answer-or-zero lesson

## Frontier (2 seeds each, corrected physics)

| pairing | prediction | notes |
|---|---|---|
| gpt-5.2 + codex | 0.57, 0.55 | one rollout burned 99% budget for 0.554 — effort without the storm clock |
| claude-fable-5 + claude_code | 0.42, 0.00* | *112 productive turns, then ended session WITHOUT calling ready/answer: n_answered=0 -> 0. Its last note: "Now the highest-value data...: across-draw replication." A deadline miss, kept as scored (real science has deadlines). |

Gap to compact oracle (0.805): 0.23-0.38 — E1 lands hard-tier-adjacent
(between D4 and B2). fable's workspace shows partial storm ontology
("regime", "period"); no agent found adaptation/selection. The hidden storm
clock (period ~16k ticks, alienized) is the E1 analogue of C4's pacemaker —
and like C4, models sense periodicity without converting it into a
predictive clock.

## Answer-or-zero

fable's zero is legitimate under the rules (unanswered = 0, stated in the
prompt) but flags a conduct pattern: research programs that never converge
to answers. No env change — the scoreboard already prices it.


---

# Addendum 22 (2026-02-16): probe day — emergent GP maps (R* theorem) + measurement adequacy

No engine changes; two probe campaigns recorded in DESIGN v0.14.

1. Evolvable biochemistry (user Q: authored GP maps can't scale): depletion
   feedback alone does NOT produce saturating phenotypes (negative probe).
   But "enzyme economics" (linear income ∝ g·R, linear upkeep ∝ g, finite
   larder, bankruptcy) yields EMERGENT bidirectional selection with a
   world-computed critical point R* = m1/c_max: mild storms kill the frugal
   (g rises), medium storms kill the greedy (g falls), calm drifts greedy —
   no authored curve shapes. Principle adopted: author prices and
   conservation laws, not curves. E2 candidate parked pending discussion.

2. Measurement adequacy (user Q: do sensor contracts miss higher-level
   science, e.g. closed membranes?): dye-assay probe shows topology is
   port-decidable operationally (closed vs open separation ~2.7e6x). The
   real flaw is in scoring: truth ensembles collapse to (μ,τ), erasing
   emergent multimodality. Candidate fixes (CRPS distributional contracts,
   assay-grammar growth, measurement-adequacy certification, prepare-tier
   assays) recorded in DESIGN; nothing built yet — discussion open.


---

# Addendum 23 (2026-02-16): CRPS distributional contracts ship (v0.10.0) + adequacy certification

User picked directions 1+3 from addendum 22, as a cross-check pair.

BUILT:
- Answers accept optional quantiles {0.1,0.25,0.5,0.75,0.9}; scoring is now
  CRPS (2x mean pinball) minus the truth ensemble's leave-one-out floor,
  exp(-excess/scale). Deterministic limit == legacy exp(-|err|/scale)
  (verified: point@truth 1.0, off-by-scale e^-1). Bimodal truth: point@mean
  0.34 / point@mode 0.32 / honest distribution 1.00 — multimodality collapse
  fixed; structure pays. Legacy point accuracy kept as report-only metric.
- Prompts updated generically (no phenomenon named; grammar world-independent).
- Floors spot-checked: B2 null/tail 0.32/0.42 (legacy 0.28/0.35); D4 0.24/0.22
  (0.22/0.22). No floor inflation.
- probes/adequacy_cert.py: A = Var_instances(mu)/mean(tau^2) on fixed
  verbatim templates; CRPS oracle-minus-climatology gap; cross-check:
  B2 Spearman(log A, gap) = 1.000, D2 = 0.904, C4 saturated (both measures
  agree). CRPS validated against the auditable audit (DESIGN v0.15).

Q1 follow-up recorded in IDEAS.md: parameter-search world screening
(sample parameterizations, keep those with certified interesting phenomena;
the R* sweep was the manual prototype).


---

# Addendum 24 (2026-02-16): first frontier run under CRPS — the option gets used

B2 spot-check (fable + claude_code, 2 seeds, v0.10.0): CRPS 0.53 / 0.42 vs
legacy point accuracy 0.39 / 0.31. Both rollouts answered with quantiles on
essentially all contracts, unprompted (beyond the one-line schema/prompt
mention) — on the world with winner bimodality, the model immediately used
the distributional channel. CRPS > legacy for honest point answers is the
intended fairness fix (legacy charged agents for the world's own noise
floor; CRPS charges only excess over it). End-to-end schema flow validated.


---

# Addendum 25 (2026-02-16): CRPS re-runs land + site restructure

## Site
- New docs/scoring.html: complete scoring mechanics (contracts, ensembles,
  CRPS + noise-floor subtraction + verified-properties table, calibration,
  preparation, theories, reference ladder, adequacy audit, non-rewards).
- New docs/results-life.html: B/E tracks split out of the chemistry page.
- Nav/index/worlds/overview updated; results pages are the curated view.

## Distributional oracle + floor battery (seed 0, quantile answers = own
calibration-rep spread as Gaussian quantiles)

| world | oracle (dist) | oracle (point) | oracle (legacy) | tail | null |
|---|---|---|---|---|---|
| B0 | 0.845 | 0.820 | 0.779 | 0.33 | 0.22 |
| B2 | 0.975 | 0.917 | 0.840 | 0.42 | 0.32 |
| E1 | 0.934 | 0.916 | 0.818 | 0.42 | 0.35 |

## Frontier re-runs (2 seeds each, CRPS; legacy metric in parens)

| world | fable + claude_code | gpt-5.2 + codex |
|---|---|---|
| B0 | 0.54 (0.39), 0.72 (0.55) | 0.55 (0.49), 0.49 (0.41) |
| B2 | 0.53 (0.39), 0.42 (0.31) [prev turn] | 0.37 (0.32), 0.34 (0.30) |
| E1 | 0.72 (0.57), 0.51 (0.31) | 0.68 (0.57), 0.53 (0.48) |

## Findings
1. QUANTILE USE IS A CONDUCT TRAIT: fable answered with quantiles on 5/5
   stochastic-world rollouts; gpt-5.2 on 0/5 — same tool schema, same prompt
   sentence. The proper score now prices honest uncertainty; gpt leaves it
   on the table.
2. CRPS lifts honest answers ~0.05-0.20 over their legacy score (noise-floor
   fairness), ordering within worlds mostly preserved; E1 fable answered
   both seeds this time (last run's answer-or-zero was conduct, not env).
3. B2's distributional oracle (0.975) reveals wide-but-knowable ensembles:
   gap to frontier 0.45-0.63 — B2 is now clearly the hardest life world and
   second overall behind C4.
4. Track order under CRPS: C4 > B2 > B0 ~ E1 > D4 > C2/C3 > B1/C0/C1.


---

# Addendum 26 (2026-02-16): documentation day — track subpages, films, scoring visuals

Site restructure (user direction), no engine changes:

1. WORLDS: docs/worlds.html is now a compact hub (shared machinery, the idea,
   agent interface, track cards); each track got its own page with god-view
   FILMS of the dynamics (animated gifs rendered from the real engine, seed 0):
   - worlds-bulk.html: D4 film — global reset, single-region flip, hysteresis
     hold + fatigue pushback;
   - worlds-chemistry.html: C2 drift film; C4 film — natural pacemaker vs
     port-driven competing pacemaker, collision fronts, release;
   - worlds-life.html: B0 film — coexistence → poison era → greedy extinction
     persists after release; B2 film — waves water the ecology (rain trails);
   - worlds-evolution.html: E0 film — colony mosaic bleaching toward frugal
     under poison; E1 film — fertilize de-adapts, storm cycle re-selects
     (gene pool tracking climate with a lag); + genotype-distribution
     timeline panel (variance persistence via mutation-selection balance).
   Films: 7 gifs, ~18 MB total, quantized 128 colors, lazy-loaded.
2. RESULTS: one page per track now — results-evolution.html split out of the
   life page (which is now ecology-only); nav updated everywhere.
3. SCORING VISUALS (docs/scoring.html): three figures generated from real
   machinery (probes/scoring_figs.py):
   - bimodal-contract figure: truth histogram + three answers with their
     actual crps_accuracy scores (mean 0.39 / mode 0.49 / honest 1.00) and
     the CDF-area picture of CRPS;
   - reference-ladder bar chart on B2 (null 0.32 → tail 0.42 → frontier
     0.37/0.53 → point oracle 0.92 → distributional oracle 0.975);
   - adequacy scatter (A ratio vs CRPS gap) for B2/C4/D2 from
     probes/adequacy_cert.py live numbers.
4. ROLLOUTS: rollouts-life.html gallery added (B/E traces).

Next (user-approved): E2 (enzyme economics, parameter search screened by the
certification battery) and B3 (selection-by-wave-regime) — with the new film
infrastructure available to showcase their emergence for review.


---

# Addendum 27 (2026-02-16): E2 enzyme economics ships (v0.11.0); B3 probe campaign parks it

E2 (reaction="enzyme") is live: the only authored biology is a price list
(income ∝ gene·substrate, rent ∝ gene, finite larder, bankruptcy, viability
floor) — the critical resource R* = rent/earnings, the famine/plenty
selection asymmetry, and the entire trade-off structure are THEOREMS of the
conservation law (DESIGN v0.16). Parameters found by search over price-space
in theory coordinates (raw-coordinate search failed 0/48; theory-coordinate
4/48 pass), certified 20/20 seeds. The world breathes: gene pool swings
frugal↔greedy with the ~1000-tick storm clock, variance regenerating every
cycle (see the worlds-evolution page film + histogram timeline).

Battery: storm-phase oracle 0.974 (dist) / 0.969 (point); floors null 0.251 /
tail 0.174 / persistence 0.227. Frontier eval launched (fable, gpt-5.2 × 2
seeds). E2 note: with 1000-tick eras, era-scale protocols fit in S3/S4
contract lengths — the selection clock is finally INSIDE the contract
horizon, unlike E1 where storms outlast most protocols.

B3 (selection by wave regime): fully built and probed, then PARKED (not
agent-facing). Two honest reasons in DESIGN v0.16: the FHN layer's
anode-break inversion (negative current makes it rain MORE) breaks the
famine-era concept, and rich rain produces competitive exclusion of the
frugal variant rather than a flippable winner. The preset and physics remain
in-engine as a probe record; winner-flip world designs are parked in IDEAS.


---

# Addendum 28 (2026-02-16): E2 frontier — fast clocks forgive; the fifth rung holds

E2 frontier (2 seeds each, CRPS): fable 0.85/0.71 (quantiles, again 5/5
conduct), gpt-5.2 0.74/0.65 (points). Oracle gap 0.13-0.26 — mid-tier.

Diagnosis: E2's era clock (~1000 ticks, chosen so selection fits inside
contract horizons) also fits inside AGENT experiments: fable discovered the
storm cycle as a bistable A/B state machine ("FLIPS B->A", per-state
timescales, release undershoot) and interpolated the climate without any
evolutionary ontology. Nobody wrote heredity/selection/mutation vocabulary
(fable's "adaptation" is sensory undershoot). The fifth ontology rung
(genes) is intact — but a good climate model prices most E2 contracts.

Design law recorded: CLOCK SPEED TRADES DISCOVERABILITY AGAINST DIFFICULTY.
Fast selection clocks make evolution observable (and film-able) but
interpolable; slow clocks (E1: gap 0.22-0.43) hide the mechanism outside
protocol horizons and punish climate-only models. The E-track now brackets
the tradeoff: E1 (slow, hard) / E2 (fast, mid). A future E3 could put the
selection response just BEYOND single-contract horizons but within
multi-contract reach — the sweet spot where only mechanistic (genetic)
models transfer.


## Addendum 29 — user redirect: BLOBS program (dissipative-soliton matter)

After reviewing the five world-search finalist films, the user picked the slime
lifecycle as closest-to-interesting but redirected the program upward: worlds built
from BLOBS — persistent localized excitations of continuum fields ("instanton-like"),
with flavors (multi-component fields), field-mediated interactions, BINDING into
molecules, composite dynamics in background fields (spinning singles, mutually
rotating pairs), and ultimately self-assembled MACHINES (e.g. a configuration that
transports a target-flavor blob upstream against a background gradient).

Controller Day-0 feasibility (probes/blobs/day0_probe.py): the 3-component
Purwins-class reaction-diffusion system (activator + slow inhibitor + fast
long-range inhibitor) holds a persistent single blob at lam=2, k1=-0.7, k3=1,
k4=1.5, tau=3, theta=0.7, Du=Dv=1, Dw=20 (L=96, dt=0.01): area ~26px, stable
2000 tu, noise-robust to 2e-3, non-replicating — sitting in the classic window
between death (k1=-0.9) and replication cascade / spot soup (k1=-0.5, k4=2.5).
Known trap confirmed immediately: the blob is LATTICE-PINNED (zero displacement
under noise) — motility requires the drift bifurcation and an un-pinning proof
(grid-refinement invariance), which is milestone M1.

Program spec: probes/blobs/PROGRAM.md (gates B1 existence, B2 mobility, B3 flavors,
B4 binding, B5 composite dynamics, B6 machine, B7 budget; honesty rules: fields
only — blob identity is measured, never a state variable; no scripted events;
machines must be same-physics configurations). Three searchers spawned:
blob-motility (M1), blob-binding (M2), blob-flavors (M3). Slime-lifecycle engine
integration is PARKED as the fallback shipping candidate, not cancelled.

First blowup lesson re-learned within minutes (explicit Euler dt vs Dw=20-30
stability: dt < dx^2/(4 Dw)) — encoded in the searcher briefs.


## Addendum 30 — BLOBS round 1 certified (M1-M3); round 2 spawned (M4-M5 prep)

Round-1 fan-in complete, all three milestones certified after controller audits:
- M1 MOTILITY (consolidated by controller from child cert artifacts after the child
  died pre-consolidation): drift bifurcation c=sqrt(0.0299(tau-4.78)), r2=0.993, at
  Dv=0.65; unpinned (IMEX-FFT, dx=0.5 converged to 0.6% vs dx=0.25; 0/8 noise-chosen
  directions lattice-clustered); 10k-tu lifetime; wall reflection + soft two-blob
  scattering logged. Audit trap hit AGAIN: naive u-only IC dies at tau=5 — searchers'
  documented symmetric-IC protocol required (convention-faithful audits, 3rd time).
- M2 BINDING: P7s = M0 + Dv=2.0, tau=2.5. Bond d1*=15.70+-0.02 (two-sided
  convergence), basin [14.5,19.5], unpinned (1.8% shift dx=1->0.5); escapes censored
  >4000tu at sigma<=0.075; stable 3-chain + equilateral triangle molecules. THE BIG
  HONEST NEGATIVE: tau=3.0's apparent bond was PURE LATTICE PINNING (continuum
  saddle, e-fold 140tu) — the Day-0 trap materialized exactly as feared and was
  caught by the dx-refinement gate. Controller audit: fresh stamps, L=64, d0=16.5 &
  18.5 -> d*=15.67/15.70. CONFIRMED.
- M3 FLAVORS: "vvw" arch (private u_i,v_i + shared long-range w) with an
  iso-background line (k1_i, k4_i co-varied) holding ONE stable background for all
  species. A=169px broad / B=25px sharp, port-classifiable 20/20 by w-signature
  alone; encounters conserve flavor (pure repulsion; only AA at d0=6 merges,
  deterministically). Audit: A+B at d0=8 repel to 12.1, conserved, 2 fresh seeds.
Design tension for M4 (spawned: blob-composite): binding lives at (Dv=2.0, tau=2.5),
motility at (Dv=0.65, tau>4.78) — round 2 must find the regime where bound
structures MOVE (traveling bonds / rotating pairs / breathing bonds). M5-prep
(spawned: blob-transport): static background gradients as "downstream", species-
selective drift as the sorting primitive, chains as obstacles/channels, noise
ratchet sketch. Machine assembly = round 3.


## Addendum 31 — M5-prep certified; A-species continuum caveat; machine searcher spawned

blob-transport scorecard audited and certified (115 runs, job-spec replay system):
- P1 GRADIENT two couplings: k1-mode (v=+2.64eps+27eps^2, r2 .999998, flip
  bifurcation at eps*~0.01 where B reverses onto a second soliton branch; LEVEL-not-
  slope limits) and the NEW isod-mode — displacing parameters along M3's
  iso-background line gives a ZERO-FOOTPRINT force (no background perturbation):
  B drifts v=-0.906eps, linear to eps=0.03, safe to 0.02. Controller audit:
  eps=0.01 fresh seed 1.2% off the law; out-of-grid eps=0.025 shows the predicted
  approach to the safe edge (14% superlinear, area growing).
- P2 SELECTIVITY partial (honest): both species drift the same sign (1.3-1.7x
  magnitude ratio); sorting requires the flip window or per-species coupling.
- P3 OBSTACLES: M2 chains cannot exist in the vvw world (pure repulsion) — instead
  WALLS SELF-ASSEMBLE (a blob parked on a tri-gradient ridge destabilizes into a
  static domain-spanning stripe: defect-turned-tool). Blocking standoff(eps)
  monotone 15.7->12.9px; channeling: two rails center B cargo from any y0>=10
  (audit: y_rms 0.50px while conveyed 16.6px).
- P4 noise ratchet honest NEGATIVE: the soliton is too stiff for Kramers hops
  (positional diffusion ~0 even at 10x working noise); deterministic saw conveys
  ~12px one-shot. Circulation redesign deferred to round 3.
- FOUNDATIONAL finding: species A (169px) is NOT a continuum object (labyrinth
  at dx=0.5; lattice-stabilized at dx=1 — same trap class as M2's dx=1 bond
  ladder). B is continuum-clean (10ktu). Controller decision: canonical working
  pair = B + A' (compact-metastable, 8600tu horizon, documented) at dx=0.5;
  M3 port-classification stands with a continuum caveat; big-species
  re-engineering parked in IDEAS.
Round 3 spawned: blob-machine (B6 gate: >=3 cycles net-upstream B transport against
an isod gradient, efficiency vs do-nothing baseline, integration risk = single- vs
two-species world choice re-verified in-world).


## Addendum 32 — B6 CERTIFIED: the first blob machine (RELAY TUG); BLOBS ladder complete

blob-machine (round 3) delivered and controller-audited the first machine:
a 3-train locomotive circulating a 5-tooth zero-footprint saw track (isok mode,
tau=5.7 in the pair-only drift zone, self-assembled-wall-style y-rails) that
picks up 3 trough-parked cargo blobs head-on and hauls them net upstream against
the load field — 757-780 px per 3600 tu, 5.6-5.8x the do-nothing baseline, 3
seeds + jitter + clean nulls (parked cargo drifts -0.5px downstream). Fresh-seed
controller audit reproduced everything (6/6 blobs upstream, ncomp frozen, M4
shell spacings). Design content: pickup = wake-shell capture as NEW LEADER
(pusher-tug, speed grows with train length); pairs cannot climb any tested saw
(3-train minimum, climb margin 1.53x); railless v1 buckled (honest negative ->
rails); power ceiling at 6-train sheds the rear blob which PARKS (pair-only zone
as parking brake) and is re-collected next lap — a self-healing relay.
Machine v1 delivers displacement, not release: the unbinding/unload primitive is
the mapped missing piece (parked with vvw-binding and max-train-length law).
M0->M5 all certified. The BLOBS ladder the user sketched (persistent excitations
-> flavors -> interactions -> binding -> composite dynamics -> machines that
transport against a background field) is fully realized in autonomous field
physics with no per-blob bookkeeping and no scripted events.


## Addendum 33 — BLOBS phase 2 spawned: dynamical b-field (M6) + rotation (M7)

User direction after reviewing the report page: (1) promote the isok background b to
a bona-fide dynamical field (it already reads as a trilinear b-u-w vertex with a
vacuum counterterm — verified algebraically: the isok perturbation collapses to
-b*(w-u0), zero on vacuum; page updated with the field-theory box) and study its
evolution + backreaction ("u and w push back on b"); (2) attack rotation via
symmetry breaking — heterodimer with different per-species movement vectors — using
the pieces we already have (per-species tau_i dials in the vvw arch). The user's
sharpened certification concern is fine-tuning: rotation must be an attractor with a
kick-angle basin, not a balanced trajectory. Long-game merge: solve the b_target
inverse problem (evolve b from primitive ICs into the discovered sawtooth+rails
machine landscape) => machines emergent from initial conditions alone.
Two searchers spawned: blob-bfield (gates BF1-BF4: coexistence, self-profile +
backreaction curves, mediated interaction w/ control, emergent-structure demo;
b_target teaser probe) and blob-rotor (gates RT1 attractor rotation >=3 revs
+-20deg basin, RT2 cross-species bond curve OR no-go map of mediation channels,
RT3 engineered isok-ring orbit demo). Labyrinth-as-feature parked in IDEAS
(user: "living systems and space-filling curves").


## Addendum 34 — M6+M7 certified: dynamical b-field (autophoresis, stigmergy, b-assembly)
## and the heterodimer rotor (rotation as attractor)

Both phase-2 searchers survived a second infrastructure outage with full disk state
(178/99 result rows) and closed out after consolidation-only resumes.

M6 BFIELD certified. The static machine background promoted to a genuine 4th field
(bounded tanh source, relaxation tau_b, optional D_b) coupling through the exact
isok channel. Gamma=0 reproduces every M4/M5 anchor. Headlines: (1) AUTOPHORESIS —
a parked blob below the drift threshold self-launches (g>=0.005) by climbing its own
lagging hill, c=0.209*g^0.341, audited to +0.3% on a fresh seed; (2) backreaction
map — drag/plow/self-trapping; trail memory law exact to 0.002%; (3) STIGMERGY
certified with controls (trail-mediated attraction/repulsion of a second blob);
(4) BF4 honest partial (noiseless channel mechanism yes, noisy confinement no,
space-partition clean negative); (5) b-ASSEMBLY (audited fresh-geometry): blobs
placed BEYOND the bond basin collapse into M4-shell molecules via their shared
self-dug halo well — and in the searcher's noiseless n=1, the assembled trimer then
self-launched: "the field assembles a machine that walks away". (6) TEASER: one-way
circulation writes an asymmetric sawtooth standing-b — the M5 track shape is a
natural fixed point of motion+relaxation, making the b_target inverse problem
(merge milestone) look genuinely reachable.

M7 ROTOR certified — the user's rotation vision realized as an ATTRACTOR, not a
tuned trajectory. New xv architecture: fully private 3-field species + one weak
cross-v coupling eta (eta=0 is exactly two M4 worlds; vacuum exact for any eta).
The anchor species' v-halo is a self-assembled circular rail (radial well 6-15px,
azimuthally flat) — predicted from stamp radial profiles BEFORE any run (d* 7-9
predicted, 7.5-8.0 observed; the program's first theory-first milestone). The
motile+anchored heterodimer at eta=0.1 rotates SPONTANEOUSLY (round-off seeded,
CW/CCW degenerate), omega dialed by tau1 (0.0035-0.0259 over 5.52-6.10), 17.4
revolutions in the 10ktu longrun, noise-robust to sigma=0.04. Controller audit:
fresh-seed omega +0.5%, cross-bond d*=7.976 exact from d0=12, onset-region point
on-curve. Extra physics: ROTOR-ONLY ZONE (rotates below the pair-travel threshold:
single-static < pair-travel < rotor-spin); rotation STABILIZES the cross-bond
(static dimer metastable, rotating dimer immortal); same-species rotors are
knife-edged (frustration hypothesis confirmed as a basin property — structural
symmetry breaking is the fix). First cross-species binding in the program (v is
the unique sign-changing mediator; w cannot bind — no-go quantified).
Films: docs/assets/blobs/m7_rotor.gif (audited fresh-seed rotor).


## Addendum 35 — BLOBS phase 3: bottom-up equation-space search + top-down factory/genesis

Spatial-dynamics theory (controller): blob existence is subcritical (homoclinic —
no local criterion suffices) BUT the vacuum's SPATIAL eigenvalues are algebraic and
predict tail structure: complex mu with wavelength 10.8-10.9px vs measured M4 shell
spacing 10.9px (1%); the A=tau*Dv invariance is one line in this formalism. This
yields a G0 funnel (temporal stability / bistability / tail eigenvalues) that
screens equation-space candidates in microseconds before any simulation.
Four searchers spawned: l0-sampler (canonical deviation-form genome — vacuum-exact
by construction, generalizing the iso-line trick structurally; funnel + poke/pair
assay battery + MAP-Elites archive + yield curves), l0-evolver (merge = block
composition, to be VALIDATED by reconstructing our own hand-designed vvw/xv
architecture jumps as single merge operations; mutation = theory-coord jitter),
blob-factory (fulfillment-center primitives: roller advection, eta(x) unload docks,
species forks, one glued demo), blob-genesis (close the sawtooth loop: self-written
landscapes that FUNCTION; self-dug ring racetracks; what grows from noise alone).
Compute fan-out to rented Prime pods planned after local funnel validation
(user-authorized). Grounding vision: fulfillment-center world.


## Addendum 36 — genesis certified, sampler stage-1 certified, stage-2 fan-out prep, lit review spawned

blob-genesis certified (reduction map: tooth/ramp/rail/ring/dock all L1-growable;
self-written tracks 10-40x more slope-efficient than hand-built; amplitude ladder
park->circulate->diode; ring self-launch audited at fresh angle 5.7 revs; noise-
genesis theory-backed null — vacuum-exact coupling is quadratic in deviations, so
gamma cannot destabilize the vacuum: no trails-beget-blobs in this coupling class).
l0-sampler stage-1 certified (parity 5/5 incl. rotor omega to 5 digits; G0c predicts
M4 shell to 0.5%; yield curves uniform 2/100 alive vs jitter 49/100; d*/wl law
audited fresh -> band widened to [1.2,1.5]; uni_3034 NON-OSCILLATORY BINDING
replicated+extended = second binding mechanism class; u0-designation-as-gene;
fold-distance geometry). Stage-2 fan-out greenlit: CPU pods at $0.0279/hr
(~2500 candidates for ~$3); worker-bundle prep ordered (sampler's own caveat fixes
+ audit corrections baked in). lit-reviewer agent spawned (areas: dissipative
solitons/Purwins school, homoclinic snaking, self-propelled spots + stigmergy,
collision-based computing, Lenia-family ALife, quality-diversity search, soliton
ratchets) — deliverables REVIEW.md / TRICKS.md / NAMING.md + reinvention audit.

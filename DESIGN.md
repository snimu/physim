> **Historical design log (February 2026)** for the retired raw-port benchmark, whose code
> is archived in `probes/legacy/physim/`. For the current system, see [README.md](README.md).

# physim — a simulated-universe benchmark for doing science
*(working draft — design discussion, v0)*

## 0. One-sentence goal

Build a verifiers taskset where each task drops the agent into a **procedurally
generated universe with hidden laws**, gives it **instruments and an experiment
budget** instead of direct state access, and rewards it for the **predictive
power of the theories it develops** — with worlds deliberately constructed so
that good science requires *choosing a level of description* and *defining the
right observables*, not just fitting curves.

## 1. Contrast with MazeBench (why this is a different kind of task)

| | MazeBench | physim |
|---|---|---|
| What is hidden | the **state** (unvisited rooms) | the **laws** (dynamics, parameters, structure) |
| Dynamics | known, simple, deterministic, learned in a few steps | unknown; the whole point |
| Epistemic act | exploration of a fixed finite structure | inference + experiment design over an infinite hypothesis space |
| An observation | pins down a room forever | never pins down a law; only reweights hypotheses |
| Reward | state achievement (gems, rooms) | predictive accuracy on held-out interventions (epistemic reward) |
| Determinism | every action repeatable | ground truth deterministic given seed, but *observations* are noisy/partial/costly |

Shared DNA with MazeBench that we keep: procedurally generated task instances
from a seeded family (like maze levels), a real engine as ground truth that the
evaluator can replay deterministically, a small fixed tool surface, long-horizon
multi-turn rollouts, deterministic evaluator-side scoring, and
evaluator-only hidden state (the agent never sees the law, like the agent never
sees board hashes).

## 2. The mental model, made precise-ish

Ground truth: a micro state space `X` with dynamics `Φ_θ` (θ = hidden
parameters/structure sampled per task). The agent **never touches X**. It gets:

- **Preparation knobs** `u ∈ U`: boundary conditions, fields, densities,
  stimulation protocols — the levers of experiment design.
- **Instruments**: functions `m_i: X → ℝ^k + noise`, each with a **cost**,
  **resolution**, **field of view**, and **noise floor**. Raw instruments are
  local and expensive (a "microscope patch"); the agent may *define new derived
  instruments* — named programs over raw channels (its candidate observables).

The hierarchy/coarse-graining idea, formalized loosely: a coarse-graining is a
map `π: X → Y`. It is a *good* observable set iff there exists a macro dynamics
`ψ` with

```
π ∘ Φ ≈ ψ ∘ π        (approximate commuting diagram / approximate closure)
```

i.e. the macro level is **approximately autonomous**: knowing `π(x)` is enough
to predict `π(Φ(x))` up to fluctuations (cf. lumpability of Markov chains,
Koopman observables, computational mechanics / "causal states", Hoel-style
causal emergence). The `≈` is exactly the user's precision tradeoff: macro laws
hold statistically, with finite-N fluctuations, and different definitions of
"the same" quantity have different bias/variance/lawfulness.

**Design invariant #1:** every generated world must *possess* at least one good
coarse-graining with a compactly expressible macro law (that's what makes a
"theory of the collective" exist to be found).

**Design invariant #2:** brute-force micro identification must be *economically
infeasible* (budget), not forbidden. The agent that measures the right order
parameter gets clean laws cheap; the agent that tracks particles drowns in cost
and noise. Coarse-graining is then a discovered strategy, not a rule.

**Design invariant #3 (operationalism):** observables are not god-given. The
environment hands over raw channels; "temperature", "polarization", "force–
velocity curve" exist only if the agent defines estimators for them. Whether an
experiment "works" depends on whether the defined observable is one for which a
closed law exists — Bridgman's point, gamified.

## 3. Prior art (and the gap we aim at)

- **BoxingGym** (arXiv:2501.01540): experimental design + model discovery vs
  generative models. Good scoring ideas (expected information gain, prediction
  error). But observables are handed to the agent and simulators are shallow —
  no emergence, no level-choice.
- **DiscoveryWorld** (arXiv:2406.06769), ScienceWorld: game-like discovery
  worlds; breadth over dynamical depth; observables again pre-defined; the
  "science" is often reading the room, not compressing data.
- **DeepMind Alchemy**: latent causal structure per episode, meta-learning of
  structured hypotheses — good precedent for per-task hidden laws, but a small
  discrete latent space.
- Robot-scientist line (Adam/Eve, AI Feynman, SINDy, symbolic regression
  benchmarks): law-finding from data, but no embodied experiment loop, no
  measurement economics, fixed ontology.

**The gap physim targets:** agent-defined observables + hierarchy with genuine
emergence + measurement cost/precision economics, in a procedurally-generated,
exactly-replayable universe with evaluator-side ground truth.

## 4. World families (each a generator: seed → θ → universe)

Alien-ize everything (random constants, warped functional forms, scrambled
names/units) so pretrained physics knowledge helps with *method*, not answers.

1. **Contractile tissue ("muscle")** — flagship, matches the motivating example.
   Micro: a 2D lattice/network of stochastic contractile units (hidden
   attachment/detachment kinetics, nonlinear elasticity, hidden disorder).
   Knobs: clamp length/force, stimulation rate, bath parameter. Micro
   instrument: expensive small-patch imaging. Macro truth: a Hill-like
   force–velocity/force–length law + hysteresis emerges. The agent should
   invent "tension" and "strain" estimators and find the macro law.
2. **Flocking (Vicsek-like)**: hidden interaction kernel + noise; macro:
   polarization order parameter, density waves, a phase transition. Tests
   whether the agent finds the order parameter and maps the phase diagram.
3. **Spin/lattice world (Ising-ish)**: hidden couplings; macro: magnetization,
   susceptibility, critical point, scaling. Cheap to simulate, rich structure.
4. **Reaction–diffusion (Gray–Scott-ish)**: hidden rates; macro: pattern
   wavelength, front speeds, phase regions in knob space.
5. **Coupled oscillators (Kuramoto-ish)**: hidden coupling/graph; macro: sync
   order parameter, critical coupling.
6. **Tier-0 warmups**: single hidden ODE/SDE (alien damped-driven oscillator,
   logistic-ish growth) — no hierarchy, pure design-of-experiments + fitting;
   calibrates the harness and scoring before emergence enters.

Same-universality-class *sibling worlds* (different micro, same macro law form)
enable transfer tests — the strongest evidence an agent found the *theory*
rather than a lookup table.

## 5. Agent interface (verifiers v1 Toolset, MCP)

Small, fixed tool surface (MazeBench discipline):

- `list_knobs() / list_instruments()` — discover the interface, not the laws.
- `run_experiment(prep: dict, protocol: list, measurements: list) -> data`
  — costs budget: sim ticks + per-measurement cost (resolution- and
  FOV-dependent). Returns tabular/array data + remaining budget. Seeded RNG
  per run; *repeating an identical experiment gives a fresh noise draw*
  (irreducible stochasticity — unlike the maze).
- `define_instrument(name, program)` — a derived observable: a program in a
  restricted, sandboxed expression language (start: whitelisted numpy
  expression DSL) over raw channels. Becomes available in `measurements`.
  This is the operationalization move, and we log it — instrument definitions
  are themselves a research artifact worth studying.
- `notebook_write / notebook_read` — cheap persistent scratch state (long
  horizon support; also gives us a window into the agent's theorizing).
- `submit_theory(predictor_program)` — optional/tiered: an executable predictor
  (sandboxed) mapping (prep, question) → prediction + uncertainty. Enables MDL
  scoring (accuracy − λ·description length) and machine-checkable theories.
- `answer_contract(contract_id, prediction, uncertainty)` — the scored act.

## 6. Scoring (the crux — and the main open problem)

**Primary reward: prediction contracts.** The evaluator issues contracts
phrased **in raw, evaluator-defined terms** ("prepare u=…; predict statistic S
of raw output at t=T, with an interval"), sampled across regimes, including
held-out **extrapolation regions** (other side of a phase boundary, knob ranges
the agent could never afford to probe densely). Score = proper scoring rule
(log-loss / CRPS / interval coverage) against ground-truth ensembles replayed
evaluator-side. Tolerances are set by ground-truth ensemble variance, so
irreducible noise is not punished but resolution-limits bite.

Why evaluator-defined S: if the eval scored the agent's own observables, the
agent defines trivial observables with trivial laws ("my constant is constant")
— degenerate. Instead the agent's ontology is **instrumentally** selected: you
invent "polarization" because it is the thing that makes the contracts
predictable. That mirrors why real definitions survive.

**Secondary metrics (report, maybe lightly reward):**
- calibration (uncertainty honesty),
- budget efficiency (score per unit budget — the economics of coarse-graining),
- MDL of submitted theory programs,
- transfer score on sibling worlds,
- structural discoveries via cheap-to-verify claims ("knob k3 is irrelevant",
  "there is a critical point near u* ∈ [a,b]") checked against θ.

**Anti-gaming rules:**
- contracts issued only after the experiment budget is spent/frozen, or
  interleaved with commit-before-run semantics; no post-hoc oracle queries;
- eval prep configs disjoint from the agent's query history by construction;
- the sim engine runs evaluator-side only (like MazeBench's Node bridge);
  tool metadata must leak nothing about θ (audit like MazeBench's
  "board hashes are evaluator-only" discipline);
- per-task alien parameterization defeats memorization.

## 7. Failure modes to design against

1. **Curve-fitting benchmark in a lab coat**: if contracts are all
   interpolations, symbolic regression on raw data wins without any
   level-choice. Fix: extrapolation contracts across phase boundaries, budget
   pressure, transfer worlds, structural-claim contracts.
2. **Ontology leakage**: instrument names, docstrings, or contract phrasing
   that reveal the intended macro variables ("measure_polarization"). Raw
   channels must be bland (fields, positions, counts).
3. **Reward hacking via the sim**: any path where the agent can run the
   ground-truth engine on eval configs. Strict budget accounting + config
   disjointness + evaluator-side replay.
4. **Noise laundering**: agents dodging hard contracts by claiming huge
   uncertainty everywhere. Proper scoring rules + calibration metrics handle
   this if tolerances come from ground-truth ensembles.
5. **Textbook shortcutting**: recognizable physics lets the model skip
   discovery. Alien-ization; also keep some *deliberately recognizable* worlds
   as a control condition to measure the shortcut's size.

## 8. Implementation sketch (Prime verifiers v1)

- Pure-Python/numpy engines (fast enough for lattice/particle worlds at study
  scale; JAX later if needed). Engine deterministic given (seed, θ, protocol).
- `physim` package layout mirroring the addition/mazebench pattern:
  - `worlds/` — generator families (`family.sample(seed) -> World`), each
    exposing `step`, `raw_channels`, `knobs`, and a `macro_truth` module used
    only by the evaluator for contract construction.
  - `instruments.py` — cost model, noise model, derived-instrument sandbox.
  - `contracts.py` — contract sampler + proper-scoring implementation.
  - `taskset.py` — `PhysimTaskData` (seed, family, budgets, tier),
    `PhysimTask` (rewards = contract scores; metrics = calibration,
    efficiency, transfer), `PhysimTaskset` (infinite, generator-based),
    `PhysimToolset` (tools above).
- Everything in-process Python — no Node bridge needed (simpler than MazeBench).

## 9. Milestones

- **M0 (walking skeleton):** one Tier-0 world (alien damped-driven
  oscillator), tools = `run_experiment` + `answer_contract`, log-loss reward,
  end-to-end `prime eval` run with a stock harness.
- **M1 (economics + operationalism):** budgets, noise/resolution cost model,
  `define_instrument` DSL, notebook; contracts with calibration scoring.
- **M2 (emergence):** contractile-tissue or Vicsek family; micro-patch
  instrument expensive, macro contracts incl. extrapolation across a phase
  boundary; measure whether agents invent order parameters (we can literally
  read their instrument definitions).
- **M3 (theories as artifacts):** `submit_theory` predictor programs, MDL
  scoring, sibling-world transfer tasks.

## 10. Open questions (for discussion)

1. Contract language: how expressive can evaluator-side statistics S be while
   staying ontology-neutral? (moments, spatial spectra, hitting times…?)
2. Should instrument *definitions* ever be directly rewarded (e.g., a bonus if
   an agent-defined observable achieves closure), or strictly instrumental?
   Direct reward risks Goodharting; instrumental-only risks weak signal early.
3. Budget calibus: how to set micro-instrument costs so the coarse-graining
   pressure is real but Tier-2 tasks stay solvable within model context limits?
4. One long rollout per universe (MazeBench-style, 100s of turns) vs episodic
   visits with persistent notebook (closer to a research program)?
5. How much stochasticity? Deterministic micro + noisy instruments vs
   stochastic micro. (Probably both, per family.)
6. Theory representation: free-form predictor programs (MDL-scorable, but
   sandbox complexity) vs structured hypothesis DSL (cleaner scoring, less
   open-ended)?


---

# v0.1 addendum — the raw-port interface ("one layer higher")

## The proposal

Drop all named knobs and instruments. The interface to *every* world is identical and semantics-free:

```
run(U) -> Y      U: [T, n_in] floats in [-1,1]   (input ports)
                 Y: [T, n_out] floats            (output ports)
```

The agent is told only `n_in`, `n_out`, and the budget. Ports are anonymized:
inputs couple into the micro substrate as smooth local fields; outputs are noisy
affine reads of local functionals of micro state, with **random gain, random
sign, random offset, shuffled channel order, and some dead channels**. Before an
agent can do experiments it must first do *sensorimotor science*: find the noise
floor, find dead sensors, learn polarities, discover which outputs co-move,
build its own observables — "learn to use its hands."

## Feasibility probe (done, 2026-02; see conversation log)

Built `RawPortWorld`: hidden 28×28 tanh-lattice with neighbor coupling J=1.3
(collective bistability + hysteresis), 8 anonymous input ports (Gaussian bump
fields), 40 output ports (36 live patch-reads with random sign/gain/offset,
shuffled, + 4 dead), measurement noise. A **scripted naive scientist** knowing
only `run(U)->Y`:

- Stage A (babbling: silence + per-port step probes): dead-channel detection
  4/4 correct; responsiveness map recovered.
- Stage B (body schema): sensor polarity 100% correct via global-drive
  co-movement. Geometry partially recoverable from correlation MDS
  (nearest-pair overlap 35% vs 15% chance) — enough for *neighborhoods*,
  which is all we need.
- Stage C (observable): defined its own macro variable m(Y) = sign-corrected
  normalized mean of live channels — i.e. it *invented magnetization* from
  generic operations.
- Stage D (law): swept its own aggregate drive up/down through m(Y): clean
  hysteresis loop (gap 0.79 vs ~0.00 noise), bistable region located
  (up-jump u≈+0.1, down-jump u≈−0.2). Total ≈1.4e5 channel-ticks.

Key empirical insight: the **first thing** blind correlation analysis finds is
the global collective mode — in an emergent world, the order parameter is the
*most discoverable* structure, while the micro law stays invisible. The
interface hides exactly what we want hidden and surfaces exactly what we want
surfaced.

## Why this is architecturally *better*, not just harder

1. **Ontology-neutrality becomes automatic.** Contracts are phrased in port
   terms ("given input program U*, predict statistic S of channels at t")
   — the v0 worry about leaking ontology through tool/knob names vanishes.
2. **One interface, all worlds.** The port-wiring layer (fields in, affine
   noisy reads out, permutation, dead channels) is a world-agnostic adapter:
   write once, wrap any micro engine. World families reduce to swappable
   dynamical cores.
3. **Alien-ization comes free.** Every task looks identical at the surface;
   wiring is resampled per task instance; no tool names to pattern-match.
4. **Two orthogonal difficulty dials.** Interface opacity (dead channels, gain
   spread, sensor lag/filtering, read nonlinearity) vs law depth (hierarchy,
   phase structure). Tiers: T0 clean ports + shallow law → T3 opaque ports +
   deep hierarchy.

## The two real costs, and their mitigations

- **Design burden → certification burden.** We cannot analytically guarantee
  solvability; instead every generated world must pass an automated
  **reference-scientist battery** at generation time (the scripted Stages A–D
  above, generalized): (i) ports responsive above noise floor, (ii) dead/live
  separable, (iii) scripted generic pipeline finds the macro law within budget
  B_ref. Ship only certified worlds; set agent budget as multiple of B_ref.
  The probe script doubles as the certifier. Also gives a floor baseline for
  scoring ("did the agent beat the dumb scientist?").
- **Context bandwidth.** Raw semantics must not mean raw data through the
  context window. The agent submits *protocol programs* (restricted DSL:
  generate U, reduce Y server-side — means, spectra, thresholds crossings,
  its own defined observables) and gets back small summaries. So
  `define_instrument` survives, now as the compression channel:
  `run_experiment(protocol_program, reducers=[...]) -> summary tables`.
  Sensorimotor bootstrap then costs tens of tool calls, not thousands.

## Accepted degeneracy (feature, not bug)

The agent can never distinguish "sensor convention" from "world property"
(gauge freedom: sign flips, offsets, units). Real physics has the same
property. Contracts are in raw channel terms, so gauge-invariance of the
score is automatic.

## Revised M0

One `RawPortWorld`-style task end-to-end in verifiers: tools =
`run_experiment(protocol, reducers)` + `notebook` + `answer_contract`;
certification battery as part of world generation; contracts = interval
predictions of channel statistics under held-out input programs, incl. one
extrapolation contract (drive regime beyond probed range / other hysteresis
branch). Baselines: (a) random, (b) the scripted reference scientist.


---

# v0.2 addendum — drop the DSL: one interface + agent-implemented tooling

Clarifications agreed in discussion (2026-02):

- `U: [T, n_in]` / `Y: [T, n_out]` is array-shape notation: a 2-D table, rows =
  time ticks, columns = ports. One experiment = submit a U table, receive the
  same-height Y table.
- The "scripted scientist" is ~100 lines of deterministic numpy (no LLM): fixed
  probe schedule (silence → per-port steps → global drives → up/down sweep) and
  fixed analysis formulas. Roles: existence proof, world **certifier**, floor
  **baseline**.

## Interface-only environment (replaces the reducer-DSL idea)

Rather than a bespoke restricted protocol/reducer language, expose the world as
a single dumb endpoint inside an agent sandbox that has a general coding
harness (Claude Code / Codex / mini-swe-agent style):

```
world.run(U: float[T, n_in]) -> Y: float[T, n_out]     # costs budget
world.budget() -> {ticks_left, ...}
world.contracts() / world.answer(contract_id, prediction, interval)
```

The agent writes its **own** tools: probe scripts, analysis code, instrument
functions, notebooks — ordinary files + Python in its sandbox. "Build your own
measuring devices" becomes literal. The DSL design burden disappears; the
context-bandwidth problem disappears (raw Y lives in sandbox files; the model
reduces it with code it writes).

Architecture = MazeBench's two-sandbox pattern: harness+agent in sandbox A;
authoritative world engine (with θ, budget ledger, contract oracle) in process/
sandbox B, reachable ONLY through the endpoint above. Ground truth and budget
accounting never enter the agent's reach. Every U submitted is logged server-
side → full deterministic replay of any rollout.

Consequences:
- The verifiers Toolset shrinks to a thin client (or even just an HTTP spec +
  in-sandbox client file the agent can read).
- The agent's code is a first-class research artifact: its instruments and
  theories are readable Python we can diff across models/worlds.
- Scoring unchanged: contracts in raw port terms, proper scoring rules,
  evaluator-side ensembles.
- Optional later: a no-code MCP-tools tier for comparing harness-less models,
  same worlds. (MazeBench keeps game-only tools for hosted training; we can
  mirror that split.)

Open per earlier + new: budget units (ticks × channels read? per-run overhead
to discourage 1-tick spam?), and whether `submit_theory` = "hand us a .py file
path in your sandbox" (probably yes — evaluator copies + sandboxes it).


---

# v0.3 addendum — interactive worlds: (S,A) -> S', state preparation as a control problem

## The model (user proposal, adopted)

The world is a **persistent process**: hidden micro state S(t) evolves
autonomously; the agent's action A(t) enters the evolution map

    S(t+1) = F(S(t), A(t), noise)      A = 0  =>  ordinary autonomous evolution

The agent NEVER sets S directly (no state surgery). Interventions are physical:
they pass through the dynamics. Observation remains through the port layer
Y(t) = ports(S(t)) + noise. `run(U) -> Y` becomes the open-loop special case
(precommit the whole action sequence; ignore observations while it runs).

Consequence: **state preparation is a control problem and a learnable skill.**
"To study S*, first find actions that steer S(0) -> near S*" — exactly the
user's framing.

## Evidence that closed-loop strictly enlarges reachable science (probes, 2026-02)

Probe on two variants of the bistable lattice world, target = hold the agent's
own macro observable m in a band between the two stable branches:

| world | best constant input | best open-loop ramp/anneal | feedback (PI on m) |
|---|---|---|---|
| local coupling (J=1.3, sigma=0.05) | 100% time-in-band | 57% | 100% |
| mean-field coupling (J=1.8, beta=0.7, sigma=0.02), band around unstable m=0 | **0%** (51 protocols) | **0%** (12 anneal timings; lingers ~0 ticks) | **100%** (holds m≈0.00 for 400 ticks) |

So there exist worlds where a whole region of state space (the unstable
manifold) is **unreachable by any open-loop protocol** but fully accessible
with feedback — the inverted-pendulum / voltage-clamp phenomenon. (Hodgkin–
Huxley needed the clamp: membrane voltages that don't self-sustain become
measurable only under feedback.) Also scientifically meaningful: whether
intermediate states are open-loop-preparable *depends on the coupling
structure* (local pinning vs global winner-take-all) — same surface interface,
different experimental accessibility, discoverable by the agent.

## Resolving the tick-latency problem: policy submission

An LLM cannot sit in the loop at world-tick rate (cost, context, latency).
Resolution consistent with v0.2 (agents implement their own tools): the agent
submits **policy programs** — its own code

    policy(t, Y_t, memory) -> A_t

executed tick-synchronously server-side against the live world, seeing ONLY
measured ports Y_t (never S). `advance(policy_or_U, T, channels) -> reduced
observations` is the single world-stepping call; state persists across calls;
`fresh_sample()` (reset to a new draw of initial conditions) is an explicit
costed action (a new mouse, not ctrl-Z). Writing a *working* controller for a
world you don't yet understand itself requires prior system identification
(signs, gains, lags) — instrument-building now literally includes building
clamps/thermostats, and we can read those artifacts.

## New contract types unlocked

1. **Prediction** (as before): statistics of channels under evaluator-chosen
   input programs.
2. **Preparation**: "bring the world into a state where channels satisfy
   predicate P over window W, then release control; we verify." Verifiable in
   raw port terms; ontology-neutral; = synthesis tasks in real science.
3. **Control**: "keep statistic S in band B for duration T while we inject
   disturbances." (Higher tiers.)

## New difficulty axis: control depth

(a) passive observation suffices (astronomy) → (b) open-loop interventions
needed (chemistry-ish) → (c) closed-loop control needed to reach/hold the
states contracts ask about (experimental biophysics). Certification battery
gains a scripted-controller stage (generic PI on the certifier's own macro
observable — shown above to work); tier label = weakest scripted scientist
that passes.

## Budget note

World time advances only inside `advance()` calls (no wall-clock background
evolution) — keeps determinism, replay, and budget accounting exact while
preserving the "world evolves whether or not you act" semantics (a do-nothing
advance still moves S).


---

# v0.4 addendum — scoring: theories as executable observable-process simulators

## Adopted (user proposal)

The primary scored artifact is an **executable transition model of the
observable process**: a program G, submitted from the agent's sandbox, that the
evaluator runs as a simulator of the ports. This *is* "the theory of the world
as seen through the interface," machine-checkable, MDL-measurable, and
diffable across agents/worlds.

## Three refinements (each backed by a probe on RawPortWorld, 2026-02)

1. **G must be allowed internal state.** Signature not (Y_t, A_t) -> Y_{t+1}
   but `G.init(Y_history) -> h; G.step(h, A_t) -> (h', Y_{t+1})`.
   Ports are partial observations; the observable process need not be Markov
   in Y alone (probe: our world happens to be near-Markov at 36 channels —
   residual 0.077 ~ noise floor 0.05 — but this is world-dependent, and with
   6 channels history already helps: 0.079 -> 0.072). The internal state h the
   agent chooses IS its ontology (its macro variables) — readable artifact.

2. **Uniform sampling in Y-space is ill-posed — evaluate along realizable
   trajectories only.** Probe: uniform draws in the Y bounding box sit far off
   the reachable manifold (median NN-distance 4.33 vs 2.50 for held-out real
   states; 28% farther than 99% of real states; dead channels + inconsistent
   patch overlaps mean most Y-box points correspond to NO micro state).
   Deeper: the evaluator *cannot generate ground truth* at an arbitrary Y —
   you cannot set S to realize a given Y, only run S forward. So the
   evaluation measure must be a distribution over **preparation protocols**
   (action programs run on the true world), never over raw Y-points.

3. **One-step comparison is nearly content-free — score K-step rollouts and
   trajectory functionals.** Probe: persistence (Y'=Y, zero physics) achieves
   96% of the best linear theory's one-step accuracy and *wins outright* in
   quiet regimes. 40-step rollouts separate them (MAE 0.277 vs 0.330 and
   growing with horizon). For stochastic/chaotic worlds pointwise rollout
   comparison fails even for the TRUE law -> score **functionals of
   trajectory windows** (means/vars, spectra, crossing counts, transition
   rates), distribution-to-distribution (truth ensemble vs G ensemble),
   normalized by truth-ensemble spread so irreducible noise isn't punished.

## The evaluation measure ("uniform vs physically interesting" resolved)

Sample protocols from a **published protocol grammar** (constants, steps,
ramps, sweeps, random walks, feedback templates — same primitives the agent
uses), stratified:

- S1 autonomous: A=0 relaxation from fresh initial conditions (baseline
  behavior; cheap sanity stratum).
- S2 interpolation: protocol parameters inside the agent's probed ranges.
- S3 extrapolation: amplitudes/frequencies/durations OUTSIDE anything the
  agent tried (drawn wider by construction; the agent knows the grammar, not
  the draws).
- S4 structure-seeking: protocols steering near discovered structure —
  phase boundaries, both hysteresis branches, unstable manifolds (found by
  the certifier's scripted scientist + controller at generation time; this is
  where "physically interesting" lives, without leaking ontology — they are
  just action programs).
- S5 discrimination (later tier): protocols chosen to maximize disagreement
  among a reference set of theories (persistence, linear fit, scripted
  scientist's fit, agent's G) — Bayesian-experimental-design flavored
  evaluation, concentrates scoring power where theories differ.

Headline score = weighted mean over strata (S3/S4 weighted up), each stratum
= mean over protocols of exp(-error/scale) per functional, scale = truth
ensemble spread. Report per-stratum breakdown always.

## Floors and ceilings (every run reports them)

- Floors: persistence G; random G; scripted scientist's fitted linear G.
- Ceiling: the true engine scored through the same pipeline (its own noise
  ensemble) — defines achievable score given irreducible stochasticity.
- Agent skill = position between floor and ceiling, per stratum.

## Anti-gaming

- G runs sandboxed (no network, CPU/memory/time caps, size cap).
- Eval protocols sampled fresh after G is frozen; agent knows the grammar,
  never the draws.
- MDL (program size + runtime) *reported*, only lightly rewarded if at all —
  a giant learned emulator that survives S3/S4 has genuinely captured
  structure; MDL distinguishes "compressed understanding" in analysis.
- Contracts (v0.2/v0.3 point-prediction + preparation + control) remain as
  cheap intermediate reward shaping and as the harness-less tier; the
  simulator submission is the main event.

## Open

- Distributional distance for stochastic G on functional vectors (energy
  distance / MMD) vs simple per-functional proper scores — start simple.
- Whether S5 uses the agent's own G in the reference set (adaptive, powerful,
  but adds evaluator complexity) — defer to M2+.
- Horizon ladder per world family (K short/medium/long) set by certifier
  mixing-time estimates.


---

# v0.5 addendum — generating hierarchy: motif families x random instances x a closure meter

## Question

Design each world's hierarchy by hand, or generate randomly and filter on a
measured "hierarchy property"?

## Answer: both, with a specific division of labor (probe-backed, 2026-02)

**Blind-random mechanisms don't work.** Probe: three N=400 worlds under an
identical slow random-walk drive:
  A: unstructured random dense tanh network (no designed structure)
  B: local lattice (motif: locality) — the RawPortWorld core
  C: 8 modules, strong intra / weak inter coupling + per-module bias
     (motifs: modularity + heterogeneity)

A generic **closure meter** (PCA rank-k coarse-graining -> fit polynomial
macro dynamics z' = f(z, u) -> held-out tests) measured:

| metric | A random | B lattice | C modular |
|---|---|---|---|
| var captured by k=1 | 0.37 | 1.00 | 0.92 |
| 1-step closure R^2 (k=1) | 0.996 | 0.998 | 0.998 |
| micro-ceiling gap (k=1) | +0.002 | -0.003 | -0.002 |
| **drive-only R^2** (z' from input history alone) | **0.96** | 0.76 | 0.71-0.73 |
| 20-step rollout skill vs persistence | 0.86 | 0.65 (k=1) | 0.75 (k=2 > k=1's 0.56) |

Reading:
- All three "close" at one step — closure alone is NOT the discriminator.
- The discriminator is **drive enslavement**: A's collective mode is ~fully
  explained by recent input history (R^2 0.96) — a filtered echo of the drive,
  no autonomous collective memory, nothing to discover. B and C carry state
  the drive cannot explain (R^2 ~0.75 despite near-perfect closure): that
  residual IS the emergent memory (bistability/hysteresis).
- **Micro-ceiling gap ~ 0** (macro fit as good as the best predictor given the
  FULL micro state) = the coarse-graining is genuinely closed: micro details
  add nothing for predicting the macro future. This is the operational
  pi.Phi ~ psi.pi test.
- The meter reads off **k\*** (number of emergent variables): B is a k=1
  world (k>1 adds only fitting instability); C is k=2+ (rollout skill jumps
  0.56 -> 0.75 from k=1 to k=2 — it detects the meso layer). Hierarchy depth
  is measurable, not just designed.

## Generation pipeline (adopted)

1. **Mechanism families with hierarchy-generating motifs** (intentional):
   locality, modularity, timescale separation, conservation laws, symmetries,
   weak coupling between designed layers. Stat mech says these motifs produce
   emergent low-rank structure; we choose motifs, never hand-tune outcomes.
2. **Random instantiation** (per task): parameters, wiring, disorder, port
   layer, gauge scrambling — sampled from the family's distribution.
3. **Certification by meter battery** (filter): keep an instance iff
   (a) sensorimotor battery passes (v0.1); (b) closure meter finds some small
   k* with: closure R^2 high, micro-ceiling gap ~ 0, drive-only R^2 LOW
   (autonomous memory exists), rollout skill > 0 at horizon ladder;
   (c) scripted-scientist (+ controller, v0.3) cracks it within reference
   budget; (d) micro identification infeasible within agent budget (cost
   accounting). Reject the rest; report acceptance rates per family.

The meter output doubles as the **difficulty label**: dim(Y) = verbosity,
k* = macro complexity, closure R^2 / rollout skill = law cleanness,
drive-only gap = how much genuine memory, plus control depth (v0.3 tiers).
Curriculum = sort published worlds along these axes (user: start easy — high-
dim Y, low k*, clean closure — verify agents rediscover baked-in rules; then
push k* up, closure down, control depth up).

Note: the meter is itself a reference theorist (PCA + poly regression). If it
finds the macro law, the task is solvable-in-principle by an agent that
reinvents generic methods — the same certifier-as-floor logic as v0.1.
Numerics: cubic-feature rollouts blow up at overfit k (seen at k=8) —
production meter needs stabilized regression (stronger ridge, saturating
features, clipped rollouts).

## Status

Design pillars all settled: raw-port interface (v0.1-0.2), interactive
persistent worlds + policy programs (v0.3), simulator-submission scoring with
protocol-measure evaluation (v0.4), motif x random x meter generation (v0.5).
Next: implement M0.


---

# M0 status (2026-02-11)

Implemented at `environments/physim` (verifiers v1, chat tier): engine
(modular tanh lattice, D0-D3 presets), session (JSON protocol commands,
budget ledger, stratified contracts, ensemble scoring with channel-range
scale floor), taskset/env (PhysimEnv drives the interaction loop
engine-authoritatively), scripted baselines (null/tail/reference), report
tooling. First grid (3 models x 4 difficulties x 3 seeds): reward decreases
monotonically with difficulty for competent models (pooled Spearman rho=-0.50,
p=0.003); gemini-3.5-flash matches the scripted reference at D0, no model
beats the reference anywhere; gpt-5-nano ~ null baseline. Full numbers:
REPORT.md. Deferred to M1+: coding-harness tier, policy programs,
preparation/control contracts, simulator submission, meter-certified
generation, per-axis difficulty decomposition.


---

# v0.6 pre-note — M4 direction: deeper hierarchy ("emergent chemistry") [DISCUSSION PENDING]

User proposal (2026-02-11, recorded for the M4 design discussion): current
worlds have ~1-2 reasoning layers (grid -> modes/sources/barriers). The bold
target is a THIRD+ layer: modes as "atoms/molecules" that interact with each
other to form larger structures with their own effective theory — an analogue
of chemistry emerging from what is currently more like bulk material
(gas/metal/glass). Known blocker: lattice size (24x24 - 32x32 is too small for
diverse interacting "species"); expect orders-of-magnitude more sites and a
faster engine (vectorization/JAX) plus port layers that only sparsely sample.
Design challenge: motifs whose collective modes are MOBILE and COMPOSABLE
(localized excitations / solitons / domain-wall bound states) rather than
pinned stripes. To discuss after M2/M3 land. Two axes going forward: making
models do better on existing worlds, and making ever more complex worlds.


---

# v0.6 addendum — M4 design thoughts: from bulk materials to "chemistry" [DRAFT for discussion]

## Reading of the goal (from user's framing)

Current worlds have ~2 reasoning layers: cells -> regional switches (modes).
The modes are PINNED (stripe geometry fixes them in place); their "interactions"
are weak couplings we wire by hand. M4's target is a third, EMERGENT layer:
collective objects that are (i) localized, (ii) persistent, (iii) MOBILE,
(iv) interacting — so that "species", "bonds", "reactions" become discoverable
regularities with their own effective theory, none of it hand-authored.

## Probe results (2026-02-12, this session): the substrate exists

Tested Gray-Scott reaction-diffusion (2 fields, 4 params) as candidate core:

1. **Atoms**: at F=0.030, k=0.066 a seeded spot neither dies nor replicates —
   a stable localized object (~45-70 cells across, lives >=12k ticks).
2. **Pair force**: two spots REPEL and equilibrate at a preferred separation
   (~20-21 cells from any initial 6-16) — a measurable pair potential.
3. **Mobility**: a gentle feed gradient (dF/dy ~ 1e-4) drags a spot at
   ~0.6 cells/kilotick — spots are steerable objects, not pinned domains.
4. **Reactions**: crowded 3-spot configs relax to 2 (annihilation); at
   k<=0.064 spots self-replicate (division); at k>=0.068 they die (decay).
   Regime boundaries = reaction thermodynamics, controllable by global knobs.
5. Contrast probe: the CURRENT tanh-lattice bistable family cannot do this —
   implanted domains always collapse (curvature-driven), which is exactly why
   D0-D4 feel like bulk materials.

So: Gray-Scott-class dynamics (or generalizations: multi-species GS, or
FitzHugh-Nagumo with lateral inhibition) is a credible M4 substrate with
laboratory-real emergent objects. All pure numpy, same engine shape.

## Design sketch (three-layer hierarchy)

- Layer 0 (hidden micro): U,V fields on LxL grid, L~96-192 (vs 24-32 today).
  Alien-ized: rescaled/warped kinetics per instance so textbook Gray-Scott
  parameters don't transfer literally.
- Layer 1 (emergent objects): spots/stripes/worms — the "atoms". Their
  existence, size, count are NOT exposed; agents must invent blob detection
  from sparse sensors, as today they invent branch-state tracking.
- Layer 2 (emergent interactions): pair repulsion with preferred spacing,
  binding/cluster geometry, division/decay/annihilation rates as functions
  of the global knobs (feed/kill analogues) and local fields. The "chemical
  theory" = species inventory + interaction laws + reaction conditions.
- Ports: inputs = localized feed/kill perturbations (chemostats + optical
  tweezers analogue: gradients can DRAG spots). Outputs = the usual anonymous
  noisy patch sensors — which now sample a scene of moving objects, so
  sensor readings fluctuate as spots wander through patches (the agent must
  infer objects from correlated transits — genuinely harder observation).
- Contracts (ontology-neutral as ever, but now probing layer-2 physics):
  prediction under held-out feed/kill schedules; preparation ("create/park a
  stable object whose signature sits in channel-band X"; "split it"); control
  ("hold the population signature in band under disturbance"). The certifier
  gains a blob-tracking reference scientist.

## Open questions for discussion

1. **Sensing scale**: with L~128 and ~40-80 patch sensors, most of the world
   is unobserved; moving objects cross sensors intermittently. Is that the
   intended difficulty (real microscopy has the same problem) or do we add a
   coarse "wide-field" channel (cheap, blurry global average) as a T0 aid?
2. **Species diversity**: single GS gives one species (+size variants). Real
   chemistry needs >=2 species with distinct interactions. Options: two
   coupled GS systems (4 fields), spatially varying kinetics, or particle
   types via parameter islands. How much diversity is enough for v1 of M4?
3. **Timescales/budget**: spot dynamics live at 1k-10k ticks. Budgets likely
   x10 current values; engine is fine (still numpy conv ops) but context/
   observation economics need rethink (agents will need server-side reduction
   more than ever — maybe object-level derived instruments become the natural
   define_instrument revival).
4. **Certification**: what is the closure meter for layer 2? Proposal: the
   certifier runs a scripted blob tracker; a world passes if (a) objects
   persist, (b) pair-distance distribution has a stable mode, (c) reaction
   rates are reproducible functions of knobs — i.e., the "chemistry" is
   lawful enough to be discoverable within budget.
5. Keep D0-D4 as-is (bulk-matter track) and add M4 worlds as a NEW FAMILY
   (e.g. C0..C3, "chemistry track")? Recommended: yes — families share the
   port layer, session, contracts, jail unchanged.


---

# v0.6 addendum 2 — unification: one lattice-field template, two regimes (not two families)

User question: is the chemistry direction orthogonal to the single-field worlds
or a generalization? Answer (verified numerically): **a generalization.** Both
existing and proposed worlds are instances of one update template — a
multi-channel lattice field theory:

    x ∈ R^{L×L×C}            (C = number of field channels/components)
    x_{t+1} = x_t + dt · [ S(x) + R(x) + B(u) ] + σξ

    S = per-channel stencil term (diffusion / neighbor averaging; C×C mixing allowed)
    R = pointwise nonlinear reaction (couples channels AT a site)
    B = input-port fields (bump kernels, per channel)

| world | C | S | R | regime |
|---|---|---|---|---|
| D0-D3 tanh lattice | 1 | neighbor avg | tanh saturation − x | bistable bulk (magnet) |
| D4 (+adaptation)   | 2 (x, a) | neighbor avg on x only | tanh(...−g·a); a integrates x | bulk + slow feedback (fatigue) |
| C-track Gray-Scott | 2 (U, V) | true Laplacian, per-channel D | −UV², +UV², feed/kill linear terms | localized objects ("chemistry") |

Checks: recasting the tanh map as x + dt·R(x, x̄) reproduces the original
trajectory exactly (a map is a flow with dt=1); D4's adaptation variable is
already a second channel of the same template; Gray-Scott is the C=2 flow with
a cubic cross-channel reaction.

Physics reading (user's tensor-field intuition): this IS lattice field theory
with a multi-component field — components/"tensor indices" without the
transformation-property bookkeeping (no symmetry constraints tying components
together, which we don't need yet). What distinguishes "bulk material" from
"chemistry" is NOT the template but the REGIME: single-channel saturating
reactions give coarsening/bistability (domains collapse -> bulk switches);
two channels with activator-inhibitor structure + separated diffusion scales
(Dv/Du, timescale ratio) stabilize finite objects. Emergence class is a
property of (C, R structure, D ratios) — i.e., of parameters, not of code.

Engineering consequence: ONE engine core
(channels, stencil, reaction registry, port layer, noise) with families as
parameter presets. The existing D-track becomes the C=1 (and C=2-with-
adaptation) corner of the space; the chemistry track is another corner; the
generator (M4 proper) samples motifs WITHIN this template and the certifier
measures which emergence class a sample lands in (bulk / objects / patterns /
chaos). The difficulty axes gain one fundamental dial: C and reaction
structure. Supporting both tracks is then not "two systems" but two certified
regions of one parameter space.


---

# v0.7 addendum — configurable apparatus: sensors as part of the physical world [ADOPTED direction]

User proposal: sensors need not be fixed. Some INPUT ports, rather than
coupling into the fields, adjust sensor properties (position, sampled channel,
gain/width, on/off). Nothing in the interface distinguishes field ports from
apparatus ports — discovering which inputs move the apparatus (vs the world)
is part of the science, and mechanics must not leak world structure (channels,
grid) explicitly.

## Probes (2026-02-12): the idea works and is discoverable

Built a Gray-Scott world with 1 field port (feed bump) + 1 apparatus port
(sensor y-translation stage), indistinguishable at the interface:

1. **Discoverability signature**: field ports act like FORCES (reading shifts
   while driven, relaxes back on release); apparatus ports act like STAGES /
   integrators (effect persists after release, reverses under opposite drive).
   base=+0.039: field port during/after = +0.041/+0.039 (reverts); apparatus
   port during/after = +0.004/+0.001 (persists), reverse drive returns to
   +0.039. Clean, learnable, and ontology-neutral — exactly the "learn your
   hands" layer, now with movable hands.
2. **Solves sparse sensing as microscopy**: a slow scan (drive apparatus port,
   record readings) localized 2 distant spots as intensity peaks (0.26) that
   the fixed sensor could never see (baseline 0.04). Sensor mobility converts
   "too few sensors" from a wall into an instrument-design problem: scanning
   (slow, thorough) vs parking (fast, local) is a real experimental tradeoff
   with budget consequences.

## Design decisions (proposed)

- Apparatus state lives in the WORLD (part of S_hidden): sensor positions,
  channel selectors, gains, and enable bits evolve under the same tick loop,
  driven by designated input ports through per-world random wiring (which
  port, which sensor, which property, what rate, possibly with inertia/limits
  — apparatus has its own crude dynamics, like real stages/optics).
- Interface UNCHANGED in shape: still n_in ports in, n_out channels out. A
  disabled sensor reads noise around a constant (indistinguishable from the
  existing dead channels — dead channels retroactively become "sensors parked
  off/nowhere", a nice unification).
- Add/remove sensors: implement as ENABLE/DISABLE of a fixed maximal sensor
  bank (n_out constant). Full add/remove with changing output shape is
  deferred — variable-width Y complicates contracts, baselines, and traces
  for little scientific gain over enable/park semantics. Revisit if needed.
- Difficulty dial: fraction of apparatus ports, apparatus rate/inertia, and
  whether key regions are reachable only by moving sensors. T0 worlds can
  ship with all-fixed sensors (current behavior = special case).
- Contracts: prediction/preparation unchanged (raw port terms). New optional
  stratum later: "apparatus contracts" (e.g., configure sensing so channel k
  tracks statistic S under held-out drive) — measures instrument-building
  directly.
- Certifier: scripted scientist gains a stage-detection pass (integrator
  signature) and a scan primitive; worlds must be solvable WITH apparatus use
  (certifier budget includes scanning cost).

## Engine refactor consequence (with v0.6 unification)

One core with three coupled blocks per tick:
    fields  x ∈ R^{L×L×C}: x += dt·[S(x) + R(x) + B(u_field)] + noise
    apparatus a_s (per sensor: pos, channel-mix, gain, enabled):
              a_s += A(a_s, u_apparatus)   (stage dynamics, rate-limited)
    readout Y = sense(x, a_s) + meas-noise
D0-D4 = C=1/2 presets with frozen apparatus; C-track = Gray-Scott presets;
apparatus fraction a new axis. This refactor supersedes "fixed port layer"
assumptions in v0.1-v0.5 texts.


---

# v0.8 pre-note — premature closure: why agents settle for wrong-but-adequate ontologies [DISCUSSION]

Observation (C1/C2 frontier runs): agents stop investigating anomalies once
their model predicts well enough. fable-5 noticed the gain-apparatus channel
behaving strangely, named it "integrator", and moved on; the stage port stayed
"constants/nothing" forever. opus-5 called apparatus ports "inert" after short
probes. Nobody circles back.

Analysis — three distinct causes, in increasing depth:
1. INCENTIVE-CORRECT LAZINESS: the reward is prediction/preparation accuracy,
   not ontological completeness. If "integrator" predicts ch20 perfectly, the
   label is scientifically adequate FOR THE CONTRACTS ISSUED. The agents are
   optimizing what we score. (fable C1: 0.96 accuracy while missing the stage
   — the miss cost it exactly the apparatus prep, 1 of 5 contracts.)
2. NO ANOMALY PRESSURE: real scientists chase anomalies because unexplained
   residuals eventually BITE (new regimes, replication failures, referees).
   Our contracts are drawn from a fixed grammar the agent partially infers;
   residual anomalies rarely bite within one rollout.
3. NO CHEAP CLOSURE TEST: an agent cannot ask "is my model complete?" —
   there is no falsification oracle. Humans get this from peers/textbooks;
   science-as-a-field gets it from time. One rollout has neither.

Candidate mechanisms (to discuss; NOT yet adopted):
A. Scoreboard transparency: publish per-contract stratum names + coverage in
   the ready() response ("5 contracts will probe apparatus behavior") so
   completeness has explicit stakes. Risk: leaks structure hints.
B. Anomaly-completion contracts: evaluator detects channels/ports the agent
   never characterized (from its experiment log) and issues extra contracts
   targeting exactly those. Incentive: explore everything or lose points.
   Risk: incentivizes shallow sweeps of everything rather than depth.
C. Residual feedback outlet: an optional tool `check_model(predictions for
   a NEW self-chosen protocol)` that returns pass/fail at contract tolerance
   (limited uses; costs budget). Gives a falsification oracle without
   leaking answers. Closest to real science (preregistered self-tests).
D. Iterated rollouts on the SAME world (research program): contracts from
   round k+1 concentrate where round k's answers were worst. Anomalies bite
   across rounds. Infrastructure: notebook persistence across episodes
   (already designed in v0; unimplemented).
E. Simply longer budgets + a prompt line ("assume every port and channel has
   a discoverable function; unexplained behavior is usually contract-relevant
   later"). Cheapest; tests whether the limit is conduct or context.

Preliminary read: (1) is working as designed — the benchmark MEASURES
incentive-driven closure; making completeness pay via B or D is the
principled fix; C is the most scientifically interesting tool; E is the
control experiment. Decide after consolidation pass.


---

# v0.8 addendum — closure decision: MEASURE, don't manipulate [ADOPTED 2026-02-13]

User adjudication of the v0.8 pre-note menu: keep the benchmark basic.
Mechanisms B (anomaly-completion contracts), C (check_model self-test tool),
and D (iterated rollouts) are REJECTED for now — each would complicate the
environment's contract with the agent, and (B) would constitute mid-rollout
env adaptation ("multi-turn env refinement"), i.e., a coupled agent-evaluator
loop we deliberately avoid: contracts remain a fixed function of
(world, seed), independent of the agent's answers. Even the prompt tweak (E)
is held: the user's dead-sensor point is decisive — the current prompt warns
"some sensors may be dead", so genuinely inert-LOOKING things exist by
design; a prompt asserting "everything has a discoverable function" would be
FALSE for dead channels and would delete the give-up-vs-persist judgment the
benchmark currently measures. An agent that calls a stage port "constants"
is making exactly the kind of fallible closure call real scientists make
about noise vs signal. That the apparatus prep then costs it points IS the
anomaly biting — scoreboard-mediated, not oracle-mediated.

What shipped instead (v0.4.3): report-only CONDUCT METRICS —
  port_coverage      fraction of input ports driven >= 10 full-drive-tick
                     equivalents over the rollout
  port_energy_min    exploration energy of the most-neglected port
  apparatus_displacement  how far any movable sensor was actually moved
No reward coupling; they quantify thoroughness so closure behavior is
visible in results tables (e.g., fable C1: high accuracy, apparatus never
displaced -> the "integrator" story is legible in metrics alone).

Also noted: iterated-rollout research programs (D) remain interesting as a
FUTURE separate track (persistent notebook across episodes), not as a
modification of the base benchmark.


---

# v0.9 pre-note — description levels for humans [PRINCIPLE, adopted]

User (2026-02-13): as worlds grow more complex, the human-facing description
must move UP levels with them. A world with "proteins" (machines assembled
from field excitations, accomplishing some function) should be described to
humans at the machine/function level — even though the AGENT interface stays
raw ports throughout. The current worlds.html applies one analysis template
to all worlds; that stops scaling at M4.

Adopted principle: each world family documents itself at its NATURAL EMERGENT
level, with panels invented for that level:
- bulk track: modules/branches/hysteresis (current panels are right);
- chemistry track: species-colored object maps, event timelines
  (births/deaths/transits), and for multi-species worlds: binding-distance
  histograms, reaction inventories ("V2 spots die within ~200 ticks of their
  V1 partner being killed"), species-sensitivity of sensors;
- future protein-like worlds: component diagrams, function traces
  ("what the machine does"), assembly/disassembly events.
The god-view generator therefore grows a per-family description module
(viz layers), mirroring how the certifier grows per-family batteries. Humans
get the highest useful level; agents keep getting only ports.


---

# v0.10 — the rich-vs-big criterion [ADOPTED design principle, 2026-02-13]

User: the next C-track difficulty step must NOT come from scaling (more
boundaries, more sensor noise — the D-track recipe). It must come from NOVEL
DYNAMICS with more interesting emergent phenomena. The quality test for a
well-designed hard world:

1. EMERGENCE CHECK (a priori): scripted probes, written with god knowledge of
   the world structure, verify the intended emergent phenomena exist and are
   quantitatively stable (as done for hysteresis, binding, cascades).
2. COMPACT-ORACLE EXISTENCE: there must EXIST a simple theory that solves the
   contracts well — implemented as a small god-parameterized predictor scored
   through the real contract pipeline. Its code size is the world's "theory
   complexity". If only a super-complex solution scores well, the world is
   merely BIG (representationally hard), not RICH (discovery hard).
3. FRONTIER GAP: frontier models score well below the compact oracle.

World quality metric: (oracle_score - frontier_score) subject to
oracle_size small. Rich = high oracle score, small oracle, large gap.
Complex != complicated; rich != big.

Iteration mode adopted: spend cycles inventing/certifying worlds against
1-3 before any frontier spend.


---

# v0.11 — effort-vs-difficulty diagnostic and the calibration lever [2026-02-14]

## Diagnostic (n=53 tools-tier rollouts, latest per model x world x seed)

World hardness := 1 - frontier mean accuracy. Per-model Spearman(hardness, effort):

| effort metric | fable-5 (n=20) | gpt-5.2 (n=14) |
|---|---|---|
| world ticks | +0.35 (p=.13) | -0.18 |
| # experiments | +0.07 | -0.16 |
| turns | -0.12 | -0.25 |
| completion tokens | **+0.75 (p<.001)** | -0.18 |
| workspace chars | **+0.54 (p=.015)** | -0.29 |
| wall minutes | +0.20 | -0.47 (p=.09) |

Reading: fable scales SYNTHESIS (thinking, writing) with difficulty but not
DATA COLLECTION; gpt-5.2 works uniformly less on harder worlds; sol/opus run
fewer experiments on hard worlds (46 vs 78; 80 vs 115). Budget use on hard
worlds: 26-40% across all models — the stopping policy, not resources, binds.
User's ideal property (harder -> try more) currently FAILS for experiments.

## Lever adopted: pay for honest uncertainty (fixed, basic, no coupling)

Intervals were previously reward-free (coverage report-only) — models could
be narrow-and-wrong at zero cost, so extra experiments had no scoreboard
value once a point estimate existed. New interval-calibration reward
(Winkler, alpha=0.2, normalized exp(-W/10*scale)): narrow-right 0.91 >
medium-right 0.74 > wide-honest 0.14 > narrow-wrong 0.03. The only path from
wide-honest to narrow-right is REDUCING UNCERTAINTY = more/better
experiments. Config `calibration_weight` (default 0 = report-only; A/B at
1.0). Contracts remain a fixed function of (world, seed); nothing adapts to
the agent.

## Long-horizon direction confirmed (user): worlds -> organisms, reproduction,
competition, selection; hardest worlds should DECOMPOSE into certified
component sub-worlds (curriculum in our back pocket) — the multi-channel
template + per-family certifiers already give this shape: compose reaction
blocks, certify each layer separately.


---

# v0.12 — B0 feasibility sprint: ecology and selection emerge [2026-02-14]

User greenlight: biology track. Probes (all scripted, god-view):

1. **Carrying capacity**: make feed F a dynamic RESOURCE field R (regenerates
   toward R_max, consumed by organisms: dR = DR·lap R + regen·(R_max−R) −
   consume·R·V). Population grows 1 → ~60 then saturates; too-high consume →
   boom-bust cycles or extinction. Logistic dynamics EMERGE from one added
   field.
2. **Two-species competition on one shared resource** (trade-off: sp1 fast
   k=0.060/consume 0.010; sp2 efficient k=0.0615/consume 0.003): stable
   coexistence ~50/42 with resource drawn to ~70%.
3. **SELECTION — environment picks the winner**: R_max=0.040/0.036 → coexist;
   R_max=0.032 → fast species EXTINCT, efficient species owns the world (58);
   R_max=0.028 → both die. Competitive exclusion controlled by ONE
   environmental knob (resource richness), which ports can perturb.

B0 design (to build): reaction="ecology" — two GS variants + shared resource
field R; ports perturb LOCAL resource regeneration (fertilize/poison
regions) + optional variant-specific seeding; sensors read species-blind
organism density (mixtures, as C3) + maybe resource level on some channels.
Discoverable laws (3 sentences): populations saturate (carrying capacity);
two kinds compete for one resource; scarcity favors the efficient kind.
Contract grammar: population statistics (rate/sd of organism traffic) under
held-out fertilize/starve schedules incl. EXTINCTION-boundary protocols.
Compact oracle: 2-variable logistic ODE per species + exclusion rule —
tiny; passes rich-vs-big by construction if frontier can't find it.
Decomposition (curriculum property): B0 = C0 (single species, static feed)
+ eco-1 (one species + resource: carrying capacity) + eco-2 (two species:
competition) — each certifiable alone; the training ladder is the world's
own factorization.


---

# v0.13 — the evolution roadmap: from god-given traits to emergent adaptation
[PLAN adopted 2026-02-15; feasibility probes PASSED]

## User direction

Traits (greedy/frugal) are currently god-given parameters. The ambition:
behavior should ARISE from lower-level mechanics — like proteins giving rise
to behavior — with reproduction + heredity + selection generating diversity
and adaptation. Iterate toward this, not in one step.

## Feasibility probes (2026-02-15, scripted, PASSED)

Mechanism: a per-cell TRAIT FIELD g ∈ [0,1] ("genome") carried by organism
tissue. The g→(consumption, kill) map is fixed physics ("biochemistry");
behavior and fitness are NOWHERE specified. Inheritance = growth-copying
(new tissue copies the g of the neighboring tissue that grew it — GS spot
division then automatically transmits g to daughters). Mutation = small
noise on g at growth sites. Results:
- Inheritance fidelity: organism-level g coherent; population sd ~0.06-0.09
  maintained by mutation (first attempt with tissue-averaging DESTROYED
  diversity — locality of inheritance is essential).
- SELECTION OBSERVED: scarcity era shifts population mean g 0.50 → 0.41
  (frugalward), no fitness function anywhere.
- ADAPTIVE RECOVERY: population crashes to n=10 under scarcity, then
  re-expands to n=45 AT THE ADAPTED GENOTYPE — evolutionary rescue.
- Directional asymmetry: returning to rich does not reverse g (relaxed
  selection ≠ counter-selection) — realistic, and a discoverable law.

## Staged plan (each stage = build + certify + oracle + frontier-validate)

E0 (next build): reaction="evo" — single species + resource + trait field g.
  Laws: everything from B0a PLUS "populations ADAPT: sustained scarcity
  shifts the population toward frugal phenotypes; recovery follows".
  Sensors: organism density (+ maybe g-sensitive channels: some sensors read
  g-weighted density = "phenotype-sensitive stain"). Contracts: population
  statistics AFTER adaptation eras (non-interpolable in time: the same
  drive gives different outcomes depending on evolutionary history —
  PATH DEPENDENCE, our hardness axis, now from heredity).
  Compact oracle: logistic + one adaptation ODE for mean-g (quantitative
  genetics: dg/dt ∝ selection differential).
E1: trait-dependent TRADE-OFF SURFACES (g 2-D: e.g., consumption vs
  motility). Niche differentiation: coexisting phenotype clusters =
  emergent SPECIES (no god-given variants — B0b becomes a THEOREM).
E2: eco-evo hybrid with waves (B2 coupling): wave-regime-dependent selection
  — which phenotype wins depends on rain rhythm; agents must connect wave
  physics to evolutionary outcome. Expected frontier-breaking.
E3: reproduction bottlenecks + spatial structure (islands/corridors via
  static resource geography): founder effects, local adaptation,
  divergence — biogeography.
E4 (aspiration): open-ended-ness — multi-locus g, epistatic maps
  (g1,g2)→kinetics, recombination on tissue merge. Decomposition property
  maintained throughout: E-track rungs each certified standalone.

## Documentation principle (v0.9) extension

E-track panels will need EVOLUTIONARY descriptions: g-distribution histories
(trait histograms over time), selection-response curves, phylogeny-like
lineage traces if feasible — another level up the description ladder.


---

# v0.13 addendum — genotype→phenotype map shape [DECIDED after probes, 2026-02-15]

User question: should g→phenotype be linear? Reality is more logit/binary
(tree logic)?

## Biology recap (user remembers correctly, with a subtlety)

- MOLECULAR level: responses are typically SIGMOIDAL (Hill functions from
  cooperative binding), often effectively BINARY (threshold traits — the
  liability-threshold model), and regulatory cascades implement tree/boolean
  logic (Kauffman networks). Nonlinearity is adaptive: canalization buffers
  development against mutation/noise (robustness); switch-like responses give
  decisive fate decisions; neutral networks store CRYPTIC variation that
  fuels later evolvability (Hsp90 capacitance).
- AGGREGATE-TRAIT level: Fisher's infinitesimal model — many loci of small
  effect sum to approximately ADDITIVE (linear) trait variation; selection
  response follows the breeder's equation R = h²S. Both descriptions are
  right at different levels.

## Probe results in OUR substrate (same protocol, three maps)

| map | selection response (scarcity era) | phenomenology |
|---|---|---|
| linear | mean g 0.51→0.38; frugal fraction 0.10→0.82 | steady directional selection (breeder's-equation-like) |
| sigmoid (Hill-like, steep at 0.5) | mean g 0.50→0.48; frugal frac 0.11→0.27 (slow) | selection STALLS on flat map regions: mutations there are phenotypically neutral → drift + cryptic variation; only threshold-adjacent lineages selectable → punctuated, slow |
| binary | same stall as sigmoid | discrete phenotypes, drift-dominated genotype |

The sigmoid/binary stall is not a bug — it is canalization + neutral
networks emerging exactly as in real biology.

## Decision

- E0 ships the LINEAR map, justified by the infinitesimal model (g is an
  aggregate polygenic trait, not a single gene): gives a clean discoverable
  adaptation law and a compact quantitative-genetics oracle (dg/dt ∝
  additive variance × selection differential).
- SIGMOID/THRESHOLD maps become their own rung (fold into E1 as "E1-c:
  canalized worlds"): cryptic variation + punctuated adaptation = extreme
  temporal non-interpolability (long stasis, sudden shifts) — a hardness
  axis no other world has; harder to certify/oracle, hence not first.
- Tree/boolean logic arrives at E4 (multi-locus epistatic maps: (g1,g2)→
  trait via AND/OR-like interactions; recombination on tissue merge).
The GP-map SHAPE is thus itself a difficulty dial: linear (learnable) →
sigmoid (cryptic/punctuated) → epistatic-boolean (rugged landscapes).


---

# v0.13 addendum 2 — cross-level map-shape emergence [TRACKED QUESTION, 2026-02-15]

User observation: micro-sigmoid may aggregate to macro-linear (central-limit
style: many sharp switches summing to a smooth dose-response) and conversely
smooth micro rules can compose into effectively switch-like collective
behavior (our own bistable lattices are exactly that: tanh cells -> binary
branch choices). The GP-map shape question therefore RECURS at every
hierarchical level, and what we set at one level need not be what agents (or
oracles) see at the level above.

Tracking plan while building the E-track: at each rung, measure the
EFFECTIVE aggregate map — regress population-level phenotype response on
population-mean genotype under standardized selection pulses — and record
its shape (linear/saturating/switch-like) next to the MICRO map we chose.
E0 (linear micro) prediction: linear aggregate. E1-c (sigmoid micro)
prediction: near-linear aggregate response of the POPULATION PHENOTYPE MIX
(fraction past threshold behaves smoothly) with punctuated per-lineage
dynamics — i.e., the user's inversion, measurable. Report these in the
per-world battery alongside oracle size.


---

# v0.13 addendum 3 — timescales are science, not friction [DECIDED with user, 2026-02-15]

User pushback on the E1 note ("make selection faster/more visible"): real
experimenters LEARN timescales by measuring local rates; the world should not
be sped up for the observer's convenience. Probe verdict (E0, scripted):

- Naive linear extrapolation of short-pulse selection rates to era scale is
  wildly wrong (predicted mean_g -1.26 / +0.04 vs truth 0.448) — because the
  response saturates as variance depletes.
- BUT the saturation is measurable EARLY: rate decays across pulse lengths
  (-1.45e-4/t at 500t -> -1.9e-5/t at 3000t) and sd_g shrinkage is visible
  within 1500 ticks. A rate scientist measuring the DECELERATION can fit the
  saturating law from ~2% of era-scale data.

So E0's slowness is legitimate discoverable structure (the timescale + its
saturation law), not unfairness. DECISION: do not tune timescales for agent
convenience anywhere in the E-track. The "budget use 1-5%" observation is a
finding about agent conduct (they don't do rate-extrapolation science), not
a world defect.

## E1 redirection: complexity you can measure, not speed

E1 = 2-D trait space (consumption axis x a second axis, e.g., motility or
wave-affinity) with niche differentiation -> EMERGENT SPECIES as phenotype
clusters; keep timescales as they fall out of the physics. E1-c (sigmoid)
unchanged. Additional measurable-complexity directions ratified for the
E/B tracks: more fields (predator/pathogen trophic layer), more diversity
(multi-modal founder genotypes), spatial structure (resource geography ->
local adaptation), richer stains (multiple partially-informative phenotype
channels). Difficulty from ONTOLOGICAL BREADTH + timescale inference, never
from clock speed.


---

# v0.13 addendum 4 — port→field coupling policy [CLARIFIED with user, 2026-02-15]

Question: with multiple fields, what do input ports control?

Current per-family wiring (audited):
- tanh/GS/excitable (one dynamic field): every FIELD port couples into that
  single field (bump-shaped local forcing); apparatus ports (C1/C2) couple
  into sensors instead.
- grayscott2 (two species fields): each port carries a hidden SPECIES TAG —
  it perturbs the feed of exactly ONE species (port_species ∈ {0,1});
  discovering which ports feed which species is part of the task.
- ecology/evo (organism fields + resource): ALL field ports couple to ONE
  field — the RESOURCE regeneration rate (fertilize/poison). No port touches
  organisms directly; influence on life is always mediated by the resource.
- ecowave: all ports inject CURRENT into the wave layer; influence on the
  ecology is mediated by wave->rain->resource.

Policy going forward (E1+, multi-field worlds): each port targets ONE hidden
(field, mode) pair drawn per world — e.g., resource-regen here, wave-current
there, maybe a mutagen field later — with the ASSIGNMENT hidden, like
apparatus ports. Port-target diversity becomes another discoverable layer
("which lever moves which stratum of reality") and a difficulty dial:
easy worlds = all ports same field; hard worlds = mixed hidden targets,
including possible two-field mixtures (a port that both warms and stirs).
Rationale: mirrors real experimental levers (a drug hits one pathway; a
heater moves one field) while keeping ontology discovery central. Fully
generalizable in the template: port coupling is a per-port vector over
(fields x modes), currently one-hot, mixtures allowed later.


---

# v0.13 addendum 5 — port coverage guarantee [AMENDED with user, 2026-02-15]

Amendment to addendum 4: every dynamic field must be REACHABLE by at least
one input port (a coverage guarantee), so each stratum of reality is
probe-able in principle. Since ports are anonymous and (in theory) movable,
what matters is coverage of the (field, mode) target set, not which port
carries which target. Unreachable-field worlds (observability without
controllability) are OFF the table for the standard tracks — if ever used,
they would be an explicitly labeled variant, not a default.

Certification addition: world generation asserts every field has >=1 port;
generators sample port->target assignments under that constraint.


---

# v0.13 addendum 6 — E1 probe findings: motility needs patch turnover [IN PROGRESS, 2026-02-15]

E1 (2-D traits: consumption x motility) probe results so far:

1. STATIC resource geography (oases + desert): populations collapse to a
   single sedentary oasis colony; HIGH-MOTILITY founders die by DILUTION
   (spreading thins V below GS viability). "Sedentary wins static worlds" is
   a theorem of this physics — motility can only pay when patches TURN OVER
   (deplete/respawn or wander). This is textbook r/K–disperser ecology
   emerging from the substrate, worth keeping as a documented law.
2. First moving-oases attempt went extinct globally (tuning: constant
   consumption too high + weakened oasis regen). The viability window for
   "wandering oases + motility premium" needs a proper parameter sweep
   (oasis speed x regen contrast x motility cost), certification-style.

E1 therefore stays IN DESIGN. Tuning agenda for next iteration: (a) sweep to
find the coexistence window where sedentary AND motile clusters both persist
(niche differentiation = emergent species); (b) port coverage per addendum 5
(regen ports + stir/geography ports); (c) aggregate-map measurement (does
2-D micro linearity compose to macro nonlinearity?); (d) E1-c sigmoid
variant unchanged in plan.


---

# v0.13 addendum 7 — E1 single-variant selection + session findings [2026-02-15]

Per user: ONE E1 variant to push; other ideas parked in IDEAS.md (created).

## Probes this session (all scripted; none reached a certifiable window yet)

1. Motility trait via diffusion: dies by dilution (addendum 6).
2. Motility via chemotaxis (upwind advection up resource gradients):
   raw gradient-normalized form is noise-dominated in flat regions ->
   incoherent advection shreds colonies. Gradient-saturated form
   (v ∝ dR/(|dR|+eps)) is VIABLE (populations persist at w_mot=0.02 across
   oasis speeds) but motility is NEUTRAL (no selection differential: sitters
   also survive — 4-oasis geometry leaves too much background food).
3. Local adaptation via static geography (oases + desert at the frugal-only
   viability edge regen=6e-5): NO divergence — desert dwellers live off
   resource DIFFUSING from oases (source-sink dynamics) and gene flow
   homogenizes; ecological (density) compensation buffers genotype selection.
4. Seasonal eras (global richness cycling): 0.55 floor under-selects
   (density compensates); 0.35 floor exterminates (E0's selection worked
   because port poison was SPATIALLY PARTIAL — refugia were load-bearing).
5. Seasonal mosaic (north/south alternating winters): survives, still no
   genotype response (sd_g shrinks -> drift/homogenization dominates).

## The load-bearing insight

E0's demonstrated selection lives in a NARROW regime: deep suppression
(effective regen mult ~0.2-0.4) that is SPATIALLY PARTIAL (refugia persist,
re-seeding happens, and the survivor pool is genotype-biased). Passive
environmental drivers so far either under-select or exterminate. Candidate
E1-v1 definition (NEXT SESSION, sweep-first): "storm worlds" — recurring
LOCALIZED deep-poison events (moving storm patches, mult ~0.25, dwell ~3-5k
ticks, covering ~30-50% of the map per event) with calm gaps; this
reproduces E0's proven differential (deep + partial + episodic) as WORLD
physics rather than agent action. Sweep storm depth x coverage x dwell for
(a) survival, (b) mean_g displacement >= 0.04 per storm cycle, (c) recovery.
Contracts then probe adaptation state vs storm history.

## Session discipline note

No build/version bump this session: physics not yet certifiable — pattern
held (probe -> fail -> understand -> re-scope), matching B1/B2 practice.


---

# v0.13 addendum 8 — the blending-inheritance bug and the storm-world fix chain [2026-02-15]

## Honest correction to E0

Colony-level diagnosis of E0's celebrated mean_g shift (0.485->0.447 under
poison): survival correlates with SHELTER (location luck; r=0.46), NOT
genotype (r=-0.08). E0's "adaptation" was mostly survivorship composition.
Deeper: paired-famine tests (symmetric bimodal colonies) show true
g-selection EXISTS at famine mult ~0.5 (frugal beats greedy 41:19 across
seeds) but is nearly regime-symmetric under the linear GP map (rich phases
counter-select), and — decisively — the growth-copy inheritance as
implemented is BLENDING inheritance (V-weighted neighbor averaging), which
destroys variance geometrically (sd 0.03->0.007 over cycles): Jenkin's 1867
objection to Darwin, reproduced in silico. Selection cannot act on variance
that blending erases.

## The fix chain (probes PASSED)

1. COPY inheritance (particulate): fresh tissue (V_old < 0.02) copies the g
   of its single dominant parent neighbor (argmax V), no averaging.
   -> variance persists (sd 0.03-0.08 sustained).
2. ASYMMETRIC GP map: c(g) linear, k(g) saturating (tanh) — famine selects
   harder than richness counter-selects.
3. Storms at the selective sweet spot: depth (regen mult) 0.5 — NOT 0.2-0.35
   (indiscriminate death) — coverage ~full, dwell ~8k, calm ~8k.

Result: sustained directional evolution under storm cycling — mean_g
0.50 -> 0.36-0.39 over 90k ticks (~ -0.02 per cycle, 2 seeds), populations
healthy (n 12-46). THE E1-v1 physics is certified in probe form.

## Next session (build)

- Engine: inheritance mode parameter (copy|blend) — E1 uses copy; decide
  whether to FIX E0 (breaking its results) or version it (E0 stays blending
  as shipped + REPORT correction; E1 = corrected physics).
- E1 "storm world" preset (reaction=evo + storm schedule + asym GP map +
  copy inheritance), certification battery incl. per-cycle dg >= 0.015,
  compact oracle (quantitative genetics with variance maintenance), docs
  (evolutionary panels: g-histogram timelines), frontier validation.


---

# v0.14 pre-note — two deep design questions [DISCUSSION OPEN, 2026-02-16]

## Q1 (user): can the biochemistry itself evolve? Hand-chosen GP maps cannot scale.

Current state: one gene g, one inheritance rule, but the g->phenotype maps
(linear consumption, saturating robustness) are DESIGNED. User wants a
uniform micro-mechanism where phenotype consequences are not hard-coded.

Candidate direction (to discuss, not adopted): replace designed TRADE-OFF
CURVES with designed CONSERVATION CONSTRAINTS, and let allocation evolve.
Concretely: the genome becomes a small vector of couplings that enter the
SAME universal reaction template the organism already runs (uptake rate,
storage rate, repair rate, ...) under a hard flux/energy budget
(sum of allocations = fixed). Trade-offs then become THEOREMS of the
conservation law (flux to uptake cannot go to repair) rather than curve
shapes we pick. One uniform micro-law everywhere; phenotypes = measured
behaviors of the evolved network; the GP map is COMPUTED by physics, not
authored. Scaling story: enrich the coupling space (more network nodes),
never author trait consequences. Certification implication: the battery must
DISCOVER what phenotypes exist (closure-meter logic applied one level up).

## Q2 (user): do sensor-statistic contracts miss higher-level science?
Example: lipid-like fields forming CLOSED BOUNDARIES (protocell walls) —
a topological, non-local property. A theory could ace local sensor
predictions while never representing closedness; adding a "closedness
sensor" would leak ontology.

Probe (2026-02-16, PASSED): topology has OPERATIONAL signatures under
intervention. Dye assay in a membrane world: inject tracer at a central
port; closed ring -> outside sensors read 0.0 forever; ring with an 8-cell
gap -> dye leaks, outside sensors read 0.003-0.008. Separation ~2.7e6 x.
Closedness is decidable ENTIRELY in port/channel terms because the world's
own transport physics computes reachability and delivers the verdict to a
local sensor. This is also how real biology measures compartments (dye
exclusion, gigaseal tests) — the operational definition IS the science.

Implications (draft): contracts stay in port/channel language, but each
emergent-phenomenon class needs a matching INTERVENTION-RESPONSE contract
family whose truth depends on the phenomenon (transport assays, source
switching, two-point response). The certifier must prove discriminability
(closed vs open separation) exactly like the dye probe. Known limits:
(a) phenomena with no causal path from any port (excluded by the port-
coverage guarantee), (b) grammar narrowness — if contracts only ever ask
tail-means under uniform drives, structure never matters; grammar must
grow with the phenomenon ladder.


## v0.14 probe results (2026-02-16): emergent GP maps are possible — the R* theorem

Q1 probes (scripts /tmp/q1_probe*.py, /tmp/q1_sweep.py):

1. NEGATIVE (honest): resource-depletion feedback alone does NOT bend the
   realized-uptake curve. With c(g) linear and constant death, per-capita
   uptake stayed linear in g (incremental slopes 0.00028/0.00023/0.00029)
   until outright extinction at g=0.9. "The world will saturate it for us"
   was wrong at this level.

2. POSITIVE: "enzyme economics" — replace ALL authored trade-off curves with
   linear bookkeeping + conservation:
       income  = c_max * g * V * R      (earn ∝ enzyme ∝ substrate)
       upkeep  = (m0 + m1 * g) * V      (enzymes cost rent, R-independent)
       larder  E ≤ cap * V              (finite storage)
       deficit → burn tissue (bankruptcy), V < V_floor → death
   Then net(g) = V * (g * (c_max*R − m1) − m0) is LINEAR in g with a
   resource-dependent slope sign. The world computes a phase boundary at
       R* = m1 / c_max
   and selection direction is an emergent function of where local R sits:
   | storm regen mult | outcome (60k ticks) | who dies in storms |
   |---|---|---|
   | none (calm) | mean_g drifts UP 0.549→0.570 | — (greed pays when R>R*) |
   | 0.30 (mild) | mean_g RISES 0.626→0.792 | frugal (dead g=0.316) |
   | 0.20 (medium) | mean_g FALLS 0.667→0.584 | greedy (dead g=0.695) |
   | 0.12 / 0.05 (deep) | extinction | everyone |
   Both selection directions and the famine/plenty asymmetry are THEOREMS of
   the conservation law, not authored curve shapes. The break-even genotype
   g_crit(R) = m0/(c_max*R − m1) clips the frugal tail when R>R* and the
   greedy tail when R<R* — a full regime diagram from one linear micro-law.

   Still authored: the constants (c_max, m0, m1, cap) and the conservation
   structure itself. Design principle adopted for the E-track roadmap:
   AUTHOR PRICES AND CONSERVATION LAWS, NOT CURVES. Push authorship one
   level down; let curve shapes, regime boundaries, and trade-offs be
   computed by the world. Scaling story: genome → allocation vector over K
   linear processes under a budget; trade-offs multiply combinatorially with
   zero additional curve-authoring.

   Known open issue for any E2 build: sustained selection at depth 0.2 eats
   variance (sd 0.234→0.072/60k); needs mutation-selection balance, and the
   depth window is again narrow (0.12 extinct / 0.30 inverted) — same
   sweet-spot engineering as E1, now one level down.

## v0.14 measurement-adequacy findings (Q2)

Dye-assay probe passed (see pre-note): topology IS port-decidable
operationally (closed vs open membrane: outside sensors 0.0 vs 0.003-0.008,
separation ~2.7e6x). Real gap identified instead, in the CONTRACT layer:

1. MULTIMODALITY COLLAPSE (concrete scoring flaw, fixable, no leak): truth
   ensembles are collapsed to (μ, τ) and answers scored exp(−|pred−μ|/scale).
   If an emergent property varies across the truth ensemble (membrane closed
   in some draws, cracked in others), truth is BIMODAL; predicting the
   physically-unrealizable mean outscores predicting the structure. Exactly
   where emergence creates structure, the score erases it. Candidate fix:
   distributional contracts scored by CRPS against the truth ensemble
   (answer = a few quantiles or (value,weight) atoms) — stays entirely in
   port language; structure starts to PAY. Applies today to B-track
   competition worlds (winner bimodality), not just hypothetical membranes.

2. GRAMMAR NARROWNESS: closedness only shows up under assay-like protocols
   (localized injection + outside listening). If sampled contracts only ever
   drive uniform tilts, the revealing protocol is never asked. Contract
   grammar must grow with the phenomenon ladder (patch injections exist;
   need them in contract sampling, not just free exploration).

3. MEASUREMENT-ADEQUACY CERTIFICATION (new rich-vs-big leg, god-side only):
   for each god-known emergent phenomenon, certify there EXISTS a contract
   in the sampled family whose truth is counterfactually dependent on it
   (flip the phenomenon with god-mode — crack the membrane — and show the
   contract answer moves by ≫ τ). No agent-visible ontology leak: the agent
   still sees only port-language contracts.

4. Prepare-tier is the strongest leak-free probe of emergent understanding:
   "prepare: outside dye < ε under injection era" can only be satisfied
   reliably by controlling closedness itself.


---

# v0.15 — CRPS distributional contracts + measurement-adequacy certification (2026-02-16)

User direction: build (1) CRPS distributional scoring AND (3) auditable
adequacy certification as a cross-check pair; if (1) empirically recovers
(3)'s signal, (1) becomes the general mechanism and (3) stays the audit.

## CRPS scoring (built, verified)

- Answers may include "quantiles" at fixed levels {0.1, 0.25, 0.5, 0.75, 0.9}.
  Point answers = degenerate distribution (backward compatible).
- Score = exp(-max(QS - QS_floor, 0)/scale), QS = 2x mean pinball loss over
  the fixed levels vs the truth ensemble; QS_floor = the ensemble's
  leave-one-out self-score (irreducible floor; perfect distributional
  knowledge -> accuracy ~1, not exp(-spread/scale)).
- VERIFIED limits: deterministic truth -> exactly legacy exp(-|err|/scale)
  (point@truth = 1.0, off-by-scale = e^-1). Bimodal truth: point@mean 0.34,
  point@mode 0.32, honest bimodal distribution 1.00 — multimodality collapse
  (v0.14 finding) is fixed: structure now PAYS.
- reward_accuracy is now CRPS-based; legacy point accuracy kept as
  report-only metric (accuracy_legacy) for leaderboard continuity.
  Floor spot-checks: B2 null/tail 0.32/0.42 (legacy 0.28/0.35),
  D4 0.24/0.22 (0.22/0.22) — no floor inflation.
- Prompts (chat + tools) state the scoring honestly and generically: "where
  the system is stochastic or has multiple regimes, an honest distribution
  scores strictly better than any point." No ontology leak (no phenomenon is
  named; the grammar is world-independent).

## Measurement-adequacy certification (built, probes/adequacy_cert.py)

Per contract template (fixed contract_seed, aligned across world seeds):
  A = Var_instances(mu) / mean_instances(tau^2)
A >> 1 => the contract's truth depends on the instance's phenomenon state
(e.g. which species wins) far beyond measurement noise — the phenomenon is
MEASURED. A ~ 1 => instance-independent law question. Auditable, god-side
only. Cross-check: correlate A with the CRPS gap between an instance-aware
oracle (own-seed quantiles) and climatology (cross-seed pooled quantiles);
high Spearman rho = CRPS recovers the auditable signal.

## Q1 follow-up recorded (user's screening principle)

Parameter choice for emergent-economics worlds (c_max, m0, m1, cap, storm
depth) should become a SEARCH with the phenomenon battery as objective:
sample parameterizations, certify interestingness (regime flips, bimodality,
selection), keep the interesting ones. The R* sweep in v0.14 was the manual
prototype. Anthropic-flavored: we only ever observe worlds that passed the
screen — acceptable for a benchmark, documented as such.


### Cross-check results (2026-02-16, /tmp/adequacy_report.json)

Fixed verbatim templates, 5/3/4 instances x 4-rep ensembles:
- B2 (winner bimodality): A = 6-834, CRPS gaps 0.33-0.93, Spearman(log A,
  gap) = 1.000. Instance-aware oracle beats climatology by up to 0.93
  (S2-poison carrying capacity: climatology 0.068 — pooled-across-winners is
  nearly worthless). CRPS recovers the auditable signal EXACTLY.
- D2: A spans 0.01-8296; rho = 0.904. The two A~0.01 contracts are
  instance-invariant equilibrium questions — adequacy cleanly flags "this
  contract does not ask about the instance" and climatology scores 1.000
  there, correctly.
- C4: every contract carries instance structure (A = 477-2145 from
  alienized wave-parameter variation; smooth, not multimodal). Gap saturates
  0.51-0.63 with no dynamic range in log A -> rho uninformative (-0.19).
  Both measures saturate TOGETHER: consistent.
VERDICT: (1) validated against (3). CRPS is the general mechanism; the
A-ratio stays as the cheap god-side audit certificate. Note: A conflates
emergent multimodality (B2) with smooth law variation (C4) — both are
legitimately "instance-specific truth the agent must pin down"; the
distinction (multimodal vs smooth) is visible in the pooled histogram if
needed, not in A.


---

# v0.16 — E2 ships (enzyme economics); B3 parked after probe campaign (2026-02-16)

## E2 (reaction="enzyme") — DESIGN

Authored surface, in full: income = c_max·g·V·R; upkeep = (m0 + m1·g)·V;
larder E ≤ cap·V; deficit burns tissue (V -= deficit/0.05); V < 0.05 dies;
colonization copies dominant-neighbor genotype + N(0, mut); storms multiply
regen by depth on a ~1000-tick alienized cycle; ports multiply regen ±0.8
(same fertilize/poison interface as B/E tracks). NO trade-off curves, NO
per-genotype death law: k is constant. Everything E0/E1 authored as curve
shapes is now computed by the ledger:
  R* = m1/c_max  (emergent critical resource);  net(g) = V·(g·(c_max·R−m1)−m0)
  → greed pays iff local R > R*; famine bankrupts the greedy first; the
  gene pool oscillates with the storm clock (verified: mean_g swings
  0.2-0.35 ↔ 0.8-0.95 across phases with variance regenerating each cycle).

PARAMETERS BY SEARCH, not design (user's screening principle): 48 candidates
sampled in THEORY coordinates (R*_target, m0/m1, c_max, cap, depth); battery =
survival ∧ bidirectional phase-conditioned selection ∧ variance maintenance ∧
R*-straddled-by-weather. v1 raw-coordinate search: 0/48 pass (extinct or
monotone). v2 theory-coordinate search: 4/48 pass; winner c_max=.0191,
m0=.00209, m1=.0094, cap=.105, depth=.13 (R*=.49). Search coordinates matter:
sample where the theory says the physics lives. Certify (engine): alive_frac
≥ .08 all spans ∧ mean sd_g ≥ .06 ∧ mean_g range > .05 — 20/20 seeds.
Settle = 10k substeps (~2.5 storm cycles): worlds arrive climate-adapted.

Readout: density + G·V "metabolic stain" mix (same convention as E0/E1).
Battery: storm-phase-aware oracle dist 0.974 / point 0.969; floors: null
0.251, tail 0.174, persistence 0.227. Oracle gap will be measured vs frontier.

## B3 (reaction="ecowave2") — PARKED, preset kept as probe record

Built: two-variant ecology (B0 trade-off) + wave-fed rain (B2), S5
winner-boundary contracts, full engine plumbing. Probe campaign findings:
(1) ANODE-BREAK INVERSION: sustained negative current RAISES wave rate in the
FHN layer (rebound excitation) — "famine" drives make it rain harder; poison
is not famine in a wave-fed world. (2) CSR-like exclusion: rich rain lets the
greedy variant overrun the frugal (competitive exclusion), opposite of the
intended selection story; soft-k2 climates coexist but no era protocol
demonstrated a winner FLIP (frugal extinctions only, from wave-shadow
geometry). A winner-flip world needs either birth-rate-based trade-offs
(fast-breeder vs stress-tolerator) or spatially structured rain shadows as
refugia — parked to IDEAS; taskset does not expose B3.

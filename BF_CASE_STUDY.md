# BF Prime Agent case study

The [Results page](https://swpo.github.io/physim/results.html) reports one selected
completed BF rollout for each of seven models. This is a case study of experimental
strategies and prediction failures, not a replicated benchmark. The machine-readable
[evidence snapshot](docs_source/data/bf-case-study.json) is the authoritative source
for scores, usage, individual case results, and plotted trajectory slices.

## Recorded condition

- Prime Agent v0.9.5, upstream commit
  `a7d791bc1be09793ed5f3ec05bf4cccbc60679ea`.
- Frozen image `physim-prime-agent:0.9.5`, SHA256
  `fa15a03560309ccdf45d329f6430cb02a17d265f3e876dce909c9c7c1d7fb237`.
- Prompt `interface-only-v2`; apparatus `centered-pulse-v2`.
- BF bundle SHA256
  `38d159a8052bb0fc24d0d8feefe3985ac645fb19954f2c84aa54954a948b561e`.
- Fifteen held-out programs, 64 forecast members and two independent truths per
  program; equal weighting of cases. Reward is `1 / (1 + primary_joint_energy)`.
  An invalid grading case gives zero overall reward.

Each rollout started with a fresh agent home, container, and observations. The
agent had no simulator source, registry, grading truths, or general internet
access. Model calls passed through Verifiers interception, including subagents
and compaction. Native subagents used the parent's configured model. Sonnet used
Anthropic Messages, Luna/Terra used Responses, and Qwen/GLM/Grok used Chat Completions
through Prime. Sonnet used native one-hour prompt caching.

No aggregate experiment, turn, token, or dollar caps stopped these selected runs.
Predictor limits remained: 4 CPUs, 8 GiB memory, 3,600 CPU/wall seconds, 512 MiB
total artifacts, 256 MiB per file, and 1,024 MiB temporary space.

Each model row records its exact source and bundle identities, trace ID, public
validation outcomes, and hashes of the grade, trace, and native usage records.
Those source hashes identify frozen research snapshots, not Git commit IDs.
The released configs described in the project README use a different condition;
they do not reproduce this campaign merely by selecting BF.

## Selection and accounting

Qwen 35B's submitted predictor failed four grading cases. Its zero reward is
retained as a model outcome; the predictor has not been repaired. GLM's displayed
run is a blind retry after an unexplained early stop without a predictor. This
selection prevents treating the table as seven unselected performance samples.

Costs and tokens include delegated work. Provider-reported costs are used where
available; other costs are estimated from recorded native usage and prices.
Unknown Grok/GLM cache-read prices are charged at the full input rate in the
estimate. Requests without usage records are omitted. Conservative spending
reserves are not treated as billed cost.

## Retrospective reward presentation

The single-page website applies the logarithmic reward
`max(0, min(-log10(S), K)) / K` with `K=2` to each saved mean energy `S`.
An invalid predictor receives zero; `S=0` receives one. These are recalculated
rewards from the existing rollouts, not new model runs. The original condition
above predates the explicit precision target in the current prompt.

The original evidence snapshot retains its recorded rewards and energies.
[Recalculated rewards](docs/data/bf-reward-summary.json) record the source hash
and mapping; the [calibration record](docs_source/data/reward-calibration.json)
contains the simulator-based precision calibration across all three worlds.

## Available evidence and reproduction

The snapshot and [submitted Python sources](docs_source/examples/case-study)
support inspection of the analyses and plots. The source files are inert review
artifacts: fitted arrays and serialized models are not included, so these downloads
alone do not execute or regrade the submitted predictors. Full observations and
traces remain in the original local campaign artifacts.

With NumPy and Matplotlib installed, `python scripts/render_bf_case_study.py`
regenerates figures from the committed snapshot. Ordinary documentation builds
use only the standard library. See [REPRODUCING.md](REPRODUCING.md) for commands.
The renderer's optional `--capture` reads the original local campaign directories;
it does not run agents, execute submitted code, or deserialize model pickles.

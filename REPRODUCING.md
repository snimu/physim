# Reproducing Physim experiments and results

This guide collects implementation and reproduction details for people and agents
working from the repository. Installation and Docker commands are in the
[project README](README.md#install-and-run-locally); the website describes the
scientific setting, experimental interface, scoring, and results.

## Select the recorded condition

The released preparations and the BF Prime Agent case study are different
experimental conditions. Do not substitute one for the other when reproducing
a result.

- The three released world configs in [configs/physim](configs/physim) (`p4g2_044.toml`,
  `bf_trail_lab.toml`, `xv_rotor_lab.toml`) pin Hugging Face revision
  `dcd6abd5eae76a47f326c70518315d2d1e101d86` and the earlier laboratory preparations.
  See [release instructions](RELEASING.md) for portable installation.
- The seven-model BF case study uses `centered-pulse-v2`, the `interface-only-v2`
  prompt, Prime Agent, and a 15-program suite. Its
  [evidence snapshot](docs_source/data/bf-case-study.json) records source and bundle
  identities, selected rollout IDs, scores, usage, and plotted arrays. The
  [case-study record](BF_CASE_STUDY.md)
  describes the runtime and run selection. Full local observations, fitted model
  assets, and traces are not included in the documentation downloads. Its bundle is
  published at dataset revision `bd77a0da2f14eef352bd80c4a38dff426e5c1bed` as
  `bundles/bf_trail_lab_centered_v2/38d159a8052bb0fc24d0d8feefe3985ac645fb19954f2c84aa54954a948b561e`;
  no shipped config selects it.

The current website recomputes reward from those saved energy scores using
`R = max(0, min(-log10(S), K)) / K` with `K=2`; zero energy maps to one and invalid
predictions map to zero. This is retrospective scoring, not a new rollout. The
original snapshot retains its original rewards. Derived values and source hashes
are in [the reward summary](docs/data/bf-reward-summary.json).

New runs expose the requested `reward_precision` in the `interface-only-v3-log-reward`
prompt. Set `env.taskset.task.tools.reward_precision` independently of inference and
experiment budgets. The prompt condition and reward mapping are otherwise fixed in the
code, so reproducing an older run, such as the case study's `interface-only-v2` prompt
with reward `1/(1+S)`, needs the source from before commit `66e28be`.

Every result should identify four objects:

| Object | What it fixes |
|---|---|
| World | Genome, simulator revision, and numerical profile |
| Preparation | Initial fields, apparatus, source, time origin, and noise policy |
| Suite | Preparation, API contract, programs, score groups/scales, truths, and aggregation |
| Run | Predictor, observations, model/harness settings, limits, validity, and scores |

Use full revisions and content hashes, rather than a mutable “latest” label.
Changing the sensor layout, starting state, or scoring definition changes the
corresponding identity.

## Registry and bundles

The [registry guide](registry/README.md) documents preserved and eval-ready worlds,
generation recipes, run history, candidate measurements, checkpoints, and lineage.
Recipe records may contain Python source; inspecting records does not execute it.
The [generation API](packages/blobkit/GENERATION.md) explains how to run recipes,
define metrics in Python, search, and harvest worlds.

Laboratory bundles contain data, not executable Python:

```text
bundles/<preparation-name>/<bundle-sha256>/
  manifest.json       # identities, numerical profile, source versions and hashes
  world.json          # field genome
  preparation.npz     # initial fields
  apparatus.json      # probes, source and control mapping
  suite.json          # programs, contract, score groups and scales
  truth/              # independent reference realizations
  checks.json         # reproduction and validation evidence
```

The loader requires a full dataset commit, downloads the selected profile within
byte caps, verifies hashes, and checks array headers before allocation. Verified
cached bundles can be loaded with `--offline`. See the
[bundle format](schemas/README.md) and
[preparation workflow](generators/physim/EVALUATION_WORKFLOW.md).

## Prediction interface example

This zero predictor checks array layout without a model API key, laboratory, or
simulation cache. It does not test predictive accuracy.

```sh
git clone https://github.com/swpo/physim.git
cd physim
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install numpy
.venv-docs/bin/python docs_source/examples/predictor.py docs_source/examples/request.json
```

On Windows, use `.venv-docs\Scripts\python`. The twelve-channel example returns
`all_finite: true` and these shapes:

```text
(64, 3, 12, 13)  # device0: samples, times, channels, positions
(64, 2, 12, 19)  # device1
(64, 1, 12, 2)   # global
```

Channel counts depend on the selected world. Follow its supplied contract rather
than hard-coding the twelve-channel example. Prediction functions must preserve
query order and output shapes and return finite values. The seed may be unused
by a deterministic predictor.

## Reproduce the released reference score

With Python 3.12 and the workspace installed:

```sh
uv sync --locked
uv run physim fetch --repo seanpohorence/physim-worlds \
  --revision dcd6abd5eae76a47f326c70518315d2d1e101d86 \
  --path bundles/p4g2_044/0c133190c1c86450f56651b47e35f0d729f6a84c7c51a4bc7d91850a9a392ff2 \
  --profile evaluation
# Use the directory printed by fetch:
uv run physim inspect --bundle /path/printed/by/fetch
uv run physim demo --bundle /path/printed/by/fetch --output outputs/reference-demo
```

This checks seven interface requests and reproduces the released persistence
predictor's 15-case energy of **0.8271209896216252**, using four forecast members
and two retained truths per case. It makes no model calls and advances no new
simulation. It is separate from the BF case study, which uses 64 forecast members.

## Model evaluations and new experiments

Follow the [environment README](environments/physim/README.md) and
[configuration guide](configs/physim/README.md) for model-provider setup and
evaluation commands. Select a preparation explicitly: there is no automatic
scan of every eval-ready world, and missing selection is an error. The
[project README](README.md#validate-and-evaluate-a-predictor) covers Docker
validation and grading of submitted Python.

Check the chosen config's harness, prompt, apparatus, and limits before running.
Published configs and campaign-specific configs need not share those settings.
Model evaluations make paid API calls; regenerating documentation figures does
not. For a new suite, use the
[preparation workflow](generators/physim/EVALUATION_WORKFLOW.md).

## Rebuild the reported figures

Most figures and films on the page come from `scripts/render_bf_thread.py`. It runs
native simulations from hash-verified registry artifacts, with no model inference, and
downloads the published p4g2_044 bundle once. It needs the development environment
(NumPy, SciPy, Matplotlib) and FFmpeg; its
[README](docs/assets/bf-thread/README.md) describes the checks and options:

```sh
PYTHONPATH=environments/physim:packages/blobkit python scripts/render_bf_thread.py
```

The results heatmap comes from the case-study snapshot, which includes the exact
scores and small slices of the saved grading arrays. With NumPy and Matplotlib
installed:

```sh
python scripts/render_bf_case_study.py
python scripts/build_docs.py
python scripts/check_docs.py
```

These commands neither run agents nor execute submitted predictors. The case-study
renderer's optional `--capture` deliberately refreshes the snapshot from the original
local campaign directories; those large artifacts are not required for ordinary builds.

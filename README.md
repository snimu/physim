# Physim

Physim studies whether agents can learn to predict unfamiliar physical systems
through experiments. Worlds are interacting spatial fields. An agent observes
and intervenes through instruments, then submits a Python function that predicts
sensor readings under new experimental programs.

```python
def predict(actions, queries, n_samples=64, seed=0):
    return {"samples": [array_for_each_query]}
```

Each sample is a coherent possible trajectory across times and instruments.
Joint energy scores compare forecasts with independent physical realizations;
lower is better.

**[Documentation](https://swpo.github.io/physim/)** ·
[Worlds](docs/index.html#worlds) · [Prediction API](docs/index.html#prediction) ·
[Evaluation](docs/index.html#evaluation) · [Results](docs/index.html#results)

For agents and developers: [reproduction guide](REPRODUCING.md), including data
identities, the runnable prediction example, released reference scores, and the
BF case study's separate experimental condition.

## Install and run locally

Use Python 3.12 for repository development. The workspace contains Physim
0.13.0.dev0 and its simulator dependency, blobkit 0.3.5. The latest published
Physim release remains 0.12.2; its pinned preparations differ from the new BF
case-study condition described in the [reproduction guide](REPRODUCING.md).

```sh
uv venv --python 3.12
uv pip install -e ./packages/blobkit -e './environments/physim[reference,hub]'
uv run physim inspect --bundle /path/to/reference-bundle
uv run physim demo --bundle /path/to/reference-bundle --output outputs/reference-demo
```

For repository development, `uv sync --locked` installs the workspace, native
Verifiers integration, and development tools.
The reference extra pins NumPy 2.5.2 and SciPy 1.18.0 for native reproduction.

The [published world dataset](https://huggingface.co/datasets/seanpohorence/physim-worlds/tree/dcd6abd5eae76a47f326c70518315d2d1e101d86) contains all 24 registry records and three
verified evaluation preparations, with archived provenance. Code is Apache-2.0
and world data are CC-BY-4.0. The dataset revision is
`dcd6abd5eae76a47f326c70518315d2d1e101d86`; downloads, offline reuse, and native
reference checks passed without credentials. Both [Physim](https://github.com/swpo/physim/releases/tag/physim-v0.12.2) and
[Blobkit](https://github.com/swpo/physim/releases/tag/blobkit-v0.3.5) now have public,
checksummed release distributions. The Physim release includes a portable setup
archive and explicit configs for the three preparations. See the [release instructions](RELEASING.md).
Once downloaded or exported, the runtime does not need the research checkout.

`demo` runs the packaged persistence predictor through seven interface checks and
all 15 cases. It reproduces **0.8271209896216252** with four forecast members and
two retained truths per case. It makes no model calls or new simulation advances.

Run a short native experiment explicitly:

```sh
uv run physim experiment --bundle /path/to/reference-bundle \
  --request scripts/physim/examples/short-experiment.json --output outputs/short-experiment
```

Each experiment restores the exact physical start and draws fresh independent
noise. The example charges 0.06 of the 50-unit maximum horizon.

## Validate and evaluate a predictor

Submitted Python executes in Docker, with only its artifact and observations
mounted. The world bundle stays on the trusted host.

```sh
docker build -f scripts/physim/docker/predictor.Dockerfile \
  -t physim-predictor:0.12.0 scripts/physim/docker
mkdir -p outputs/observations
uv run physim validate --artifact scripts/physim/examples/predictor --observations outputs/observations
uv run physim grade --bundle /path/to/reference-bundle --artifact scripts/physim/examples/predictor \
  --observations outputs/observations --output outputs/zero-grade
```

The example is an intentionally inaccurate zero predictor. For a model-driven
investigation, build `scripts/physim/docker/agent.Dockerfile` as
`physim-agent:0.12.2`, and configure [configs/physim/eval.toml](configs/physim/eval.toml).
The standard taskset ID is `physim`; `physim_r6` remains a compatibility alias.
Select a local bundle or one of `configs/physim/p4g2_044.toml`,
`bf_trail_lab.toml`, and `xv_rotor_lab.toml`. Each pins one published preparation;
there is no automatic selection of all eval-ready worlds. Missing selection is
an error before model execution.
Its experiment budget is the single source for the prompt and service limits.
Model runs require separately configured provider credentials and incur API costs.

The development package also supports the full
[Prime Agent harness](environments/physim/PRIME_AGENT.md), including native provider
interfaces, caching, subagents, and an offline integration test. The campaign
runner reports spend without automatically stopping an authorized run on dollars.

## Data identity and current scope

The reference covers one prepared `p4g2_044` world: four activators, eight channels,
a 256 × 256 periodic grid, and movable probes with 13 and 19 slots. The bundle is
3,732,420 bytes of listed payloads plus its manifest. It includes the exact fields,
apparatus, 15 programs, score groups, and 30 retained truth realizations.
World, preparation, suite, and run have separate content identities.

Two additional laboratories, `bf_trail_lab` and `xv_rotor_lab`, are prepared with
11 programs each, fresh scientific evidence and completed native model pilots.
Their four- and six-port bundles, recipes and observations are preserved in the
[registry](registry/README.md). See the [scientific report](handoff/eval_preparation/REPORT.md)
and [repeatable preparation workflow](generators/physim/EVALUATION_WORKFLOW.md).

Reference/development results on this disclosed preparation do not demonstrate
unfamiliar-world generalization. The primary groups in c006/c007 miss some fine
switch/recovery timing; the suite preserves that limitation and the existing data.
Model results use 64 forecast members, unlike the four-member persistence control.

HF downloads require a full immutable commit and verify byte sizes and hashes.
Local loading and verified-cache reuse work offline. See [the bundle format](schemas/README.md).

## Repository map

Blobkit also provides the complete world-generation workflow, with custom Python
metrics, evolutionary search, and harvesting. Recipes, run history, and lineage
are recorded alongside the worlds:

```sh
uv run blobkit generate generators/physim/recipes/small_search.py --registry outputs/small-search
uv run blobkit registry verify outputs/small-search
```

See [the generation API](packages/blobkit/GENERATION.md) and [the registry](registry/README.md).

| Area | Purpose |
|---|---|
| `environments/physim/` | Installable Verifiers v1 taskset and prepared-world runtime |
| `generators/physim/` | Python recipes, registry import/export, and reference validation |
| `scripts/physim/` | Dockerfiles, examples, release helpers, and existing scientific checks |
| `configs/physim/` | Evaluation settings and approved release metadata |
| `packages/blobkit/` | Installable simulation, evolutionary search, metrics, and harvesting library |
| `registry/` | Genomes, recipe sources, generation runs, checkpoints, and lineage |
| `tests/` | Generic package checks and local registry/bundle regressions |
| `schemas/` | Bundle and catalog format contracts |
| `docs_source/`, `docs/` | Edited sources and generated static GitHub Pages output |
| `probes/` | Historical research, older engines, and run evidence |
| `handoff/` | Historical audit records and maintainer migration evidence |
| `outputs/`, `dist/` | Ignored local runs and release products |

The first four directories follow Prime Intellect's residency conventions.
Blobkit is a separate dependency; `packages/` is specific to this workspace.
The environment and portable preparation workflows are proposed in
[Prime draft PR #22](https://github.com/PrimeIntellect-ai/residency-environments/pull/22).
Blobkit, exploratory research, and this website remain here. The local environment
copy stays until the upstream contribution is accepted and the research workspace
has been adapted to consume it as an installed dependency.
Older engines are archived under `probes/legacy/physim/`. See
[REPOSITORY.md](REPOSITORY.md) for validation commands and the upstream boundary.

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

Use Python 3.12 and uv. `uv sync --locked` installs the Physim environment
(0.13.0.dev0, pinned from the residency repository), an editable Blobkit 0.3.5, the
native Verifiers integration, and development tools. The environment requires NumPy
2.5.2 and SciPy 1.18.0 for native reproduction. See [the development guide](DEVELOPMENT.md)
for ownership and dependency updates.

World data are published on Hugging Face as
[`seanpohorence/physim-worlds`](https://huggingface.co/datasets/seanpohorence/physim-worlds/tree/bd77a0da2f14eef352bd80c4a38dff426e5c1bed).
The environment pins revision `bd77a0da2f14eef352bd80c4a38dff426e5c1bed`, whose catalog
lists three evaluation preparations, BF, XV and `p4g2_044`, among 24 world records with
archived provenance. Code is Apache-2.0 and world data are CC-BY-4.0. List the
preparations, fetch one, and run its packaged reference checks:

```sh
uv sync --locked
uv run physim catalog --repo seanpohorence/physim-worlds --revision bd77a0da2f14eef352bd80c4a38dff426e5c1bed
uv run physim fetch --repo seanpohorence/physim-worlds --revision bd77a0da2f14eef352bd80c4a38dff426e5c1bed \
  --path bundles/bf_trail_lab_centered_v2/38d159a8052bb0fc24d0d8feefe3985ac645fb19954f2c84aa54954a948b561e
uv run physim inspect --bundle /path/to/bundle
uv run physim demo --bundle /path/to/bundle --output outputs/bf-demo
```

`fetch` verifies every file against the pinned revision and prints the bundle
directory. `demo` runs the packaged persistence predictor through seven interface
checks and every program. For BF it reproduces **0.4970086688520715** over 15 programs,
with four forecast members and two retained truths per program. It makes no model
calls or new simulation advances.

Run a short native experiment explicitly:

```sh
uv run physim experiment --bundle /path/to/bundle \
  --request scripts/physim/examples/short-experiment.json --output outputs/short-experiment
```

Each experiment restores the exact physical start and draws fresh independent
noise. The example charges 0.06 of the 50-unit maximum horizon.

## Validate and evaluate a predictor

Submitted Python executes in a disposable Docker or Prime runtime, with only its
artifact and observations available. The world bundle stays on the trusted host.
The installed environment provisions its scientific runtime dependencies.

```sh
mkdir -p outputs/observations
uv run physim validate --runtime docker --artifact scripts/physim/examples/predictor --observations outputs/observations
uv run physim grade --runtime docker --bundle /path/to/reference-bundle --artifact scripts/physim/examples/predictor \
  --observations outputs/observations --output outputs/zero-grade
```

The example is an intentionally inaccurate zero predictor. For a model-driven
investigation, configure [configs/physim/eval.toml](configs/physim/eval.toml). It evaluates
every preparation in the installed environment's pinned catalog, one task each; pass
`--env.taskset.task.tools.bundle /path/to/bundle` to evaluate a single preparation.
The standard taskset ID is `physim`; `physim_r6` remains a compatibility alias.
Its experiment budget is the single source for the prompt and service limits.
Model runs require separately configured provider credentials and incur API costs.

The environment also supports Verifiers' native
[Prime Agent harness](environments/physim/PRIME_AGENT.md);
`scripts/physim/smoke_prime_agent.py` is a no-charge integration test. The campaign
runner reports spend without automatically stopping an authorized run on dollars.

## Data identity and current scope

Each evaluation preparation is a content-addressed bundle with the exact prepared
fields, apparatus, programs, score groups, and two retained truth realizations per
program. World, preparation, suite, and run have separate content identities. All
three current preparations use the `centered-pulse-v2` apparatus on a 256 × 256 periodic
grid, with two movable probes of 13 and 19 slots:

| Preparation | Ports | Programs | Payload bytes |
|---|---|---|---|
| `bf_trail_lab_centered_v2` | 4 | 15 | 1,916,173 |
| `xv_rotor_lab_centered_v2` | 6 | 15 | 2,502,577 |
| `p4g2_044_centered_v2` | 12 | 19 | 4,173,278 |

See the [preparation evidence](handoff/evaluation_campaign_20260916/SCIENCE.md) and the
[preparation workflow](generators/physim/EVALUATION_WORKFLOW.md). These suites are
disclosed development material: results on them do not demonstrate unfamiliar-world
generalization. Model results use 64 forecast members, unlike the four-member
persistence control.

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
| `environments/physim/` | Links to the environment maintained in the residency repository |
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
Blobkit, exploratory research, and this website remain here. The research workspace
installs the environment from a pinned residency commit; it has no local copy of
the environment source.
Older engines are archived under `probes/legacy/physim/`. See
[REPOSITORY.md](REPOSITORY.md) for validation commands and the upstream boundary.

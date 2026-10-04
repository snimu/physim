# Repository organization

The active layout follows [Prime Intellect's residency-environments guidance](https://github.com/PrimeIntellect-ai/residency-environments/blob/01d9f5f80572b7ec82575b10d45a800ed844e496/AGENTS.md),
reviewed at commit `01d9f5f80572b7ec82575b10d45a800ed844e496`.

| Directory | Responsibility |
|---|---|
| `environments/physim/` | Documentation links to the externally maintained environment |
| `generators/physim/` | Executable recipes, historical registry import, reference export and validation |
| `scripts/physim/` | Images, examples, release helpers, existing local validation |
| `configs/physim/` | Portable evaluation settings and release metadata |
| `tests/` | Upstream generic package checks and local registry/bundle regressions |
| `packages/blobkit/` | Installable simulation, generation, metrics, search, and registry library |
| `registry/` | Immutable world, recipe, run, and lineage records with archived code/data artifacts |
| `schemas/` | Versioned data formats |
| `docs_source/`, `docs/` | Edited documentation and generated static site |
| `probes/`, `handoff/` | Preserved research and audit evidence |

## Blobkit and the upstream contribution

Prime has no `packages/` convention. Its `pmpp-hard` environment depends on a
separately released `kernelguard` package, which is the closer precedent for our
simulator. Blobkit belongs in a separately installable library, because it serves
both native environment execution and research/data generation. Physim pins the public Blobkit 0.3.5 wheel URL and SHA-256; the local uv
workspace resolves it from `packages/blobkit/` during development.

Generation and evaluation share Blobkit's simulation implementation. The package
also provides customizable Python metrics/operators, evolutionary search,
scheduling, checkpoints, and harvesting. Concrete recipes call those APIs from
`generators/physim/`. Their source, settings, and execution history are archived
with the worlds in `registry/`; reading the registry does not execute code. The
environment does not import generation APIs or depend on the generator checkout.
Harvested genomes acquire physical world/preparation/suite identities when
prepared and validated for evaluation.

The original ownership plan is recorded in
`handoff/architecture/PLAN.md`. Blobkit source and releases remain in this
personal repository. The intended upstream contribution includes the Physim
environment and its portable evaluation-specific generation, preparation and
validation workflows, together with configs and Docker/build support. Evaluation
imports the installed Blobkit simulation API without importing campaign scripts.

The Prime candidate includes the environment, explicit evaluation configs,
Docker/build support, and portable BF/XV preparation and validation workflows.
The preparation downloader follows immutable registry references and fetches only
the selected world's required inputs. Fresh continuation, truth generation,
mechanism controls, and registry round-trip checks use installed packages without
the personal research checkout. Historical search and initialization evidence
remain archived in the registry; the portable recipes start at saved endpoints.
The contribution is open as [draft PR #22](https://github.com/PrimeIntellect-ai/residency-environments/pull/22).
See [the verification report](handoff/pr_preparation_20260915/REPORT.md) for checks and reproduction evidence.

This repository retains Blobkit, exploratory research, and the website. The research
workspace now installs the environment from a full commit in the residency fork.
Environment source is maintained only there, including before upstream acceptance;
`environments/physim/` here contains documentation links only. See [DEVELOPMENT.md](DEVELOPMENT.md)
for dependency updates and testing with a local environment checkout.

Prime asks for actual eval smoke runs and maintains generic package checks. Our
existing scientific regression checks are retained under `scripts/physim/validation/`
for local reproducibility; they are not proposed as new upstream per-env tests.
`tests/test_envs.py` checks the installed dependency, release pins, and editable
Blobkit source. Environment package builds and generic package checks belong to
the residency repository. Its root workspace, tests, and CI are maintained there.

## Development and validation

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -n auto tests -v
uv run python scripts/physim/validation/test_blob_round6.py --gates toy native
uv run python scripts/physim/validation/test_blob_round6_eval.py
uv run python scripts/physim/validation/test_blob_round6_explore.py
uv run python -m unittest discover -s scripts/physim/validation -p test_r6_verifiers.py
uv run python -m unittest discover -s scripts/physim/validation -p test_bundles.py
uv run python scripts/build_docs.py
uv run python scripts/check_docs.py
```

Set `PHYSIM_TEST_BUNDLE` to a verified evaluation bundle to enable the additional
bundle/cache/reference tests. Without it, those checks explicitly skip. Native
migration checks also need the original research fixtures. CI runs the
independent checks; [RELEASING.md](RELEASING.md) covers native and clean-install
validation. The environment README contains the eval CLI smoke command.

The root uses Python 3.12, uv, and Prime's Ruff F/I rules at line length 120.
The installed environment's four Physim reference files (`blobround6.py`, `blobround6_eval.py`,
`blobround6_explore.py`, `devices.py`) and the historical blobkit implementation
must retain their bytes: scientific manifests bind their exact source bytes.
Changing their formatting would invalidate those identities. This is an explicit
local exception disclosed in the PR, not a recertification of the law.

## Historical boundaries

The active installable blobkit source is `packages/blobkit/`. The original
`probes/blobs/blobkit/` tree remains as provenance and for old research scripts.
New changes belong in the active package. The old engine, servers, and tasksets
have moved out of the installable environment into `probes/legacy/physim/`.
Only migration helpers explicitly activate those legacy modules. The historical source fixture remains in `probes/legacy/physim/physim/blobdata/`
for research imports; it is not part of the installed environment.

The R6 scheduler, scorer, experiment service, and CPU kernels keep their original
bytes. Five device definitions were extracted with identical syntax trees.
`handoff/repo_cleanup/` preserves the earlier cleanup evidence;
`handoff/residency_alignment/` records this reorganization and the pre-move source.
`handoff/blobkit_polish/` records standalone library packaging and CPU/CUDA checks.
Research caches, retained truths, rollouts, and frozen run manifests are preserved.
The installed runtime loads only explicit standalone bundles.

Edit `docs_source/`, then rebuild/check `docs/`. The release staging helper updates
world metadata. Runs and binary products belong in ignored `outputs/` and `dist/`.
Do not stage historical logs, process IDs, caches, or bulk output with source changes.

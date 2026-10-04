# Development and package ownership

This repository is the research workspace and the home of **Blobkit**, the simulator and generation library. The **Physim environment package** is maintained only in the residency-environments repository. Research scripts import that installed package for preparation, instruments, scoring, and evaluation.

The dependency chain is research scripts → Physim environment → Blobkit. Blobkit has no runtime dependency on Physim. The `environments/physim/` directory here contains links for existing documentation URLs, not an installable package.

## Install and test

Use Python 3.12 and uv:

```sh
uv sync --locked
uv run pytest tests -q
uv run pytest packages/blobkit/tests -m 'not accelerator and not slow' -q
uv run python scripts/physim/validation/test_blob_round6.py --gates toy
uv run python scripts/physim/validation/test_blob_round6_eval.py
uv run python scripts/physim/validation/test_blob_round6_explore.py
uv run python -m unittest discover -s scripts/physim/validation -p test_r6_verifiers.py
uv run python -m unittest discover -s scripts/physim/validation -p test_bundles.py
```

`pyproject.toml` and `uv.lock` pin Physim to a full commit in our residency fork while the upstream PR is open. That package also pins the Verifiers harness fixes. The root uv override selects the editable `packages/blobkit/` workspace member; installing the environment outside this workspace uses its public, checksummed Blobkit release.

Set `PHYSIM_TEST_BUNDLE` to the original verified `p4g2_044` bundle for the optional historical reference checks. `scripts/physim/check_clean_install.py` installs the pinned environment with its released Blobkit dependency in a separate directory and checks a reference demo plus a short native experiment without model calls.

## Where changes go

- Simulator, generation library, and Blobkit releases: `packages/blobkit/` here.
- Environment runtime, agent tools, prompts, scoring integration, harness setup, and portable environment recipes: the residency checkout.
- Research campaigns, exploratory generators, registry evidence, and the website: here.

For an environment update, commit and push in the residency checkout, then update the full `physim.rev` in this repository's `[tool.uv.sources]` and the matching `physim` URL and `source_commit` in `configs/physim/release.toml`. Update the commit in the documentation links in `environments/physim/README.md` and `environments/physim/PRIME_AGENT.md` as well. Run `uv lock`, `uv sync --locked`, and the integration checks. The dependency test rejects inconsistent pins. There is no environment source to copy back.

`configs/physim/eval.toml` is the research preset for the pinned environment: it selects all evaluation-ready preparations in the package's immutable catalog. Per-world presets and harness examples, including Qwen context settings, live in the residency repository's `configs/physim/` directory.

## Test changes in both checkouts

Install the locked dependencies first, then temporarily replace only the environment with an editable sibling checkout:

```sh
uv sync --locked
uv pip install --no-deps --editable ../residency-environments/environments/physim
uv run --no-sync pytest tests/test_apparatus.py tests/test_variable_worlds.py -q
```

Use the actual path to your residency checkout. `--no-sync` preserves this temporary local environment override while Blobkit remains editable here. Restore the pinned environment with `uv sync --locked` before the full dependency/provenance checks or a reproducible run. No machine-specific checkout path is committed.

## Releases and published evidence

Build Blobkit here with `uv build --package blobkit`. Build or release the Physim environment from its residency checkout. `RELEASING.md` retains the historical release evidence and dataset workflow; the older Docker recipes under `scripts/physim/docker/` reproduce the published 0.12.x setup, while the current environment provisions portable runtimes itself.

Campaign snapshots include the installed environment files and their installation provenance as well as local research and Blobkit sources. A changed installed environment invalidates a previously frozen campaign.

The website's two downloadable agent manuals and its retrospective reward mapping use frozen, hash-checked inputs in `scripts/fixtures/`; [the fixture provenance](scripts/fixtures/README.md) records their original source. These are documentation inputs. Live agent prompts and reward behavior belong to the residency environment package. The V1 website manual's stale reward paragraph is corrected to match its preserved template. Updating an environment pin does not update these snapshots or the article's evidence. Documentation builds require only the Python standard library and no installed environment.

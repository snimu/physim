# World data releases

Code is Apache-2.0 and world data are CC-BY-4.0. The approved dataset destination
is `seanpohorence/physim-worlds`, recorded in `configs/physim/release.toml`.
Runtime code and documentation belong in GitHub; world payloads and their
generation provenance belong in that separate Hugging Face dataset. Archived
recipe source artifacts retain the code license. The current [public snapshot](https://huggingface.co/datasets/seanpohorence/physim-worlds/tree/dcd6abd5eae76a47f326c70518315d2d1e101d86)
was published on 2026-09-14 at `dcd6abd5eae76a47f326c70518315d2d1e101d86`.
It contains 24 world records, 19 distinct genomes, three eval-ready preparations,
and 204 provenance artifacts. All 330 files were downloaded anonymously and
verified; both bundle profiles support offline reuse, and all three reference
checks and short native simulations passed. Receipts are in
`handoff/hf_release_20260914/`. Public [Blobkit 0.3.5](https://github.com/swpo/physim/releases/tag/blobkit-v0.3.5)
and [Physim 0.12.2](https://github.com/swpo/physim/releases/tag/physim-v0.12.2)
distributions are available with SHA-256 pins. The Physim setup archive includes
portable world configs and Dockerfiles. Current portability receipts are in
`handoff/portable_release_20260915/`.

The dataset-card update at `0813ee4d0a4e97a12bbf598d5d43a45eddf5492f` links Physim 0.12.2
and documents Hugging Face's verified Parquet conversion. Across the two card
updates, only `README.md`, `registry/README.md`, and `release.json` changed. The
portable configs deliberately retain the original data revision above because
all scientific payloads and catalog rows are identical. The viewer contains
24 world rows and three evaluation rows; both converted tables match their
source JSONL exactly.

The contribution-guide update at `1d8b73624669aea004befd54ec050bb7280f1678`
adds `CONTRIBUTING.md` and links it from both dataset READMEs. It updates the
release manifest to inventory the guide; all scientific files and catalog rows
remain unchanged. The editable guide is `registry/CONTRIBUTING.md`, which release
staging copies to the dataset root. Publication and example-validation receipts
are in `handoff/registry_contribution_20260915/`.

The first live 0.12.1 smoke exposed a stock bash-harness setup timeout while
fetching dependencies inside a fresh container. Version 0.12.2 ships an agent-image
recipe that pre-caches those dependencies, as Prime's `pmpp-hard` images do, and
uses offline uv plus a disabled pip index at runtime. The exact installed stock
harness starts with Docker networking disabled in 2.2 seconds. This is image
preparation; the environment continues to use native Verifiers error handling.

## Rebuild and verify the candidate

Run from the development workspace with the preserved historical inputs available:

```sh
uv run python generators/physim/export_reference_bundle.py --output dist/reference-bundle
uv run python generators/physim/check_reference_parity.py --bundle dist/reference-bundle \
  --output handoff/residency_alignment/native_parity.json
PHYSIM_TEST_BUNDLE=dist/reference-bundle uv run python -m unittest discover \
  -s scripts/physim/validation -p test_bundles.py
uv run python scripts/physim/check_clean_install.py --bundle dist/reference-bundle \
  --workdir /tmp/physim-clean-release --report handoff/residency_alignment/clean_install.json
uv run python scripts/physim/prepare_world_release.py --bundle dist/reference-bundle \
  --registry registry --output dist/hf-worlds-next
uv run python scripts/build_docs.py
uv run python scripts/check_docs.py
```

Use fresh output directories. The exporter extracts the exact historical physical
start, serializes apparatus, and copies 15 verified native truth files. It does
not regenerate truths or call a model. Staging exports the entire verified generation registry and every eval-ready
bundle. The original reference bundle is supplied with `--bundle`; BF and XV are
reconstructed from their registry artifacts. The HF directory contains separate
world and evaluation catalogs, a dataset card, code/data licenses, and a checksummed
`release.json` inventory. Missing declared evaluations fail staging. The evaluation loader reads only
its data bundle and never executes recipe sources.

Before staging, verify the registry and refresh its browsing projection:

```sh
uv run blobkit registry verify registry
uv run python generators/physim/export_registry_catalog.py --registry registry --sync-docs
```

`generators/physim/import_registry.py` imports the known historical worlds and
available evidence. The original evolutionary recipe for a sourced world may be
partial; its registry record must retain those gaps. New `blobkit generate` runs
archive recipe code, settings, seeds, candidates, checkpoints, and harvested worlds.

Build Blobkit here with `uv build --package blobkit`. Build Physim from its
residency checkout with `uv build environments/physim`. Inspect their payloads: the Physim distributions
exclude archived engines, private arrays, and model outputs. Blobkit's CPU source
must retain its bundle-bound hashes. The 0.3.5 integrity table covers the installed
package; the historical 0.3.4 table is preserved separately. Blobkit's own test
suite covers CPU reference assays and CUDA parity, batching, and record handling.
See `packages/blobkit/README.md` and `handoff/blobkit_polish/` for scope and receipts.

The Docker recipes in `scripts/physim/docker/` preserve the published 0.12.x setup.
For the current environment, use the linked environment README and `DEVELOPMENT.md`.
Validate `scripts/physim/examples/predictor`, then grade it on the reference bundle.
The zero predictor should pass the interface gate while scoring poorly.

## Code release and upstream prerequisites

1. Source and distributions are published from isolated release commits:
   Blobkit `bfdd4319fbbbf1fe92e20afad3c5e9118c8d862e` and
   Physim `eb6647cb429226dc43b27db6950329ed849b92d9`. Wheel package bytes match
   those commits. Work in the development checkout remains unstaged.
2. Physim pins the public Blobkit wheel URL and SHA-256. Its own release includes
   a checksummed wheel, source archive, `requirements.txt`, and portable setup archive.
   Do not install the unrelated PyPI project named `physim`.
3. The world data are published and verified at the snapshot below. Preserve its
   full commit when reproducing evaluations; keep the rollout dataset separate.
4. For a new code release, run `check_published_install.py` with its full wheel URL,
   SHA-256, configs, a fresh work directory, and a report path. This installs from
   public URLs, fetches all three selected worlds, checks offline reuse and native
   task loading, reproduces reference scores, and runs fresh short simulations.
5. Use the installed environment's runtime setup and run a stock Verifiers smoke using one of
   `p4g2_044.toml`, `bf_trail_lab.toml`, or `xv_rotor_lab.toml`. The base `eval.toml`
   now selects the installed package's immutable catalog. A supplied local bundle
   overrides that selection.
6. Prepare the focused residency contribution described in `REPOSITORY.md`.
   Maintainers still need to choose the external runner's config and model panel.

Download the verified current snapshot:

```sh
uv run physim catalog --repo seanpohorence/physim-worlds --revision dcd6abd5eae76a47f326c70518315d2d1e101d86
uv run physim fetch --repo seanpohorence/physim-worlds --revision dcd6abd5eae76a47f326c70518315d2d1e101d86 \
  --path bundles/p4g2_044/0c133190c1c86450f56651b47e35f0d729f6a84c7c51a4bc7d91850a9a392ff2 --profile evaluation
uv run physim fetch --repo seanpohorence/physim-worlds --revision dcd6abd5eae76a47f326c70518315d2d1e101d86 \
  --path bundles/p4g2_044/0c133190c1c86450f56651b47e35f0d729f6a84c7c51a4bc7d91850a9a392ff2 --profile evaluation --offline
```

The catalog also lists the BF and XV bundle paths. The published suites are
disclosed development material. Future held-out
suites need distinct identities and an explicit access policy.

## Residency evaluation review

Checked upstream main at `01d9f5f80572b7ec82575b10d45a800ed844e496` on 2026-09-14.
The repository's [maintainer notes](https://github.com/PrimeIntellect-ai/residency-environments/blob/01d9f5f80572b7ec82575b10d45a800ed844e496/.github/MAINTAINERS.md)
distinguish automatic code review and package checks from model evaluation: its
CI does not run models.

An external evaluation workflow does exist. The [latest PR #20 report](https://github.com/PrimeIntellect-ai/residency-environments/pull/20#issuecomment-5572869974)
lists Qwen3.5-2B, Qwen3.5-9B, Qwen3.5-122B-A10B, and DeepSeek V4 Flash, with
GLM-5.3 judging, and links a run in `PrimeIntellect-ai/env-reports` triggered by
`snimu`. Earlier reports identified reward exploits that the contributor fixed
before reevaluation. Some inline reviews identify `prime-agent` as their author
and `snimu` as their checker. The linked workflow and repository returned HTTP
404 with the available access. Its trigger mechanism, configuration precedence,
resource provisioning, and default model/sample selection remain unverified.

Upstream [AGENTS.md](https://github.com/PrimeIntellect-ai/residency-environments/blob/01d9f5f80572b7ec82575b10d45a800ed844e496/AGENTS.md)
says automated evaluations read `[tool.verifiers.eval]` for omitted sample counts.
It recommends an initial one-example, two-rollout, four-turn smoke. This does not
establish that the external runner loads a named config or supplies world paths.
Physim currently declares one example and one rollout, requires an explicit
bundle, and never scans the registry to select worlds.

Before requesting that review:

- Use the public, checksummed Blobkit and Physim distributions and published world
  bundles. Prebuilt Docker image publication is optional; both Dockerfiles are
  included in the portable setup archive.
- The three portable world configs now select fixed preparations and keep model
  choice overrideable. A changing set of eval-ready entries is never an implicit
  benchmark default. Run the three configs separately to evaluate the fixed set.
- Confirm whether the external runner accepts our config/setup or requires a
  runnable bare taskset default. The portable configs now resolve pinned HF sources on
  another machine. Bare taskset invocation still requires explicit selection.
- Agree on repeated-rollout counts and how the report interprets Physim's
  continuous reward. Keep raw joint energy and persistence controls available;
  grading programs inside one bundle are not separate taskset examples.
- Use Verifiers' existing trace status, typed errors, truncation, retry, and resume
  mechanisms. No separate failure detector is needed. Completed rollouts without
  a valid predictor now earn zero, with a recorded `no_predictor` or
  `invalid_predictor` reason. Infrastructure failures remain native errors.
- Review the solver boundary and scoring for reward exploits, including private
  truth access, experiment-budget bypasses, and artifact mutation after submission.
  Preserve the existing scientific definitions while validating those boundaries.

The recorded BF and XV live pilots establish native execution locally. They do
not establish portability to the external runner or performance across its model
panel. The portability report records subsequent checks against the published contribution.

The evaluation defaults favor capability over efficiency: 1,024 turns, 1,048,576
output tokens, 24 hours, 1,000 experiments, 50,000 simulation tu, and 128 checks of
each kind. The environment README documents native Verifiers overrides for longer
runs and distinguishes exploration from the existing predictor execution limits.

Framework behavior was checked against the installed Verifiers 0.3.1 source and
the official [evaluation](https://github.com/PrimeIntellect-ai/verifiers/blob/fb9d6d7f7bfc8dd6492c15a0c003634e31610bdb/docs/v1/evaluation.md),
[agent](https://github.com/PrimeIntellect-ai/verifiers/blob/fb9d6d7f7bfc8dd6492c15a0c003634e31610bdb/docs/v1/agent.md),
and [taskset](https://github.com/PrimeIntellect-ai/verifiers/blob/fb9d6d7f7bfc8dd6492c15a0c003634e31610bdb/docs/v1/tasksets.md)
guides. CLI syntax can differ across versions; validate our shipped commands with
the installed dependency before adopting examples from current upstream docs.

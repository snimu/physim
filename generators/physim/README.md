# Physim recipes, registry, and reference validation

The reusable generation engine lives in the installed `blobkit` package. These
entry points define concrete recipes and import/export recorded data; evaluation
does not import this directory.

```sh
uv run blobkit generate generators/physim/recipes/small_search.py --registry outputs/small-search
uv run blobkit registry verify outputs/small-search
uv run python generators/physim/import_registry.py --output registry
uv run python generators/physim/export_registry_catalog.py --registry registry --sync-docs
```

`recipes/small_search.py` demonstrates custom Python metrics, mutation and
recombination, selection, and harvesting with short CPU simulations. Use
`--stop-after GENERATION` and `--resume CHECKPOINT_ID` for checkpointing, or
`--workers N` for local process scheduling. See the package's `GENERATION.md`
for callback contracts and recipe replay.

The historical importer preserves the packaged genomes and available source
evidence, and links the prepared reference world to its existing evaluation
identities. Missing historical recipes/checkpoints are marked partial. It can no
longer run from this checkout: it reads the p4g2_044 source record from
`environments/physim/physim/blobdata/`, removed in 0.12.1 (a copy is in
`probes/legacy/physim/physim/blobdata/`), and four untracked research files under
`probes/blobs/agentenv/round6/worked_example/p4g2_044/`. The committed `registry/`
already contains its output.

## Fresh phenomenology

`characterize.py` runs fresh CPU simulations using installed Blobkit and records
full activator/channel fields, organism-level measurements, and the current V3
descriptors from the research source. It pins source hashes and reports extension
criteria without interpreting a fixed observation window as convergence.

```sh
uv run python generators/physim/characterize.py --output outputs/phenomenology
uv run python generators/physim/probe_candidates.py outputs/phenomenology/bf_s11001
uv run python generators/physim/rotor_check.py --output outputs/rotor-check
uv run --package blobkit --extra plot python generators/physim/plot_characterization.py \
  outputs/phenomenology/bf_s11001 --output outputs/figures
```

The default `--worlds` list includes `p4g2_044`, whose genome `characterize.py` also
reads from the removed `blobdata/` path; pass `--worlds m4 xv bf mv3 ds6_000 m0` to run
the others.

The probe recipe uses current native source and sensor operations, three future
noise seeds, and paired interventions. The rotor recipe compares a prepared XV
pair with a cross-coupling control. These are scientific investigations, not
automatic evaluation certification. The registry only distinguishes `preserved`
and `eval-ready`; it contains no candidate priorities or future plans.

The [2026-09-13 investigation](../../handoff/evaluation_candidates/fresh/REPORT.md)
retains the executed sources, measured responses, full-field figures, and audit
receipts. `summarize_characterization.py` verifies this fixed experiment battery,
including exact source hashes against the report's `source/` archive:

```sh
uv run python generators/physim/summarize_characterization.py \
  outputs/phenomenology-20260913 --output handoff/evaluation_candidates/fresh
```

## Reference bundle migration

The [evaluation preparation workflow](EVALUATION_WORKFLOW.md) downloads explicit
inputs from a pinned HF registry and takes BF and XV
through fresh interventions, mechanism controls, frozen suites, independent
grading truth, native validation and bounded model pilots. Completed preparations
are preserved as new world records; `register_evaluation.py export` reconstructs
their runnable bundles from registry artifacts alone.

`export_reference_bundle.py` extracts the exact prepared fields and apparatus,
compiles the existing programs, and copies the verified native truth files.
`check_reference_parity.py` compares the packaged runtime with the preserved
source and short native continuations. Neither starts a world-search campaign or
calls a model.

These migration tools need historical research fixtures that are not in this
repository: the untracked `probes/blobs/agentenv/round6/worked_example/p4g2_044/` origin
and case scripts and the `probes/blobs/agentenv/cache/` state cache. Copies of the two
scripts are kept in `handoff/repo_cleanup/original_source/` and as artifacts of the
`historical-p4g2_044` registry recipe.
After export, installed experiments and grading need only the bundle and declared
packages. `_research.py` explicitly enables archived source imports for migration;
that path is never enabled by the installed taskset.

From the repository root after `uv sync`:

```sh
uv run python generators/physim/export_reference_bundle.py --output dist/reference-bundle
uv run python generators/physim/check_reference_parity.py --bundle dist/reference-bundle \
  --output handoff/residency_alignment/native_parity.json
```

The historical physics characterization remains under
`probes/blobs/agentenv/round6/physics/`; the original case and truth production scripts
are the preserved copies named above. They are provenance for this first export, not
runtime dependencies. The Prime contribution includes the portable BF/XV preparation and validation
recipes. Historical import and first-reference migration remain personal-repo
research tools; current evaluation uses the published bundles.

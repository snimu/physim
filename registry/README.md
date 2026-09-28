# World registry

This directory holds content-addressed genomes, recipes, generation runs,
candidate lineage, checkpoints, harvested worlds, and exact source/evidence
artifacts. `blobkit.registry.Registry` owns the storage format and verifies every
object and reference. `index.json` is a generated browsing projection.

To add a world, follow the [contribution guide](https://huggingface.co/datasets/seanpohorence/physim-worlds/blob/main/CONTRIBUTING.md).
It covers preserved worlds, eval-ready preparations, and reviewed HF pull requests
without granting contributors write access to the main dataset. Its editable
source in the code repository is `registry/CONTRIBUTING.md`.

The registry includes sourced worlds and validated evaluation preparations.
Historical evidence is marked partial where complete generation settings or
checkpoints are unavailable. Existing physical world/preparation/suite/bundle
identities are linked without changing them. New searches archive executable
recipes and their run records; the small example is a workflow demonstration.

```sh
uv run python generators/physim/import_registry.py --output registry
uv run blobkit generate generators/physim/recipes/small_search.py --registry registry
uv run blobkit registry verify registry
uv run python generators/physim/export_registry_catalog.py --registry registry
```

Reading or verifying the registry does not execute its source artifacts.
`blobkit registry export-recipe` materializes a recipe for inspection and explicit
execution. Runtime evaluation loads only the separate verified data bundle and
installed simulator. Python recipe code is Apache-2.0; world data are CC-BY-4.0,
with external attribution retained in source records. Release staging can include
this registry next to the evaluation bundles in the approved Hugging Face dataset.

## Availability

Each catalog row has one status:

- **preserved**: the world and available provenance are stored. Any world can
  be preserved, including simple controls, historical worlds and example harvests.
- **eval-ready**: an exact preparation, apparatus, suite, truth and validation
  evidence are linked and ready to run in the environment. This applies to the
  linked preparation/suite and is separate from publication or exposure.

`availability.json` explicitly lists the eval-ready world-record IDs, their
physical references and validation evidence. Every other record is preserved.
The exporter verifies those references and evidence before export or staging;
actual bundle loading still performs the environment's full validation.

BF, XV, and p4g2_044 have runnable evaluation preparations. The published
`catalog.jsonl` lists the current bundle paths, identities, and grading-program
counts; `worlds.jsonl` lists all preserved and eval-ready records. The original
source-world records and generation provenance remain preserved. Availability annotations
never change immutable genomes, recipes or world records. The registry contains
no review priorities or future plans. Run the exporter with `--sync-docs` to
refresh the documentation catalog as well.

Use `python generators/physim/register_evaluation.py export WORLD_RECORD_ID
--registry registry --output outputs/restored-bundle` to reconstruct a new
preparation's bundle from registry artifacts. See the
[preparation workflow](../generators/physim/EVALUATION_WORKFLOW.md) and
[scientific report](../handoff/eval_preparation/REPORT.md) for reproduction and scope.

The current registry and evaluation bundles are [published on Hugging Face](https://huggingface.co/datasets/seanpohorence/physim-worlds).
Superseded evaluation preparations are removed from the current dataset. Use the
dataset revision pinned in the environment's config for a reproducible run.

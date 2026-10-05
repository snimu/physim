# World bundle v1

## Generation registry

`registry-record-v1.schema.json` describes the outer generation-registry record.
`blobkit.registry.Registry` verifies content hashes and reference existence;
`blobkit.generation` enforces the recipe/candidate/checkpoint contracts it writes.
IDs hash canonical JSON without `id`. Binary artifacts hash their exact bytes.

Genomes, recipes, generation runs, candidates, checkpoints, completed/paused
results, and harvested world records have distinct ID prefixes. Recipe sources
are archived artifacts and are never executed by a registry read or verification.
Each candidate links its recipe, run, genome, parent candidates, evaluation seed,
measurements, score, and variation metadata. Checkpoints commit a generation and
its selected population; results link that checkpoint and harvested worlds.

`world-record` is a provenance/catalog identity. It can link an existing Physim
physical `world`, preparation, suite, or bundle ID; it does not replace them.
Sourced historical records explicitly describe missing recipes or run evidence.

## Evaluation bundles

The authoritative validator is `physim.bundles`. The JSON schema describes the
outer document; the loader also checks content identities, cross-file references,
profile membership, physical parameters, suite plans, and bounded array headers.

A bundle directory contains `manifest.json` plus only named payload files.
Required inputs are `world.json`, `preparation.npz`, `apparatus.json`, `suite.json`,
and the suite's `truth/*.npz`. Exported bundles also carry `checks.json`, which
`physim demo` and the validation scripts read. The simulation profile excludes suite
and truth payloads. Files are SHA-256 checked before parsing.

Identities use SHA-256 of canonical UTF-8 JSON: sorted keys, no insignificant
whitespace, unescaped Unicode, finite numbers. Each object is hashed without its
`id` property. The bundle hashes the world/preparation/suite ID mapping. Run
reports similarly hash their complete report before adding `id`.

World identity binds the genome, CPU numerical profile, exact simulation sources,
and reference numerical dependency versions. Preparation binds the world, exact
field bytes, apparatus file, time rebasing, and fresh-noise policy. Suite binds
preparation, programs/selectors/scales, scoring source, and every retained truth.
License/publication metadata is outside the physical content IDs; every result
also records the complete manifest SHA-256.

A run's `grade.json` includes these references, package versions/source hashes,
forecast manifest hash, predictor identity, validity, and scores. Model-run host
state separately retains observation hashes, harness settings, costs, and budgets.
Do not overwrite or merge retry records.

The loader rejects traversal, symlinks, mismatched IDs, duplicate JSON keys,
nonfinite values, object arrays, mismatched truth requests, and oversized input.
It checks ZIP expansion size and NPY headers before NumPy allocations. V1 uses
the fixed CPU grid and 13/19-slot apparatus, with the public port count derived
from the genome. It admits 1–16 activators and 1–48 channels, at most 64 fields in
total. Zero diffusion is supported for stationary memory fields; negative
diffusion is rejected. Coupling matrices, bilinear indices, port permutations,
prepared arrays, observations and predictions must agree on these dimensions.
Shape validation alone does not certify scientific or evaluation suitability.

Native reproduction pins NumPy 2.5.2 and SciPy 1.18.0 and checks source hashes.
Bitwise parity has been checked on the local CPU platform. Other architectures
must run the reference check; cross-platform bitwise identity is not claimed.

HF resolution requires a full 40-character repository commit. Downloaded files
are byte-capped as they stream, checked against the manifest, and promoted to the
cache only when the selected profile verifies. `--offline` never makes a network
request and rechecks cached hashes. The adapter currently supports public dataset
repositories; direct local bundle loading also works without the hub dependency.

The URL/HTTP handling follows the [Hugging Face download API](https://huggingface.co/docs/huggingface_hub/guides/download).

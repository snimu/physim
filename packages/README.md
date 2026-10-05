# Reusable packages

`blobkit/` is the simulator library used by Physim and by world-generation research.
It is an independent distribution, not a Verifiers taskset. The residency repository
does not currently define a shared-library directory; `packages/` is a local
workspace extension, not a claimed Prime convention.

For a residency PR, keep blobkit as an explicit versioned dependency, following
the existing `pmpp-hard` → `kernelguard` dependency pattern. Blobkit 0.3.5 is
published as a checksummed GitHub release; the environment pins its wheel URL and
SHA-256, and the uv workspace resolves it from `packages/blobkit/` during development.
Do not put the simulator only in `generators/`: the trusted runtime needs it during
experiments.

The original `probes/blobs/blobkit/` tree is historical source/evidence. The active
workspace member is `packages/blobkit/`; only it should be edited for new package
work. CPU reference hashes bind the actual numerical implementation.

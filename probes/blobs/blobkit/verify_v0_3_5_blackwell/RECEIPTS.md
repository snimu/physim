# Blackwell (sm_103) JAX validation receipts — gpu extra floor change

The `accelerator`/`gpu` extras pinned `jax==0.4.38`, which cannot run on
Blackwell (sm_100/sm_103 need CUDA >= 12.8; 0.4.38 wheels are CUDA-12.6-era).
This change keeps 0.4.38 as the floor and validates a modern JAX on B300.

Environment: NVIDIA B300 SXM6 PC x8, driver 580.173.02, Ubuntu 24.04,
Python 3.12.3, blobkit 0.3.5.

## Run 1 — released blobkit 0.3.5 wheel, JAX 0.11.2 + CUDA-13 wheels

    uv pip install blobkit-0.3.5-py3-none-any.whl 'jax[cuda13]' pytest
    pytest tests --require-gpu -q

    84 passed, 2 skipped, 3 warnings in 920.12s

Covers: f64 CPU-vs-accelerator trajectory parity (7 GT worlds, rel-L2 < 1e-9),
noisy chunking bitwise identity, padding/noise lane independence, batched
initial-field ownership, full-grid seven-world batch vs CPU (f64, < 1e-5),
assay repack+ballast canonical equality, devrec/asyncapply record parity,
CPU suite, registry, generation resume/lineage, packaging, integrity.

## Run 2 — this branch (built wheel), JAX 0.11.2 + CUDA-12 wheels

    uv build -o dist            # wheel built from this branch
    pip install dist/blobkit-0.3.5-py3-none-any.whl 'jax[cuda12]' pytest
    pytest tests --require-gpu -q

    84 passed, 2 skipped, 3 warnings in 1077.57s

Pitfall for reproducing: a `pip install -e` of the source tree leaves a
`blobkit.egg-info/` inside `packages/blobkit/` that shadows the installed
distribution (sys-path order) and fails
`test_fleet_bundle_preserves_install_metadata_and_data` with a missing
LICENSE; remove it or install from the wheel.

## Parity notes

The accelerator noise stream is JAX threefry (CPU uses NumPy PCG64), so noisy
parity is descriptor-level by design (GATES.md precedent); the noise=0 f64
trajectory gate and the bond/anchoring battery are the exact checks that
matter for an XLA/driver bump. Nothing in the locked numerics changed.

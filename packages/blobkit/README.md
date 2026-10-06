# blobkit 0.3.5

Spatial-field simulators, world genomes, measurement batteries, and adaptive
experiment assays. Blobkit installs independently of Physim and the research tree.
The CPU runtime needs NumPy and SciPy; accelerator support is optional.

## Install

From the Physim repository root:

```sh
uv pip install ./packages/blobkit
```

Or install a built distribution in any Python environment:

```sh
uv pip install /path/to/blobkit-0.3.5-py3-none-any.whl
```

Python 3.10–3.13 is supported by the package metadata. Python 3.12 is the reference
validation environment. NumPy 2.5.2 and SciPy 1.18.0 reproduce the prepared Physim
reference; use those exact versions when comparing its native results. Version
0.3.5 is available as a [public release wheel and source archive](https://github.com/swpo/physim/releases/tag/blobkit-v0.3.5);
these commands do not require a PyPI release.

For JAX on CPU or another supported platform:

```sh
uv pip install './packages/blobkit[accelerator]'
```

For NVIDIA CUDA 12 on Linux x86-64:

```sh
uv pip install './packages/blobkit[gpu]'
blobkit --gpu
```

Both accelerator extras require JAX 0.4.38 or newer. 0.4.38 is the version
these kernels were developed and gated against; the full parity suite also
passes on JAX 0.11.2 (CUDA-12 and CUDA-13 wheels) on Blackwell B300 — receipts
in `probes/blobs/blobkit/verify_v0_3_5_blackwell/RECEIPTS.md`. Blackwell GPUs
need a CUDA >= 12.8 wheel build. The
CUDA extra installs the CUDA libraries through Python wheels; the host still
needs a compatible NVIDIA driver. `blobkit --gpu` exits unsuccessfully if JAX
cannot see a real GPU. `blobkit --accelerator` also allows JAX CPU devices.
Install `blobkit[plot]` (or `./packages/blobkit[plot]` from this checkout) for the
optional `hier_metrics.save_strip` PNG helper; plotting is not a CPU runtime dependency.

## Load and simulate a world

```python
from blobkit import worlds
from blobkit.soup import get_backend

genome = worlds.load("m4")
backend = get_backend("cpu")  # "gpu" uses the JAX implementation
state = backend.init_soup(genome, L=64, seed=1, workers=1)
backend.advance(state, 25.0)
record = backend.snapshot_rec(state)
backend.save_run(record, "m4-short.npz")
```

`worlds.names()` lists 15 packaged genomes. Each `load()` returns an independent
mutable copy. `worlds.kicks_for(genome)` returns any documented initialization
kicks. Calls do not read the historical checkout. Native soup snapshots use the
25-unit coarse recording grid; requested advance times must respect that grid.

## Run assays

```python
from blobkit.assay_v2b import run_assay_b
from blobkit.soup import get_backend
from blobkit.worlds import load

result = run_assay_b(load("m0"), seed=7, backend=get_backend("cpu"),
                     results_path=None, verbose=False)
print(result["interest"], result["horizon"])
```

The full assay starts at 2,500 time units and may extend to 20,000. It is much
more expensive than the short simulation above. The fixed CPU `m0`, seed 7
reference produces interest 2.8 at 2,500.

For population experiments, `blobkit.assay_batch.run_assay_batch` advances lanes
on one padded JAX tensor. It accepts `(genome, seed)` pairs or dictionaries with
`genome`, `seed`, optional `t0`/`cap`, and optional `ic` initial fields. Horizons
must be finite, positive, on the shared doubling ladder, and on the recording
grid. Assay horizons must extend beyond the metric's 500-unit burn-in; use the
low-level simulator for shorter runs. Each `ic` must match its lane's shape and contain finite real values.

Use a `if __name__ == "__main__":` guard around scripts that call the batched
assay: its battery workers use multiprocessing spawn. An empty batch returns an
empty list. `battery_procs=0` runs those measurements inline. Group worlds by
`nf_bucket(genome)` when padding efficiency matters.

CPU and JAX use different noise generators. Noisy trajectories need not match
across backends. The tests compare noise-free f64 trajectories across backends,
noisy chunked runs on the same backend, and padded lanes with explicit numerical
tolerances. Short trajectory agreement does not imply identical long chaotic runs.
The optional device recording modules retain their `*_proto` names; their tests
cover equivalence to host recording, not a general performance guarantee.

## Portable fleet bundles

```sh
uv run --package blobkit python -m blobkit.deploy_tools /tmp/my-blobkit-fleet --backend gpu_batch
```

From a standalone installation, use `python -m blobkit.deploy_tools` instead.
The bundle includes a wheel (when a builder is available), an installable source
fallback, the Apache license, all genomes, configs, and worker scripts. Metadata
comes from the installed distribution, including accelerator extras. Its README
selects `pod_run_batch.sh` for batched execution. This command creates files;
it does not provision compute or launch a fleet.

## Integrity and tests

The generation API and registry workflow are documented in [GENERATION.md](GENERATION.md).
To share a world and its provenance, follow the
[registry contribution guide](https://huggingface.co/datasets/seanpohorence/physim-worlds/blob/main/CONTRIBUTING.md).
Start a small search from the repository with:

```sh
uv run blobkit generate generators/physim/recipes/small_search.py --registry outputs/small-search
uv run blobkit registry verify outputs/small-search
```

Recipes supply Python functions for evaluation, fitness, variation, selection,
and harvesting. The package runs the search and records code, seeds, metrics,
parents, and resumable checkpoints alongside harvested worlds. The environment
continues to use the simulation API without importing generation code.

```sh
blobkit
uv run --package blobkit --extra test pytest packages/blobkit/tests -m 'not accelerator and not slow'
uv run --package blobkit --extra accelerator --extra test pytest packages/blobkit/tests -m 'not slow'
# On an NVIDIA host, include the longer CUDA checks:
uv run --package blobkit --extra gpu --extra test pytest packages/blobkit/tests --require-gpu
```

Tests also run against installed wheels: copy `tests/` outside the checkout,
install the wheel and test extra, then run `python -m pytest tests`. CPU-only
installs skip accelerator checks; `--require-gpu` makes a missing GPU a failure.

`blobkit.verify_locks(strict=True)` checks installed file integrity against the
0.3.5 release table. This is an integrity check, not a numerical certification.
The historical 0.3.4 table remains in the package and can be inspected with
`verify_locks(reference="0.3.4", quiet=True)`. Differences from that older release
remain visible. The genome, CPU kernels, and reference measurement code retain
their original bytes. Detailed receipts are in `handoff/blobkit_polish/` in the
Physim repository; the original research evidence remains under `probes/`.

`BLOBKIT_DATA` overrides world JSONs by name, with fallback to packaged data.
`BLOBKIT_RESULTS` selects the assay CLI's default results path.
`BLOBKIT_SKIP_LOCK=1` disables the import-time integrity check; explicit verification
still runs. Code is Apache-2.0; see [LICENSE](LICENSE).

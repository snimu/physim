"""Fresh full-field phenomenology runs with the installed CPU simulator.

This research recipe uses the repository's current V3 descriptors on top of the
installed Blobkit metrics. It preserves data and source hashes; it does not
declare evaluation readiness or change the locked numerical/metric modules.
"""

import argparse
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(variable, "1")

import numpy as np
from blobkit import genome, metrics_v1, metrics_v2, worlds
from blobkit.assay_v2 import horizon_criteria, js
from blobkit.soup import sim_cpu

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "probes/blobs/l0/complexity/metrics_v3.py"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(js(value), indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


@contextlib.contextmanager
def current_v3():
    """Bind V3's historical import names to the installed shared implementation."""
    aliases = {"genome": genome, "metrics_v1": metrics_v1, "metrics_v2": metrics_v2}
    before = {name: sys.modules.get(name) for name in aliases}
    search_path = sys.path[:]
    try:
        sys.modules.update(aliases)
        spec = importlib.util.spec_from_file_location("physim_current_v3", V3)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path[:] = search_path
        for name, value in before.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def load_genome(name):
    if name == "p4g2_044":
        source = ROOT / "probes/legacy/physim/physim/blobdata/p4g2_044.json"
        return json.loads(source.read_text())["genome"]
    return worlds.load(name)


def characterize(name, seed, horizon, output):
    started = time.monotonic()
    destination = Path(output) / f"{name}_s{seed}"
    destination.mkdir(parents=True, exist_ok=False)
    g = load_genome(name)
    state = sim_cpu.init_soup(g, L=128.0, seed=seed, dtype="f32", workers=1, kicks=worlds.kicks_for(g))
    write_json(destination / "genome.json", g)
    write_json(
        destination / "protocol.json",
        dict(
            world=name,
            seed=seed,
            horizon_tu=horizon,
            L=128.0,
            dx=0.5,
            dt=0.02,
            noise=0.002,
            dtype="f32",
            backend="installed-blobkit-cpu",
            n_soup=12,
            initialization="Installed init_soup default dressed pokes, including its per-act default 0.5px kicks.",
            explicit_kick_overrides=worlds.kicks_for(g),
            snapshot_cadence_tu=250,
            horizon_policy="Fixed observation window; extension criteria recorded, no convergence assumed.",
            versions={p: importlib.metadata.version(p) for p in ("blobkit", "numpy", "scipy")},
            sources={
                str(p.relative_to(ROOT)): digest(p)
                for p in (
                    Path(__file__),
                    V3,
                    Path(sim_cpu.__file__),
                    Path(genome.__file__),
                    Path(metrics_v1.__file__),
                    Path(metrics_v2.__file__),
                )
            },
        ),
    )
    fields = [state["F"].copy()]
    times = [0.0]
    for target in np.arange(250.0, horizon + 0.1, 250.0):
        status = sim_cpu.advance(state, float(target))
        fields.append(state["F"].copy())
        times.append(state["t_step"] * state["dt"])
        if target % 500 == 0 or status != "ok":
            print(f"{name} s{seed}: T={times[-1]:g}, {status}, {time.monotonic() - started:.0f}s", flush=True)
        if status != "ok":
            break
    np.savez_compressed(destination / "fields.npz", t=np.array(times), F=np.stack(fields))
    np.savez_compressed(destination / "final_state.npz", F=state["F"])
    rec = sim_cpu.snapshot_rec(state)
    # JSON keeps the full measurement record inspectable without pickle loading.
    write_json(destination / "record.json", rec)
    if state["status"] != "ok":
        write_json(destination / "failure.json", dict(status=state["status"], T=times[-1]))
        return dict(world=name, seed=seed, status=state["status"])
    analysis = dict(rec)
    v2 = metrics_v2.full_battery(analysis, genome=g)
    with current_v3() as v3:
        late = [(t, f) for t, f in zip(times, fields) if t >= max(500, horizon - 1500)]
        masks = [
            ~v3.support_mask(f[: state["na"]], state["thr_a"], carpet_frac=v3.VOID_CARPET_FRAC)[0] for _, f in late
        ]
        result = v3.full_battery_v3(
            analysis,
            genome=g,
            fsnaps=dict(t=[t for t, _ in late], F=[f for _, f in late]),
            v2_out=v2,
            void_masks=masks,
            void_mask_ts=[t for t, _ in late],
        )
        summary = v3.lean_summary_v3(result)
        summary["v3_weight"] = v3.W9
    result["horizon_diagnostics"] = horizon_criteria(rec, g, D=v2["D"])
    write_json(destination / "metrics.json", result)
    # Occupancy includes EVERY activator, including dense carpets excluded from blob lists.
    occupancy = np.asarray([[(f[i] > state["thr_a"][i]).mean() for i in range(state["na"])] for f in fields])
    write_json(
        destination / "field_summary.json",
        dict(
            t=times,
            activator_occupancy=occupancy,
            field_std=np.std(np.stack(fields), axis=(-1, -2)),
            field_mean=np.mean(np.stack(fields), axis=(-1, -2)),
        ),
    )
    result_row = dict(
        world=name,
        seed=seed,
        status="ok",
        T=times[-1],
        wall_seconds=round(time.monotonic() - started, 2),
        summary=summary,
        horizon_diagnostics=result["horizon_diagnostics"],
        final_activator_occupancy=occupancy[-1],
        full_field_sha256=digest(destination / "fields.npz"),
    )
    write_json(destination / "summary.json", result_row)
    print(f"DONE {name} s{seed}: C9={summary['d9']['C9']}, {summary['d9']['cls']}", flush=True)
    return js(result_row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", nargs="+", default=["m4", "xv", "bf", "mv3", "ds6_000", "m0", "p4g2_044"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[11001, 11002])
    parser.add_argument("--horizon", type=float, default=2500)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.horizon <= 500 or args.horizon % 250 or args.workers < 1:
        parser.error("horizon must exceed burn-in and be a multiple of 250; workers must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    rows, errors = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = {
            pool.submit(characterize, name, seed, args.horizon, args.output): (name, seed)
            for name in args.worlds
            for seed in args.seeds
        }
        for future in as_completed(jobs):
            name, seed = jobs[future]
            try:
                rows.append(future.result())
            except Exception as error:
                errors.append(dict(world=name, seed=seed, error=repr(error)))
                print(f"FAILED {name} s{seed}: {error!r}", flush=True)
            write_json(args.output / "progress.json", dict(completed=rows, errors=errors, total=len(jobs)))
    if errors:
        raise SystemExit(f"{len(errors)} jobs failed; see progress.json")


if __name__ == "__main__":
    main()

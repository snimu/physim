"""Calibrate the reward target with independent native forecasts, without inference.

Run with the locked Physim environment. Per-case ensembles are resumable and
validated against bundle identity; the existing grading truths are never changed.
"""

import argparse
import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
from physim.blobround6_eval import score_case
from physim.bundles import Bundle

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(job):
    world, case_index, members, seed, output, source = job
    bundle = Bundle(source / world / "bundle")
    record = bundle.suite["cases"][case_index]
    request = record["request"]
    directory = output / world
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (request["id"] + ".npz")
    identity = dict(bundle=bundle.references(), members=members, seed=seed, case=request["id"])
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            if json.loads(str(saved["identity"])) != identity:
                raise ValueError(f"Calibration cache identity mismatch: {path}")
            prediction = {"samples": [saved[f"query{i}"] for i in range(len(request["queries"]))]}
    else:
        prediction = bundle.make_oracle().sample_truth(
            request["actions"], request["queries"], n_samples=members, truth_seed=seed
        )
        temporary = path.with_suffix(".pending.npz")
        np.savez_compressed(
            temporary,
            identity=json.dumps(identity, sort_keys=True),
            **{f"query{i}": value for i, value in enumerate(prediction["samples"])},
        )
        temporary.replace(path)
    truth = bundle.truth(record)
    scores = {}
    # Prefixes show the finite-ensemble effect without additional simulations.
    for count in sorted({4, 16, members}):
        if count > members:
            continue
        result = score_case(
            request,
            {"samples": [a[:count] for a in prediction["samples"]]},
            truth,
            groups=record["groups"],
            n_samples=count,
            n_truth=bundle.suite["truth_members"],
            roster=bundle.roster,
            limits=bundle.limits,
        )
        scores[str(count)] = result["joint_energy_equal_group_mean"]
    return dict(world=world, **identity, scores=scores, forecast_sha256=digest(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "outputs/eval-preparation-20260916")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/reward-calibration-20260926")
    parser.add_argument("--members", type=int, default=64)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.members < 4:
        parser.error("at least four members are required")
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = []
    for wi, world in enumerate(("bf", "xv", "p4g2_044")):
        bundle = Bundle(args.source / world / "bundle")
        for ci in range(len(bundle.suite["cases"])):
            jobs.append((world, ci, args.members, 926_000_000 + wi * 10000 + ci, args.output, args.source))
    completed = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case, job) for job in jobs]
        for future in as_completed(futures):
            record = future.result()
            completed.append(record)
            (args.output / "progress.json").write_text(json.dumps(completed, indent=2) + "\n")
            print(
                f"{len(completed)}/{len(jobs)} {record['world']} {record['case']} "
                f"S={record['scores'][str(args.members)]:.8g}",
                flush=True,
            )
    worlds = {}
    for world in ("bf", "xv", "p4g2_044"):
        records = sorted((r for r in completed if r["world"] == world), key=lambda r: r["case"])
        worlds[world] = dict(
            cases=records,
            mean_energy={
                str(n): float(np.mean([r["scores"][str(n)] for r in records]))
                for n in sorted({4, 16, args.members})
                if n <= args.members
            },
        )
    worst = max(w["mean_energy"][str(args.members)] for w in worlds.values())
    # Integer precision targets with >=2x headroom above native score. This is
    # an operational margin, not a confidence bound on all starting states.
    target = math.floor(-math.log10(2 * worst))
    if target < 1:
        raise ValueError("No positive integer K satisfies the native-score margin")
    report = dict(
        schema="physim-reward-calibration-v1",
        members=args.members,
        truth_members=2,
        selection="All cases in all three frozen evaluation suites",
        rule="Largest integer K with 10**(-K) >= 2 * maximum native suite energy",
        recommended_k=target,
        worst_native_energy=worst,
        worlds=worlds,
        limitations="One fresh forecast ensemble against each saved pair of truths; "
        "calibration applies to these preparations, scales and finite-ensemble scorer.",
    )
    (args.output / "calibration.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {"recommended_k": target, "mean_energy": {k: v["mean_energy"] for k, v in worlds.items()}}, indent=2
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

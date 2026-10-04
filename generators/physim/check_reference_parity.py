"""Migration regression: compare extracted runtime to preserved research inputs."""

import argparse
import ast
import importlib.util
import json
from importlib.resources import files
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
from _research import activate_research

activate_research()
from physim.bundles import Bundle, digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    backup = ROOT / "handoff/repo_cleanup/original_source"
    old_path = backup / "probes/blobs/agentenv/device.py"
    old, new = ast.parse(old_path.read_text()), ast.parse(files("physim").joinpath("devices.py").read_text())
    checks = []

    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
        if not passed:
            raise AssertionError(name)

    for name in ("lattice_offsets", "rot2", "ProbeDevice", "bilinear", "step_chunk"):
        a = next(n for n in old.body if getattr(n, "name", None) == name)
        b = next(n for n in new.body if getattr(n, "name", None) == name)
        check(name + " operations unchanged", ast.dump(a) == ast.dump(b))
    baseline = json.loads((ROOT / "handoff/repo_cleanup/source_baseline.json").read_text())["source_sha256"]
    for rel in (
        "environments/physim/physim/blobround6.py",
        "environments/physim/physim/blobround6_eval.py",
        "environments/physim/physim/blobround6_explore.py",
        "probes/blobs/blobkit/blobkit/soup/sim_cpu.py",
        "probes/blobs/blobkit/blobkit/genome.py",
    ):
        target = (
            rel.replace("physim/physim/blobround6", "physim/physim/legacy_v1/blobround6")
            if rel.endswith(("blobround6.py", "blobround6_eval.py"))
            else rel
        )
        source = (
            files("physim").joinpath(target.removeprefix("environments/physim/physim/"))
            if target.startswith("environments/physim/physim/")
            else ROOT / target
        )
        check(rel + " bytes unchanged", digest(source) == baseline[rel])
    for name in ("soup/sim_cpu.py", "soup/sim_v1.py", "genome.py"):
        check(
            "installed blobkit/" + name + " bytes unchanged",
            digest(ROOT / "packages/blobkit/blobkit" / name) == digest(ROOT / "probes/blobs/blobkit/blobkit" / name),
        )
    path = ROOT / "probes/blobs/agentenv/round6/worked_example/p4g2_044/origin.py"
    spec = importlib.util.spec_from_file_location("old_origin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from physim.legacy_v1 import blobround6

    module.R6 = blobround6
    original, meta = module.make_origin()
    bundle = Bundle(args.bundle)
    extracted = bundle.make_oracle()
    for i, actions in enumerate(
        (
            [],
            [dict(t=0, kind="inject", port=2, amp=0.7, dur=0.04)],
            [dict(t=0, kind="adjust", device=0, u=[0.1, -0.2, 0.3])],
        )
    ):
        queries = [dict(sensor=s, t=[0, 0.02, 0.06]) for s in ("device0", "device1", "global")]
        a = original.sample_truth(actions, queries, n_samples=2, truth_seed=173)["samples"]
        b = extracted.sample_truth(actions, queries, n_samples=2, truth_seed=173)["samples"]
        check(f"native action variant {i} bitwise parity", all(np.array_equal(x, y) for x, y in zip(a, b)))
    report = dict(ok=all(c["passed"] for c in checks), checks=checks, references=bundle.references())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

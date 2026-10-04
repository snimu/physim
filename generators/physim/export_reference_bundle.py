"""One-time migration from preserved research fixtures into an immutable bundle.

Only this exporter needs the research checkout. Installed loaders never import it.
No new truths, model calls, or ongoing native simulation are generated here.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
import tomllib
from importlib.resources import files as package_files
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORKED = ROOT / "probes/blobs/agentenv/round6/worked_example"
from _research import activate_research

activate_research()
from physim.bundles import FORMAT, NUMERICS, Bundle, digest, identified, implementation_identity


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def export(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("export target already exists; use a fresh directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".export-", dir=output.parent))
    try:
        _export(temporary / "bundle")
        (temporary / "bundle").rename(output)
    finally:
        shutil.rmtree(temporary)
    print(f"Verified bundle: {output}")


def _export(output):
    origin_module = load_source("reference_origin_export", WORKED / "p4g2_044/origin.py")
    compiler = load_source("reference_case_export", WORKED / "p4g2_044/cases/build_cases.py")
    from physim.legacy_v1 import blobround6

    origin_module.R6 = blobround6
    oracle, origin = origin_module.make_origin()
    old_suite = compiler.build_suite("compact")
    output.mkdir(parents=True)
    (output / "truth").mkdir()
    write_json(output / "world.json", oracle._template["g"])
    np.savez_compressed(output / "preparation.npz", fields=oracle._template["F"])
    devices = []
    for d in oracle._devices:
        parameters = dict(
            dev_id=d.dev_id,
            lattice=d.lattice,
            n_rings=d.n_rings,
            base_ds=d.base_ds,
            center=d.center.tolist(),
            L=d.L,
            secret_rot=d.secret_rot,
            reflect=d.reflect,
            motion_theta=0.0,
            motion_reflect=False,
            node_perm=d.node_perm.tolist(),
            dil_bounds=list(d.dil_bounds),
        )
        devices.append(dict(parameters=parameters, dilation=d.dilation, motion_basis=d.Bm.tolist()))
    apparatus = dict(
        devices=devices,
        device_slots=[d.k for d in oracle._devices],
        port_permutation=oracle._perm.tolist(),
        adjustment_matrix=oracle._mix.tolist(),
        emitter_yx=oracle._emitter.tolist(),
    )
    write_json(output / "apparatus.json", apparatus)
    truth_sources = {}
    for dirname in ("native_validation", "native_supplemental"):
        directory = WORKED / "p4g2_044" / dirname
        manifest = json.loads((directory / "manifest.json").read_text())
        assert manifest["status"] == "COMPLETE"
        for record in manifest["completed"]:
            source = directory / record["file"]
            assert digest(source) == record["sha256"]
            truth_sources[record["case_id"]] = (source, record["sha256"])
    cases = []
    for case in old_suite["public_cases"]:
        cid = case["id"]
        source, _ = truth_sources[cid]
        shutil.copyfile(source, output / "truth" / (cid + ".npz"))
        cases.append(
            dict(
                request=case,
                groups=old_suite["private"]["score_groups"][cid],
                family=old_suite["private"]["entries"][cid]["family"],
                truth=f"truth/{cid}.npz",
            )
        )
    suite = dict(
        schema_version="physim-suite-v1",
        scoring_version="r6-offline-score-v1",
        contract_version="r6-absolute-time-12-port-v1",
        forecast_members=64,
        truth_members=2,
        predictor_seed=20260908,
        aggregation="equal-case-mean",
        cases=cases,
        known_limits=[
            "One prepared reference world.",
            "Two independent truth realizations per case.",
            "Primary groups in c006 and c007 miss some fine switch/recovery timing.",
        ],
    )
    write_json(output / "suite.json", suite)
    controls = json.loads((WORKED / "p4g2_044/predictor_sanity/results.json").read_text())
    write_json(
        output / "checks.json",
        dict(
            schema_version="physim-reference-checks-v1",
            source_origin=origin,
            retained_truth_sha256={c["request"]["id"]: truth_sources[c["request"]["id"]][1] for c in cases},
            reference=dict(
                predictor="initial_persistence",
                forecast_members=4,
                primary_joint_energy=controls["aggregate"]["initial_persistence"]["joint_energy"],
                absolute_tolerance=1e-10,
            ),
            source_code_sha256={
                str(p.relative_to(ROOT)): digest(p)
                for p in [WORKED / "p4g2_044/origin.py", WORKED / "p4g2_044/cases/build_cases.py"]
            },
        ),
    )
    objects = {}
    objects["world"] = identified(
        "world",
        dict(
            name="p4g2_044",
            genome_sha256=digest(output / "world.json"),
            numerics=NUMERICS,
            implementation=implementation_identity("fixed-source-v1"),
        ),
    )
    objects["preparation"] = identified(
        "preparation",
        dict(
            world_id=objects["world"]["id"],
            field_sha256=origin["initial_field_sha256"],
            file_sha256=digest(output / "preparation.npz"),
            apparatus_sha256=digest(output / "apparatus.json"),
            noise_policy=origin["noise_policy"],
            noise_coefficient=origin["native_noise_coefficient"],
            original_time=1700.0,
            public_time=0.0,
        ),
    )
    objects["suite"] = identified(
        "suite",
        dict(
            preparation_id=objects["preparation"]["id"],
            file_sha256=digest(output / "suite.json"),
            scoring_source_sha256=digest(package_files("physim").joinpath("legacy_v1/blobround6_eval.py")),
            truth_sha256={c["truth"]: digest(output / c["truth"]) for c in cases},
        ),
    )
    files = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        name = path.relative_to(output).as_posix()
        role = "truth" if name.startswith("truth/") else path.stem
        profiles = (
            ["simulation", "evaluation"]
            if name in ("world.json", "preparation.npz", "apparatus.json", "checks.json")
            else ["evaluation"]
        )
        files.append(dict(path=name, bytes=path.stat().st_size, sha256=digest(path), role=role, profiles=profiles))
    bundle_id = identified("bundle", {kind: obj["id"] for kind, obj in objects.items()})["id"]
    release = tomllib.loads((ROOT / "configs/physim/release.toml").read_text())
    manifest = dict(
        schema_version=FORMAT,
        bundle_id=bundle_id,
        status="local-reference-verified",
        licenses=dict(code=release["code_license"], data=release["data_license"]),
        objects=objects,
        files=files,
    )
    write_json(output / "manifest.json", manifest)
    bundle = Bundle(output)
    for record in bundle.suite["cases"]:
        bundle.truth(record)
    print(
        json.dumps(
            dict(
                directory=str(output),
                bundle_id=bundle_id,
                files=len(files),
                bytes=sum(f["bytes"] for f in files),
                initial_field_sha256=origin["initial_field_sha256"],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    export(parser.parse_args().output)

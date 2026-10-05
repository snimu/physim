"""A release must preserve the registry and include every declared evaluation."""

import importlib.util
import json
import tomllib
from pathlib import Path

import pytest
from blobkit import worlds
from blobkit.registry import Registry
from physim.bundles import Bundle, digest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("world_release", ROOT / "scripts/physim/prepare_world_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
CONFIG = tomllib.loads((ROOT / "configs/physim/release.toml").read_text())


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    root = tmp_path_factory.mktemp("world-release")
    registry = Registry(ROOT / "registry")
    index = json.loads((registry.root / "index.json").read_text())
    p4 = next(w["id"] for w in index["worlds"] if w["name"] == "p4g2_044_centered_v2")
    # Supplying p4 separately exercises --bundle; BF and XV are reconstructed from registry artifacts.
    supplied = release.export_bundle(registry, p4, root / "p4-bundle")
    output = root / "snapshot"
    report = release.stage_release(
        registry_root=ROOT / "registry",
        bundle_paths=[supplied.root],
        output=output,
        release=CONFIG,
    )
    return output, report


def test_release_contains_all_worlds_and_all_evaluations_with_original_identities(staged):
    output, report = staged
    assert Registry(output / "registry").verify() == Registry(ROOT / "registry").verify()
    assert report["availability"]["counts"] == {"eval-ready": 3, "preserved": 21}
    worlds = [json.loads(line) for line in (output / "worlds.jsonl").read_text().splitlines()]
    assert len(worlds) == 24
    assert len({row["genome"] for row in worlds}) == 19
    assert all((row["bundle_path"] is not None) == (row["status"] == "eval-ready") for row in worlds)
    for row in worlds:
        assert (output / row["record_path"]).is_file()
        assert (output / row["genome_path"]).is_file()
    entries = [json.loads(line) for line in (output / "catalog.jsonl").read_text().splitlines()]
    assert {e["world_name"]: (e["public_ports"], e["case_count"]) for e in entries} == {
        "p4g2_044_centered_v2": (12, 19),
        "bf_trail_lab_centered_v2": (4, 15),
        "xv_rotor_lab_centered_v2": (6, 15),
    }
    for entry in entries:
        assert Bundle(output / entry["bundle_path"]).references() == entry["references"]
    for row in report["files"]:
        assert digest(output / row["path"]) == row["sha256"]
    for kind in ("genome", "recipe", "generation-run", "world-record", "candidate", "checkpoint", "artifact"):
        for source in (ROOT / "registry" / kind).glob("*"):
            assert (output / "registry" / kind / source.name).read_bytes() == source.read_bytes()


def test_release_refuses_to_omit_an_eval_ready_bundle(tmp_path):
    registry = Registry(tmp_path / "registry")
    refs = {kind: f"{kind}:sha256:" + "a" * 64 for kind in ("world", "preparation", "suite", "bundle")}
    identifier = registry.add_source_world("unbundled", worlds.load("m0"), source={"kind": "fixture"}, links=refs)
    evidence = registry.artifact(b"Validation evidence for a preparation whose bundle files were not archived.")
    availability = {
        "schema_version": "physim-registry-availability-v1",
        "eval_ready": {identifier: {"references": refs, "evidence": [evidence]}},
    }
    (registry.root / "availability.json").write_text(json.dumps(availability))
    with pytest.raises(ValueError, match="does not preserve a complete evaluation bundle"):
        release.stage_release(registry_root=registry.root, bundle_paths=[], output=tmp_path / "bad", release=CONFIG)

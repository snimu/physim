"""Only preserved / eval-ready are registry statuses; readiness needs evidence."""

import importlib.util
import json
from pathlib import Path

import pytest
from blobkit import worlds
from blobkit.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_export", ROOT / "generators/physim/export_registry_catalog.py")
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


@pytest.fixture
def available(tmp_path):
    registry = Registry(tmp_path / "registry")
    refs = {kind: f"{kind}:sha256:" + "a" * 64 for kind in ("world", "preparation", "suite", "bundle")}
    identifier = registry.add_source_world(
        "any-preserved-world", worlds.load("m0"), source={"kind": "fixture"}, links=refs
    )
    evidence = registry.artifact(b"Validation evidence for the fixture's linked preparation and suite.")
    availability = {
        "schema_version": "physim-registry-availability-v1",
        "eval_ready": {identifier: {"references": refs, "evidence": [evidence]}},
    }
    return registry, identifier, availability


def write_availability(registry, availability):
    (registry.root / "availability.json").write_text(json.dumps(availability))


def test_preserved_is_default_even_with_links_or_a_high_search_score(available):
    registry, _, _ = available
    registry.put("world-record", {"name": "example-harvest", "score": 1000000})
    catalog = export.build_catalog(registry.root)
    assert all(w["status"] == "preserved" for w in catalog["worlds"])
    assert all("priority" not in w and "curation" not in w for w in catalog["worlds"])


def test_any_world_can_be_eval_ready_with_explicit_evidence(available, tmp_path):
    registry, identifier, availability = available
    original = registry.path(identifier).read_bytes()
    write_availability(registry, availability)
    export.export_catalog(registry.root)
    catalog = json.loads((registry.root / "index.json").read_text())
    assert catalog["worlds"][0]["status"] == "eval-ready"
    assert catalog["availability"]["counts"] == {"eval-ready": 1}
    assert registry.path(identifier).read_bytes() == original
    assert "status" not in registry.get(identifier)["payload"]
    staged = export.stage_registry(registry.root, tmp_path / "stage")
    assert staged == catalog
    assert export.build_catalog(tmp_path / "stage") == catalog
    assert Registry(tmp_path / "stage").path(identifier).read_bytes() == original


@pytest.mark.parametrize("missing", ["world", "preparation", "suite", "bundle"])
def test_readiness_requires_every_physical_identity(available, missing):
    registry, identifier, availability = available
    availability["eval_ready"][identifier]["references"].pop(missing)
    write_availability(registry, availability)
    with pytest.raises(ValueError, match="require world, preparation, suite and bundle"):
        export.build_catalog(registry.root)


def test_readiness_rejects_mismatched_identities_and_missing_evidence(available):
    registry, identifier, availability = available
    entry = availability["eval_ready"][identifier]
    original = entry["references"]["bundle"]
    entry["references"]["bundle"] = "different"
    write_availability(registry, availability)
    with pytest.raises(ValueError, match="do not match"):
        export.build_catalog(registry.root)
    entry["references"]["bundle"] = original
    entry["evidence"] = []
    write_availability(registry, availability)
    with pytest.raises(ValueError, match="require validation evidence"):
        export.build_catalog(registry.root)


def test_unknown_world_and_corrupt_evidence_fail(available):
    registry, identifier, availability = available
    entry = availability["eval_ready"].pop(identifier)
    availability["eval_ready"]["unknown-world"] = entry
    write_availability(registry, availability)
    with pytest.raises(ValueError, match="unknown world"):
        export.build_catalog(registry.root)
    availability["eval_ready"] = {identifier: entry}
    write_availability(registry, availability)
    registry.path(entry["evidence"][0]).write_bytes(b"Changed")
    with pytest.raises(ValueError, match="integrity"):
        export.build_catalog(registry.root)


def test_preserved_only_registry_stages_without_availability_file(available, tmp_path):
    registry, _, _ = available
    expected = export.build_catalog(registry.root)
    assert export.stage_registry(registry.root, tmp_path / "stage") == expected


def test_current_catalog_has_only_two_statuses_and_no_future_plans():
    catalog = export.build_catalog(ROOT / "registry")
    assert catalog["availability"]["counts"] == {"eval-ready": 3, "preserved": 21}
    assert {w["name"] for w in catalog["worlds"] if w["status"] == "eval-ready"} == {
        "p4g2_044_centered_v2",
        "bf_trail_lab_centered_v2",
        "xv_rotor_lab_centered_v2",
    }
    for row in catalog["worlds"]:
        assert not ({"curation", "role", "priority", "next_check", "evaluation_stage"} & row.keys())

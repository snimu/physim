"""Import packaged and reference worlds with their available historical evidence.

This copies known artifacts; it does not reconstruct missing evolutionary runs,
execute historical sources, launch simulations, or publish a dataset.
"""

import argparse
import json
from pathlib import Path

import blobkit
from blobkit.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def import_registry(destination):
    registry = Registry(destination)
    packaged = Path(blobkit.__file__).parent / "data/worlds"
    extraction = json.loads((packaged / "_extraction.json").read_text())
    evidence = {
        name: (ROOT / name).read_bytes()
        for name in (
            "probes/blobs/blobkit/tools/extract_worlds.py",
            "probes/blobs/blobkit/MANIFEST.md",
            "probes/blobs/l0/complexity/worlds.py",
        )
    }
    evidence["packaged-extraction.json"] = (packaged / "_extraction.json").read_bytes()
    rows = []
    for name, origin in extraction["worlds"].items():
        genome = json.loads((packaged / (name + ".json")).read_text())
        world_id = registry.add_source_world(
            name,
            genome,
            source={
                "kind": "historical-package-extraction",
                "original_source": origin["source"],
                "original_genome_id": origin["id"],
                "genome_provenance": genome.get("provenance", {}),
                "kicks": extraction["kicks"].get(genome["id"]),
                "recipe_status": "partial",
                "missing": ["complete original generation recipe and execution record"],
            },
            artifacts={**evidence, "original-genome.json": (packaged / (name + ".json")).read_bytes()},
        )
        rows.append(dict(name=name, world=world_id, source_status="partial"))
    reference_path = ROOT / "probes/legacy/physim/physim/blobdata/p4g2_044.json"
    reference = json.loads(reference_path.read_text())
    catalog = json.loads((ROOT / "docs_source/worlds.json").read_text())
    metadata = catalog["worlds"][0]
    genome = reference.get("genome", reference)
    reference_evidence = {"source-record.json": reference_path.read_bytes()}
    for relative in (
        "probes/blobs/agentenv/round6/worked_example/p4g2_044/origin.py",
        "probes/blobs/agentenv/round6/worked_example/p4g2_044/cases/build_cases.py",
        "probes/blobs/agentenv/round6/worked_example/p4g2_044/native_validation/manifest.json",
        "probes/blobs/agentenv/round6/worked_example/p4g2_044/native_supplemental/manifest.json",
    ):
        reference_evidence[relative] = (ROOT / relative).read_bytes()
    sources = {name: registry.artifact(data) for name, data in reference_evidence.items()}
    historical_recipe = registry.put(
        "recipe",
        dict(
            name="historical-p4g2_044",
            provenance_status="partial",
            entrypoint=None,
            sources=sources,
            known={"operator": genome.get("provenance", {}), "island": reference["island"]},
            missing=["full search settings", "historical dependency snapshot", "parent genomes and checkpoints"],
        ),
        refs=sources.values(),
    )
    historical_run = registry.put(
        "generation-run",
        dict(
            recipe=historical_recipe,
            provenance_status="partial",
            source_candidate=reference["cand"],
            seed=reference["seed"],
            island=reference["island"],
            measurements={k: v for k, v in reference.items() if k != "genome"},
        ),
        refs=[historical_recipe],
    )
    identifier = registry.add_source_world(
        "p4g2_044",
        genome,
        source={
            "kind": "historical-evolution",
            "original_source": reference_path.relative_to(ROOT).as_posix(),
            "genome_provenance": genome.get("provenance", {}),
            "recorded_measurements": {k: v for k, v in reference.items() if k != "genome"},
            "recipe_status": "partial",
            "missing": ["complete original evolutionary recipe and generation checkpoints"],
        },
        artifacts=reference_evidence,
        links=metadata["reference_bundle"]["references"],
        recipe=historical_recipe,
        run=historical_run,
    )
    rows.append(dict(name="p4g2_044", world=identifier, source_status="partial"))
    report = dict(schema_version="physim-registry-index-v1", worlds=rows, verification=registry.verify())
    output = Path(destination) / "index.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "registry")
    print(json.dumps(import_registry(parser.parse_args().output), indent=2))

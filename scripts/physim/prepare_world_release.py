"""Stage the verified registry and all its eval-ready bundles for Hugging Face.

No uploads, model calls, or recipe execution. Preserve existing content identities.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

from blobkit.registry import Registry
from physim.bundles import Bundle, digest, identified

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from generators.physim.export_registry_catalog import export_catalog, stage_registry
from generators.physim.register_evaluation import export_bundle


def record_path(registry, identifier):
    return "registry/" + registry.path(identifier).relative_to(registry.root).as_posix()


def copy_bundle(bundle, destination):
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(bundle.root / "manifest.json", destination / "manifest.json")
    for name in bundle.files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle.verified_path(name), target)
    restored = Bundle(destination)
    restored.check_runtime()
    return restored


def dataset_card(release, catalog, entries):
    counts = catalog["availability"]["counts"]
    table = "\n".join(
        f"| {entry['world_name']} | {entry['public_ports']} | {entry['case_count']} | "
        f"[bundle]({entry['bundle_path']}/manifest.json) |"
        for entry in entries
    )
    template = (Path(__file__).parent / "worlds_dataset_card.md").read_text()
    values = {
        "DATASET_REPO": release["dataset_repo"],
        "WORLD_COUNT": len(catalog["worlds"]),
        "GENOME_COUNT": len({row["genome"] for row in catalog["worlds"]}),
        "PRESERVED_COUNT": counts.get("preserved", 0),
        "EVAL_COUNT": counts.get("eval-ready", 0),
        "EVALUATION_TABLE": table,
    }
    for name, value in values.items():
        template = template.replace("{{" + name + "}}", str(value))
    return template


def stage_release(*, registry_root, bundle_paths, output, release):
    registry = Registry(registry_root)
    supplied = {}
    for path in bundle_paths:
        bundle = Bundle(path)
        bundle.check_runtime()
        identifier = bundle.manifest["bundle_id"]
        if identifier in supplied:
            raise ValueError(f"Duplicate supplied bundle: {identifier}")
        supplied[identifier] = bundle
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    catalog = stage_registry(registry.root, output / "registry")
    shutil.copyfile(ROOT / "registry/README.md", output / "registry/README.md")
    shutil.copyfile(ROOT / "registry/CONTRIBUTING.md", output / "CONTRIBUTING.md")
    entries = []
    used = set()
    for row in sorted(catalog["worlds"], key=lambda world: (world["name"], world["id"])):
        if row["status"] != "eval-ready":
            continue
        refs = row["evaluation"]["references"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", row["name"]):
            raise ValueError(f"Unsafe evaluation preparation name: {row['name']}")
        relative = f"bundles/{row['name']}/{refs['bundle'].split(':')[-1]}"
        destination = output / relative
        if refs["bundle"] in supplied:
            bundle = copy_bundle(supplied[refs["bundle"]], destination)
            used.add(refs["bundle"])
        else:
            bundle = export_bundle(registry, row["id"], destination)
        if bundle.references() != refs:
            raise ValueError(f"Bundle identities differ from the registry: {row['name']}")
        for case in bundle.suite["cases"]:
            bundle.truth(case)
        implementation = bundle.manifest["objects"]["world"]["implementation"]
        entries.append(
            dict(
                world_name=row["name"],
                world_record=row["id"],
                description=f"Verified laboratory preparation of {bundle.manifest['objects']['world']['name']}.",
                bundle_path=relative,
                status="eval-ready",
                dataset_repo=release["dataset_repo"],
                exposure=release["exposure"],
                references=bundle.references(),
                profiles={
                    profile: sum(r["bytes"] for r in bundle.files.values() if profile in r["profiles"])
                    for profile in ("simulation", "evaluation")
                },
                manifest_bytes=(destination / "manifest.json").stat().st_size,
                case_count=len(bundle.suite["cases"]),
                truth_members=2,
                forecast_members=64,
                public_ports=bundle.roster.n_ports,
                code_versions=dict(physim=version("physim"), blobkit=implementation["blobkit_version"]),
                reference_dependencies=implementation["reference_dependencies"],
                licenses=bundle.manifest["licenses"],
            )
        )
    if supplied.keys() - used:
        raise ValueError("A supplied bundle is not linked to an eval-ready registry record")
    by_record = {entry["world_record"]: entry for entry in entries}
    worlds = [
        dict(
            world_record=row["id"],
            name=row["name"],
            status=row["status"],
            genome=row["genome"],
            genome_path=record_path(registry, row["genome"]),
            record_path=record_path(registry, row["id"]),
            recipe=row.get("recipe"),
            run=row.get("run"),
            bundle_path=by_record.get(row["id"], {}).get("bundle_path"),
        )
        for row in catalog["worlds"]
    ]
    for name, rows in (("catalog.jsonl", entries), ("worlds.jsonl", worlds)):
        (output / name).write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows))
    (output / "README.md").write_text(dataset_card(release, catalog, entries))
    shutil.copyfile(ROOT / "LICENSE-DATA", output / "LICENSE")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE-CODE")
    (output / ".gitattributes").write_text(
        "*.npz filter=lfs diff=lfs merge=lfs -text\n*.bin filter=lfs diff=lfs merge=lfs -text\n"
    )
    sources = [
        Path(__file__).resolve(),
        Path(__file__).with_name("worlds_dataset_card.md"),
        ROOT / "registry/CONTRIBUTING.md",
        ROOT / "generators/physim/export_registry_catalog.py",
        ROOT / "generators/physim/register_evaluation.py",
    ]
    baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    report = identified(
        "dataset-release",
        dict(
            schema_version="physim-dataset-release-v1",
            dataset_repo=release["dataset_repo"],
            registry_verification=catalog["verification"],
            availability=catalog["availability"],
            evaluations=entries,
            code=dict(
                git_baseline=baseline,
                working_tree_dirty=dirty,
                exporter_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in sources},
                package_publication="published" if release.get("code_packages") else "pending",
                code_packages=release.get("code_packages", {}),
            ),
            files=[
                dict(path=p.relative_to(output).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
                for p in sorted(output.rglob("*"))
                if p.is_file()
            ],
        ),
    )
    (output / "release.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "registry")
    parser.add_argument(
        "--bundle",
        action="append",
        type=Path,
        default=[],
        help="supplemental bundle absent from registry artifacts; repeat if necessary",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sync-docs", action="store_true", help="refresh the registry browsing projection")
    args = parser.parse_args()
    release = tomllib.loads((ROOT / "configs/physim/release.toml").read_text())
    report = stage_release(registry_root=args.registry, bundle_paths=args.bundle, output=args.output, release=release)
    if args.sync_docs:
        export_catalog(args.registry, sync_docs=True)
    print(
        json.dumps(
            dict(
                directory=str(args.output.resolve()),
                release_id=report["id"],
                registry=report["registry_verification"],
                evaluations=len(report["evaluations"]),
                files=len(report["files"]) + 1,
                bytes=sum(row["bytes"] for row in report["files"]),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

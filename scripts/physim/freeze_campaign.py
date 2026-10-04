"""Archive the local implementation and dependency identities before paid runs."""

import hashlib
import importlib.metadata
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def freeze(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = set()
    for directory in ("packages/blobkit", "generators/physim", "scripts/physim"):
        for path in (ROOT / directory).rglob("*"):
            if (
                path.is_file()
                and (path.suffix in (".py", ".toml", ".md", ".txt", ".Dockerfile") or path.name == "Dockerfile")
                and not any(part in (".venv", "__pycache__", "build", "dist") for part in path.parts)
            ):
                paths.add(path)
    paths.update(ROOT / name for name in ("pyproject.toml", "uv.lock"))
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}
    distribution = importlib.metadata.distribution("physim")
    environment_paths = {
        str(path): distribution.locate_file(path)
        for path in distribution.files
        if path.parts[0] in ("physim", "physim_r6", "physim_r6_scaling") and path.suffix in (".py", ".txt", ".json")
    }
    environment_sources = {
        relative: hashlib.sha256(path.read_bytes()).hexdigest() for relative, path in sorted(environment_paths.items())
    }
    archive_id = hashlib.sha256(
        json.dumps(dict(workspace=sources, environment=environment_sources), sort_keys=True).encode()
    ).hexdigest()
    archive = output / f"sources-{archive_id}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(paths):
            handle.write(path, path.relative_to(ROOT))
        for relative, path in sorted(environment_paths.items()):
            handle.write(path, "installed/" + relative)
    packages = {
        dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions() if dist.metadata.get("Name")
    }
    from physim.runtime_sandbox import PUBLIC_IMAGE

    tags = [PUBLIC_IMAGE]
    prime_agent = output / "prime_agent.json"
    if prime_agent.exists():
        tags.append(json.loads(prime_agent.read_text())["image"])
    images = json.loads(subprocess.check_output(["docker", "image", "inspect", *tags]))
    record = dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        source_id=archive_id,
        archive=archive.name,
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        sources=sources,
        environment_sources=environment_sources,
        environment_install=json.loads(distribution.read_text("direct_url.json") or "null"),
        packages=dict(sorted(packages.items())),
        images={tag: image["Id"] for tag, image in zip(tags, images, strict=True)},
    )
    encoded = json.dumps(record, indent=2) + "\n"
    (output / f"provenance-{archive_id}.json").write_text(encoded)
    (output / "provenance.json").write_text(encoded)
    print(json.dumps({key: record[key] for key in ("source_id", "archive", "images")}, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/evaluation-campaign-20260916")
    freeze(parser.parse_args().output)

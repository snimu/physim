"""The research workspace consumes one pinned environment and editable Blobkit."""

import importlib.metadata
import json
import tomllib
from pathlib import Path

import blobkit
import physim

ROOT = Path(__file__).resolve().parents[1]


def test_environment_install_matches_workspace_and_release_pins():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    source = project["tool"]["uv"]["sources"]["physim"]
    release = tomllib.loads((ROOT / "configs/physim/release.toml").read_text())["code_packages"]
    installed = json.loads(importlib.metadata.distribution("physim").read_text("direct_url.json"))
    assert installed["url"] == source["git"]
    assert installed["vcs_info"]["commit_id"] == source["rev"] == release["source_commit"]
    assert installed["subdirectory"] == source["subdirectory"]
    assert release["physim"] == f"git+{source['git']}@{source['rev']}#subdirectory={source['subdirectory']}"
    assert "environments/physim" not in project["tool"]["uv"]["workspace"]["members"]
    assert not (ROOT / "environments/physim/pyproject.toml").exists()
    assert not (ROOT / "environments/physim/physim").exists()
    assert not Path(physim.__file__).is_relative_to(ROOT / "environments")


def test_blobkit_is_the_editable_local_library():
    assert Path(blobkit.__file__).resolve().is_relative_to(ROOT / "packages/blobkit")
    installed = json.loads(importlib.metadata.distribution("blobkit").read_text("direct_url.json"))
    assert installed["dir_info"]["editable"]
    assert "physim" not in (importlib.metadata.requires("blobkit") or [])


def test_evaluation_preset_loads_with_the_pinned_framework():
    from verifiers.v1.configs.cli.eval import EvalConfig

    config = EvalConfig.model_validate(tomllib.loads((ROOT / "configs/physim/eval.toml").read_text()))
    assert config.env.taskset.id == "physim"
    assert config.push is False
    # No bundle override: the preset evaluates every preparation in the package's pinned catalog.
    tools = config.env.taskset.task.tools
    assert tools.bundle is None and tools.bundle_source is None
    assert sorted(path.name for path in (ROOT / "configs/physim").glob("*.toml")) == ["eval.toml", "release.toml"]

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


def test_active_evaluation_presets_load_with_the_pinned_framework():
    from verifiers.v1.configs.cli.eval import EvalConfig

    for name in ("eval", "p4g2_044", "bf_trail_lab", "xv_rotor_lab"):
        config = EvalConfig.model_validate(tomllib.loads((ROOT / f"configs/physim/{name}.toml").read_text()))
        assert config.env.taskset.id == "physim"
        assert config.push is False
        if name != "eval":
            assert config.select.limit == 1
            assert config.env.taskset.task.tools.bundle_source.revision == "dcd6abd5eae76a47f326c70518315d2d1e101d86"

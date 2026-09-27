"""Cross-filesystem artifacts retain exact Linux names and isolation."""

import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from physim import evaluation, taskset
from physim.artifact_store import (
    ARCHIVE,
    MARKER,
    SandboxError,
    archive_info,
    archive_workspace,
    read_artifact_files,
    snapshot_artifact,
)
from physim.sandbox import ExecutionLimits, Sandbox, docker


def tar_stream(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, value in entries:
            member = tarfile.TarInfo(name)
            if isinstance(value, bytes):
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
            else:
                member.type = value[0]
                member.linkname = "/outside"
                archive.addfile(member)
    stream.seek(0)
    return stream


def fixture_files():
    return [
        ("predictor.py", b"# data, never imported on the host"),
        ("y15.npy", b"lower"),
        ("Y15.npy", b"UPPER"),
        ("Data/value", b"one"),
        ("data/value", b"two"),
        ("\u00e9.txt", b"composed"),
        ("e\u0301.txt", b"decomposed"),
    ]


def test_case_and_unicode_names_survive_every_host_staging_copy(tmp_path):
    files = fixture_files()
    first = tmp_path / "first"
    manifest = archive_workspace(tar_stream(files), first, ExecutionLimits())
    assert not (first / "y15.npy").exists()
    assert read_artifact_files(first, manifest["files"]) == files
    frozen = tmp_path / "frozen"
    assert evaluation._snapshot_inputs(first, frozen) == manifest["files"]
    final = tmp_path / "final"
    assert snapshot_artifact(frozen, final, ExecutionLimits())["files"] == manifest["files"]
    assert read_artifact_files(final, manifest["files"]) == files


@pytest.mark.parametrize(
    "entries",
    [
        [("../escape", b"x")],
        [("/absolute", b"x")],
        [("link", (tarfile.SYMTYPE,))],
        [("link", (tarfile.LNKTYPE,))],
        [("fifo", (tarfile.FIFOTYPE,))],
        [("a", b"x"), ("./a", b"y")],
        [("a", b"x"), ("a/b", b"y")],
        [("a/b", b"x"), ("a", b"y")],
    ],
)
def test_unsafe_archives_are_rejected_without_publishing_manifest(tmp_path, entries):
    with pytest.raises(SandboxError):
        archive_workspace(tar_stream([("predictor.py", b"x"), *entries]), tmp_path / "bad", ExecutionLimits())
    assert not (tmp_path / "bad" / MARKER).exists()


def test_archives_retain_size_caps_and_tamper_detection(tmp_path):
    limits = ExecutionLimits(file_mib=1)
    with pytest.raises(SandboxError, match="size limit"):
        archive_workspace(tar_stream([("predictor.py", b"x" * (1024 * 1024 + 1))]), tmp_path / "large", limits)
    target = tmp_path / "good"
    info = archive_workspace(tar_stream(fixture_files()), target, limits)
    with (target / ARCHIVE).open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(SandboxError, match="hash mismatch"):
        read_artifact_files(target, info["files"])


def test_legacy_artifacts_still_work_and_links_stay_forbidden(tmp_path):
    source = tmp_path / "old"
    source.mkdir()
    (source / "predictor.py").write_bytes(b"old predictor")
    output = tmp_path / "converted"
    info = snapshot_artifact(source, output, ExecutionLimits())
    assert read_artifact_files(output, info["files"]) == [("predictor.py", b"old predictor")]
    (source / "link").symlink_to(source / "predictor.py")
    with pytest.raises(SandboxError, match="symlinks"):
        snapshot_artifact(source, tmp_path / "bad", ExecutionLimits())


def test_archived_checkpoint_preserves_both_names(tmp_path):
    artifact = tmp_path / "validate_01"
    files = fixture_files()
    manifest = archive_workspace(tar_stream(files), artifact, ExecutionLimits())
    (tmp_path / "laboratory_state.json").write_text(
        json.dumps(
            dict(
                prompt_condition=taskset.PROMPT_CONDITION,
                reward_precision=taskset.DEFAULT_PRECISION,
                checks=[dict(path=artifact.name, validation=dict(ok=True), snapshot=manifest)],
                experiments=[],
                usage=dict(experiments=0, charged_tu=0),
            )
        )
    )
    _, restored, _ = taskset.load_checkpoint(artifact)
    assert restored == files


@pytest.mark.skipif(os.environ.get("PHYSIM_DOCKER_TESTS") != "1", reason="requires Docker")
def test_docker_export_validation_and_grading_keep_case_distinct_and_readonly(tmp_path):
    observations = tmp_path / "observations"
    observations.mkdir()
    # This runs in the Linux investigation container and then checks that both
    # names still exist after export, grading freeze, and predictor staging.
    code = """import pathlib
pathlib.Path('/workspace/y15.npy').write_text('2')
pathlib.Path('/workspace/Y15.npy').write_text('5')
pathlib.Path('/workspace/Data').mkdir()
pathlib.Path('/workspace/data').mkdir()
pathlib.Path('/workspace/Data/x').write_text('11')
pathlib.Path('/workspace/data/x').write_text('13')
"""
    predictor = """import pathlib, numpy as np
def predict(actions, queries, n_samples=64, seed=0):
    root = pathlib.Path(__file__).parent
    assert (root/'y15.npy').read_text() == '2'
    assert (root/'Y15.npy').read_text() == '5'
    assert (root/'Data/x').read_text() == '11'
    assert (root/'data/x').read_text() == '13'
    try:
        (root/'cannot_write').write_text('bad')
    except OSError:
        pass
    else:
        raise RuntimeError('workspace must be read-only')
    slots = {'device0':13, 'device1':19, 'global':2}
    return {'samples':[np.full((n_samples,len(q['t']),12,slots[q['sensor']]),7.0) for q in queries]}
"""
    box = Sandbox(observations)
    try:
        result = box.python(code + f"\npathlib.Path('/workspace/predictor.py').write_text({predictor!r})")
        assert result["exit_code"] == 0, result
        artifact = tmp_path / "submit_01"
        box.export_workspace(artifact)
    finally:
        box.close()
    assert evaluation.validate_predictor(artifact, observations)["ok"]
    # Use the real grading path and a two-case prepared data-only fixture;
    # numerical truth and scoring execute unchanged, with no model API call.
    from physim.bundles import Bundle

    root = Path(__file__).resolve().parents[1]
    bundle = Bundle(root / "outputs/eval-preparation-20260916/p4g2_044/bundle")
    bundle.suite = dict(bundle.suite, cases=bundle.suite["cases"][:2])
    grade = evaluation.grade(artifact, observations, tmp_path / "grade", bundle=bundle, members=2)
    assert grade["status"] == "COMPLETE" and grade["valid_cases"] == 2
    assert {f["path"] for f in grade["predictor"]["files"]} == {f["path"] for f in archive_info(artifact)["files"]}
    # No helper/predictor volumes may outlive their sandbox lifecycle.
    remaining = docker(["volume", "ls", "--format", "{{.Name}}", "--filter", f"name={box.name}"])
    assert not remaining.strip()

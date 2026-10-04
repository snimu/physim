"""Campaign diagnostics preserve native harness behavior and redact credentials."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import verifiers.v1.harnesses.bash.harness as bash


def diagnostics_module():
    path = Path(__file__).resolve().parents[1] / "scripts/physim/campaign_diagnostics.py"
    spec = importlib.util.spec_from_file_location("campaign_diagnostics_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostics_redact_auth_and_query_secrets():
    value = diagnostics_module().redact(
        "Authorization: Bearer private-token --api-key=private-key http://host/mcp?vf_state_signature=secret-value"
    )
    for secret in ("private-token", "private-key", "secret-value"):
        assert secret not in value


def test_full_harness_error_is_saved_before_native_truncation(tmp_path, monkeypatch):
    from verifiers.v1.harness import Harness

    async def native_check(*args):
        raise RuntimeError("native error still propagates")

    monkeypatch.setattr(Harness, "_check_result", native_check)
    diagnostics_module().install(tmp_path)
    result = SimpleNamespace(
        stdout="", stderr="root cause first\n" + "x" * 5000 + "\nAuthorization: Bearer private-token"
    )
    with pytest.raises(RuntimeError, match="native error still propagates"):
        asyncio.run(Harness._check_result(None, SimpleNamespace(id="trace"), None, result))
    saved = (tmp_path / "trace.harness.stderr.log").read_text()
    assert saved.startswith("root cause first") and len(saved) > 5000
    assert "private-token" not in saved
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["installation"]["vcs_info"]["commit_id"]
    assert "Native harness unchanged" in manifest["behavior"]


def test_capture_keeps_native_program_and_prompts_unchanged(tmp_path, monkeypatch):
    from verifiers.v1.harness import Harness

    original_program = bash.CHAT_PROGRAM_SOURCE
    original_prompt = bash.BASH_SYSTEM_PROMPT

    async def native_check(*args):
        return "native-result"

    monkeypatch.setattr(Harness, "_check_result", native_check)
    diagnostics_module().install(tmp_path)
    assert bash.CHAT_PROGRAM_SOURCE == original_program
    assert bash.BASH_SYSTEM_PROMPT == original_prompt
    result = SimpleNamespace(stdout="ok", stderr="")
    assert asyncio.run(Harness._check_result(None, SimpleNamespace(id="trace"), None, result)) == "native-result"


def test_diagnostics_preserve_external_cancellation(tmp_path, monkeypatch):
    from verifiers.v1.harness import Harness

    async def cancelled(*args):
        raise asyncio.CancelledError

    monkeypatch.setattr(Harness, "_check_result", cancelled)
    diagnostics_module().install(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            Harness._check_result(None, SimpleNamespace(id="trace"), None, SimpleNamespace(stdout="", stderr=""))
        )

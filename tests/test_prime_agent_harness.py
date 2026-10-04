"""The installed environment uses the framework's native Prime Agent harness."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from verifiers.v1.harnesses.prime_agent.harness import PrimeAgentHarness, PrimeAgentHarnessConfig
from verifiers.v1.task import TaskData
from verifiers.v1.utils.loaders import load_harness


def test_native_harness_keeps_interception_and_context_settings():
    writes = {}

    async def write(path, data):
        writes[path] = data

    config = PrimeAgentHarnessConfig(
        id="prime-agent",
        context_window=65536,
        compaction={"reserve_tokens": 36864, "keep_recent_tokens": 12000},
    )
    harness = load_harness(config)
    assert isinstance(harness, PrimeAgentHarness)
    harness.install_skills = AsyncMock()
    trace = SimpleNamespace(id="fresh-rollout", info={})
    result = asyncio.run(
        harness.prepare_acp(
            SimpleNamespace(model="test/model", sampling=SimpleNamespace(max_tokens=32768, reasoning_effort="high")),
            trace,
            SimpleNamespace(write=write, run=AsyncMock(return_value=SimpleNamespace(exit_code=0, stderr=""))),
            "http://proxy:123/v1",
            "interception-only",
            {},
            TaskData(system_prompt="Public task", prompt="Begin"),
        )
    )
    home = result.env["PRIME_AGENT_CODING_AGENT_DIR"]
    provider = json.loads(writes[home + "/models.json"])["providers"]["intercept"]
    assert provider["baseUrl"] == "http://proxy:123/v1"
    assert provider["models"][0]["contextWindow"] == 65536
    assert provider["models"][0]["maxTokens"] == 32768
    assert result.env["PRIME_AGENT_INTERCEPT_KEY"] == "interception-only"
    assert not any(k in result.env for k in ("PRIME_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"))
    assert json.loads(writes[home + "/settings.json"])["compaction"]["reserveTokens"] == 36864
    assert "--offline" in result.command
    assert "--continue" not in result.command and "--resume" not in result.command

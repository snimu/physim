"""Regression checks for unbounded investigation and explicit predictor resources."""

import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from physim import taskset
from physim.blobround6_explore import ExperimentService
from physim.evaluation import _snapshot_inputs
from physim.runtime_sandbox import RuntimeSandbox
from physim.sandbox import ExecutionLimitError, ExecutionLimits
from physim_r6.scaling import ScalingTask, SpendConfig, spend_accounting


def test_unlimited_experiments_keep_accounting_and_request_validation():
    oracle = SimpleNamespace(sample_truth=lambda *args, **kw: {"samples": []})
    service = ExperimentService(oracle, max_experiments=None, max_total_tu=None)
    for _ in range(1001):
        service.experiment([], [{"sensor": "global", "t": [50]}])
    assert service.usage() == dict(experiments=1001, max_experiments=None, charged_tu=50050, max_total_tu=None)
    with pytest.raises(ValueError):
        service.experiment([], [{"sensor": "global", "t": [51]}])
    assert service.usage()["experiments"] == 1001


def test_null_caps_and_predictor_policy_round_trip_and_reach_prompt():
    config = taskset.R6ToolsConfig(
        max_experiments=None,
        max_total_tu=None,
        max_validation_attempts=None,
        max_submission_attempts=None,
        predictor_limits=ExecutionLimits(cpu_seconds=3600, wall_seconds=3600, cpus=4, memory_gib=8),
    )
    restored = taskset.R6ToolsConfig.model_validate_json(config.model_dump_json())
    assert restored == config
    with patch.object(taskset, "public_roster", return_value=taskset.E.E.DEFAULT_ROSTER):
        prompt = taskset.public_prompt(config)
    assert "unlimited experiments" in prompt and "Validation attempts: unlimited" in prompt
    assert "3600 CPU seconds" in prompt and "8 GiB" in prompt
    assert "None" not in prompt


def test_predictor_configuration_reaches_validator(tmp_path):
    config = taskset.R6ToolsConfig(
        predictor_limits=ExecutionLimits(cpu_seconds=3600, wall_seconds=3600, cpus=4, memory_gib=8)
    )
    state = taskset.R6State(output=str(tmp_path))
    with (
        patch.object(taskset, "_snapshot", return_value={}),
        patch.object(taskset, "public_roster", return_value=taskset.E.E.DEFAULT_ROSTER),
        patch.object(taskset.E, "validate_predictor", return_value={"ok": True}) as validate,
    ):
        assert taskset._check(state, config, final=True)["accepted"]
        assert asdict(validate.call_args.kwargs["execution_limits"]) == asdict(config.predictor_limits)


def test_optional_budget_preserves_accounting_and_historical_finite_configs():
    config = SpendConfig(input_usd_per_mtok=1, output_usd_per_mtok=2, context_window=100000, max_response_tokens=10000)
    trace = SimpleNamespace(calls=[SimpleNamespace(usage=None)], extra_usage=[])
    assert spend_accounting(trace, config)["accounted_cost_usd"] == pytest.approx(0.12)
    assert config.limit_usd is None
    assert SpendConfig.model_validate_json(config.model_dump_json()).limit_usd is None
    assert SpendConfig(**(config.model_dump() | {"limit_usd": 150})).limit_usd == 150
    for limit in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            SpendConfig(**(config.model_dump() | {"limit_usd": limit}))


@pytest.mark.parametrize("limit,expected_stop", [(None, False), (150, True)])
def test_native_budget_hook_never_stops_uncapped_run_and_still_writes_receipts(tmp_path, limit, expected_stop):
    config = SpendConfig(
        limit_usd=limit, input_usd_per_mtok=1, output_usd_per_mtok=2, context_window=100000, max_response_tokens=10000
    )
    task = SimpleNamespace(config=SimpleNamespace(spend=config))
    trace = SimpleNamespace(
        calls=[SimpleNamespace(usage=SimpleNamespace(cost=1000000)), SimpleNamespace(usage=None)],
        extra_usage=[],
        state=SimpleNamespace(output=str(tmp_path)),
        info={},
    )
    assert asyncio.run(ScalingTask.dollar_budget(task, trace)) is expected_stop
    receipt = json.loads((tmp_path / "spend_state.json").read_text())
    assert receipt["stopped"] is expected_stop
    assert receipt["limit_usd"] == limit
    assert receipt["reported_cost_usd"] == 1000000
    assert receipt["unreported_cost_reserve_usd"] == pytest.approx(0.12)


def test_grading_preserves_more_than_one_hundred_host_observations(tmp_path):
    source = tmp_path / "observations"
    source.mkdir()
    for i in range(101):
        (source / f"experiment_{i}.npz").write_bytes(b"host-generated fixture")
    rows = _snapshot_inputs(source, tmp_path / "frozen", observations=True)
    assert len(rows) == 101


def test_resource_kill_is_distinguishable_from_a_bad_predictor():
    box = object.__new__(RuntimeSandbox)
    box.limits = ExecutionLimits()
    box.runtime = SimpleNamespace(
        write=AsyncMock(),
        run=AsyncMock(return_value=SimpleNamespace(exit_code=137, stdout="", stderr="")),
    )
    with pytest.raises(ExecutionLimitError, match="status 137"):
        asyncio.run(box.predict([], [], 1, 0, 12))


def test_spend_hook_uses_native_verifiers_trace_boundary():
    import verifiers.v1 as vf
    from physim_r6.scaling import ScalingTask
    from verifiers.v1.session import hook_boundary

    assert hook_boundary(ScalingTask.dollar_budget, allow_trace=True) is vf.Trace

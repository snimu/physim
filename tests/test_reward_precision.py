"""Scientific score preservation, reward boundaries, and disclosed targets."""

import json
import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from physim import taskset as T
from physim.rewards import precision_label, precision_reward


@pytest.mark.parametrize("energy,expected", [(None, 0), (0, 1), (0.001, 1), (0.01, 1), (0.1, 0.5), (1, 0), (2, 0)])
def test_reward_boundaries(energy, expected):
    assert precision_reward(energy, 2) == pytest.approx(expected)


@pytest.mark.parametrize("k", [0, -1, math.inf, math.nan])
def test_precision_must_be_positive_and_finite(k):
    with pytest.raises(ValueError):
        precision_reward(0.1, k)
    with pytest.raises(ValueError):
        T.R6ToolsConfig(reward_precision=k)


@pytest.mark.parametrize("energy", [-0.1, math.inf, math.nan])
def test_bad_scientific_score_is_not_silently_rewarded(energy):
    with pytest.raises(ValueError):
        precision_reward(energy)


def test_precision_changes_prompt_without_changing_budgets():
    low = T.R6ToolsConfig(reward_precision=1)
    high = low.model_copy(update={"reward_precision": 3.5})
    assert "K = 1" in T.public_prompt(low)
    assert "K = 3.5" in T.public_prompt(high)
    assert "S <= 10^(-3.5)" in T.public_prompt(high)
    assert low.max_experiments == high.max_experiments
    assert precision_reward(0.01, 3.5) < precision_reward(0.01, 1)
    precise = T.R6ToolsConfig(reward_precision=2.0000001)
    assert "K = 2.0000001" in T.public_prompt(precise)
    assert float(precision_label(precise.reward_precision)) == precise.reward_precision


def test_precision_is_part_of_run_identity():
    from verifiers.v1.utils.loaders import load_taskset

    with patch.object(T, "required_bundle", return_value=None):
        tasks = [
            next(
                iter(
                    load_taskset(
                        T.R6Config(id="physim", task=T.R6TaskConfig(tools=T.R6ToolsConfig(reward_precision=k)))
                    )
                )
            )
            for k in (1, 2)
        ]
    assert tasks[0].data.protocol != tasks[1].data.protocol
    assert "-k-1" in tasks[0].data.protocol
    assert "-k-2" in tasks[1].data.protocol


def test_checkpoint_cannot_silently_change_precision(tmp_path):
    artifact = tmp_path / "validate_01"
    artifact.mkdir()
    (tmp_path / "laboratory_state.json").write_text(
        json.dumps(dict(prompt_condition=T.PROMPT_CONDITION, reward_precision=1))
    )
    with pytest.raises(T.vf.TaskError, match="reward precision"):
        T.load_checkpoint(artifact, reward_precision=2)


@pytest.mark.asyncio
async def test_task_applies_mapping_to_aggregate_and_preserves_energy(tmp_path):
    config = T.R6TaskConfig(tools=T.R6ToolsConfig(reward_precision=2))
    task = SimpleNamespace(config=config, data=SimpleNamespace(protocol="test"))
    state = T.R6State(output=str(tmp_path), submitted=True, artifact=str(tmp_path / "artifact"))
    trace = SimpleNamespace(
        state=state,
        info={},
        id="test",
        calls=[],
        agent=SimpleNamespace(config=SimpleNamespace(harness=SimpleNamespace(id="bash"))),
    )
    # Averaging then mapping differs substantially from averaging mapped case rewards.
    energy = (0.001 + 1.999) / 2
    with (
        patch.object(T.E, "grade", return_value={"primary_joint_energy": energy}) as grade,
        patch.object(T, "required_bundle", return_value=None),
        patch.object(T.E, "file_digest", return_value="fixture"),
    ):
        assert await T.R6Task.prediction_reward(task, trace) == 0
    assert trace.info["r6"]["primary_joint_energy"] == energy
    assert trace.info["r6"]["reward_precision"] == 2
    assert grade.call_args.kwargs["run_context"]["reward_precision"] == 2


@pytest.mark.asyncio
async def test_no_predictor_still_receives_zero_with_target_recorded():
    task = SimpleNamespace(config=T.R6TaskConfig())
    trace = SimpleNamespace(state=T.R6State(), info={})
    assert await T.R6Task.prediction_reward(task, trace) == 0
    assert trace.info["r6"]["primary_joint_energy"] is None
    assert trace.info["r6"]["reward_precision"] == 2

"""Agent-facing contract must specify I/O without suggesting the hidden mechanism."""

import inspect
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from physim import blobround6 as R6
from physim import blobround6_eval as E
from physim import evaluation
from physim import taskset as T
from physim.blobround6_explore import ExperimentService, RequestError
from physim.sandbox import SandboxInfrastructureError

# Regression vocabulary for the leak we found, including negative disclaimers.
# This supplements boundary checks; it is not a proof of semantic neutrality.
FORBIDDEN = re.compile(
    r"\b(spatial|field|fields|grid|grids|geometry|geometric|translation|dilation|"
    r"center|centered|source|sources|pulse|pulses|diffusion|periodic|lattice|"
    r"square|hexagonal|activator|inhibitor|reaction|coordinates|position|positions|"
    r"pose|poses|microscopic|p4g2_044|blobkit)\b",
    re.I,
)


def assert_neutral(text):
    assert not FORBIDDEN.search(text), FORBIDDEN.search(text).group()


@pytest.mark.parametrize("protocol", [R6.APPARATUS_PROTOCOL, R6.LEGACY_PROTOCOL])
@pytest.mark.parametrize("n_ports", [4, 6, 12])
@pytest.mark.parametrize("coding", ["shell", "ipython"])
def test_rendered_prompt_and_tools_only_describe_interface(protocol, n_ports, coding):
    with patch.object(T, "public_roster", return_value=E.PublicRoster(n_ports=n_ports, protocol=protocol)):
        prompt = T.public_prompt(T.R6ToolsConfig(), coding)
    assert_neutral(prompt)
    assert f"{n_ports} channels" in prompt
    for fn in [
        T.LaboratoryTools.experiment,
        T.LaboratoryTools.validate,
        T.LaboratoryTools.submit,
        T.LaboratoryTools.usage,
    ]:
        assert_neutral(inspect.getdoc(fn))
    assert_neutral(T.recovery_prompt())


@pytest.mark.parametrize("protocol", [R6.APPARATUS_PROTOCOL, R6.LEGACY_PROTOCOL])
def test_invalid_requests_expose_only_public_rules(protocol):
    service = ExperimentService(None, roster=E.PublicRoster(protocol=protocol))
    requests = [
        ([], [{"sensor": "device0", "t": [0.013]}]),
        ([], [{"sensor": "global", "t": [1, 0]}]),
        ([{"t": 0, "kind": "inject"}], []),
        ([{"t": 0, "kind": "adjust", "device": 0, "u": [2, 0, 0]}], []),
    ]
    for actions, queries in requests:
        with pytest.raises(RequestError) as error:
            service.experiment(actions, queries)
        assert_neutral(str(error.value))
    assert service.usage()["experiments"] == 0


@pytest.mark.asyncio
async def test_observation_transfer_contains_only_request_and_measurements(tmp_path):
    server = T.LaboratoryTools(T.R6ToolsConfig())
    server.state.output = str(tmp_path)
    (tmp_path / "observations").mkdir()
    oracle = SimpleNamespace(sample_truth=lambda *args, **kwargs: {"samples": [np.zeros((1, 1, 12, 2))]})
    server.service = ExperimentService(oracle)
    request = dict(actions=[], queries=[dict(sensor="global", t=[0])])
    transferred = []
    with patch.object(T, "_put_observation", side_effect=lambda state, path: transferred.append(path)):
        response = json.loads(await server.experiment(**request))
    assert set(response) == {"path", "arrays", "usage"}
    assert_neutral(json.dumps(response))
    assert response["path"] == "/observations/experiment_001.npz"
    with np.load(transferred[0], allow_pickle=False) as data:
        assert set(data.files) == {"request", "query0"}
        assert json.loads(data["request"].item()) == request
        assert data["query0"].shape == (1, 1, 12, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ValueError("private field grid"), E.EvaluationError("private field grid")])
async def test_internal_failures_are_not_request_feedback(tmp_path, error):
    server = T.LaboratoryTools(T.R6ToolsConfig())
    server.state.output = str(tmp_path)

    def fail(*args, **kwargs):
        raise error

    server.service = ExperimentService(SimpleNamespace(sample_truth=fail))
    with pytest.raises(T.vf.ToolsetError) as failure:
        await server.experiment(actions=[], queries=[])
    assert_neutral(str(failure.value))
    assert "private field grid" in json.loads((tmp_path / "laboratory_state.json").read_text())["infrastructure_error"]


@pytest.mark.asyncio
async def test_outer_mcp_boundary_masks_transport_errors(tmp_path):
    server = T.LaboratoryTools(T.R6ToolsConfig())
    server.state.output = str(tmp_path)

    async def fail():
        raise RuntimeError("/private/path/centered-pulse-v2/fields.npz")

    with patch.object(T.vf.Toolset, "_with_state", side_effect=lambda fn: fn):
        wrapped = server._with_state(fail)
    response = await wrapped()
    assert_neutral(response)
    assert "/private/path/" not in response


@pytest.mark.parametrize("protocol", [R6.APPARATUS_PROTOCOL, R6.LEGACY_PROTOCOL])
def test_validation_response_has_no_private_protocol_or_truth(protocol):
    roster = E.PublicRoster(n_ports=6, protocol=protocol)

    def predictions(box, actions, queries, *, members, seed, roster):
        return {"samples": [np.zeros((members, len(q["t"]), 6, roster.slots(q["sensor"]))) for q in queries]}, {}

    with patch.object(evaluation, "Sandbox"), patch.object(evaluation, "read_prediction", side_effect=predictions):
        report = evaluation.validate_predictor(
            "/artifact", "/observations", roster=roster, sandbox_factory=evaluation.Sandbox
        )
    assert report["ok"]
    assert report["public_roster"] == dict(n_ports=6, device_slots=[13, 19])
    assert_neutral(json.dumps(report))
    assert "protocol" not in report["public_roster"]


def test_container_transport_error_is_not_validation_feedback():
    with (
        patch.object(evaluation, "Sandbox"),
        patch.object(evaluation, "read_prediction", side_effect=SandboxInfrastructureError("/private/source/path")),
        pytest.raises(SandboxInfrastructureError),
    ):
        evaluation.validate_predictor("/artifact", "/observations", sandbox_factory=evaluation.Sandbox)


def test_checkpoint_without_current_condition_cannot_restore_leaky_manual(tmp_path):
    artifact = tmp_path / "submit_01"
    artifact.mkdir()
    (tmp_path / "laboratory_state.json").write_text(json.dumps({"checks": []}))
    with pytest.raises(T.vf.TaskError, match="prompt condition"):
        T.load_checkpoint(artifact)


@pytest.mark.asyncio
async def test_internal_error_is_pushed_then_terminates_as_framework_failure(tmp_path):
    server = T.LaboratoryTools(T.R6ToolsConfig())
    saved = T.R6State(output=str(tmp_path))

    async def pull():
        return saved.model_copy(deep=True)

    async def push(before):
        nonlocal saved
        saved = server.state.model_copy(deep=True)

    async def fail():
        raise RuntimeError("private field grid")

    with patch.object(server, "_pull_state", pull), patch.object(server, "_push_state", push):
        response = await server._with_state(fail)()
    assert_neutral(response)
    assert saved.infrastructure_error == "RuntimeError: private field grid"
    with pytest.raises(T.vf.TaskError, match="Laboratory service failed"):
        await T.R6Task.infrastructure_failed(None, SimpleNamespace(state=saved))
    access = SimpleNamespace(close=AsyncMock())
    task = SimpleNamespace(_runtime_access={"trace": access})
    task._finalize = lambda trace, runtime: T.R6Task._finalize(task, trace, runtime)
    with pytest.raises(T.vf.TaskError, match="Laboratory service failed"):
        await T.R6Task.finalize(task, SimpleNamespace(id="trace", state=saved), None)
    access.close.assert_awaited_once()
    assert task._runtime_access == {} and saved.runtime_access == {}

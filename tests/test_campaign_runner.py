"""Campaign admission and receipt accounting without model calls."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "scripts/physim/run_campaign.py"
    spec = importlib.util.spec_from_file_location("campaign_runner_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status,expected", [(400, False), (401, False), (None, False), (429, True), (503, True)])
def test_retry_only_transient_provider_errors(runner, status, expected):
    assert runner.retryable_provider_error(dict(type="ProviderError", status_code=status)) is expected
    assert not runner.retryable_provider_error(dict(type="HarnessError", status_code=status))


def test_user_manages_all_spending_but_selected_run_bound_remains(runner):
    for spent in (49, 50, 149, 150, 151, 1000000):
        assert not runner.pause_before_launch(spent, 0, 1)
        assert runner.pause_before_launch(spent, 1, 1)


def test_resolved_campaign_has_unlimited_investigation_and_large_predictor(runner, tmp_path):
    model = dict(
        id="offline/test",
        specs=dict(context_window=100000, max_output_tokens=65000),
        pricing=dict(input_usd_per_mtok=1, output_usd_per_mtok=2),
        reasoning=dict(supported_efforts=["max", "high", "low"]),
    )
    config = runner.configuration(tmp_path, tmp_path, model, tmp_path / "bundle")
    agent = config["env"]["agent"]
    assert all(agent[key] is None for key in ("max_turns", "max_input_tokens", "max_output_tokens", "max_total_tokens"))
    tools = config["env"]["taskset"]["task"]["tools"]
    assert all(
        tools[key] is None
        for key in ("max_experiments", "max_total_tu", "max_validation_attempts", "max_submission_attempts")
    )
    assert tools["predictor_runtime"]["type"] == agent["runtime"]["type"] == "docker"
    assert tools["predictor_runtime"]["allow"] == []
    assert tools["predictor_limits"]["cpu_seconds"] == 3600
    assert agent["sampling"]["reasoning_effort"] == "max"
    assert config["env"]["taskset"]["task"]["spend"]["limit_usd"] is None


@pytest.mark.parametrize(
    "model_id,transport",
    [
        ("anthropic/claude-sonnet-5", "anthropic_messages"),
        ("openai/gpt-5.6-terra", "responses"),
        ("qwen/qwen3.5-35b-a3b", "chat_completions"),
    ],
)
def test_prime_agent_condition_preserves_science_and_uses_native_routes(runner, tmp_path, model_id, transport):
    runner.dump(tmp_path / "prime_agent.json", {"image": "physim-prime-agent:0.9.5"})
    model = dict(
        id=model_id,
        specs=dict(context_window=262144, max_output_tokens=65536),
        pricing=dict(input_usd_per_mtok=2, output_usd_per_mtok=10),
        reasoning=dict(supported_efforts=["max", "high"]),
    )
    config = runner.configuration(tmp_path, tmp_path, model, tmp_path / "bundle")
    agent = config["env"]["agent"]
    task = config["env"]["taskset"]["task"]
    assert agent["harness"]["id"] == "prime-agent"
    assert agent["harness"]["autonomous"]
    assert agent["harness"]["context_window"] == 262144
    assert agent["harness"]["compaction"]["reserve_tokens"] > agent["sampling"]["max_tokens"]
    assert agent["sampling"]["reasoning_effort"] == "max"
    assert task["coding_interface"] == "ipython"
    assert task["spend"]["limit_usd"] is None
    assert task["tools"]["max_experiments"] is None
    assert agent["runtime"]["allow"] == []
    assert agent["sampling"]["extra_body"]["usage"] == {"include": True}
    if transport == "anthropic_messages":
        assert task["spend"]["cache_write_usd_per_mtok"] == 4


def test_ledger_uses_final_receipt_once_and_keeps_retry_spend(runner, tmp_path):
    for i, cost in enumerate((0.5, 17.0)):
        attempt = tmp_path / "attempts" / str(i)
        runner.dump(attempt / "attempt.json", dict(key="one", launched=True, status="error" if i == 0 else "complete"))
        runner.dump(
            attempt / "artifacts" / "trace" / "spend_final.json", dict(accounted_cost_usd=cost, reported_cost_usd=cost)
        )
        runner.dump(
            attempt / "artifacts" / "trace" / "spend_state.json",
            dict(accounted_cost_usd=cost - 0.1, reported_cost_usd=cost - 0.1),
        )
    ledger = runner.ledger(tmp_path)
    assert ledger["accounted_cost_usd"] == 17.5
    assert ledger["target_usd"] == 50 and ledger["pause_ceiling_usd"] is None


def test_missing_receipt_blocks_more_spending(runner, tmp_path):
    runner.dump(
        tmp_path / "attempts" / "interrupted" / "attempt.json", dict(key="one", launched=True, status="running")
    )
    with pytest.raises(RuntimeError, match="Missing spend receipt"):
        runner.ledger(tmp_path)


def test_response_reservation_leaves_room_for_conversation(runner, tmp_path):
    model = dict(
        id="offline/test",
        specs=dict(context_window=262144, max_output_tokens=235929),
        pricing=dict(input_usd_per_mtok=0.95, output_usd_per_mtok=4),
    )
    config = runner.configuration(tmp_path, tmp_path, model, tmp_path / "bundle")
    maximum = config["sampling"]["max_tokens"]
    assert maximum == 65536
    assert maximum + 27495 + 576 < model["specs"]["context_window"]
    assert config["env"]["agent"]["sampling"]["max_tokens"] == maximum
    assert config["env"]["taskset"]["task"]["spend"]["max_response_tokens"] == maximum
    model["specs"]["max_output_tokens"] = 32768
    smaller = runner.configuration(tmp_path, tmp_path, model, tmp_path / "bundle")
    assert smaller["sampling"]["max_tokens"] == 32768


def test_terminal_provider_error_reserves_last_call_from_trace(runner, tmp_path):
    import json

    attempt = tmp_path / "attempts" / "failure"
    runner.dump(attempt / "attempt.json", dict(key="one", launched=True, status="error"))
    runner.dump(
        attempt / "artifacts" / "trace" / "spend_state.json",
        dict(accounted_cost_usd=0.2, reported_cost_usd=0.2, model_calls=1),
    )
    runner.dump(
        attempt / "eval.json",
        {
            "env": {
                "taskset": {
                    "task": {
                        "spend": dict(
                            limit_usd=150,
                            input_usd_per_mtok=1,
                            output_usd_per_mtok=2,
                            context_window=100000,
                            max_response_tokens=50000,
                        )
                    }
                }
            }
        },
    )
    trace_path = attempt / "runs" / "run" / "traces.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps(
            {
                "traces": [
                    {
                        "calls": [
                            {"usage": {"cost": 0.2}},
                            {"usage": None},
                        ],
                        "extra_usage": [],
                    }
                ]
            }
        )
    )
    result = runner.ledger(tmp_path)
    assert result["reported_cost_usd"] == 0.2
    assert result["unreported_cost_reserve_usd"] == pytest.approx(0.2)
    assert result["accounted_cost_usd"] == pytest.approx(0.4)
    assert result["attempts"][0]["model_calls"] == 2
    assert result["attempts"][0]["accounting_basis"] == "completed_native_trace"

    # A separately reviewed untraced request is a reserve, never a reported
    # charge or another native call. Re-reading must not accumulate it.
    runner.dump(
        attempt / "untraced_requests.json",
        dict(
            trace_sha256=result["attempts"][0]["trace_sha256"],
            max_requests=3,
            basis="One failed SDK request with at most two retries outside interception",
        ),
    )
    for _ in range(2):
        updated = runner.ledger(tmp_path)
        assert updated["reported_cost_usd"] == 0.2
        assert updated["accounted_cost_usd"] == pytest.approx(1.0)
        assert updated["attempts"][0]["model_calls"] == 2
        assert updated["attempts"][0]["untraced_cost_reserve_usd"] == pytest.approx(0.6)
    trace_path.write_text(trace_path.read_text() + "\n")
    with pytest.raises(RuntimeError, match="review is stale"):
        runner.ledger(tmp_path)


def test_budget_price_ceiling_only_changes_spend_reserve(runner, tmp_path):
    model = dict(
        id="offline/test",
        specs=dict(context_window=100000, max_output_tokens=10000),
        pricing=dict(input_usd_per_mtok=1, output_usd_per_mtok=2),
        budget_pricing=dict(input_usd_per_mtok=2.5, output_usd_per_mtok=3),
    )
    config = runner.configuration(tmp_path, tmp_path, model, tmp_path / "bundle")
    assert config["env"]["taskset"]["task"]["spend"]["input_usd_per_mtok"] == 2.5
    assert config["sampling"]["max_tokens"] == 10000


def test_ledger_restores_omitted_native_usage_fields(runner, tmp_path):
    import json

    attempt = tmp_path / "attempts" / "native-no-dollar-cost"
    runner.dump(attempt / "attempt.json", dict(key="one", launched=True, status="error"))
    runner.dump(
        attempt / "eval.json",
        {
            "env": {
                "taskset": {
                    "task": {
                        "spend": dict(
                            input_usd_per_mtok=2,
                            output_usd_per_mtok=10,
                            context_window=100000,
                            max_response_tokens=10000,
                        )
                    }
                }
            }
        },
    )
    trace_path = attempt / "runs" / "run" / "traces.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps(
            {
                "traces": [
                    {
                        "calls": [
                            {"usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cached_input_tokens": 4000}},
                            {"usage": {"prompt_tokens": 500, "completion_tokens": 100}},
                            {"usage": None},
                        ],
                        "extra_usage": [{"prompt_tokens": 100, "completion_tokens": 50}],
                    }
                ]
            }
        )
    )
    result = runner.ledger(tmp_path)
    assert result["reported_cost_usd"] == 0
    # Preserve token estimates and the full-call reserve for truly missing usage.
    assert result["unreported_cost_reserve_usd"] == pytest.approx(0.012 + 0.002 + 0.3 + 0.0007)
    assert result["attempts"][0]["model_calls"] == 3


@pytest.mark.parametrize("parallel_models,failed_world", [(False, None), (False, "xv"), (True, None)])
def test_worlds_overlap_keep_isolation_and_finish_peers_before_pause(
    runner, tmp_path, monkeypatch, parallel_models, failed_world
):
    import json
    from threading import Barrier, Lock
    from types import SimpleNamespace

    root = tmp_path / "campaign"
    preparations = tmp_path / "preparations"
    models = ("offline/terra", "offline/sonnet")
    worlds = ("bf", "xv", "p4g2_044")

    class Bundle:
        def __init__(self, path):
            self.world = path.parent.name
            self.roster = SimpleNamespace(protocol="centered-pulse-v2")

        def check_runtime(self):
            pass

        def references(self):
            return {"world": self.world}

    monkeypatch.setattr(runner, "Bundle", Bundle)
    runner.dump(root / "provenance.json", dict(source_id="test", sources={}))
    runner.dump(
        root / "catalog.json",
        dict(
            data=[
                dict(
                    id=m,
                    specs=dict(context_window=10000, max_output_tokens=1000),
                    pricing=dict(input_usd_per_mtok=1, output_usd_per_mtok=2),
                )
                for m in models
            ]
        ),
    )
    for world in worlds:
        runner.dump(preparations / world / "native_validation.json", dict(ready=True, references={"world": world}))
    # A completed result above the former spending ceiling is kept; no rerun.
    prior = root / "attempts/offline--terra-bf-r1-attempt1"
    runner.dump(prior / "attempt.json", dict(key="offline--terra-bf-r1", status="complete", launched=True))
    runner.dump(prior / "artifacts/trace/spend_final.json", dict(accounted_cost_usd=160, reported_cost_usd=160))
    original_prior = (prior / "attempt.json").read_bytes()
    barriers = {models[0]: Barrier(2, timeout=5), models[1]: Barrier(3, timeout=5)}
    mixed_barrier = Barrier(3, timeout=5)
    total_peak = 0
    active = {m: 0 for m in models}
    peaks = {m: 0 for m in models}
    started = []
    finished = []
    lock = Lock()

    def run(command, **kwargs):
        nonlocal total_peak
        config = json.loads(Path(command[-1]).read_text())
        attempt = Path(command[-1]).parent
        record = json.loads((attempt / "attempt.json").read_text())
        model, world = record["model"], record["world"]
        assert config["env"]["taskset"]["task"]["spend"]["limit_usd"] is None
        assert config["env"]["taskset"]["task"]["output_root"] == str(attempt / "artifacts")
        with lock:
            if model == models[1] and not parallel_models:
                assert len(finished) == 2 + len([m for m, _ in finished if m == models[1]])
            started.append((model, world))
            ordinal = len(started)
            active[model] += 1
            peaks[model] = max(peaks[model], active[model])
            total_peak = max(total_peak, sum(active.values()))
        # No receipt exists yet. A racing global ledger read would reject the
        # half-started sibling, so require every world to enter before finishing.
        if parallel_models:
            if ordinal <= 3:
                mixed_barrier.wait()
        else:
            barriers[model].wait()
        failed = model == models[0] and world == failed_world
        trace = dict(
            id=world,
            ok=not failed,
            calls=[dict(usage=dict(cost=2))],
            extra_usage=[],
            stop_condition="error" if failed else "submitted",
            errors=[dict(type="HarnessError")] if failed else [],
            info=dict(r6=dict(primary_joint_energy=0.2)),
        )
        trace_path = attempt / "runs/rollout/traces.jsonl"
        trace_path.parent.mkdir(parents=True)
        trace_path.write_text(json.dumps(dict(traces=[trace])) + "\n")
        with lock:
            active[model] -= 1
            finished.append((model, world))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    args = SimpleNamespace(
        output=root,
        preparations=preparations,
        models=",".join(models),
        worlds=",".join(worlds),
        execute=True,
        rollouts=1,
        concurrent_worlds=3,
        max_new_runs=18,
        parallel_models=parallel_models,
    )
    runner.execute(args)
    assert (prior / "attempt.json").read_bytes() == original_prior
    if parallel_models:
        assert total_peak == 3
        assert {m for m, _ in started[:3]} == set(models)
    else:
        assert peaks[models[0]] == 2
        assert peaks[models[1]] == (3 if failed_world is None else 0)
    assert len(finished) == (5 if failed_world is None else 2)
    assert (models[0], "p4g2_044") in finished
    result = json.loads((root / "ledger.json").read_text())
    assert result["reported_cost_usd"] == 160 + 2 * len(finished)
    assert result["pause_ceiling_usd"] is None


def test_parallel_failure_holds_queue_but_finishes_active_peers(runner, monkeypatch):
    from threading import Barrier, Event

    barrier = Barrier(3, timeout=5)
    release_peers = Event()
    started, finished = [], []
    real_wait = runner.wait

    def worker(number):
        started.append(number)
        barrier.wait()
        if number == 0:
            finished.append(number)
            return False
        assert release_peers.wait(5)
        finished.append(number)
        return True

    def wait(*args, **kwargs):
        result = real_wait(*args, **kwargs)
        # The first completed job is the failure; let its active peers finish.
        release_peers.set()
        return result

    monkeypatch.setattr(runner, "wait", wait)
    assert not runner.run_parallel_jobs([(i,) for i in range(9)], worker, 3)
    assert set(started) == set(finished) == {0, 1, 2}


def test_invalidated_campaign_cannot_launch_even_with_execute(runner, tmp_path):
    from types import SimpleNamespace

    (tmp_path / "HOLD.json").write_text('{"reason":"prompt review"}')
    with pytest.raises(RuntimeError, match="Campaign is held"):
        runner.execute(SimpleNamespace(output=tmp_path, execute=True))


def test_freeze_archives_installed_environment_and_records_git_pin(tmp_path, monkeypatch):
    import hashlib
    import importlib.metadata
    import json
    import zipfile

    path = Path(__file__).resolve().parents[1] / "scripts/physim/freeze_campaign.py"
    spec = importlib.util.spec_from_file_location("freeze_campaign_test", path)
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)
    source = tmp_path / "research"
    source.mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        (source / name).write_text("offline fixture")
    monkeypatch.setattr(freeze, "ROOT", source)

    def command(args, **kwargs):
        if args[0] == "docker":
            return json.dumps([{"Id": "sha256:offline-image"}]).encode()
        assert args[:2] == ["git", "rev-parse"]
        return "a" * 40

    monkeypatch.setattr(freeze.subprocess, "check_output", command)
    output = tmp_path / "snapshot"
    freeze.freeze(output)
    record = json.loads((output / "provenance.json").read_text())
    distribution = importlib.metadata.distribution("physim")
    code = distribution.locate_file("physim/taskset.py").read_bytes()
    assert record["environment_sources"]["physim/taskset.py"] == hashlib.sha256(code).hexdigest()
    assert record["environment_install"]["vcs_info"]["commit_id"]
    with zipfile.ZipFile(output / record["archive"]) as archive:
        assert archive.read("installed/physim/taskset.py") == code
    assert not any(name.startswith("environments/") for name in record["sources"])


def test_changed_installed_environment_rejects_a_frozen_campaign(runner, tmp_path):
    from types import SimpleNamespace

    runner.dump(tmp_path / "catalog.json", {"data": []})
    runner.dump(
        tmp_path / "provenance.json",
        {
            "sources": {},
            "environment_sources": {"physim/taskset.py": "0" * 64},
        },
    )
    with pytest.raises(RuntimeError, match="Installed environment changed"):
        runner.execute(SimpleNamespace(output=tmp_path, execute=True))

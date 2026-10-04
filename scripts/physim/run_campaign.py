"""Concurrent-world, spend-accounted campaigns using Verifiers eval and task hooks.

Without --execute this only resolves configurations. Credentials stay in the
native Verifiers client; no token is read, written, or passed on a command line.
The native harnesses come from the pinned Verifiers dependency.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from physim.bundles import Bundle
from physim.runtime_sandbox import PUBLIC_IMAGE
from physim_r6.scaling import SpendConfig, spend_accounting
from verifiers.v1.configs.cli.eval import EvalConfig
from verifiers.v1.types import Usage

ROOT = Path(__file__).resolve().parents[2]
TARGET_USD = 50.0


def retryable_provider_error(error):
    status = error.get("status_code")
    return (
        error.get("type") == "ProviderError"
        and isinstance(status, int)
        and (status in {408, 409, 429} or 500 <= status < 600)
    )


def pause_before_launch(accounted, launched, max_new_runs):
    # Spending decisions belong to the user. Only the selected run bound
    # limits queue admission; measured/reserved cost never stops a rollout.
    return launched >= max_new_runs


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def ledger(root):
    rows = []
    for attempt in sorted((root / "attempts").glob("*/attempt.json")):
        record = json.loads(attempt.read_text())
        receipts = []
        for artifact in sorted((attempt.parent / "artifacts").glob("*")):
            final, current = artifact / "spend_final.json", artifact / "spend_state.json"
            if final.exists() or current.exists():
                receipts.append(json.loads((final if final.exists() else current).read_text()))
        # A terminal provider exception bypasses task finalization. Recompute
        # from the saved native trace so the last failed call is also reserved.
        trace_paths = list((attempt.parent / "runs").glob("*/traces.jsonl"))
        config_path = attempt.parent / "eval.json"
        evidence = {}
        if record.get("status") != "running" and trace_paths and config_path.exists():
            trace = completed_trace(attempt.parent)
            if trace is None or len(trace_paths) != 1:
                raise RuntimeError(f"Cannot reconcile terminal trace for {attempt.parent.name}")
            config = json.loads(config_path.read_text())["env"]["taskset"]["task"]["spend"]

            def usage(value):
                # Serialized native traces omit optional null fields (notably
                # cost on non-OpenAI routes). Restore the native model defaults.
                return (
                    Usage.model_validate({"prompt_tokens": 0, "completion_tokens": 0, **value})
                    if value is not None
                    else None
                )

            native = SimpleNamespace(
                calls=[SimpleNamespace(usage=usage(call.get("usage"))) for call in trace.get("calls", [])],
                extra_usage=[usage(value) for value in trace.get("extra_usage", [])],
            )
            receipts = [spend_accounting(native, SpendConfig.model_validate(config))]
            evidence = dict(
                accounting_basis="completed_native_trace",
                trace_sha256=hashlib.sha256(trace_paths[0].read_bytes()).hexdigest(),
                config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
            )
        # Unknown spend must be reconciled before any subsequent paid run.
        if record.get("launched") and not receipts and record.get("status") != "zero_call_failure":
            raise RuntimeError(f"Missing spend receipt for {attempt.parent.name}; inspect before continuing")
        # Reviewed requests that failed outside native interception have no
        # call record. Keep their upper bound separate from measured charges.
        supplement = attempt.parent / "untraced_requests.json"
        untraced_reserve = 0.0
        if supplement.exists():
            review = json.loads(supplement.read_text())
            if review["trace_sha256"] != evidence.get("trace_sha256"):
                raise RuntimeError(f"Untraced-request review is stale: {attempt.parent.name}")
            count = review["max_requests"]
            if not isinstance(count, int) or isinstance(count, bool) or count < 1 or not review.get("basis"):
                raise ValueError("Untraced requests require a positive bound and review evidence")
            untraced_reserve = count * SpendConfig.model_validate(config).next_call_reserve
            if not math.isfinite(untraced_reserve):
                raise ValueError("Invalid untraced-request reserve")
            evidence.update(untraced_requests_upper_bound=count, untraced_cost_reserve_usd=untraced_reserve)
        rows.append(
            dict(
                **record,
                **evidence,
                accounted_cost_usd=sum(r["accounted_cost_usd"] for r in receipts) + untraced_reserve,
                reported_cost_usd=sum(r["reported_cost_usd"] for r in receipts),
                unreported_cost_reserve_usd=sum(r["accounted_cost_usd"] - r["reported_cost_usd"] for r in receipts)
                + untraced_reserve,
                model_calls=sum(r.get("model_calls", 0) for r in receipts),
            )
        )
    return dict(
        target_usd=TARGET_USD,
        automatic_target_pause=False,
        pause_ceiling_usd=None,
        budget_policy="User controls spending; accounting only, no automatic dollar stops",
        attempts=rows,
        accounted_cost_usd=sum(r["accounted_cost_usd"] for r in rows),
        reported_cost_usd=sum(r["reported_cost_usd"] for r in rows),
        unreported_cost_reserve_usd=sum(r["unreported_cost_reserve_usd"] for r in rows),
    )


def configuration(root, attempt_dir, model, bundle):
    specs = model.get("specs") or {}
    # Optional documented ceilings affect missing-cost reserves only; actual
    # provider charges remain authoritative for measured cost.
    pricing = model.get("budget_pricing") or model["pricing"]
    # max_tokens reserves output within the context window on some routes.
    # The advertised maximum can otherwise leave almost no room for history
    # (Kimi: 235,929 output out of 262,144 total). Preserve at least 3/4 for
    # input, while retaining native finish-reason audits for this response cap.
    maximum = min(specs["max_output_tokens"], specs["context_window"] // 4)
    sampling = {"max_tokens": maximum}
    efforts = (model.get("reasoning") or {}).get("supported_efforts", [])
    if efforts:
        sampling["reasoning_effort"] = next(
            level for level in ("max", "xhigh", "high", "medium", "low") if level in efforts
        )
    else:
        sampling["extra_body"] = {"reasoning": {"enabled": True}}
    # No total turn/input/output-token or investigation cap. Provider context
    # is a model property; the explicit single-response allowance leaves room
    # for the conversation and is audited for truncation.
    data = dict(
        model=model["id"],
        select={"limit": 1},
        num_rollouts=1,
        max_concurrent=1,
        push=False,
        rich=None,
        output_dir=str(attempt_dir / "runs"),
        run={"name": "rollout"},
        sampling=sampling,
        env={
            "taskset": {
                "id": "physim_r6_scaling",
                "task": {
                    "output_root": str(attempt_dir / "artifacts"),
                    "agent_image": PUBLIC_IMAGE,
                    "tools": {
                        "bundle": str(bundle),
                        "predictor_runtime": {"type": "docker", "image": PUBLIC_IMAGE, "allow": []},
                        "max_experiments": None,
                        "max_total_tu": None,
                        "max_validation_attempts": None,
                        "max_submission_attempts": None,
                        "predictor_limits": {
                            "cpu_seconds": 3600,
                            "wall_seconds": 3600,
                            "cpus": 4,
                            "memory_gib": 8,
                            "artifact_mib": 512,
                            "file_mib": 256,
                        },
                    },
                    "spend": {
                        "limit_usd": None,
                        "input_usd_per_mtok": pricing["input_usd_per_mtok"],
                        "output_usd_per_mtok": pricing["output_usd_per_mtok"],
                        "cache_read_usd_per_mtok": pricing.get("cache_read_usd_per_mtok"),
                        "cache_write_usd_per_mtok": pricing.get("cache_write_usd_per_mtok"),
                        "context_window": specs["context_window"],
                        "max_response_tokens": maximum,
                    },
                },
            },
            "agent": {
                "max_turns": None,
                "max_input_tokens": None,
                "max_output_tokens": None,
                "max_total_tokens": None,
                "sampling": sampling,
                "timeout": {"setup": 900, "rollout": 604800, "finalize": 28800, "scoring": 86400},
                "harness": {"id": "bash", "edit": True, "search": False, "tool_timeout": 28800},
                "runtime": {
                    "type": "docker",
                    "image": PUBLIC_IMAGE,
                    "workdir": "/workspace",
                    "cpu": 4,
                    "memory": 8,
                    "allow": [],
                },
                "retries": {"max_retries": 0},
            },
            "retries": {"max_retries": 0},
        },
    )
    harness_file = root / "prime_agent.json"
    if harness_file.exists():
        options = json.loads(harness_file.read_text())
        sampling.setdefault("extra_body", {})["usage"] = {"include": True}
        agent = data["env"]["agent"]
        task = data["env"]["taskset"]["task"]
        transport = (
            "anthropic_messages"
            if model["id"].startswith("anthropic/")
            else "responses"
            if model["id"].startswith("openai/")
            else "chat_completions"
        )
        agent["harness"] = {
            "id": "prime-agent",
            "context_window": specs["context_window"],
            "autonomous": True,
            "compaction": {"reserve_tokens": maximum + 4096, "keep_recent_tokens": 12000},
        }
        agent["runtime"]["image"] = task["agent_image"] = options.get("image", PUBLIC_IMAGE)
        task["coding_interface"] = "ipython"
        # Native Anthropic reports token buckets without a dollar charge.
        # Cache creation can cost twice the base input rate with the one-hour
        # cache used here. This ceiling is a reserve, never labelled as billed.
        if transport == "anthropic_messages":
            task["spend"]["cache_write_usd_per_mtok"] = 2 * pricing["input_usd_per_mtok"]
    return EvalConfig.model_validate(data).model_dump(mode="json")


def completed_trace(attempt):
    paths = list((attempt / "runs").glob("*/traces.jsonl"))
    if len(paths) != 1:
        return None
    episodes = [json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    return episodes[-1]["traces"][-1] if episodes and episodes[-1].get("traces") else None


def run_parallel_jobs(jobs, worker, concurrency):
    """Refill a bounded queue; a failed job holds pending work, never active peers."""
    pending = iter(jobs)
    healthy = True
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        active = set()

        def fill():
            while len(active) < concurrency:
                job = next(pending, None)
                if job is None:
                    break
                active.add(pool.submit(worker, *job))

        fill()
        while active:
            done, active = wait(active, return_when=FIRST_COMPLETED)
            outcomes = [future.result() for future in done]
            healthy = healthy and all(outcomes)
            if healthy:
                fill()
    return healthy


def execute(args):
    root = args.output.resolve()
    if (root / "HOLD.json").exists():
        raise RuntimeError("Campaign is held: review HOLD.json; use a new campaign for a changed evaluation condition")
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".campaign.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    models = {r["id"]: r for r in json.loads((root / "catalog.json").read_text())["data"]}
    provenance = None
    if args.execute:
        provenance = json.loads((root / "provenance.json").read_text())
        for relative, expected in provenance["sources"].items():
            if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Source changed after the campaign snapshot: {relative}; freeze a new snapshot")
        distribution = importlib.metadata.distribution("physim")
        for relative, expected in provenance.get("environment_sources", {}).items():
            if hashlib.sha256(distribution.locate_file(relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError(
                    f"Installed environment changed after the campaign snapshot: {relative}; freeze a new snapshot"
                )
    bundles = {w: (args.preparations / w / "bundle").resolve() for w in args.worlds.split(",")}
    for world, path in bundles.items():
        bundle = Bundle(path)
        bundle.check_runtime()
        if bundle.roster.protocol != "centered-pulse-v2":
            raise ValueError(f"{world} uses the old apparatus")
        validation = json.loads((path.parent / "native_validation.json").read_text())
        if not validation["ready"] or validation["references"] != bundle.references():
            raise ValueError(f"{world} has no matching completed validation")
    launched = 0
    launch_lock = Lock()

    def run_world(model_id, repetition, world, bundle, previous):
        nonlocal launched
        model = models[model_id]
        key = f"{model_id.replace('/', '--')}-{world}-r{repetition + 1}"
        if any(row["status"] == "complete" for row in previous):
            return True
        for retry in range(len(previous), 3):
            with launch_lock:
                if pause_before_launch(0, launched, args.max_new_runs):
                    print(f"Selected run bound reached before {key}; active worlds will finish", flush=True)
                    return False
                if args.execute:
                    launched += 1
            attempt = root / "attempts" / f"{key}-attempt{retry + 1}"
            if attempt.exists():
                raise RuntimeError(f"Inspect unfinished attempt before continuing: {attempt}")
            config = configuration(root, attempt, model, bundle)
            if not args.execute:
                dump(root / "planned_configs" / f"{key}.json", config)
                return True
            attempt.mkdir(parents=True)
            dump(attempt / "eval.json", config)
            dump(attempt / "provenance.json", provenance)
            record = dict(
                key=key,
                model=model_id,
                world=world,
                repetition=repetition + 1,
                attempt=retry + 1,
                status="running",
                launched=True,
                started_utc=datetime.now(timezone.utc).isoformat(),
                source_id=provenance["source_id"],
                bundle_references=Bundle(bundle).references(),
                budget_policy="User controls spending; accounting only, no automatic dollar stops",
            )
            dump(attempt / "attempt.json", record)
            print(
                f"Starting {key}, attempt {retry + 1}; no automatic dollar limit",
                flush=True,
            )
            with (attempt / "eval.log").open("w") as log:
                run = subprocess.run(
                    [
                        sys.executable,
                        str(
                            Path(__file__).with_name(
                                "prime_agent_eval.py"
                                if (root / "prime_agent.json").exists()
                                else "campaign_diagnostics.py"
                            )
                        ),
                        "--diagnostics",
                        str(attempt / "diagnostics"),
                        "@",
                        str(attempt / "eval.json"),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=ROOT,
                )
            trace = completed_trace(attempt)
            if trace is None:
                record.update(status="needs_inspection", exit_code=run.returncode)
            else:
                info = trace.get("info", {}).get("r6", {})
                errors = trace.get("errors", [])
                record.update(
                    status="complete" if trace.get("ok") else "error",
                    exit_code=run.returncode,
                    trace_id=trace["id"],
                    stop_condition=trace.get("stop_condition"),
                    errors=errors,
                    energy=info.get("primary_joint_energy"),
                    rewards=trace.get("rewards"),
                    limit_audit=info.get("limit_audit"),
                )
                if not trace.get("calls") and not trace.get("extra_usage"):
                    record["status"] = "zero_call_failure"
                if trace.get("stop_condition") in {
                    "dollar_budget",
                    "context_length",
                    "max_turns",
                    "max_input_tokens",
                    "max_output_tokens",
                    "max_total_tokens",
                }:
                    record["status"] = "limited"
                if info.get("limit_audit", {}).get("length_finished_calls"):
                    record["status"] = "limited"
                failures = info.get("grade", {}).get("failures", [])
                artifact_path = Path(info.get("artifact_directory", attempt / "artifacts"))
                state_path = artifact_path / "laboratory_state.json"
                if state_path.exists():
                    for check in json.loads(state_path.read_text()).get("checks", []):
                        failures += check.get("validation", {}).get("checks", [])
                if any(f.get("error_type") == "ExecutionLimitError" for f in failures):
                    record["status"] = "limited"
            dump(attempt / "attempt.json", record)
            print(f"Finished {key}: {record['status']}", flush=True)
            if record["status"] == "complete":
                return True
            # In-place SDK retries run first. Only transient provider faults
            # permit an automatic whole-trajectory replacement, never low scores.
            errors = record.get("errors", [])
            if not errors or not retryable_provider_error(errors[-1]):
                print(f"{key} needs inspection; other active worlds will finish", flush=True)
                return False
        print(f"{key} exhausted its attempt allowance", flush=True)
        return False

    if getattr(args, "parallel_models", False):
        # One immutable ledger snapshot supplies attempt history. Workers write
        # isolated directories; reconcile globally only after they all finish.
        before = ledger(root)
        dump(root / "ledger.json", before)
        jobs = []
        for repetition in range(args.rollouts):
            for world, bundle in bundles.items():
                for model_id in args.models.split(","):
                    key = f"{model_id.replace('/', '--')}-{world}-r{repetition + 1}"
                    previous = [row for row in before["attempts"] if row["key"] == key]
                    jobs.append((model_id, repetition, world, bundle, previous))
        healthy = run_parallel_jobs(jobs, run_world, args.concurrent_worlds)
        after = ledger(root)
        dump(root / "ledger.json", after)
        print(f"Parallel stage finished; campaign accounted ${after['accounted_cost_usd']:.4f}", flush=True)
        if not healthy:
            print("Pending runs held for limit/infrastructure inspection; active runs finished", flush=True)
        return

    for model_id in args.models.split(","):
        for repetition in range(args.rollouts):
            # Reconcile only between waves, after all workers have finished.
            # Active workers write separate attempt directories and receipts;
            # no thread reads another world's half-started receipt or overwrites
            # a shared ledger. The progress logger reads the live per-run files.
            before = ledger(root)
            dump(root / "ledger.json", before)
            jobs = []
            for world, bundle in bundles.items():
                key = f"{model_id.replace('/', '--')}-{world}-r{repetition + 1}"
                previous = [row for row in before["attempts"] if row["key"] == key]
                jobs.append((model_id, repetition, world, bundle, previous))
            with ThreadPoolExecutor(max_workers=args.concurrent_worlds) as pool:
                futures = [pool.submit(run_world, *job) for job in jobs]
                # Collect every outcome: one failed world must not terminate
                # already-running worlds and waste their experiments.
                outcomes = [future.result() for future in futures]
            after = ledger(root)
            dump(root / "ledger.json", after)
            print(f"Wave finished; campaign accounted ${after['accounted_cost_usd']:.4f}", flush=True)
            if not all(outcomes):
                print("Paused before the next model for limit/infrastructure inspection", flush=True)
                return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/evaluation-campaign-20260916")
    parser.add_argument("--preparations", type=Path, default=ROOT / "outputs/eval-preparation-20260916")
    parser.add_argument("--models", required=True)
    parser.add_argument("--worlds", default="bf,xv,p4g2_044")
    parser.add_argument("--rollouts", type=int, default=1)
    parser.add_argument("--max-new-runs", type=int, default=3)
    parser.add_argument("--concurrent-worlds", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--parallel-models", action="store_true", help="Share the concurrency limit across models")
    parser.add_argument("--execute", action="store_true")
    execute(parser.parse_args())

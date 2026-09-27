"""Offline checks for the R6 task's native Verifiers integration."""

import ast
import asyncio
import hashlib
import json
import tempfile
import tomllib
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verifiers.v1 as vf
from physim import taskset as T
from verifiers.v1.utils.loaders import harness_config_type, load_harness, load_taskset


class NativeTaskTests(unittest.TestCase):
    def setUp(self):
        self.bundle_patch = patch.object(T, "required_bundle", return_value=None)
        self.bundle_patch.start()
        self.addCleanup(self.bundle_patch.stop)

    def test_missing_bundle_fails_before_model_execution(self):
        self.bundle_patch.stop()
        config_path = Path(__file__).resolve().parents[3] / "configs/physim/eval.toml"
        eval_config = tomllib.loads(config_path.read_text())
        configs = [T.R6Config(id="physim"), T.R6Config(**eval_config["env"]["taskset"])]
        for config in configs:
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, "No world selected") as error:
                next(iter(load_taskset(config)))
            self.assertIn("no default world", str(error.exception))
            self.assertIn("does not automatically select eval-ready registry entries", str(error.exception))
            self.assertIn("--env.taskset.task.tools.bundle", str(error.exception))

    def test_remote_bundle_requires_immutable_unambiguous_selection(self):
        source = dict(repo="owner/worlds", revision="a" * 40, path="bundles/world/hash")
        config = T.R6ToolsConfig(bundle_source=source)
        self.assertIsNone(config.bundle)
        with self.assertRaisesRegex(ValueError, "not both"):
            T.R6ToolsConfig(bundle="local", bundle_source=source)
        with self.assertRaises(ValueError):
            T.R6ToolsConfig(bundle_source=dict(source, revision="main"))

    def test_remote_bundle_preserves_source_for_subprocess_and_offline_reuse(self):
        self.bundle_patch.stop()
        source = dict(repo="owner/worlds", revision="a" * 40, path="bundles/world/hash", offline=True)
        config = T.R6ToolsConfig(bundle_source=source)
        with patch("physim.hub.fetch_bundle", return_value=Path("cached")) as fetch, patch.object(T, "Bundle"):
            T.required_bundle(config)
            fetch.assert_called_once_with(**config.bundle_source.model_dump(), profile="evaluation")
        restored = T.R6ToolsConfig.model_validate_json(config.model_dump_json())
        self.assertIsNone(restored.bundle)
        self.assertEqual(restored.bundle_source, config.bundle_source)

    def test_completed_run_without_valid_predictor_earns_zero(self):
        for checks, reason in (([], "no_predictor"), ([dict(snapshot={"files": []})], "invalid_predictor")):
            with self.subTest(reason=reason):
                trace = SimpleNamespace(state=T.R6State(checks=checks), info={})
                task = SimpleNamespace(config=T.R6TaskConfig())
                self.assertEqual(asyncio.run(T.R6Task.prediction_reward(task, trace)), 0.0)
                self.assertEqual(trace.info["r6"]["score_reason"], reason)
                self.assertIsNone(trace.info["r6"]["primary_joint_energy"])

    def test_checkpoint_reads_only_verified_public_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "validate_01"
            artifact.mkdir()
            obs = root / "observations"
            obs.mkdir()
            (artifact / "predictor.py").write_text("model's predictor")
            (artifact / "unlisted_secret").write_text("must not copy")
            (obs / "experiment_001.npz").write_bytes(b"public data")
            state = dict(
                prompt_condition=T.PROMPT_CONDITION,
                reward_precision=T.DEFAULT_PRECISION,
                checks=[
                    dict(
                        path="validate_01",
                        validation=dict(ok=True),
                        snapshot=dict(
                            files=[dict(path="predictor.py", sha256=T.E.file_digest(artifact / "predictor.py"))]
                        ),
                    )
                ],
                experiments=[dict(file="experiment_001.npz", sha256=T.E.file_digest(obs / "experiment_001.npz"))],
                usage=dict(experiments=1, charged_tu=12),
                origin=dict(private="hidden"),
            )
            (root / "laboratory_state.json").write_text(json.dumps(state))
            metadata, files, observations = T.load_checkpoint(artifact)
            self.assertEqual(files, [("predictor.py", b"model's predictor")])
            self.assertEqual(observations, [("experiment_001.npz", b"public data")])
            self.assertEqual(metadata["inherited_charged_tu"], 12)
            self.assertNotIn("hidden", json.dumps(metadata))
            (artifact / "predictor.py").write_text("tampered")
            with self.assertRaisesRegex(vf.TaskError, "hash mismatch"):
                T.load_checkpoint(artifact)
            state["checks"][0]["validation"]["ok"] = False
            (root / "laboratory_state.json").write_text(json.dumps(state))
            with self.assertRaisesRegex(vf.TaskError, "previously validated"):
                T.load_checkpoint(artifact)

    def test_checkpoint_rejects_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").write_bytes(b"data")
            (root / "link").symlink_to(root / "data")
            digest = hashlib.sha256(b"data").hexdigest()
            for name in ("../data", "/data", "link", ".vf-state/data"):
                with self.assertRaises(vf.TaskError):
                    T._checkpoint_file(root, name, digest)

    def test_checkpoint_protocol_exposes_recovery_condition(self):
        task = next(
            iter(
                load_taskset(
                    T.R6Config(id="physim_r6", task=T.R6TaskConfig(checkpoint_artifact=Path("/tmp/prior/validate_01")))
                )
            )
        )
        self.assertIn("-checkpoint-", task.data.protocol)
        self.assertIn("Exploration is closed", task.data.system_prompt)
        self.assertNotIn("/tmp/prior", task.data.system_prompt)

    def test_native_loader_and_stock_harness(self):
        taskset = load_taskset(T.R6Config(id="physim_r6"))
        task = next(iter(taskset))
        self.assertIsInstance(task, vf.Task)
        self.assertEqual(
            type(load_harness(vf.HarnessConfig(id="bash"))).__module__, "verifiers.v1.harnesses.bash.harness"
        )
        self.assertNotIn("run", T.R6Task.__dict__)
        self.assertNotIn("rollout", T.R6Task.__dict__)
        self.assertEqual(task.data.network_allow, [])
        self.assertEqual(task.data.workdir, "/workspace")

    def test_long_run_budgets_reach_verifiers_and_experiment_service(self):
        config_path = Path(__file__).resolve().parents[3] / "configs/physim/eval.toml"
        for extended in (False, True):
            with self.subTest(extended=extended):
                config = tomllib.loads(config_path.read_text())
                task_config = T.R6Config(**config["env"]["taskset"])
                agent_config = vf.AgentConfig(model="offline-config-check", **config["env"]["agent"])
                if extended:
                    task_config.task.tools.max_experiments = 5000
                    task_config.task.tools.max_total_tu = 250000
                    task_config.task.tools.max_validation_attempts = 512
                    task_config.task.tools.max_submission_attempts = 512
                    # Revalidate so larger limits must survive the CLI/config schema.
                    task_config = T.R6Config.model_validate(task_config.model_dump())
                    agent_config.timeout.rollout = 172800
                    agent_config.max_turns = 4096
                    agent_config.max_output_tokens = 4194304
                task = next(iter(load_taskset(task_config)))
                agent = vf.make_agent(agent_config)
                # Resolve native execution parameters without starting a model or Docker.
                resolved = agent._rollout_params(task, None, {})
                self.assertEqual(resolved["timeouts"].agent, 172800 if extended else 86400)
                self.assertEqual(resolved["limits"].max_turns, 4096 if extended else 1024)
                self.assertEqual(resolved["runtime_config"].cpu, 4)
                self.assertEqual(resolved["runtime_config"].memory, 8)
                limits = task_config.task.tools
                service = T.ExperimentService(
                    None, max_experiments=limits.max_experiments, max_total_tu=limits.max_total_tu
                )
                self.assertEqual(service.usage()["max_experiments"], limits.max_experiments)
                self.assertEqual(service.usage()["max_total_tu"], limits.max_total_tu)
                self.assertIn(f"{limits.max_experiments} experiments", task.data.system_prompt)

    def test_public_interface_examples_unchanged(self):
        root = Path(__file__).resolve().parents[3]
        old = ast.parse(
            (root / "handoff/repo_cleanup/original_source/environments/physim/physim_r6/evaluation.py").read_text()
        )
        from physim import evaluation

        # Preserve the exact public requests for every historical bundle.
        function = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "public_validation_cases")
        namespace = {"deepcopy": deepcopy}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "frozen-public-cases", "exec"), namespace)
        self.assertEqual(namespace["public_validation_cases"](), evaluation.public_validation_cases("fixed-source-v1"))

    def test_ipython_uses_stock_rlm_and_changes_only_interface_description(self):
        config = harness_config_type("rlm")(id="rlm", max_depth=0, summarize_at_tokens=16000)
        self.assertEqual(type(load_harness(config)).__module__, "verifiers.v1.harnesses.rlm.harness")
        task = next(
            iter(
                load_taskset(
                    T.R6Config(id="physim_r6", task=T.R6TaskConfig(coding_interface="ipython", agent_image="rlm-test"))
                )
            )
        )
        self.assertEqual(task.data.image, "rlm-test")
        self.assertEqual(task.data.protocol, f"r6-verifiers-v1-ipython-1-{T.PROMPT_CONDITION}-k-2")
        self.assertIn("persistent IPython", task.data.system_prompt)
        self.assertIn("laboratory_validate", task.data.system_prompt)
        self.assertEqual(task.data.network_allow, [])

    def test_public_prompt_and_fixtures(self):
        prompt = T.public_prompt(T.R6ToolsConfig())
        self.assertIn('data["request"].item()', prompt)
        self.assertIn("laboratory_validate", prompt)
        self.assertNotIn("p4g2_044", prompt)
        self.assertNotIn("use the python tool", prompt.lower())
        self.assertEqual(len(T.E.public_validation_cases()), 7)

    def test_prompt_variant_has_distinct_protocol_and_same_science(self):
        base = next(iter(load_taskset(T.R6Config(id="physim_r6"))))
        guided = next(iter(load_taskset(T.R6Config(id="physim_r6", prompt="Save a file first."))))
        self.assertNotEqual(base.data.protocol, guided.data.protocol)
        self.assertEqual(guided.data.prompt, "Save a file first.")
        self.assertEqual(base.data.system_prompt, guided.data.system_prompt)
        self.assertEqual(base.data.image, guided.data.image)
        self.assertEqual(base.config.tools, guided.config.tools)

    def test_reject_untrusted_tool_placement(self):
        for tools in (
            T.R6ToolsConfig(colocated=True),
            T.R6ToolsConfig(url="https://example.com"),
            T.R6ToolsConfig(runtime=vf.DockerConfig()),
        ):
            with self.assertRaises(ValueError):
                T.R6Task.toolsets(T.R6TaskConfig(tools=tools))

    def test_runtime_identity_cannot_be_a_shell_expression(self):
        for value in ("", "--privileged", "123456789abc; touch x", "../../host"):
            with self.assertRaises(vf.ToolsetError):
                T._container(T.R6State(container_id=value))

    def test_check_then_repair_then_submit_freezes_separate_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            state = T.R6State(container_id="abc012345678", output=directory)
            captured = []
            version = {"text": "bad"}

            def snapshot(state, target, limits):
                target.mkdir()
                (target / "predictor.py").write_text(version["text"])
                captured.append(target)
                return {"files": [{"path": "predictor.py"}]}

            def validate(target, observations, *, roster, execution_limits):
                self.assertEqual(roster.n_ports, 12)
                self.assertEqual(execution_limits, T.R6ToolsConfig().predictor_limits)
                return {"ok": (target / "predictor.py").read_text() == "good"}

            with patch.object(T, "_snapshot", snapshot), patch.object(T.E, "validate_predictor", validate):
                a = T._check(state, T.R6ToolsConfig(), final=False)
                self.assertFalse(a["ok"])
                version["text"] = "good"
                b = T._check(state, T.R6ToolsConfig(), final=False)
                self.assertTrue(b["ok"])
                self.assertFalse(state.submitted)
                c = T._check(state, T.R6ToolsConfig(), final=True)
                self.assertTrue(c["accepted"])
                self.assertEqual(Path(state.artifact).name, "submit_01")
                self.assertEqual((captured[0] / "predictor.py").read_text(), "bad")
                T._check(state, T.R6ToolsConfig(), final=True)
                self.assertEqual(len(captured), 3)

    def test_validator_startup_error_is_not_contract_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            state = T.R6State(container_id="abc012345678", output=directory)
            with (
                patch.object(T, "_snapshot", return_value={"files": []}),
                patch.object(T.E, "validate_predictor", side_effect=T.E.SandboxError("daemon unavailable")),
            ):
                with self.assertRaises(T.E.SandboxError):
                    T._check(state, T.R6ToolsConfig(), final=True)
                self.assertFalse(state.submitted)


class StateConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bundle_patch = patch.object(T, "required_bundle", return_value=None)
        self.bundle_patch.start()
        self.addCleanup(self.bundle_patch.stop)

    async def test_checkpoint_has_no_new_experiments_or_private_service(self):
        server = T.LaboratoryTools(T.R6ToolsConfig())
        server.state.exploration_closed = True
        server.state.usage = dict(experiments=9, charged_tu=52)
        result = json.loads(await server.experiment(actions=[], queries=[]))
        self.assertIn("exploration closed", result["error"])
        self.assertEqual(result["usage"]["experiments"], 9)
        self.assertEqual(server.state.experiments, [])
        self.assertIsNone(server.service)

    async def test_rlm_can_finish_after_immutable_submission(self):
        from types import SimpleNamespace

        trace = SimpleNamespace(state=T.R6State(submitted=True))
        shell = next(iter(load_taskset(T.R6Config(id="physim_r6"))))
        ipython = next(iter(load_taskset(T.R6Config(id="physim_r6", task=T.R6TaskConfig(coding_interface="ipython")))))
        self.assertTrue(await shell.submitted(trace))
        self.assertFalse(await ipython.submitted(trace))
        # Stock VF selects the stop-hook boundary from its type annotation.
        from verifiers.v1.session import hook_boundary

        self.assertIs(hook_boundary(shell.submitted, allow_trace=True), T.vf.Trace)
        server = T.LaboratoryTools(T.R6ToolsConfig())
        server.state.submitted = True
        result = json.loads(await server.experiment(actions=[], queries=[]))
        self.assertEqual(result["error"], "predictor already submitted")
        self.assertIsNone(server.service)

    async def test_parallel_tools_serialize_pull_mutate_push(self):
        server = T.LaboratoryTools(T.R6ToolsConfig())
        saved = T.R6State()

        async def pull():
            return saved.model_copy(deep=True)

        async def push(before):
            nonlocal saved
            saved = server.state.model_copy(deep=True)

        async def call(label):
            server.state.checks.append({"kind": label})
            await asyncio.sleep(0.01)
            return label

        server._pull_state, server._push_state = pull, push
        wrapped = server._with_state(call)
        self.assertEqual(await asyncio.gather(wrapped("a"), wrapped("b")), ["a", "b"])
        self.assertEqual([c["kind"] for c in saved.checks], ["a", "b"])


if __name__ == "__main__":
    unittest.main()

"""Toy-only R6 evaluation gates: no native physics or model/network calls.

Run: uv run python scripts/physim/validation/test_blob_round6_eval.py
Optional --json-out writes an auditable test report.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
from physim.legacy_v1 import blobround6_eval as E

ROSTER = E.PublicRoster(1, (1,))


def case(times=None):
    return dict(id="toy-001", actions=[], queries=[dict(sensor="device0", t=[0, 1] if times is None else times)])


def groups(times=2):
    return [
        dict(
            id="trajectory",
            selectors=[dict(query=0, time_index=i, port=0, slot=0) for i in range(times)],
            scales=[1.0] * times,
            unit="toy field value",
        )
    ]


def samples(rows):
    array = np.asarray(rows, dtype=float)
    return {"samples": [array.reshape(array.shape + (1, 1))]}


def score(pred, truth, *, request=None, score_groups=None, **kwargs):
    return E.score_case(
        case() if request is None else request,
        pred,
        truth,
        groups=groups() if score_groups is None else score_groups,
        n_samples=len(pred["samples"][0]),
        n_truth=len(truth["samples"][0]),
        roster=ROSTER,
        **kwargs,
    )


class ValidationTests(unittest.TestCase):
    def test_shape_dtype_and_nonfinite_rejection(self):
        shapes = ((2, 1, 1),)
        bad = [
            np.ones((2, 1, 1)),
            np.ones((2, 2, 1, 2)),
            np.ones((2, 2, 1, 1), dtype=bool),
            np.ones((2, 2, 1, 1), dtype=complex),
            np.ones((2, 2, 1, 1), dtype=object),
            np.full((2, 2, 1, 1), np.nan),
            np.full((2, 2, 1, 1), np.inf),
            "array",
            None,
        ]
        for item in bad:
            with self.subTest(item=str(type(item))):
                with self.assertRaises(E.EvaluationError):
                    E.validate_samples({"samples": [item]}, shapes, 2)

    def test_exact_payload_and_query_count(self):
        for obj in ({}, {"samples": []}, {"samples": ()}, {"samples": [np.ones((2, 2, 1, 1))], "seed": 5}):
            with self.subTest(obj=list(obj)):
                with self.assertRaises(E.EvaluationError):
                    E.validate_samples(obj, ((2, 1, 1),), 2)

    def test_json_lists_strict_without_coercing_bool_string_or_ragged(self):
        good = samples([[1, 2], [3, 4]])["samples"][0].tolist()
        result = E.validate_samples({"samples": [good]}, ((2, 1, 1),), 2)
        np.testing.assert_array_equal(result[0], np.asarray(good))
        for bad in (True, "2", 1e309, 10**400):
            modified = deepcopy(good)
            modified[0][0][0][0] = bad
            with self.assertRaises(E.EvaluationError):
                E.validate_samples({"samples": [modified]}, ((2, 1, 1),), 2)
        good[0].append([[5]])
        with self.assertRaises(E.EvaluationError):
            E.validate_samples({"samples": [good]}, ((2, 1, 1),), 2)

    def test_strict_case_grammar(self):
        requests = [
            dict(case(), seed=1),
            dict(case(), id=""),
            dict(case(), actions=[dict(t=0, kind="inject", port=0, amp=3.1, dur=1)]),
            dict(case(), queries=[dict(sensor="device0", t=[0.01])]),
            dict(case(), queries=[dict(sensor="hidden", t=[0])]),
            dict(case(), queries=[]),
            dict(case(), queries=[dict(sensor="global", t=[])]),
        ]
        for request in requests:
            with self.subTest(request=request):
                with self.assertRaises(E.EvaluationError):
                    E.validate_plan(request, groups=groups(), roster=ROSTER)

    def test_empty_query_allowed_when_some_observations_exist(self):
        request = case()
        request["queries"].append(dict(sensor="global", t=[]))
        pred, truth = samples([[1, 2], [2, 3]]), samples([[1, 2]])
        pred["samples"].append(np.empty((2, 0, 1, 2)))
        truth["samples"].append(np.empty((1, 0, 1, 2)))
        result = score(pred, truth, request=request)
        self.assertIsNone(result["marginal_crps"][1]["crps_by_port_slot_mean_over_times"])

    def test_query_times_are_strictly_increasing_native_ticks(self):
        for times in ([1, 0], [0, 0], [0.02, 0.0200000001]):
            with self.subTest(times=times), self.assertRaisesRegex(E.EvaluationError, "strictly increasing"):
                E.validate_case(case(times), roster=ROSTER)
        request = case([0, 0.02, 0.04])
        request["queries"].append(dict(sensor="global", t=[0, 0.04]))
        original = deepcopy(request)
        self.assertEqual(E.validate_case(request, roster=ROSTER), ((3, 1, 1), (2, 1, 2)))
        self.assertEqual(request, original)

    def test_exploration_empty_flag_validates_whole_request(self):
        for request, shapes in ((dict(case(), queries=[]), ()), (case([]), ((0, 1, 1),))):
            self.assertEqual(E.validate_case(request, roster=ROSTER, allow_empty=True), shapes)
            with self.assertRaises(E.EvaluationError):
                E.validate_case(request, roster=ROSTER)
            bad = dict(request, actions=[dict(t=0, kind="inject", port=0, amp=4, dur=1)])
            with self.assertRaises(E.EvaluationError):
                E.validate_case(bad, roster=ROSTER, allow_empty=True)

    def test_group_indices_scales_duplicates_and_keys(self):
        for update in (dict(scales=[1, 0]), dict(scales=[1, np.inf]), dict(scales=[1]), dict(unit=""), dict(extra=1)):
            bad = [dict(groups()[0], **update)]
            with self.assertRaises(E.EvaluationError):
                E.validate_plan(case(), groups=bad, roster=ROSTER)
        for field, value in (("query", 1), ("time_index", 2), ("port", 1), ("slot", 1), ("port", True), ("slot", 0.0)):
            bad = groups()
            bad[0]["selectors"][0][field] = value
            with self.assertRaises(E.EvaluationError):
                E.validate_plan(case(), groups=bad, roster=ROSTER)
        bad = groups()
        bad[0]["selectors"][1] = deepcopy(bad[0]["selectors"][0])
        with self.assertRaises(E.EvaluationError):
            E.validate_plan(case(), groups=bad, roster=ROSTER)
        with self.assertRaises(E.EvaluationError):
            E.validate_plan(case(), groups=groups() + groups(), roster=ROSTER)

    def test_all_caps_fail_before_predictor_or_truth(self):
        class Forbidden:
            def predict(self, *args, **kwargs):
                raise AssertionError("prediction called before caps")

            def sample_truth(self, *args, **kwargs):
                raise AssertionError("truth called before caps")

        requests = [
            (case(), groups(), dict(max_prediction_members=1), 2, 1),
            (case(), groups(), dict(max_truth_members=1), 1, 2),
            (case(), groups(), dict(max_horizon_tu=0.5), 2, 1),
            (case(), groups(), dict(max_times_per_query=1), 2, 1),
            (case(), groups(), dict(max_total_times=1), 2, 1),
            (case(), groups(), dict(max_output_values=5), 2, 1),
            (case(), groups(), dict(max_pairwise_work=10), 2, 1),
            (case(), groups(), dict(max_group_dimensions=1), 2, 1),
            (dict(case(), queries=case()["queries"] * 2), groups(), dict(max_queries=1), 2, 1),
            (
                dict(
                    case(),
                    actions=[
                        dict(t=0, kind="inject", port=0, amp=0, dur=1),
                        dict(t=1, kind="inject", port=0, amp=0, dur=1),
                    ],
                ),
                groups(),
                dict(max_actions=1),
                2,
                1,
            ),
        ]
        for request, score_groups, changed, m, n in requests:
            with self.subTest(cap=changed):
                with self.assertRaises(E.EvaluationError):
                    E.evaluate_trusted_predictor(
                        Forbidden(),
                        Forbidden(),
                        request,
                        groups=score_groups,
                        n_samples=m,
                        n_truth=n,
                        roster=ROSTER,
                        limits=replace(E.DEFAULT_LIMITS, **changed),
                    )

    def test_pairwise_work_estimate_includes_member_squared_dimensions(self):
        plan = E.validate_plan(case(), groups=groups(), n_samples=10, n_truth=3, roster=ROSTER)
        self.assertEqual(plan["pairwise_work"], 2 * 10 * 3 + 2 * 10 * (10 + 3))


class ScoreTests(unittest.TestCase):
    def test_crps_matches_bruteforce_with_unequal_members(self):
        rng = np.random.default_rng(34)
        x, y = rng.normal(size=(7, 2, 1, 1)), rng.normal(size=(3, 2, 1, 1))
        expected = np.abs(x[:, None] - y[None]).mean(axis=(0, 1))
        expected -= 0.5 * np.abs(x[:, None] - x[None]).mean(axis=(0, 1))
        np.testing.assert_allclose(E._marginal_crps(x, y), expected, atol=1e-15)

    def test_energy_matches_bruteforce(self):
        rng = np.random.default_rng(345)
        x, y = rng.normal(size=(7, 4)), rng.normal(size=(3, 4))
        expected = np.sqrt(np.mean((x[:, None] - y[None]) ** 2, axis=-1)).mean()
        expected -= 0.5 * np.sqrt(np.mean((x[:, None] - x[None]) ** 2, axis=-1)).mean()
        self.assertAlmostEqual(E._energy_score(x, y), expected, places=14)

    def test_constant_exact_score_zero_and_wrong_score_in_units(self):
        a, b = samples([[1, 1]] * 4), samples([[1, 1]] * 3)
        result = score(a, b)
        self.assertEqual(result["joint_energy_equal_group_mean"], 0.0)
        wrong = score(samples([[3, 3]] * 4), b)
        self.assertEqual(wrong["joint_energy_equal_group_mean"], 2.0)
        self.assertEqual(wrong["marginal_crps"][0]["crps_by_port_slot_mean_over_times"], [[2.0]])

    def test_joint_and_marginal_member_permutation_invariance(self):
        rng = np.random.default_rng(19)
        pred, truth = samples(rng.normal(size=(9, 2))), samples(rng.normal(size=(5, 2)))
        report = score(pred, truth)
        shuffled = score(
            {"samples": [pred["samples"][0][[4, 1, 3, 2, 6, 7, 8, 0, 5]]]},
            {"samples": [truth["samples"][0][[4, 0, 3, 1, 2]]]},
        )
        self.assertAlmostEqual(
            report["joint_energy_equal_group_mean"], shuffled["joint_energy_equal_group_mean"], places=14
        )
        np.testing.assert_allclose(
            report["marginal_crps"][0]["crps_by_port_slot_mean_over_times"],
            shuffled["marginal_crps"][0]["crps_by_port_slot_mean_over_times"],
        )

    def test_same_marginals_wrong_temporal_dependence_scores_worse(self):
        coherent = samples([[-1, -1], [1, 1]])
        wrong = samples([[-1, 1], [1, -1]])
        correct_report, wrong_report = score(coherent, coherent), score(wrong, coherent)
        self.assertEqual(correct_report["marginal_crps"], wrong_report["marginal_crps"])
        self.assertAlmostEqual(correct_report["joint_energy_equal_group_mean"], 0.5)
        self.assertAlmostEqual(wrong_report["joint_energy_equal_group_mean"], math_sqrt2_minus_half())
        self.assertGreater(
            wrong_report["joint_energy_equal_group_mean"], correct_report["joint_energy_equal_group_mean"]
        )

    def test_joint_member_identity_across_separate_queries(self):
        request = case([1])
        request["queries"].append(dict(sensor="device0", t=[2]))
        score_groups = groups()
        score_groups[0]["selectors"][1] = dict(query=1, time_index=0, port=0, slot=0)
        coherent = {"samples": [samples([[-1], [1]])["samples"][0]] * 2}
        wrong = {"samples": [coherent["samples"][0], coherent["samples"][1][::-1]]}
        correct_report = score(coherent, coherent, request=request, score_groups=score_groups)
        wrong_report = score(wrong, coherent, request=request, score_groups=score_groups)
        self.assertGreater(
            wrong_report["joint_energy_equal_group_mean"], correct_report["joint_energy_equal_group_mean"]
        )

    def test_truth_ensemble_score_is_mean_of_individual_truth_scores(self):
        pred, truth = samples([[0, 1], [1, 2], [2, 3]]), samples([[0.2, 1.2], [1.7, 2.7]])
        batch = score(pred, truth)
        singles = [score(pred, {"samples": [truth["samples"][0][i : i + 1]]}) for i in range(2)]
        self.assertAlmostEqual(
            batch["joint_energy_equal_group_mean"], np.mean([r["joint_energy_equal_group_mean"] for r in singles])
        )
        np.testing.assert_allclose(
            batch["marginal_crps"][0]["crps_by_port_slot_mean_over_times"],
            np.mean([r["marginal_crps"][0]["crps_by_port_slot_mean_over_times"] for r in singles], axis=0),
        )

    def test_duplicate_truth_observations_do_not_reweight_by_member_matching(self):
        pred = samples([[0, 0], [2, 2], [4, 4]])
        a, b = score(pred, samples([[1, 1]])), score(pred, samples([[1, 1]] * 7))
        self.assertAlmostEqual(a["joint_energy_equal_group_mean"], b["joint_energy_equal_group_mean"])

    def test_group_scales_and_equal_group_weights(self):
        score_groups = groups()
        score_groups[0]["scales"] = [2, 2]
        score_groups.append(dict(groups()[0], id="second"))
        result = score(samples([[3, 3]]), samples([[1, 1]]), score_groups=score_groups)
        self.assertEqual([g["energy_score"] for g in result["joint_energy"]], [1.0, 2.0])
        self.assertEqual(result["joint_energy_equal_group_mean"], 1.5)
        self.assertEqual(result["joint_energy"][0]["unit"], "dimensionless")

    def test_global_mean_and_variance_units_remain_separate(self):
        request = case()
        request["queries"][0]["sensor"] = "global"
        pred, truth = {"samples": [np.ones((2, 2, 1, 2))]}, {"samples": [np.zeros((1, 2, 1, 2))]}
        result = score(pred, truth, request=request)
        self.assertEqual(result["marginal_crps"][0]["slot_units"], ["field_value", "field_value_squared"])

    def test_overflow_fails_explicitly_without_nonfinite_report(self):
        with self.assertRaisesRegex(E.EvaluationError, "overflowed"):
            score(samples([[1e308, 1e308]]), samples([[-1e308, -1e308]]))


def math_sqrt2_minus_half():
    return float(np.sqrt(2) - 0.5)


class HarnessTests(unittest.TestCase):
    def test_fresh_private_seed_and_no_public_seed_or_report_leak(self):
        calls = []

        class Pred:
            def predict(self, actions, queries, n_samples, seed):
                calls.append(("predict", seed))
                return samples([[0, 0]] * n_samples)

        class Truth:
            def sample_truth(self, actions, queries, n_samples, *, truth_seed):
                calls.append(("truth", truth_seed))
                return samples([[1, 1]] * n_samples)

        with patch.object(E.secrets, "randbits", return_value=424242) as random_seed:
            report = E.evaluate_trusted_predictor(
                Pred(), Truth(), case(), groups=groups(), n_samples=3, n_truth=2, predictor_seed=13, roster=ROSTER
            )
        self.assertEqual(calls, [("predict", 13), ("truth", 424242)])
        random_seed.assert_called_once_with(64)
        self.assertNotIn("424242", json.dumps(report))
        self.assertNotIn("seed", json.dumps(report))

    def test_equal_numeric_seeds_are_allowed_without_matching_members(self):
        truth_seeds = []

        class Truth:
            def sample_truth(self, actions, queries, n_samples, *, truth_seed):
                truth_seeds.append(truth_seed)
                return samples([[1, 1]] * n_samples)

        report = E.evaluate_trusted_predictor(
            E.ConstantPredictor(roster=ROSTER),
            Truth(),
            case(),
            groups=groups(),
            n_samples=3,
            n_truth=2,
            predictor_seed=13,
            truth_seed=13,
            roster=ROSTER,
        )
        self.assertEqual(truth_seeds, [13])
        self.assertEqual(report["joint_energy_equal_group_mean"], 1.0)

    def test_predictor_seed_does_not_determine_truth_samples(self):
        observed = []

        class Truth:
            def sample_truth(self, actions, queries, n_samples, *, truth_seed):
                values = samples(np.random.default_rng(truth_seed).normal(size=(n_samples, 2)))
                observed.append(values["samples"][0])
                return values

        for model_seed in (0, 11, 999):
            E.evaluate_trusted_predictor(
                E.ConstantPredictor(roster=ROSTER),
                Truth(),
                case(),
                groups=groups(),
                n_samples=3,
                n_truth=4,
                predictor_seed=model_seed,
                truth_seed=66,
                roster=ROSTER,
            )
        for array in observed[1:]:
            np.testing.assert_array_equal(array, observed[0])

    def test_malformed_prediction_fails_before_truth(self):
        class Pred:
            def predict(self, *args, **kwargs):
                return {"samples": [np.array([np.nan])]}

        class Truth:
            def sample_truth(self, *args, **kwargs):
                raise AssertionError("must not spend truth work on malformed prediction")

        with self.assertRaises(E.EvaluationError):
            E.evaluate_trusted_predictor(Pred(), Truth(), case(), groups=groups(), roster=ROSTER)

    def test_predictor_mutating_request_cannot_change_truth_request(self):
        received = []

        class Pred:
            def predict(self, actions, queries, n_samples, seed):
                queries[0]["t"][1] = 200
                return samples([[0, 0]] * n_samples)

        class Truth:
            def sample_truth(self, actions, queries, n_samples, *, truth_seed):
                received.append(queries[0]["t"])
                return samples([[1, 1]] * n_samples)

        E.evaluate_trusted_predictor(Pred(), Truth(), case(), groups=groups(), roster=ROSTER)
        self.assertEqual(received, [[0, 1]])

    def test_constant_and_persistence_are_action_blind_and_explicit(self):
        constant = E.ConstantPredictor(0, roster=ROSTER)
        persistence = E.PersistencePredictor({"device0": [[2]]}, roster=ROSTER)
        request = case()
        baseline = persistence.predict([], request["queries"], n_samples=3)
        moved = persistence.predict([dict(t=0, kind="adjust", device=0, u=[1, 0, 0])], request["queries"], n_samples=3)
        np.testing.assert_array_equal(baseline["samples"][0], moved["samples"][0])
        truth = samples([[2, 2]])
        self.assertEqual(score(baseline, truth)["joint_energy_equal_group_mean"], 0.0)
        self.assertEqual(
            score(constant.predict([], request["queries"], n_samples=3), truth)["joint_energy_equal_group_mean"], 2.0
        )

    def test_bounded_json_bundle_roundtrip_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            request = case()
            (folder / "case.json").write_text(json.dumps(request))
            (folder / "groups.json").write_text(json.dumps(groups()))
            E.write_sample_bundle(folder / "pred.json", request, samples([[0, 0], [2, 2]]), n_members=2, roster=ROSTER)
            E.write_sample_bundle(folder / "truth.json", request, samples([[1, 1]]), n_members=1, roster=ROSTER)
            self.assertEqual(
                E.main(
                    [
                        "--case",
                        str(folder / "case.json"),
                        "--groups",
                        str(folder / "groups.json"),
                        "--prediction",
                        str(folder / "pred.json"),
                        "--truth",
                        str(folder / "truth.json"),
                        "--n-samples",
                        "2",
                        "--n-truth",
                        "1",
                        "--n-ports",
                        "1",
                        "--device-slots",
                        "1",
                        "--out",
                        str(folder / "score.json"),
                    ]
                ),
                0,
            )
            report = json.loads((folder / "score.json").read_text())
            self.assertEqual(report["joint_energy_equal_group_mean"], 0.5)
            with self.assertRaises(E.EvaluationError):
                E.read_sample_bundle(folder / "pred.json", dict(request, id="wrong"), n_members=2, roster=ROSTER)
            changed_time = deepcopy(request)
            changed_time["queries"][0]["t"] = [0, 2]
            with self.assertRaisesRegex(E.EvaluationError, "exact public case"):
                E.read_sample_bundle(folder / "pred.json", changed_time, n_members=2, roster=ROSTER)
            changed_actions = deepcopy(request)
            changed_actions["actions"] = [dict(t=0, kind="inject", port=0, amp=1, dur=1)]
            with self.assertRaisesRegex(E.EvaluationError, "exact public case"):
                E.read_sample_bundle(folder / "pred.json", changed_actions, n_members=2, roster=ROSTER)

    def test_file_byte_cap_duplicate_keys_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            for text in ('{"a":1,"a":2}', '{"a":NaN}', "[" * 10000):
                path.write_text(text)
                with self.assertRaises(E.EvaluationError):
                    E.read_json_data(path)
            path.write_text("[123456789]")
            with self.assertRaises(E.EvaluationError):
                E.read_json_data(path, limits=replace(E.DEFAULT_LIMITS, max_bundle_bytes=5))

    def test_cli_world_horizon_checked_before_bundle_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            request = case([0, 60])
            (folder / "case.json").write_text(json.dumps(request))
            (folder / "groups.json").write_text(json.dumps(groups()))
            # Paths deliberately do not exist: the invalid world horizon must
            # be rejected first, without any prediction/truth file loading.
            args = [
                "--case",
                str(folder / "case.json"),
                "--groups",
                str(folder / "groups.json"),
                "--prediction",
                str(folder / "absent_prediction.json"),
                "--truth",
                str(folder / "absent_truth.json"),
                "--n-ports",
                "1",
                "--device-slots",
                "1",
                "--max-horizon-tu",
                "50",
                "--out",
                str(folder / "score.json"),
            ]
            with self.assertRaisesRegex(E.EvaluationError, "horizon"):
                E.main(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    suite = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (ValidationTests, ScoreTests, HarnessTests)
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(
        suite="r6_offline_evaluation_toy",
        tests=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
        skipped=len(result.skipped),
        passed=result.wasSuccessful(),
        wall_seconds=time.perf_counter() - start,
        python=sys.version,
        numpy=np.__version__,
        native_steps=0,
        model_calls=0,
        remote_calls=0,
        execution_boundary="reviewed local Python and data-only JSON; no submitted-code sandbox",
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

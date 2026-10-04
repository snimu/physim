"""Local exploration contract and budget tests; toy physics only."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
from physim.blobround6_eval import DEFAULT_LIMITS, EvaluationError, PublicRoster
from physim.blobround6_explore import ExperimentService
from test_blob_round6 import _toy


class ExplorationTests(unittest.TestCase):
    def make(self, **kwargs):
        oracle, calls, _, _ = _toy(noise=True)
        return ExperimentService(oracle, roster=PublicRoster(2, (2, 3), protocol="fixed-source-v1"), **kwargs), calls

    def test_restarts_same_physical_state_with_fresh_noise(self):
        service, _ = self.make()
        queries = [dict(sensor="device0", t=[0, 0.1])]
        first = service.experiment([], queries)["samples"][0]
        second = service.experiment([], queries)["samples"][0]
        np.testing.assert_array_equal(first[:, 0], second[:, 0])
        self.assertFalse(np.array_equal(first[:, 1], second[:, 1]))
        self.assertEqual(first.shape, (1, 2, 2, 2))
        self.assertEqual(service.usage()["experiments"], 2)

    def test_max_amplitude_matches_evaluation_and_emitter_is_fixed(self):
        service, calls = self.make()
        service.experiment(
            [dict(t=0, kind="inject", port=0, amp=3, dur=0.02), dict(t=0.02, kind="adjust", device=0, u=[1, 0, 0])],
            [dict(sensor="device0", t=[0.04])],
        )
        injections = [inj for _, _, injs in calls for inj in injs]
        self.assertEqual(injections[0]["amp"], 3)
        self.assertEqual([injections[0]["y"], injections[0]["x"]], [15.5, 15.5])

    def test_validation_precedes_budget_and_physics(self):
        service, calls = self.make()
        for actions in (
            [dict(t=0, kind="inject", port=0, amp=4, dur=1)],
            [dict(t=0, kind="adjust", device=0, u=[2, 0, 0])],
        ):
            with self.assertRaises(EvaluationError):
                service.experiment(actions, [dict(sensor="global", t=[1])])
        self.assertEqual(calls, [])
        self.assertEqual(service.usage()["experiments"], 0)

    def test_budget_enforced_before_extra_physics(self):
        service, calls = self.make(max_total_tu=0.1)
        service.experiment([], [dict(sensor="global", t=[0.1])])
        count = len(calls)
        with self.assertRaises(EvaluationError):
            service.experiment([], [dict(sensor="global", t=[0.02])])
        self.assertEqual(len(calls), count)

    def test_invalid_time_order_consumes_no_experiment_budget(self):
        service, calls = self.make()
        for times in ([0.04, 0], [0, 0], [0.02, 0.0200000001]):
            with self.subTest(times=times), self.assertRaisesRegex(EvaluationError, "strictly increasing"):
                service.experiment([], [dict(sensor="global", t=times)])
        self.assertEqual(calls, [])
        self.assertEqual(service.usage()["experiments"], 0)
        self.assertEqual(service.usage()["charged_tu"], 0)

    def test_concurrent_requests_cannot_bypass_count(self):
        service, _ = self.make(max_experiments=1)

        def attempt(_):
            try:
                service.experiment([], [dict(sensor="global", t=[0.02])])
                return True
            except EvaluationError:
                return False

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(4))), 1)
        self.assertEqual(service.usage()["experiments"], 1)

    def test_fractional_budget_never_rounds_up(self):
        service, calls = self.make(max_total_tu=0.011)
        with self.assertRaises(EvaluationError):
            service.experiment([], [dict(sensor="global", t=[0.02])])
        self.assertEqual(calls, [])
        self.assertLessEqual(service.usage()["max_total_tu"], 0.011)

    def test_output_cap_precedes_physics(self):
        service, calls = self.make(limits=replace(DEFAULT_LIMITS, max_output_values=1))
        with self.assertRaises(EvaluationError):
            service.experiment([], [dict(sensor="device0", t=[0])])
        self.assertEqual(calls, [])

    def test_no_public_truth_seed(self):
        service, _ = self.make()
        with self.assertRaises(TypeError):
            service.experiment([], [dict(sensor="global", t=[0])], truth_seed=2)

    def test_empty_observations_validate_but_do_not_step(self):
        service, calls = self.make()
        self.assertEqual(service.experiment([], []), {"samples": []})
        result = service.experiment([], [dict(sensor="device0", t=[])])
        self.assertEqual(result["samples"][0].shape, (1, 0, 2, 2))
        self.assertEqual(calls, [])
        with self.assertRaises(EvaluationError):
            service.experiment([dict(t=0, kind="inject", port=0, amp=4, dur=1)], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""World dimensions propagate through validation without exposing private data."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from blobkit import worlds
from physim import blobround6 as R6
from physim import blobround6_eval as scoring
from physim import evaluation, taskset
from physim.bundles import NUMERICS, Bundle, BundleError


def physics_fixture(name):
    bundle = Bundle.__new__(Bundle)
    bundle.genome = worlds.load(name)
    n_ports = len(bundle.genome["acts"]) + len(bundle.genome["chans"])
    bundle.manifest = dict(
        objects=dict(
            world=dict(numerics=NUMERICS),
            preparation=dict(noise_policy=R6.NOISE_POLICY, public_time=0, noise_coefficient=0.002),
        )
    )
    records = []
    for i, (lattice, slots) in enumerate((("square", 13), ("hex", 19))):
        parameters = dict(
            dev_id=i,
            lattice=lattice,
            n_rings=3,
            base_ds=3.0,
            center=[64, 64],
            L=128.0,
            secret_rot=0.0,
            reflect=False,
            motion_theta=0.0,
            motion_reflect=False,
            node_perm=list(range(slots)),
            dil_bounds=[0.5, 3],
        )
        records.append(dict(parameters=parameters, dilation=1.0, motion_basis=np.eye(2).tolist()))
    bundle.apparatus = dict(
        devices=records,
        device_slots=[13, 19],
        port_permutation=list(range(n_ports)),
        adjustment_matrix=np.eye(3).tolist(),
        emitter_yx=[64, 64],
    )
    return bundle


@pytest.mark.parametrize("name", ["bf", "xv", "m4", "ds6_000"])
def test_actual_packaged_world_dimensions_are_supported(name):
    physics_fixture(name)._validate_physics()


def test_nondiffusing_memory_is_valid_but_negative_diffusion_is_not():
    b = physics_fixture("bf")
    assert b.genome["chans"][2]["D"] == 0
    b._validate_physics()
    b.genome["chans"][2]["D"] = -0.01
    with pytest.raises(BundleError, match="coefficient"):
        b._validate_physics()


@pytest.mark.parametrize("change", ["matrix", "bilinear", "permutation", "count"])
def test_dimension_mismatches_fail_before_simulation(change):
    b = physics_fixture("bf")
    if change == "matrix":
        b.genome["K"][0].append(0)
    elif change == "bilinear":
        b.genome["bilin"][0][1] = 3
    elif change == "permutation":
        b.apparatus["port_permutation"] = list(range(12))
    else:
        b.genome["chans"] = b.genome["chans"] * 20
    with pytest.raises(BundleError):
        b._validate_physics()


class PublicPredictorBox:
    forced_ports = None

    def __init__(self, observations, artifact):
        pass

    def prediction(self, actions, queries, *, n_samples, seed, n_ports):
        n_ports = self.forced_ports or n_ports
        slots = {"device0": 13, "device1": 19, "global": 2}
        arrays = [np.zeros((n_samples, len(q["t"]), n_ports, slots[q["sensor"]])).tolist() for q in queries]
        return json.dumps(dict(samples=arrays)), dict(wall_seconds=0)

    def close(self):
        pass


@pytest.mark.parametrize("ports", [4, 6, 12])
def test_all_public_gate_cases_use_the_world_roster(ports):
    with patch.object(evaluation, "Sandbox", PublicPredictorBox):
        result = evaluation.validate_predictor(
            Path("artifact"),
            Path("observations"),
            roster=scoring.PublicRoster(n_ports=ports),
            sandbox_factory=PublicPredictorBox,
        )
    assert result["ok"] and result["checks_passed"] == 7
    assert result["checks"][0]["actual_shapes"][0] == [2, 2, ports, 13]


def test_twelve_port_predictor_is_rejected_for_four_port_world():
    with patch.object(evaluation, "Sandbox", PublicPredictorBox), patch.object(PublicPredictorBox, "forced_ports", 12):
        result = evaluation.validate_predictor(
            Path("artifact"),
            Path("observations"),
            roster=scoring.PublicRoster(n_ports=4),
            sandbox_factory=PublicPredictorBox,
        )
    assert not result["ok"]


def test_prompt_advertises_only_the_public_roster():
    b = SimpleNamespace(roster=scoring.PublicRoster(n_ports=4))
    with patch.object(taskset, "required_bundle", return_value=b):
        text = taskset.public_prompt(taskset.R6ToolsConfig(bundle=Path("private-bf-bundle")))
    assert "4 channels" in text and "0 to 3" in text and "times, 4," in text
    assert "all12" not in text and "0..11" not in text and "times, 12," not in text
    assert "private-bf-bundle" not in text and "bilinear" not in text


def test_apparatus_versions_select_matching_runtime_and_source_geometry():
    old = physics_fixture("bf")
    old._validate_physics()
    assert old.protocol == R6.LEGACY_PROTOCOL
    assert old.runner.__name__ == "physim.legacy_v1.blobround6"
    updated = physics_fixture("bf")
    del updated.apparatus["emitter_yx"]
    updated.apparatus["protocol"] = R6.APPARATUS_PROTOCOL
    updated._validate_physics()
    assert updated.runner is R6 and updated.scoring is scoring
    # A detached source cannot silently survive the centered-apparatus change.
    updated.apparatus["emitter_yx"] = [64, 70]
    with pytest.raises(BundleError, match="apparatus"):
        updated._validate_physics()

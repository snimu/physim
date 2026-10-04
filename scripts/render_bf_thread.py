"""Render the BF thread figures: the BF world, its apparatus, and its experiments.

Every figure displays BF the same way: one panel per field in genome order
(u0, x0, x1, x2), each with a fixed color scale and identity hue. Apparatus glyphs
are drawn identically on every panel because every sensor reads every field.

Inputs are the registry's content-addressed BF genome and preparation, verified by
hash. The centered-pulse-v2 apparatus is rebuilt with the rule in
generators/physim/eval_preparation.py. Experiments run through the native
OracleRunner, and a capturing stepper keeps the fields at every recorded time.
Extra global queries only add capture points: sampling consumes no randomness and
the stepper advances one step at a time, so trajectories are unchanged. Before any
figure is drawn, the four recorded causal-check arms in
docs_source/data/bf-evaluation.npz must be reproduced bit for bit.

From the repository root, with the development environment:

    PYTHONPATH=environments/physim:packages/blobkit python scripts/render_bf_thread.py

Runs are cached under outputs/bf-thread-20261002; figures, videos and provenance are
written to docs/assets/bf-thread/. Requires NumPy, SciPy, Matplotlib and FFmpeg.
No model inference is performed.
"""

import argparse
import copy
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

for _key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_key, "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/physim-bf-thread-mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from blobkit.soup import sim_cpu
from matplotlib.cm import ScalarMappable
from matplotlib.colors import AsinhNorm, LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch, Rectangle
from physim import blobround6 as R6
from physim.bundles import Bundle
from physim.devices import ProbeDevice, bilinear, step_chunk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.scientific_video import video_writer  # noqa: E402

REGISTRY = ROOT / "registry/artifact"
CACHE = ROOT / "outputs/bf-thread-20261002"
OUT = ROOT / "docs/assets/bf-thread"
EVIDENCE = ROOT / "docs_source/data/bf-evaluation.npz"
GENOME_SHA = "d59f7d9d7ffdb0251bceb2f989f91d2e2ac86dce4409f5d36f3f3e65cad3e038"
PREPARATION_SHA = "de9dda65ef430cd70353e472a956c32df462a5bb33b41641e26ced0b07bd68f8"
FIELD_SHA = "c4c3c0c67b0eab22367b1780ae1ad5d6386f356048db9ad1862b3187cbf904c7"
PORT_PERM = [2, 0, 3, 1]  # public port -> field index; fields are (u0, x0, x1, x2)
SEED = 53001  # the recorded causal-check truth seed; all comparisons share future noise
FILM_SEED = 926201  # the published BF film's continuation seed
CAUSAL_TIMES = [0, 2, 5, 10, 20, 30, 40, 50]
P4_FIELD_SHA = "847754b2bff40693e2f830ea083a97d1b23a513fab50ad11ca7f9d44399cc7ea"  # the t = 1700 preparation
P4_FILM_SEED = 926203  # the published p4g2_044 film's continuation seed
DX, N, HALF = 0.5, 256, 80  # grid spacing, grid size, crop half-width in cells (40 units)
LAB = 16.0  # half-width of the laboratory view around the device center
WORLD_OFFSET, WORLD = (-6.0, 4.0), 28.0  # world view: center offset (y, x) from the device, half-width
CENTER_EXTENT = [(-HALF - 0.5) * DX, (HALF - 0.5) * DX, (HALF - 0.5) * DX, (-HALF - 0.5) * DX]

INK, MUTED, LINE, WASH = "#17242f", "#52616e", "#dbe2e8", "#f3f6f9"
GRAY_TRACE = "#b9c3cc"
MONO = ["Liberation Mono", "DejaVu Sans Mono"]  # the page uses ui-monospace


def inject(port, amp, t=0, device=0, dur=5):
    return dict(t=t, kind="inject", device=device, port=port, amp=amp, dur=dur)


def adjust(u, t=0, device=0):
    return dict(t=t, kind="adjust", device=device, u=u)


RUNS = {
    "sham": dict(actions=[], feedback=True, note="BF suite c001 (no actions)"),
    "trail_pulse": dict(actions=[inject(2, 0.05)], feedback=True, note="BF suite c006 (high trail pulse)"),
    "feedback_removed_sham": dict(actions=[], feedback=False, note="causal control without the x2*x1 term"),
    "feedback_removed_trail_pulse": dict(
        actions=[inject(2, 0.05)], feedback=False, note="causal control without the x2*x1 term"
    ),
    "walk": dict(
        actions=[adjust([1, 0, 0], t=t) for t in (0, 5, 10)]
        + [adjust([0, 1, 0], t=t) for t in (15, 20, 25)]
        + [adjust([0, 0, 0.4], t=30)],
        feedback=True,
        note="apparatus demonstration, not a suite case",
    ),
}


# ------------------------------------------------------------------------------------------
# Display vocabulary: one hue per field (validated categorical slots), one-hue sequential ramps
# ------------------------------------------------------------------------------------------
def _oklab(rgb):
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(
        np.array(
            [
                [0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005],
            ]
        )
        @ lin
    )
    return (
        np.array(
            [
                [0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660],
            ]
        )
        @ lms
    )


def _srgb(lab):
    lms = (
        np.array(
            [[1, 0.3963377774, 0.2158037573], [1, -0.1055613458, -0.0638541728], [1, -0.0894841775, -1.2914855480]]
        )
        @ lab
    )
    lin = (
        np.array(
            [
                [4.0767416621, -3.3077115913, 0.2309699292],
                [-1.2684380046, 2.6097574011, -0.3413193965],
                [-0.0041960863, -0.7034186147, 1.7076147010],
            ]
        )
        @ lms**3
    )
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


def ramp(hue, mid=0.55, dark=0.32, n=256):
    """White -> identity hue (at `mid`) -> deep shade of the same hue, monotone in OKLab lightness."""
    L_h, a, b = _oklab(np.array([int(hue[i : i + 2], 16) / 255 for i in (1, 3, 5)]))
    C_h, h = np.hypot(a, b), np.arctan2(b, a)
    colors = []
    for t in np.linspace(0, 1, n):
        if t <= mid:
            L, C = 0.995 + (L_h - 0.995) * t / mid, C_h * (t / mid) ** 0.9
        else:
            u = (t - mid) / (1 - mid)
            L, C = L_h + (dark - L_h) * u, C_h * (1 - 0.35 * u)
        colors.append(_srgb(np.array([L, C * np.cos(h), C * np.sin(h)])))
    return LinearSegmentedColormap.from_list(f"bf-{hue}", np.clip(colors, 0, 1), N=n)


FIELDS = [
    dict(
        key="u0",
        sym="u₀",
        role="excitation",
        hue="#2a78d6",
        vmin=-0.70,
        vmax=1.10,
        ticks=[-0.7, 0, 1],
        trace=(-1.0, 1.2),
        trace_ticks=[-0.7, 0, 1],
    ),
    dict(
        key="x0",
        sym="x₀",
        role="slow inhibitor",
        hue="#1baf7a",
        vmin=0.0,
        vmax=1.05,
        ticks=[0, 0.5, 1],
        trace=(-0.1, 1.1),
        trace_ticks=[0, 0.5, 1],
    ),
    dict(
        key="x1",
        sym="x₁",
        role="fast inhibitor",
        hue="#4a3aa7",
        vmin=0.0,
        vmax=0.55,
        ticks=[0, 0.25, 0.5],
        trace=(-0.03, 0.6),
        trace_ticks=[0, 0.25, 0.5],
    ),
    # Trails (~0.02) and source pulses (~0.25) share x2: linear near zero, logarithmic above.
    dict(
        key="x2",
        sym="x₂",
        role="trail",
        hue="#eb6834",
        vmin=0.0,
        vmax=0.25,
        ticks=[0, 0.01, 0.03, 0.1, 0.25],
        trace=(0.0, 0.3),
        trace_ticks=[0, 0.01, 0.1],
        linear_width=0.004,
    ),
]
for _f in FIELDS:
    _f["cmap"] = ramp(_f["hue"])


# p4g2_044 highlights: four of its twelve fields, with the same display rules as BF, in the
# published film's window. u3 rests high and dips into a labyrinth, so its ramp is reversed.
P4_CENTER, P4_HALF, P4_POSTER_T = (30.0, 50.0), 40.0, 300.0  # view center (y, x), half-width, poster time
P4_FIELDS = [
    dict(key="u0", index=0, sym="u₀", role="blobs", hue="#2a78d6", vmin=-1.0, vmax=1.1, ticks=[-1, 0, 1]),
    dict(key="u1", index=1, sym="u₁", role="stripes", hue="#1baf7a", vmin=-1.3, vmax=1.25, ticks=[-1, 0, 1]),
    dict(
        key="u3",
        index=3,
        sym="u₃",
        role="labyrinth",
        hue="#4a3aa7",
        vmin=-1.7,
        vmax=1.7,
        ticks=[-1.5, 0, 1.5],
        reverse=True,
    ),
    dict(
        key="x7",
        index=11,
        sym="x₇",
        role="slow memory",
        hue="#eb6834",
        vmin=0.0,
        vmax=0.03,
        ticks=[0, 0.01, 0.02, 0.03],
    ),
]
for _f in P4_FIELDS:
    # White marks the resting value; fields that rest high and dip get the reversed ramp.
    _f["cmap"] = ramp(_f["hue"]).reversed() if _f.get("reverse") else ramp(_f["hue"])


def norm(f):
    if "linear_width" in f:
        return AsinhNorm(f["linear_width"], vmin=f["vmin"], vmax=f["vmax"])
    return Normalize(f["vmin"], f["vmax"])


plt.rcParams.update(
    {
        "font.family": ["Liberation Sans", "DejaVu Sans"],  # page: system sans, Helvetica/Arial fallback
        "font.size": 9,
        "text.color": INK,
        "axes.linewidth": 0.6,
        "axes.edgecolor": LINE,
        "savefig.facecolor": "white",
    }
)


# ------------------------------------------------------------------------------------------
# The BF laboratory
# ------------------------------------------------------------------------------------------
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(sha):
    path = REGISTRY / f"{sha}.bin"
    if digest(path) != sha:
        raise ValueError(f"registry artifact hash mismatch: {path}")
    return path


class Lab:
    """The recorded BF preparation with its centered-pulse-v2 apparatus."""

    def __init__(self):
        self.genome = json.loads(verified(GENOME_SHA).read_text())
        with np.load(verified(PREPARATION_SHA), allow_pickle=False) as data:
            self.fields = data["fields"].copy()
        if hashlib.sha256(self.fields.tobytes()).hexdigest() != FIELD_SHA:
            raise ValueError("preparation field identity mismatch")
        # Same rule as generators/physim/eval_preparation.py::prepare for BF.
        y, x = np.unravel_index(np.argmax(self.fields[0]), self.fields[0].shape)
        self.center = (np.array([y, x]) + 0.5) * DX
        rng = np.random.default_rng(41001)
        self.devices = [
            ProbeDevice(i, lattice, 3, spacing, self.center, 128.0, 0.0, False, 0.0, False, rng.permutation(slots))
            for i, (lattice, spacing, slots) in enumerate((("square", 3.0, 13), ("hex", 6.0, 19)))
        ]
        ci = np.floor(self.center / DX).astype(int)
        self.rows, self.cols = [(np.arange(-HALF, HALF) + c) % N for c in ci]

    def crop(self, fields):
        return fields[:, self.rows][:, :, self.cols]

    def run(self, name, record_dt=0.5, horizon=50.0):
        spec = RUNS[name]
        identity = dict(
            name=name,
            actions=spec["actions"],
            feedback=spec["feedback"],
            truth_seed=SEED,
            member=0,
            record_dt=record_dt,
            horizon=horizon,
            field_sha256=FIELD_SHA,
            protocol=R6.APPARATUS_PROTOCOL,
            port_permutation=PORT_PERM,
            causal_times=CAUSAL_TIMES,
        )
        path = CACHE / f"{name}.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as z:
                if json.loads(str(z["identity"])) == identity:
                    return dict(times=z["times"], crops=z["crops"], dev0=z["dev0"], identity=identity, path=path)
        crops = {}
        state = sim_cpu.init_soup(self.genome, L=128, n_soup=0, seed=0, workers=1, noise=0.002)
        state["F"] = self.fields.copy()
        if not spec["feedback"]:
            state["bilin"] = []  # remove only the x2*x1 reaction term, as bf_feedback_check.py does

        def step(sim, count, injections=None):
            step_chunk(sim, count, injections=injections)
            crops[sim["t_step"]] = self.crop(sim["F"])

        oracle = R6.OracleRunner(
            _template=state,
            _devices=self.devices,
            _port_perm=PORT_PERM,
            _adjust_mix=np.eye(3).tolist(),
            _stepper=step,
        )
        grid = [round(float(t), 6) for t in np.arange(0, horizon + 1e-9, record_dt)]
        queries = [dict(sensor="device0", t=CAUSAL_TIMES), dict(sensor="global", t=grid)]
        samples = oracle.sample_truth(spec["actions"], queries, n_samples=1, truth_seed=SEED)["samples"]
        crops[0] = self.crop(self.fields)
        times = np.array(grid)
        stack = np.stack([crops[round(t / R6.SIM_DT)] for t in grid]).astype(np.float32)
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, times=times, crops=stack, dev0=samples[0][0], identity=json.dumps(identity))
        print(f"recorded {name}", flush=True)
        return dict(times=times, crops=stack, dev0=samples[0][0], identity=identity, path=path)

    def continuation(self, horizon=300.0, record_dt=2.5):
        """Unforced continuation with the same construction as scripts/render_world_movies.py."""
        identity = dict(seed=FILM_SEED, horizon=horizon, record_dt=record_dt, field_sha256=FIELD_SHA, noise=0.002)
        path = CACHE / "film.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as z:
                if json.loads(str(z["identity"])) == identity:
                    return dict(times=z["times"], crops=z["crops"], identity=identity, path=path)
        sim = sim_cpu.init_soup(self.genome, L=128.0, seed=0, n_soup=0, dtype="f32", noise=0.002, workers=1)
        sim["F"], sim["t_step"] = self.fields.copy(), 0
        sim["rng"] = np.random.default_rng(FILM_SEED)
        times = np.arange(0, horizon + record_dt / 2, record_dt)
        crops = []
        for t in times:
            step_chunk(sim, round(t / sim["dt"]) - sim["t_step"])
            crops.append(self.crop(sim["F"]))
        crops = np.asarray(crops, dtype=np.float32)
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, times=times, crops=crops, identity=json.dumps(identity))
        print("recorded film continuation", flush=True)
        return dict(times=times, crops=crops, identity=identity, path=path)

    def rel(self, points):
        """Minimum-image offsets (y, x) from the device center."""
        d = np.asarray(points, float) - self.center
        return (d + 64.0) % 128.0 - 64.0

    def read(self, crop, nodes):
        """(4, k) bilinear readings at world positions, with the arithmetic of physim.devices.bilinear."""
        r = self.rel(nodes)
        gy, gx = r[:, 0] / DX + HALF, r[:, 1] / DX + HALF
        i0, j0 = np.floor(gy).astype(int), np.floor(gx).astype(int)
        fy, fx = (gy - i0)[None], (gx - j0)[None]
        f = crop.astype(np.float32)
        return (
            f[:, i0, j0] * (1 - fy) * (1 - fx)
            + f[:, i0, j0 + 1] * (1 - fy) * fx
            + f[:, i0 + 1, j0] * fy * (1 - fx)
            + f[:, i0 + 1, j0 + 1] * fy * fx
        )

    def poses(self, actions, times):
        """Device poses and latched pulses at each time, following the protocol's ordering rules."""
        tick = lambda t: round(t / R6.SIM_DT)  # noqa: E731
        devices = copy.deepcopy(self.devices)
        launched, k, timeline = [], 0, []
        for t in times:
            while k < len(actions) and tick(actions[k]["t"]) <= tick(t):
                a = actions[k]
                if a["kind"] == "adjust":
                    R6._adjust_pose(devices[a["device"]], a["u"], np.eye(3))
                else:
                    launched.append(dict(a, center=devices[a["device"]].center.copy()))
                k += 1
            timeline.append(
                dict(
                    nodes=[d.node_positions() for d in devices],
                    centers=[d.center.copy() for d in devices],
                    active=[p for p in launched if tick(p["t"]) <= tick(t) < tick(p["t"] + p["dur"])],
                )
            )
        return timeline


def p4_bundle():
    """The published p4g2_044 reference bundle (simulation profile), downloaded once and verified.

    docs_source/worlds.json pins the dataset revision and the manifest hash; the manifest pins
    every file, and the preparation must carry the recorded t = 1700 field hash.
    """
    record = next(
        w for w in json.loads((ROOT / "docs_source/worlds.json").read_text())["worlds"] if w["id"] == "p4g2_044"
    )
    ref = record["reference_bundle"]
    base = (
        f"https://huggingface.co/datasets/{ref['dataset_repo']}/resolve/{ref['dataset_revision']}/{ref['bundle_path']}"
    )
    root = CACHE / "p4g2_044-bundle"
    manifest = root / "manifest.json"
    if not manifest.exists():
        root.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"{base}/manifest.json", manifest)
    if digest(manifest) != ref["references"]["manifest_sha256"]:
        raise ValueError("p4g2_044 manifest differs from the catalog's reference bundle")
    for item in json.loads(manifest.read_text())["files"]:
        target = root / item["path"]
        if "simulation" in item["profiles"] and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(f"{base}/{item['path']}", target)
    bundle = Bundle(root, profile="simulation")
    if bundle.manifest["objects"]["preparation"]["field_sha256"] != P4_FIELD_SHA:
        raise ValueError("the reference bundle's preparation is not the recorded p4g2_044 preparation")
    return bundle, dict(source=base, **bundle.references())


def p4_continuation(horizon=450.0, record_dt=2.5):
    """Unforced continuation of the published preparation, built as scripts/render_world_movies.py builds it."""
    bundle, reference = p4_bundle()
    identity = dict(
        seed=P4_FILM_SEED,
        horizon=horizon,
        record_dt=record_dt,
        field_sha256=P4_FIELD_SHA,
        bundle=reference["bundle"],
    )
    path = CACHE / "p4g2_044-film.npz"
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            if json.loads(str(z["identity"])) == identity:
                return dict(times=z["times"], frames=z["frames"], identity=identity, reference=reference, path=path)
    sim = copy.deepcopy(bundle.make_oracle()._template)
    if hashlib.sha256(np.asarray(sim["F"]).tobytes()).hexdigest() != P4_FIELD_SHA:
        raise ValueError("p4g2_044 preparation identity mismatch")
    sim["workers"] = 1
    sim["rng"] = np.random.default_rng(P4_FILM_SEED)
    times = np.arange(0, horizon + record_dt / 2, record_dt)
    frames = []
    for t in times:
        step_chunk(sim, round(t / sim["dt"]) - sim["t_step"])
        frames.append(np.asarray(sim["F"], dtype=np.float16))  # full domain, all twelve fields
        if t % 50 == 0:
            print(f"p4g2_044 continuation t = {t:g}", flush=True)
    frames = np.asarray(frames)
    np.savez_compressed(path, times=times, frames=frames, identity=json.dumps(identity))
    return dict(times=times, frames=frames, identity=identity, reference=reference, path=path)


def verify(lab, runs):
    """Reproduce recorded evidence before drawing anything."""
    with np.load(EVIDENCE, allow_pickle=False) as ev:
        if ev["causal_times"].tolist() != CAUSAL_TIMES:
            raise ValueError("recorded causal times changed")
        recorded = {
            "sham": ev["coupled_sham"][0],
            "trail_pulse": ev["coupled_pulse"][0],
            "feedback_removed_sham": ev["feedback_removed_sham"][0],
            "feedback_removed_trail_pulse": ev["feedback_removed_pulse"][0],
        }
    for name, reference in recorded.items():
        if not np.array_equal(runs[name]["dev0"][:, 1, :], reference):  # public port 1 is u0
            raise ValueError(f"{name} does not reproduce the recorded causal check")
    run, device = runs["trail_pulse"], lab.devices[0]
    for j, t in enumerate(CAUSAL_TIMES):
        ti = int(np.flatnonzero(run["times"] == t)[0])
        mine = lab.read(run["crops"][ti], device.node_positions())[PORT_PERM][:, device.node_perm]
        if not np.allclose(mine, run["dev0"][j], rtol=0, atol=2e-6):
            raise ValueError("crop readings differ from the oracle's device-0 queries")
    removed = (runs["feedback_removed_trail_pulse"]["crops"], runs["feedback_removed_sham"]["crops"])
    if not np.array_equal(removed[0][:, :3], removed[1][:, :3]):
        raise ValueError("without feedback, the trail pulse must not change u0, x0 or x1")
    effect = lambda a, b: float(  # noqa: E731
        np.sqrt(np.mean((runs[a]["dev0"][-1, 1] - runs[b]["dev0"][-1, 1]) ** 2))
    )
    return dict(
        causal_check_member0_bitwise=sorted(recorded),
        crop_readings_match_oracle_queries=True,
        feedback_removed_u0_x0_x1_identical=True,
        time50_u0_effect_rms=dict(
            coupled=effect("trail_pulse", "sham"),
            feedback_removed=effect("feedback_removed_trail_pulse", "feedback_removed_sham"),
        ),
    )


# ------------------------------------------------------------------------------------------
# Layout and drawing primitives
# ------------------------------------------------------------------------------------------
class Layout:
    """Desktop: four panels in a row. Mobile: the same panels as a 2 x 2 grid of equal size."""

    def __init__(self, mobile):
        self.mobile = mobile
        self.W = 4.1 if mobile else 8.2
        self.x0 = 0.14 if mobile else 0.16
        self.cols = 2 if mobile else 4
        self.rows = 4 // self.cols
        self.gap = 0.12
        self.panel = (self.W - 2 * self.x0 - (self.cols - 1) * self.gap) / self.cols
        self.suffix = "-mobile" if mobile else ""
        self.dpi = 240 if mobile else 200  # designed at 100 px per inch, saved at 2x or more

    def x(self, i):
        return self.x0 + (i % self.cols) * (self.panel + self.gap)

    def row(self, i):
        return i // self.cols


class Canvas:
    """Place axes and text in inches measured from the top-left corner."""

    def __init__(self, width, height, dpi=100):
        self.W, self.H = width, height
        self.fig = plt.figure(figsize=(width, height), dpi=dpi, facecolor="white")

    def ax(self, x, y, w, h):
        return self.fig.add_axes([x / self.W, 1 - (y + h) / self.H, w / self.W, h / self.H])

    def text(self, x, y, s, **kw):
        return self.fig.text(x / self.W, 1 - y / self.H, s, **kw)

    def width_of(self, artist):
        self.fig.canvas.draw()
        return artist.get_window_extent().width / self.fig.dpi


class Clock:
    """Elapsed time: a fixed "t =" and a right-aligned value in a slot sized for the longest one.

    Digits share one width and every value shows one decimal, so nothing moves between frames.
    """

    def __init__(self, cv, right, y, longest):
        self.value = cv.text(right, y, f"{longest:.1f}", fontsize=10, ha="right", va="top")
        cv.text(right - cv.width_of(self.value) - 0.05, y, "t =", fontsize=10, ha="right", va="top")

    def set(self, t):
        self.value.set_text(f"{t:.1f}")


def field_axes(cv, x, y, size, f, titled=True):
    ax = cv.ax(x, y, size, size)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(LINE)
        spine.set_linewidth(0.7)
    if titled:
        ax.add_patch(Rectangle((0.0, 1.045), 0.05, 0.05, transform=ax.transAxes, color=f["hue"], clip_on=False))
        sym = ax.text(0.075, 1.035, f["sym"], transform=ax.transAxes, fontsize=10.5, fontweight="bold", va="bottom")
        ax.annotate(
            f["role"],
            xy=(1, 0),
            xycoords=sym,
            xytext=(5, 0),
            textcoords="offset points",
            fontsize=9.5,
            va="bottom",
            color=MUTED,
        )
    return ax


def show(ax, img, f, center=(0.0, 0.0), half=LAB, interpolation="bilinear"):
    image = ax.imshow(img, cmap=f["cmap"], norm=norm(f), extent=CENTER_EXTENT, interpolation=interpolation, zorder=0)
    ax.set_xlim(center[1] - half, center[1] + half)
    ax.set_ylim(center[0] + half, center[0] - half)
    return image


def colorbar(cv, f, x, y, w, h=0.07):
    cax = cv.ax(x, y, w, h)
    bar = cv.fig.colorbar(ScalarMappable(norm=norm(f), cmap=f["cmap"]), cax=cax, orientation="horizontal")
    bar.set_ticks(f["ticks"])
    bar.set_ticklabels([f"{t:g}" for t in f["ticks"]])
    bar.outline.set_edgecolor(LINE)
    bar.outline.set_linewidth(0.5)
    cax.tick_params(labelsize=7.5, length=2, width=0.5, color=MUTED, labelcolor=MUTED, pad=1.5)
    cax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())


WHITE_STROKE = [pe.withStroke(linewidth=2.6, foreground="white")]


def sensors(ax, rel_nodes, device, alpha=1.0):
    marker, size = ("o", 4.6) if device == 0 else ("s", 4.0)
    halo = ax.plot(
        [], [], marker, ms=size + 1.6, mfc="none", mec="white", mew=2.2, ls="none", alpha=0.85 * alpha, zorder=5
    )[0]
    core = ax.plot([], [], marker, ms=size, mfc="none", mec=INK, mew=0.95, ls="none", alpha=alpha, zorder=5.1)[0]
    for artist in (halo, core):
        artist.set_data(rel_nodes[:, 1], rel_nodes[:, 0])
    return halo, core


def source(ax, rel_center, color=INK):
    halo = ax.plot([], [], "+", ms=8, mew=3.4, color="white", alpha=0.85, zorder=6)[0]
    core = ax.plot([], [], "+", ms=8, mew=1.5, color=color, zorder=6.1)[0]
    for artist in (halo, core):
        artist.set_data([rel_center[1]], [rel_center[0]])
    return halo, core


def scalebar(ax, length=5):
    (x_lo, x_hi), y_hi = ax.get_xlim(), ax.get_ylim()[0]
    span = x_hi - x_lo
    x0, y0 = x_lo + 0.07 * span, y_hi - 0.08 * span
    ax.plot(
        [x0, x0 + length],
        [y0, y0],
        color=INK,
        lw=1.4,
        solid_capstyle="butt",
        zorder=8,
        path_effects=[pe.withStroke(linewidth=3.2, foreground="white")],
    )
    ax.text(
        x0 + length / 2,
        y0 - 0.03 * span,
        f"{length} units",
        ha="center",
        va="bottom",
        fontsize=7.5,
        zorder=8,
        path_effects=[pe.withStroke(linewidth=2.4, foreground="white")],
    )


def legend(cv, x, y, items, vertical=False):
    """Inline legend: items are ('d0' | 'd1' | 'src' | 'ring:<field>', label)."""
    ax = cv.ax(x, y, cv.W - x, 0.22 * (len(items) if vertical else 1))
    ax.set_xlim(0, cv.W - x)
    ax.set_ylim(len(items) - 0.5 if vertical else 0.5, -0.5)
    ax.axis("off")
    cx = 0.06
    for k, (kind, label) in enumerate(items):
        yy = k if vertical else 0
        cx = 0.06 if vertical else cx
        if kind == "d0":
            ax.plot(cx, yy, "o", ms=4.6, mfc="none", mec=INK, mew=0.95)
        elif kind == "d1":
            ax.plot(cx, yy, "s", ms=4.0, mfc="none", mec=INK, mew=0.95)
        elif kind == "src":
            ax.plot(cx, yy, "+", ms=8, mew=1.5, color=INK)
        text = ax.text(cx + 0.14, yy, label, va="center", fontsize=8.5)
        if not vertical:
            cx += 0.14 + cv.width_of(text) + 0.32


def save(cv, name, layout):
    path = OUT / f"{name}{layout.suffix}.png"
    cv.fig.savefig(path, dpi=layout.dpi, metadata={"Software": None})
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return path


# ------------------------------------------------------------------------------------------
# Static figures
# ------------------------------------------------------------------------------------------
def fig_fields(lab, runs, L):
    """BF is four fields: the preparation every experiment starts from, in the world view."""
    title, bar = 0.30, 0.42
    row_h = title + L.panel + bar
    cv = Canvas(L.W, 0.04 + L.rows * row_h)
    center = WORLD_OFFSET
    for i, f in enumerate(FIELDS):
        y = 0.04 + title + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        show(ax, runs["sham"]["crops"][0, i], f, center, WORLD)
        colorbar(cv, f, L.x(i), y + L.panel + 0.07, L.panel)
        if i == 0:
            scalebar(ax, 10)
    return save(cv, "bf-fields", L), dict(time=0, view_center_from_device=list(WORLD_OFFSET), half_width=WORLD)


def fig_grid(lab, runs, L):
    """The continuous picture and the discrete grid: whole domain, one blob, then individual cells."""
    f = FIELDS[0]
    rows, cols = [(np.arange(-N // 2, N // 2) + c) % N for c in np.floor(lab.center / DX).astype(int)]
    whole = lab.fields[0][rows][:, cols]  # periodic domain, centered on the devices' blob
    ext = [(-N // 2 - 0.5) * DX, (N // 2 - 0.5) * DX, (N // 2 - 0.5) * DX, (-N // 2 - 0.5) * DX]
    cells = (np.arange(N) - N // 2) * DX
    blob_half = 8.0
    cy0, cx0 = -1.0, 2.0  # lower-left cell center of the 6 x 6 cell window on the blob's flank
    gy = cells[(cells >= cy0 - 1e-9) & (cells < cy0 + 3.0 - 1e-9)]
    gx = cells[(cells >= cx0 - 1e-9) & (cells < cx0 + 3.0 - 1e-9)]
    win = [gx[0] - DX / 2, gx[-1] + DX / 2, gy[-1] + DX / 2, gy[0] - DX / 2]

    size = L.panel * (2.0 if L.mobile else 1.22)
    small = L.panel if L.mobile else size
    gap = 0.12 if L.mobile else (L.W - 2 * L.x0 - 3 * size) / 2
    if L.mobile:
        xa, ya, xb, yb, xc, yc = L.x0, 0.34, L.x0, 0.34 + size + 0.62, L.x0 + small + gap, 0.34 + size + 0.62
        height = yb + small + 0.42
    else:
        xa = L.x0
        xb, xc = xa + size + gap, xa + 2 * (size + gap)
        ya = yb = yc = 0.34
        height = 0.34 + size + 0.44
    cv = Canvas(L.W, height)

    a = field_axes(cv, xa, ya, size, f)
    a.imshow(whole, cmap=f["cmap"], norm=norm(f), extent=ext, interpolation="bilinear")
    a.set_xlim(ext[0], ext[1])
    a.set_ylim(ext[2], ext[3])
    a.add_patch(Rectangle((-blob_half, -blob_half), 2 * blob_half, 2 * blob_half, fill=False, ec=INK, lw=0.9, zorder=5))
    scalebar(a, 20)

    b = field_axes(cv, xb, yb, small, f, titled=False)
    b.imshow(whole, cmap=f["cmap"], norm=norm(f), extent=ext, interpolation="bilinear")
    b.set_xlim(-blob_half, blob_half)
    b.set_ylim(blob_half, -blob_half)
    for sp in b.spines.values():
        sp.set_color(INK)
        sp.set_linewidth(0.9)
    b.add_patch(Rectangle((win[0], win[3]), win[1] - win[0], win[2] - win[3], fill=False, ec=INK, lw=0.9, zorder=5))
    scalebar(b, 2)

    c = field_axes(cv, xc, yc, small, f, titled=False)
    c.imshow(whole, cmap=f["cmap"], norm=norm(f), extent=ext, interpolation="nearest")
    c.set_xlim(win[0], win[1])
    c.set_ylim(win[2], win[3])
    for sp in c.spines.values():
        sp.set_color(INK)
        sp.set_linewidth(0.9)
    for e in np.arange(win[0], win[1] + 1e-9, DX):
        c.axvline(e, color="white", lw=1.2, zorder=2)
    for e in np.arange(win[3], win[2] + 1e-9, DX):
        c.axhline(e, color="white", lw=1.2, zorder=2)
    index = {round(v, 6): k for k, v in enumerate(cells)}
    for yy in gy:
        for xx in gx:
            v = whole[index[round(yy, 6)], index[round(xx, 6)]]
            rgba = f["cmap"](norm(f)(v))
            dark = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2] < 0.45
            c.plot(xx, yy - 0.13, ".", ms=2.2, color="white" if dark else INK, alpha=0.7, zorder=3)
            c.text(
                xx,
                yy + 0.06,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=6.2 if L.mobile else 7,
                color="white" if dark else INK,
                zorder=4,
            )

    for src, dst, box in ((a, b, (-blob_half, blob_half, blob_half, -blob_half)), (b, c, win)):
        x_right, y_top, y_bottom = box[1], box[3], box[2]
        if L.mobile and src is a:
            corners = (((box[0], y_bottom), (0, 1)), ((x_right, y_bottom), (1, 1)))
        else:
            corners = (((x_right, y_top), (0, 1)), ((x_right, y_bottom), (0, 0)))
        for xy, uv in corners:
            cv.fig.add_artist(
                ConnectionPatch(
                    xyA=xy, coordsA=src.transData, xyB=uv, coordsB=dst.transAxes, color=MUTED, lw=0.6, zorder=0
                )
            )
    labels = (
        (a, xa, ya + size, f"Whole domain: {N * DX:g} × {N * DX:g} units, periodic"),
        (b, xb, yb + small, f"{2 * blob_half:g} × {2 * blob_half:g} units around one blob"),
        (c, xc, yc + small, f"{len(gx)} × {len(gy)} grid points, spacing {DX:g}"),
    )
    for _, x, y, text in labels:
        cv.text(x, y + 0.08, text, fontsize=8.5, color=MUTED, va="top")
    meta = dict(
        field="u0",
        time=0,
        grid=[N, N],
        spacing=DX,
        domain=N * DX,
        zoom_half_width=blob_half,
        cell_window_yx=[[float(gy[0]), float(gy[-1])], [float(gx[0]), float(gx[-1])]],
    )
    return save(cv, "bf-grid", L), meta


def fig_apparatus(lab, runs, L):
    """Both devices and their shared source, drawn on every field at t = 0."""
    title = 0.30
    row_h = title + L.panel + 0.14
    legend_h = 0.66 if L.mobile else 0.24
    cv = Canvas(L.W, 0.04 + L.rows * row_h + legend_h + 0.06)
    for i, f in enumerate(FIELDS):
        y = 0.04 + title + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        show(ax, runs["sham"]["crops"][0, i], f)
        for k, device in enumerate(lab.devices):
            sensors(ax, lab.rel(device.node_positions()), k)
        source(ax, lab.rel(lab.center))
        if i == 0:
            scalebar(ax)
    legend(
        cv,
        L.x0 - 0.04,
        0.04 + L.rows * row_h,
        [
            ("d0", "Device 0 · 13 sensors, spacing 3"),
            ("d1", "Device 1 · 19 sensors, spacing 6"),
            ("src", "Source at both array centers"),
        ],
        vertical=L.mobile,
    )
    return save(cv, "bf-apparatus", L), dict(time=0, half_width=LAB)


def fig_sensor_grid(lab, runs, L, u=(0.2, -0.4, 0.1)):
    """One sensor between grid points: four u0 values, their bilinear weights, and the reading they make."""
    device = copy.deepcopy(lab.devices[0])
    R6._adjust_pose(device, list(u), np.eye(3))  # a small shift puts the sensors between grid points
    crop = runs["sham"]["crops"][0]
    nodes = device.node_positions()
    k = 1  # canonical ring-1 sensor on the +x side, on the flank of the excitation
    sy, sx = lab.rel(nodes)[k]
    gy, gx = sy / DX + HALF, sx / DX + HALF
    i0, j0 = int(np.floor(gy)), int(np.floor(gx))
    fy, fx = gy - i0, gx - j0
    corners = [(0, 0), (0, 1), (1, 0), (1, 1)]  # top-left, top-right, bottom-left, bottom-right
    weights = {(0, 0): (1 - fy) * (1 - fx), (0, 1): (1 - fy) * fx, (1, 0): fy * (1 - fx), (1, 1): fy * fx}
    values = {c: float(crop[0, i0 + c[0], j0 + c[1]]) for c in corners}
    reading = float(lab.read(crop, nodes[k : k + 1])[0, 0])
    direct = float(bilinear(lab.fields, nodes[k : k + 1], DX)[0, 0])
    if abs(reading - direct) > 1e-6 or abs(reading - sum(weights[c] * values[c] for c in corners)) > 1e-6:
        raise ValueError("sensor-grid reading differs from physim.devices.bilinear")
    f = FIELDS[0]
    size = L.panel
    top = 0.34
    cv = Canvas(L.W, top + size + 0.10 + (1.30 if L.mobile else 0.0))
    xl, xz = L.x(0), L.x(1)
    left = field_axes(cv, xl, top, size, f)
    show(left, crop[0], f)
    sensors(left, lab.rel(nodes), 0)
    source(left, lab.rel(device.center))
    scalebar(left)
    half = 0.75
    left.add_patch(Rectangle((sx - half, sy - half), 2 * half, 2 * half, fill=False, ec=INK, lw=0.9, zorder=9))

    zoom = cv.ax(xz, top, size, size)
    show(zoom, crop[0], f, (sy, sx), half, interpolation="nearest")
    zoom.set_xticks([])
    zoom.set_yticks([])
    for spine in zoom.spines.values():
        spine.set_color(INK)
        spine.set_linewidth(0.9)
    edges = (np.arange(2 * HALF + 1) - HALF - 0.5) * DX
    for e in edges:
        zoom.axvline(e, color="white", lw=1.0, alpha=0.75, zorder=1)
        zoom.axhline(e, color="white", lw=1.0, alpha=0.75, zorder=1)
    cells = (np.arange(2 * HALF) - HALF) * DX
    for (di, dj), weight in weights.items():
        cy, cx = cells[i0 + di], cells[j0 + dj]
        zoom.plot([sx, cx], [sy, cy], color=INK, lw=0.6 + 2.4 * weight, zorder=3, solid_capstyle="round")
        zoom.plot(cx, cy, "o", ms=5.5, color=INK, mec="white", mew=1.0, zorder=4)
        my, mx = sy + 0.55 * (cy - sy), sx + 0.55 * (cx - sx)
        zoom.text(
            mx,
            my,
            f"{weight:.2f}",
            ha="center",
            va="center",
            fontsize=7.5,
            color=MUTED,
            zorder=5,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9),
        )
        zoom.text(
            cx + (0.07 if dj else -0.07),
            cy + (0.07 if di else -0.07),
            f"{values[(di, dj)]:.2f}",
            ha="left" if dj else "right",
            va="top" if di else "bottom",
            fontsize=8.5,
            fontweight="bold",
            zorder=5,
            path_effects=WHITE_STROKE,
        )
    zoom.plot(sx, sy, "o", ms=10.5, mfc="white", mec=INK, mew=1.4, zorder=6)
    for ya, yb in ((sy - half, 1.0), (sy + half, 0.0)):
        cv.fig.add_artist(
            ConnectionPatch(
                xyA=(sx + half, ya),
                coordsA=left.transData,
                xyB=(0, yb),
                coordsB=zoom.transAxes,
                color=MUTED,
                lw=0.6,
                zorder=0,
            )
        )

    # The weighted sum, term by term in the same corner order: weight (muted) × value (bold).
    ex, ey = (L.x0 + 0.05, top + size + 0.30) if L.mobile else (L.x(2) + 0.10, top + 0.26 * size)
    line = 0.21
    for r, c in enumerate(corners):
        y = ey + r * line
        if r:
            cv.text(ex, y, "+", fontsize=9, va="center", family=MONO)
        cv.text(ex + 0.20, y, f"{weights[c]:.2f}", fontsize=9, va="center", family=MONO, color=MUTED)
        cv.text(ex + 0.62, y, "×", fontsize=9, va="center", family=MONO, color=MUTED)
        cv.text(ex + 1.30, y, f"{values[c]:.2f}", fontsize=9, va="center", ha="right", family=MONO, fontweight="bold")
    y = ey + 4 * line + 0.04
    cv.fig.add_artist(Line2D([ex / cv.W, (ex + 1.32) / cv.W], [1 - (y - 0.11) / cv.H] * 2, color=INK, lw=0.6))
    cv.text(ex, y, "=", fontsize=9, va="center", family=MONO)
    cv.text(ex + 1.30, y, f"{reading:.2f}", fontsize=9, va="center", ha="right", family=MONO, fontweight="bold")
    cv.text(ex + 1.45, y, "sensor reading", fontsize=8.5, va="center", color=MUTED)
    meta = dict(
        adjust_u=list(u),
        sensor="device 0, canonical index 1",
        position_from_device_center=[sy, sx],
        weights={f"{a}{b}": float(w) for (a, b), w in weights.items()},
        u0_values={f"{a}{b}": v for (a, b), v in values.items()},
        u0_reading=reading,
        time=0,
    )
    return save(cv, "bf-sensor-grid", L), meta


# ------------------------------------------------------------------------------------------
# Videos
# ------------------------------------------------------------------------------------------
def trace_axes(cv, x, y, w, h, f, tmax=50, limits=None, ticks=None):
    """Readings over time; a color strip beside the y axis doubles as the panel's color scale.

    `limits` zooms the readings axis (then linear); the strip keeps the field's own color scale.
    """
    label_w, strip_w = 0.26, 0.05
    ax = cv.ax(x + label_w + strip_w, y, w - label_w - strip_w, h)
    asinh = "linear_width" in f and limits is None
    if asinh:
        ax.set_yscale("asinh", linear_width=f["linear_width"])
    ticks = ticks or f["trace_ticks"]
    ax.set_ylim(*(limits or f["trace"]))
    ax.set_xlim(0, tmax)
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{v:g}" for v in ticks])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ticks = list(range(0, tmax + 1, 10))
    ax.set_xticks(ticks)
    ax.set_xticklabels(["0"] + [""] * (len(ticks) - 2) + [str(tmax)])
    ax.tick_params(labelsize=7, length=2, width=0.5, pad=1.5, colors=MUTED)
    ax.tick_params(axis="y", length=0, pad=strip_w * 72 + 2.5)  # labels sit outside the color strip
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3ccd4")
    ax.grid(axis="y", color="#eef1f4", lw=0.6, zorder=0)
    scale = cv.ax(x + label_w, y, strip_w, h)
    lo, hi = limits or f["trace"]
    if asinh:
        scale.set_yscale("asinh", linear_width=f["linear_width"])
        w0 = f["linear_width"]
        edges = np.sinh(np.linspace(np.arcsinh(lo / w0), np.arcsinh(hi / w0), 400)) * w0
    else:
        edges = np.linspace(lo, hi, 400)
    mids = 0.5 * (edges[1:] + edges[:-1])
    scale.pcolormesh([0, 1], edges, f["cmap"](norm(f)(mids))[:, None, :3], shading="flat", rasterized=True)
    scale.set_ylim(lo, hi)
    scale.axis("off")
    return ax


def film_canvas(L, rows):
    """A film frame: the clock row, then rows of field panels and readings at the panel size."""
    top, title = 0.40, 0.30
    row_h = title + L.panel + 0.34
    return Canvas(L.W, top + rows * row_h, dpi=L.dpi), top + title, row_h


def wide_axes(cv, L, y, slots=(1, 3)):
    """Axes spanning panel slots `slots` (inclusive) on a desktop row, or the second slot on a phone row."""
    first, last = (1, 1) if L.mobile else slots
    x0, x1 = L.x(first), L.x(last) + L.panel
    return x0, x1 - x0


def film_source(lab, runs, L, fps=6, hold=12, tmax=15.0, poster_t=5.0):
    """A source, mechanically: the x2 pulse builds a Gaussian bump at the device center while it is on."""
    run, f, k = runs["trail_pulse"], FIELDS[3], 3
    pulse = RUNS["trail_pulse"]["actions"][0]
    times = run["times"][run["times"] <= tmax + 1e-9]
    device = lab.devices[0]
    nodes = lab.rel(device.node_positions())
    on_line = np.flatnonzero(np.abs(nodes[:, 0]) < 1e-6)  # sensors on the line through the center
    cells = (np.arange(2 * HALF) - HALF) * DX
    keep = np.abs(cells) <= LAB
    cv, y, _ = film_canvas(L, 1)
    clock = Clock(cv, L.W - L.x0, 0.1, times.max())
    ax = field_axes(cv, L.x(0), y, L.panel, f)
    image = show(ax, run["crops"][0, k], f)
    ax.plot([-LAB, LAB], [0, 0], color=INK, lw=0.8, ls=(0, (3, 2)), alpha=0.7, zorder=4)
    sensors(ax, nodes, 0)
    marker = source(ax, (0.0, 0.0))
    scalebar(ax)
    x, w = wide_axes(cv, L, y)
    pad = 0.34
    prof = cv.ax(x + pad, y, w - pad, L.panel)
    prof.set_xlim(-LAB, LAB)
    prof.set_ylim(0, 0.3)
    prof.set_yticks([0, 0.1, 0.2, 0.3])
    prof.set_yticklabels(["0", "0.1", "0.2", "0.3"])
    prof.set_xticks([-15, -10, -5, 0, 5, 10, 15])
    prof.tick_params(labelsize=7, length=2, width=0.5, pad=1.5, colors=MUTED)
    for side in ("top", "right"):
        prof.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        prof.spines[side].set_color("#c3ccd4")
    prof.grid(axis="y", color="#eef1f4", lw=0.6, zorder=0)
    prof.set_xlabel("distance along the dashed line", fontsize=7.5, color=MUTED, labelpad=2)
    prof.plot(cells[keep], run["crops"][0, k, HALF, keep], color=GRAY_TRACE, lw=1.0, zorder=1)
    curve = prof.plot([], [], color=f["hue"], lw=1.6, zorder=2)[0]
    dots = prof.plot([], [], "o", ms=4.6, mfc="white", mec=INK, mew=0.95, ls="none", zorder=3)[0]
    state = prof.text(
        0.015, 0.97, "source on", transform=prof.transAxes, fontsize=8, color=f["hue"], fontweight="bold", va="top"
    )
    path, poster = OUT / f"bf-pulse{L.suffix}.mp4", OUT / f"bf-pulse{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            t = times[ti]
            crop = run["crops"][ti]
            image.set_data(crop[k])
            curve.set_data(cells[keep], crop[k, HALF, keep])
            dots.set_data(nodes[on_line, 1], lab.read(crop, device.node_positions()[on_line])[k])
            on = pulse["t"] - 1e-9 <= t < pulse["t"] + pulse["dur"] - 1e-9
            state.set_visible(on)
            marker[1].set_color(f["hue"] if on else INK)
            clock.set(t)
            frame(poster if n < len(times) and abs(t - poster_t) < 1e-9 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
        poster_time=poster_t,
        run="trail_pulse",
        field="x2",
        times=[0.0, tmax],
    )


def film_adjust(lab, runs, L, fps=12, hold=18, tmax=40.0, poster_t=40.0):
    """Adjustments, mechanically: device 0 shifts and dilates over x2, and its readings change with each move."""
    run, f, k = runs["walk"], FIELDS[3], 3
    actions = RUNS["walk"]["actions"]
    times = run["times"][run["times"] <= tmax + 1e-9]
    timeline = lab.poses(actions, times)
    readings = np.stack([lab.read(run["crops"][i], timeline[i]["nodes"][0])[k] for i in range(len(times))])
    moves = [a for a in actions if a["kind"] == "adjust" and a["device"] == 0]
    cv, y, _ = film_canvas(L, 1)
    clock = Clock(cv, L.W - L.x0, 0.1, times.max())
    ax = field_axes(cv, L.x(0), y, L.panel, f)
    image = show(ax, run["crops"][0, k], f)
    ghost = (
        ax.plot([], [], "o", ms=4.6, mfc="none", mec=INK, mew=0.8, alpha=0.3, ls="none", zorder=5)[0],
        ax.plot([], [], "+", ms=8, mew=1.2, color=INK, alpha=0.3, zorder=5)[0],
    )
    live = sensors(ax, np.zeros((0, 2)), 0) + source(ax, (np.nan, np.nan))
    scalebar(ax)
    x, w = wide_axes(cv, L, y)
    tr = trace_axes(cv, x, y, w, L.panel, f, tmax=int(tmax), limits=(0, 0.03), ticks=[0, 0.01, 0.02, 0.03])
    labels = {
        "down": [m["t"] for m in moves if m["u"][0]],
        "right": [m["t"] for m in moves if m["u"][1]],
        "dilate": [m["t"] for m in moves if m["u"][2]],
    }
    for word, ts in labels.items():
        for t0 in ts:
            tr.axvline(t0, color=MUTED, lw=0.5, ls=(0, (1, 1.5)), zorder=0.5)
        tr.text(
            np.mean(ts),
            1.02,
            word,
            transform=tr.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=MUTED,
        )
    lines = [tr.plot([], [], color=f["hue"], lw=0.9, alpha=0.9, zorder=2)[0] for _ in range(readings.shape[1])]
    cursor = tr.axvline(0, color=INK, lw=0.6, alpha=0.5, zorder=3)
    path, poster = OUT / f"bf-walk{L.suffix}.mp4", OUT / f"bf-walk{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            t, pose = times[ti], timeline[ti]
            image.set_data(run["crops"][ti, k])
            nodes, center = lab.rel(pose["nodes"][0]), lab.rel(pose["centers"][0])
            for artist in live[:2]:
                artist.set_data(nodes[:, 1], nodes[:, 0])
            for artist in live[2:]:
                artist.set_data([center[1]], [center[0]])
            recent = [m for m in moves if m["t"] <= t + 1e-9 and t - m["t"] < 2.5]
            if recent:
                j = int(np.flatnonzero(np.isclose(times, recent[-1]["t"]))[0])
                before = (
                    (lab.rel(lab.devices[0].node_positions()), lab.rel(lab.center))
                    if j == 0
                    else (lab.rel(timeline[j - 1]["nodes"][0]), lab.rel(timeline[j - 1]["centers"][0]))
                )
                ghost[0].set_data(before[0][:, 1], before[0][:, 0])
                ghost[1].set_data([before[1][1]], [before[1][0]])
            else:
                ghost[0].set_data([], [])
                ghost[1].set_data([], [])
            for s, line in enumerate(lines):
                line.set_data(times[: ti + 1], readings[: ti + 1, s])
            cursor.set_xdata([t, t])
            clock.set(t)
            frame(poster if n < len(times) and abs(t - poster_t) < 1e-9 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
        poster_time=poster_t,
        run="walk",
        field="x2",
        times=[0.0, tmax],
    )


def film_world(lab, film, L, fps=16, hold=16, poster_t=150.0):
    """Four fields over an unforced 300-time-unit continuation, in the world view."""
    times = film["times"]
    title, bar = 0.30, 0.42
    row_h = title + L.panel + bar
    top = 0.34
    cv = Canvas(L.W, top + L.rows * row_h, dpi=L.dpi)
    clock = Clock(cv, L.W - L.x0, 0.1, times.max())
    images = []
    for i, f in enumerate(FIELDS):
        y = top + title + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        images.append(show(ax, film["crops"][0, i], f, WORLD_OFFSET, WORLD))
        colorbar(cv, f, L.x(i), y + L.panel + 0.07, L.panel)
        if i == 0:
            scalebar(ax, 10)
    path, poster = OUT / f"bf-world{L.suffix}.mp4", OUT / f"bf-world{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            for i in range(4):
                images[i].set_data(film["crops"][ti, i])
            clock.set(times[ti])
            frame(poster if n < len(times) and abs(times[ti] - poster_t) < 1e-9 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
        poster_time=poster_t,
        times=[float(times[0]), float(times[-1])],
    )


def film_p4(film, L, fps=12, hold=12, poster_t=P4_POSTER_T):
    """Four of p4g2_044's twelve fields over an unforced continuation, displayed the way BF is."""
    times, frames = film["times"], film["frames"]
    cells = round(P4_HALF / DX)
    rows, cols = [(np.arange(-cells, cells) + round(c / DX)) % N for c in P4_CENTER]
    crop = lambda ti, k: frames[ti, k][rows][:, cols].astype(np.float32)  # noqa: E731
    extent = [(-cells - 0.5) * DX, (cells - 0.5) * DX, (cells - 0.5) * DX, (-cells - 0.5) * DX]
    title, bar = 0.30, 0.42
    row_h = title + L.panel + bar
    top = 0.34
    cv = Canvas(L.W, top + L.rows * row_h, dpi=L.dpi)
    cv.text(L.x0, 0.1, "4 of 12 fields · unforced continuation", fontsize=8.5, color=MUTED, va="top")
    clock = Clock(cv, L.W - L.x0, 0.1, times.max())
    images = []
    for i, f in enumerate(P4_FIELDS):
        y = top + title + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        images.append(
            ax.imshow(crop(0, f["index"]), cmap=f["cmap"], norm=norm(f), extent=extent, interpolation="bilinear")
        )
        ax.set_xlim(-P4_HALF, P4_HALF)
        ax.set_ylim(P4_HALF, -P4_HALF)
        colorbar(cv, f, L.x(i), y + L.panel + 0.07, L.panel)
        if i == 0:
            scalebar(ax, 20)
    path, poster = OUT / f"p4g2_044-highlights{L.suffix}.mp4", OUT / f"p4g2_044-highlights{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            for image, f in zip(images, P4_FIELDS):
                image.set_data(crop(ti, f["index"]))
            clock.set(times[ti])
            frame(poster if n < len(times) and abs(times[ti] - poster_t) < 1e-9 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
        poster_time=poster_t,
        times=[float(times[0]), float(times[-1])],
        view=dict(center_yx=list(P4_CENTER), half_width=P4_HALF),
        fields=[
            {k: f[k] for k in ("key", "index", "role", "hue", "vmin", "vmax", "ticks", "reverse") if k in f}
            for f in P4_FIELDS
        ],
    )


# ------------------------------------------------------------------------------------------
# What an evaluation experiment is scored on
# ------------------------------------------------------------------------------------------
QUERY_TIMES = [0, 2, 5, 8, 10, 12, 15, 20, 22, 25, 30, 35, 40, 45, 50]  # every BF suite query
SCORE_CASE = ("c006", "High trail pulse", "trail_pulse", "sham")


def scoring_groups():
    """The BF suite's score groups, taken from the suite builder itself and restated in world terms."""
    sys.path.insert(0, str(ROOT / "generators/physim"))
    from build_evaluation_bundle import score_groups

    case = dict(
        id=SCORE_CASE[0],
        actions=RUNS[SCORE_CASE[2]]["actions"],
        queries=[dict(sensor=s, t=QUERY_TIMES) for s in ("device0", "device1", "global")],
    )
    groups = []
    for group in score_groups(case, PORT_PERM):
        selectors = group["selectors"]
        queries, ports, scales = {s["query"] for s in selectors}, {s["port"] for s in selectors}, set(group["scales"])
        if len(queries) != 1 or len(ports) != 1 or len(scales) != 1:
            raise ValueError("expected one sensor, one port and one scale per BF score group")
        times = sorted({QUERY_TIMES[s["time_index"]] for s in selectors})
        slots = sorted({s["slot"] for s in selectors})
        if len(selectors) != len(times) * len(slots):
            raise ValueError("expected every selected slot at every selected time")
        port = ports.pop()
        groups.append(
            dict(
                id=group["id"],
                name=group["id"].replace("_", " "),
                device=queries.pop(),
                port=port,
                field=PORT_PERM[port],
                times=times,
                slots=slots,
                scale=scales.pop(),
                size=len(selectors),
            )
        )
    return case, groups


def film_scored(lab, runs, L, fps=12, hold=24, poster_t=50.0):
    """The high trail pulse at device 0: u0 and x2 with their readings, scored readings marked as taken."""
    _, groups = scoring_groups()
    scored = {g["field"]: g["times"] for g in groups if g["device"] == 0 and g["field"] in (0, 3)}
    run = runs["trail_pulse"]
    pulse = RUNS["trail_pulse"]["actions"][0]
    times = run["times"]
    device = lab.devices[0]
    nodes = lab.rel(device.node_positions())
    readings = np.stack([lab.read(c, device.node_positions()) for c in run["crops"]])
    cv, y0, row_h = film_canvas(L, 2 if L.mobile else 1)
    clock = Clock(cv, L.W - L.x0, 0.1, times.max())
    panels = []
    for n, k in enumerate((0, 3)):
        f = FIELDS[k]
        slot = 0 if L.mobile else 2 * n
        y = y0 + (n * row_h if L.mobile else 0)
        ax = field_axes(cv, L.x(slot), y, L.panel, f)
        image = show(ax, run["crops"][0, k], f)
        sensors(ax, nodes, 0)
        marker = source(ax, (0.0, 0.0))
        if n == 0:
            scalebar(ax)
        tr = trace_axes(cv, L.x(slot + 1), y, L.panel, L.panel, f)
        tr.axvspan(pulse["t"], pulse["t"] + pulse["dur"], color=FIELDS[3]["hue"], alpha=0.12, lw=0, zorder=0)
        tr.text(
            pulse["t"] + pulse["dur"] / 2,
            1.02,
            "pulse",
            transform=tr.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=MUTED,
        )
        for t0 in scored[k]:
            tr.axvline(t0, color="#c3ccd4", lw=0.6, zorder=0.5)
        lines = [tr.plot([], [], color=f["hue"], lw=0.9, alpha=0.85, zorder=2)[0] for _ in range(len(nodes))]
        stamps = []
        for t0 in scored[k]:
            ti = int(np.flatnonzero(np.isclose(times, t0))[0])
            stamps.append(
                (
                    t0,
                    tr.plot(
                        [t0] * len(nodes),
                        readings[ti, k],
                        "o",
                        ms=3.2,
                        color=f["hue"],
                        mec="white",
                        mew=0.6,
                        zorder=4,
                        visible=False,
                    )[0],
                )
            )
        panels.append((k, image, marker, lines, stamps))
    path, poster = OUT / f"bf-score{L.suffix}.mp4", OUT / f"bf-score{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            t = times[ti]
            on = pulse["t"] - 1e-9 <= t < pulse["t"] + pulse["dur"] - 1e-9
            for k, image, marker, lines, stamps in panels:
                image.set_data(run["crops"][ti, k])
                marker[1].set_color(FIELDS[k]["hue"] if (on and k == 3) else INK)
                for s, line in enumerate(lines):
                    line.set_data(times[: ti + 1], readings[: ti + 1, k, s])
                for t0, dots in stamps:
                    dots.set_visible(t >= t0 - 1e-9)
            clock.set(t)
            frame(poster if n == len(order) - 1 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
        run="trail_pulse",
        device=0,
        scored_times={FIELDS[k]["key"]: ts for k, ts in scored.items()},
        score_groups_source="generators/physim/build_evaluation_bundle.py::score_groups",
    )


# ------------------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    names = [
        "fields",
        "grid",
        "apparatus",
        "sensor-grid",
        "world",
        "pulse",
        "walk",
        "score-video",
        "p4-film",
    ]
    parser.add_argument("--only", nargs="*", choices=names, help="Render a subset of figures")
    parser.add_argument("--layout", choices=["desktop", "mobile", "both"], default="both")
    args = parser.parse_args()
    selected = args.only or names
    layouts = [Layout(m) for m in {"desktop": [False], "mobile": [True], "both": [False, True]}[args.layout]]
    OUT.mkdir(parents=True, exist_ok=True)

    lab = Lab()
    runs = {name: lab.run(name) for name in RUNS}
    checks = verify(lab, runs)
    print("verified:", checks, flush=True)
    film = lab.continuation() if "world" in selected else None
    p4_film = p4_continuation() if "p4-film" in selected else None

    record_path = OUT / "provenance.json"
    figures = {}
    for L in layouts:
        tag = "mobile" if L.mobile else "desktop"
        for name in selected:
            if name == "world":
                meta = film_world(lab, film, L)
            elif name == "pulse":
                meta = film_source(lab, runs, L)
            elif name == "walk":
                meta = film_adjust(lab, runs, L)
            elif name == "score-video":
                meta = film_scored(lab, runs, L)
            elif name == "p4-film":
                meta = film_p4(p4_film, L)
            else:
                fn = {
                    "fields": fig_fields,
                    "grid": fig_grid,
                    "apparatus": fig_apparatus,
                    "sensor-grid": fig_sensor_grid,
                }[name]
                path, meta = fn(lab, runs, L)
                meta = dict(meta, file=str(path.relative_to(OUT)))
            figures.setdefault(name, {})[tag] = meta

    devices = [
        dict(
            lattice=d.lattice,
            n_rings=d.n_rings,
            spacing=d.base_ds,
            center_yx=d.center.tolist(),
            node_perm=d.node_perm.tolist(),
        )
        for d in lab.devices
    ]
    record = dict(
        description="BF thread figures: native simulations of the recorded BF preparation; no inference.",
        script="scripts/render_bf_thread.py",
        script_sha256=digest(__file__),
        inputs=dict(
            genome=dict(path=f"registry/artifact/{GENOME_SHA}.bin", sha256=GENOME_SHA),
            preparation=dict(
                path=f"registry/artifact/{PREPARATION_SHA}.bin", sha256=PREPARATION_SHA, field_sha256=FIELD_SHA
            ),
            recorded_evidence=dict(path=str(EVIDENCE.relative_to(ROOT)), sha256=digest(EVIDENCE)),
        ),
        apparatus=dict(
            protocol=R6.APPARATUS_PROTOCOL,
            port_permutation=PORT_PERM,
            devices=devices,
            rule="generators/physim/eval_preparation.py: center at the activator-0 maximum, "
            "node permutations from default_rng(41001)",
        ),
        numerics=dict(grid=[N, N], L=128.0, dx=DX, dt=R6.SIM_DT, noise=0.002, dtype="float32"),
        runs={
            name: dict(
                actions=spec["actions"],
                feedback=spec["feedback"],
                note=spec["note"],
                truth_seed=SEED,
                member=0,
                record_dt=0.5,
                horizon=50.0,
                cache_sha256=digest(runs[name]["path"]),
            )
            for name, spec in RUNS.items()
        },
        film=(
            dict(
                seed=FILM_SEED,
                horizon=300.0,
                record_dt=2.5,
                cache_sha256=digest(film["path"]),
                construction="scripts/render_world_movies.py capture('bf')",
            )
            if film
            else None
        ),
        p4_film=(
            dict(
                reference_bundle=p4_film["reference"],
                field_sha256=P4_FIELD_SHA,
                seed=P4_FILM_SEED,
                horizon=450.0,
                record_dt=2.5,
                cache_sha256=digest(p4_film["path"]),
                construction="scripts/render_world_movies.py capture('p4g2_044')",
            )
            if p4_film
            else None
        ),
        verification=checks,
        display=dict(
            fields=[
                {k: f[k] for k in ("key", "role", "hue", "vmin", "vmax", "ticks") if k in f}
                | ({"asinh_linear_width": f["linear_width"]} if "linear_width" in f else {})
                for f in FIELDS
            ],
            lab_view=dict(center="device center", half_width=LAB),
            world_view=dict(center_offset_from_device_yx=list(WORLD_OFFSET), half_width=WORLD),
            glyphs="device 0 circles, device 1 squares, source plus; pulse ring of radius sigma on its field only",
        ),
        figures=figures,
    )
    # Merge with entries written meanwhile by other invocations (e.g. one per figure).
    previous = json.loads(record_path.read_text()) if record_path.exists() else {}
    merged = {k: v for k, v in previous.get("figures", {}).items() if k in names}
    for name, entry in figures.items():
        merged.setdefault(name, {}).update(entry)
    record["figures"] = dict(sorted(merged.items()))
    for key in ("film", "p4_film"):
        if record[key] is None:
            record[key] = previous.get(key)
    record_path.write_text(json.dumps(record, indent=2, default=float) + "\n")
    print("wrote", record_path.relative_to(ROOT))


if __name__ == "__main__":
    main()

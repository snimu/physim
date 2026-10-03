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
from matplotlib.patches import Circle, ConnectionPatch, Rectangle
from physim import blobround6 as R6
from physim.bundles import Bundle
from physim.devices import INJ_SIGMA, ProbeDevice, bilinear, step_chunk

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
        + [adjust([0, 1, 0], t=15), inject(2, 0.05, t=18)]
        + [adjust([0, 1, 0], t=t) for t in (20, 25)]
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


def column_title(cv, x, y, size, f):
    """Field title placed in inches, matching the title field_axes draws above a panel."""
    cv.fig.add_artist(
        Rectangle(
            (x / cv.W, 1 - (y - 0.045 * size) / cv.H),
            0.05 * size / cv.W,
            0.05 * size / cv.H,
            color=f["hue"],
            transform=cv.fig.transFigure,
        )
    )
    sym = cv.text(x + 0.075 * size, y - 0.035 * size, f["sym"], fontsize=10.5, fontweight="bold", va="bottom")
    cv.fig.add_artist(
        matplotlib.text.Annotation(
            f["role"],
            xy=(1, 0),
            xycoords=sym,
            xytext=(5, 0),
            textcoords="offset points",
            fontsize=9.5,
            va="bottom",
            color=MUTED,
        )
    )


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


def pulse_ring(ax, f):
    """Dashed circle of radius sigma at a pulse's latched launch position (shown on its field only)."""
    under = Circle((0, 0), INJ_SIGMA, fill=False, ec="white", lw=2.6, alpha=0.8, zorder=4, visible=False)
    ring = Circle((0, 0), INJ_SIGMA, fill=False, ec=f["hue"], lw=1.4, ls=(0, (2.5, 1.6)), zorder=4.1, visible=False)
    ax.add_patch(under)
    ax.add_patch(ring)
    return under, ring


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
    """One sensor between grid cells: bilinear weights, applied to every field."""
    device = copy.deepcopy(lab.devices[0])
    R6._adjust_pose(device, list(u), np.eye(3))  # the article's example adjustment
    crop = runs["sham"]["crops"][0]
    nodes = device.node_positions()
    k = 1  # canonical ring-1 sensor on the +x side, on the flank of the excitation
    sy, sx = lab.rel(nodes)[k]
    gy, gx = sy / DX + HALF, sx / DX + HALF
    i0, j0 = int(np.floor(gy)), int(np.floor(gx))
    fy, fx = gy - i0, gx - j0
    weights = {(0, 0): (1 - fy) * (1 - fx), (0, 1): (1 - fy) * fx, (1, 0): fy * (1 - fx), (1, 1): fy * fx}
    values = lab.read(crop, nodes[k : k + 1])[:, 0]
    direct = bilinear(lab.fields, nodes[k : k + 1], DX)[:, 0]
    if not np.allclose(values, direct, rtol=0, atol=1e-6):
        raise ValueError("sensor-grid reading differs from physim.devices.bilinear")
    f = FIELDS[0]
    size = L.panel
    text_x, text_y = (L.x0, 0.34 + size + 0.32) if L.mobile else (2 * size + 2 * 0.62 + 0.06, 0.34)
    cv = Canvas(L.W, (0.34 + size + 0.32 + 1.95) if L.mobile else 0.34 + size + 0.1)
    xl, xz = L.x0, L.x0 + size + (0.12 if L.mobile else 0.56)
    left = field_axes(cv, xl, 0.34, size, f)
    show(left, crop[0], f)
    sensors(left, lab.rel(nodes), 0)
    source(left, lab.rel(device.center))
    scalebar(left)
    half = 1.25
    left.add_patch(Rectangle((sx - half, sy - half), 2 * half, 2 * half, fill=False, ec=INK, lw=0.9, zorder=9))

    zoom = cv.ax(xz, 0.34, size, size)
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
    near_y, near_x = cells[np.abs(cells - sy) < half], cells[np.abs(cells - sx) < half]
    yy, xx = np.meshgrid(near_y, near_x, indexing="ij")
    zoom.plot(xx.ravel(), yy.ravel(), ".", color=INK, ms=2.4, alpha=0.5, zorder=2)
    for (di, dj), weight in weights.items():
        cy, cx = cells[i0 + di], cells[j0 + dj]
        zoom.plot([sx, cx], [sy, cy], color=INK, lw=0.9, zorder=3, path_effects=WHITE_STROKE)
        zoom.plot(cx, cy, "o", ms=4.6, color=INK, mec="white", mew=1.0, zorder=4)
        zoom.text(
            cx + (0.12 if dj else -0.12),
            cy + (0.13 if di else -0.13),
            f"{weight:.2f}",
            ha="left" if dj else "right",
            va="top" if di else "bottom",
            fontsize=8,
            zorder=5,
            path_effects=WHITE_STROKE,
        )
    zoom.plot(sx, sy, "o", ms=10.5, mfc="white", mec="white", mew=3.2, zorder=6)
    zoom.plot(sx, sy, "o", ms=10.5, mfc="white", mec=INK, mew=1.4, zorder=6.1)
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
    cv.text(xz, 0.27, "Grid cells, 0.5 units wide", fontsize=8.5, color=MUTED, va="bottom")

    cv.text(text_x, text_y + 0.02, "One sensor, four readings", fontsize=10, fontweight="bold", va="top")
    cv.text(
        text_x,
        text_y + 0.30,
        "Weights from the four nearest cells\n(bilinear interpolation), applied to\nevery field at this position:",
        fontsize=8.5,
        va="top",
        color=MUTED,
        linespacing=1.35,
    )
    for i, fld in enumerate(FIELDS):
        ty = text_y + 1.0 + i * 0.25
        cv.fig.add_artist(
            Rectangle(
                (text_x / cv.W, 1 - (ty + 0.07) / cv.H),
                0.12 / cv.W,
                0.14 / cv.H,
                color=fld["hue"],
                transform=cv.fig.transFigure,
            )
        )
        cv.text(text_x + 0.2, ty, fld["sym"], fontsize=9.5, fontweight="bold", va="center")
        cv.text(text_x + 0.5, ty, fld["role"], fontsize=8.5, va="center", color=MUTED)
        cv.text(text_x + 2.6, ty, f"{values[i]:.4f}", fontsize=9.5, va="center", ha="right", family=MONO)
    meta = dict(
        adjust_u=list(u),
        sensor="device 0, canonical index 1",
        position_from_device_center=[sy, sx],
        weights={f"{a}{b}": float(w) for (a, b), w in weights.items()},
        readings=values.tolist(),
        time=0,
    )
    return save(cv, "bf-sensor-grid", L), meta


# ------------------------------------------------------------------------------------------
# Videos
# ------------------------------------------------------------------------------------------
def trace_axes(cv, x, y, w, h, f, tmax=50):
    """Readings over time; a color strip beside the y axis doubles as the panel's color scale."""
    label_w, strip_w = 0.26, 0.05
    ax = cv.ax(x + label_w + strip_w, y, w - label_w - strip_w, h)
    if "linear_width" in f:
        ax.set_yscale("asinh", linear_width=f["linear_width"])
    ax.set_ylim(*f["trace"])
    ax.set_xlim(0, tmax)
    ax.set_yticks(f["trace_ticks"])
    ax.set_yticklabels([f"{v:g}" for v in f["trace_ticks"]])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(range(0, tmax + 1, 10))
    ax.set_xticklabels(["0", "", "", "", "", str(tmax)])
    ax.tick_params(labelsize=7, length=2, width=0.5, pad=1.5, colors=MUTED)
    ax.tick_params(axis="y", length=0, pad=strip_w * 72 + 2.5)  # labels sit outside the color strip
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3ccd4")
    ax.grid(axis="y", color="#eef1f4", lw=0.6, zorder=0)
    scale = cv.ax(x + label_w, y, strip_w, h)
    lo, hi = f["trace"]
    if "linear_width" in f:
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


def anim_experiment(lab, runs, L, run_name, header, subheader, name, gray=None, poster_t=40.0, fps=12, hold=18):
    """Field panels with device 0 at its protocol pose, and device-0 reading traces under each field."""
    run = runs[run_name]
    actions = RUNS[run_name]["actions"]
    times = run["times"]
    timeline = lab.poses(actions, times)
    readings = np.stack([lab.read(run["crops"][i], timeline[i]["nodes"][0]) for i in range(len(times))])
    twin = np.stack([lab.read(c, lab.devices[0].node_positions()) for c in runs[gray]["crops"]]) if gray else None
    pulses = [a for a in actions if a["kind"] == "inject"]
    moves = [a for a in actions if a["kind"] == "adjust" and a["device"] == 0]
    head_lines = header.count("\n") + subheader.count("\n") + 2
    top = 0.24 + 0.2 * head_lines + 0.34
    trace_h = 1.0
    row_h = L.panel + 0.30 + trace_h + 0.48
    cv = Canvas(L.W, top + L.rows * row_h + 0.12, dpi=L.dpi)
    cv.text(L.x0, 0.12, header, fontsize=8.6 if L.mobile else 9, va="top", family=MONO, linespacing=1.35)
    cv.text(
        L.x0,
        0.14 + 0.2 * (header.count("\n") + 1) + 0.06,
        subheader,
        fontsize=8.5,
        color=MUTED,
        va="top",
        linespacing=1.35,
    )
    clock = cv.text(L.W - L.x0, 0.12, "t = 0", fontsize=10, ha="right", va="top")
    images, live, ghosts, rings, curves, twins, cursors = [], [], [], [], [], [], []
    for i, f in enumerate(FIELDS):
        y = top + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        images.append(show(ax, run["crops"][0, i], f))
        ghost = (
            ax.plot([], [], "o", ms=4.6, mfc="none", mec=INK, mew=0.8, alpha=0.3, ls="none", zorder=5)[0],
            ax.plot([], [], "+", ms=8, mew=1.2, color=INK, alpha=0.3, zorder=5)[0],
        )
        ghosts.append(ghost)
        live.append(sensors(ax, np.zeros((0, 2)), 0) + source(ax, (np.nan, np.nan)))
        rings.append([(p, *pulse_ring(ax, f)) for p in pulses if PORT_PERM[p["port"]] == i])
        if i == 0:
            scalebar(ax)
        tr = trace_axes(cv, L.x(i), y + L.panel + 0.30, L.panel, trace_h, f)
        for p in pulses:
            tr.axvspan(p["t"], p["t"] + p["dur"], color=FIELDS[PORT_PERM[p["port"]]]["hue"], alpha=0.12, lw=0, zorder=0)
        for m in moves:
            tr.axvline(m["t"], color=MUTED, lw=0.5, ls=(0, (1, 1.5)), zorder=0.5)
        twins.append([tr.plot([], [], color=GRAY_TRACE, lw=0.7, zorder=1)[0] for _ in range(13)] if gray else [])
        curves.append([tr.plot([], [], color=f["hue"], lw=0.9, alpha=0.9, zorder=2)[0] for _ in range(13)])
        cursors.append(tr.axvline(0, color=INK, lw=0.6, alpha=0.5, zorder=3))
    caption = (
        "Device-0 readings: colored with the pulse, gray without it."
        if gray
        else "Device-0 readings; dotted lines mark moves."
    )
    cv.text(L.x0, cv.H - 0.06, caption, fontsize=8.5, color=MUTED, va="bottom")

    launched_at = {}
    for state in timeline:
        for p in state["active"]:
            launched_at.setdefault((p["t"], p["port"]), p["center"])
    path, poster = OUT / f"{name}{L.suffix}.mp4", OUT / f"{name}{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            t, state = times[ti], timeline[ti]
            nodes, center = lab.rel(state["nodes"][0]), lab.rel(state["centers"][0])
            # For 2.5 time units after a move, a faint ghost shows the pose just before it.
            recent = [m for m in moves if m["t"] <= t + 1e-9 and t - m["t"] < 2.5]
            before = None
            if recent:
                k = int(np.flatnonzero(np.isclose(times, recent[-1]["t"]))[0])
                before = (
                    (lab.rel(lab.devices[0].node_positions()), lab.rel(lab.center))
                    if k == 0
                    else (lab.rel(timeline[k - 1]["nodes"][0]), lab.rel(timeline[k - 1]["centers"][0]))
                )
            active = {(p["t"], p["port"]): p for p in state["active"]}
            for i in range(4):
                images[i].set_data(run["crops"][ti, i])
                s_halo, s_core, c_halo, c_core = live[i]
                for artist in (s_halo, s_core):
                    artist.set_data(nodes[:, 1], nodes[:, 0])
                for artist in (c_halo, c_core):
                    artist.set_data([center[1]], [center[0]])
                g_nodes, g_src = ghosts[i]
                if before is not None:
                    g_nodes.set_data(before[0][:, 1], before[0][:, 0])
                    g_src.set_data([before[1][1]], [before[1][0]])
                else:
                    g_nodes.set_data([], [])
                    g_src.set_data([], [])
                lit = False
                for p, under, ring in rings[i]:
                    on = (p["t"], p["port"]) in active
                    done = t >= p["t"] + p["dur"] - 1e-9
                    launch = active.get((p["t"], p["port"]), {}).get("center")
                    if launch is None and done:
                        launch = launched_at[(p["t"], p["port"])]
                    if launch is not None:
                        ly, lx = lab.rel(launch)
                        under.center = ring.center = (lx, ly)
                    lit = lit or on
                    # While running: dashed ring in the field's hue. Afterwards: a faint marker of where it ran.
                    ring.set_edgecolor(FIELDS[i]["hue"] if on else INK)
                    ring.set_alpha(1.0 if on else 0.7)
                    ring.set_linestyle((0, (2.5, 1.6)) if on else (0, (1, 1.6)))
                    under.set_alpha(0.8 if on else 0.55)
                    under.set_visible(on or done)
                    ring.set_visible(on or done)
                c_core.set_color(FIELDS[i]["hue"] if lit else INK)
                for k in range(13):
                    curves[i][k].set_data(times[: ti + 1], readings[: ti + 1, i, k])
                    if gray:
                        twins[i][k].set_data(times[: ti + 1], twin[: ti + 1, i, k])
                cursors[i].set_xdata([t, t])
            clock.set_text(f"t = {t:g}")
            frame(poster if n < len(times) and abs(t - poster_t) < 1e-9 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        poster_time=poster_t,
        hold_frames=hold,
    )


def film_world(lab, film, L, fps=16, hold=16, poster_t=150.0):
    """Four fields over an unforced 300-time-unit continuation, in the world view."""
    times = film["times"]
    title, bar = 0.30, 0.42
    row_h = title + L.panel + bar
    top = 0.34
    cv = Canvas(L.W, top + L.rows * row_h, dpi=L.dpi)
    cv.text(L.x0, 0.1, "Unforced continuation · no sources applied", fontsize=8.5, color=MUTED, va="top")
    clock = cv.text(L.W - L.x0, 0.1, "t = 0", fontsize=10, ha="right", va="top")
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
            clock.set_text(f"t = {times[ti]:g}")
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
    clock = cv.text(L.W - L.x0, 0.1, "t = 0", fontsize=10, ha="right", va="top")
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
            clock.set_text(f"t = {times[ti]:g}")
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


def group_values(lab, run, group):
    """Scaled readings (times x slots) in the oracle's port and slot order."""
    device = lab.devices[group["device"]]
    if np.abs(lab.rel(device.node_positions())).max() > (HALF - 1) * DX:
        raise ValueError("sensor outside the stored crop")
    rows = []
    for t in group["times"]:
        ti = int(np.flatnonzero(np.isclose(run["times"], t))[0])
        stream = lab.read(run["crops"][ti], device.node_positions())[PORT_PERM][:, device.node_perm]
        rows.append(stream[group["port"], group["slots"]])
    return np.array(rows) / group["scale"]


def score_figure(lab, runs, L, dpi=100):
    """The scoring view of one suite experiment; returns the canvas, a per-frame update, and metadata."""
    case_id, title, run_name, base_name = SCORE_CASE
    case, groups = scoring_groups()
    run, base = runs[run_name], runs[base_name]
    times = run["times"]
    for g in groups:
        g["values"], g["baseline"] = group_values(lab, run, g), group_values(lab, base, g)
        g["effect_by_time"] = np.sqrt(((g["values"] - g["baseline"]) ** 2).mean(axis=1))
    by_field = {}
    for g in groups:
        if g["device"] == 0:
            by_field[g["field"]] = g
    wide = [g for g in groups if g["device"] == 1]
    device0 = lab.devices[0]
    rd = np.stack([lab.read(c, device0.node_positions()) for c in run["crops"]])
    rs = np.stack([lab.read(c, device0.node_positions()) for c in base["crops"]])

    top = 1.86 if L.mobile else 1.18
    trace_h, row_gap = 0.98, 0.5
    row_h = L.panel + 0.40 + trace_h + row_gap
    table_rows = len(groups)
    card_h = 1.1 if L.mobile else 0.42
    table_top = top + L.rows * row_h - 0.06
    table_h = 0.34 + table_rows * card_h + 0.12
    cv = Canvas(L.W, table_top + table_h + (0.86 if L.mobile else 0.5), dpi=dpi)

    action = json.dumps(RUNS[run_name]["actions"][0])
    heading = cv.text(L.x0, 0.10, f"{case_id} · {title}", fontsize=10, fontweight="bold", va="top")
    if L.mobile:
        cv.text(
            L.x0,
            0.34,
            action.replace(', "port"', ',\n "port"'),
            fontsize=8.2,
            family=MONO,
            va="top",
            color=MUTED,
            linespacing=1.3,
        )
        cv.text(
            L.x0,
            0.82,
            "Four groups of readings are scored. Each reading\nis divided by its group's scale; x₁ and the "
            "global\nsensor are recorded but not scored.",
            fontsize=8.5,
            color=MUTED,
            va="top",
            linespacing=1.35,
        )
    else:
        cv.text(L.x0 + cv.width_of(heading) + 0.16, 0.115, action, fontsize=8.6, family=MONO, va="top", color=MUTED)
        cv.text(
            L.x0,
            0.40,
            "Four groups of readings are scored, and each reading is divided by its group's scale.\n"
            "x₁ and the global sensor are recorded but not scored.",
            fontsize=8.5,
            color=MUTED,
            va="top",
            linespacing=1.35,
        )
    clock = cv.text(L.W - L.x0, 0.10, "t = 0", fontsize=10, ha="right", va="top")

    images, dots, bands = [], [], []
    for i, f in enumerate(FIELDS):
        y = top + L.row(i) * row_h
        ax = field_axes(cv, L.x(i), y, L.panel, f)
        images.append(show(ax, run["crops"][0, i], f))
        scored0 = i in by_field
        scored1 = any(g["field"] == i for g in wide)
        sensors(ax, lab.rel(device0.node_positions()), 0, alpha=1.0 if scored0 else 0.22)
        sensors(ax, lab.rel(lab.devices[1].node_positions()), 1, alpha=1.0 if scored1 else 0.22)
        source(ax, lab.rel(lab.center))
        if i == 0:
            scalebar(ax)
        if not (scored0 or scored1):
            ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, color="white", alpha=0.62, zorder=7))
            ax.text(
                0.5,
                0.5,
                "not scored",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=9.5,
                color=MUTED,
                zorder=8,
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=LINE, lw=0.6),
            )
        # Readings over time, divided by the group's scale; dots mark scored readings.
        ty = y + L.panel + 0.40
        tr = cv.ax(L.x(i) + 0.30, ty, L.panel - 0.30, trace_h)
        for side in ("top", "right"):
            tr.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            tr.spines[side].set_color("#c3ccd4")
        tr.set_xlim(0, 50)
        tr.set_xticks(range(0, 51, 10))
        tr.set_xticklabels(["0", "", "", "", "", "50"])
        tr.tick_params(labelsize=7, length=2, width=0.5, pad=1.5, colors=MUTED)
        g = by_field.get(i)
        label_y = ty - 0.07
        if g is None:
            tr.set_ylim(*f["trace"])
            tr.set_yticks([])
            for k in range(13):
                tr.plot(times, rd[:, i, k], color=f["hue"], lw=0.7, alpha=0.22)
            cv.text(L.x(i) + 0.30, label_y, "recorded, not scored", fontsize=8, color=MUTED, va="bottom")
            dots.append(([], None, None))
            continue
        lo, hi = f["trace"]
        if f["key"] == "u0":
            hi = 1.75  # headroom for the band label
        tr.set_ylim(lo / g["scale"], hi / g["scale"])
        ticks = {"u0": [-1, 0, 1], "x0": [0, 1, 2], "x2": [0, 2, 4, 6]}[f["key"]]
        tr.set_yticks(ticks)
        tr.grid(axis="y", color="#eef1f4", lw=0.6, zorder=0)
        for t in g["times"]:
            tr.axvline(t, color="#c3ccd4", lw=0.6, zorder=0.5)
        tr.axvspan(0, 5, color=FIELDS[3]["hue"], alpha=0.12, lw=0, zorder=0)
        if f["key"] == "u0":
            band = tr.axvspan(20, 50, color=f["hue"], alpha=0.07, lw=0, zorder=0.2)
            note = tr.text(
                35, 0.97 * hi / g["scale"], "delayed response", fontsize=7, color=MUTED, va="top", ha="center"
            )
            bands.append((20, band, note))
        name = cv.text(L.x(i) + 0.30, label_y, g["name"], fontsize=8.5, fontweight="bold", va="bottom")
        cv.text(
            L.x(i) + 0.30 + cv.width_of(name) + 0.08,
            label_y,
            f"÷ {g['scale']:g}",
            fontsize=8.5,
            color=MUTED,
            va="bottom",
            family=MONO,
        )
        twins = [tr.plot([], [], color=GRAY_TRACE, lw=0.7, zorder=1)[0] for _ in range(13)]
        lines = [tr.plot([], [], color=f["hue"], lw=0.9, alpha=0.85, zorder=2)[0] for _ in range(13)]
        stamps = []
        for j, t in enumerate(g["times"]):
            # values are in stream-slot order; each slot is one of the 13 sensors
            pts = tr.plot(
                [t] * len(g["slots"]),
                g["values"][j],
                "o",
                ms=3.2,
                color=f["hue"],
                mec="white",
                mew=0.6,
                zorder=4,
                visible=False,
            )[0]
            stamps.append((t, pts))
        dots.append((stamps, lines, twins))
        tr.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())

    # Group table: what is scored, its scale, and where this experiment's evidence sits.
    cv.text(L.x0, table_top, "Scored groups", fontsize=10, fontweight="bold", va="top")
    if not L.mobile:
        for x, text in (
            (1.85, "Scored readings"),
            (4.42, "Scale"),
            (5.02, "Effect of the pulse at each scored time"),
            (7.38, "RMS"),
        ):
            cv.text(L.x0 + x, table_top + 0.02, text, fontsize=8, color=MUTED, va="top")
    ymax = 1.12 * max(g["effect_by_time"].max() for g in groups)
    bars, totals = [], []
    for r, g in enumerate(groups):
        f = FIELDS[g["field"]]
        y = table_top + 0.34 + r * card_h
        cv.fig.add_artist(Line2D([L.x0 / cv.W, (L.W - L.x0) / cv.W], [1 - (y - 0.06) / cv.H] * 2, color=LINE, lw=0.6))
        cv.fig.add_artist(
            Rectangle(
                (L.x0 / cv.W, 1 - (y + 0.13) / cv.H),
                0.1 / cv.W,
                0.1 / cv.H,
                color=f["hue"],
                transform=cv.fig.transFigure,
            )
        )
        cv.text(L.x0 + 0.17, y + 0.04, g["name"], fontsize=9, fontweight="bold", va="center")
        what = f"{f['sym']} at device {g['device']}'s {len(g['slots'])} sensors"
        when = f"t = {', '.join(f'{t:g}' for t in g['times'])} · {g['size']} values"
        if L.mobile:
            cv.text(L.x0 + 0.17, y + 0.27, what + f"  ÷ {g['scale']:g}", fontsize=8, va="center")
            cv.text(L.x0 + 0.17, y + 0.45, when, fontsize=7.6, color=MUTED, va="center")
            bx, by, bw = L.x0 + 0.17, y + 0.58, L.W - 2 * L.x0 - 0.75
        else:
            cv.text(L.x0 + 1.85, y + 0.04, what, fontsize=8, va="center")
            cv.text(L.x0 + 1.85, y + 0.21, when, fontsize=7.4, color=MUTED, va="center")
            cv.text(L.x0 + 4.42, y + 0.04, f"÷ {g['scale']:g}", fontsize=8.6, va="center", family=MONO)
            bx, by, bw = L.x0 + 5.02, y - 0.06, 2.1
        ax = cv.ax(bx, by, bw, 0.28)
        ax.set_xlim(-1.5, 51.5)
        ax.set_ylim(0, ymax)
        ax.axis("off")
        ax.axhline(0, color="#c3ccd4", lw=0.6)
        rects = ax.bar(g["times"], g["effect_by_time"], width=2.4, color=f["hue"], zorder=2)
        for rect in rects:
            rect.set_visible(False)
        for t in g["times"]:
            ax.plot([t, t], [0, -0.06 * ymax], color="#c3ccd4", lw=0.6, clip_on=False)
        if r == table_rows - 1 or L.mobile:
            ax.text(-1.5, -0.1 * ymax, "t = 0", fontsize=6.5, color=MUTED, va="top")
            ax.text(51.5, -0.1 * ymax, "50", fontsize=6.5, color=MUTED, va="top", ha="right")
        bars.append(list(zip(g["times"], rects)))
        total = cv.text(
            L.W - L.x0, (y + 0.04) if not L.mobile else (y + 0.72), "", fontsize=9, va="center", ha="right", family=MONO
        )
        totals.append(total)
    note = (
        "Effect of the pulse: RMS difference from the run without it,\nin scale units (same noise). A forecast that "
        "ignored the pulse\nwould score roughly these values. Each group gives one\nenergy score; the experiment's "
        "score is their equal-weight mean."
        if L.mobile
        else "Effect of the pulse: RMS difference from the run without it, in scale units (same noise). A forecast that "
        "ignored the pulse\nwould score roughly these values. Each group gives one energy score; the experiment's "
        "score is their equal-weight mean."
    )
    cv.text(L.x0, cv.H - 0.08, note, fontsize=8, color=MUTED, va="bottom", linespacing=1.35)

    def update(ti):
        t = times[ti]
        for i in range(4):
            images[i].set_data(run["crops"][ti, i])
            stamps, lines, twins = dots[i]
            if lines is not None:
                g = by_field[i]
                for k in range(13):
                    lines[k].set_data(times[: ti + 1], rd[: ti + 1, i, k] / g["scale"])
                    twins[k].set_data(times[: ti + 1], rs[: ti + 1, i, k] / g["scale"])
            for ts, pts in stamps:
                pts.set_visible(t >= ts - 1e-9)
        for start, band, label in bands:
            band.set_visible(t >= start)
            label.set_visible(t >= start)
        for g, row, total in zip(groups, bars, totals):
            seen = [k for k, (ts, _) in enumerate(row) if t >= ts - 1e-9]
            for k, (_, rect) in enumerate(row):
                rect.set_visible(k in seen)
            if seen:
                d = (g["values"] - g["baseline"])[seen]
                total.set_text(f"{np.sqrt((d**2).mean()):.2f}")
            else:
                total.set_text("–")
        clock.set_text(f"t = {t:g}")

    meta = dict(
        case=case_id,
        run=run_name,
        baseline=base_name,
        query_times=QUERY_TIMES,
        groups=[
            dict(
                id=g["id"],
                device=g["device"],
                field=FIELDS[g["field"]]["key"],
                port=g["port"],
                times=g["times"],
                slots=g["slots"],
                scale=g["scale"],
                values=g["size"],
                effect_rms_by_time=g["effect_by_time"].tolist(),
                effect_rms=float(np.sqrt(((g["values"] - g["baseline"]) ** 2).mean())),
            )
            for g in groups
        ],
        source="generators/physim/build_evaluation_bundle.py::score_groups",
    )
    return cv, update, times, meta


def fig_score(lab, runs, L):
    cv, update, times, meta = score_figure(lab, runs, L)
    update(len(times) - 1)
    return save(cv, "bf-score", L), meta


def anim_score(lab, runs, L, fps=12, hold=24):
    cv, update, times, meta = score_figure(lab, runs, L, dpi=L.dpi)
    path, poster = OUT / f"bf-score{L.suffix}.mp4", OUT / f"bf-score{L.suffix}.jpg"
    order = list(range(len(times))) + [len(times) - 1] * hold
    with video_writer(cv.fig, path, fps=fps) as frame:
        for n, ti in enumerate(order):
            update(ti)
            frame(poster if n == len(order) - 1 else None)
    plt.close(cv.fig)
    print("wrote", path.relative_to(ROOT), flush=True)
    return dict(
        meta,
        files=[str(path.relative_to(OUT)), str(poster.relative_to(OUT))],
        encoding=frame.validation,
        fps=fps,
        hold_frames=hold,
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
        "score",
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
                act = RUNS["trail_pulse"]["actions"][0]
                header = json.dumps(act) if not L.mobile else (json.dumps(act).replace(', "port"', ',\n "port"'))
                sub = (
                    "In the world: a Gaussian source (σ = 2) adds to x₂\nat device 0's center for 5 time units."
                    if L.mobile
                    else "In the world: a Gaussian source (σ = 2) adds to x₂ at device 0's center for 5 time units."
                )
                meta = anim_experiment(lab, runs, L, "trail_pulse", header, sub, "bf-pulse", gray="sham")
            elif name == "score-video":
                meta = anim_score(lab, runs, L)
            elif name == "p4-film":
                meta = film_p4(p4_film, L)
            elif name == "walk":
                header = (
                    "adjust u = [1, 0, 0] at t = 0, 5, 10\nadjust u = [0, 1, 0] at t = 15, 20, 25\n"
                    "inject port 2 at t = 18\nadjust u = [0, 0, 0.4] at t = 30"
                    if L.mobile
                    else "adjust device 0 by u = [1, 0, 0] at t = 0, 5, 10, then by u = [0, 1, 0] at t = 15, 20, 25\n"
                    "inject port 2 at t = 18 · adjust by u = [0, 0, 0.4] at t = 30"
                )
                sub = (
                    "In the world: the device steps down, then right, then\nwidens. Moves carry the sensors and "
                    "the next launch\npoint; a launched pulse stays where it started."
                    if L.mobile
                    else "In the world: the device steps down, then right, then widens. Moves carry the sensors and "
                    "the next\nlaunch point; a launched pulse stays where it started."
                )
                meta = anim_experiment(lab, runs, L, "walk", header, sub, "bf-walk", poster_t=40.0)
            else:
                fn = {
                    "fields": fig_fields,
                    "grid": fig_grid,
                    "apparatus": fig_apparatus,
                    "sensor-grid": fig_sensor_grid,
                    "score": fig_score,
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

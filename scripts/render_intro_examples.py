"""Recreate the early motion/binding examples with readable, stacked panels.

Run with ``python -m scripts.render_intro_examples``. The motion example is simulated with its documented spectral stepper; the
binding example retains the original field frames and recorded separation.
Source hashes and settings are saved alongside the films. No agent evaluations are run.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(key, "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/physim-intro-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from scripts.scientific_video import video_writer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets/worlds"
CACHE = ROOT / "outputs/intro-examples-20260927"


def load_source(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recorded_binding():
    source = ROOT / "docs/assets/blobs/m2_bind.gif"
    record = ROOT / "probes/blobs/binding/data/bcs_d18.5.json"
    with Image.open(source) as gif:
        # The original field panel, without any original titles, axes or chart.
        fields = []
        for i in range(gif.n_frames):
            gif.seek(i)
            fields.append(np.asarray(gif.convert("RGB").crop((73, 34, 268, 230))))
    times = np.arange(len(fields)) * 12.0
    measurements = np.asarray(json.loads(record.read_text())["seps"])[:, :2]
    identity = dict(
        name="binding",
        rendering="Original field-panel frames; separation curve from the archived experiment record.",
        crop_pixels=[73, 34, 268, 230],
        sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [source, record]},
    )
    data = dict(
        fields=np.asarray(fields),
        times=times,
        measurement=np.interp(times, measurements[:, 0], measurements[:, 1]),
        u0=0,
        identity=json.dumps(identity),
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / "binding-historical.npz"
    np.savez_compressed(cache, **data)
    return data, identity, cache


def capture(name):
    if name == "binding":
        return recorded_binding()
    motion = load_source("intro_motion", "probes/blobs/motility/sim.py")
    duration, spacing, domain = 600, 4, 96
    times = np.arange(0, duration + 0.1, spacing)
    settings = dict(
        T=duration,
        dx=0.5,
        L_phys=domain,
        dt=0.02,
        noise=0,
        seed=0,
        rec_tu=spacing,
        snap_times=times,
        stepper="imexfft",
        kick_angle=60,
        center=(32.0, 24.0),
    )
    params = dict(tau=5.0, Dv=0.65)
    sources = ["probes/blobs/motility/sim.py", "probes/blobs/binding/sim.py"]
    identity = dict(
        name=name,
        parameters=params,
        settings={k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in settings.items() if k != "ic"},
        sources={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
    )
    identity = json.loads(json.dumps(identity))
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{name}.npz"
    if cache.exists():
        with np.load(cache) as data:
            assert json.loads(str(data["identity"])) == identity
            return {k: data[k] for k in data.files}, identity, cache
    print("Simulating", name, flush=True)
    result = motion.run(p=params, **settings)
    assert result["status"] == "ok", result["status"]
    fields = np.array([result["snaps"][t] for t in times])
    assert set(result["ncomp"]) == {1}
    measurement = np.linalg.norm(result["com"][: len(times)] - result["com"][0], axis=1)
    data = dict(fields=fields, times=times, measurement=measurement, u0=result["u0"], identity=json.dumps(identity))
    np.savez_compressed(cache, **data)
    print(name, "start/end measurement", measurement[0], measurement[-1], flush=True)
    return data, identity, cache


def render(name):
    data, identity, cache = capture(name)
    fields, times, measurement = data["fields"], data["times"], data["measurement"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 15,
            "text.color": "#17242f",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig = plt.figure(figsize=(4.8, 6.6), dpi=100)
    ax = fig.add_axes([0.09, 0.43, 0.84, 0.5])
    chart = fig.add_axes([0.2, 0.11, 0.73, 0.22])
    im = ax.imshow(
        fields[0] if name == "binding" else fields[0] - data["u0"],
        cmap="inferno",
        vmin=-0.4,
        vmax=1.9,
        interpolation="bilinear",
    )
    ax.set_axis_off()
    fig.suptitle("A moving excitation" if name == "travel" else "A bound pair", fontsize=21, y=0.985)
    time = ax.text(0.03, 0.96, "", transform=ax.transAxes, va="top", color="white", fontsize=15)
    chart.plot(times, measurement, color="#126e64", lw=2)
    (dot,) = chart.plot([times[0]], [measurement[0]], "o", color="#17242f", ms=6)
    chart.set(xlabel="Time", ylabel="Distance moved" if name == "travel" else "Separation", xlim=(0, times[-1]))
    chart.tick_params(labelsize=13)
    chart.set_xticks([0, 300, 600] if name == "travel" else [0, 1000, 2000])
    if name == "binding":
        chart.set_ylim(15, 19)
    else:
        chart.set_ylim(0, max(measurement) * 1.08)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"early-{name}.mp4"
    with video_writer(fig, path, fps=12) as frame:
        for i, t in enumerate(times):
            im.set_data(fields[i] if name == "binding" else fields[i] - data["u0"])
            time.set_text(f"t = {t:g}")
            dot.set_data([t], [measurement[i]])
            frame(OUT / f"early-{name}.jpg" if i == 0 else None)
    plt.close(fig)
    identity.update(
        encoding=frame.validation,
        frames=len(times),
        fps=12,
        measurement_start=float(measurement[0]),
        measurement_end=float(measurement[-1]),
        data_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
        video_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    (OUT / f"early-{name}.json").write_text(json.dumps(identity, indent=2) + "\n")
    print("Rendered", name, flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--example", choices=["travel", "binding"])
    args = parser.parse_args()
    for name in [args.example] if args.example else ["travel", "binding"]:
        render(name)

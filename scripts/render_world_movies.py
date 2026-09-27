"""Render focused scientific films with fixed views and validated frame encoding.

``python -m scripts.render_world_movies`` captures unforced continuations from
saved preparations when needed, then renders the selected fields and windows.
The full simulation domain is retained; only the displayed images are cropped.
"""

import argparse
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(key, "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/physim-world-movies-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from physim.bundles import Bundle
from physim.devices import step_chunk

from scripts.scientific_video import video_writer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets/worlds"
CACHE = ROOT / "outputs/world-movies-20260927"
CONFIG = {
    "bf": dict(seed=926201, duration=300, fields=[0, 3], center=[115, 15], width=64, end=300),
    "xv": dict(seed=926202, duration=650, fields=[0, 1], center=[64, 68], width=32, end=650),
    "p4g2_044": dict(seed=926203, duration=900, fields=[0, 1, 2, 3], center=[30, 50], width=80, end=450),
}


def capture(world):
    c = CONFIG[world]
    bundle = Bundle(ROOT / "outputs/eval-preparation-20260916" / world / "bundle")
    times = np.arange(0, c["duration"] + 2.5, 2.5)
    identity = dict(
        world=world,
        bundle=bundle.references(),
        seed=c["seed"],
        times=times.tolist(),
        field_indices=c["fields"],
        noise=0.002,
        description="Unforced full-domain continuation of the saved preparation.",
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{world}.npz"
    if path.exists():
        with np.load(path) as z:
            if json.loads(str(z["identity"])) != identity:
                raise ValueError("Movie cache identity mismatch")
            return z["fields"], times, identity, path
    sim = deepcopy(bundle.make_oracle()._template)
    sim["workers"] = 1
    sim["rng"] = np.random.default_rng(c["seed"])
    frames = []
    for t in times:
        step_chunk(sim, round(t / sim["dt"]) - sim["t_step"])
        frames.append(sim["F"][c["fields"]].copy())
        if t % 100 == 0:
            print(world, t, flush=True)
    frames = np.asarray(frames)
    np.savez_compressed(path, fields=frames, identity=json.dumps(identity, sort_keys=True))
    return frames, times, identity, path


def xv_rgb(frame):
    # Independently scaled positive activator values, at the same coordinates.
    a, b = np.clip(frame / 1.1, 0, 1)
    base = np.array([12, 20, 38]) / 255
    cyan = np.array([63, 207, 230]) / 255
    gold = np.array([255, 190, 85]) / 255
    return np.clip(base + a[..., None] * (cyan - base) + b[..., None] * (gold - base), 0, 1)


def render(world):
    frames, times, identity, cache = capture(world)
    c = CONFIG[world]
    keep = times <= c["end"]
    frames, times = frames[keep], times[keep]
    half = int(c["width"])
    indices = [(np.arange(-half, half) + round(v / 0.5)) % 256 for v in c["center"]]
    frames = frames[:, :, indices[0]][:, :, :, indices[1]]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16, "text.color": "#17242f"})
    if world == "xv":
        fig = plt.figure(figsize=(6.4, 6.2), dpi=100)
        ax = fig.add_axes([0.08, 0.06, 0.84, 0.84])
        axes = [ax]
        images = [ax.imshow(xv_rgb(frames[0]), interpolation="bilinear")]
        fig.text(0.1, 0.96, "u₀ · orbiting excitation", color="#087789", fontsize=17, weight="bold")
        fig.text(0.1, 0.915, "u₁ · partner", color="#a05d0a", fontsize=17, weight="bold")
        ranges = [[0, 1.1], [0, 1.1]]
    else:
        fig, axes = plt.subplots(1, 2, figsize=(10, 5.6), dpi=100)
        fig.subplots_adjust(left=0.025, right=0.975, bottom=0.06, top=0.85, wspace=0.08)
        names = (
            ["Moving excitations · u₀", "Persistent trail · x₂"]
            if world == "bf"
            else ["Localized excitations · u₀", "Stripe pattern · u₁"]
        )
        ranges = [[-1.1, 1.1], [0, 0.024]] if world == "bf" else [[-1.1, 1.1], [-1.3, 1.2]]
        images = []
        for i, ax in enumerate(axes):
            images.append(
                ax.imshow(frames[0, i], cmap="viridis", vmin=ranges[i][0], vmax=ranges[i][1], interpolation="bilinear")
            )
            ax.set_title(names[i], fontsize=18, pad=10)
        if world == "bf":
            outline = axes[1].contour(frames[0, 0], levels=[0.5], colors="white", linewidths=1)
    for ax in axes:
        ax.set_axis_off()
    title = (
        fig.suptitle("", fontsize=17, y=0.995 if world != "xv" else 0.995)
        if world != "xv"
        else fig.text(0.91, 0.96, "", ha="right", fontsize=15)
    )
    OUT.mkdir(exist_ok=True, parents=True)
    path = OUT / f"{world}-fields.mp4"
    fps = 12 if world == "p4g2_044" else 16
    with video_writer(fig, path, fps=fps) as frame:
        for i, t in enumerate(times):
            if world == "xv":
                images[0].set_data(xv_rgb(frames[i]))
            else:
                for j, im in enumerate(images):
                    im.set_data(frames[i, j])
                if world == "bf":
                    outline.remove()
                    outline = axes[1].contour(frames[i, 0], levels=[0.5], colors="white", linewidths=1)
            title.set_text(f"t = {t:g}")
            frame(OUT / f"{world}-fields.jpg" if i == 0 else None)
    plt.close(fig)
    identity.update(
        encoding=frame.validation,
        field_ranges=ranges,
        displayed_fields=c["fields"][:2],
        frames=len(times),
        fps=fps,
        displayed_times=times.tolist(),
        duration_tu=c["end"],
        view_width=c["width"],
        crop_center_yx=c["center"],
        indices_yx=[a.tolist() for a in indices],
        fields_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
        video_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        selection=(
            "Selected after inspecting a 900-time-unit continuation; shows elongation and splitting of u0 excitations alongside changing u1 stripes."
            if world == "p4g2_044"
            else "Fixed view of the coupled fields responsible for the described motion."
        ),
    )
    (OUT / f"{world}-fields.json").write_text(json.dumps(identity, indent=2) + "\n")
    print("Rendered", world, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=list(CONFIG))
    args = parser.parse_args()
    for world in [args.world] if args.world else CONFIG:
        render(world)

"""Render apparatus schematics from native sensor geometry; no world simulation.

Run with the development environment and PYTHONPATH=environments/physim:packages/blobkit.
The coordinates illustrate the contract, not a published laboratory preparation.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
from physim.devices import INJ_SIGMA, lattice_offsets

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets/apparatus"
INK, SOURCE, MUTED = "#192630", "#bd570d", "#697885"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "text.color": INK,
        "svg.fonttype": "path",
        "svg.hashsalt": "physim-apparatus-v2",
    }
)


def sensors(ax, lattice, center=(0, 0), spacing=3):
    yx = lattice_offsets(lattice, 3) * spacing + np.array(center)
    ax.scatter(yx[:, 1], yx[:, 0], s=70, facecolors="white", edgecolors=INK, linewidths=1.6, zorder=3)


def source(ax, xy=(0, 0), active=True):
    color = SOURCE if active else MUTED
    ax.add_patch(Circle(xy, INJ_SIGMA, facecolor=color, alpha=0.10, edgecolor="none", zorder=1))
    ax.add_patch(Circle(xy, INJ_SIGMA, fill=False, edgecolor=color, linewidth=1.2, linestyle="--", zorder=2))
    ax.scatter(*xy, marker="+", color=color, s=220, linewidths=2.4, zorder=4)


def setup(ax, limits):
    ax.set_aspect("equal")
    ax.set_xlim(*limits[0])
    ax.set_ylim(*limits[1])
    ax.axis("off")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{name}.svg"
    fig.savefig(target, metadata={"Date": None}, facecolor="white")
    target.write_text("\n".join(line.rstrip() for line in target.read_text().splitlines()) + "\n")
    fig.savefig(f"/tmp/physim-{name}.png", dpi=130, facecolor="white")
    plt.close(fig)


def render(mobile=False):
    suffix = "-mobile" if mobile else ""
    fig, axes = plt.subplots(2 if mobile else 1, 1 if mobile else 2, figsize=(5.5, 8) if mobile else (11, 4.6))
    fig.subplots_adjust(
        left=0.06, right=0.94, top=0.90 if mobile else 0.83, bottom=0.15 if mobile else 0.17, wspace=0.18, hspace=0.4
    )
    for i, (ax, lattice) in enumerate(zip(axes, ("square", "hex"))):
        setup(ax, ((-8, 8), (-7, 7)))
        sensors(ax, lattice)
        source(ax)
        ax.set_title(f"Device {i} · {len(lattice_offsets(lattice, 3))} sensors", fontsize=15, fontweight="bold", pad=15)
    fig.legend(
        handles=[
            Line2D(
                [], [], marker="o", markerfacecolor="white", markeredgecolor=INK, color="none", label="Sensor position"
            ),
            Line2D(
                [],
                [],
                marker="+",
                markeredgewidth=2,
                markersize=12,
                color=SOURCE,
                linestyle="none",
                label="Source at array center",
            ),
            Line2D([], [], color=SOURCE, linestyle="--", label="Radius σ = 2"),
        ],
        loc="lower center",
        ncol=1 if mobile else 3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.02),
    )
    save(fig, "geometry" + suffix)

    fig, axes = plt.subplots(3 if mobile else 1, 1 if mobile else 3, figsize=(5.5, 10) if mobile else (11, 4))
    fig.subplots_adjust(
        left=0.02, right=0.98, top=0.91 if mobile else 0.75, bottom=0.09 if mobile else 0.20, wspace=0.12, hspace=0.65
    )
    titles = ["1. Launch pulse", "2. Reposition device", "3. Launch next pulse"]
    subtitles = ["t = 1", "t = 2 · first pulse continues", "t = 6 · first pulse has ended"]
    for i, ax in enumerate(axes):
        setup(ax, ((-4.5, 11), (-5.5, 5.5)))
        sensors(ax, "square", center=(0, 0 if i == 0 else 7), spacing=1.5)
        source(ax, (0 if i < 2 else 7, 0))
        if i == 1:
            ax.annotate("", xy=(6, -4), xytext=(1, -4), arrowprops=dict(arrowstyle="->", color=INK, lw=1.4))
            ax.text(3.5, -5.2, "instant move", ha="center", fontsize=11)
        ax.set_title(titles[i], fontsize=13, fontweight="bold", pad=31)
        ax.text(0.5, 1.09, subtitles[i], transform=ax.transAxes, ha="center", fontsize=10, color=MUTED)
    label = (
        "A launched pulse stays at its launch position.\nFuture pulses use the device’s new center."
        if mobile
        else "A launched pulse stays at its launch position. Future pulses use the device’s new center."
    )
    fig.text(0.5, 0.025 if mobile else 0.07, label, ha="center", fontsize=12)
    save(fig, "pulse-and-move" + suffix)


if __name__ == "__main__":
    render()
    render(mobile=True)

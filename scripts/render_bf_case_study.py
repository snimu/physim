"""Capture bounded BF rollout evidence, then render the Results-page figures.

Default rendering uses only the committed snapshot. --capture reads local saved
campaign artifacts; it never executes submitted code, unpickles models, or runs
inference/simulation. Model source files are copied as text for inspection only.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import tarfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs_source/data/bf-case-study.json"
FIGURES = ROOT / "docs/assets/results"
CAMPAIGN = ROOT / "outputs/evaluation-campaign-20260919-prime-agent-bf"
BUNDLE = ROOT / "outputs/eval-preparation-20260916/bf/bundle"
MODELS = [
    ("qwen/qwen3.5-35b-a3b", "Qwen3.5 35B A3B", "Qwen 35B", False),
    ("qwen/qwen3.5-397b-a17b", "Qwen3.5 397B A17B", "Qwen 397B", False),
    ("openai/gpt-5.6-luna", "GPT-5.6 Luna", "Luna", False),
    ("x-ai/grok-4.6", "Grok 4.6", "Grok", False),
    ("openai/gpt-5.6-terra", "GPT-5.6 Terra", "Terra", False),
    ("anthropic/claude-sonnet-5", "Claude Sonnet 5", "Sonnet", True),
    ("z-ai/glm-5.3-flash", "GLM 5.3 Flash", "GLM", True),
]
# Experiment names on the write-up, in world terms (fields u0, x1, x2; devices 0 and 1).
DISPLAY_NAMES = {
    "c001": "No actions",
    "c002": "Weak u₀ pulse",
    "c003": "Strong u₀ pulse",
    "c004": "Low trail pulse",
    "c005": "Medium trail pulse",
    "c006": "High trail pulse",
    "c007": "u₀ pulse, then trail pulse",
    "c008": "Delayed u₀ pulse",
    "c009": "x₁ pulse",
    "c010": "Shift device 0",
    "c011": "Dilate device 1",
    "c012": "u₀ pulse, then shift",
    "c013": "Shift, then u₀ pulse",
    "c014": "Two sources",
    "c015": "Shift during u₀ pulse",
}
CASE_NAMES = [
    "No actions",
    "Weak activator pulse",
    "Strong activator pulse",
    "Low trail pulse",
    "Medium trail pulse",
    "High trail pulse",
    "Activator, then trail",
    "Delayed activator pulse",
    "Inhibitor pulse",
    "Move first device",
    "Widen second device",
    "Pulse, then move",
    "Move, then pulse",
    "Two sources",
    "Move during injection",
]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    spec = importlib.util.spec_from_file_location("prime_usage", ROOT / "scripts/physim/prime_usage.py")
    usage_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usage_module)
    suite = read(BUNDLE / "suite.json")
    evidence = {
        "schema": "physim-bf-case-study-v1",
        "selection": "One completed BF rollout per model; GLM is a blind retry after an unexplained early stop.",
        "harness": "Prime Agent",
        "prompt": "interface-only-v2",
        "apparatus": suite["contract_version"],
        "forecast_members": suite["forecast_members"],
        "truth_members": suite["truth_members"],
        "reward": "1 / (1 + mean case energy); zero if any grading case is invalid",
        "cost_note": "Recorded-use costs exclude requests without usage; estimates are not invoices. Unknown cache-read prices use full input rates. Reserves are excluded.",
        "cases": [
            dict(
                id=c["request"]["id"],
                family=c["family"],
                label=label,
                actions=c["request"]["actions"],
                queries=c["request"]["queries"],
            )
            for c, label in zip(suite["cases"], CASE_NAMES, strict=True)
        ],
        "models": [],
    }
    # Small slices retain every forecast/truth member for the plotted channels.
    slices = {}
    for case_id, channel in (("c005", 2), ("c012", 1), ("c013", 1)):
        path = BUNDLE / "truth" / f"{case_id}.npz"
        with np.load(path, allow_pickle=False) as arrays:
            slices[case_id] = {
                "sensor": "device0",
                "channel": channel,
                "slot": 6,
                "truth": arrays["query0"][:, :, channel, 6].tolist(),
                "truth_file_sha256": sha(path),
                "forecasts": {},
            }
    for model, name, short, replacement in MODELS:
        campaign = Path(str(CAMPAIGN) + "-retries") if replacement else CAMPAIGN
        key = model.replace("/", "--")
        attempt = campaign / "attempts" / f"{key}-bf-r1-attempt1"
        meta = read(attempt / "attempt.json")
        artifact = attempt / "artifacts" / meta["trace_id"]
        grade, lab, audit = (read(artifact / f) for f in ("grade.json", "laboratory_state.json", "limit_audit.json"))
        assert meta["status"] == "complete" and lab["submitted"] and not audit["truncated"]
        trace_path = attempt / "runs/rollout/traces.jsonl"
        trace = json.loads(trace_path.read_text().splitlines()[0])["traces"][0]
        prices = {m["id"]: m["pricing"] for m in read(campaign / "catalog.json")["data"]}
        usage = usage_module.summarize(attempt / "diagnostics", prices)
        energies = {c["case_id"]: c["joint_energy"] for c in grade["results"]}
        failed = {c["case_id"]: c["error_type"] for c in grade["failures"]}
        kinds = dict(none=0, inject=0, adjust=0, mixed=0)
        for exp in lab["experiments"]:
            actions = {a["kind"] for a in exp["request"]["actions"]}
            kinds["none" if not actions else "mixed" if len(actions) > 1 else next(iter(actions))] += 1
        energy = grade["primary_joint_energy"]
        energy = energy if energy is not None and math.isfinite(energy) else None
        reward = meta["rewards"]["prediction_reward"]["score"]
        assert math.isclose(reward, 1 / (1 + energy) if energy is not None else 0)
        row = dict(
            model=model,
            name=name,
            short=short,
            key=key,
            trace_id=meta["trace_id"],
            source_id=meta["source_id"],
            references=meta["bundle_references"],
            reward=reward,
            energy=energy,
            valid_cases=grade["valid_cases"],
            experiments=lab["usage"]["experiments"],
            experiment_kinds=kinds,
            usage=usage,
            pricing=prices[model],
            cost_usd=usage["reported_cost_usd"] + usage["estimated_unreported_cost_usd"],
            cost_basis="estimate" if usage["estimated_unreported_cost_usd"] else "provider-reported",
            elapsed_minutes=(trace["timing"]["agent"]["end"] - trace["timing"]["agent"]["start"]) / 60,
            checks=[dict(kind=c["kind"], ok=c["validation"]["ok"]) for c in lab["checks"]],
            cases=[
                dict(id=c["id"], energy=energies.get(c["id"]), error=failed.get(c["id"])) for c in evidence["cases"]
            ],
            sources={
                "grade_sha256": sha(artifact / "grade.json"),
                "trace_sha256": sha(trace_path),
                "usage_sha256": sha(attempt / "diagnostics/native-usage.jsonl"),
            },
            predictor_sources=[],
        )
        # Read regular, small Python files as inert bytes. No tar extraction.
        with tarfile.open(artifact / "submit_01/workspace.tar") as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.endswith(".py") and member.size < 200_000:
                    filename = Path(member.name).name
                    source = archive.extractfile(member).read()
                    target = ROOT / "docs_source/examples/case-study" / key / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source)
                    row["predictor_sources"].append(
                        {"file": f"examples/case-study/{key}/{filename}", "sha256": hashlib.sha256(source).hexdigest()}
                    )
        for case_id, item in slices.items():
            if case_id not in energies:
                continue
            path = artifact / "grading_predictions" / f"{case_id}.npz"
            with np.load(path, allow_pickle=False) as arrays:
                item["forecasts"][short] = {
                    "samples": arrays["query0"][:, :, item["channel"], item["slot"]].tolist(),
                    "file_sha256": sha(path),
                }
        evidence["models"].append(row)
    evidence["trajectory_slices"] = slices
    DATA.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")


def save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ("svg", "png"):
        fig.savefig(FIGURES / f"{name}.{extension}", dpi=180, bbox_inches="tight", facecolor="white")
    svg = FIGURES / f"{name}.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)


def render(heatmap_only=False):
    data = read(DATA)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#17242f",
            "text.color": "#17242f",
            "svg.fonttype": "path",
        }
    )
    values = np.array(
        [
            [r["cases"][i]["energy"] if r["cases"][i]["energy"] is not None else np.nan for r in data["models"]]
            for i in range(15)
        ]
    )
    fig, ax = plt.subplots(figsize=(10.8, 7.3), layout="constrained")
    im = ax.imshow(values, cmap="viridis_r", norm=LogNorm(0.002, 5), aspect="auto")
    ax.set_xticks(range(7), [r["short"].replace(" ", "\n") for r in data["models"]])
    ax.xaxis.tick_top()
    ax.tick_params(length=0, pad=9)
    ax.set_yticks(range(15), [DISPLAY_NAMES[c["id"]] for c in data["cases"]])
    for i, j in np.ndindex(values.shape):
        value = values[i, j]
        if np.isnan(value):
            ax.add_patch(
                Rectangle(
                    (j - 0.5, i - 0.5), 1, 1, facecolor="#eceff1", edgecolor="#adb5bb", hatch="///", linewidth=0.3
                )
            )
            ax.text(j, i, "invalid", ha="center", va="center", fontsize=9, color="#17242f")
        else:
            ax.text(
                j,
                i,
                f"{value:.3f}",
                ha="center",
                va="center",
                fontsize=10,
                color="white" if im.norm(value) > 0.58 else "#17242f",
            )
    bar = fig.colorbar(im, ax=ax, fraction=0.027, pad=0.025)
    bar.set_label("Experiment energy · lower is better (log color scale)")
    save(fig, "bf-case-energies")
    if heatmap_only:
        return
    t = np.array(data["cases"][0]["queries"][0]["t"])
    for mobile in (False, True):
        fig, axes = plt.subplots(
            2 if mobile else 1, 1 if mobile else 2, figsize=(6, 8) if mobile else (11, 4.3), layout="constrained"
        )
        a, b = axes.ravel()
        case = data["trajectory_slices"]["c005"]
        a.axvspan(0, 5, color="#e5e9ed", zorder=0)
        a.plot(t, np.mean(case["truth"], axis=0), color="#17242f", lw=2, label="Observed")
        a.plot(t, np.mean(case["forecasts"]["Qwen 397B"]["samples"], axis=0), color="#ae5528", lw=2, label="Qwen 397B")
        a.set(
            title="A  A pulse outside the response library",
            xlabel="Time",
            ylabel="Channel 2 · center sensor",
            ylim=(0, 2.7),
        )
        a.legend(frameon=False, loc="upper right", fontsize=10)
        for case_id, color, label in (
            ("c012", "#126e64", "Observed: pulse, then move"),
            ("c013", "#075dad", "Observed: move, then pulse"),
        ):
            case = data["trajectory_slices"][case_id]
            b.plot(t, np.mean(case["truth"], axis=0), color=color, lw=2, label=label)
        b.plot(
            t,
            np.mean(case["forecasts"]["GLM"]["samples"], axis=0),
            "--",
            color="#17242f",
            lw=2,
            label="GLM: either order",
        )
        b.set(title="B  The order of actions matters", xlabel="Time", ylabel="Channel 1 · center sensor")
        b.legend(frameon=False, fontsize=9, loc="lower left")
        for ax in axes.ravel():
            ax.grid(axis="y", alpha=0.15)
            ax.set_xlim(0, 50)
            title = ax.get_title()
            ax.set_title("")
            ax.set_title(title, loc="left", fontsize=12, pad=12)
        save(fig, "bf-predictor-diagnostics" + ("-mobile" if mobile else ""))
    print(f"Rendered BF case study from {DATA.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--heatmap-only", action="store_true")
    args = parser.parse_args()
    if args.capture:
        capture()
    render(heatmap_only=args.heatmap_only)

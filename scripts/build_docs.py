"""Build the static public documentation using only the Python standard library.

Sources live in docs_source/. Existing media and historical pages are retained.
No model, simulator, package manager, network access, or publishing is invoked.
"""

import hashlib
import json
import os
import re
import runpy
import shutil
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from world_equations import render_equations

ROOT = Path(__file__).resolve().parents[1]
SOURCE, DOCS = ROOT / "docs_source", ROOT / "docs"
PAGES = {"index": ("PhySim", "PhySim: a virtual science environment", "")}
MAIN = ("index",)
SECTIONS = {
    "worlds": "PhySim Worlds",
    "experiments": "Experimenting with virtual worlds",
    "evaluation": "Evaluating agents",
    "results": "Preliminary Results",
    "discovering": "Discovering new worlds",
    "next": "What’s next?",
    "get-involved": "Get Involved",
    "credit": "Credit",
}
# Use the exact runtime mapping without importing simulator dependencies.
REWARDS = runpy.run_path(str(ROOT / "environments/physim/physim/rewards.py"))
PRECISION = REWARDS["DEFAULT_PRECISION"]
LEGACY_FRAGMENTS = json.loads((SOURCE / "legacy-fragments.json").read_text())
REDIRECTS = {
    "worlds.html": "index.html#worlds",
    "experiment.html": "index.html#experiments",
    "scoring.html": "index.html#evaluation",
    "results.html": "index.html#results",
    "contribute.html": "index.html#get-involved",
    "fields.html": "index.html#field-model",
    "generation.html": "index.html#generation",
    "simulator.html": "index.html#numerics",
    "api.html": "index.html#actions",
    "registry.html": "https://github.com/swpo/physim/blob/main/registry/README.md",
    "try.html": "https://github.com/swpo/physim/blob/main/REPRODUCING.md",
    "archive/index.html": "https://github.com/swpo/physim/tree/main/probes",
}
DESCRIPTIONS = {
    "index": "Physim evaluates agents learning physics through experiments; Blobkit discovers worlds through simulation and evolutionary search over field equations.",
}


def table_of_contents():
    links = "".join(f'<li><a href="#{key}">{escape(label)}</a></li>' for key, label in SECTIONS.items())
    return '<nav class="contents" aria-label="Table of contents"><p>Contents</p><ol>' + links + "</ol></nav>"


def page_context(key, section, prefix=""):
    return ""


def continuation(key, prefix=""):
    return ""


def table(headers, rows, caption, numeric=True):
    return (
        '<div class="table-scroll"><table><caption>'
        + escape(caption)
        + "</caption><thead><tr>"
        + "".join('<th scope="col">' + escape(h) + "</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>"
            + "".join(
                "<td" + (' class="numeric"' if i and numeric else "") + ">" + str(c) + "</td>"
                for i, c in enumerate(row)
            )
            + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )


def generated_content():
    case_study = json.loads((SOURCE / "data/bf-case-study.json").read_text())
    calibration_path = SOURCE / "data/reward-calibration.json"
    calibration = json.loads(calibration_path.read_text()) if calibration_path.exists() else None
    if calibration and calibration["recommended_k"] != PRECISION:
        raise ValueError("Runtime precision does not match the reviewed calibration")
    reward_rows = []
    case_rows = []
    for row in case_study["models"]:
        reward = REWARDS["precision_reward"](row["energy"], PRECISION)
        reward_rows.append(dict(model=row["model"], name=row["name"], energy=row["energy"], reward=reward))
        usage = row["usage"]
        cost_note = ("†" if row["cost_basis"] == "estimate" else "") + (
            "*" if usage["undiscounted_cache_estimate"] else ""
        )
        anchor = next(s["file"] for s in row["predictor_sources"] if s["file"].endswith("/predictor.py"))
        name = f'<a href="{escape(anchor, quote=True)}">{escape(row["name"])}</a>'
        case_rows.append(
            (
                name,
                f"{reward:.3f}",
                f"{row['energy']:.4f}" if row["energy"] is not None else "Invalid",
                f"{row['experiments']:,}",
                f"${row['cost_usd']:.2f}{cost_note}",
            )
        )
    derived = dict(
        schema="physim-retrospective-rewards-v1",
        precision=PRECISION,
        mapping=REWARDS["REWARD_MAPPING"],
        models=reward_rows,
        source="bf-case-study.json",
        source_sha256=hashlib.sha256((SOURCE / "data/bf-case-study.json").read_bytes()).hexdigest(),
        note="Retrospective remapping of saved energies; no new agent rollouts.",
    )
    (DOCS / "data").mkdir(exist_ok=True, parents=True)
    (DOCS / "data/bf-reward-summary.json").write_text(json.dumps(derived, indent=2, allow_nan=False) + "\n")
    calibration_text = "<p>Native-simulator calibration is running; the precision target is provisional.</p>"
    if calibration:
        bf_energy = calibration["worlds"]["bf"]["mean_energy"]["64"]
        if bf_energy != max(record["mean_energy"]["64"] for record in calibration["worlds"].values()):
            raise ValueError("The BF-only calibration note assumes BF sets the precision target")
        calibration_text = (
            f"<p>We use <var>K</var> = {PRECISION:g}, giving full reward at <var>S</var> ≤ {10**-PRECISION:g}. "
            "The agent’s prompt states this target; it can be varied independently of the experiment and token budgets.</p>"
            "<details><summary>Precision calibration</summary><p>We generated 64 forecast samples using the actual world equations, with independent realizations of the world’s noise. These "
            f"were scored against two saved simulation realizations for every BF experiment. The mean energy was {bf_energy:.5f}. "
            "We chose the largest integer K whose full-reward threshold is at least twice this simulator-based score. "
            "This margin applies to this preparation and these measurement scales; "
            'it is not a universal precision limit. <a href="data/reward-calibration.json">Calibration record</a> · '
            '<a href="data/bf-reward-summary.json">Recomputed model rewards</a>.</p></details>'
        )
    return {
        "table_of_contents": table_of_contents(),
        "score_recipe": (SOURCE / "partials/scoring.html").read_text(),
        "reward_precision": f"{PRECISION:g}",
        "reward_calibration": calibration_text,
        **{
            f"{key}_equations": render_equations(
                key, source, json.loads((SOURCE / source["file"]).read_text(), parse_float=Decimal)
            )
            for key, source in json.loads((SOURCE / "data/equation-sources.json").read_text()).items()
        },
        "case_study_table": table(
            ("Model / predictor source", "Reward ↑", "Energy ↓", "Experiments", "Cost"),
            case_rows,
            "One BF rollout per model · Prime Agent · 15 evaluation experiments",
        ),
    }


def render(key, heading, section, body, title=None, description=None, prefix=""):
    values = {
        "root": prefix,
        "stylesheet": prefix + "site.css?v=" + hashlib.sha256((SOURCE / "site.css").read_bytes()).hexdigest()[:12],
        "title": escape(title or PAGES[key][0]),
        "description": escape(description or DESCRIPTIONS[key], quote=True),
        "heading": escape(heading),
        "context": page_context(key, section, prefix),
        "body": body,
        "continuation": continuation(key, prefix),
    }
    source = (SOURCE / "template.html").read_text()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], source)


def redirect(old, target):
    prefix = os.path.relpath(DOCS, (DOCS / old).parent) + "/"
    if urlsplit(target).scheme:
        relative, fallback, js_hash = target, "", '""'
    else:
        target_page, _, fragment = target.partition("#")
        relative = os.path.relpath(DOCS / target_page, (DOCS / old).parent)
        fallback = f"#{fragment}" if fragment else ""
        # Retain deep links within the site; repository destinations have their own anchors.
        js_hash = f"(window.location.hash || {json.dumps(fallback)})" if fallback else "window.location.hash"
    js_target = json.dumps(relative).replace("<", "\\u003c")
    chapter = {
        "fields": "worlds",
        "generation": "worlds",
        "simulator": "worlds",
        "api": "experiment",
        "blobs": "worlds",
        "rollouts": "results",
    }.get(Path(old).stem, Path(old).stem)
    aliases = LEGACY_FRAGMENTS.get(chapter, [])
    current_ids = set(re.findall(r'id="([^"]+)"', (SOURCE / "pages/index.html").read_text()))
    mapping = {name: name if name in current_ids else fallback.lstrip("#") for name in aliases}
    anchors = "".join(
        f'<a id="{escape(name)}" href="{escape(relative)}#{escape(destination)}">{escape(name)}</a> '
        for name, destination in mapping.items()
    )
    if mapping:
        js_hash = f'(map[window.location.hash.slice(1)] ? "#" + map[window.location.hash.slice(1)] : {js_hash})'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Page moved · Physim</title>
<link rel="stylesheet" href="{prefix}site.css"></head><body>
<main style="margin:3rem auto;padding:1rem"><h1>Page moved</h1>
<p><a href="{escape(relative + fallback, quote=True)}">Continue to this page</a>.</p>
<p><a href="{prefix}index.html">Current Physim documentation</a></p>
<div hidden>{anchors}</div></main>
<script>const map = {json.dumps(mapping)}; window.location.replace({js_target} + {js_hash});</script>
</body></html>'''


def build():
    DOCS.mkdir(exist_ok=True)
    blocks = generated_content()
    for key, (_, heading, section) in PAGES.items():
        body = (SOURCE / "pages" / f"{key}.html").read_text()
        body = re.sub(r"\{\{(\w+)\}\}", lambda m: blocks[m[1]], body)
        (DOCS / f"{key}.html").write_text(render(key, heading, section, body))
    for old, target in REDIRECTS.items():
        (DOCS / old).write_text(redirect(old, target))
    shutil.copyfile(SOURCE / "site.css", DOCS / "site.css")
    for source in json.loads((SOURCE / "data/equation-sources.json").read_text()).values():
        target = DOCS / source["file"]
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(SOURCE / source["file"], target)
    for filename in ("worlds.json", "results.json", "registry.json"):
        (DOCS / "data").mkdir(exist_ok=True)
        shutil.copyfile(SOURCE / filename, DOCS / "data" / filename)
    for filename in ("bf-evaluation.json", "bf-evaluation.npz", "bf-case-study.json", "reward-calibration.json"):
        if not (SOURCE / "data" / filename).exists():
            continue
        shutil.copyfile(SOURCE / "data" / filename, DOCS / "data" / filename)
    (DOCS / "examples").mkdir(exist_ok=True)
    for path in (SOURCE / "examples").iterdir():
        if path.is_file():
            shutil.copyfile(path, DOCS / "examples" / path.name)
    shutil.copytree(SOURCE / "examples/case-study", DOCS / "examples/case-study", dirs_exist_ok=True)
    # Only explicitly mapped old URLs are rewritten. Archive pages/media are inputs.
    records = json.loads((SOURCE / "archive-map.json").read_text())
    aliases = {"blobs.html": "index.html#worlds", "rollouts.html": "index.html#results"}
    for record in records:
        if record["old"] in {f"{key}.html" for key in PAGES} | set(REDIRECTS):
            continue
        target = aliases.get(record["old"], record["archive"])
        path = DOCS / record["old"]
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(redirect(record["old"], target))
    print(f"Built {len(PAGES)} current pages and compatibility redirects.")


if __name__ == "__main__":
    build()

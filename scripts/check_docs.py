"""Check static documentation, local links, and published evidence consistency."""

import hashlib
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from build_docs import DOCS, MAIN, PAGES, PRECISION, REDIRECTS, REWARDS, ROOT, SOURCE, redirect


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.images, self.meta = [], [], [], {}
        self.lang, self.h1, self.nav, self.main, self.titles = None, 0, [], False, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a" and "name" in a:
            self.ids.append(a["name"])
        for key in ("href", "src", "poster", "data-mobile-poster", "data-mobile-src"):
            if key in a:
                self.links.append(a[key])
        if "srcset" in a:
            self.links.extend(candidate.split()[0] for candidate in a["srcset"].split(","))
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.titles += 1
        if tag == "meta":
            self.meta[a.get("name")] = a.get("content")
        if tag == "img":
            self.images.append(a)
        if tag == "nav":
            self.nav.append(a.get("aria-label"))
        if tag == "main":
            self.main = a.get("id") == "main"


def check():
    pages, errors = {}, []
    for path in sorted(DOCS.rglob("*.html")):
        parser = Page()
        parser.feed(path.read_text())
        pages[path.resolve()] = parser
    links = 0
    for path, page in pages.items():
        for raw in page.links:
            url = urlsplit(raw)
            if url.scheme or url.netloc:
                continue
            links += 1
            target = (
                (DOCS / unquote(url.path).lstrip("/"))
                if url.path.startswith("/")
                else (path.parent / unquote(url.path) if url.path else path)
            ).resolve()
            if target.is_dir():
                target /= "index.html"
            if not target.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing {raw}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f"{path.relative_to(ROOT)}: missing fragment {raw}")
        if not page.meta.get("viewport"):
            errors.append(f"{path.relative_to(ROOT)}: missing viewport")
    for key in PAGES:
        path = DOCS / f"{key}.html"
        page = pages[path.resolve()]
        source = path.read_text()
        for condition, problem in (
            (page.lang == "en", "language"),
            (page.h1 == 1, "single h1"),
            (page.titles == 1, "single title"),
            (bool(page.meta.get("description")), "description"),
            (page.main, "main landmark/skip target"),
            (page.nav == ["Table of contents"], "single table of contents"),
            (not any(n > 1 for n in Counter(page.ids).values()), "unique IDs"),
            (all(img.get("alt") for img in page.images), "image alternatives"),
            ("{{" not in source, "resolved template variables"),
            (any(urlsplit(link).path == "site.css" for link in page.links), "shared stylesheet"),
        ):
            if not condition:
                errors.append(f"{path.name}: failed {problem}")
        if key in MAIN:
            index = MAIN.index(key)
            if index and f'rel="prev" href="{MAIN[index - 1]}.html"' not in source:
                errors.append(f"{path.name}: missing previous page in main flow")
            if index + 1 < len(MAIN) and f'rel="next" href="{MAIN[index + 1]}.html"' not in source:
                errors.append(f"{path.name}: missing next page in main flow")
    for old, target in REDIRECTS.items():
        if (DOCS / old).read_text() != redirect(old, target):
            errors.append(f"{old}: stale chapter redirect")
        for key in PAGES:
            if any(urlsplit(link).path == old for link in pages[(DOCS / f"{key}.html").resolve()].links):
                errors.append(f"{key}.html: link directly to the new section instead of {old}")
    catalog = json.loads((DOCS / "data/worlds.json").read_text())
    for world in catalog["worlds"]:
        for path in (DOCS / world["genome"]["file"], ROOT / world["genome"]["source"]):
            if hashlib.sha256(path.read_bytes()).hexdigest() != world["genome"]["sha256"]:
                errors.append(f"{path}: genome/catalog hash mismatch")
    for name in ("worlds.json", "results.json", "registry.json"):
        if (DOCS / "data" / name).read_bytes() != (SOURCE / name).read_bytes():
            errors.append(f"{name}: generated snapshot is stale")
    for source in json.loads((SOURCE / "data/equation-sources.json").read_text()).values():
        for root in (SOURCE, DOCS):
            path = root / source["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                errors.append(f"{path}: equation genome differs from its published source")
    visual_source = json.loads((SOURCE / "data/world-visuals.json").read_text())
    if hashlib.sha256((SOURCE / "data/world-visuals.npz").read_bytes()).hexdigest() != visual_source["data_sha256"]:
        errors.append("World visual data changed; review and regenerate the figures")
    bf_source = json.loads((SOURCE / "data/bf-evaluation.json").read_text())
    if hashlib.sha256((SOURCE / "data/bf-evaluation.npz").read_bytes()).hexdigest() != bf_source["data_sha256"]:
        errors.append("BF evaluation figure data changed; review and regenerate the figures")
    for filename in ("bf-evaluation.json", "bf-evaluation.npz", "bf-case-study.json"):
        if (SOURCE / "data" / filename).read_bytes() != (DOCS / "data" / filename).read_bytes():
            errors.append(f"{filename}: published figure evidence is stale")
    for path in (SOURCE / "examples").iterdir():
        if path.is_file() and path.read_bytes() != (DOCS / "examples" / path.name).read_bytes():
            errors.append(f"{path.name}: example is stale")
    case_study = json.loads((SOURCE / "data/bf-case-study.json").read_text())
    derived = json.loads((DOCS / "data/bf-reward-summary.json").read_text())
    if derived["source_sha256"] != hashlib.sha256((SOURCE / "data/bf-case-study.json").read_bytes()).hexdigest():
        errors.append("Retrospective reward source hash is stale")
    if derived["precision"] != PRECISION or len(derived["models"]) != len(case_study["models"]):
        errors.append("Retrospective reward target or model count differs")
    for original, remapped in zip(case_study["models"], derived["models"]):
        if (
            remapped["model"] != original["model"]
            or remapped["energy"] != original["energy"]
            or remapped["reward"] != REWARDS["precision_reward"](original["energy"], PRECISION)
        ):
            errors.append(f"Retrospective reward does not match saved energy: {original['model']}")
    calibration_path = SOURCE / "data/reward-calibration.json"
    if calibration_path.exists():
        calibration = json.loads(calibration_path.read_text())
        if calibration_path.read_bytes() != (DOCS / "data/reward-calibration.json").read_bytes():
            errors.append("Published reward calibration is stale")
        if calibration["members"] != 64 or calibration["recommended_k"] != PRECISION:
            errors.append("Calibration does not match the default forecast count or reward target")
        for world, count in (("bf", 15), ("xv", 15), ("p4g2_044", 19)):
            record = calibration["worlds"][world]
            if len(record["cases"]) != count or len({r["case"] for r in record["cases"]}) != count:
                errors.append(f"Incomplete or repeated native calibration cases for {world}")
            expected = sum(r["scores"]["64"] for r in record["cases"]) / count
            if abs(expected - record["mean_energy"]["64"]) > 1e-14:
                errors.append(f"Native calibration average differs for {world}")
    for world in ("bf-fields", "xv-fields", "p4g2_044-fields", "early-travel", "early-binding"):
        record = json.loads((DOCS / "assets/worlds" / f"{world}.json").read_text())
        video = DOCS / "assets/worlds" / f"{world}.mp4"
        if hashlib.sha256(video.read_bytes()).hexdigest() != record["video_sha256"]:
            errors.append(f"Movie no longer matches its simulation record: {world}")
        if max(record["encoding"]["mean_absolute_pixel_errors"]) > 5:
            errors.append(f"Encoded movie frames differ from source images: {world}")
    for row in case_study["models"]:
        for source in row["predictor_sources"]:
            for root in (SOURCE, DOCS):
                if hashlib.sha256((root / source["file"]).read_bytes()).hexdigest() != source["sha256"]:
                    errors.append(f"{source['file']}: submitted predictor source differs from evidence")
    records = json.loads((SOURCE / "archive-map.json").read_text())
    for record in records:
        archived = DOCS / record["archive"]
        if not archived.is_file() or "Research archive." not in archived.read_text():
            errors.append(f"{record['archive']}: missing archived original/banner")
    evidence = json.loads((SOURCE / "results.json").read_text())
    # Verify snapshots against research records when present; clean docs builds
    # do not require those optional research fixtures.
    fields = ("run", "model", "stop", "score_kind", "primary_joint_energy", "experiments")
    checked_sources = 0
    for profile in evidence["profiles"]:
        source = ROOT / profile["source"]["path"]
        if source.is_file():
            checked_sources += 1
            if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
                errors.append(f"{source}: evidence source changed; review snapshot")
            original = json.loads(source.read_text())["rows"]
            if len(original) != len(profile["rows"]):
                errors.append(f"{profile['id']}: missing or extra attempts")
            for a, b in zip(original, profile["rows"]):
                if any(a.get(k) != b.get(k) for k in fields):
                    errors.append(f"{b['run']}: snapshot differs from source")
    control_source = ROOT / evidence["control_source"]["path"]
    if control_source.is_file():
        checked_sources += 1
        if hashlib.sha256(control_source.read_bytes()).hexdigest() != evidence["control_source"]["sha256"]:
            errors.append("Control evidence source changed; review snapshot")
        if json.loads(control_source.read_text())["aggregate"] != evidence["controls"]["aggregate"]:
            errors.append("Control aggregates differ from source")
    # Both downloadable manuals are frozen documentation snapshots. Their source
    # and hash provenance are recorded in scripts/fixtures/README.md.
    substitutions = (
        ("n_ports", "12"),
        ("last_port", "11"),
        ("example_port", "2"),
        ("max_experiments", "1000"),
        ("max_total_tu", "50000"),
        ("max_validation_attempts", "128"),
        ("max_submission_attempts", "128"),
        ("predictor_cpus", "1"),
        ("predictor_memory_gib", "1"),
        ("predictor_cpu_seconds", "20"),
        ("predictor_wall_seconds", "30"),
        ("coding_tools", "Use the bash and edit tools to run commands and work with files."),
        ("reward_precision", f"{PRECISION:g}"),
        ("reward_threshold", f"10^(-{PRECISION:g})"),
    )
    contracts = (
        (
            "published_agent_spec.txt",
            "AGENT_SPEC.md",
            "27e431c3aecabb8efc6fb29d907635eca9040ae24b453f16f088c3c8959a494a",
        ),
        (
            "published_agent_spec_v1.txt",
            "AGENT_SPEC_V1.md",
            "04b8480edf8b73038d9f26a92a06141edc06f139b46a73ff67aa7f4421cbae90",
        ),
    )
    for fixture, example, expected_hash in contracts:
        template = (ROOT / "scripts/fixtures" / fixture).read_bytes()
        if hashlib.sha256(template).hexdigest() != expected_hash:
            errors.append(f"Published agent contract template {fixture} changed; review its provenance")
        contract = template.decode()
        for key, value in substitutions:
            contract = contract.replace("{" + key + "}", value)
        if contract != (SOURCE / "examples" / example).read_text():
            errors.append(f"Downloadable agent contract {example} differs from the published contract snapshot")
    summary = {
        "html_pages": len(pages),
        "current_pages": len(PAGES),
        "local_links_checked": links,
        "archived_originals": len(records),
        "evidence_sources_checked": checked_sources,
        "errors": errors,
    }
    print(json.dumps(summary, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(check())

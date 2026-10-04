"""Install the pinned environment and reproduce the reference outside the checkout.

Requires uv and an available Python >=3.12. Uses PyPI for declared dependencies,
never a model API. Leaves an inspectable clean install and reports in --workdir.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(args, cwd, env):
    print("Running: " + " ".join(str(x) for x in args[:3]), flush=True)
    result = subprocess.run(
        [str(x) for x in args], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode:
        raise RuntimeError(f"Command failed: {(result.stderr or result.stdout)[-4000:]}")
    if result.stderr:
        print(result.stderr[-2000:], file=sys.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    directory = args.workdir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(s in k.upper() for s in ("TOKEN", "API_KEY", "SECRET"))
        and k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
    }
    env["UV_CACHE_DIR"] = str(directory / "uv-cache")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required")
    release = tomllib.loads((ROOT / "configs/physim/release.toml").read_text())
    package = "physim @ " + release["code_packages"]["physim"]
    run([uv, "--no-config", "venv", "--python", sys.executable, directory / "venv"], directory, env)
    python = directory / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Resolve the package's declared public Blobkit dependency, just as a fresh
    # user install does; do not override its URL with a second local wheel.
    run([uv, "--no-config", "pip", "install", "--python", python, package], directory, env)
    shutil.copytree(args.bundle.resolve(), directory / "bundle")
    installed = json.loads(
        run(
            [
                python,
                "-I",
                "-c",
                """import json,sys,importlib.util,importlib.metadata as m
import physim,blobkit
from physim import Bundle
from physim import PhysimTaskset
from physim_r6 import R6Taskset
from verifiers.v1.utils.loaders import taskset_config_type, load_taskset
assert importlib.util.find_spec('verifiers') is not None
assert importlib.util.find_spec('physim.taskset') is not None
assert importlib.util.find_spec('physim.blobcore') is None
assert PhysimTaskset is R6Taskset
config = taskset_config_type('physim')(id='physim', task={'tools': {'bundle': 'bundle'}})
assert len(list(load_taskset(config))) == 1
assert not any('research' in k or k == 'device' for k in sys.modules)
print(json.dumps(dict(physim=physim.__file__,blobkit=blobkit.__file__,versions={n:m.version(n) for n in ('physim','blobkit','numpy','scipy','verifiers')})))""",
            ],
            directory,
            env,
        )
    )
    inspection = json.loads(
        run([python, "-I", "-m", "physim.cli", "inspect", "--bundle", directory / "bundle"], directory, env)
    )
    demo = json.loads(
        run(
            [
                python,
                "-I",
                "-m",
                "physim.cli",
                "demo",
                "--bundle",
                directory / "bundle",
                "--output",
                directory / "demo",
            ],
            directory,
            env,
        )
    )
    request = dict(
        actions=[dict(t=0, kind="inject", port=0, amp=0.5, dur=0.04)],
        queries=[dict(sensor=s, t=[0, 0.02, 0.06]) for s in ("device0", "device1", "global")],
    )
    apparatus = json.loads((directory / "bundle/apparatus.json").read_text())
    if apparatus.get("protocol") == "centered-pulse-v2":
        request["actions"][0]["device"] = 0
    (directory / "request.json").write_text(json.dumps(request))
    experiment = json.loads(
        run(
            [
                python,
                "-I",
                "-m",
                "physim.cli",
                "experiment",
                "--bundle",
                directory / "bundle",
                "--request",
                directory / "request.json",
                "--output",
                directory / "experiment",
            ],
            directory,
            env,
        )
    )
    report = dict(
        ok=demo["ok"],
        workdir=str(directory),
        installed=installed,
        inspection=inspection,
        reference_demo=demo,
        native_experiment=experiment,
        no_model_api=True,
        isolated_python=True,
        source_checkout_on_python_path=False,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

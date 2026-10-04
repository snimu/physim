"""Capture native harness diagnostics without changing prompts, tools, or retries."""

from __future__ import annotations

import importlib.metadata
import json
import re
from pathlib import Path


def redact(text):
    text = re.sub(r"(?i)(bearer\s+)[^\s'\"<>]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:--api-key|api_key|secret)[= :]+)[^\s'\"<>]+", r"\1[REDACTED]", text)
    return re.sub(r"(https?://[^\s?'\"<>]+)\?[^\s'\"<>]+", r"\1?[REDACTED]", text)


def install(directory):
    from verifiers.v1.harness import Harness

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    distribution = importlib.metadata.distribution("verifiers")
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "verifiers": distribution.version,
                "installation": json.loads(distribution.read_text("direct_url.json") or "null"),
                "behavior": "Native harness unchanged; capture redacted stdout and stderr before error truncation.",
            },
            indent=2,
        )
        + "\n"
    )
    original_check = Harness._check_result

    async def checked(self, trace, runtime, result):
        name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(trace.id))
        for stream in ("stdout", "stderr"):
            path = directory / f"{name}.harness.{stream}.log"
            with path.open("a") as output:
                output.write(redact(getattr(result, stream) or ""))
            path.chmod(0o600)
        return await original_check(self, trace, runtime, result)

    Harness._check_result = checked


def main():
    import argparse

    from verifiers.v1.cli.eval.main import main as eval_main

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    install(args.diagnostics)
    eval_main(remaining)


if __name__ == "__main__":
    main()

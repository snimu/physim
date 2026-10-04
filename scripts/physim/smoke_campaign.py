"""No-charge stock-harness smoke: local scripted responses, real Docker and grading."""

import argparse
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from physim.bundles import Bundle
from run_campaign import configuration, dump

PREDICTOR = """from pathlib import Path
import json
import numpy as np
def predict(actions, queries, n_samples=64, seed=0):
    with np.load(sorted(Path('/observations').glob('*.npz'))[-1]) as data:
        request=json.loads(data['request'].item())
        initial={q['sensor']: data[f'query{i}'][0,0].copy() for i,q in enumerate(request['queries'])}
    return {'samples':[np.broadcast_to(initial[q['sensor']],(n_samples,len(q['t']),*initial[q['sensor']].shape)).copy() for q in queries]}
"""

# Printed results are booleans only: never dump environment values, process
# arguments, framework connection credentials, or arbitrary runtime files.
BOUNDARY_PROBE = """import importlib.util, json, os, socket, urllib.request
from pathlib import Path
checks = {}
checks['private_packages_absent'] = all(importlib.util.find_spec(x) is None for x in ['physim', 'blobkit'])
checks['private_mounts_absent'] = not any(Path(x).exists() for x in ['/var/run/docker.sock', '/Users', '/host_mnt', '/registry'])
checks['provider_credentials_absent'] = not any(os.environ.get(x) for x in ['PRIME_API_KEY', 'OPENAI_API_KEY', 'HF_TOKEN', 'ANTHROPIC_API_KEY'])
for name, url in [('hf', 'https://huggingface.co/'), ('github', 'https://github.com/'), ('host_preview', 'http://vf.host.internal:8765/')]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            checks[name + '_blocked'] = response.status == 403
    except Exception:
        checks[name + '_blocked'] = True
try:
    connection = socket.create_connection(('1.1.1.1', 443), timeout=2)
    connection.close()
    checks['direct_network_blocked'] = False
except OSError:
    checks['direct_network_blocked'] = True
print(json.dumps({'boundary_audit': checks}))
assert all(checks.values())
"""


def main(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    bundle = Bundle(args.bundle)
    calls = []
    captured_requests = []
    steps = []
    if args.audit_boundary:
        steps.extend(
            [
                ("bash", {"command": "python - <<'PY'\n" + BOUNDARY_PROBE + "PY\n"}),
                ("laboratory_experiment", {"actions": [], "queries": [{"sensor": "global", "t": [0.013]}]}),
                ("laboratory_usage", {}),
            ]
        )
    if args.replay_trace:
        episode = json.loads(args.replay_trace.read_text().splitlines()[-1])
        for node in episode["traces"][-1]["nodes"]:
            message = node["message"]
            if message["role"] == "assistant":
                for call in message.get("tool_calls") or []:
                    steps.append((call["name"], json.loads(call["arguments"])))
    replayed_tool_calls = len(steps)
    steps += [
        (
            "laboratory_experiment",
            {"actions": [], "queries": [{"sensor": s, "t": [0]} for s in ["device0", "device1", "global"]]},
        ),
        ("bash", {"command": "cat > /workspace/predictor.py <<'PY'\n" + PREDICTOR + "PY\n"}),
        ("laboratory_validate", {}),
        ("laboratory_submit", {}),
    ]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if args.audit_boundary:
                captured_requests.append({key: body[key] for key in ("messages", "tools") if key in body})
            index = sum(len(m.get("tool_calls") or []) for m in body["messages"] if m["role"] == "assistant")
            tools = [t["function"]["name"] for t in body.get("tools", [])]
            calls.append(dict(index=index, model=body["model"], tool_names=tools))
            if index < len(steps):
                name, arguments = steps[index]
                assert name in tools, (name, tools)
                message = dict(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        dict(
                            id=f"call_{index}",
                            type="function",
                            function=dict(name=name, arguments=json.dumps(arguments)),
                        )
                    ],
                )
                reason = "tool_calls"
            else:
                message, reason = dict(role="assistant", content="Submitted."), "stop"
            response = dict(
                id=f"offline-{index}",
                object="chat.completion",
                created=0,
                model=body["model"],
                choices=[dict(index=0, message=message, finish_reason=reason)],
                usage=dict(prompt_tokens=10, completion_tokens=10, total_tokens=20, cost=0.0),
            )
            if body.get("stream"):
                delta = dict(message)
                if delta.get("tool_calls"):
                    delta["tool_calls"] = [dict(call, index=i) for i, call in enumerate(delta["tool_calls"])]
                first = dict(
                    response, object="chat.completion.chunk", choices=[dict(index=0, delta=delta, finish_reason=None)]
                )
                final = dict(
                    response, object="chat.completion.chunk", choices=[dict(index=0, delta={}, finish_reason=reason)]
                )
                encoded = (
                    "data: " + json.dumps(first) + "\n\ndata: " + json.dumps(final) + "\n\ndata: [DONE]\n\n"
                ).encode()
                content_type = "text/event-stream"
            else:
                encoded = json.dumps(response).encode()
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    model = dict(
        id="offline/scripted",
        specs=dict(context_window=10000, max_output_tokens=128),
        pricing=dict(input_usd_per_mtok=0, output_usd_per_mtok=0),
    )
    config = configuration(root, root, model, args.bundle.resolve())
    config["client"] = dict(
        type="eval",
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        api_key_var="PHYSIM_OFFLINE_SMOKE_KEY",
        headers={},
    )
    dump(root / "eval.json", config)
    command = [
        sys.executable,
        str(Path(__file__).with_name("campaign_diagnostics.py")),
        "--diagnostics",
        str(root / "diagnostics"),
    ]
    command += ["@", str(root / "eval.json")]
    try:
        with (root / "eval.log").open("w") as log:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    finally:
        server.shutdown()
        server.server_close()
    dump(root / "scripted_calls.json", calls)
    if args.audit_boundary:
        dump(root / "agent_visible_requests.json", captured_requests)
    if result.returncode:
        raise RuntimeError(f"Offline smoke failed; inspect {root / 'eval.log'}")
    paths = list((root / "runs").glob("*/traces.jsonl"))
    episode = json.loads(paths[0].read_text().splitlines()[-1])
    assert episode.get("traces"), episode.get("errors")
    trace = episode["traces"][-1]
    info = trace["info"]["r6"]
    assert trace["ok"], trace.get("errors")
    assert info["spend_final"]["accounted_cost_usd"] == 0
    assert not info["limit_audit"]["truncated"]
    assert info["grade"]["status"] == "COMPLETE"
    if args.audit_boundary:
        tool_outputs = [m.get("content", "") for r in captured_requests for m in r["messages"] if m["role"] == "tool"]
        boundary = next((text for text in tool_outputs if '"boundary_audit"' in text), None)
        assert boundary and "false" not in boundary.lower(), boundary
        assert any("multiple of 0.02 time units" in text for text in tool_outputs)
        # Look at what the actual native model request received, rather than
        # assuming the task prompt/tool docstrings are the entire interface.
        import re

        forbidden = re.compile(
            r"\b(spatial|fields?|grids?|geometry|translation|dilation|centered|sources?|pulses?|diffusion|periodic|lattice|activator|inhibitor|coordinates|poses?|blobkit|p4g2_044)\b",
            re.I,
        )
        public = [
            m.get("content", "")
            for r in captured_requests
            for m in r["messages"]
            if m["role"] in ("system", "user", "tool")
        ]
        public += [json.dumps(r.get("tools", [])) for r in captured_requests]
        assert not any(forbidden.search(text) for text in public), "Hidden-mechanism vocabulary reached the model"
        system = next(m["content"] for m in captured_requests[0]["messages"] if m["role"] == "system")
        assert "# Investigate and predict\n" in system
    expected = json.loads(bundle.verified_path("checks.json").read_text())["reference"]["primary_joint_energy"]
    assert abs(info["primary_joint_energy"] - expected) < 1e-10
    report = dict(
        ok=True,
        references=bundle.references(),
        model_calls=len(calls),
        cost_usd=0,
        energy=info["primary_joint_energy"],
        stop_condition=trace["stop_condition"],
        audit=info["limit_audit"],
        replayed_tool_calls=replayed_tool_calls,
        boundary_audited=args.audit_boundary,
    )
    if args.expected_experiments is not None:
        assert info["limit_audit"]["usage"]["experiments"] == args.expected_experiments
    dump(root / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path)
    parser.add_argument("--audit-boundary", action="store_true")
    parser.add_argument("--expected-experiments", type=int)
    main(parser.parse_args())

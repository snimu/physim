# Prime Agent integration

`physim_prime_agent` is an installable Verifiers harness adapter for the full
Prime Agent v0.9.5 executable. Prime Agent owns its Python kernel, agent loop,
compaction, subagents, and MCP client. Verifiers supplies provider interception,
runtime isolation, laboratory tools, and grading. The existing Bash harness
remains supported.

## Build and check the runtime

Install the locked workspace and build the base images from the repository root:

```sh
uv sync --locked
docker build -f scripts/physim/docker/predictor.Dockerfile \
  -t physim-predictor:0.12.0 scripts/physim/docker
docker build -f scripts/physim/docker/agent.Dockerfile \
  -t physim-agent:0.12.2 scripts/physim/docker
```

Download the Linux release matching the Docker architecture from
[Prime Agent v0.9.5](https://github.com/PrimeIntellect-ai/prime-agent/releases/tag/v0.9.5),
verify the release checksum, and extract it into a directory containing
`prime-agent` and `prime-agent-runtime/`. The BF case study used the Linux ARM64
archive with SHA256
`81303f98f31aed99aa641a66ccb87629940de1e45dd86d56ede1d88fd521971c`.
Use the extracted release directory as the build context:

```sh
docker build -f scripts/physim/docker/prime-agent.Dockerfile \
  -t physim-prime-agent:0.9.5 /path/to/verified-release
```

The Dockerfile installs the runtime and scientific dependencies before network
isolation. It records installed Python versions at
`/opt/prime-agent/python-lock.txt`. Rebuilding from the release is supported;
identical image bytes also require identical base images and dependency versions.
The [BF case-study record](../../BF_CASE_STUDY.md) identifies the original image.

Run the integration test against a verified local bundle, choosing an output
directory that does not already exist:

```sh
uv run python scripts/physim/smoke_prime_agent.py \
  --bundle /path/to/verified-bundle \
  --output outputs/prime-agent-offline-check
```

This uses a local scripted provider and makes no paid inference calls. It checks
isolation, native tool discovery, an experiment, predictor validation, submission,
and reference grading. Additional artifact and interface regressions are in:

```sh
uv run pytest tests/test_agent_visibility.py tests/test_prime_agent_harness.py -q
PHYSIM_DOCKER_TESTS=1 uv run pytest tests/test_artifact_store.py -q
```

## Selecting the harness

Set these fields in a Verifiers evaluation configuration, using the selected
model's context and response limits:

```json
{
  "env": {
    "agent": {
      "harness": {
        "id": "physim_prime_agent",
        "transport": "chat_completions",
        "context_window": 131072,
        "max_response_tokens": 8192,
        "thinking": "high",
        "thinking_format": "reasoning_effort"
      },
      "runtime": {
        "type": "docker",
        "image": "physim-prime-agent:0.9.5",
        "workdir": "/workspace",
        "allow": []
      }
    },
    "taskset": {
      "id": "physim",
      "task": {
        "agent_image": "physim-prime-agent:0.9.5",
        "coding_interface": "ipython",
        "tools": {"bundle": "/path/to/verified-bundle"}
      }
    }
  }
}
```

This is a configuration fragment: supply the model, client, resource limits, and
run settings separately. Supported transports are `chat_completions`, `responses`,
and `anthropic_messages`. The campaign runner chooses Messages for Anthropic,
Responses for OpenAI, and Chat Completions for its other recorded models.
The adapter requests one-hour native Anthropic caching. Provider pricing and
reported usage remain separate from this request.

Each rollout gets a new home and workspace. No personal credentials, history,
skills, simulator source, registry, or truths enter the agent container. Model
requests, including subagent calls, use Verifiers interception; general network
access remains blocked. The environment's `interface-only-v3-log-reward` instructions,
which also state the reward precision K, and agent-visible errors describe the
experimental interface without disclosing the hidden simulator. Checkpoints from
another prompt condition, including the BF case study's `interface-only-v2`, are rejected.

## Campaigns, diagnostics, and artifacts

`scripts/physim/run_campaign.py` resolves configs without model calls unless
`--execute` is supplied. It accepts an explicit model list, world list,
preparation directory, rollout count, and concurrency. A campaign directory
contains a recorded `catalog.json`; adding
`prime_agent.json` with `{"image":"physim-prime-agent:0.9.5"}` selects this harness.
Before execution, `scripts/physim/freeze_campaign.py --output CAMPAIGN` records
source and dependency identities. Each preparation must have matching completed
native validation. These local campaign inputs are not created by installing the
package or by selecting a released config.

`scripts/run_reviewed_stage.py` runs an explicitly selected stage and starts the
local progress logger. It returns after the stage for review. Concurrent jobs use
separate attempt directories; an error holds pending work while active peers
finish. Completed zero-reward model outcomes are retained. Provider-transient
replacements are bounded; other failures require inspection. The older
`scripts/run_open_batch.py` preserves the original campaign's queue/review rules.

Campaign settings have no automatic dollar stop. Spending is reported so the
operator can decide whether to launch more work. Provider-reported cost,
token-derived estimates, and conservative missing-usage reserves are distinct.
Native streaming usage is recorded by `scripts/physim/prime_agent_eval.py` without
changing the Prime Agent loop. Its diagnostic files exclude provider credentials.
The Bash diagnostic overlay is separate and guarded against dependency changes.

Submitted workspaces are bounded tar archives with hashes. They are restored in
Linux, preserving case-sensitive and Unicode-distinct filenames on macOS hosts.
Prediction receives read-only artifacts and observations. Infrastructure failures
remain Verifiers errors rather than being graded as failed model predictions.

For the released preparations and the separate case-study condition, see
[REPRODUCING.md](../../REPRODUCING.md).

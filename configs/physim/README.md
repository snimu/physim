# Physim configurations

`eval.toml` evaluates every preparation in the installed environment's pinned catalog,
one task each, with stock Verifiers' bash harness, the Prime runtime, and generous
investigation limits. Override `model` on the CLI. For local execution, set both
`env.agent.runtime.type` and `env.taskset.task.tools.predictor_runtime.type` to `docker`.
Pass `--env.taskset.task.tools.bundle /path/to/bundle` to evaluate one preparation instead.
Data are fetched and checked by the trusted host before model execution.

The config disables result uploads. `--dry-run` checks configuration without a model
call, but does not load or verify physical data. A wiring smoke uses
`-n 1 -r 2 --env.agent.max-turns 4`; use the full config for scientific rollouts.
Per-world presets and shared harness examples live with the environment in the
residency repository.

`release.toml` is release metadata, not a runtime default. It records the published
dataset revision, release ID and licenses, and the current code pins that the next
export will record.

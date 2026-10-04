# Physim configurations

`p4g2_044.toml`, `bf_trail_lab.toml`, and `xv_rotor_lab.toml` each select one
specific evaluation preparation at the verified HF commit
`dcd6abd5eae76a47f326c70518315d2d1e101d86`. They use stock Verifiers' bash harness,
Prime runtime (override both `env.agent.runtime.type` and
`env.taskset.task.tools.predictor_runtime.type` to `docker` for local execution), and generous investigation limits. Override `model` on the CLI.
Data are fetched and checked by the trusted host before model execution. Set
`env.taskset.task.tools.bundle_source.offline = true` to require a populated cache.

`eval.toml` evaluates all preparations in the installed environment's pinned catalog.
Pass `--env.taskset.task.tools.bundle /path/to/bundle` to select one local preparation.
The named configs preserve the original reference preparations explicitly; their
scientific inputs stay fixed when the environment dependency changes. These presets are
research inputs; environment implementation and shared harness examples live in
the residency repository.

All configs disable result uploads. `--dry-run` checks configuration without a
model call, but does not load or verify physical data. A wiring smoke uses
`-n 1 -r 2 --env.agent.max-turns 4`; use the full config for scientific rollouts.
The `bf-pilot.toml` and `xv-pilot.toml` files preserve historical local run settings.

`release.toml` records the latest dataset publication (`bd77a0da…`, 2026-09-28, with
three `centered-pulse-v2` preparations), its release ID and licenses, and the current
code pins that the next export will record. It is release metadata, not an implicit
runtime world-selection default; the named world configs above still pin `dcd6abd5…`.

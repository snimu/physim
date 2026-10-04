# Reusable configurations

Environment settings live in `configs/<environment>/`. Keep credentials and
outputs elsewhere. Physim's `eval.toml` uses the stock Bash harness and the Prime
runtime, and evaluates every preparation in the installed environment's pinned
catalog. `release.toml` records the approved license and dataset choices.

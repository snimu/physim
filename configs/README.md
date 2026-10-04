# Reusable configurations

Environment settings live in `configs/<environment>/`. Keep credentials and
outputs elsewhere. Physim's configs use the stock Bash harness and the Prime runtime
by default. The three named world configs each fetch one pinned HF bundle through
`bundle_source`; `eval.toml` evaluates every preparation in the installed environment's
pinned catalog. `release.toml` records the approved license and dataset choices.

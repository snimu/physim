# Reusable configurations

Environment settings live in `configs/<environment>/`. Keep credentials and
outputs elsewhere. Physim's configs use the stock Bash harness. The three
published-world configs each fetch one pinned HF bundle through `bundle_source`;
`eval.toml` takes a trusted local bundle. `release.toml` records the approved license
and dataset choices.

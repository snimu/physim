# Development scripts

Environment-specific build helpers, sandbox images, release utilities, and local
validation live in `scripts/<environment>/`. Repository-wide documentation builders
and figure renderers remain directly in this directory, as do a few Physim campaign
tools: `calibrate_reward.py` (the native reward calibration behind the docs),
`campaign_progress.py`, `campaign_results.py`, `render_campaign_results.py`,
`run_open_batch.py` and `run_reviewed_stage.py`. Synthetic-data tools live in `generators/`.

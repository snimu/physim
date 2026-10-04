# Physim support scripts

Run from the repository root through `uv run python scripts/physim/<script>.py`.

- `docker/`: historical image recipes for the published 0.12.x setup. The current
  installed environment provisions portable runtimes; see `environments/physim/README.md`.
- `examples/`: a zero predictor and a short native experiment request.
- `check_clean_install.py`: install the pinned environment and its released Blobkit
  dependency outside the checkout, and
  reproduce the persistence score plus a short native experiment without a model.
- `check_published_install.py`: install the public wheel and its public dependency,
  copy the three world configs from `--configs`, fetch the bundles they pin, and verify
  native/offline operation from a fresh directory. Requires an HTTPS wheel URL with a
  SHA-256 fragment.
- `prepare_world_release.py`: stage approved data/license metadata for HF; never uploads.
- Campaign tools: `run_campaign.py` (concurrent-world, spend-accounted campaigns),
  `freeze_campaign.py`, `campaign_diagnostics.py`, `prime_agent_eval.py`, `prime_usage.py`,
  and the no-charge smoke tests `smoke_campaign.py` and `smoke_prime_agent.py`. They use
  the installed environment and its native harnesses; see `DEVELOPMENT.md`.
- `validation/`: existing scientific and integration checks kept for local research
  reproducibility. These are not new per-environment tests for upstream submission.

Reference export and parity migration live in `generators/physim/`.

`check_harness_image.py` verifies the installed stock bash harness can resolve its
dependencies and start in the agent image with Docker networking disabled. Run
it with the historical release and image. Current environment smoke tests are
maintained in the residency repository. See `DEVELOPMENT.md` for the active workflow.

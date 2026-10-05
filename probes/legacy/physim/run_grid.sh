#!/usr/bin/env bash
# grid runner: models x difficulties, chat tier (null harness)
# Historical (February 2026): drives the retired M0 environment archived in this directory;
# its flags and the path below no longer apply to the installed physim package.
set -u
cd /Users/spoho/Documents/prime/test/physim
export PRIME_API_KEY=$(.venv/bin/python -c "import json;print(json.load(open('$HOME/.prime/config.json'))['api_key'])")
MODEL="$1"; DIFF="$2"; N="${3:-3}"
SAFE=$(echo "$MODEL" | tr '/' '-')
.venv/bin/eval physim -n "$N" -m "$MODEL" \
  --env.scientist.harness.id null \
  --env.taskset.difficulty "$DIFF" \
  --rich false \
  > "/tmp/physim_${SAFE}_${DIFF}.log" 2>&1
echo "done $MODEL $DIFF"

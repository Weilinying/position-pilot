#!/bin/zsh
# 由用户在终端执行一次有限 4B Primary；不启动 Repeat / Research / Earnings。
set -euo pipefail
p4_root=/Users/linyingwei/Documents/position-pilot
p4_candidate=/private/tmp/position-pilot-phase4b-candidate-v1
p4_config=/private/tmp/position-pilot-phase4b-t6/docs/evaluation/reports/2026-10-04-phase4b-candidate-v1-config.json
cd "$p4_candidate"
# 离线预检先于凭证装载和任何真实模型请求。
PYTHONPATH=backend:tests/evaluation "$p4_root/.venv/bin/python" - "$p4_config" <<'PY'
import sys
from pathlib import Path
from phase4_strategy_freeze import verify_candidate
verify_candidate(Path(sys.argv[1]))
print("4B Candidate preflight PASS; only AQ13–AQ16 / 6 Ask.")
PY
p4_stamp=$(date -u +%Y%m%dT%H%M%SZ)
p4_artifact="$p4_root/build/evaluation-runs/p4b-gemini-primary-v1-$p4_stamp"
mkdir -p "$p4_artifact"
cp "$p4_config" "$p4_artifact/candidate-config.json"
unset GEMINI_API_KEY
RUN_PHASE4_STRATEGY_EVAL=1 \
LLM_PROVIDER=GOOGLE_GEMINI \
LLM_MODEL=gemini-3.8-flash \
PHASE4_CASE_IDS=AQ13,AQ14,AQ15,AQ16 \
PHASE4_CANDIDATE_CONFIG="$p4_artifact/candidate-config.json" \
EVAL_RUN_ID="p4b-gemini-primary-v1-$p4_stamp" \
PHASE4_ARTIFACT_DIR="$p4_artifact" \
UV_PROJECT_ENVIRONMENT="$p4_root/.venv" \
uv run --no-sync --env-file "$p4_root/.env" "$p4_root/.venv/bin/pytest" \
  tests/evaluation/test_phase4_strategy_online.py -m online -s -q
print -r -- "Artifact: $p4_artifact"
# pytest pass 仅代表流程执行；Behavioral / Critical / Rubric 留待 Human Review。

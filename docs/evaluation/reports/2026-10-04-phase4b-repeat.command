#!/bin/zsh
# 用户执行有限一致性 Gate；不启动 Research 或其他 Core Case。
set -euo pipefail
p4_root=/Users/linyingwei/Documents/position-pilot
p4_candidate=/private/tmp/position-pilot-phase4b-candidate-v1
p4_driver=/private/tmp/position-pilot-phase4b-t6
p4_config="$p4_driver/docs/evaluation/reports/2026-10-04-phase4b-candidate-v1-config.json"
p4_primary="$p4_root/build/evaluation-runs/p4b-gemini-primary-v1-20261004T141232Z"
cd "$p4_candidate"
# 优先导入冻结副本的既有 Harness / Production；只有新外层命令来自执行分支。
export PYTHONPATH="$p4_candidate/backend:$p4_candidate/tests/evaluation:$p4_driver/tests/evaluation"
"$p4_root/.venv/bin/python" -m phase4b_repeat_gate \
  --config "$p4_config" --primary "$p4_primary" --plan-only
p4_stamp=$(date -u +%Y%m%dT%H%M%SZ)
p4_artifact="$p4_root/build/evaluation-runs/p4b-gemini-repeat-v1-$p4_stamp"
print -r -- "Artifact: $p4_artifact"
unset GEMINI_API_KEY
LLM_PROVIDER=GOOGLE_GEMINI \
LLM_MODEL=gemini-3.8-flash \
UV_PROJECT_ENVIRONMENT="$p4_root/.venv" \
uv run --no-sync --env-file "$p4_root/.env" "$p4_root/.venv/bin/python" \
  -m phase4b_repeat_gate --config "$p4_config" --primary "$p4_primary" --artifact "$p4_artifact"
print -r -- "Artifact: $p4_artifact"
# Runtime 完成不是 Behavioral / Critical PASS；结束后等待逐次 Review。

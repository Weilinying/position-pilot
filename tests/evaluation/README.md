# Behavioral Evaluation Test Package

长期 Evaluation 入口、运行方式、Failure Taxonomy 与 Acceptance 边界见 `docs/evaluation/README.md`。

本目录保持最小实现说明：

- `test_real_model_behavior.py` 定义 Dataset `1.0`、固定 Fixtures、Coverage Matrix、Controlled Contrast、Run Metadata、Reporter 与 pytest Assertions；
- pytest 是唯一 Execution Engine；
- Real-model Cases 需要显式 `RUN_REAL_LLM_BEHAVIORAL_EVAL=1` 与本地 Credential，不进入默认 CI；
- Model Selection 实验见 `docs/evaluation/model-selection.md`，报告保存在 `docs/evaluation/reports/`。

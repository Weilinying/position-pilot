"""4B 生命周期 Overlay；不改写 Dataset 0.1 或已验收 4A Manifest。"""

STRATEGY_SCRIPT_VERSION = "phase4b-strategy-v1"
STRATEGY_QUESTIONS = {
    "AQ13": ("结合我已经确认的 GOOG 长期 Thesis 和期限，判断是否继续持有。",),
    "AQ14": ("我之前的 GOOG 长期策略已经失效、待复核。现在应该如何判断？",),
    "AQ15": (
        "请删除我之前已经确认的 GOOG LONG_TERM 目标资本配置计划。",
        "现在分析 GOOG 时还会用旧计划吗？",
    ),
    "AQ16": (
        "GOOG 最近适合怎么分批买？",
        "你上次提过分批买，我没有确认。现在我的既定策略是什么？",
    ),
}


def strategy_manifest() -> dict[str, object]:
    """标明真实 Lifecycle 与延后范围；FULL 表示能力可测试，不代表 PASS。"""
    return {
        "script_version": STRATEGY_SCRIPT_VERSION,
        "case_ids": list(STRATEGY_QUESTIONS),
        "model_turn_count": 6,
        "scope": "FULL",
        "setup": {
            "AQ13": "真实 Service 确认 Thesis/Horizon，新 Thread 与新 Service 读取",
            "AQ14": "真实 Service 失效旧 Thesis；新 Pending 草案过期，不再读取",
            "AQ15": "确认 Position Plan；模型提失效草案，显式确认后新 Thread 再问",
            "AQ16": "无已确认 Strategy，同 Thread 两轮未确认建议",
        },
        "questions": STRATEGY_QUESTIONS,
        "aq14_overlay_reason": (
            "当前 Contract 没有 ACTIVE Strategy 自动过期或 STALE Version；"
            "使用真实 INVALIDATED 与过期 Candidate，不伪造状态"
        ),
        "aq15_overlay_reason": (
            "旧分批计划不是可持久 Payload；目标资本配置取代旧描述，"
            "确认是独立 Application 操作而非聊天肯定词"
        ),
        "fixture_setup_is_model_evidence": False,
        "memory": "NoOp online default; filtered fixture only in offline regression",
        "research": "DEFERRED",
        "earnings": "DEFERRED",
        "repeat": "NOT_RUN; Primary Human Review 后单独批准",
    }

"""4B 四案例一次有限 Primary，评分留待 Human Review。"""

import json
import os

import pytest
from phase4_strategy_harness import RUN_STRATEGY_ENV, run_strategy_evaluation


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(os.getenv(RUN_STRATEGY_ENV) != "1", reason="需要显式 4B 在线授权")
def test_phase4_strategy_primary() -> None:
    result = run_strategy_evaluation()
    print(json.dumps(result["summary"], ensure_ascii=False, default=str, indent=2))

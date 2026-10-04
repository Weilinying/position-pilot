"""Production 不得依赖已迁到测试目录的手写 Runtime。"""

import ast
from pathlib import Path

import position_pilot


def test_production_has_no_legacy_runtime_dependency() -> None:
    """防止未来重新装配旧 Loop，或在发布包中依赖测试模块。"""
    package = Path(position_pilot.__file__).parent
    violations: list[str] = []
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for module in modules:
                assert isinstance(node, (ast.Import, ast.ImportFrom))
                if (
                    module == "legacy"
                    or module.startswith("legacy.")
                    or module == "tests"
                    or module.startswith("tests.")
                    or module == "position_pilot.integrations.aliyun_llm"
                ):
                    violations.append(f"{path.relative_to(package)}:{node.lineno}: {module}")
            if isinstance(node, ast.ClassDef) and node.name in {
                "InvestmentAgent",
                "ModelCompletionRuntime",
            }:
                violations.append(f"{path.relative_to(package)}:{node.lineno}: {node.name}")
    assert violations == []

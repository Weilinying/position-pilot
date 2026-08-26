"""Investment Agent 的自由文本 Answer 与结构化 Source References。"""

import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import normalize_ticker

MAX_ANSWER_LENGTH = 12_000
MAX_SOURCE_REFERENCES = 20


class SourceReferenceType(StrEnum):
    """Final Answer 当前允许声明使用的 Context 类型。"""

    PORTFOLIO_SNAPSHOT = "PORTFOLIO_SNAPSHOT"
    CURRENT_QUOTE = "CURRENT_QUOTE"
    PRICE_HISTORY = "PRICE_HISTORY"
    RECENT_NEWS = "RECENT_NEWS"


class InvalidStructuredAnswer(ValueError):
    """LLM Final Completion 不满足稳定 JSON Contract。"""


class UnresolvedSourceReference(ValueError):
    """Source Reference 无法绑定到本轮成功取得的 Context。"""


@dataclass(frozen=True, slots=True)
class SourceReference:
    """模型声明回答使用的 Context 身份，不承载任何金融事实值。"""

    type: SourceReferenceType
    ticker: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, SourceReferenceType):
            raise InvalidStructuredAnswer("SourceReference.type 无效")
        if self.type is SourceReferenceType.PORTFOLIO_SNAPSHOT:
            if self.ticker is not None:
                raise InvalidStructuredAnswer("PORTFOLIO_SNAPSHOT Source Reference 不允许 ticker")
            return
        if not isinstance(self.ticker, str):
            raise InvalidStructuredAnswer(f"{self.type.value} Source Reference 必须包含 ticker")
        try:
            normalized_ticker = normalize_ticker(self.ticker)
        except (InvalidPortfolioValue, AttributeError) as error:
            raise InvalidStructuredAnswer("SourceReference.ticker 格式无效") from error
        object.__setattr__(self, "ticker", normalized_ticker)


@dataclass(frozen=True, slots=True)
class StructuredInvestmentAnswer:
    """LLM 返回的自由文本 Answer 与其声明使用的结构化来源。"""

    answer: str
    source_refs: tuple[SourceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise InvalidStructuredAnswer("answer 必须是非空字符串")
        if len(self.answer) > MAX_ANSWER_LENGTH:
            raise InvalidStructuredAnswer(f"answer 长度不得超过 {MAX_ANSWER_LENGTH}")
        if not isinstance(self.source_refs, tuple):
            raise InvalidStructuredAnswer("source_refs 必须是 tuple")
        if len(self.source_refs) > MAX_SOURCE_REFERENCES:
            raise InvalidStructuredAnswer(f"source_refs 数量不得超过 {MAX_SOURCE_REFERENCES}")
        if any(not isinstance(reference, SourceReference) for reference in self.source_refs):
            raise InvalidStructuredAnswer("source_refs 包含不支持的类型")
        if len(set(self.source_refs)) != len(self.source_refs):
            raise InvalidStructuredAnswer("source_refs 不得重复")


def structured_answer_schema() -> dict[str, object]:
    """返回可注入 Prompt / Repair Payload 的稳定 JSON Schema。"""

    return {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_ANSWER_LENGTH,
            },
            "source_refs": {
                "type": "array",
                "maxItems": MAX_SOURCE_REFERENCES,
                "uniqueItems": True,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": SourceReferenceType.PORTFOLIO_SNAPSHOT.value},
                            },
                            "required": ["type"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "enum": [
                                        SourceReferenceType.CURRENT_QUOTE.value,
                                        SourceReferenceType.PRICE_HISTORY.value,
                                        SourceReferenceType.RECENT_NEWS.value,
                                    ]
                                },
                                "ticker": {"type": "string"},
                            },
                            "required": ["type", "ticker"],
                            "additionalProperties": False,
                        },
                    ]
                },
            },
        },
        "required": ["answer", "source_refs"],
        "additionalProperties": False,
    }


def parse_structured_answer(content: str) -> StructuredInvestmentAnswer:
    """严格解析外层 JSON，但不解析或验证 answer 自然语言。"""

    if not isinstance(content, str) or not content.strip():
        raise InvalidStructuredAnswer("Structured Answer content 不能为空")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise InvalidStructuredAnswer("Final Response 必须是有效 JSON object") from error
    if not isinstance(payload, Mapping) or set(payload) != {"answer", "source_refs"}:
        raise InvalidStructuredAnswer("Structured Answer 只能包含 answer 与 source_refs")
    raw_answer = payload.get("answer")
    if not isinstance(raw_answer, str):
        raise InvalidStructuredAnswer("answer 必须是字符串")
    raw_source_refs = payload.get("source_refs")
    if not isinstance(raw_source_refs, list):
        raise InvalidStructuredAnswer("source_refs 必须是 array")
    return StructuredInvestmentAnswer(
        answer=raw_answer,
        source_refs=tuple(_parse_source_reference(value) for value in raw_source_refs),
    )


def validate_source_references(
    answer: StructuredInvestmentAnswer,
    available_sources: Collection[SourceReference],
) -> None:
    """验证每个声明来源都对应本轮实际成功取得的 Context。"""

    available = set(available_sources)
    for reference in answer.source_refs:
        if reference not in available:
            owner = reference.type.value
            if reference.ticker is not None:
                owner = f"{owner}({reference.ticker})"
            raise UnresolvedSourceReference(f"{owner} 没有对应的本轮成功 Context")


def _parse_source_reference(value: object) -> SourceReference:
    if not isinstance(value, Mapping):
        raise InvalidStructuredAnswer("Source Reference 必须是 object")
    raw_type = value.get("type")
    if not isinstance(raw_type, str):
        raise InvalidStructuredAnswer("SourceReference.type 必须是字符串")
    try:
        reference_type = SourceReferenceType(raw_type)
    except ValueError as error:
        raise InvalidStructuredAnswer("SourceReference.type 无效") from error
    if reference_type is SourceReferenceType.PORTFOLIO_SNAPSHOT:
        if set(value) != {"type"}:
            raise InvalidStructuredAnswer("PORTFOLIO_SNAPSHOT 只能包含 type")
        return SourceReference(reference_type)
    if set(value) != {"type", "ticker"}:
        raise InvalidStructuredAnswer(f"{reference_type.value} 只能包含 type 与 ticker")
    ticker = value.get("ticker")
    if not isinstance(ticker, str):
        raise InvalidStructuredAnswer("SourceReference.ticker 必须是字符串")
    return SourceReference(reference_type, ticker)

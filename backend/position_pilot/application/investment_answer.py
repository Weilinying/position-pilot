"""Investment Agent 的结构化 Answer Parts 与确定性 Fact Renderer。"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.market_data import MarketDataResult, MarketDataStatus, MarketQuote
from position_pilot.domain.portfolio import normalize_ticker

MAX_ANSWER_PARTS = 50
MAX_TEXT_PART_LENGTH = 4_000
MAX_TOTAL_TEXT_LENGTH = 12_000


class AnswerPartType(StrEnum):
    """当前支持的最小 Answer Part 类型。"""

    TEXT = "text"
    FACT_REFERENCE = "fact_ref"


class AnswerFactType(StrEnum):
    """已经迁移到结构化引用的确定性事实类型。"""

    CURRENT_QUOTE = "CURRENT_QUOTE"


class InvalidStructuredAnswer(ValueError):
    """LLM Answer Parts 不满足稳定 JSON Contract。"""


class UnresolvedFactReference(ValueError):
    """Fact Reference 无法绑定到本轮成功 Tool Result。"""


@dataclass(frozen=True, slots=True)
class TextPart:
    """由 LLM 生成的解释与自然语言连接文本。"""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise InvalidStructuredAnswer("TextPart.text 必须是非空字符串")
        if len(self.text) > MAX_TEXT_PART_LENGTH:
            raise InvalidStructuredAnswer(f"TextPart.text 长度不得超过 {MAX_TEXT_PART_LENGTH}")


@dataclass(frozen=True, slots=True)
class FactReferencePart:
    """只声明事实身份，不允许携带 LLM 生成的 authoritative value。"""

    fact_type: AnswerFactType
    ticker: str

    def __post_init__(self) -> None:
        if not isinstance(self.fact_type, AnswerFactType):
            raise InvalidStructuredAnswer("FactReferencePart.fact_type 无效")
        try:
            normalized_ticker = normalize_ticker(self.ticker)
        except (InvalidPortfolioValue, AttributeError) as error:
            raise InvalidStructuredAnswer("FactReferencePart.ticker 格式无效") from error
        object.__setattr__(self, "ticker", normalized_ticker)


AnswerPart = TextPart | FactReferencePart


@dataclass(frozen=True, slots=True)
class StructuredInvestmentAnswer:
    """LLM Final Completion 必须返回的有序 Answer Parts。"""

    parts: tuple[AnswerPart, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.parts, tuple) or not 1 <= len(self.parts) <= MAX_ANSWER_PARTS:
            raise InvalidStructuredAnswer(f"parts 数量必须在 1 到 {MAX_ANSWER_PARTS} 之间")
        if any(not isinstance(part, (TextPart, FactReferencePart)) for part in self.parts):
            raise InvalidStructuredAnswer("parts 包含不支持的类型")
        total_text_length = sum(len(part.text) for part in self.parts if isinstance(part, TextPart))
        if total_text_length > MAX_TOTAL_TEXT_LENGTH:
            raise InvalidStructuredAnswer(f"TextPart 总长度不得超过 {MAX_TOTAL_TEXT_LENGTH}")


@dataclass(frozen=True, slots=True)
class ResolvedInvestmentAnswer:
    """后端解析 Fact Reference 后的最终文本与 LLM 原始文本。"""

    answer: str
    llm_text: str
    referenced_current_quote_tickers: tuple[str, ...]


def structured_answer_schema() -> dict[str, object]:
    """返回可注入 Prompt / Repair Payload 的稳定 JSON Schema。"""

    return {
        "type": "object",
        "properties": {
            "parts": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_ANSWER_PARTS,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": AnswerPartType.TEXT.value},
                                "text": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": MAX_TEXT_PART_LENGTH,
                                },
                            },
                            "required": ["type", "text"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": AnswerPartType.FACT_REFERENCE.value},
                                "fact_type": {"const": AnswerFactType.CURRENT_QUOTE.value},
                                "ticker": {"type": "string"},
                            },
                            "required": ["type", "fact_type", "ticker"],
                            "additionalProperties": False,
                        },
                    ]
                },
            }
        },
        "required": ["parts"],
        "additionalProperties": False,
    }


def parse_structured_answer(content: str) -> StructuredInvestmentAnswer:
    """严格解析 LLM JSON，拒绝 price 等未声明字段。"""

    if not isinstance(content, str) or not content.strip():
        raise InvalidStructuredAnswer("Structured Answer content 不能为空")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise InvalidStructuredAnswer("Final Response 必须是有效 JSON object") from error
    if not isinstance(payload, Mapping) or set(payload) != {"parts"}:
        raise InvalidStructuredAnswer("Structured Answer 只能包含 parts")
    raw_parts = payload.get("parts")
    if not isinstance(raw_parts, list):
        raise InvalidStructuredAnswer("parts 必须是 array")
    return StructuredInvestmentAnswer(tuple(_parse_part(raw_part) for raw_part in raw_parts))


def resolve_structured_answer(
    answer: StructuredInvestmentAnswer,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
) -> ResolvedInvestmentAnswer:
    """只从本轮成功 Quote Result 填充 authoritative price。"""

    rendered_parts: list[str] = []
    llm_text_parts: list[str] = []
    referenced_tickers: list[str] = []
    for part in answer.parts:
        if isinstance(part, TextPart):
            rendered_parts.append(part.text)
            llm_text_parts.append(part.text)
            continue
        quote = _resolve_current_quote(part, market_results_by_ticker)
        rendered_parts.append(f"{_format_decimal(quote.last_price)} {quote.currency}")
        referenced_tickers.append(part.ticker)
    return ResolvedInvestmentAnswer(
        answer="".join(rendered_parts),
        llm_text="".join(llm_text_parts),
        referenced_current_quote_tickers=tuple(referenced_tickers),
    )


def _parse_part(value: object) -> AnswerPart:
    if not isinstance(value, Mapping):
        raise InvalidStructuredAnswer("Answer Part 必须是 object")
    part_type = value.get("type")
    if part_type == AnswerPartType.TEXT.value:
        if set(value) != {"type", "text"}:
            raise InvalidStructuredAnswer("TextPart 只能包含 type 与 text")
        text = value.get("text")
        if not isinstance(text, str):
            raise InvalidStructuredAnswer("TextPart.text 必须是字符串")
        return TextPart(text)
    if part_type == AnswerPartType.FACT_REFERENCE.value:
        if set(value) != {"type", "fact_type", "ticker"}:
            raise InvalidStructuredAnswer("FactReferencePart 只能包含 type、fact_type 与 ticker")
        raw_fact_type = value.get("fact_type")
        if not isinstance(raw_fact_type, str):
            raise InvalidStructuredAnswer("FactReferencePart.fact_type 必须是字符串")
        try:
            fact_type = AnswerFactType(raw_fact_type)
        except ValueError as error:
            raise InvalidStructuredAnswer("FactReferencePart.fact_type 无效") from error
        ticker = value.get("ticker")
        if not isinstance(ticker, str):
            raise InvalidStructuredAnswer("FactReferencePart.ticker 必须是字符串")
        return FactReferencePart(fact_type=fact_type, ticker=ticker)
    raise InvalidStructuredAnswer("Answer Part type 无效")


def _resolve_current_quote(
    reference: FactReferencePart,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
) -> MarketQuote:
    result = market_results_by_ticker.get(reference.ticker)
    if result is None or result.status is not MarketDataStatus.OK or result.data is None:
        raise UnresolvedFactReference(
            f"CURRENT_QUOTE({reference.ticker}) 没有对应的成功 Tool Result"
        )
    if result.data.ticker != reference.ticker:
        raise UnresolvedFactReference(
            f"CURRENT_QUOTE({reference.ticker}) 与 Tool Result ticker 不一致"
        )
    return result.data


def _format_decimal(value: Decimal) -> str:
    """以普通十进制文本渲染并移除无意义的尾随零。"""

    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered

"""M4 Final Response 的确定性 Grounding Contract Guard。"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from position_pilot.application.investment_context import (
    PortfolioSnapshot,
    PriceDirection,
    QuoteDerivedFacts,
    RecentPriceHistoryFacts,
)
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)

_NUMBER_PATTERN = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?")
_ISO_DATE_OR_TIME_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?\b"
)
_FINANCIAL_UNIT_PATTERN = re.compile(
    r"^\s*(?:USD|美元|美金|元|股|shares?|%|％)",
    re.IGNORECASE,
)
_FINANCIAL_KEYWORD_PATTERN = re.compile(
    r"价格|报价|现金|成本|金额|股数|数量|权重|比例|阈值|盈利|亏损|收益|"
    r"收盘|高点|低点|涨跌|价格路径|柱数|price|quote|cash|cost|share|weight|ratio|"
    r"profit|loss|return|close|high|low|change|bar",
    re.IGNORECASE,
)
_BUYING_POWER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:现金|资金|购买力).{0,30}(?:足够|不足|不够).{0,30}"
        r"(?:购买|买入|支付|覆盖).{0,16}(?:一股|至少|整股)",
        r"(?:买得起|买不起|可以买|可买|能买|不能买|无法买).{0,12}"
        r"(?:一股|至少一股|整股)",
        r"(?:可以|能够|无法|不能).{0,12}(?:购买|买入).{0,16}"
        r"(?:一股|至少一股|整股)",
        r"(?:现金|资金).{0,30}覆盖.{0,12}(?:一股|单股)",
        r"(?:具备|拥有).{0,12}(?:购买|买入).{0,12}(?:资金条件|能力)",
        r"(?:enough|insufficient)\s+(?:cash|funds).{0,30}(?:buy|purchase).{0,20}share",
        r"(?:can|cannot|can't)\s+(?:afford|buy|purchase).{0,20}share",
    )
)
_RELATION_VALUES_PATTERN = r"(ABOVE|BELOW|EQUAL)"
_PRICE_DIRECTION_VALUES_PATTERN = r"(UP|DOWN|FLAT)"


class GroundingViolationCode(StrEnum):
    """Guard 只覆盖已确认的高置信 Context Contract 越界类型。"""

    UNSUPPORTED_FINANCIAL_NUMBER = "UNSUPPORTED_FINANCIAL_NUMBER"
    BUYING_POWER_CLAIM = "BUYING_POWER_CLAIM"
    CASH_QUOTE_RELATION_CONTRADICTION = "CASH_QUOTE_RELATION_CONTRADICTION"
    PRICE_COST_RELATION_CONTRADICTION = "PRICE_COST_RELATION_CONTRADICTION"
    PRICE_HISTORY_DIRECTION_CONTRADICTION = "PRICE_HISTORY_DIRECTION_CONTRADICTION"


_REPAIR_INSTRUCTION_BY_CODE = {
    GroundingViolationCode.UNSUPPORTED_FINANCIAL_NUMBER: (
        "删除所有 Context 未提供的金融数值，不要重新计算、换算或使用近似值。"
    ),
    GroundingViolationCode.BUYING_POWER_CLAIM: (
        "删除整句购买能力推导。不要以肯定、否定或假设方式复述买一股、买不起、"
        "资金足够/不足或覆盖一股；只保留 Cash/Quote Relation 和"
        " executable_purchase_quantity=UNKNOWN。"
    ),
    GroundingViolationCode.CASH_QUOTE_RELATION_CONTRADICTION: (
        "按 Guard 消息给出的代码关系原样修正 Cash/Quote 方向；不解释成购买能力。"
    ),
    GroundingViolationCode.PRICE_COST_RELATION_CONTRADICTION: (
        "按 Guard 消息给出的代码关系原样修正 Quote/Average Cost 方向。"
    ),
    GroundingViolationCode.PRICE_HISTORY_DIRECTION_CONTRADICTION: (
        "按 Guard 消息给出的代码方向原样修正 Price History 首尾收盘价方向。"
    ),
}


@dataclass(frozen=True, slots=True)
class GroundingViolation:
    """供日志、测试和一次 Repair 使用的稳定违规描述。"""

    code: GroundingViolationCode
    message: str

    def as_dict(self) -> dict[str, str]:
        """生成不包含完整用户回答的 Repair Payload。"""

        return {"code": self.code.value, "message": self.message}


def validate_final_response(
    answer: str,
    snapshot: PortfolioSnapshot,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
    historical_results_by_ticker: Mapping[str, MarketDataResult[HistoricalBars]] | None = None,
) -> tuple[GroundingViolation, ...]:
    """验证回答是否越过 M4 已有事实和确定性计算边界。"""

    historical_results = historical_results_by_ticker or {}
    violations: list[GroundingViolation] = []
    violations.extend(
        _unsupported_number_violations(
            answer,
            snapshot,
            market_results_by_ticker,
            historical_results,
        )
    )
    violations.extend(_buying_power_violations(answer))
    violations.extend(_cash_quote_relation_violations(answer, snapshot, market_results_by_ticker))
    violations.extend(_price_cost_relation_violations(answer, snapshot, market_results_by_ticker))
    violations.extend(_price_history_direction_violations(answer, historical_results))
    return _deduplicate_violations(violations)


def build_repair_instruction(
    violations: tuple[GroundingViolation, ...],
) -> dict[str, object]:
    """构造一次性 No-Tool Response Correction 指令。"""

    return {
        "task": "REPAIR_FINAL_RESPONSE",
        "guard_violations": [violation.as_dict() for violation in violations],
        "violation_specific_instructions": [
            _REPAIR_INSTRUCTION_BY_CODE[violation.code] for violation in violations
        ],
        "instructions": [
            "只改写上一条 Final Answer，不重新执行 Agent，也不得请求任何 Tool。",
            "直接删除违规推导，不要在否定句、免责声明或规则解释中复述违规内容。",
            "只使用原始 Context、Tool Results 和已提供的 Derived Facts。",
            "不得生成新的金融数值或购买能力结论。",
            "缺失的确定性事实必须保持 UNKNOWN。",
        ],
        "return_only_repaired_final_answer": True,
    }


def _unsupported_number_violations(
    answer: str,
    snapshot: PortfolioSnapshot,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
    historical_results_by_ticker: Mapping[str, MarketDataResult[HistoricalBars]],
) -> list[GroundingViolation]:
    allowed = _allowed_financial_numbers(
        snapshot,
        market_results_by_ticker,
        historical_results_by_ticker,
    )
    unsupported: set[Decimal] = set()
    for match in _NUMBER_PATTERN.finditer(answer):
        if _is_list_ordinal(answer, match.start(), match.end()):
            continue
        if _is_iso_date_or_time_component(answer, match.start(), match.end()):
            continue
        if not _is_financial_number(answer, match.start(), match.end()):
            continue
        value = _parse_decimal(match.group())
        if value is not None and value not in allowed:
            unsupported.add(value)
    return [
        GroundingViolation(
            GroundingViolationCode.UNSUPPORTED_FINANCIAL_NUMBER,
            f"回答包含 Context 未提供的金融数值：{value}",
        )
        for value in sorted(unsupported)
    ]


def _buying_power_violations(answer: str) -> list[GroundingViolation]:
    if not any(pattern.search(answer) for pattern in _BUYING_POWER_PATTERNS):
        return []
    return [
        GroundingViolation(
            GroundingViolationCode.BUYING_POWER_CLAIM,
            "回答把 Cash/Quote 数值关系解释成了购买能力或整股可执行性",
        )
    ]


def _cash_quote_relation_violations(
    answer: str,
    snapshot: PortfolioSnapshot,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
) -> list[GroundingViolation]:
    successful_quotes = _successful_quotes(market_results_by_ticker)
    violations: list[GroundingViolation] = []
    quoted_tickers = tuple(successful_quotes)
    for ticker, quote in successful_quotes.items():
        derived_facts = QuoteDerivedFacts.from_quote(snapshot, quote)
        expected_relation = derived_facts.cash_vs_one_share_price.value
        relevant_text = _ticker_relevant_text(answer, ticker, quoted_tickers)
        named_relations = _explicit_relation_values(
            relevant_text,
            "cash_vs_one_share_price",
        )
        if any(relation != expected_relation for relation in named_relations):
            violations.append(
                GroundingViolation(
                    GroundingViolationCode.CASH_QUOTE_RELATION_CONTRADICTION,
                    f"回答错误解释了 {ticker} 的 Cash/Quote 关系；代码关系为 {expected_relation}",
                )
            )
    return violations


def _price_cost_relation_violations(
    answer: str,
    snapshot: PortfolioSnapshot,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
) -> list[GroundingViolation]:
    successful_quotes = _successful_quotes(market_results_by_ticker)
    violations: list[GroundingViolation] = []
    for ticker, quote in successful_quotes.items():
        derived_facts = QuoteDerivedFacts.from_quote(snapshot, quote)
        relations = derived_facts.price_vs_average_cost_by_position
        for relation in relations:
            relevant_text = _position_relation_text(
                answer,
                ticker,
                relation.position_type.value,
                len(relations),
            )
            named_relations = _explicit_relation_values(
                relevant_text,
                "price_vs_average_cost",
            )
            expected_relation = relation.price_vs_average_cost.value
            if any(value != expected_relation for value in named_relations):
                violations.append(
                    GroundingViolation(
                        GroundingViolationCode.PRICE_COST_RELATION_CONTRADICTION,
                        (
                            f"回答错误复述了 {ticker} {relation.position_type.value} 的"
                            f"价格/成本关系；代码关系为 {expected_relation}"
                        ),
                    )
                )
    return violations


def _price_history_direction_violations(
    answer: str,
    historical_results_by_ticker: Mapping[str, MarketDataResult[HistoricalBars]],
) -> list[GroundingViolation]:
    """只校验模型显式复述的结构化区间方向。"""

    successful_histories = _successful_histories(historical_results_by_ticker)
    historical_tickers = tuple(successful_histories)
    violations: list[GroundingViolation] = []
    for ticker, history in successful_histories.items():
        expected_direction = RecentPriceHistoryFacts.from_historical_bars(history).close_direction
        relevant_text = _ticker_relevant_text(answer, ticker, historical_tickers)
        named_directions = _explicit_price_directions(relevant_text)
        if any(direction is not expected_direction for direction in named_directions):
            violations.append(
                GroundingViolation(
                    GroundingViolationCode.PRICE_HISTORY_DIRECTION_CONTRADICTION,
                    (
                        f"回答错误复述了 {ticker} 的 Price History 方向；"
                        f"代码方向为 {expected_direction.value}"
                    ),
                )
            )
    return violations


def _explicit_relation_values(answer: str, field_name: str) -> tuple[str, ...]:
    """只读取模型显式复述的结构化关系值。

    Guard 不尝试从“现金略高于价格”等开放文本反推操作数，避免将
    生产阻断器演变为自然语言规则引擎。
    """

    pattern = re.compile(
        rf"\b{re.escape(field_name)}\b"
        rf"(?:\s*\.\s*relation|\s+relation|\s*关系)?"
        rf"\s*(?:显示\s*)?(?:=|:|为|is)\s*[`\"']*\b{_RELATION_VALUES_PATTERN}\b",
        re.IGNORECASE,
    )
    return tuple(match.upper() for match in pattern.findall(answer))


def _explicit_price_directions(answer: str) -> tuple[PriceDirection, ...]:
    pattern = re.compile(
        r"\bclose_direction\b\s*(?:显示\s*)?(?:=|:|为|is)\s*[`\"']*\b"
        rf"{_PRICE_DIRECTION_VALUES_PATTERN}\b",
        re.IGNORECASE,
    )
    return tuple(PriceDirection(match.upper()) for match in pattern.findall(answer))


def _allowed_financial_numbers(
    snapshot: PortfolioSnapshot,
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
    historical_results_by_ticker: Mapping[str, MarketDataResult[HistoricalBars]],
) -> set[Decimal]:
    facts = snapshot.deterministic_derived_facts
    allowed = {
        Decimal("0"),
        snapshot.available_cash,
        Decimal(facts.distinct_ticker_count),
        facts.total_position_cost_basis,
    }
    for position in snapshot.positions:
        allowed.update((position.shares, position.average_cost, position.cost_basis))
    for _, shares in facts.total_shares_by_ticker:
        allowed.add(shares)
    for _, weight in facts.position_cost_basis_weight_by_ticker:
        allowed.add(weight)
    for quote in _successful_quotes(market_results_by_ticker).values():
        allowed.add(quote.last_price)
        if quote.bid_price is not None:
            allowed.add(quote.bid_price)
        if quote.ask_price is not None:
            allowed.add(quote.ask_price)
    for history in _successful_histories(historical_results_by_ticker).values():
        historical_facts = RecentPriceHistoryFacts.from_historical_bars(history)
        allowed.update(
            (
                Decimal(historical_facts.bar_count),
                historical_facts.first_close,
                historical_facts.latest_close,
                historical_facts.period_high,
                historical_facts.period_low,
                historical_facts.close_change,
                historical_facts.absolute_close_change,
                historical_facts.close_change_percent,
                historical_facts.absolute_close_change_percent,
            )
        )
    return allowed


def _successful_quotes(
    market_results_by_ticker: Mapping[str, MarketDataResult[MarketQuote]],
) -> dict[str, MarketQuote]:
    return {
        ticker: result.data
        for ticker, result in market_results_by_ticker.items()
        if result.status is MarketDataStatus.OK and result.data is not None
    }


def _successful_histories(
    historical_results_by_ticker: Mapping[str, MarketDataResult[HistoricalBars]],
) -> dict[str, HistoricalBars]:
    return {
        ticker: result.data
        for ticker, result in historical_results_by_ticker.items()
        if result.status is MarketDataStatus.OK and result.data is not None
    }


def _is_list_ordinal(answer: str, start: int, end: int) -> bool:
    line_start = answer.rfind("\n", 0, start) + 1
    prefix = answer[line_start:start]
    suffix = answer[end : end + 1]
    return bool(re.fullmatch(r"\s*[*#>\-]*\s*", prefix)) and suffix in {".", "、", ")", "）"}


def _is_financial_number(answer: str, start: int, end: int) -> bool:
    before = answer[max(0, start - 24) : start]
    after = answer[end : min(len(answer), end + 16)]
    return (
        answer[start:end].endswith(("%", "％"))
        or before.rstrip().endswith(("$", "¥", "￥"))
        or bool(_FINANCIAL_UNIT_PATTERN.search(after))
        or bool(_FINANCIAL_KEYWORD_PATTERN.search(before))
    )


def _is_iso_date_or_time_component(answer: str, start: int, end: int) -> bool:
    """时间戳是 Tool Source Metadata，不是 LLM 生成的金融计算。"""

    return any(
        date_match.start() <= start and end <= date_match.end()
        for date_match in _ISO_DATE_OR_TIME_PATTERN.finditer(answer)
    )


def _parse_decimal(raw: str) -> Decimal | None:
    normalized = raw.replace(",", "").removesuffix("%").lstrip("+")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _ticker_relevant_text(
    answer: str,
    ticker: str,
    quoted_tickers: tuple[str, ...],
) -> str:
    if len(quoted_tickers) == 1:
        return answer
    return "\n".join(
        sentence
        for sentence in _sentences(answer)
        if ticker.lower() in sentence.lower()
        and not any(
            other.lower() in sentence.lower() for other in quoted_tickers if other != ticker
        )
    )


def _position_relation_text(
    answer: str,
    ticker: str,
    position_type: str,
    relation_count: int,
) -> str:
    """当同一 Ticker 有多类 Position 时，只检查能明确归属的关系值。"""

    if relation_count == 1:
        return answer
    position_alias = "长期" if position_type == "LONG_TERM" else "波段"
    other_position_type = "SWING" if position_type == "LONG_TERM" else "LONG_TERM"
    other_position_alias = "波段" if position_type == "LONG_TERM" else "长期"
    return "\n".join(
        sentence
        for sentence in _sentences(answer)
        if ticker.lower() in sentence.lower()
        and (position_type.lower() in sentence.lower() or position_alias in sentence)
        and other_position_type.lower() not in sentence.lower()
        and other_position_alias not in sentence
    )


def _sentences(answer: str) -> tuple[str, ...]:
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?；;])|\n+", answer)
        if sentence.strip()
    )


def _deduplicate_violations(
    violations: list[GroundingViolation],
) -> tuple[GroundingViolation, ...]:
    unique: dict[tuple[GroundingViolationCode, str], GroundingViolation] = {}
    for violation in violations:
        unique[(violation.code, violation.message)] = violation
    return tuple(unique.values())

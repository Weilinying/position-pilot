"""Alpaca Market Data Adapter 测试。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from position_pilot.application.market_data_service import HistoricalBarsQuery
from position_pilot.domain.market_data import MarketDataCoverage, MarketDataStatus
from position_pilot.integrations.alpaca_market_data import (
    AlpacaMarketDataProvider,
    HttpTransportUnavailable,
    JsonHttpResponse,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 20, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    url: str
    headers: dict[str, str]
    timeout_seconds: float


@dataclass(slots=True)
class FakeJsonTransport:
    """按顺序返回固定 Alpaca JSON，并记录不透明 HTTP 请求。"""

    responses: list[JsonHttpResponse]
    requests: list[RecordedRequest] = field(default_factory=list)

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        self.requests.append(RecordedRequest(url, dict(headers), timeout_seconds))
        return self.responses.pop(0)


class UnavailableTransport:
    """模拟 DNS、连接或读取失败。"""

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        raise HttpTransportUnavailable("offline")


def make_provider(
    transport: FakeJsonTransport | UnavailableTransport,
    *,
    api_key_id: str | None = "test-key",
    api_secret_key: str | None = "test-secret",
) -> AlpacaMarketDataProvider:
    """创建固定时间与 Fake Transport 的 Adapter。"""

    return AlpacaMarketDataProvider(
        api_key_id=api_key_id,
        api_secret_key=api_secret_key,
        base_url="https://data.example.test",
        timeout_seconds=3,
        transport=transport,
        clock=lambda: NOW,
    )


def test_parses_current_iex_snapshot_with_explicit_coverage() -> None:
    """Snapshot 应映射 last trade、bid/ask、来源与市场时间。"""

    transport = FakeJsonTransport(
        responses=[
            JsonHttpResponse(
                200,
                {
                    "latestTrade": {"p": 220.125, "t": "2026-08-21T11:59:59.123456789Z"},
                    "latestQuote": {
                        "bp": 220.1,
                        "ap": 220.2,
                        "t": "2026-08-21T11:59:59.900000000Z",
                    },
                },
            )
        ]
    )

    result = make_provider(transport).get_current_quote("GOOG")

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert str(result.data.last_price) == "220.125"
    assert str(result.data.bid_price) == "220.1"
    assert result.data.feed == "IEX"
    assert result.data.coverage is MarketDataCoverage.SINGLE_EXCHANGE
    assert result.data.last_trade_at.tzinfo is UTC
    assert "feed=iex" in transport.requests[0].url
    assert transport.requests[0].headers["APCA-API-KEY-ID"] == "test-key"


def test_missing_latest_trade_is_no_data_not_provider_failure() -> None:
    """正常空 Snapshot 必须与 Provider Failure 区分。"""

    transport = FakeJsonTransport([JsonHttpResponse(200, {"latestTrade": None})])

    result = make_provider(transport).get_current_quote("GOOG")

    assert result.status is MarketDataStatus.NO_DATA
    assert result.data is None


def test_zero_quote_prices_are_treated_as_unavailable() -> None:
    """Alpaca 的浮点零值 Quote 应映射为可选空值而非非法响应。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "latestTrade": {"p": 220.125, "t": "2026-08-21T11:59:59Z"},
                    "latestQuote": {
                        "bp": 0.0,
                        "ap": "0.00",
                        "t": "2026-08-21T11:59:59Z",
                    },
                },
            )
        ]
    )

    result = make_provider(transport).get_current_quote("GOOG")

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert result.data.bid_price is None
    assert result.data.ask_price is None


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, MarketDataStatus.INVALID_REQUEST),
        (401, MarketDataStatus.AUTHENTICATION_FAILED),
        (403, MarketDataStatus.AUTHENTICATION_FAILED),
        (404, MarketDataStatus.NO_DATA),
        (422, MarketDataStatus.INVALID_REQUEST),
        (429, MarketDataStatus.RATE_LIMITED),
        (500, MarketDataStatus.PROVIDER_UNAVAILABLE),
        (418, MarketDataStatus.INVALID_PROVIDER_RESPONSE),
    ],
)
def test_maps_http_status_without_exposing_provider_payload(
    status_code: int,
    expected: MarketDataStatus,
) -> None:
    """HTTP Failure 必须映射为稳定状态且不转发不可信 Payload。"""

    transport = FakeJsonTransport(
        [JsonHttpResponse(status_code, {"message": "test-secret must not leak"})]
    )

    result = make_provider(transport).get_current_quote("GOOG")

    assert result.status is expected
    assert result.message is not None
    assert "test-secret" not in result.message


def test_network_failure_is_provider_unavailable() -> None:
    """网络失败不得伪装成无行情。"""

    result = make_provider(UnavailableTransport()).get_current_quote("GOOG")

    assert result.status is MarketDataStatus.PROVIDER_UNAVAILABLE


def test_missing_credentials_fail_before_network_call() -> None:
    """缺少 Credential 应明确失败且不发出匿名请求。"""

    transport = FakeJsonTransport([])

    result = make_provider(transport, api_key_id=None).get_current_quote("GOOG")

    assert result.status is MarketDataStatus.AUTHENTICATION_FAILED
    assert transport.requests == []


def test_parses_paginated_adjusted_sip_daily_bars() -> None:
    """Historical Adapter 应跟随分页并保留 SIP 与 adjustment 元数据。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "bars": [
                        {
                            "t": "2026-08-18T04:00:00Z",
                            "o": 200,
                            "h": 205,
                            "l": 199,
                            "c": 204,
                            "v": 1000,
                        }
                    ],
                    "next_page_token": "next-token",
                },
            ),
            JsonHttpResponse(
                200,
                {
                    "bars": [
                        {
                            "t": "2026-08-19T04:00:00Z",
                            "o": 204,
                            "h": 206,
                            "l": 201,
                            "c": 202,
                            "v": 1200,
                        }
                    ],
                    "next_page_token": None,
                },
            ),
        ]
    )
    query = HistoricalBarsQuery(ticker="GOOG", start=START, end=END, limit=10)

    result = make_provider(transport).get_historical_bars(query)

    assert result.status is MarketDataStatus.OK
    assert result.data is not None
    assert len(result.data.bars) == 2
    assert result.data.feed == "SIP"
    assert result.data.coverage is MarketDataCoverage.CONSOLIDATED
    assert result.data.adjustment == "ALL"
    assert result.data.timeframe == "1Day"
    assert "adjustment=all" in transport.requests[0].url
    assert "page_token=next-token" in transport.requests[1].url


def test_rejects_recent_sip_query_before_network_call() -> None:
    """Basic Plan 不得请求无权限的最近 15 分钟 SIP 数据。"""

    transport = FakeJsonTransport([])
    query = HistoricalBarsQuery(
        ticker="GOOG",
        start=START,
        end=datetime(2026, 8, 21, 11, 50, tzinfo=UTC),
    )

    result = make_provider(transport).get_historical_bars(query)

    assert result.status is MarketDataStatus.INVALID_REQUEST
    assert transport.requests == []


def test_invalid_bar_payload_has_explicit_failure() -> None:
    """非法 OHLCV 不得被静默丢弃或返回部分成功。"""

    transport = FakeJsonTransport(
        [
            JsonHttpResponse(
                200,
                {
                    "bars": [
                        {
                            "t": "2026-08-18T04:00:00Z",
                            "o": 200,
                            "h": 190,
                            "l": 199,
                            "c": 204,
                            "v": 1000,
                        }
                    ],
                    "next_page_token": None,
                },
            )
        ]
    )

    result = make_provider(transport).get_historical_bars(
        HistoricalBarsQuery(ticker="GOOG", start=START, end=END)
    )

    assert result.status is MarketDataStatus.INVALID_PROVIDER_RESPONSE

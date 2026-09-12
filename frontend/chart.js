const RANGE_VALUES = new Set(["1M", "3M", "6M", "1Y"]);

export const CHART_RANGES = Object.freeze(["1M", "3M", "6M", "1Y"]);

function numeric(value) {
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

function chartDate(value) {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  if (value && typeof value === "object" && Number.isInteger(value.year) && Number.isInteger(value.month) && Number.isInteger(value.day)) {
    const month = String(value.month).padStart(2, "0");
    const day = String(value.day).padStart(2, "0");
    return `${value.year}-${month}-${day}`;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Date(value > 10_000_000_000 ? value : value * 1000).toISOString().slice(0, 10);
  }
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10);
}

function normalizeBar(bar) {
  const time = chartDate(bar?.market_date ?? bar?.date ?? bar?.time ?? bar?.timestamp);
  const open = numeric(bar?.open);
  const high = numeric(bar?.high);
  const low = numeric(bar?.low);
  const close = numeric(bar?.close);
  const volume = numeric(bar?.volume);
  if (!time || [open, high, low, close, volume].some((value) => value === null)) return null;
  return { time, open, high, low, close, volume };
}

function normalizeTransaction(transaction) {
  if (!transaction || typeof transaction !== "object") return null;
  const action = String(transaction.action ?? transaction.side ?? "").toUpperCase();
  const occurredAt = transaction.occurred_at ?? transaction.executed_at ?? transaction.time ?? null;
  return {
    ...transaction,
    action,
    market_date: transaction.market_date ?? chartDate(occurredAt),
    occurred_at: occurredAt,
  };
}

function normalizeMarker(marker) {
  if (!marker || typeof marker !== "object") return null;
  const marketDate = chartDate(marker.market_date ?? marker.date ?? marker.time);
  if (!marketDate) return null;
  const transactions = Array.isArray(marker.transactions)
    ? marker.transactions.map(normalizeTransaction).filter(Boolean)
    : [];
  return { ...marker, market_date: marketDate, has_bar: Boolean(marker.has_bar), transactions };
}

export function normalizeChartPayload(payload = {}) {
  const bars = Array.isArray(payload.bars) ? payload.bars.map(normalizeBar).filter(Boolean) : [];
  const markers = Array.isArray(payload.markers) ? payload.markers.map(normalizeMarker).filter(Boolean) : [];
  const range = RANGE_VALUES.has(payload.range) ? payload.range : "3M";
  return { ...payload, range, bars, markers };
}

function actionLabel(transaction) {
  const action = String(transaction?.action ?? transaction?.side ?? "").toUpperCase();
  return action === "SELL" ? "SELL" : action === "BUY" ? "BUY" : "";
}

export function buildChartMarkers(payload) {
  const normalized = normalizeChartPayload(payload);
  const markers = [];
  for (const marker of normalized.markers) {
    // 没有对应日 K 的交易只保留在详情中，不能移动或强画到相邻 Bar。
    if (!marker.has_bar) continue;
    const transactionsByAction = new Map();
    for (const transaction of marker.transactions) {
      const action = actionLabel(transaction);
      if (!action) continue;
      const records = transactionsByAction.get(action) ?? [];
      records.push(transaction);
      transactionsByAction.set(action, records);
    }
    for (const [action, records] of transactionsByAction) {
      markers.push({
        id: `${marker.market_date}-${action}`,
        time: marker.market_date,
        position: action === "BUY" ? "belowBar" : "aboveBar",
        shape: action === "BUY" ? "arrowUp" : "arrowDown",
        color: action === "BUY" ? "#1b6b54" : "#a33b34",
        text: records.length > 1 ? `${action} · ${records.length}` : action,
      });
    }
  }
  return markers.sort((left, right) => String(left.time).localeCompare(String(right.time)));
}

function volumeData(bars) {
  return bars.map((bar) => ({
    time: bar.time,
    value: bar.volume,
    color: bar.close >= bar.open ? "rgba(27, 107, 84, 0.42)" : "rgba(163, 59, 52, 0.42)",
  }));
}

function configureChart(chart, container) {
  chart.applyOptions({
    width: container.clientWidth,
    height: Math.max(360, Math.min(560, container.clientHeight || 460)),
    layout: {
      background: { color: "transparent" },
      textColor: "#40524b",
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: "rgba(20, 37, 31, 0.06)" },
      horzLines: { color: "rgba(20, 37, 31, 0.06)" },
    },
    rightPriceScale: { borderColor: "rgba(20, 37, 31, 0.12)" },
    timeScale: { borderColor: "rgba(20, 37, 31, 0.12)", timeVisible: false, rightOffset: 3 },
    crosshair: { mode: 1 },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  });
}

export function createPositionChart({ container, payload, onDateSelect }) {
  const library = globalThis.LightweightCharts;
  if (!library?.createChart || !library.CandlestickSeries || !library.HistogramSeries) {
    throw new Error("Lightweight Charts is unavailable");
  }
  const normalized = normalizeChartPayload(payload);
  const chart = library.createChart(container, {});
  configureChart(chart, container);
  const candles = chart.addSeries(library.CandlestickSeries, {
    upColor: "#1b6b54",
    downColor: "#a33b34",
    borderVisible: false,
    wickUpColor: "#1b6b54",
    wickDownColor: "#a33b34",
  });
  candles.setData(normalized.bars);
  const volume = chart.addSeries(library.HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
    color: "rgba(27, 107, 84, 0.34)",
  });
  volume.setData(volumeData(normalized.bars));
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });

  const chartMarkers = buildChartMarkers(normalized);
  const markerPrimitive = typeof library.createSeriesMarkers === "function"
    ? library.createSeriesMarkers(candles, chartMarkers)
    : null;
  const markersByDate = new Map(normalized.markers.map((marker) => [marker.market_date, marker]));
  const clickHandler = (param) => {
    const date = chartDate(param?.time);
    if (date && markersByDate.has(date)) onDateSelect?.(date, markersByDate.get(date));
  };
  chart.subscribeClick(clickHandler);
  const resizeObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(() => configureChart(chart, container))
    : null;
  resizeObserver?.observe(container);
  chart.timeScale().fitContent();
  return {
    chart,
    candles,
    volume,
    markerPrimitive,
    destroy() {
      resizeObserver?.disconnect();
      chart.unsubscribeClick(clickHandler);
      chart.remove();
    },
  };
}

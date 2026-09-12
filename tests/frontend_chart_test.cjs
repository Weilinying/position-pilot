const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

async function loadChartModule() {
  const file = path.join(__dirname, "..", "frontend", "chart.js");
  const source = fs.readFileSync(file, "utf8");
  return import(`data:text/javascript,${encodeURIComponent(source)}`);
}

async function main() {
  const { normalizeChartPayload, buildChartMarkers, createPositionChart } = await loadChartModule();
  const payload = normalizeChartPayload({
    range: "3M",
    bars: [{ market_date: "2026-08-20", open: "100.00", high: "110", low: "95", close: "105", volume: "1200" }],
    markers: [{
      market_date: "2026-08-20",
      has_bar: true,
      transactions: [
        { action: "BUY", shares: "2", price: "99", occurred_at: "2026-08-20T14:00:00Z" },
        { action: "BUY", shares: "1", price: "101", occurred_at: "2026-08-20T15:00:00Z" },
        { action: "SELL", shares: "1", price: "108", occurred_at: "2026-08-20T16:00:00Z" },
      ],
    }, {
      market_date: "2026-08-21",
      has_bar: false,
      transactions: [
        { action: "BUY", shares: "1", price: "102", occurred_at: "2026-08-21T14:00:00Z" },
      ],
    }],
  });
  assert.equal(payload.bars[0].open, 100);
  assert.equal(payload.bars[0].volume, 1200);
  assert.deepEqual(buildChartMarkers(payload).map((marker) => [marker.time, marker.position, marker.text]), [
    ["2026-08-20", "belowBar", "BUY · 2"],
    ["2026-08-20", "aboveBar", "SELL"],
  ]);

  let click;
  let removed = false;
  const series = {
    setData: () => {},
    priceScale: () => ({ applyOptions: () => {} }),
  };
  const chart = {
    applyOptions: () => {},
    addSeries: () => series,
    subscribeClick: (handler) => { click = handler; },
    unsubscribeClick: () => {},
    timeScale: () => ({ fitContent: () => {} }),
    remove: () => { removed = true; },
  };
  globalThis.LightweightCharts = {
    CandlestickSeries: {},
    HistogramSeries: {},
    createChart: () => chart,
    createSeriesMarkers: () => ({}),
  };
  const selected = [];
  const instance = createPositionChart({ container: { clientWidth: 900, clientHeight: 460 }, payload, onDateSelect: (date) => selected.push(date) });
  click({ time: { year: 2026, month: 8, day: 20 } });
  assert.deepEqual(selected, ["2026-08-20"]);
  instance.destroy();
  assert.equal(removed, true);
  console.log("Chart payload normalization, grouped markers, click selection, and cleanup passed.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

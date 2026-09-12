const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/app.js', 'utf8');
const refresh = source.slice(source.indexOf('async function refreshValuation()'), source.indexOf('async function refreshPortfolio('));

async function main() {
  const formatting = vm.createContext({});
  vm.runInContext(source.slice(source.indexOf('function formatDecimal('), source.indexOf('function formatTimestamp(')) + source.slice(source.indexOf('function formatPnl('), source.indexOf('function pnlTone(')), formatting);
  assert.equal(formatting.formatPnl('0E-8'), '$0');
  assert.equal(formatting.formatPnl('-0E-8'), '$0');
  assert.equal(formatting.formatPnl('1E-8'), '+$0.00000001');
  assert.equal(formatting.formatPnl('-1E-8'), '-$0.00000001');
  assert.equal(formatting.formatMoney('1.234E+5'), '$123,400');
  let resolve;
  const requests = [];
  const cell = {textContent: 'old', dataset: {tone: 'positive'}};
  const group = {dataset: {ticker: 'TSLA'}, querySelectorAll: () => [cell], querySelector: () => null};
  const historyPnl = {textContent: 'old', dataset: {}};
  const historyRow = {dataset: {recordKind: 'trade', recordId: 'sell-1'}, querySelector: () => historyPnl};
  const state = {snapshot: {}, valuation: null, accounting: null, summary: null, valuationController: null, portfolioReadState: 'idle', writeState: 'idle', authTransition: 'idle', portfolioGeneration: 1};
  let summaryRenderCount = 0;
  const context = vm.createContext({state, AbortController, ApiError: class extends Error {}, requestJson: (url) => { requests.push(url); return new Promise(r => {resolve = r;}); }, elements: {positionList: {querySelectorAll: () => [group]}, transactionList: {querySelectorAll: () => [historyRow]}, summaryRealizedPnl: {textContent: '', dataset: {}}, summaryUnrealizedPnl: {textContent: '', dataset: {}}, summaryTotalPnl: {textContent: '', dataset: {}}, summaryPnlStatus: {textContent: '', dataset: {}}}, createHoldingTree: () => ({querySelectorAll: () => [{textContent: 'new', dataset: {}}], querySelector: () => null}), renderPortfolioSummary: () => {summaryRenderCount += 1;}, accountingTransaction: () => ({metrics: {realized_pnl: '79'}}), formatPnl: value => value === '79' ? '+$79' : '—', pnlTone: () => 'positive'});
  vm.runInContext(refresh, context);
  const pending = context.refreshValuation();
  assert.equal(state.portfolioReadState, 'idle');
  assert.equal(state.writeState, 'idle');
  await context.refreshValuation();
  assert.deepEqual(requests, ['/v1/portfolio/summary']);
  resolve({valuation: {tickers: []}, accounting: {transactions: [{transaction_id: 'sell-1', metrics: {realized_pnl: '79'}}]}, totals: {realized_pnl: '79', unrealized_pnl: '60', total_pnl: '139', valuation_complete: true}});
  await pending;
  assert.equal(cell.textContent, 'new');
  assert.equal(cell.dataset.tone, undefined);
  assert.equal(state.summary.totals.total_pnl, '139');
  assert.equal(summaryRenderCount, 1);
  assert.equal(historyPnl.textContent, '+$79');
  assert.equal(state.valuationController, null);
  const stale = context.refreshValuation();
  state.portfolioGeneration++;
  cell.textContent = 'edited';
  resolve({valuation: {tickers: []}, accounting: {transactions: []}, totals: {}});
  await stale;
  assert.equal(cell.textContent, 'edited');
  const controls = source.slice(source.indexOf('function updateControls()'), source.indexOf('function enterHome('));
  const control = () => ({disabled: false, dataset: {}});
  const controlElements = {
    logout: control(), headerLogout: control(), setupLogout: control(), setupFields: control(),
    reloadPortfolio: control(), tradeFields: control(), cashFields: control(), openingFields: control(),
    reconciliationFields: control(), reconciliationAddRow: control(), reconciliationLoadCurrent: control(), reconciliationRevalidate: control(),
    reconciliationSubmit: control(), question: control(), ask: control(), navChat: control(),
    navPortfolio: control(), newQuestion: control(), writeState: control(),
  };
  const importSubmit = control();
  const controlsState = {snapshot: {}, writeState: 'idle', portfolioReadState: 'idle', authTransition: 'idle', questionPending: true, importPending: false};
  const controlsContext = vm.createContext({state: controlsState, elements: controlElements, importConfigs: [{controls: {textSubmit: importSubmit, screenshotSubmit: null}}], renderPortfolioState: () => {}, renderWriteState: () => {}, setLocalizedText: () => {}});
  vm.runInContext(controls, controlsContext);
  controlsContext.updateControls();
  assert.equal(controlElements.reconciliationFields.disabled, false);
  assert.equal(controlElements.reconciliationLoadCurrent.disabled, false);
  assert.equal(controlElements.reconciliationSubmit.disabled, true);
  assert.equal(importSubmit.disabled, true);
  const manual = source.slice(source.indexOf('function loadCurrentReconciliationDraft('), source.indexOf('async function handleReconciliation('));
  function element() {return {children: [], dataset: {}, append(...children) {this.children.push(...children);}, addEventListener(name, callback) {this[name] = callback;}, querySelector() {return null;}, get childElementCount() {return this.children.length;}};}
  const rows = element();
  let selected;
  const goog = {ticker: 'GOOG', position_type: 'UNSPECIFIED', shares: '1', average_cost: '100'};
  const tsla = {ticker: 'TSLA', position_type: 'SWING'};
  const purchase = {id: 'buy-tsla', ...tsla, source: 'BUY', purchased_at: '2026-09-01'};
  let aborted = false;
  const manualContext = vm.createContext({state: {snapshot: {positions: [goog, tsla], lots: [{...goog, source: 'OPENING'}, purchase]}, importGeneration: 1, importPending: true, importController: {abort: () => {aborted = true;}}}, elements: {reconciliationRows: rows}, updateControls: () => {}, clearElement: node => {node.children = [];}, createOpeningRow: parent => {const row = element(); const fields = new Map(); row.querySelector = key => {if (!fields.has(key)) fields.set(key, {dataset: {}}); return fields.get(key);}; parent.append(row); return row;}, makeElement: (_tag, _className, text) => Object.assign(element(), {textContent: text}), translate: value => value, formatTimestamp: value => value, openBuyCorrection: lot => {selected = lot;}, clearMessage: () => {}, setMessage: () => {throw new Error('Unexpected empty holdings');}});
  vm.runInContext(manual, manualContext);
  manualContext.loadCurrentReconciliationDraft();
  assert.equal(aborted, true);
  assert.equal(manualContext.state.importPending, false);
  assert.equal(rows.children.length, 2);
  assert.equal(rows.children[1].children[0].textContent, 'TSLA · SWING');
  rows.children[1].children[1].click();
  assert.equal(selected, purchase);
  console.log('Background valuation: nonblocking, deduplicated, stale response ignored.');
}
main().catch(error => {console.error(error); process.exitCode = 1;});

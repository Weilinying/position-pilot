const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/app.js', 'utf8');
const refresh = source.slice(source.indexOf('async function refreshValuation()'), source.indexOf('async function refreshPortfolio('));

async function main() {
  let resolve;
  const requests = [];
  const cell = {textContent: 'old', dataset: {tone: 'positive'}};
  const group = {dataset: {ticker: 'TSLA'}, querySelectorAll: () => [cell]};
  const state = {snapshot: {}, valuationPending: false, portfolioReadState: 'idle', writeState: 'idle', authTransition: 'idle', portfolioGeneration: 1};
  const context = vm.createContext({state, ApiError: class extends Error {}, requestJson: (url) => { requests.push(url); return new Promise(r => {resolve = r;}); }, elements: {positionList: {querySelectorAll: () => [group]}}, createHoldingTree: () => ({querySelectorAll: () => [{textContent: 'new', dataset: {}}]})});
  vm.runInContext(refresh, context);
  const pending = context.refreshValuation();
  assert.equal(state.portfolioReadState, 'idle');
  assert.equal(state.writeState, 'idle');
  await context.refreshValuation();
  assert.deepEqual(requests, ['/v1/portfolio/valuation']);
  resolve({tickers: []});
  await pending;
  assert.equal(cell.textContent, 'new');
  assert.equal(cell.dataset.tone, undefined);
  assert.equal(state.valuationPending, false);
  const stale = context.refreshValuation();
  state.portfolioGeneration++;
  cell.textContent = 'edited';
  resolve({tickers: []});
  await stale;
  assert.equal(cell.textContent, 'edited');
  const manual = source.slice(source.indexOf('function loadCurrentReconciliationDraft('), source.indexOf('async function handleReconciliation('));
  function element() {return {children: [], dataset: {}, append(...children) {this.children.push(...children);}, addEventListener(name, callback) {this[name] = callback;}, querySelector() {return null;}, get childElementCount() {return this.children.length;}};}
  const rows = element();
  let selected;
  const goog = {ticker: 'GOOG', position_type: 'UNSPECIFIED', shares: '1', average_cost: '100'};
  const tsla = {ticker: 'TSLA', position_type: 'SWING'};
  const purchase = {id: 'buy-tsla', ...tsla, source: 'BUY', purchased_at: '2026-09-01'};
  const manualContext = vm.createContext({state: {snapshot: {positions: [goog, tsla], lots: [{...goog, source: 'OPENING'}, purchase]}}, elements: {reconciliationRows: rows}, clearElement: node => {node.children = [];}, createOpeningRow: parent => {const row = element(); const fields = new Map(); row.querySelector = key => {if (!fields.has(key)) fields.set(key, {dataset: {}}); return fields.get(key);}; parent.append(row); return row;}, makeElement: (_tag, _className, text) => Object.assign(element(), {textContent: text}), translate: value => value, formatTimestamp: value => value, openBuyCorrection: lot => {selected = lot;}, clearMessage: () => {}, setMessage: () => {throw new Error('Unexpected empty holdings');}});
  vm.runInContext(manual, manualContext);
  manualContext.loadCurrentReconciliationDraft();
  assert.equal(rows.children.length, 2);
  assert.equal(rows.children[1].children[0].textContent, 'TSLA · SWING');
  rows.children[1].children[1].click();
  assert.equal(selected, purchase);
  console.log('Background valuation: nonblocking, deduplicated, stale response ignored.');
}
main().catch(error => {console.error(error); process.exitCode = 1;});

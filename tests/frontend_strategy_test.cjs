const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/app.js', 'utf8');

class Element {
  constructor(tag, className, text) { this.tag = tag; this.className = className; this.textContent = text; this.children = []; this.disabled = false; }
  append(...items) { this.children.push(...items); }
  addEventListener(name, callback) { this[name] = callback; }
}

async function main() {
  let candidate = {id: 'draft-1', status: 'PENDING', scope: {ticker: 'GOOG', position_type: 'LONG_TERM'}, kind: 'POSITION_PLAN_V1', operation: 'UPSERT', payload: {target_budget: '300', currency: 'USD'}, evidence_quote: '<img src=x onerror=alert(1)>', candidate_revision: 1, base_version: 0};
  const requests = [];
  let failure = null;
  const state = {account: {email: 'a@example.test'}, authGeneration: 1, activeThreadId: 'thread-1'};
  const context = vm.createContext({
    translate: key => key,
    state, currentAccountKey: () => state.account.email,
    makeElement: (...args) => new Element(...args), clearElement: node => {node.children = [];},
    setLocalizedText: (node, key) => {node.textContent = key;}, makeClientRequestId: () => 'stable-request-id',
    requestJson: async (url, options = {}) => {
      requests.push({url, ...options});
      if (options.method) {
        if (failure) throw failure;
        candidate = {...candidate, status: url.endsWith('/confirm') ? 'CONFIRMED' : 'CANCELLED', candidate_revision: 2};
        return {};
      }
      return candidate;
    },
  });
  vm.runInContext(source.slice(source.indexOf('function renderIntentCandidate('), source.indexOf('function renderQuestionResult(')), context);
  const view = {candidate: new Element('section')};
  context.renderIntentCandidate(view, candidate);
  assert.equal(requests.length, 0);
  assert.equal(view.candidate.children.find(node => node.tag === 'blockquote').textContent, candidate.evidence_quote);
  let actions = view.candidate.children.at(-1);
  await actions.children[0].click();
  assert.equal(requests.length, 2);
  assert.deepEqual(JSON.parse(requests[0].body), {candidate_revision: 1, base_version: 0, client_request_id: 'stable-request-id'});
  assert.equal(view.candidate.children.some(node => node.className === 'intent-actions'), false);
  context.renderIntentCandidate(view, candidate);
  assert.equal(view.candidate.children.some(node => node.className === 'intent-actions'), false);

  candidate = {...candidate, status: 'PENDING', candidate_revision: 1};
  context.renderIntentCandidate(view, candidate);
  actions = view.candidate.children.at(-1);
  failure = {status: 409};
  candidate = {...candidate, status: 'EXPIRED'};
  await actions.children[0].click();
  assert.equal(view.candidate.children.at(-1).textContent, 'intent_conflict');
  assert.equal(view.candidate.children.some(node => node.className === 'intent-actions'), false);

  failure = null; candidate = {...candidate, status: 'PENDING'};
  context.renderIntentCandidate(view, candidate);
  actions = view.candidate.children.at(-1);
  const before = requests.length;
  state.authGeneration += 1; state.account.email = 'b@example.test';
  await actions.children[0].click();
  assert.equal(requests.length, before);
  console.log('Strategy card: explicit confirmation, state recovery, conflict refresh, text safety and stale-account isolation passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });

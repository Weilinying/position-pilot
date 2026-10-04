const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('frontend/app.js', 'utf8');

function extract(startMarker, endMarker) {
  return source.slice(source.indexOf(startMarker), source.indexOf(endMarker));
}

const context = vm.createContext({
  URL,
  Uint8Array,
  globalThis: {},
  document: {createTextNode: (text) => ({text})},
  clearElement: (element) => { element.children = []; },
  makeElement: (tag, className, text) => ({
    tag, className, text, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
  }),
  translate: (key) => key,
});
vm.runInContext(
  extract('function makeClientRequestId()', 'function formatTimestamp(')
    + extract('function isSafeHttpUrl(', 'function createSourceCard(')
    + extract('function normalizeConversationAnswer(', 'function createQuestionExchange(')
    + extract('function conversationMessagesUrl(', 'async function loadConversationThread(')
    + extract('function renderAnswerWithCitations(', 'function renderQuestionResult('),
  context,
);

assert.match(context.makeClientRequestId(), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
assert.equal(context.isSafeHttpUrl('https://example.com/article'), true);
assert.equal(context.isSafeHttpUrl('http://example.com/article'), true);
assert.equal(context.isSafeHttpUrl('javascript:alert(1)'), false);
assert.equal(context.isSafeHttpUrl('data:text/html,<p>unsafe</p>'), false);
assert.equal(context.isSafeHttpUrl('/relative/article'), false);
assert.equal(context.isSafeHttpUrl('https://user:password@example.com/article'), false);
assert.equal(context.conversationMessagesUrl('thread-1'), '/v1/threads/thread-1/messages?limit=100');
assert.equal(context.conversationMessagesUrl('thread-1', '101'), '/v1/threads/thread-1/messages?limit=100&before=101');
assert.equal(context.conversationMessagesUrl('thread-1', 'cursor with spaces'), '/v1/threads/thread-1/messages?limit=100&before=cursor%20with%20spaces');

const normalized = context.normalizeConversationAnswer({
  answer: {
    text: 'Use the latest evidence [source:known]. Ignore [source:missing].',
    warnings: ['USAGE_UNKNOWN'],
    sources: [{source_id: 'known', url: 'https://example.com/article'}],
    citations: [{source_id: 'known', locator: 'paragraph 2'}, {source_id: 'missing'}],
  },
});
assert.equal(normalized.text.includes('[source:missing]'), true);
assert.deepEqual(normalized.warnings, ['USAGE_UNKNOWN']);
assert.deepEqual(normalized.citations.map((item) => item.source_id), ['known', 'missing']);

const answerElement = {children: [], append(...items) { this.children.push(...items); }};
context.renderAnswerWithCitations(
  answerElement,
  normalized.text,
  normalized.citations,
  normalized.sources,
);
assert.equal(answerElement.children.find((item) => item.tag === 'a').href, 'https://example.com/article');
assert.equal(answerElement.children.find((item) => item.tag === 'a').rel, 'noopener noreferrer');
assert.equal(answerElement.children.some((item) => item.text?.includes('[source:missing]')), true);

const sourceText = source;
assert.match(sourceText, /\/v1\/threads\?limit=100/);
assert.match(sourceText, /next_cursor/);
assert.match(sourceText, /messagePages\.unshift/);
assert.match(sourceText, /seenCursors/);
assert.match(sourceText, /expected_thread_revision/);
assert.match(sourceText, /client_request_id/);
assert.match(sourceText, /authGeneration !== state\.authGeneration/);
assert.match(sourceText, /currentAccountKey\(\) !== accountKey/);
assert.doesNotMatch(sourceText, /requestJson\("\/v1\/investment\/questions"/);

console.log('Conversation frontend contract: safe source links, citation filtering inputs, and Thread API request fields verified.');

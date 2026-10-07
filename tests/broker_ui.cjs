// Runs the broker page's inline submit script (read from stdin) against a mocked DOM.
// Usage: node tests/broker_ui.cjs < script.js  (invoked by tests/test_ui.py)
'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const SCRIPT = fs.readFileSync(0, 'utf8');
const FAKE = 'demo-value';
const flush = () => new Promise(resolve => setImmediate(resolve));

function setup() {
  const page = {fetches: [], timers: new Map(), nextTimer: 1, listener: null, active: null};
  const focusable = el => Object.assign(el, {focus() { page.active = el; }});
  const button = {disabled: false, textContent: 'Send once'};
  const input = focusable({value: '', disabled: false});
  const classes = new Set();
  const message = focusable({textContent: '', classList: {
    toggle(name, on) { on ? classes.add(name) : classes.delete(name); },
    contains: name => classes.has(name),
  }});
  const form = {
    removed: false,
    addEventListener(type, fn) { assert.strictEqual(type, 'submit'); page.listener = fn; },
    querySelector(selector) { assert.strictEqual(selector, 'button'); return button; },
    remove() { this.removed = true; },
  };
  const h1 = {textContent: 'Ready for a secret'};
  const intro = {textContent: 'Review the command before supplying the secret. The request expires after five minutes.'};
  const elements = {form, secret: input, message, intro};
  const document = {
    title: 'Ready for a secret · Keyrelay',
    getElementById: id => elements[id] || null,
    querySelector(selector) { assert.strictEqual(selector, 'h1'); return h1; },
  };
  const fetch = (url, options) => new Promise((resolve, reject) => {
    const call = {url, options, resolve, reject};
    if (options.signal) options.signal.addEventListener('abort', () => {
      const error = new Error('The operation was aborted');
      error.name = 'AbortError';
      reject(error);
    });
    page.fetches.push(call);
  });
  const context = vm.createContext({
    document, fetch, AbortController,
    location: {pathname: '/r/fake-request'},
    setTimeout(fn, ms) { const id = page.nextTimer++; page.timers.set(id, {fn, ms}); return id; },
    clearTimeout(id) { page.timers.delete(id); },
  });
  vm.runInContext(SCRIPT, context);
  assert.ok(page.listener, 'submit listener registered');
  const submit = () => page.listener({preventDefault() {}});
  return {page, button, input, message, form, h1, intro, document, submit};
}

function response(status) {
  return {ok: status >= 200 && status < 300, status};
}

function assertSending(ui) {
  assert.strictEqual(ui.input.value, '');
  assert.strictEqual(ui.input.disabled, true);
  assert.strictEqual(ui.button.disabled, true);
  assert.strictEqual(ui.button.textContent, 'Sending…');
  assert.strictEqual(ui.message.textContent, 'Sending…');
}

function assertSucceeded(ui) {
  assert.strictEqual(ui.form.removed, true);
  assert.strictEqual(ui.h1.textContent, 'Secret sent');
  assert.match(ui.intro.textContent, /accepted the secret/);
  assert.doesNotMatch(ui.intro.textContent, /before supplying/);
  assert.strictEqual(ui.document.title, 'Secret sent · Keyrelay');
  assert.match(ui.message.textContent, /^Sent\./);
  assert.strictEqual(ui.message.classList.contains('error'), false);
  assert.strictEqual(ui.page.active, ui.message);
  assert.strictEqual(ui.page.timers.size, 0, 'timeout cleared');
}

function assertRecovered(ui, pattern) {
  assert.match(ui.message.textContent, pattern);
  assert.strictEqual(ui.message.classList.contains('error'), true);
  assert.ok(!ui.message.textContent.includes(FAKE), 'value not shown');
  assert.strictEqual(ui.input.value, '');
  assert.strictEqual(ui.input.disabled, false);
  assert.strictEqual(ui.button.disabled, false);
  assert.strictEqual(ui.button.textContent, 'Send once');
  assert.strictEqual(ui.page.active, ui.input);
  assert.strictEqual(ui.form.removed, false);
  assert.strictEqual(ui.h1.textContent, 'Ready for a secret');
  assert.strictEqual(ui.document.title, 'Ready for a secret · Keyrelay');
  assert.strictEqual(ui.page.timers.size, 0, 'timeout cleared');
}

const scenarios = {
  async duplicatePendingSubmitThenSuccess() {
    const ui = setup();
    ui.input.value = FAKE;
    ui.submit();
    ui.submit();
    await flush();
    assert.strictEqual(ui.page.fetches.length, 1);
    const [call] = ui.page.fetches;
    assert.strictEqual(call.url, '/r/fake-request/submit');
    assert.strictEqual(call.options.method, 'POST');
    assert.deepStrictEqual(JSON.parse(call.options.body), {secret: FAKE});
    assertSending(ui);
    call.resolve(response(200));
    await flush();
    assertSucceeded(ui);
    assert.strictEqual(ui.page.fetches.length, 1);
  },

  async networkFailureIsAmbiguousThenManualRetry() {
    const ui = setup();
    ui.input.value = FAKE;
    ui.submit();
    await flush();
    assertSending(ui);
    ui.page.fetches[0].reject(new TypeError('Failed to fetch ' + FAKE));
    await flush();
    assertRecovered(ui, /Could not confirm delivery[\s\S]*check your terminal/);
    assert.ok(!ui.message.textContent.includes('Failed to fetch'), 'raw diagnostic hidden');
    await flush();
    assert.strictEqual(ui.page.fetches.length, 1, 'no automatic retry');

    ui.input.value = FAKE;
    ui.submit();
    await flush();
    assert.strictEqual(ui.page.fetches.length, 2);
    ui.page.fetches[1].resolve(response(200));
    await flush();
    assertSucceeded(ui);
  },

  async timeoutAbortsAndRecovers() {
    const ui = setup();
    ui.input.value = FAKE;
    ui.submit();
    await flush();
    assert.strictEqual(ui.page.timers.size, 1);
    const [[id, timer]] = ui.page.timers;
    assert.strictEqual(timer.ms, 15000);
    ui.page.timers.delete(id);
    timer.fn();
    await flush();
    assert.strictEqual(ui.page.fetches.length, 1);
    assertRecovered(ui, /Could not confirm delivery/);
  },

  async httpErrorsAreCategorized() {
    const expected = {
      400: /^Not accepted\. This request may already have a secret/,
      403: /^Access denied\./,
      404: /expired or was already completed/,
      500: /^Not sent \(error 500\)/,
    };
    for (const [status, pattern] of Object.entries(expected)) {
      const ui = setup();
      ui.input.value = FAKE;
      ui.submit();
      await flush();
      ui.page.fetches[0].resolve(response(Number(status)));
      await flush();
      assertRecovered(ui, pattern);
      assert.strictEqual(ui.page.fetches.length, 1);
    }
  },
};

(async () => {
  for (const [name, run] of Object.entries(scenarios)) {
    try {
      await run();
    } catch (error) {
      console.error(name + ': ' + error.message);
      process.exit(1);
    }
  }
  console.log('ok ' + Object.keys(scenarios).length);
})();

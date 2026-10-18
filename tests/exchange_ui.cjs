// Runs an exchange page's inline script (stdin) against a mocked DOM: visible fields stay text, all values clear on submit.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const inputs = [
  {dataset: {name: 'user', visible: '1'}, type: 'text', value: 'fake-user', disabled: false, focus() {}},
  {dataset: {name: 'password'}, type: 'password', value: 'fake-password', disabled: false, focus() {}},
];
const button = {};
const reveal = {pressed: 'false', setAttribute(_, value) { this.pressed = value; }, getAttribute() { return this.pressed; }, addEventListener(_, fn) { this.click = fn; }};
let submit;
const form = {querySelectorAll: () => inputs, querySelector: () => button, addEventListener: (_, fn) => submit = fn, remove() { this.removed = true; }};
const message = {classList: {toggle() {}}, focus() {}};
let payload;
const context = {document: {getElementById: id => ({form, message, intro: {}, reveal})[id], querySelector: () => ({})}, location: {pathname: '/r/test'}, AbortController, setTimeout, clearTimeout,
  fetch: async (_url, options) => {
    payload = JSON.parse(JSON.parse(options.body).secret);
    assert.ok(inputs.every(i => i.value === '' && i.disabled));
    assert.deepEqual(inputs.map(i => i.type), ['text', 'password']);
    return {ok: true};
  }};
vm.runInNewContext(require('node:fs').readFileSync(0, 'utf8'), context);
reveal.click();
assert.deepEqual(inputs.map(i => i.type), ['text', 'text']);
(async () => {
  await submit({preventDefault() {}});
  assert.deepEqual(payload, {user: 'fake-user', password: 'fake-password'});
  assert.ok(form.removed);
})().catch(error => { console.error(error); process.exitCode = 1; });

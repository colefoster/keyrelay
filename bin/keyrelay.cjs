#!/usr/bin/env node
'use strict';
const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const candidates = process.platform === 'win32'
  ? [['py', '-3'], ['python3'], ['python']]
  : [['python3'], ['python']];
const python = candidates.find(([program, ...args]) => {
  const result = spawnSync(program, [...args, '-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'], { stdio: 'ignore' });
  return result.status === 0;
});
if (!python) {
  console.error('Keyrelay needs Python 3.9 or newer. Install it from https://www.python.org/downloads/, then run this command again.');
  process.exit(1);
}
const [program, ...prefix] = python;
const args = process.argv.slice(2);
const child = spawn(program, [...prefix, path.join(__dirname, '..', 'keyrelay.py'), ...(args.length ? args : ['--help'])], { stdio: 'inherit' });
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}
child.on('error', error => {
  console.error(`Could not start Keyrelay: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 1);
});

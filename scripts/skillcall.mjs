#!/usr/bin/env node
// Windows-safe runner for the installed binance-web3 skill CLIs.
// Their `if (import.meta.url === `file://${process.argv[1]}`)` entry guard
// never matches on Windows (backslash paths), so `node cli.mjs ...` exits 0
// with no output. This wrapper imports the module and dispatches directly.
//
// Usage: node scripts/skillcall.mjs <skill-dir-name> <command> '<json_params>'
// e.g.:  node scripts/skillcall.mjs binance-trading-signal smart-money '{"chainId":"56"}'

import { pathToFileURL } from 'node:url';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const [skill, cmd, paramsStr] = process.argv.slice(2);
if (!skill || !cmd) {
  console.error("usage: node scripts/skillcall.mjs <skill> <command> '<json_params>'");
  process.exit(1);
}
const cliPath = resolve(here, '..', '.agents', 'skills', skill, 'scripts', 'cli.mjs');
const mod = await import(pathToFileURL(cliPath).href);
const builder = mod.COMMANDS[cmd];
if (!builder) {
  console.error(`Unknown command '${cmd}'. Available: ${Object.keys(mod.COMMANDS).join(', ')}`);
  process.exit(1);
}
let params = {};
if (paramsStr) params = JSON.parse(paramsStr);
try {
  const result = await mod.call(builder(params));
  console.log(JSON.stringify(result, null, 2));
} catch (err) {
  console.error(err.message);
  if (err.body) console.log(JSON.stringify(err.body, null, 2));
  process.exit(err.exitCode || 1);
}

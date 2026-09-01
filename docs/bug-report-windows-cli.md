# Bug report: binance-web3 skill CLIs produce no output on Windows

**Affected skills:** `binance-trading-signal` (v3.3), `crypto-market-rank` (v3.0)
from binance-skills-hub (`skills/binance-web3/...`)

**Environment:** Windows 11 Home 10.0.26200, Node v24.13.1, installed via
`npx skills add <github-url>` on 2026-09-01.

## Symptom

Running either skill's CLI exactly as its SKILL.md documents produces **no
output and exit code 0**:

```
node .agents/skills/binance-trading-signal/scripts/cli.mjs smart-money '{"chainId":"56","page":1,"pageSize":3}'
# (no output, exit 0)
```

## Cause (observed in the script source)

Both `scripts/cli.mjs` files gate their dispatch block with:

```js
if (import.meta.url === `file://${process.argv[1]}`) { ... }
```

On Windows the two sides never match:

- `import.meta.url` is a file URL with forward slashes and a leading slash:
  `file:///C:/Users/<user>/project/.agents/skills/binance-trading-signal/scripts/cli.mjs`
- `` `file://${process.argv[1]}` `` interpolates the raw Windows path with
  backslashes: `file://C:\Users\<user>\project\.agents\skills\binance-trading-signal\scripts\cli.mjs`

The guard is false, the dispatch block is skipped, and the process exits 0
having done nothing. The module code itself is fine — its exported
`COMMANDS`/`call` work when imported.

## Reproduction

1. Windows, any Node >= 22.
2. `npx skills add https://github.com/binance/binance-skills-hub/tree/main/skills/binance-web3/binance-trading-signal`
3. `node <skill-dir>/scripts/cli.mjs smart-money '{"chainId":"56","page":1,"pageSize":3}'`
4. Observe: exit 0, zero bytes of output. Same for `crypto-market-rank`
   (`node <skill-dir>/scripts/cli.mjs token-rank '{"rankType":10,"chainId":"56"}'`).

## Workaround

Import the module and dispatch manually, converting the path with
`pathToFileURL`:

```js
import { pathToFileURL } from 'node:url';
const mod = await import(pathToFileURL(cliPath).href);
const result = await mod.call(mod.COMMANDS['smart-money']({ chainId: '56' }));
```

## Suggested fix

Use the standard portable guard:

```js
import { pathToFileURL } from 'node:url';
if (import.meta.url === pathToFileURL(process.argv[1]).href) { ... }
```

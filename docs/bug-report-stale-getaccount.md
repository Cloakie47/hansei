# Bug report: spot_getAccount serves a stale snapshot after a confirmed deposit

**Affected tool:** `spot_getAccount` on the Binance MCP server
(`https://agent.binance.com/mcp/agentic`), authenticated Agentic sub-account
session (uid 1273127438).

**Environment:** Claude Code on Windows, 2026-09-02 session (~06:50-07:20 UTC).

## Summary

40 USDT was deposited and credited to the sub-account's Spot wallet at
2026-09-01T18:16:01Z (confirmed by `wallet_depositHistory`, status 1).
Roughly twelve hours later, `spot_getAccount` still returned USDT
`0.00000000` with `updateTime` frozen at 1788279320551 =
2026-09-01T16:15:20.551Z — a timestamp BEFORE the deposit — across 4 calls,
while `wallet_queryUserWalletBalance` reported the funds correctly.

## Exact calls and responses

Call 1: `spot_getAccount` `{"omitZeroBalances": true}`
Response (abridged to the relevant fields):
`{"updateTime":1788279320551,"accountType":"SPOT","balances":[],"permissions":["TRD_GRP_049"],"uid":1273127438}`

Call 2: `spot_getAccount` `{}` (no params)
Response: full balance list of every listable asset, all zero, including:
`{"asset":"USDT","free":"0.00000000","locked":"0.00000000"}` — same
`updateTime` 1788279320551.

Call 3: `spot_getAccount` `{"omitZeroBalances": true}` (retry, minutes later)
Response: identical to call 1 — `"balances":[]`, `updateTime` 1788279320551.

Call 4: `spot_getAccount` `{"omitZeroBalances": true, "recvWindow": 10000}`
(cache-bust attempt)
Response: identical — `"balances":[]`, `updateTime` 1788279320551.

## Cross-checks in the same session

`wallet_queryUserWalletBalance` `{}` (default BTC quote):
`[{"activate":true,"balance":"0.0005224","walletName":"Spot"}, ...rest 0]`

`wallet_queryUserWalletBalance` `{"quoteAsset": "USDT"}`:
`[{"activate":true,"balance":"40","walletName":"Spot"}, ...rest 0]`

`wallet_depositHistory` `{}`:
`[{"id":"5206442588739550208","amount":"40","coin":"USDT","network":"BSC","status":1,"address":"0x18ff8442eaead681ce51c0138dcfd5f117629685","addressTag":"","txId":"0x6cf49f154709b797c884e293296323e87a7292d4efd130dba7aaaf44ccafbc17","insertTime":1788286561000,"transferType":0,"confirmTimes":"1/1","unlockConfirm":0,"walletType":0,"travelRuleStatus":1}]`

(`insertTime` 1788286561000 = 2026-09-01T18:16:01Z; `walletType` 0 = Spot;
`status` 1 = success.)

## Observed facts

- `spot_getAccount.updateTime` (2026-09-01T16:15:20Z) predates the deposit
  credit (18:16:01Z) and did not advance across 4 calls spanning the session.
- Two other authenticated endpoints on the same session reflect the deposit.
- The tool's own doc says "Data Source: Memory => Database"; we observed
  only that the returned snapshot is stale, not why.

## Impact

An agent that trusts `spot_getAccount` alone sizes trades against phantom
capital. In this instance the stale figure was LOWER than reality (0 vs 40
USDT), which fails safe — the agent refuses to trade. But the same staleness
after a balance-reducing event (a fill or transfer out) would report MORE
free USDT than exists, and an agent would oversize or place orders that
cannot settle. Our workaround: prefer `spot_getAccount` only when its
`updateTime` is at least as fresh as the latest known deposit/fill, fall
back to `wallet_queryUserWalletBalance` only while the wallet provably holds
nothing but USDT, and refuse to size a trade otherwise.

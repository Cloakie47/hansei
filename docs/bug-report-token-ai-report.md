# Bug report: analysis_getTokenAiReport returns empty success, no report object

**Affected tool:** `analysis_getTokenAiReport` on the Binance MCP server
(`https://agent.binance.com/mcp/agentic`)

**Environment:** Claude Code on Windows, authenticated Agentic sub-account
session, 2026-09-01 (~17:00 UTC).

## Symptom

The tool returns a bare success envelope with no report payload for every
token tested, including `BTC`, the example in the tool's own schema
documentation.

## Exact calls and responses

Call 1: `analysis_getTokenAiReport` with `{"token": "BNB"}`
Response: `{"code":"000000","success":true}`

Call 2: `analysis_getTokenAiReport` with `{"token": "XRP"}`
Response: `{"code":"000000","success":true}`

Call 3: `analysis_getTokenAiReport` with `{"token": "BTC"}`
Response: `{"code":"000000","success":true}`

All three calls omitted the optional `timestamp`, `product`, and `expId`
fields, which the schema explicitly recommends ("When `timestamp` is omitted
the latest available report is returned; when `product` is omitted it
defaults to `spot`").

## Expected

Per the tool description: "Returns a structured report (report metadata,
token metadata, and content modules) for the given token."

## Observed

No `data` field, no report metadata, no content modules, only
`{"code":"000000","success":true}`, identical for every token.

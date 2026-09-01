# HANSEI Rulebook
Rules are numbered permanently. Deleted rules are struck through, never removed.

- **R001** Never propose more than 20% of sub-account balance in one position.
- **R002** Run query-token-audit before proposing anything outside the top 20 pairs.
- **R003** Do not re-propose an idea rejected in the last 24h unless something
  material changed — and state what changed.
- **R004** Any restriction on a tool must also cover tool_execute invoked with
  that tool name as an argument. The visible tool list understates the write
  surface.
- **R005** Only propose assets that exist as an active Binance spot USDT pair.
  Signals for non-listed assets are discarded at ingest.
- **R006** A signal counts as evidence for a spot pair only if its contract
  address matches the canonical Binance-Peg or issuer contract for that asset.
  If the canonical contract cannot be determined, the signal is DISCARDED, not
  accepted. Ticker-string matches alone are never sufficient.
- **R007** Evidence must draw on at least two structurally independent sources
  (cross-sectional, time series, order book, report). Multiple readings of one
  source count as one.

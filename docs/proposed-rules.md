# Proposed rules awaiting Pilot approval

NOT in rulebook.md. Rules take effect only when the Pilot approves them.

## Proposed (2026-09-02): exclude ultra-volatile pairs from the pool

- **R016 (PROPOSED)** Pairs whose RAW average daily move exceeds 12% are
  excluded from the scan universe. Rationale: a 12%-daily asset routinely
  travels ±20% inside the R013 72h hold — structural stops are meaningless
  at that amplitude and the pair is not swing-tradeable on our clock. The
  8% threshold-scaling cap (shipped) makes their thresholds sane; this
  exclusion would remove them entirely. NOT SHIPPED — awaiting Pilot
  approval; 12% chosen as 1.5x the scaling cap so the buffer zone between
  "capped" and "excluded" stays visible in the setups log.

## Resolved

- R014 — APPROVED 2026-09-02 with the Pilot's wording; now in rulebook.md,
  gate active in propose.build_packet, every block logged to
  logs/suppressed.jsonl with the computed R:R.

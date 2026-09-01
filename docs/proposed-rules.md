# Proposed rules awaiting Pilot approval

NOT in rulebook.md. Rules take effect only when the Pilot approves them.

## R014 (PROPOSED 2026-09-02 — minimum reward-to-risk)

Draft wording:

- **R014** A packet requires a reward-to-risk of at least 2:1, computed from
  structural levels (target = the relevant swing objective for the setup,
  stop = the recent swing low), never from fixed percentages. The R:R and
  both levels are rendered on the packet. A draft below 2:1 is suppressed to
  NO_PROPOSAL and logged to logs/suppressed.jsonl with its computed R:R.

Implementation status: the computation is already live (risk_reward in
scripts/scan.py; rendered on packets as "R:R x.x : 1 (target, stop)") and
R:R failures are REPORTED but do not yet block. The gate activates only on
approval of this rule.

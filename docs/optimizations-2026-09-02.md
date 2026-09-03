# Top 5 optimizations, 2026-09-02, ranked by demo impact

Ranked list, the weakness each addresses, and what happened tonight. Every
implemented item has a line in logs/autonomous-changes.jsonl and its own
commit.

## 1. Replay mode (IMPLEMENTED, scripts/replay.py)

Weakness: the demo's core claim is "the agent learns the Pilot's judgment,"
but a quiet tape yields ~0-3 live decisions/day, by demo day the Sync Rate
chart could have five points. Replay drills the decision loop on historical
data: anonymised symbols (SYM-xx), hidden dates, packets from A+B evidence,
and an outcome REVEAL after each verdict (+6h/+24h/best/worst). Strict
separation: everything under logs/replay/, decisions flagged replay:true,
never mixed into live Sync Rate. Two sessions exist (s30d7, s45d11, one
s30d7 packet's identity was exposed by the code-path proof and is marked
compromised; the rest are blind). FOR PILOT AWARENESS: replay maps 2-of-2
AVAILABLE sources to 62% because order books have no history; live mappings
untouched.

## 2. Quiet-tape throughput package (IMPLEMENTED, three tuning commits)

Weakness: two consecutive zero-packet scans; diagnosis with numbers in
logs/quiet-tape-diagnosis-2026-09-02.md. Floor 20m -> 15m (25 -> 40
eligible pairs; scan 6 measured 33 past floor), deep cap 12 -> 16, and the
Source A change trigger is now volatility-relative (max(2.5%, 1.6x the
pair's own 7d average absolute daily move)) so majors can trigger on moves
that are large for them. Scan 6 result, honestly: more candidates (10
two-source), still zero three-source, the bottleneck has moved to the
confluence requirement, which is the approval ask below.

## 3. Approved-draft placement flow (IMPLEMENTED, run.py/propose.py)

Weakness: approving a packet DELETED the draft that the placement step
needs, the first real approval would have dead-ended at 1am. Approved
drafts now persist to logs/approved/<id>.json and run.py verdict prints the
exact three placement steps (prepare, the MCP call, record) for the current
MODE. Chart auto-refreshes after verdicts; run.py chart added.

## 4. Docs-reality sweep (IMPLEMENTED)

Weakness: judge-visible inconsistencies. CLAUDE.md's file layout predated
packets/, docs/, replay/, the suppression logs; the build-order checklist
showed nothing done; the skills list included never-installed skills
without status; the packet spec's example rules used placeholder ids that
now collide with real rules (its "R007"/"R011" mean different things
today). All brought to reality. Remaining flagged, not fixed: the p-005
and p-006 packet files still show the pre-R009 54/55% confidence with the
LOW CONVICTION banner, historically accurate, left as the record.

## 5. Two-source pathway (REQUIRES PILOT APPROVAL, the real bottleneck)

Weakness: after the sign fix, genuine 3-source confluence is rare (0
instances in the last 3 scans; 9 instances in 2 volatile days before).
Mechanical v1 maps 2-source to 57%, under the floor, so the live pipeline
produces near-zero packets in normal conditions, while scan 6 shows 10
two-source candidates with real excursions (FIL +17%, CRV +16%, ONG +24%).
OPTIONS, Pilot to choose:
  a. Keep v1 as-is: quiet tape = quiet agent. Sync Rate stays sparse;
     replay carries the demo. (No change.)
  b. Approve confidence v2 EARLY, seeded by replay outcomes instead of the
     8 live decided proposals, v2's evidence-scaled spread could put
     strong 2-source candidates (huge volume multiple, aligned book) at or
     above 60% and weak 3-source below it. This changes what crosses
     R009's floor -> approval required.
  c. Approve a 2-source mapping bump (57 -> 60). Bluntest lever; explicitly
     loosens the effective gate -> approval required, and the suppression
     log's clustering check would be watching its own designer.
Recommendation: (b), calibrated on replay reveals, keeping the 60% floor
untouched. Decision is yours.

## Also flagged, no action

- spot_getAccount staleness persists (bug report filed); balance falls back
  safely but the first LIVE fill will force the fresh-getAccount path,
  re-verify freshness that day.
- Square publishing still needs the OpenAPI key (dry run ready).
- The Debrief's Step 2/4/5 prose remains Unit-written by design; run.py
  debrief computes the numbers only.

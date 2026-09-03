# HANSEI, 90-second demo script

Format: SHOW = what is on screen. SAY = the spoken line. Target ~230 words
spoken; each beat 10-20 seconds. Terminal font large; files pre-opened in
tabs (list at the bottom of this doc).

## Beat 1, the claim, proven with timestamps (0:00-0:20)

SHOW: README.md, section "The claim, proven with timestamps", scroll
slowly through the five bullets. Then a split: git log entry fe0dcf0
(20:14Z) beside logs/proposals.jsonl's CONVICTION rejections.

SAY: "HANSEI is a short-swing system, entries on daily structure,
positions held hours to three days, a 72-hour hard stop, and every entry
and exit individually approved by a human. It proposes; I decide. Here is
that loop working, with timestamps. At 19:57 UTC my agent generated two packets. At 20:05 I
rejected them as momentum chases. At 20:14, nine minutes later, a setup
classifier built from that critique was committed, and at 20:25 it
independently flagged both packets as CHASE. Human judgment first, code
catching up, then agreeing. That ordering is in the git history."

## Beat 2, a live scan, zero packets, every failure named (0:20-0:45)

SHOW: terminal, `python scripts/run.py scan` running live. Let the output
land; zoom on the VOTE FAILED lines and the R009/R014 suppression lines.

STALENESS GUARD, do this on camera or in the cut, do NOT skip: the
dashboard's funnel is a snapshot of ONE scan. If you show a scan here and
then open a dashboard built from an earlier scan, the numbers mismatch and
a judge could catch it. So, in order, every time:
  1. python scripts/run.py scan          (Beat 2, on screen)
  2. python scripts/dashboard.py          (regenerate, ~1 second, inlines
                                           this scan's funnel + the stamp)
  3. open dashboard/index.html            (Beat 3+)
The dashboard's orange stamp bar prints the generation time and the scan id
it is showing; glance at it before filming the dashboard, if it names a
different scan than the terminal, run step 2 again.

SAY: "This is a live scan. Twenty-five pairs pass the volume floor,
sixteen get deep analysis, four classify as setups, and zero become
proposals. Watch WHY: every failure is named by dimension. This pullback
failed trend structure and location. This one passed its checklist and
died because the reward-to-risk was 0.68 to 1, priced honestly off a
structural stop, and it doesn't pay. A quiet tape producing zero packets
is a correct output, and every silence is auditable."

## Beat 3, the rulebook is the learning (0:45-1:05)

SHOW: rulebook.md, scrolled top to bottom, pausing on struck-through R002
and R007. Then dashboard/sync-rate.png, rulebook-growth panel.

SAY: "Sixteen rules in two days, every one traceable to a logged event,
a fake token that impersonated WINkLink became the contract-verification
rule; a 268-to-1 fantasy ratio became the reachability cap. Struck rules
stay visible forever. The rulebook is the learning, and it is append-only."

## Beat 4, the honest part (1:05-1:30)

SHOW: debriefs/2026-09-02.md, the addendum "the drill that audited its
maker". Highlight the R013 paragraph, then the 'believed fixed' line.

SAY: "One honest limit, said before you find it: stops and targets gate
every trade but no protective order rests on the exchange, between scans
the stop is advisory, positions are guarded by the 72-hour time stop and
the human's presence. We assessed the protective-OCO path and documented
why shipping an untestable write flow would have broken our own rules.
And the part I trust most: the system documents its own failures.
Three times, documented behavior turned out to be unimplemented. Sharpest:
rule R013 promised an exit proposal for any position held past 72 hours,
it was rule text with no code behind it until a drill exposed it. A
same-signal bug was 'believed fixed' twice before a re-score proved
otherwise. Approving a packet used to delete the very draft needed to
place it. Every one is in the nightly debrief, published, unedited.
Believed-fixed is not a state. The record is."

## Closing card (1:30)

SHOW: repo URL + the line "Zero approvals so far. Zero pretending."

## Pre-open these tabs before recording

1. README.md (timestamp section visible)
2. terminal at repo root, balance context fresh (run the three MCP calls
   + run.py balance no more than 25 minutes before recording)
3. rulebook.md
4. dashboard/sync-rate.png
5. debriefs/2026-09-02.md (addendum in view)
6. logs/proposals.jsonl (tail)

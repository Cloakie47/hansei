# Assessed and declined: a clickable web UI that places orders

Date: 2026-09-03. The Pilot asked whether a browser page could run analysis,
view reports, and place buy/sell/limit orders with buttons. Assessed, and
DECLINED — building nothing. The reasoning is recorded because the decision
is itself part of the product's design integrity.

## What was asked

A local web page (like our existing dashboard/index.html) with controls to
place trades directly, not just read reports.

## Four reasons for declining

1. IT LITERALLY CANNOT PLACE ORDERS. The Binance MCP is reached only through
   the Claude Code session's OAuth. spot_newOrder, tool_execute, and every
   authenticated tool are callable solely from inside the live Claude
   session — not over HTTP from a browser. Our dashboard is a file:// page
   with no server, no credential, and no route to agent.binance.com/mcp/
   agentic; that OAuth belongs to the Claude Code process. A page CAN read
   local files, render them, and fetch PUBLIC market data; it CANNOT place,
   cancel, or read authenticated account state. There is no button a static
   page can carry that executes a trade. Making one possible would mean
   re-architecting authentication, which the feature freeze forbids.

2. THE HONEST VERSION DUPLICATES THE TERMINAL. The most a page could truthfully
   offer is: read the logs (the dashboard already does this) and PRINT the
   exact tool-call for the human to paste into the Claude session — the same
   prepare/record split place.py already uses. That print-a-command surface
   is exactly what run.py already provides in the terminal, which is the
   demo surface. Rebuilding it in a browser adds no capability.

3. BUY/SELL BUTTONS CONTRADICT THE PREMISE. The README and demo LEAD with
   "it cannot execute anything on its own; every trade requires the Pilot's
   confirmation, enforced by Binance." A page with a BUY button reads as
   one-click execution — the opposite of the product's premise and its
   safety story. A judge sees a buy button and reads "this app trades,"
   undermining the single most defensible thing about the design. Even a
   button that only printed a command would send the wrong message.

4. OPPORTUNITY COST. With the deadline near, zero live packets, undecided
   drills, and the video unshot, hours spent on a web order UI are hours not
   spent on the artifacts that must exist. It is the highest-opportunity-cost
   item available.

## The design position this records

Confirm-before-execute is not a limitation we tolerate; it is the product.
The correct web artifact is the read-only, honest dashboard we already have
— it reports and it does not pretend to trade. A trading UI would have been
either impossible (through session MCP) or dishonest (buttons that imply
execution). We chose to show the reasoning rather than the buttons.

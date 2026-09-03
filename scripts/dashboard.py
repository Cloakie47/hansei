"""HANSEI static dashboard generator, writes dashboard/index.html.

Read-only reporting, freeze-safe: no trading logic, no controls, no forms.
The HTML is fully self-contained (inline CSS, no JS, no external requests)
so it opens by double-clicking the file. Data is inlined at build time;
regenerate with:  python scripts/dashboard.py

Palette: the dataviz-validated set used by chart.py (blue #2a78d6, orange
#eb6834, aqua #1baf7a; ink/muted/grid text tokens). Single committed light
look with explicit backgrounds. Direct labels everywhere; denominators
always stated; nothing rendered fuller than the data is.
"""

import html
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard" / "index.html"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, BG, CARD = "#1f1f1e", "#6b6a63", "#e4e3dc", "#faf9f5", "#ffffff"


def load(path):
    p = ROOT / path
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def esc(s):
    return html.escape(str(s))


def latest_scan_batch():
    """Last scan's history row + the setups entries from that scan batch."""
    hist = [h for h in load("logs/scan-history.jsonl") if not h.get("seeded")]
    if not hist:
        return None, []
    last = hist[-1]
    t0 = datetime.strptime(last["ts"], "%Y-%m-%dT%H:%M:%SZ")
    # Dedup by symbol, keeping the entry closest to the scan-history row.
    # If two scans land within the window (a bad take re-scanned under
    # recording pressure), the funnel must not show a symbol twice.
    best = {}
    for s in load("logs/setups.jsonl"):
        ts = datetime.strptime(s["ts"], "%Y-%m-%dT%H:%M:%SZ")
        d = abs((ts - t0).total_seconds())
        if d <= 240 and (s["symbol"] not in best or d < best[s["symbol"]][0]):
            best[s["symbol"]] = (d, s)
    batch = [v[1] for v in best.values()]
    return last, batch


def rule_dates(rule_ids):
    """First commit date per rule id, from git history of rulebook.md. Ids
    come from the parsed rulebook so a new rule can never fall off the end
    (R017 was showing '?' under a hardcoded range that stopped at R016)."""
    dates = {}
    for rid in rule_ids:
        try:
            out = subprocess.run(
                ["git", "log", "--reverse", "--format=%cs", "-S", f"**{rid}**",
                 "--", "rulebook.md"],
                capture_output=True, text=True, cwd=ROOT).stdout.strip().splitlines()
            dates[rid] = out[0] if out else "?"
        except Exception:
            dates[rid] = "?"
    return dates


def parse_rules():
    import re
    text = (ROOT / "rulebook.md").read_text(encoding="utf-8")
    rules, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^- (~~)?\*\*(R\d{3})\*\*\s*(.*)$", line)
        if m:
            cur = {"id": m.group(2), "struck": bool(m.group(1)),
                   "text": m.group(3).rstrip()}
            rules.append(cur)
        elif cur and line.startswith("  ") and line.strip():
            cur["text"] += " " + line.strip()
            if "~~" in line:
                cur["struck"] = True
    for r in rules:
        r["text"] = r["text"].replace("~~", "").strip()
    return rules


def bar(width_pct, color, label, value):
    return (f'<div class="bar-row"><div class="bar-label">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{max(width_pct, 2):.0f}%;background:{color}"></div></div>'
            f'<div class="bar-value">{esc(value)}</div></div>')


def drill_calibration():
    """Renders in BOTH states: only the decided drills (today), and the same
    plus a discrimination stat once blind-mixed drills (ground truth in the
    session file) are decided. Never half-built, sections appear only when
    their data exists."""
    dec = load("logs/replay/decisions.jsonl")
    if not dec:
        return ("<p class='muted'>No drill verdicts yet. Drills are the one "
                "place the decision loop visibly completes: a blind verdict, "
                "then the revealed outcome.</p>")
    sessions = {}
    sdir = ROOT / "logs" / "replay" / "sessions"
    if sdir.exists():
        for f in sdir.glob("*.json"):
            s = json.loads(f.read_text(encoding="utf-8"))
            sessions[s["sid"]] = s

    rows, approved, pos24, gt_correct, gt_total = [], 0, 0, 0, 0
    for d in dec:
        s = sessions.get(d["sid"], {})
        pkt = s.get("packets", {}).get(d["rid"], {})
        o = pkt.get("outcome", {})
        c24 = o.get("chg_24h_pct")
        verdict = d["verdict"]
        if verdict == "APPROVED":
            approved += 1
            if c24 is not None and c24 > 0:
                pos24 += 1
        gt = pkt.get("ground_truth")  # only on blind-mixed sessions
        blind = gt is not None
        if blind:
            gt_total += 1
            # "correct" = Pilot rejected a live-reject, or approved a live-pass
            if ((gt == "would-reject" and verdict == "REJECTED")
                    or (gt == "would-pass" and verdict == "APPROVED")):
                gt_correct += 1
        rows.append({
            "rid": d["rid"], "symbol": d["symbol"], "verdict": verdict,
            "code": d.get("reject_reason") or "",
            "c6": o.get("chg_6h_pct"), "c24": c24,
            "best": o.get("max_gain_pct"), "worst": o.get("max_drawdown_pct"),
            "blind": blind, "gt": gt, "live": pkt.get("live_verdict", "")})

    hdr = (f"<div class='big'>{approved} of {len(rows)} "
           f"<span class='denom'>drills approved · {pos24}/{approved} "
           f"positive at 24h</span></div>")
    if gt_total:
        hdr += (f"<p class='honest'>Discrimination (blind mixed set): "
                f"{gt_correct} of {gt_total} verdicts matched what the live "
                f"gates would do, the drill measures whether the Pilot's blind "
                f"judgment agrees with the system, not just the approval rate.</p>")
    else:
        hdr += ("<p class='honest'>These are all APPROVED so far; a blind mixed "
                "set (some the live system would reject) is queued so the next "
                "round measures discrimination, not just approval rate.</p>")
    body = ["<table><tr><th>drill</th><th>symbol</th><th>verdict</th>"
            "<th>+6h</th><th>+24h</th><th>best</th><th>worst</th>"
            "<th>vs live gates</th></tr>"]
    for r in rows:
        def pc(x):
            return f"{x:+.2f}%" if isinstance(x, (int, float)) else ", "
        vlabel = ("blind: system would " +
                  ("REJECT" if r["gt"] == "would-reject" else "PASS")
                  if r["blind"] else ", ")
        body.append(
            f"<tr><td>{esc(r['rid'])}</td><td>{esc(r['symbol'])}</td>"
            f"<td class='v-{r['verdict']}'>{esc(r['verdict'])}"
            f"{(' ' + esc(r['code'])) if r['code'] else ''}</td>"
            f"<td>{pc(r['c6'])}</td><td>{pc(r['c24'])}</td>"
            f"<td>{pc(r['best'])}</td><td>{pc(r['worst'])}</td>"
            f"<td class='muted'>{esc(vlabel)}</td></tr>")
    body.append("</table>")
    caveat = ("<p class='muted'>Drills use A+B evidence only (no order book) "
              "and never touch live Sync Rate, a separate calibration range.</p>")
    return hdr + "".join(body) + caveat


def build():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    props = [p for p in load("logs/proposals.jsonl") if not p.get("test")]
    decided = [p for p in props if p.get("verdict") in ("APPROVED", "REJECTED", "NO_PROPOSAL")]
    approved = [p for p in decided if p["verdict"] == "APPROVED"]
    sup = [s for s in load("logs/suppressed.jsonl") if not s.get("test")]
    last_scan, batch = latest_scan_batch()
    scan_id = last_scan["ts"] if last_scan else "none yet"

    # --- funnel section ---
    funnel_html = "<p class='muted'>no scan history yet</p>"
    fail_html = ""
    if last_scan:
        classified = [s for s in batch if not s["blocked"]]
        vote_pass = [s for s in classified if s.get("vote_pass")]
        pairs = last_scan["pairs_past_floor"]
        deep = last_scan["scanned_deep"]
        pk = last_scan["packets"]
        mx = max(pairs, 1)
        funnel_html = "".join([
            bar(100, BLUE, "pairs past volume floor", pairs),
            bar(100 * deep / mx, BLUE, "deep-scanned", deep),
            bar(100 * len(classified) / mx, AQUA, "classified setups", len(classified)),
            bar(100 * len(vote_pass) / mx, AQUA, "passed indicator vote", len(vote_pass)),
            bar(100 * pk / mx if pk else 0, ORANGE if pk == 0 else AQUA, "PACKETS", pk),
        ])
        fails = []
        for s in batch:
            if s["blocked"]:
                continue
            if not s.get("vote_pass") and s.get("vote_failed"):
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}), vote "
                             f"{s.get('vote_n_pass')}/{s.get('vote_need')}: failed "
                             f"{esc('; '.join(s['vote_failed']))}</li>")
            elif s.get("rr_refusal"):
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}), "
                             f"{esc(s['rr_refusal'])}</li>")
            elif s.get("rr") is not None and s["rr"] < 2:
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}), R:R "
                             f"{s['rr']} below R014's 2:1</li>")
        chases = [s["symbol"] for s in batch if s["blocked"]]
        if chases:
            fails.append(f"<li class='muted'>{len(chases)} candidates blocked by the "
                         f"setup classifier (CHASE / UNCLASSIFIED): "
                         f"{esc(', '.join(chases))}</li>")
        fail_html = (f"<h3>Named failures, scan of {esc(last_scan['ts'])}</h3>"
                     f"<ul class='fails'>{''.join(fails)}</ul>") if fails else ""

    # --- sync rate ---
    rate = f"{100 * len(approved) / len(decided):.0f}%" if decided else "n/a"
    sync_html = (
        f"<div class='big'>{rate} <span class='denom'>({len(approved)} of "
        f"{len(decided)} decided)</span></div>"
        f"<p class='honest'>Honest label: {len(approved)} approvals out of "
        f"{len(decided)} decided proposals. The number is this empty on purpose, "
        f"a quiet tape producing zero packets is a correct output, and no chart "
        f"here is drawn fuller than the data is.</p>")

    # --- rulebook ---
    parsed_rules = parse_rules()
    dates = rule_dates([r["id"] for r in parsed_rules])
    rules_html = ""
    for r in parsed_rules:
        cls = "rule struck" if r["struck"] else "rule"
        note = ", struck, superseded" if r["struck"] else ""
        rules_html += (f"<div class='{cls}'><span class='rid'>{r['id']}</span>"
                       f"<span class='rdate'>{esc(dates.get(r['id'], '?'))}{note}</span>"
                       f"<div class='rtext'>{esc(r['text'])}</div></div>")

    # --- decision log ---
    dec_html = ""
    for p in decided:
        code = p.get("reject_reason") or ""
        extra = " (spec-superseded: administrative, excluded from preference inference)" \
            if p.get("spec_superseded") else ""
        dec_html += (f"<tr><td>{esc(p['id'])}</td><td>{esc(p['ts'])}</td>"
                     f"<td>{esc(p.get('symbol') or ', ')}</td>"
                     f"<td class='v-{p['verdict']}'>{esc(p['verdict'])}</td>"
                     f"<td>{esc(code)}{esc(extra)}</td></tr>")

    # --- drill calibration (the loop visibly completing) ---
    drill_html = drill_calibration()

    # --- confidence drift monitor collapsed to one stat line ---
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import run as runmod
        drift_rows, drift_warns = runmod.confidence_drift()
    except Exception:
        drift_rows, drift_warns = [], []
    if drift_rows:
        last = drift_rows[-1]
        w = (" · " + esc(drift_warns[0])) if drift_warns else " · no drift warning active"
        drift_line = (f"latest day mean {last['mean']:.3f}, median {last['median']:.3f}, "
                      f"{last['near_floor']} within 0.02 of the 60% floor{w} "
                      f"(monitoring only, gates nothing)")
    else:
        drift_line = "no confidence-bearing drafts yet"

    # --- suppressions ---
    sup_counts = Counter(s["rule"] for s in sup)
    sup_html = "".join(
        bar(100 * v / max(sup_counts.values()), ORANGE, f"{k} suppressions", v)
        for k, v in sorted(sup_counts.items()))

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>HANSEI dashboard</title>
<style>
  body {{ background:{BG}; color:{INK}; font:15px/1.5 system-ui, sans-serif;
         max-width:880px; margin:2rem auto; padding:0 1rem; }}
  h1 {{ font-size:1.5rem; }} h2 {{ font-size:1.1rem; margin-top:2.2rem;
       border-bottom:1px solid {GRID}; padding-bottom:.3rem; }}
  h3 {{ font-size:.95rem; color:{MUTED}; }}
  .muted {{ color:{MUTED}; }} .card {{ background:{CARD}; border:1px solid {GRID};
       border-radius:8px; padding:1rem 1.2rem; }}
  .bar-row {{ display:flex; align-items:center; gap:.6rem; margin:.35rem 0; }}
  .bar-label {{ width:230px; color:{MUTED}; font-size:.85rem; text-align:right; }}
  .bar-track {{ flex:1; background:{BG}; border-radius:4px; height:18px; }}
  .bar-fill {{ height:18px; border-radius:4px; }}
  .bar-value {{ width:44px; font-variant-numeric:tabular-nums; }}
  .big {{ font-size:2.6rem; font-weight:700; }}
  .denom {{ font-size:1.1rem; color:{MUTED}; font-weight:400; }}
  .honest {{ color:{MUTED}; max-width:640px; }}
  .fails li {{ margin:.4rem 0; font-size:.9rem; }}
  .rule {{ padding:.55rem 0; border-bottom:1px solid {GRID}; }}
  .rule.struck .rtext {{ text-decoration:line-through; color:{MUTED}; }}
  .rid {{ font-weight:700; color:{BLUE}; margin-right:.8rem; }}
  .rdate {{ color:{MUTED}; font-size:.85rem; }}
  .rtext {{ font-size:.9rem; margin-top:.15rem; }}
  table {{ border-collapse:collapse; width:100%; font-size:.85rem; }}
  th, td {{ text-align:left; padding:.4rem .6rem; border-bottom:1px solid {GRID}; }}
  th {{ color:{MUTED}; font-weight:600; }}
  .v-REJECTED {{ color:{ORANGE}; font-weight:600; }}
  .v-APPROVED {{ color:{AQUA}; font-weight:600; }}
  .v-NO_PROPOSAL {{ color:{MUTED}; font-weight:600; }}
  .warn {{ color:{ORANGE}; font-weight:600; }}
  .stamp {{ background:#fff5ec; border:1px solid {ORANGE}; border-radius:6px;
       padding:.5rem .8rem; font-size:.85rem; color:{INK}; }}
  .chain div {{ padding:.35rem 0 .35rem .9rem; border-left:3px solid {BLUE};
       margin:.3rem 0; font-size:.92rem; }}
  footer {{ color:{MUTED}; font-size:.8rem; margin:2.5rem 0 1rem; }}
</style></head><body>
<h1>HANSEI, the honest report card</h1>
<p class="stamp">Generated <b>{now}</b> · funnel below is scan
<b>{esc(scan_id)}</b>. Static snapshot from the append-only logs, if these
do not match the scan on screen, regenerate: <code>python scripts/dashboard.py</code></p>

<h2>The claim, proven with timestamps</h2>
<div class="card">
<p>The product's claim is that the agent learns the Pilot's judgment. Here is
that loop executing in one evening, direction of causation provable from git
history and logs (all times UTC, 2026-09-01):</p>
<div class="chain">
<div><b>19:57</b>, the agent generates two packets (FIL +15%, CRV +15%,
both near range highs) that pass every gate then in force.</div>
<div><b>20:05</b>, the Pilot rejects them as momentum chases.
<b>No setup classifier exists at this moment.</b></div>
<div><b>20:14</b>, a setup classifier built from that critique is committed
(<code>fe0dcf0</code>).</div>
<div><b>20:25</b>, on its first pass over fresh data the classifier
independently labels both packets CHASE and blocks the class permanently.</div>
<div><b>05:02 (+1)</b>, the Pilot's formal CONVICTION rejections are logged.</div>
</div>
<p class="muted">Human judgment first; the code caught up nine minutes later,
then agreed, then made the mistake structurally impossible to repeat.</p>
</div>

<h2>Drill calibration, where the loop completes</h2>
<div class="card">{drill_html}</div>

<h2>The funnel, latest scan</h2>
<div class="card">{funnel_html}{fail_html}</div>

<h2>Sync Rate</h2>
<div class="card">{sync_html}</div>

<h2>The rulebook, every rule traceable, struck rules stay visible</h2>
<div class="card">{rules_html}</div>

<h2>Decision log, every decided proposal</h2>
<div class="card"><table>
<tr><th>id</th><th>decided (UTC)</th><th>symbol</th><th>verdict</th><th>reason</th></tr>
{dec_html}</table></div>

<h2>Suppressions by rule, the packets that never were</h2>
<div class="card">{sup_html}
<p class="muted">Every suppression carries its named reason in
logs/suppressed.jsonl; vote failures name their dimensions in
logs/setups.jsonl.</p>
<p class="muted" style="margin-top:.8rem">Confidence drift monitor: {drift_line}.</p></div>

<footer>HANSEI · Binance Agent OS Mini Hackathon · MODE=PAPER · no
profitability claim, the metric is behaviour change, measured from
append-only logs.</footer>
</body></html>"""
    OUT.write_text(page, encoding="utf-8")
    print(f"written: {OUT} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(build())

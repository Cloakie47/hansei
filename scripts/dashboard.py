"""HANSEI static dashboard generator — writes dashboard/index.html.

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
    batch = []
    for s in load("logs/setups.jsonl"):
        ts = datetime.strptime(s["ts"], "%Y-%m-%dT%H:%M:%SZ")
        if abs((ts - t0).total_seconds()) <= 240:
            batch.append(s)
    return last, batch


def rule_dates():
    """First commit date per rule id, from git history of rulebook.md."""
    dates = {}
    for n in range(1, 17):
        rid = f"R{n:03d}"
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


def build():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    props = [p for p in load("logs/proposals.jsonl") if not p.get("test")]
    decided = [p for p in props if p.get("verdict") in ("APPROVED", "REJECTED", "NO_PROPOSAL")]
    approved = [p for p in decided if p["verdict"] == "APPROVED"]
    sup = [s for s in load("logs/suppressed.jsonl") if not s.get("test")]
    last_scan, batch = latest_scan_batch()

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
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}) — vote "
                             f"{s.get('vote_n_pass')}/{s.get('vote_need')}: failed "
                             f"{esc('; '.join(s['vote_failed']))}</li>")
            elif s.get("rr_refusal"):
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}) — "
                             f"{esc(s['rr_refusal'])}</li>")
            elif s.get("rr") is not None and s["rr"] < 2:
                fails.append(f"<li><b>{esc(s['symbol'])}</b> ({esc(s['setup'])}) — R:R "
                             f"{s['rr']} below R014's 2:1</li>")
        chases = [s["symbol"] for s in batch if s["blocked"]]
        if chases:
            fails.append(f"<li class='muted'>{len(chases)} candidates blocked by the "
                         f"setup classifier (CHASE / UNCLASSIFIED): "
                         f"{esc(', '.join(chases))}</li>")
        fail_html = (f"<h3>Named failures — scan of {esc(last_scan['ts'])}</h3>"
                     f"<ul class='fails'>{''.join(fails)}</ul>") if fails else ""

    # --- sync rate ---
    rate = f"{100 * len(approved) / len(decided):.0f}%" if decided else "n/a"
    sync_html = (
        f"<div class='big'>{rate} <span class='denom'>({len(approved)} of "
        f"{len(decided)} decided)</span></div>"
        f"<p class='honest'>Honest label: {len(approved)} approvals out of "
        f"{len(decided)} decided proposals. The number is this empty on purpose — "
        f"a quiet tape producing zero packets is a correct output, and no chart "
        f"here is drawn fuller than the data is.</p>")

    # --- rulebook ---
    dates = rule_dates()
    rules_html = ""
    for r in parse_rules():
        cls = "rule struck" if r["struck"] else "rule"
        note = " — struck, superseded" if r["struck"] else ""
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
                     f"<td>{esc(p.get('symbol') or '—')}</td>"
                     f"<td class='v-{p['verdict']}'>{esc(p['verdict'])}</td>"
                     f"<td>{esc(code)}{esc(extra)}</td></tr>")

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
  footer {{ color:{MUTED}; font-size:.8rem; margin:2.5rem 0 1rem; }}
</style></head><body>
<h1>HANSEI — the honest report card</h1>
<p class="muted">Static, read-only snapshot generated {now} by
scripts/dashboard.py from the append-only logs. Regenerate:
<code>python scripts/dashboard.py</code></p>

<h2>The funnel — latest scan</h2>
<div class="card">{funnel_html}{fail_html}</div>

<h2>Sync Rate</h2>
<div class="card">{sync_html}</div>

<h2>The rulebook — every rule traceable, struck rules stay visible</h2>
<div class="card">{rules_html}</div>

<h2>Decision log — every decided proposal</h2>
<div class="card"><table>
<tr><th>id</th><th>decided (UTC)</th><th>symbol</th><th>verdict</th><th>reason</th></tr>
{dec_html}</table></div>

<h2>Suppressions by rule — the packets that never were</h2>
<div class="card">{sup_html}
<p class="muted">Every suppression carries its named reason in
logs/suppressed.jsonl; vote failures name their dimensions in
logs/setups.jsonl.</p></div>

<footer>HANSEI · Binance Agent OS Mini Hackathon · MODE=PAPER · no
profitability claim — the metric is behaviour change, measured from
append-only logs.</footer>
</body></html>"""
    OUT.write_text(page, encoding="utf-8")
    print(f"written: {OUT} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(build())

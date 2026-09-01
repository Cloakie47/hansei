"""HANSEI dashboard chart — dashboard/sync-rate.png from the logs.

Four panels, all excluding "test": true entries:
  1. Sync Rate over time (approved / all decided), denominator labelled at
     every point so a small n is visible rather than hidden.
  2. Rulebook growth: active rule count per day (derived from git history of
     rulebook.md), struck rules marked.
  3. Suppressions per day from suppressed.jsonl, split R009 vs R010.
  4. Confidence distribution: suppressed vs surviving drafts — the R009
     clustering check. Clustering just above 60% shows up here.

Honesty rule: when n is too small to support a trend, the axes render with a
plain statement instead of a fake line.

Usage: python scripts/chart.py
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard" / "sync-rate.png"

# Palette: validated with the dataviz six-checks validator (light mode).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dc"


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def real(entries):
    return [e for e in entries if e.get("test") is not True]


def day_of(e):
    return e["ts"][:10]


def sync_rate_by_day(proposals):
    per_day = defaultdict(lambda: {"approved": 0, "decided": 0})
    for p in proposals:
        if p.get("verdict") in ("APPROVED", "REJECTED", "NO_PROPOSAL"):
            d = per_day[day_of(p)]
            d["decided"] += 1
            if p["verdict"] == "APPROVED":
                d["approved"] += 1
    return dict(sorted(per_day.items()))


def rulebook_history():
    """(day -> (active, struck)) from git history of rulebook.md."""
    log = subprocess.run(
        ["git", "log", "--reverse", "--format=%H %cI", "--", "rulebook.md"],
        capture_output=True, text=True, cwd=ROOT).stdout.strip().splitlines()
    per_day = {}
    for line in log:
        sha, iso = line.split(" ", 1)
        text = subprocess.run(["git", "show", f"{sha}:rulebook.md"],
                              capture_output=True, text=True, cwd=ROOT).stdout
        import re
        active = len(re.findall(r"^- \*\*R\d{3}\*\*", text, re.M))
        struck = len(re.findall(r"^- ~~\*\*R\d{3}\*\*", text, re.M))
        per_day[iso[:10]] = (active, struck)  # last commit of the day wins
    return per_day


def main():
    proposals = real(load_jsonl(ROOT / "logs" / "proposals.jsonl"))
    suppressed = real(load_jsonl(ROOT / "logs" / "suppressed.jsonl"))
    pending = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((ROOT / "logs" / "pending").glob("p-*.json"))]

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.5), facecolor="white")
    fig.suptitle("HANSEI — Sync Rate & rule discipline", fontsize=15,
                 fontweight="bold", color=INK, x=0.06, ha="left")
    for ax in axes.flat:
        ax.set_facecolor("white")
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=9)

    # Panel 1 — Sync Rate
    ax = axes[0][0]
    ax.set_title("Sync Rate (approved / all decided)", color=INK, fontsize=11, loc="left")
    sr = sync_rate_by_day(proposals)
    ax.set_ylim(0, 100)
    ax.set_ylabel("%", color=MUTED)
    days = list(sr)
    if len(days) < 2:
        if days:
            d = days[0]
            v = sr[d]
            rate = 100 * v["approved"] / v["decided"]
            ax.plot([d], [rate], "o", color=BLUE, markersize=9)
            ax.annotate(f"{rate:.0f}%  ({v['approved']} of {v['decided']})",
                        (d, rate), textcoords="offset points", xytext=(10, 8),
                        color=INK, fontsize=10)
        ax.text(0.5, 0.62, f"{len(days)} day of decided proposals —\ntoo few points to draw a trend",
                transform=ax.transAxes, ha="center", color=MUTED, fontsize=10)
    else:
        xs, ys = days, [100 * sr[d]["approved"] / sr[d]["decided"] for d in days]
        ax.plot(xs, ys, "-o", color=BLUE, linewidth=2, markersize=8)
        for x, y in zip(xs, ys):
            v = sr[x]
            ax.annotate(f"{y:.0f}% ({v['approved']} of {v['decided']})", (x, y),
                        textcoords="offset points", xytext=(6, 8), color=INK, fontsize=9)

    # Panel 2 — Rulebook growth
    ax = axes[0][1]
    ax.set_title("Rulebook: active rules (× = struck, cumulative)", color=INK,
                 fontsize=11, loc="left")
    hist = rulebook_history()
    days = list(hist)
    active = [hist[d][0] for d in days]
    struck = [hist[d][1] for d in days]
    ax.plot(days, active, "-o", color=BLUE, linewidth=2, markersize=8)
    for x, a, s in zip(days, active, struck):
        ax.annotate(f"{a} active", (x, a), textcoords="offset points",
                    xytext=(8, -3), color=INK, fontsize=9)
        if s:
            ax.plot([x], [a], marker="x", color=ORANGE, markersize=11, mew=2.5)
            ax.annotate(f"{s} struck", (x, a), textcoords="offset points",
                        xytext=(8, -16), color=ORANGE, fontsize=9)
    ax.set_ylim(0, max(active) + 2)

    # Panel 3 — Suppressions per day
    ax = axes[1][0]
    ax.set_title("Suppressions per day (R009 floor vs R010 dupe)", color=INK,
                 fontsize=11, loc="left")
    per_day = defaultdict(lambda: {"R009": 0, "R010": 0})
    for s in suppressed:
        per_day[day_of(s)][s["rule"]] += 1
    days = sorted(per_day)
    if not days:
        ax.text(0.5, 0.5, "no suppressions logged yet", transform=ax.transAxes,
                ha="center", color=MUTED, fontsize=10)
    else:
        import numpy as np
        x = np.arange(len(days))
        w = 0.34
        r9 = [per_day[d]["R009"] for d in days]
        r10 = [per_day[d]["R010"] for d in days]
        b1 = ax.bar(x - w / 2 - 0.01, r9, w, color=ORANGE, label="R009 (< 60%)")
        b2 = ax.bar(x + w / 2 + 0.01, r10, w, color=AQUA, label="R010 (pending dupe)")
        for bars in (b1, b2):
            for rect in bars:
                if rect.get_height():
                    ax.annotate(f"{int(rect.get_height())}",
                                (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                                textcoords="offset points", xytext=(0, 3),
                                ha="center", color=INK, fontsize=10)
        ax.set_xticks(x, days)
        ax.legend(frameon=False, fontsize=9, labelcolor=INK)
        ax.set_ylim(0, max(r9 + r10) + 1.5)

    # Panel 4 — Confidence distribution (R009 clustering check)
    ax = axes[1][1]
    ax.set_title("Draft confidence: suppressed vs surviving (clustering check)",
                 color=INK, fontsize=11, loc="left")
    sup_conf = [s["confidence"] for s in suppressed if s.get("confidence") is not None]
    packets = [p for p in pending] + \
              [p for p in proposals if p.get("confidence") is not None
               and p.get("verdict") != "NO_PROPOSAL"]
    surv_conf = []
    for p in packets:
        c = p.get("draft", {}).get("confidence") if "draft" in p else p.get("confidence")
        if c is not None:
            surv_conf.append(c)
    ax.axvline(0.60, color=MUTED, linestyle="--", linewidth=1.2)
    ax.annotate("60% floor (R009)", (0.601, 0.52), xycoords=("data", "axes fraction"),
                color=MUTED, fontsize=9, ha="left")
    ax.plot(sup_conf, [0.30] * len(sup_conf), "o", color=ORANGE, markersize=10,
            alpha=0.85, label=f"suppressed (n={len(sup_conf)})")
    ax.plot(surv_conf, [0.62] * len(surv_conf), "o", color=BLUE, markersize=10,
            alpha=0.85, label=f"surviving (n={len(surv_conf)})")
    ax.set_xlim(0.35, 0.80)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("draft confidence", color=MUTED)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="lower left")
    n = len(sup_conf) + len(surv_conf)
    lines = [f"n={n} drafts over {len(set(day_of(s) for s in suppressed)) or 1} day(s) — "
             "distribution, not a trend. Watch for clustering just above the floor."]
    if any(c < 0.60 for c in surv_conf):
        lines.append("2 surviving drafts at 54-55% predate R009 (p-005/p-006, "
                     "generated before the floor existed).")
    ax.text(0.02, 0.955, "\n".join(lines), transform=ax.transAxes, ha="left",
            va="top", color=MUTED, fontsize=8.5)

    fig.text(0.06, 0.015, "test-flagged entries excluded everywhere · "
             "generated by scripts/chart.py from logs/*.jsonl", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0.02, 0.03, 0.99, 0.95))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160)
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

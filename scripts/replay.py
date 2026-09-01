"""HANSEI replay mode — build-order step 7. Drill the decision loop on
historical data with symbols anonymised and dates hidden, so the Pilot can
practise verdicts and the pair (Unit, Pilot) can accumulate agreement data
without waiting for live confluence.

STRICT SEPARATION: everything lives under logs/replay/. Replay decisions are
flagged "replay": true and NEVER touch logs/proposals.jsonl, Sync Rate, or
calibration for the live system. This is a drill range, not the range.

Sources: historical order books do not exist, so replay evidence is A
(cross-sectional over the replay universe) and B (time series) only — two
structurally independent sources, satisfying R007. Confidence note, stated
loudly: with only two sources AVAILABLE, full 2-of-2 confluence maps to
0.62 (the same "everything available fired" tier that 3-of-3 maps to in
live scanning); 1-of-2 maps to 0.57 and is suppressed by the same 60%
floor. Live gates and live mappings are untouched.

Look-ahead caveat, disclosed: the replay universe is today's floor-passing
pairs, which biases toward what is liquid NOW, not at T. Acceptable for a
decision drill; not usable for strategy backtesting claims.

Commands:
  replay.py new [--days-ago N] [--seed S]   build a session, render packets
  replay.py pending                          list undecided replay packets
  replay.py verdict <rid> <y|n> [code]       log decision, then REVEAL outcome
  replay.py stats                            drill stats: approval rate, hit rates
"""

import json
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as scanmod

ROOT = HERE.parent
RDIR = ROOT / "logs" / "replay"
SESSIONS = RDIR / "sessions"
RPACKETS = RDIR / "packets"
DECISIONS = RDIR / "decisions.jsonl"

CONF_FULL, CONF_PARTIAL = 0.62, 0.57
FLOOR = 0.60
DEEP = 8

VALID_CODES = {"SIZE", "TIMING", "CONVICTION", "RISK", "DUPLICATE", "ASSET", "OTHER"}


def get(path, **params):
    url = f"https://api.binance.com/api/v3/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def klines_window(symbol, t_ms):
    start = t_ms - 7 * 86_400_000
    end = t_ms + 24 * 3_600_000
    return get("klines", symbol=symbol, interval="1h",
               startTime=start, endTime=end, limit=200)


def analyse(symbol, t_ms):
    """A+B features at time T plus the hidden outcome after T."""
    ks = klines_window(symbol, t_ms)
    past = [k for k in ks if k[6] <= t_ms]     # candles closed by T
    future = [k for k in ks if k[0] >= t_ms]
    if len(past) < 48 or len(future) < 6:
        return None
    closes = [float(k[4]) for k in past]
    qvols = [float(k[7]) for k in past]
    last = closes[-1]
    chg24 = (last / closes[-25] - 1) * 100 if len(closes) >= 25 else 0
    vol24 = sum(qvols[-24:])
    prior_daily = sum(qvols[:-24]) / max((len(qvols) - 24) / 24, 1)
    vol_ratio = vol24 / prior_daily if prior_daily else None
    lo = min(float(k[3]) for k in past)
    hi = max(float(k[2]) for k in past)
    range_pos = (last - lo) / (hi - lo) if hi > lo else 0.5
    daily_chgs = []
    for i in range(24, len(closes), 24):
        daily_chgs.append(abs(closes[i] / closes[i - 24] - 1) * 100)
    chg_thr = max(2.5, 1.6 * (sum(daily_chgs) / len(daily_chgs))) if daily_chgs else 4.0
    body = abs(float(past[-1][4]) - float(past[-1][1]))
    prior_bodies = [abs(float(k[4]) - float(k[1])) for k in past[-25:-1]]
    body_ratio = body / (sum(prior_bodies) / len(prior_bodies)) if prior_bodies else None

    a_trig = [t for t, ok in (("chg", abs(chg24) >= chg_thr),
                              ("vol", vol_ratio is not None and vol_ratio >= scanmod.A_VOL_RATIO)) if ok]
    b_trig = [t for t, ok in (("range-edge", range_pos <= 0.15 or range_pos >= 0.85),
                              ("vol-expand", vol_ratio is not None and vol_ratio >= scanmod.B_VOL_EXPAND),
                              ("candle", body_ratio is not None and body_ratio >= 2.0)) if ok]
    fut_closes = [float(k[4]) for k in future[:25]]
    outcome = {
        "chg_6h_pct": (fut_closes[6] / last - 1) * 100 if len(fut_closes) > 6 else None,
        "chg_24h_pct": (fut_closes[-1] / last - 1) * 100,
        "max_gain_pct": (max(float(k[2]) for k in future[:25]) / last - 1) * 100,
        "max_drawdown_pct": (min(float(k[3]) for k in future[:25]) / last - 1) * 100,
    }
    return {"symbol": symbol, "last": last, "chg24_pct": chg24, "chg_thr": chg_thr,
            "vol_ratio": vol_ratio, "range_pos": range_pos, "body_ratio": body_ratio,
            "a_trig": a_trig, "b_trig": b_trig, "vol24_usdt": vol24,
            "outcome": outcome}


def render(rid, alias, f, conf):
    lines = [
        f"━━━ REPLAY PACKET {rid} ━━━  (DRILL — historical, anonymised, not a live proposal)",
        "",
        f"PROPOSAL   BUY [stake] USDT of {alias} (spot, market)",
        f"CONFIDENCE {conf:.0%}  (2-of-2 available sources; C has no history)",
        f"THESIS     {alias} moved {f['chg24_pct']:+.2f}% in its trailing 24h "
        f"(own-volatility threshold {f['chg_thr']:.1f}%), 24h volume "
        f"{(f['vol_ratio'] or 0):.2f}x its prior average, sitting at "
        f"{f['range_pos']:.0%} of its 7-day range.",
        "",
        "EVIDENCE",
        f"  • [A] cross-sectional -> 24h {f['chg24_pct']:+.2f}% vs threshold "
        f"{f['chg_thr']:.1f}%; volume {(f['vol_ratio'] or 0):.2f}x prior avg "
        f"({f['vol24_usdt']/1e6:.1f}m USDT); triggers: {f['a_trig']}",
        f"  • [B] time series -> {f['range_pos']:.0%} of 7d range; current candle "
        f"body {f['body_ratio']:.2f}x prior 24 avg; triggers: {f['b_trig']}",
        "  • [C] unavailable in replay (no historical order book)",
        "",
        "INVALIDATION",
        "  The triggering excursion reversing within 24h: change sign flip or",
        "  volume back under 1x average.",
        "",
        f"━━━ Pilot: python scripts/replay.py verdict {rid} y|n [code] ━━━",
    ]
    RPACKETS.mkdir(parents=True, exist_ok=True)
    path = RPACKETS / f"{rid}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_new(args):
    days = int(args[args.index("--days-ago") + 1]) if "--days-ago" in args else 30
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 1
    rng = random.Random(seed)
    t_ms = int((datetime.now(timezone.utc) - timedelta(days=days))
               .replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
    sid = f"s{days}d{seed}"
    pairs, _ = scanmod.active_usdt_pairs()
    tickers = get("ticker/24hr")
    universe = sorted((t["symbol"] for t in tickers
                       if t["symbol"] in pairs and float(t["quoteVolume"]) >= scanmod.VOLUME_FLOOR))
    print(f"replay universe: {len(universe)} pairs (today's floor-passers — "
          "look-ahead caveat applies, see file header)")
    feats = []
    for sym in universe:
        try:
            f = analyse(sym, t_ms)
        except Exception:
            f = None
        if f:
            feats.append(f)
    feats.sort(key=lambda f: abs(f["chg24_pct"]) / f["chg_thr"], reverse=True)
    aliases = [f"SYM-{i:02d}" for i in range(1, len(feats) + 1)]
    rng.shuffle(aliases)
    session = {"sid": sid, "t_ms": t_ms, "days_ago": days, "seed": seed,
               "packets": {}, "mapping": {}}
    n_pack = 0
    for f, alias in zip(feats[:DEEP], aliases):
        full = bool(f["a_trig"]) and bool(f["b_trig"])
        conf = CONF_FULL if full else CONF_PARTIAL
        if conf < FLOOR:
            continue
        n_pack += 1
        rid = f"r-{sid}-{n_pack:02d}"
        path = render(rid, alias, f, conf)
        session["packets"][rid] = {"alias": alias, "confidence": conf,
                                   "features": {k: f[k] for k in
                                                ("chg24_pct", "vol_ratio", "range_pos", "chg_thr")},
                                   "outcome": f["outcome"]}
        session["mapping"][rid] = f["symbol"]
        print(f"  {rid}: {alias}  ({path})")
    SESSIONS.mkdir(parents=True, exist_ok=True)
    (SESSIONS / f"{sid}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    print(f"session {sid}: {n_pack} replay packets from {len(feats)} analysed pairs. "
          f"Decide with: python scripts/replay.py verdict <rid> y|n [code]")
    if n_pack == 0:
        print("(quiet historical window — try another --days-ago)")
    return 0


def _load_sessions():
    out = {}
    if SESSIONS.exists():
        for p in SESSIONS.glob("s*.json"):
            s = json.loads(p.read_text(encoding="utf-8"))
            out[s["sid"]] = s
    return out


def _decided_rids():
    if not DECISIONS.exists():
        return set()
    return {json.loads(l)["rid"] for l in DECISIONS.read_text(encoding="utf-8").splitlines() if l.strip()}


def cmd_pending():
    done = _decided_rids()
    n = 0
    for s in _load_sessions().values():
        for rid, p in s["packets"].items():
            if rid not in done:
                print(f"{rid}  {p['alias']}  BUY  {p['confidence']:.0%}  ({RPACKETS / (rid + '.txt')})")
                n += 1
    if not n:
        print("no pending replay packets — create a session: python scripts/replay.py new --days-ago N")
    return 0


def cmd_verdict(args):
    rid, yn = args[0], args[1].lower()
    code = args[2].upper() if len(args) > 2 else None
    if yn == "n" and code not in VALID_CODES:
        print(f"rejection needs a code from {sorted(VALID_CODES)}")
        return 1
    if yn == "y" and code is not None:
        print("approval takes no code")
        return 1
    if rid in _decided_rids():
        print(f"{rid} already decided")
        return 1
    for s in _load_sessions().values():
        if rid in s["packets"]:
            p = s["packets"][rid]
            entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "replay": True, "rid": rid, "sid": s["sid"],
                     "symbol": s["mapping"][rid], "confidence": p["confidence"],
                     "verdict": "APPROVED" if yn == "y" else "REJECTED",
                     "reject_reason": code}
            with open(DECISIONS, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ": ")) + "\n")
            o = p["outcome"]
            print(f"logged: {rid} {entry['verdict']}" + (f" ({code})" if code else ""))
            print(f"REVEAL: {p['alias']} was {s['mapping'][rid]}, "
                  f"T = {datetime.fromtimestamp(s['t_ms']/1000, tz=timezone.utc):%Y-%m-%d %H:%M} UTC "
                  f"({s['days_ago']}d ago)")
            print(f"  outcome after T: +6h {o['chg_6h_pct']:+.2f}% | +24h {o['chg_24h_pct']:+.2f}% | "
                  f"best {o['max_gain_pct']:+.2f}% | worst {o['max_drawdown_pct']:+.2f}%")
            return 0
    print(f"unknown rid {rid}")
    return 1


def cmd_stats():
    if not DECISIONS.exists():
        print("no replay decisions yet")
        return 0
    rows = [json.loads(l) for l in DECISIONS.read_text(encoding="utf-8").splitlines() if l.strip()]
    sessions = _load_sessions()
    for r in rows:
        r["outcome"] = sessions[r["sid"]]["packets"][r["rid"]]["outcome"]
    app = [r for r in rows if r["verdict"] == "APPROVED"]
    rej = [r for r in rows if r["verdict"] == "REJECTED"]
    print(f"replay decisions: {len(rows)} (approved {len(app)}, rejected {len(rej)}) — "
          f"drill data, never mixed into live Sync Rate")
    def mean24(rs):
        vals = [r["outcome"]["chg_24h_pct"] for r in rs if r["outcome"]["chg_24h_pct"] is not None]
        return sum(vals) / len(vals) if vals else None
    if app:
        print(f"approved: mean +24h outcome {mean24(app):+.2f}% | "
              f"hit rate (positive 24h): {sum(1 for r in app if r['outcome']['chg_24h_pct'] > 0)}/{len(app)}")
    if rej:
        print(f"rejected: mean +24h outcome {mean24(rej):+.2f}% (what was passed on)")
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "new":
        return cmd_new(argv[2:])
    if cmd == "pending":
        return cmd_pending()
    if cmd == "verdict":
        return cmd_verdict(argv[2:])
    if cmd == "stats":
        return cmd_stats()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

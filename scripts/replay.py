"""HANSEI replay mode, build-order step 7. Drill the decision loop on
historical data with symbols anonymised and dates hidden, so the Pilot can
practise verdicts and the pair (Unit, Pilot) can accumulate agreement data
without waiting for live confluence.

STRICT SEPARATION: everything lives under logs/replay/. Replay decisions are
flagged "replay": true and NEVER touch logs/proposals.jsonl, Sync Rate, or
calibration for the live system. This is a drill range, not the range.

Sources: historical order books do not exist, so replay evidence is A
(cross-sectional over the replay universe) and B (time series) only, two
structurally independent sources, satisfying R007. Confidence note, stated
loudly: with only two sources AVAILABLE, full 2-of-2 confluence maps to
0.62 (the same "everything available fired" tier that 3-of-3 maps to in
live scanning); 1-of-2 maps to 0.57 and is suppressed by the same 60%
floor. Live gates and live mappings are untouched.

Look-ahead caveat, disclosed: the replay universe is today's floor-passing
pairs, which biases toward what is liquid NOW, not at T. Acceptable for a
decision drill; not usable for strategy backtesting claims.

CALIBRATION CAVEAT (Pilot-directed, 2026-09-02): drills carry A+B evidence
only, there is no order-book history, so replay verdicts calibrate the
Pilot on TWO-SOURCE evidence while live packets carry three sources. Replay
outcomes MUST NOT be used to retune live confidence weights without
adjusting for the missing C source: a weight fitted on A+B-only data has
never seen the imbalance/spread terms and would misprice them. Replay stats
prints this warning; treat replay hit rates as drill feedback, not as
calibration input for confidence_v2's C-dependent terms.

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


def daily_structure(symbol, t_ms):
    """Daily-kline structure at T for the setup classifier (same fields the
    live scanner computes)."""
    start = t_ms - 95 * 86_400_000
    daily = get("klines", symbol=symbol, interval="1d",
                startTime=start, endTime=t_ms, limit=100)
    daily = [k for k in daily if k[6] <= t_ms]
    if len(daily) < 25:
        return None
    closes = [float(k[4]) for k in daily]
    chgs = [abs(float(k[4]) / float(k[1]) - 1) * 100 for k in daily[-8:-1] if float(k[1])]
    avg = (min(sum(chgs) / len(chgs), scanmod.AVG_DAILY_CAP) if chgs else None)
    avg_raw = sum(chgs) / len(chgs) if chgs else None
    window = daily[-10:-2]
    return {
        "sma20": sum(closes[-20:]) / 20,
        "sma20_prev5": sum(closes[-25:-5]) / 20,
        "sma20_rising": sum(closes[-20:]) / 20 > sum(closes[-25:-5]) / 20,
        "chg_3d_pct": (closes[-1] / closes[-4] - 1) * 100,
        "chg_5d_pct": (closes[-1] / closes[-6] - 1) * 100,
        "avg_abs_daily_pct": avg,
        "avg_abs_daily_raw_pct": avg_raw,
        "consol_high": max(float(k[2]) for k in window),
        "consol_low": min(float(k[3]) for k in window),
        "_daily": daily, # for the R015 dimensions
    }


_BTC_CACHE = {}


def _btc_closes_at(t_ms):
    if t_ms not in _BTC_CACHE:
        btc_daily = get("klines", symbol="BTCUSDT", interval="1d",
                        startTime=t_ms - 95 * 86_400_000, endTime=t_ms, limit=100)
        _BTC_CACHE[t_ms] = [float(k[4]) for k in btc_daily if k[6] <= t_ms]
    return _BTC_CACHE[t_ms]


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
    chg_thr = (max(2.5, 1.6 * min(sum(daily_chgs) / len(daily_chgs),
                                   scanmod.AVG_DAILY_CAP)) if daily_chgs else 4.0)
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
    # Current-spec additions: setup classification + structural R:R + v3
    # confidence, matching what the live system proposes (A+B only, no
    # order-book history, so C-dependent v3 terms simply contribute zero).
    ds = daily_structure(symbol, t_ms)
    lo7 = min(float(k[3]) for k in past[-168:])
    hi7 = max(float(k[2]) for k in past[-168:])
    swing_low_48h = min(float(k[3]) for k in past[-48:])
    setup, setup_detail, rr, v3, vote = "UNCLASSIFIED", "insufficient daily history", None, None, None
    if ds:
        row = dict(ds, chg_pct=chg24)
        b_like = {"range_pos": range_pos, "last": last, "vol_expand": vol_ratio,
                  "body_ratio": body_ratio, "hi_7d": hi7, "lo_7d": lo7,
                  "swing_low_48h": swing_low_48h}
        setup, setup_detail = scanmod.classify_setup(row, b_like)
        if setup not in ("CHASE", "UNCLASSIFIED"):
            rr, _rr_refusal = scanmod.risk_reward(row, b_like, setup)
            # R015 vote at T (final spec), VWAP proxied from the last 24 1h
            # candles' quote/base volume at T
            base_vol24 = sum(float(k[5]) for k in past[-24:])
            vwap24 = (vol24 / base_vol24) if base_vol24 else last
            vwap_dist = (last - vwap24) / vwap24 * 100
            btc_closes = _btc_closes_at(t_ms)
            dims = scanmod.compute_dimensions(ds["_daily"], btc_closes, vwap_dist)
            vote = scanmod.setup_vote(setup, dims)
            import run as runmod
            # families, not sources: 'vol' (A) and 'vol-expand' (B) are the
            # same quantity and count once (2026-09-02 fix)
            n_avail = scanmod.independent_source_count({"A": a_trig, "B": b_trig})
            metrics = {"vol_ratio_7d": vol_ratio, "vol_expand": vol_ratio,
                       "imbalance": None, "aligned": None, "spread_bps": None,
                       "chg24": chg24}
            structure = dict(ds, last=last, range_pos=range_pos, vol_expand=vol_ratio,
                             body_ratio=body_ratio)
            structure.pop("_daily", None)
            v3 = runmod.confidence_v3(setup, n_avail, metrics, structure,
                                      rr["rr"] if rr else None)
    return {"symbol": symbol, "last": last, "chg24_pct": chg24, "chg_thr": chg_thr,
            "vol_ratio": vol_ratio, "range_pos": range_pos, "body_ratio": body_ratio,
            "a_trig": a_trig, "b_trig": b_trig, "vol24_usdt": vol24,
            "setup": setup, "setup_detail": setup_detail,
            "rr": rr, "v3": v3, "vote": vote,
            "outcome": outcome}


def render(rid, alias, f, conf, blind=False):
    # blind=True (mixed calibration sessions): drop the SETUP and R:R lines,
    # they encode the live system's own verdict and would give away
    # good-vs-bad. The Pilot judges the raw A/B evidence, which is exactly
    # the "modest up-move, elevated volume, upper range" shape whose
    # approval the drill is meant to test.
    rr = f.get("rr")
    head = [
        f"━━━ REPLAY PACKET {rid} ━━━  (DRILL, historical, anonymised, not a live proposal)",
        "",
        f"PROPOSAL   BUY [stake] USDT of {alias} (spot, market)",
        f"CONFIDENCE {conf:.0%}  (v3, A+B evidence only, C-dependent terms zero, no book history)",
    ]
    if not blind:
        head.append(f"SETUP      {f.get('setup')}, {f.get('setup_detail', '')}")
        if rr:
            head.append(f"R:R        {rr['rr']:.1f} : 1 (target {rr['target']:g}, "
                        f"stop {rr['stop']:g}, entry ref {rr['entry']:g})")
    lines = head + [
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
        f"  Structural stop at {rr['stop']:g} (48h swing low); the setup's own "
        "reversal conditions apply." if rr else
        "  The triggering excursion reversing within 24h.",
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
    sid = f"s{days}d{seed}v3"
    pairs, _ = scanmod.active_usdt_pairs()
    tickers = get("ticker/24hr")
    universe = sorted((t["symbol"] for t in tickers
                       if t["symbol"] in pairs and float(t["quoteVolume"]) >= scanmod.VOLUME_FLOOR))
    print(f"replay universe: {len(universe)} pairs (today's floor-passers, "
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
               "spec": "classifier-v3", # current-spec drills; older sessions lack this
               "packets": {}, "mapping": {}}
    n_pack = 0
    for f, alias in zip(feats[:DEEP], aliases):
        # Current-spec gates, mirroring live: classified setup, both available
        # sources triggering, structural R:R >= 2 (R014), v3 conf >= floor.
        if f.get("setup") in ("CHASE", "UNCLASSIFIED"):
            continue
        # Final spec: the R015 vote replaces the source-trigger gate
        if not (f.get("vote") and f["vote"]["pass"]):
            continue
        if not f.get("rr") or f["rr"]["rr"] < 2.0:
            continue
        conf = f.get("v3") or CONF_PARTIAL
        if conf < FLOOR:
            continue
        n_pack += 1
        rid = f"r-{sid}-{n_pack:02d}"
        path = render(rid, alias, f, conf)
        session["packets"][rid] = {"alias": alias, "confidence": conf,
                                   "setup": f["setup"],
                                   "rr": round(f["rr"]["rr"], 2),
                                   "features": {k: f[k] for k in
                                                ("chg24_pct", "vol_ratio", "range_pos", "chg_thr")},
                                   "outcome": f["outcome"]}
        session["mapping"][rid] = f["symbol"]
        print(f"  {rid}: {alias}  {f['setup']} rr={f['rr']['rr']:.2f} v3={conf:.3f}  ({path})")
    SESSIONS.mkdir(parents=True, exist_ok=True)
    (SESSIONS / f"{sid}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    print(f"session {sid}: {n_pack} replay packets from {len(feats)} analysed pairs. "
          f"Decide with: python scripts/replay.py verdict <rid> y|n [code]")
    if n_pack == 0:
        print("(quiet historical window, try another --days-ago)")
    return 0


def cmd_mixed(args):
    """Blind calibration session with a DELIBERATE quality mix, genuine
    setups AND chase-shaped candidates, drawn from several real historical
    windows. Unlike `new`, it does NOT gate on the full spec: the point is
    to give the Pilot rejections to make, so the drill stats mean something.
    Each packet stores the live system's own verdict (would_pass + why) as
    hidden ground truth for later comparison; the packet the Pilot sees is
    blind. Renders in the same format as `new` so it is indistinguishable.

    Selection per window: the single best full-gate passer (if any) plus the
    highest-ranked CHASE/vote-fail candidate, a matched good/bad pair, so
    the session is genuinely mixed by construction, not by luck."""
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 42
    windows = [int(x) for x in args[args.index("--windows") + 1].split(",")] \
        if "--windows" in args else [22, 34, 51]
    rng = random.Random(seed)
    sid = f"mix{seed}"
    session = {"sid": sid, "seed": seed, "spec": "classifier-v3-mixed",
               "windows": windows, "packets": {}, "mapping": {}, "t_by_rid": {}}
    goods, bads = [], []
    pairs, _ = scanmod.active_usdt_pairs()
    for days in windows:
        t_ms = int((datetime.now(timezone.utc) - timedelta(days=days))
                   .replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
        tickers = get("ticker/24hr")
        universe = sorted(t["symbol"] for t in tickers
                          if t["symbol"] in pairs
                          and float(t["quoteVolume"]) >= scanmod.VOLUME_FLOOR)
        feats = []
        for sym in universe:
            try:
                f = analyse(sym, t_ms)
            except Exception:
                f = None
            if f:
                feats.append(f)
        feats.sort(key=lambda f: abs(f["chg24_pct"]) / f["chg_thr"], reverse=True)
        good = next((f for f in feats
                     if f.get("setup") not in ("CHASE", "UNCLASSIFIED")
                     and f.get("vote") and f["vote"]["pass"]
                     and f.get("rr") and f["rr"]["rr"] >= 2.0
                     and (f.get("v3") or 0) >= FLOOR), None)
        bad = next((f for f in feats
                    if f.get("setup") == "CHASE"
                    or (f.get("setup") not in ("UNCLASSIFIED",)
                        and f.get("vote") and not f["vote"]["pass"])), None)
        if good:
            goods.append((good, t_ms, "would-pass"))
        if bad and bad is not good:
            bads.append((bad, t_ms, "would-reject"))
    # Guarantee a genuine mix: take up to 2 goods (if any exist), fill the
    # rest with bads to 6, then shuffle so order reveals nothing. An all-one-
    # kind set is a broken drill, so goods are included deliberately, not by
    # luck of the shuffle.
    rng.shuffle(goods)
    rng.shuffle(bads)
    picks = goods[:2] + bads[:6 - min(len(goods), 2)]
    rng.shuffle(picks)
    aliases = [f"SYM-{i:02d}" for i in range(1, len(picks) + 20)]
    rng.shuffle(aliases)
    n = 0
    for (f, t_ms, kind), alias in zip(picks[:6], aliases):
        n += 1
        rid = f"r-{sid}-{n:02d}"
        conf = f.get("v3") or CONF_PARTIAL
        render(rid, alias, f, conf, blind=True)
        session["packets"][rid] = {
            "alias": alias, "confidence": conf, "setup": f.get("setup"),
            "rr": round(f["rr"]["rr"], 2) if f.get("rr") else None,
            "ground_truth": kind,
            "live_verdict": ("would_pass_all_gates" if kind == "would-pass"
                             else f"live system BLOCKS: {f.get('setup')}"
                             + (f", vote {f['vote']['n_pass']}/{f['vote']['need']}"
                                if f.get("vote") else "")),
            "outcome": f["outcome"]}
        session["mapping"][rid] = f["symbol"]
        session["t_by_rid"][rid] = t_ms
    SESSIONS.mkdir(parents=True, exist_ok=True)
    (SESSIONS / f"{sid}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    # Do NOT print the pass/reject breakdown: that ratio is aggregate ground
    # truth and leaks information about the blind set. Only the count and the
    # rids are printed; the mix stays sealed in the session file.
    print(f"mixed session {sid}: {n} BLIND packets from {len(windows)} real "
          f"windows. Ground truth (which the live system would pass or reject) "
          f"is sealed in the session file and printed to no one. Decide blind:")
    for rid in session["packets"]:
        print(f"  python scripts/replay.py verdict {rid} y|n [code]   "
              f"({RPACKETS / (rid + '.txt')})")
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
        if s.get("retired"):
            continue  # documented catches, not drills
        tag = "" if s.get("spec") == "classifier-v3" else "  [PRE-CLASSIFIER SPEC, old evidence format]"
        blind = s.get("spec") == "classifier-v3-mixed"
        for rid, p in s["packets"].items():
            if rid not in done:
                # mixed sessions stay blind: no setup/rr leak in the listing
                extra = "" if blind else (f"  {p['setup']} rr={p['rr']}" if p.get("setup") else "")
                mixtag = "  [BLIND MIXED, no setup shown]" if blind else tag
                print(f"{rid}  {p['alias']}  BUY  {p['confidence']:.0%}{extra}  "
                      f"({RPACKETS / (rid + '.txt')}){mixtag}")
                n += 1
    if not n:
        print("no pending replay packets, create a session: python scripts/replay.py new --days-ago N")
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
            if s.get("retired"):
                print(f"{rid} is RETIRED, {s['retired'][:120]}...")
                return 1
            p = s["packets"][rid]
            entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "replay": True, "rid": rid, "sid": s["sid"],
                     "symbol": s["mapping"][rid], "confidence": p["confidence"],
                     "verdict": "APPROVED" if yn == "y" else "REJECTED",
                     "reject_reason": code}
            with open(DECISIONS, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ": ")) + "\n")
            o = p["outcome"]
            t_ms = s.get("t_by_rid", {}).get(rid, s.get("t_ms"))
            when = (datetime.fromtimestamp(t_ms/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                    if t_ms else "unknown")
            print(f"logged: {rid} {entry['verdict']}" + (f" ({code})" if code else ""))
            print(f"REVEAL: {p['alias']} was {s['mapping'][rid]}, T = {when} UTC")
            if p.get("live_verdict"):
                print(f"  live system would have: {p['live_verdict']} "
                      f"(ground truth: {p.get('ground_truth')})")
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
    print(f"replay decisions: {len(rows)} (approved {len(app)}, rejected {len(rej)}), "
          f"drill data, never mixed into live Sync Rate")
    print("CAVEAT: A+B evidence only (no order-book history). Do not retune live "
          "confidence weights from these outcomes without adjusting for the "
          "missing C source: see the header of scripts/replay.py.")
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
    if cmd == "mixed":
        return cmd_mixed(argv[2:])
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

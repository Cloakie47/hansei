"""HANSEI decision packet generator.

Spec: prompts/decision-packet.md. This module owns the deterministic half:
rule parsing, pre-flight checks, id allocation, packet rendering, and the
proposals.jsonl log. The Unit (Claude, in-session) supplies the trade idea
as a draft JSON and performs the MCP fetches, because MCP tools are only
callable inside the session.

Session flow:
  0. Claude fetches live market data and spot_getAccount, saves both as JSON.
  1. python scripts/propose.py packet <draft.json> <market.json> <account.json>
       -> parses active rules from rulebook.md (struck ~~rules~~ ignored)
       -> reads the last 10 non-test entries of logs/proposals.jsonl
       -> runs the affordability pre-flight from place.py
       -> checks the draft against EVERY active rule; any BLOCKED rule means
          no packet is printed — the blocked rule prints instead, exit 2
       -> otherwise renders the packet exactly per the spec, and saves the
          pending proposal to logs/pending/<id>.json for the verdict step
  2. python scripts/propose.py verdict <id> <APPROVED|REJECTED> [code] [note]
       -> record_verdict(): appends the full schema line to logs/proposals.jsonl.
          Reject codes limited to SIZE/TIMING/CONVICTION/RISK/DUPLICATE/ASSET/
          OTHER; anything else is refused. Pass --test to mark a pipeline test.
  3. python scripts/propose.py no-proposal "<reason>"
       -> the real "No proposal today." code path: prints it and logs a
          proposal with verdict NO_PROPOSAL so Debrief metrics count it.

In-process entry point: generate_packet(invoke, draft) — invoke is the
session-side MCP caller, used for spot_ticker24hr and spot_getAccount.

Draft JSON fields: symbol, side, type (MARKET/LIMIT), quoteOrderQty or
price+quantity, confidence (0-1), thesis, evidence (list of strings),
signals_used (list), invalidation, size_reasoning, optional material_change.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import place  # affordability_check, proposal_notional_usdt, append_jsonl, now_iso

ROOT = Path(__file__).resolve().parent.parent
RULEBOOK = ROOT / "rulebook.md"
PROPOSALS_LOG = ROOT / "logs" / "proposals.jsonl"
PENDING_DIR = ROOT / "logs" / "pending"
APPROVED_DIR = ROOT / "logs" / "approved"  # drafts preserved for placement
PACKETS_DIR = ROOT / "packets"
SUPPRESSED_LOG = ROOT / "logs" / "suppressed.jsonl"

# R009 hard floor: below this a draft is suppressed to NO_PROPOSAL and logged.
# The suppression log exists so confidence clustering just above the floor is
# visible — a hard floor invites 61% nudging, and the log is how we catch it.
CONFIDENCE_FLOOR = 0.60
LOW_CONVICTION = CONFIDENCE_FLOOR  # packet flag threshold (for >=60% packets)


def log_suppressed(rule, draft, reason):
    entry = {
        "ts": place.now_iso(),
        "rule": rule,
        "symbol": draft.get("symbol"),
        "side": draft.get("side"),
        "confidence": draft.get("confidence"),
        "evidence_sources": sorted(evidence_sources(draft)),
        "reason": reason,
    }
    rr = draft.get("rr")
    if rr and rr.get("rr") is not None:
        entry["rr"] = round(rr["rr"], 3)  # near-misses stay visible
    if draft.get("setup"):
        entry["setup"] = draft["setup"]
    place.append_jsonl(SUPPRESSED_LOG, entry)


def pending_clash(symbol, side):
    """R010: the id of a PENDING packet with the same symbol+side, or None."""
    if PENDING_DIR.exists():
        for p in sorted(PENDING_DIR.glob("p-*.json")):
            d = json.loads(p.read_text(encoding="utf-8")).get("draft", {})
            if d.get("symbol") == symbol and d.get("side") == side:
                return p.stem
    return None

VALID_VERDICTS = {"APPROVED", "REJECTED", "NO_PROPOSAL"}
VALID_REJECT_CODES = {"SIZE", "TIMING", "CONVICTION", "RISK", "DUPLICATE", "ASSET", "OTHER"}

# Maintained by hand; R002 says anything outside this set needs query-token-audit.
TOP_20_BASES = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "AVAX", "LINK",
    "DOT", "TON", "LTC", "BCH", "XLM", "UNI", "ATOM", "NEAR", "ETC", "SUI",
}

BAR = "━" * 3  # ━━━
BULLET = "•"   # •

RULE_RE = re.compile(r"^- \*\*(R\d{3})\*\* (.*)$")


def parse_active_rules(text=None):
    """Rules from rulebook.md as [{id, text}], continuation lines joined.
    Any bullet containing ~~ is struck through and ignored."""
    if text is None:
        text = RULEBOOK.read_text(encoding="utf-8")
    rules, current = [], None
    for line in text.splitlines():
        m = RULE_RE.match(line)
        if m:
            current = {"id": m.group(1), "text": m.group(2).strip(), "struck": "~~" in line}
            rules.append(current)
        elif current and line.startswith("  ") and line.strip():
            current["text"] += " " + line.strip()
            if "~~" in line:
                current["struck"] = True
        else:
            current = None
    return [{"id": r["id"], "text": r["text"]} for r in rules if not r["struck"]]


def load_proposals(include_test=False):
    if not PROPOSALS_LOG.exists():
        return []
    entries = []
    for line in PROPOSALS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not include_test and obj.get("test") is True:
            continue
        entries.append(obj)
    return entries


def recent_proposals(n=10):
    return load_proposals(include_test=False)[-n:]


def next_proposal_id(now=None):
    """Next sequential p-YYYYMMDD-NNN. Counts every logged and pending id for
    the day, test entries included — ids must never collide."""
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    seqs = [0]
    ids = [e["id"] for e in load_proposals(include_test=True)]
    if place.FILLS_LOG.exists():
        ids += [json.loads(l).get("id") for l in
                place.FILLS_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if PENDING_DIR.exists():
        ids += [p.stem for p in PENDING_DIR.glob("p-*.json")]
    for pid in ids:
        # \d{3,}: sequences can exceed 999 (they did — test ids 998/999 pushed
        # the counter past three digits and a \d{3} pattern went blind, which
        # collided two packets on one id)
        m = re.match(rf"^p-{day}-(\d{{3,}})$", pid or "")
        if m:
            seqs.append(int(m.group(1)))
    return f"p-{day}-{max(seqs) + 1:03d}"


# ---------------------------------------------------------------------------
# Rule checkers. Keyed by rule id; every ACTIVE rule in rulebook.md gets a
# packet line. A rule with no checker renders as MANUAL so a newly added rule
# is never silently skipped. Return (status, detail); status BLOCKED kills
# the packet.

def _check_r001(draft, ctx):
    aff = ctx["affordability"]
    if aff["status"] == "SKIPPED":
        return "SKIPPED", "balance 0 — not enforceable, orderTest does not check balance"
    if aff["status"] == "OK":
        pct = aff["fraction_of_balance"] * 100
        return "OK", (f"{aff['notional_usdt']:.2f} of {aff['usdt_free']:.2f} USDT = {pct:.1f}% "
                      f"[balance via {aff.get('balance_source', '?')}]")
    return "BLOCKED", aff.get("note", "affordability check failed")


def _check_r002(draft, ctx):
    base = re.sub(r"(USDT|USDC|FDUSD|TUSD|BTC|ETH|BNB)$", "", draft["symbol"])
    if base in TOP_20_BASES:
        return "OK", f"N/A — {base} is top-20, audit not required"
    audit = draft.get("audit")
    if audit == "PASS":
        return "OK", f"{base} not top-20, query-token-audit PASS"
    if audit == "FAIL":
        return "BLOCKED", f"{base} not top-20 and query-token-audit FAILED"
    return "BLOCKED", f"{base} not top-20 and no query-token-audit result in draft"


def _check_r003(draft, ctx):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    clashes = []
    for e in ctx["recent"]:
        if e.get("verdict") != "REJECTED":
            continue
        try:
            ts = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if ts >= cutoff and e.get("symbol") == draft["symbol"] and e.get("side") == draft["side"]:
            clashes.append(e["id"])
    if not clashes:
        return "OK", "no rejected proposal for this symbol+side in last 24h"
    change = draft.get("material_change")
    if change:
        return "OK", f"re-proposal after {','.join(clashes)}; material change: {change}"
    return "BLOCKED", f"rejected in last 24h ({','.join(clashes)}) and no material change stated"


def _check_r004(draft, ctx):
    return "OK", "tooling rule — enforced in place.py (assert_paper_safe + tool_execute log)"


# R007: structurally independent evidence sources. A=cross-sectional,
# B=time series, C=order book, D=report. ONCHAIN is optional context only —
# it never counts toward the two, and may never be the sole basis.
R007_SOURCES = {"A", "B", "C", "D"}


def evidence_sources(draft):
    tags = set()
    for ev in draft.get("evidence", []):
        if isinstance(ev, dict):
            tags.add(str(ev.get("source", "?")).upper())
        else:
            tags.add("?")  # untagged string evidence never counts as a source
    return tags


def _check_r005(draft, ctx):
    return "OK", "enforced at ingest (scripts/ingest.py) — on-chain signals filtered before packets"


def _check_r006(draft, ctx):
    return "OK", "enforced at ingest (scripts/ingest.py) — canonical contract match, fail-closed"


def _check_r011(draft, ctx):
    return "OK", "enforced at ingest (scan.py TRD_GRP_261 marker) — bstocks never reach drafts"


def _check_r012(draft, ctx):
    if not draft.get("invalidation"):
        return "BLOCKED", "no invalidation condition — exit plan incomplete"
    if not draft.get("max_hold_hours"):
        return "BLOCKED", "no time stop — exit plan incomplete"
    return "OK", f"invalidation stated + {draft['max_hold_hours']}h time stop"


def _check_r013(draft, ctx):
    hold = draft.get("max_hold_hours")
    if hold is None:
        return "BLOCKED", "no max hold on draft"
    if hold > 72:
        return "BLOCKED", f"max hold {hold}h exceeds the 72h ceiling"
    return "OK", f"max hold {hold}h <= 72h"


def _check_r008(draft, ctx):
    base = re.sub(r"(USDT|USDC|FDUSD|TUSD|BTC|ETH|BNB)$", "", draft["symbol"])
    if base in TOP_20_BASES:
        return "OK", f"N/A — {base} is top-20, vetting not required"
    vet = draft.get("vetting")
    if not isinstance(vet, dict) or "verdict" not in vet:
        return "BLOCKED", f"{base} not top-20 and no vetting result in draft (R008 fail-closed)"
    path, verdict = vet.get("path"), vet.get("verdict")
    if verdict == "PASS":
        return "OK", f"vetted via {path}: {vet.get('detail')}"
    return "BLOCKED", f"vetting via {path} FAILED: {vet.get('detail')}"


def _check_r007(draft, ctx):
    tags = evidence_sources(draft)
    counted = sorted(tags & R007_SOURCES)
    ignored = sorted(tags - R007_SOURCES)
    if len(counted) >= 2:
        detail = f"{len(counted)} independent sources: {','.join(counted)}"
        if ignored:
            detail += f" (context only, not counted: {','.join(ignored)})"
        return "OK", detail
    return "BLOCKED", (f"only {len(counted)} independent source(s) {counted}; "
                       f"non-counting tags: {ignored} — need 2 of A/B/C/D")


def _check_r009(draft, ctx):
    conf = draft.get("confidence")
    if conf is None:
        return "BLOCKED", "no confidence value on draft"
    if conf < CONFIDENCE_FLOOR:
        return "BLOCKED", f"confidence {conf:.0%} < 60% — must be suppressed to NO_PROPOSAL"
    return "OK", f"confidence {conf:.0%} >= 60% floor"


def _check_r010(draft, ctx):
    clash = pending_clash(draft["symbol"], draft["side"])
    if clash:
        return "BLOCKED", f"{clash} already PENDING for this symbol+side"
    return "OK", "no pending packet for this symbol+side"


def _check_r014(draft, ctx):
    rr = draft.get("rr")
    if not rr or rr.get("rr") is None:
        return "BLOCKED", "no structural target/stop — blocked, not estimated"
    if rr["rr"] < 2.0:
        return "BLOCKED", f"R:R {rr['rr']:.2f}:1 < 2:1"
    return "OK", (f"R:R {rr['rr']:.2f}:1 (target {rr['target']:g}, stop {rr['stop']:g}, "
                  "structural levels)")


CHECKERS = {"R001": _check_r001, "R002": _check_r002, "R003": _check_r003,
            "R004": _check_r004, "R005": _check_r005, "R006": _check_r006,
            "R007": _check_r007, "R008": _check_r008, "R009": _check_r009,
            "R010": _check_r010, "R011": _check_r011, "R012": _check_r012,
            "R013": _check_r013, "R014": _check_r014}


def run_rule_checks(draft, rules, ctx):
    results = []
    for rule in rules:
        checker = CHECKERS.get(rule["id"])
        if checker:
            status, detail = checker(draft, ctx)
        else:
            status, detail = "MANUAL", "no mechanical check implemented — verify by hand"
        results.append({"id": rule["id"], "text": rule["text"], "status": status, "detail": detail})
    return results


# ---------------------------------------------------------------------------
# Rendering

def _rule_line(res):
    label = res["text"][:44].rstrip()
    dots = "." * max(3, 50 - len(label))
    return f"  {res['id']} {label} {dots} {res['status']} ({res['detail']})"


def render_packet(pid, draft, checks):
    order_kind = draft["type"].lower()
    notional = place.proposal_notional_usdt(draft)
    notional_txt = f"{notional:g}" if notional is not None else "?"
    lines = [
        f"{BAR} DECISION PACKET {pid} {BAR}",
        "",
        f"PROPOSAL   {draft['side']} {notional_txt} USDT of {draft['symbol']} (spot, {order_kind})",
        f"CONFIDENCE {round(draft['confidence'] * 100)}%",
    ]
    if draft["confidence"] < LOW_CONVICTION:
        lines.append("LOW CONVICTION — below 60%, consider NO_PROPOSAL instead")
    if draft.get("setup"):
        lines.append(f"SETUP      {draft['setup']} — {draft.get('setup_detail', '')}")
    rr = draft.get("rr")
    if rr:
        lines.append(f"R:R        {rr['rr']:.1f} : 1 (target {rr['target']:g}, "
                     f"stop {rr['stop']:g}, entry ref {rr['entry']:g})")
    reg = draft.get("market_regime")
    if reg:
        lines.append(f"REGIME     BTC {reg['regime']}, 24h {reg['btc_chg24_pct']:+.2f}% "
                     f"(context only, not a gate)")
    lines += [
        f"THESIS     {draft['thesis']}",
        "",
        "EVIDENCE",
    ]
    for ev in draft["evidence"]:
        if isinstance(ev, dict):
            lines.append(f"  {BULLET} [{ev.get('source', '?')}] {ev.get('text', '')}")
        else:
            lines.append(f"  {BULLET} {ev}")
    vet_res = next((c for c in checks if c["id"] in ("R008", "R002")), None)
    if vet_res and "N/A" in vet_res["detail"]:
        vet_txt = "N/A (top-20)"
    elif isinstance(draft.get("vetting"), dict):
        vet_txt = f"{draft['vetting'].get('verdict')} via {draft['vetting'].get('path')}"
    else:
        vet_txt = draft.get("audit", "N/A")
    lines.append(f"  {BULLET} Vetting: {vet_txt}")
    lines += ["", "RULES CHECKED"]
    lines += [_rule_line(c) for c in checks]
    lines += [
        "",
        "INVALIDATION",
        f"  {draft['invalidation']}",
        "",
        "TIME STOP",
        f"  {draft.get('max_hold_hours', 72)}h maximum hold (R013) — exit proposed at the "
        "next scan after expiry, whichever of invalidation/time stop comes first.",
        "",
        "SIZE REASONING",
        f"  {draft['size_reasoning']}",
        "",
        f"{BAR} Pilot: y / n {BAR}",
        "If n, one code please: SIZE / TIMING / CONVICTION / RISK / DUPLICATE / ASSET / OTHER",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core paths

def build_packet(draft, market, account):
    """Returns (pid, packet_text, checks) or raises/blocks. BLOCKED rules
    print instead of a packet — caller decides exit."""
    # R009 hard floor: suppress to NO_PROPOSAL, log for clustering visibility.
    if draft.get("confidence") is not None and draft["confidence"] < CONFIDENCE_FLOOR:
        reason = f"confidence {draft['confidence']:.1%} < 60.0% floor — suppressed to NO_PROPOSAL"
        log_suppressed("R009", draft, reason)
        return None, (f"NO PACKET (R009): {draft['symbol']} {draft['side']} {reason}. "
                      f"Logged to logs/suppressed.jsonl. Emit the day-level NO_PROPOSAL "
                      f"if nothing else clears the bar."), None
    # R010: never stack a second packet on a symbol+side the Pilot hasn't decided.
    clash = pending_clash(draft["symbol"], draft["side"])
    if clash:
        reason = f"duplicate-pending skip — {clash} already awaits a verdict"
        log_suppressed("R010", draft, reason)
        return None, (f"NO PACKET (R010): {draft['symbol']} {draft['side']} {reason}. "
                      f"Logged to logs/suppressed.jsonl."), None
    # R014: structural reward-to-risk gate. No structure = blocked, not estimated.
    rr = draft.get("rr")
    if not rr or rr.get("rr") is None:
        reason = "R014: no structural target/stop could be derived — blocked, not estimated"
        log_suppressed("R014", draft, reason)
        return None, (f"NO PACKET (R014): {draft['symbol']} {draft['side']} {reason}. "
                      f"Logged to logs/suppressed.jsonl."), None
    if rr["rr"] < 2.0:
        reason = (f"R014: reward-to-risk {rr['rr']:.2f}:1 below 2:1 "
                  f"(target {rr['target']:g}, stop {rr['stop']:g})")
        log_suppressed("R014", draft, reason)
        return None, (f"NO PACKET (R014): {draft['symbol']} {draft['side']} {reason}. "
                      f"Logged to logs/suppressed.jsonl."), None
    rules = parse_active_rules()
    ctx = {
        "recent": recent_proposals(10),
        "market": market,
        "affordability": place.affordability_check(draft, account),
    }
    checks = run_rule_checks(draft, rules, ctx)
    blocked = [c for c in checks if c["status"] == "BLOCKED"]
    if blocked:
        return None, "\n".join(
            f"PACKET BLOCKED by {c['id']}: {c['detail']}" for c in blocked), checks
    pid = next_proposal_id()
    return pid, render_packet(pid, draft, checks), checks


def save_packet_text(pid, text):
    """The rendered packet is the artifact of record — terminal output gets
    mangled in transit. Written at generation time, UTF-8."""
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    path = PACKETS_DIR / f"{pid}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def save_pending(pid, draft, checks):
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    top20 = any(c["id"] in ("R002", "R008") and "N/A" in c["detail"] for c in checks)
    vet = draft.get("vetting") or {}
    pending = {
        "id": pid,
        "draft": draft,
        "rules_checked": [c["id"] for c in checks],
        "audit_passed": (None if top20
                         else vet.get("verdict", draft.get("audit")) == "PASS"),
        "vetting_path": "N/A (top-20)" if top20 else vet.get("path", "none"),
    }
    (PENDING_DIR / f"{pid}.json").write_text(
        json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    return pending


def generate_packet(invoke, draft):
    """In-process entry point. invoke is the session-side MCP caller."""
    market = invoke("spot_ticker24hr", {"symbol": draft["symbol"], "type": "FULL"})
    account = invoke("spot_getAccount", {"omitZeroBalances": True})
    pid, text, checks = build_packet(draft, market, account)
    if pid:
        save_pending(pid, draft, checks)
        save_packet_text(pid, text)
    return pid, text, checks


def record_verdict(pid, verdict, reason_code=None, note=None, test=False,
                   spec_superseded=False):
    """Append the Pilot's verdict to logs/proposals.jsonl per the CLAUDE.md
    schema. Refuses invalid verdicts and reject codes outside the fixed list."""
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"invalid verdict '{verdict}'; must be one of {sorted(VALID_VERDICTS)}")
    if verdict == "REJECTED":
        if reason_code not in VALID_REJECT_CODES:
            raise ValueError(
                f"invalid reject code '{reason_code}'; must be one of {sorted(VALID_REJECT_CODES)}")
    elif reason_code is not None:
        raise ValueError(f"reason_code only applies to REJECTED, not {verdict}")

    pending_path = PENDING_DIR / f"{pid}.json"
    if not pending_path.exists():
        raise FileNotFoundError(f"no pending proposal {pid} — generate the packet first")
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    draft = pending["draft"]

    entry = {
        "id": pid,
        "ts": place.now_iso(),
        "symbol": draft["symbol"],
        "side": draft["side"],
        "notional_usdt": place.proposal_notional_usdt(draft),
        "confidence": draft["confidence"],
        "thesis": draft["thesis"],
        "signals_used": draft.get("signals_used", []),
        "rules_checked": pending["rules_checked"],
        "invalidation": draft["invalidation"],
        "audit_passed": pending["audit_passed"],
        "vetting_path": pending.get("vetting_path"),
        "setup": draft.get("setup"),
        "rr": (round(draft["rr"]["rr"], 2)
               if isinstance(draft.get("rr"), dict) and draft["rr"].get("rr") is not None
               else None),
        "verdict": verdict,
        "reject_reason": reason_code,
        "pilot_note": note,
    }
    if test:
        entry["test"] = True
    if spec_superseded:
        # administrative rejection of an outdated packet spec: counts in Sync
        # Rate (it was decided), but is EXCLUDED from bias analysis and from
        # any Step-4 inference about Pilot preference (Pilot-directed
        # 2026-09-02) — admin rejections must never be learned as
        # "the Pilot rejects BUY proposals".
        entry["spec_superseded"] = True
    place.append_jsonl(PROPOSALS_LOG, entry)
    if verdict == "APPROVED":
        # keep the draft for the placement step (place.py prepare needs it,
        # including the id it uses as newClientOrderId)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        (APPROVED_DIR / f"{pid}.json").write_text(
            json.dumps(dict(draft, id=pid), indent=2, ensure_ascii=False), encoding="utf-8")
    pending_path.unlink()
    return entry


def log_no_proposal(reason, test=False):
    """The real 'No proposal today.' path — logged so Debrief metrics see it."""
    entry = {
        "id": next_proposal_id(),
        "ts": place.now_iso(),
        "symbol": None,
        "side": None,
        "notional_usdt": 0,
        "confidence": None,
        "thesis": reason,
        "signals_used": [],
        "rules_checked": [r["id"] for r in parse_active_rules()],
        "invalidation": None,
        "audit_passed": None,
        "verdict": "NO_PROPOSAL",
        "reject_reason": None,
        "pilot_note": None,
    }
    if test:
        entry["test"] = True
    place.append_jsonl(PROPOSALS_LOG, entry)
    return entry


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "packet":
        draft = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        market = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        account = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        pid, text, checks = build_packet(draft, market, account)
        print(text)
        if pid is None:
            return 2
        save_pending(pid, draft, checks)
        save_packet_text(pid, text)
    elif cmd == "verdict":
        args = [a for a in argv[2:] if a != "--test"]
        test = "--test" in argv
        pid, verdict = args[0], args[1]
        reason_code = args[2] if len(args) > 2 else None
        note = " ".join(args[3:]) if len(args) > 3 else None
        entry = record_verdict(pid, verdict, reason_code, note, test=test)
        print(json.dumps(entry, separators=(",", ": "), ensure_ascii=False))
    elif cmd == "no-proposal":
        reason = argv[2] if len(argv) > 2 else "No idea cleared the bar."
        entry = log_no_proposal(reason, test="--test" in argv)
        print("No proposal today.")
        print(json.dumps(entry, separators=(",", ": "), ensure_ascii=False))
    else:
        print("usage: propose.py packet <draft.json> <market.json> <account.json> | "
              "verdict <id> <APPROVED|REJECTED> [code] [note] [--test] | "
              "no-proposal <reason> [--test]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

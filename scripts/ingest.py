"""R005 signal ingest filter.

The on-chain signal feeds (smart money, market rank) surface microcap
launchpad tokens that do not exist on Binance spot. We trade an Agentic
sub-account with spot-only scope, so any signal whose asset is not an
ACTIVE Binance spot USDT pair is discarded AT INGEST — logged with a
reason, never surfaced as packet evidence (R005).

Eligibility = <TICKER>USDT exists on Binance spot exchangeInfo, with
status TRADING, quoteAsset USDT, and isSpotTradingAllowed true. The
lookup uses the public /api/v3/exchangeInfo endpoint (market data, no
auth) so the filter is self-contained and replayable.

CLI: python scripts/ingest.py <signals.json>
  signals.json is an array of signal objects (or {"data": [...]}).
  Prints eligible signals as JSON; discards go to logs/signals_discarded.jsonl.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import place  # append_jsonl, now_iso

ROOT = Path(__file__).resolve().parent.parent
DISCARD_LOG = ROOT / "logs" / "signals_discarded.jsonl"
EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo?symbol={symbol}"

_symbol_cache = {}


def spot_symbol_info(symbol):
    """exchangeInfo for one spot symbol, or None if not listed."""
    if symbol in _symbol_cache:
        return _symbol_cache[symbol]
    try:
        with urllib.request.urlopen(EXCHANGE_INFO_URL.format(symbol=symbol), timeout=15) as resp:
            data = json.loads(resp.read().decode())
        info = data["symbols"][0] if data.get("symbols") else None
    except urllib.error.HTTPError as e:
        if e.code == 400:  # -1121 invalid symbol = not listed
            info = None
        else:
            raise
    _symbol_cache[symbol] = info
    return info


def signal_ticker(signal):
    for key in ("ticker", "tokenSymbol", "symbol", "tokenName"):
        val = signal.get(key)
        if val:
            return str(val).upper()
    return None


def check_eligibility(ticker):
    """(eligible, symbol, reason)."""
    if not re.fullmatch(r"[A-Z0-9]{1,18}", ticker):
        return False, None, f"ticker {ticker!r} is not a valid Binance spot symbol (non-alphanumeric)"
    symbol = f"{ticker}USDT"
    info = spot_symbol_info(symbol)
    if info is None:
        return False, symbol, f"{symbol} is not listed on Binance spot"
    if info.get("status") != "TRADING":
        return False, symbol, f"{symbol} status is {info.get('status')}, not TRADING"
    if info.get("quoteAsset") != "USDT":
        return False, symbol, f"{symbol} quote asset is {info.get('quoteAsset')}, not USDT"
    if not info.get("isSpotTradingAllowed"):
        return False, symbol, f"{symbol} has spot trading disabled"
    return True, symbol, None


def log_discard(signal, ticker, reason):
    place.append_jsonl(DISCARD_LOG, {
        "ts": place.now_iso(),
        "ticker": ticker,
        "contract": signal.get("contractAddress"),
        "chainId": signal.get("chainId"),
        "reason": reason,
    })


def filter_signals(signals):
    """(eligible, discarded). Every discard is logged with its reason."""
    eligible, discarded = [], []
    for sig in signals:
        ticker = signal_ticker(sig)
        if not ticker:
            log_discard(sig, None, "no ticker field on signal")
            discarded.append((sig, "no ticker field on signal"))
            continue
        ok, symbol, reason = check_eligibility(ticker)
        if ok:
            sig["_spot_symbol"] = symbol
            eligible.append(sig)
        else:
            log_discard(sig, ticker, reason)
            discarded.append((sig, reason))
    return eligible, discarded


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    if len(argv) != 2:
        print("usage: ingest.py <signals.json>")
        return 1
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    signals = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    eligible, discarded = filter_signals(signals)
    print(json.dumps({
        "eligible_count": len(eligible),
        "discarded_count": len(discarded),
        "eligible": [{"ticker": signal_ticker(s), "spot_symbol": s["_spot_symbol"]} for s in eligible],
        "discard_reasons": [r for _, r in discarded],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

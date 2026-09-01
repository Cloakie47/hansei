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

# R006: canonical contract per (ticker, chainId). A signal's contract must
# match, or the signal is DISCARDED — fail-closed: no entry here means no
# acceptance, ticker-string matches alone are never sufficient. BSC ("56")
# entries are the long-established Binance-Peg / issuer contracts.
CANONICAL_CONTRACTS = {
    ("XRP", "56"): "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
    ("ADA", "56"): "0x3ee2200efb3400fabb9aacf31297cbdd1d435d47",
    ("DOGE", "56"): "0xba2ae424d960c26247dd6c32edc70b295c744c43",
    ("LINK", "56"): "0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd",
    ("DOT", "56"): "0x7083609fce4d1d8dc0c979aab8c869ea2c873402",
    ("LTC", "56"): "0x4338665cbb7b2485a8855a139b75d5e34ab0db94",
    ("BCH", "56"): "0x8ff795a6f4d97e7887c79bea79aba5cc76444adf",
    ("ETH", "56"): "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
    ("UNI", "56"): "0xbf5140a22578168fd562dccf235e5d43a02ce9b1",
    ("ATOM", "56"): "0x0eb3a705fc54725037cc9e008bdede697f62f335",
    ("WIN", "56"): "0xaef0d72a118ce24fee3cd1d43d383897d05b4e99",
    ("CAKE", "56"): "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
    ("SOL", "56"): "0x570a5d26f7765ecb712c0924e4de545b89fd43df",
}

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


def signal_contract(signal):
    return signal.get("contractAddress") or signal.get("ca")


def check_canonical(signal, ticker):
    """R006, fail-closed. (ok, reason, expected)."""
    chain_id = str(signal.get("chainId") or "56")
    expected = CANONICAL_CONTRACTS.get((ticker, chain_id))
    observed = signal_contract(signal)
    if expected is None:
        return False, (f"R006: no canonical contract known for {ticker} on chain "
                       f"{chain_id} — fail-closed discard"), None
    if not observed:
        return False, f"R006: signal has no contract address to verify against canonical", expected
    if observed.lower() != expected.lower():
        return False, (f"R006: contract mismatch — observed {observed}, "
                       f"canonical {expected}"), expected
    return True, None, expected


def log_discard(signal, ticker, reason, expected_contract=None):
    entry = {
        "ts": place.now_iso(),
        "ticker": ticker,
        "contract": signal_contract(signal),
        "chainId": signal.get("chainId"),
        "reason": reason,
    }
    if expected_contract is not None:
        entry["canonical_contract"] = expected_contract
    place.append_jsonl(DISCARD_LOG, entry)


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
        if not ok:
            log_discard(sig, ticker, reason)
            discarded.append((sig, reason))
            continue
        ok6, reason6, expected = check_canonical(sig, ticker)
        if not ok6:
            log_discard(sig, ticker, reason6, expected_contract=expected)
            discarded.append((sig, reason6))
            continue
        sig["_spot_symbol"] = symbol
        eligible.append(sig)
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

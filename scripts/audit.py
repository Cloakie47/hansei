"""R002 checker: query-token-audit with a strict fail-loud parser.

Calls the public Binance Web3 token-audit endpoint (same one the
query-token-audit skill documents) and maps the response to a PASS/FAIL
verdict. The parser is strict by design:

- riskLevelEnum must be one of the known values. The live API returns "MID"
  where SKILL.md documents "MEDIUM" — both are mapped. ANY other value
  raises AuditParseError; an unrecognised level is never passed as safe.
- riskLevel must be an integer 0-5, else AuditParseError.
- hasResult/isSupported false -> FAIL (audit unavailable is not a pass).
- A response that raises AuditParseError is treated as FAIL by callers.

FAIL conditions: riskLevel >= 4, any hit riskItem with riskType RISK,
buy/sell tax > 10%, or audit unavailable. Hit CAUTION items and unknown
taxes are flagged but do not fail on their own.

CLI: python scripts/audit.py <chainId> <contractAddress>
  exit 0 = PASS, 2 = FAIL, 3 = unparseable (counts as FAIL)
"""

import json
import sys
import urllib.request
import uuid

AUDIT_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"

# Live API says "MID" where SKILL.md says "MEDIUM"; normalise both.
KNOWN_ENUMS = {"LOW": "LOW", "MEDIUM": "MEDIUM", "MID": "MEDIUM", "HIGH": "HIGH"}
KNOWN_LEVELS = {0, 1, 2, 3, 4, 5}
MAX_TAX_PCT = 10.0
FAIL_LEVEL = 4


class AuditParseError(ValueError):
    """Response contains a value outside the known schema. Never treat the
    token as safe when this is raised."""


def fetch_audit(chain_id, contract_address):
    body = json.dumps({
        "binanceChainId": str(chain_id),
        "contractAddress": contract_address,
        "requestId": str(uuid.uuid4()),
    }).encode()
    req = urllib.request.Request(AUDIT_URL, data=body, headers={
        "Content-Type": "application/json",
        "source": "agent",
        "Accept-Encoding": "identity",
        "User-Agent": "binance-web3/1.4 (Skill)",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _parse_tax(raw, label, flags):
    if raw in (None, ""):
        flags.append(f"{label} unknown")
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        raise AuditParseError(f"unparseable {label}: {raw!r}")
    return val


def parse_audit(resp):
    """Strict mapping of the audit response to a verdict. Raises
    AuditParseError on anything outside the known schema."""
    if not isinstance(resp, dict) or resp.get("code") != "000000":
        raise AuditParseError(f"unexpected API code: {resp.get('code') if isinstance(resp, dict) else type(resp)}")
    data = resp.get("data")
    if not isinstance(data, dict):
        raise AuditParseError("missing data object")

    if not (data.get("hasResult") is True and data.get("isSupported") is True):
        return {"verdict": "FAIL", "level": None, "level_enum": None,
                "reasons": ["audit unavailable (hasResult/isSupported not true) — treated as FAIL"],
                "flags": []}

    raw_enum = data.get("riskLevelEnum")
    if raw_enum not in KNOWN_ENUMS:
        raise AuditParseError(f"unknown riskLevelEnum: {raw_enum!r} (known: {sorted(set(KNOWN_ENUMS))})")
    level_enum = KNOWN_ENUMS[raw_enum]

    level = data.get("riskLevel")
    if not isinstance(level, int) or level not in KNOWN_LEVELS:
        raise AuditParseError(f"unknown riskLevel: {level!r} (known: {sorted(KNOWN_LEVELS)})")

    reasons, flags = [], []
    extra = data.get("extraInfo") or {}
    buy_tax = _parse_tax(extra.get("buyTax"), "buyTax", flags)
    sell_tax = _parse_tax(extra.get("sellTax"), "sellTax", flags)

    if level >= FAIL_LEVEL:
        reasons.append(f"riskLevel {level} ({level_enum}) >= {FAIL_LEVEL}")
    for tax, label in ((buy_tax, "buyTax"), (sell_tax, "sellTax")):
        if tax is not None and tax > MAX_TAX_PCT:
            reasons.append(f"{label} {tax}% > {MAX_TAX_PCT}%")

    for item in data.get("riskItems") or []:
        for det in item.get("details") or []:
            if det.get("isHit") is True:
                risk_type = det.get("riskType")
                line = f"{item.get('id')}: {det.get('title')}"
                if risk_type == "RISK":
                    reasons.append(f"hit RISK — {line}")
                elif risk_type == "CAUTION":
                    flags.append(f"hit CAUTION — {line}")
                else:
                    raise AuditParseError(f"unknown riskType: {risk_type!r} on hit item {line}")

    return {"verdict": "FAIL" if reasons else "PASS",
            "level": level, "level_enum": level_enum,
            "buy_tax": buy_tax, "sell_tax": sell_tax,
            "reasons": reasons, "flags": flags}


def audit_token(chain_id, contract_address):
    """Fetch + parse. AuditParseError is converted to a FAIL verdict here so
    callers can rely on verdict, but the parse failure is named."""
    try:
        return parse_audit(fetch_audit(chain_id, contract_address))
    except AuditParseError as e:
        return {"verdict": "FAIL", "level": None, "level_enum": None,
                "reasons": [f"unparseable audit — treated as FAIL: {e}"], "flags": []}


def main(argv):
    if len(argv) != 3:
        print("usage: audit.py <chainId> <contractAddress>")
        return 1
    result = audit_token(argv[1], argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["verdict"] == "PASS":
        return 0
    return 3 if any("unparseable" in r for r in result["reasons"]) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

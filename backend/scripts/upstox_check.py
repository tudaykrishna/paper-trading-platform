"""Standalone Upstox connectivity check — no app imports, just the token.

    python scripts/upstox_check.py            # reads UPSTOX_ACCESS_TOKEN from ../.env or env
    python scripts/upstox_check.py <token>    # or pass it explicitly

Decodes the JWT locally (expiry / client id), then calls a few endpoints on both
the production and sandbox hosts and prints the raw status + body so you can see
exactly what Upstox says.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import httpx

PROD = "https://api.upstox.com/v2"
SANDBOX = "https://api-sandbox.upstox.com/v2"


def _load_token() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    if os.environ.get("UPSTOX_ACCESS_TOKEN"):
        return os.environ["UPSTOX_ACCESS_TOKEN"].strip()
    for candidate in (Path(__file__).resolve().parents[2] / ".env", Path(".env")):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if line.startswith("UPSTOX_ACCESS_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no token: pass it as an argument or set UPSTOX_ACCESS_TOKEN / .env")


def _decode_jwt(token: str) -> None:
    try:
        _, payload_b64, _ = token.split(".")
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! could not decode as JWT: {exc}")
        return
    now = time.time()
    exp = payload.get("exp", 0)
    print("  JWT payload:", json.dumps(payload, indent=2))
    print(f"  expired? {'YES' if now > exp else 'no'}  "
          f"({int(exp - now)} s left, exp={time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(exp))})")


def _call(base: str, path: str, token: str, params: dict | None = None) -> None:
    url = f"{base}{path}"
    try:
        r = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params=params,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        print(f"  {path:45} -> transport error: {exc}")
        return
    body = r.text
    if len(body) > 400:
        body = body[:400] + "…"
    print(f"  {path:45} -> {r.status_code}  {body}")


def main() -> None:
    token = _load_token()
    print(f"token: {token[:18]}…{token[-8:]}  (len {len(token)})\n")
    _decode_jwt(token)

    print("\n== production (api.upstox.com) ==")
    _call(PROD, "/user/profile", token)
    _call(PROD, "/user/get-funds-and-margin", token, {"segment": "SEC"})
    _call(PROD, "/market-quote/ltp", token, {"instrument_key": "NSE_EQ|INE002A01018"})

    print("\n== sandbox (api-sandbox.upstox.com) ==")
    _call(SANDBOX, "/user/profile", token)

    print(
        "\nReading:\n"
        "  200 on production /user/profile      -> token is good; the app just has a stale copy\n"
        "  401 UDAPI100050 on production, 200 on sandbox -> you generated a SANDBOX token;\n"
        "        regenerate via the LIVE dialog (api.upstox.com/v2/login/authorization/dialog)\n"
        "  401 on both                          -> token truly invalid: re-do Step 3, and make sure\n"
        "        you POST the auth *code* to /login/authorization/token and use the returned access_token\n"
    )


if __name__ == "__main__":
    main()

"""HMAC-SHA256 request signing for the 2328.io API.

Algorithm (from 2328.io docs):
  1. Serialize body to compact JSON (no extra whitespace).
  2. Base64-encode that JSON string.
  3. HMAC-SHA256 over the base64 string with the API key -> lowercase hex.

For bodyless (GET) requests, sign an empty string (base64('') == '').

Webhook verification reverses this: pull `sign` out, re-encode the remaining
fields with the SAME byte-exact compact JSON, recompute, constant-time compare.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def compact_json(data: dict[str, Any]) -> str:
    """Byte-exact compact JSON: no whitespace, non-ASCII kept literal (UTF-8)."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def sign_body(body: str, api_key: str) -> str:
    """HMAC-SHA256( base64(body), api_key ) -> lowercase hex."""
    b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    return hmac.new(
        api_key.encode("utf-8"), b64.encode("ascii"), hashlib.sha256
    ).hexdigest()


def sign_payload(data: dict[str, Any], api_key: str) -> tuple[str, str]:
    """Return (compact_json_body, signature) for a request payload."""
    body = compact_json(data)
    return body, sign_body(body, api_key)


def sign_empty(api_key: str) -> str:
    """Signature for bodyless GET requests (constant per key)."""
    return sign_body("", api_key)


def verify_webhook(payload: dict[str, Any], api_key: str) -> bool:
    """Verify an incoming webhook.

    The webhook body equals the payment/info object plus a `sign` field. We
    strip `sign`, re-encode the rest byte-exactly, recompute and constant-time
    compare. Field order matters for byte-exactness, so we preserve insertion
    order of the original dict (Python dicts are ordered).
    """
    received = payload.get("sign")
    if not received or not isinstance(received, str):
        return False
    rest = {k: v for k, v in payload.items() if k != "sign"}
    body = compact_json(rest)
    expected = sign_body(body, api_key)
    return hmac.compare_digest(expected, received)

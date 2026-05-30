"""Verify Telegram Mini App initData.

Telegram signs the launch params with a key derived from the bot token:
  secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)
where data_check_string is all fields except `hash`, sorted by key, joined
as "key=value" with newlines.

Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def parse_and_verify_init_data(
    init_data: str, bot_token: str, max_age_seconds: int = 86400
) -> dict | None:
    """Return parsed user dict if initData is authentic and fresh, else None."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={pairs[k]}" for k in sorted(pairs.keys())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    # Freshness check
    auth_date = pairs.get("auth_date")
    if auth_date and auth_date.isdigit():
        if time.time() - int(auth_date) > max_age_seconds:
            return None

    user_raw = pairs.get("user")
    if user_raw:
        try:
            return json.loads(user_raw)
        except json.JSONDecodeError:
            return {}
    return {}

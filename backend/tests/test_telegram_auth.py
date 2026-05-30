"""Tests for Telegram initData verification."""
from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

from app.core.telegram_auth import parse_and_verify_init_data

BOT_TOKEN = "123456:test-bot-token"


def _make_init_data(user: dict, auth_date: int) -> str:
    fields = {"auth_date": str(auth_date), "user": json.dumps(user, separators=(",", ":"))}
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = h
    return urlencode(fields)


def test_valid_init_data_returns_user():
    import time
    user = {"id": 42, "first_name": "Ilya", "username": "ilya"}
    init_data = _make_init_data(user, int(time.time()))
    result = parse_and_verify_init_data(init_data, BOT_TOKEN)
    assert result is not None
    assert result["id"] == 42


def test_tampered_init_data_rejected():
    import time
    user = {"id": 42, "first_name": "Ilya"}
    init_data = _make_init_data(user, int(time.time()))
    tampered = init_data.replace("42", "99")
    assert parse_and_verify_init_data(tampered, BOT_TOKEN) is None


def test_stale_init_data_rejected():
    user = {"id": 42}
    init_data = _make_init_data(user, 1000)  # very old
    assert parse_and_verify_init_data(init_data, BOT_TOKEN, max_age_seconds=10) is None


def test_empty_init_data_rejected():
    assert parse_and_verify_init_data("", BOT_TOKEN) is None

"""Unit tests for HMAC signing & webhook verification (the security core)."""
from __future__ import annotations

import base64
import hashlib
import hmac

from app.core import signing


def _reference_sign(body: str, key: str) -> str:
    """Independent reimplementation of the documented algorithm."""
    b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    return hmac.new(key.encode(), b64.encode(), hashlib.sha256).hexdigest()


def test_sign_body_matches_reference():
    body = '{"amount":"100.00","currency":"USD","order_id":"ORDER-1"}'
    key = "secret-key"
    assert signing.sign_body(body, key) == _reference_sign(body, key)


def test_sign_empty_is_constant_and_correct():
    key = "secret-key"
    s1 = signing.sign_empty(key)
    s2 = signing.sign_empty(key)
    assert s1 == s2
    assert s1 == _reference_sign("", key)


def test_compact_json_no_whitespace_and_unicode_literal():
    out = signing.compact_json({"a": 1, "desc": "Премиум"})
    assert " " not in out
    assert "Премиум" in out  # not \u-escaped
    assert out == '{"a":1,"desc":"Премиум"}'


def test_sign_payload_roundtrip():
    payload = {"amount": "100.00", "currency": "RUB", "order_id": "X-1"}
    key = "k"
    body, sig = signing.sign_payload(payload, key)
    assert sig == _reference_sign(body, key)


def test_verify_webhook_accepts_valid_signature():
    key = "webhook-key"
    payload = {
        "uuid": "abc-123",
        "order_id": "ORDER-1",
        "payment_status": "paid",
        "merchant_amount": "99.50",
    }
    body = signing.compact_json(payload)
    payload_with_sign = dict(payload)
    payload_with_sign["sign"] = signing.sign_body(body, key)
    assert signing.verify_webhook(payload_with_sign, key) is True


def test_verify_webhook_rejects_tampered_payload():
    key = "webhook-key"
    payload = {"uuid": "abc-123", "payment_status": "paid", "merchant_amount": "99.50"}
    body = signing.compact_json(payload)
    payload_with_sign = dict(payload)
    payload_with_sign["sign"] = signing.sign_body(body, key)
    # Tamper after signing
    payload_with_sign["merchant_amount"] = "999999.00"
    assert signing.verify_webhook(payload_with_sign, key) is False


def test_verify_webhook_rejects_missing_sign():
    assert signing.verify_webhook({"uuid": "x"}, "k") is False
    assert signing.verify_webhook({"uuid": "x", "sign": ""}, "k") is False

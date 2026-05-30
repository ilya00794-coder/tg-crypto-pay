"""End-to-end API test with a mocked 2328.io gateway.

Exercises: Telegram auth -> create invoice (markup applied) -> simulate a
paid webhook (HMAC-signed) -> merchant balance credited -> payout debits it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_e2e.db")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test-bot-token")
os.environ.setdefault("GATEWAY_API_KEY", "test-api-key")
os.environ.setdefault("GATEWAY_PAYOUT_API_KEY", "test-payout-key")
os.environ.setdefault("DEFAULT_MARKUP_PERCENT", "10")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import signing
from app.core.config import get_settings
from app.main import app
from app.services import gateway as gw_module

BOT_TOKEN = "123456:" + "test-bot-token"


def tg_headers(user_id: int = 777) -> dict:
    user = {"id": user_id, "first_name": "Test", "username": "tester"}
    fields = {"auth_date": str(int(time.time())), "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(fields)}


class FakeGateway:
    """Stand-in for GatewayClient: no network, deterministic responses."""

    def __init__(self, *_args, **_kwargs):
        self.last_payout = None

    async def aclose(self):
        pass

    async def create_payment(self, payload):
        return {
            "state": 0,
            "result": {
                "uuid": "gw-uuid-1",
                "order_id": payload["order_id"],
                "amount": payload["amount"],
                "currency": payload["currency"],
                "url": "https://2328.io/pay/gw-uuid-1",
                "tg_deeplink": "https://t.me/testbot?start=pay_gw-uuid-1",
                "payer_currency": "USDT",
                "payer_amount": "110.00",
                "network": "TRX-TRC20",
                "address": "TXYZfakeaddress",
                "payment_status": "check",
                "qr": "data:image/png;base64,FAKE",
                "txid": None,
            },
        }

    async def payment_info(self, uuid=None, order_id=None):
        return {"state": 0, "result": {"uuid": "gw-uuid-1", "payment_status": "check"}}

    async def create_payout(self, payload):
        self.last_payout = payload
        return {"state": 0, "result": {"uuid": "payout-uuid-1", "status": "pending"}}

    async def payout_status(self, uuid):
        return {"state": 0, "result": {"uuid": uuid, "status": "pending"}}


@pytest_asyncio.fixture
async def client(monkeypatch):
    # Override the gateway dependency to use the fake (no network).
    from app.api import deps

    app.dependency_overrides[deps.get_gateway] = lambda: FakeGateway()

    # fresh db
    if os.path.exists("test_e2e.db"):
        os.remove("test_e2e.db")
    from app.db.session import init_db

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_full_flow(client):
    h = tg_headers()

    # 1. who am I (creates merchant)
    r = await client.get("/api/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["markup_percent"] == 10.0

    # 2. create invoice for $100 net; payer should be charged with +10% markup
    r = await client.post(
        "/api/invoices",
        headers=h,
        json={"amount": 100.0, "currency": "USD", "order_id": "INV-1",
              "to_currency": "USDT", "network": "TRX-TRC20"},
    )
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["tg_deeplink"].startswith("https://t.me/")
    assert inv["pay_address"] == "TXYZfakeaddress"
    assert inv["markup_percent"] == 10.0
    assert inv["status"] == "check"

    # 3. balance is empty before payment
    r = await client.get("/api/balance", headers=h)
    assert r.json()["balances"] == []

    # 4. simulate a signed 'paid' webhook from the gateway
    settings = get_settings()
    webhook_body = {
        "uuid": "gw-uuid-1",
        "order_id": "m1-INV-1",
        "payment_status": "paid",
        "payer_currency": "USDT",
        "merchant_amount": "110.00",  # gateway credited us 110 (payer paid 100*1.1)
        "txid": "0xabc",
    }
    body_str = signing.compact_json(webhook_body)
    webhook_body["sign"] = signing.sign_body(body_str, settings.gateway_api_key)
    r = await client.post("/api/webhooks/payment", json=webhook_body)
    assert r.status_code == 200, r.text

    # 5. merchant balance now ~100 USDT (110 / 1.10), our 10 is the fee we keep
    r = await client.get("/api/balance", headers=h)
    bals = {b["currency"]: b["available"] for b in r.json()["balances"]}
    assert "USDT" in bals
    assert abs(float(bals["USDT"]) - 100.0) < 0.0001

    # 6. replay the same webhook -> balance unchanged (idempotency)
    r = await client.post("/api/webhooks/payment", json=webhook_body)
    assert r.status_code == 200
    r = await client.get("/api/balance", headers=h)
    bals = {b["currency"]: b["available"] for b in r.json()["balances"]}
    assert abs(float(bals["USDT"]) - 100.0) < 0.0001

    # 7. payout 40 USDT -> ok, balance drops to 60
    r = await client.post(
        "/api/payouts",
        headers=h,
        json={"currency": "USDT", "network": "TRX-TRC20", "amount": 40.0,
              "to_address": "TXYZdest", "order_id": "W-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    r = await client.get("/api/balance", headers=h)
    bals = {b["currency"]: b["available"] for b in r.json()["balances"]}
    assert abs(float(bals["USDT"]) - 60.0) < 0.0001

    # 8. payout more than balance -> 400
    r = await client.post(
        "/api/payouts",
        headers=h,
        json={"currency": "USDT", "network": "TRX-TRC20", "amount": 1000.0,
              "to_address": "TXYZdest", "order_id": "W-2"},
    )
    assert r.status_code == 400

    # 9. webhook with bad signature -> 401
    bad = dict(webhook_body)
    bad["sign"] = "deadbeef"
    r = await client.post("/api/webhooks/payment", json=bad)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_requires_auth(client):
    r = await client.get("/api/me")
    assert r.status_code == 401

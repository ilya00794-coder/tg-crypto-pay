"""Async client for the 2328.io payment gateway.

Wraps payment creation, status lookup, balance, and payouts with correct
HMAC signing and required headers. All money/blockchain custody happens on
2328.io's side; this client is the only place that talks to them.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core import signing
from app.core.config import Settings


class GatewayError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GatewayClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._s = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.gateway_base_url, timeout=30.0
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, sign: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "project": self._s.gateway_project_uuid,
            "sign": sign,
            "User-Agent": self._s.gateway_user_agent,
        }

    async def _post(self, path: str, payload: dict[str, Any], *, payout: bool = False) -> dict:
        key = self._s.gateway_payout_api_key if payout else self._s.gateway_api_key
        body, sign = signing.sign_payload(payload, key)
        resp = await self._client.post(
            path, content=body.encode("utf-8"), headers=self._headers(sign)
        )
        return self._handle(resp)

    async def _get(self, path: str, *, payout: bool = False) -> dict:
        key = self._s.gateway_payout_api_key if payout else self._s.gateway_api_key
        sign = signing.sign_empty(key)
        resp = await self._client.get(path, headers=self._headers(sign))
        return self._handle(resp)

    @staticmethod
    def _handle(resp: httpx.Response) -> dict:
        try:
            data = resp.json()
        except Exception:
            raise GatewayError(
                f"Non-JSON response: {resp.text[:200]}", resp.status_code, resp.text
            )
        if resp.status_code >= 400:
            raise GatewayError(
                f"Gateway HTTP {resp.status_code}", resp.status_code, data
            )
        # 2328.io wraps success as {"state":0,"result":{...}}
        if isinstance(data, dict) and data.get("state") not in (0, None):
            raise GatewayError(
                f"Gateway state={data.get('state')}", resp.status_code, data
            )
        return data

    # --- Payments ---
    async def create_payment(self, payload: dict[str, Any]) -> dict:
        return await self._post("/v1/payment", payload)

    async def payment_info(self, *, uuid: str | None = None, order_id: str | None = None) -> dict:
        body: dict[str, Any] = {}
        if uuid:
            body["uuid"] = uuid
        if order_id:
            body["order_id"] = order_id
        return await self._post("/v1/payment/info", body)

    # --- Balance ---
    async def balance(self) -> dict:
        return await self._get("/v1/balance")

    # --- Payouts (separate key) ---
    async def create_payout(self, payload: dict[str, Any]) -> dict:
        return await self._post("/v1/payout", payload, payout=True)

    async def payout_status(self, uuid: str) -> dict:
        return await self._get(f"/v1/payout/status/{uuid}", payout=True)

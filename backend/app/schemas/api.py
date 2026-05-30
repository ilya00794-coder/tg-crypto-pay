"""Pydantic request/response schemas for the Mini App API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateInvoiceIn(BaseModel):
    amount: float = Field(gt=0, description="Net amount the merchant wants to receive")
    currency: str = Field(description="Display currency: fiat (USD/EUR/RUB) or crypto")
    order_id: str = Field(max_length=128)
    to_currency: str | None = Field(default=None, description="Preselected crypto")
    network: str | None = None
    description: str = Field(default="", max_length=200)
    ttl_seconds: int | None = Field(default=None, ge=300, le=86400)


class InvoiceOut(BaseModel):
    order_id: str
    gateway_uuid: str | None
    status: str
    currency: str
    amount: float
    markup_percent: float
    pay_url: str | None
    tg_deeplink: str | None
    pay_address: str | None
    payer_currency: str | None
    payer_amount: str | None
    network: str | None
    qr: str | None
    txid: str | None


class BalanceEntry(BaseModel):
    currency: str
    available: str


class BalanceOut(BaseModel):
    balances: list[BalanceEntry]


class PayoutIn(BaseModel):
    currency: str
    network: str
    amount: float = Field(gt=0)
    to_address: str
    order_id: str = Field(max_length=128, description="Idempotency key")


class PayoutOut(BaseModel):
    order_id: str
    gateway_uuid: str | None
    status: str
    currency: str
    network: str
    amount: float
    to_address: str
    txid: str | None
    error_type: str | None


class MerchantSettingsIn(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    payout_address: str | None = Field(default=None, max_length=255)
    payout_network: str | None = Field(default=None, max_length=32)


class MerchantOut(BaseModel):
    tg_user_id: int
    name: str
    payout_address: str | None
    payout_network: str | None
    markup_percent: float | None

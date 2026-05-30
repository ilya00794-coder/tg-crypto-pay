"""Business logic for invoices, balances and payouts (Variant B).

This is where YOUR product logic lives on top of the 2328.io gateway:
- apply your markup (your crypto fee) when creating an invoice
- map gateway statuses to our InvoiceStatus
- on a confirmed payment, credit the merchant's virtual balance in the ledger
  (idempotently), net of your fee
- enforce that a merchant can only withdraw up to their available balance
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    Invoice,
    InvoiceStatus,
    LedgerDirection,
    LedgerEntry,
    Merchant,
    Payout,
    PayoutStatus,
)
from app.services.gateway import GatewayClient

# gateway payment_status -> our InvoiceStatus
_STATUS_MAP = {
    "pending": InvoiceStatus.created,
    "check": InvoiceStatus.check,
    "paid": InvoiceStatus.paid,
    "overpaid": InvoiceStatus.overpaid,
    "underpaid": InvoiceStatus.underpaid,
    "underpaid_check": InvoiceStatus.check,
    "cancel": InvoiceStatus.cancel,
    "aml_lock": InvoiceStatus.aml_lock,
}
SUCCESS_STATUSES = {InvoiceStatus.paid, InvoiceStatus.overpaid}


def effective_markup(merchant: Merchant, settings: Settings) -> float:
    return (
        merchant.markup_percent
        if merchant.markup_percent is not None
        else settings.default_markup_percent
    )


async def create_invoice(
    db: AsyncSession,
    gw: GatewayClient,
    settings: Settings,
    merchant: Merchant,
    *,
    amount: float,
    currency: str,
    order_id: str,
    to_currency: str | None,
    network: str | None,
    description: str,
    ttl_seconds: int | None,
) -> Invoice:
    markup = effective_markup(merchant, settings)

    payload: dict = {
        "amount": str(amount),
        "currency": currency,
        "order_id": order_id,
        "url_callback": f"{settings.public_base_url}/api/webhooks/payment",
        # price_markup is how we take our fee in crypto: payer pays amount*(1+markup)
        "price_markup": markup,
        "description": description or "",
    }
    if to_currency:
        payload["to_currency"] = to_currency
    if network:
        payload["network"] = network
    if ttl_seconds:
        payload["ttl_seconds"] = ttl_seconds

    resp = await gw.create_payment(payload)
    r = resp.get("result", {})

    inv = Invoice(
        merchant_id=merchant.id,
        order_id=order_id,
        gateway_uuid=r.get("uuid"),
        currency=currency,
        amount=amount,
        markup_percent=markup,
        status=_STATUS_MAP.get(r.get("payment_status", "check"), InvoiceStatus.check),
        description=description or "",
        pay_url=r.get("url"),
        tg_deeplink=r.get("tg_deeplink"),
        pay_address=r.get("address"),
        payer_currency=r.get("payer_currency"),
        payer_amount=r.get("payer_amount"),
        network=r.get("network"),
        qr=r.get("qr"),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def apply_payment_update(db: AsyncSession, data: dict) -> Invoice | None:
    """Update an invoice from a gateway payment object (webhook or polled info).

    On a successful payment, credit the merchant ledger exactly once
    (idempotent by gateway uuid). Returns the updated invoice or None.
    """
    uuid = data.get("uuid")
    order_id = data.get("order_id")
    stmt = select(Invoice)
    if uuid:
        stmt = stmt.where(Invoice.gateway_uuid == uuid)
    elif order_id:
        stmt = stmt.where(Invoice.order_id == order_id)
    else:
        return None

    inv = (await db.execute(stmt)).scalar_one_or_none()
    if inv is None:
        return None

    new_status = _STATUS_MAP.get(data.get("payment_status", ""), inv.status)
    inv.status = new_status
    inv.txid = data.get("txid") or inv.txid
    inv.merchant_amount = data.get("merchant_amount") or inv.merchant_amount
    inv.payer_currency = data.get("payer_currency") or inv.payer_currency
    inv.network = data.get("network") or inv.network

    if new_status in SUCCESS_STATUSES and uuid:
        await _credit_merchant_once(db, inv, data, uuid)

    await db.commit()
    await db.refresh(inv)
    return inv


async def _credit_merchant_once(
    db: AsyncSession, inv: Invoice, data: dict, uuid: str
) -> None:
    """Idempotent credit: the merchant's net (merchant_amount minus our fee).

    `merchant_amount` from the gateway is what landed on OUR balance after the
    gateway's own fee. The payer already paid the markup, so we keep the markup
    portion as our fee and credit the merchant the rest. We approximate the
    merchant's net as merchant_amount / (1 + markup/100).
    """
    exists = (
        await db.execute(
            select(LedgerEntry).where(
                LedgerEntry.ref == uuid,
                LedgerEntry.direction == LedgerDirection.credit,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        return  # already credited

    received = Decimal(str(data.get("merchant_amount") or "0"))
    markup = Decimal(str(inv.markup_percent or 0))
    merchant_net = received / (Decimal("1") + markup / Decimal("100")) if received else Decimal("0")
    crypto = data.get("payer_currency") or "USDT"

    db.add(
        LedgerEntry(
            merchant_id=inv.merchant_id,
            direction=LedgerDirection.credit,
            currency=crypto,
            amount=merchant_net,
            ref=uuid,
            note=f"payment {inv.order_id}",
        )
    )


async def merchant_balances(db: AsyncSession, merchant_id: int) -> dict[str, Decimal]:
    """Compute available balance per currency = credits - debits."""
    rows = (
        await db.execute(
            select(LedgerEntry).where(LedgerEntry.merchant_id == merchant_id)
        )
    ).scalars().all()
    bal: dict[str, Decimal] = {}
    for e in rows:
        amt = Decimal(str(e.amount))
        if e.direction == LedgerDirection.debit:
            amt = -amt
        bal[e.currency] = bal.get(e.currency, Decimal("0")) + amt
    return bal


async def create_payout(
    db: AsyncSession,
    gw: GatewayClient,
    merchant: Merchant,
    *,
    currency: str,
    network: str,
    amount: float,
    to_address: str,
    order_id: str,
) -> Payout:
    # Idempotency: return existing payout for same order_id
    existing = (
        await db.execute(select(Payout).where(Payout.order_id == order_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    balances = await merchant_balances(db, merchant.id)
    available = balances.get(currency, Decimal("0"))
    if Decimal(str(amount)) > available:
        raise ValueError(
            f"Insufficient balance: requested {amount} {currency}, available {available}"
        )

    resp = await gw.create_payout(
        {
            "currency": currency,
            "network": network,
            "amount": str(amount),
            "to_address": to_address,
            "order_id": order_id,
            "url_callback": None,
        }
    )
    r = resp.get("result", {})

    payout = Payout(
        merchant_id=merchant.id,
        order_id=order_id,
        gateway_uuid=r.get("uuid"),
        currency=currency,
        network=network,
        amount=amount,
        to_address=to_address,
        status=PayoutStatus.pending,
    )
    db.add(payout)
    # Debit the ledger immediately to reserve funds (idempotent by order_id ref).
    db.add(
        LedgerEntry(
            merchant_id=merchant.id,
            direction=LedgerDirection.debit,
            currency=currency,
            amount=amount,
            ref=order_id,
            note=f"payout {order_id}",
        )
    )
    await db.commit()
    await db.refresh(payout)
    return payout

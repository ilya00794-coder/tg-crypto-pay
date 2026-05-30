"""Mini App API routes (Telegram-auth'd)."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_merchant, get_gateway
from app.core.config import Settings, get_settings
from app.db.models import Invoice, Merchant, Payout
from app.db.session import get_db
from app.schemas.api import (
    BalanceEntry,
    BalanceOut,
    CreateInvoiceIn,
    InvoiceOut,
    MerchantOut,
    MerchantSettingsIn,
    PayoutIn,
    PayoutOut,
)
from app.services import billing
from app.services.billing import effective_markup
from app.services.gateway import GatewayClient, GatewayError

router = APIRouter(prefix="/api", tags=["app"])


def _invoice_out(inv: Invoice) -> InvoiceOut:
    return InvoiceOut(
        order_id=inv.order_id,
        gateway_uuid=inv.gateway_uuid,
        status=inv.status.value,
        currency=inv.currency,
        amount=float(inv.amount),
        markup_percent=float(inv.markup_percent),
        pay_url=inv.pay_url,
        tg_deeplink=inv.tg_deeplink,
        pay_address=inv.pay_address,
        payer_currency=inv.payer_currency,
        payer_amount=inv.payer_amount,
        network=inv.network,
        qr=inv.qr,
        txid=inv.txid,
    )


@router.get("/me", response_model=MerchantOut)
async def get_me(
    merchant: Merchant = Depends(get_current_merchant),
    settings: Settings = Depends(get_settings),
):
    return MerchantOut(
        tg_user_id=merchant.tg_user_id,
        name=merchant.name,
        payout_address=merchant.payout_address,
        payout_network=merchant.payout_network,
        markup_percent=effective_markup(merchant, settings),
    )


@router.patch("/me", response_model=MerchantOut)
async def update_me(
    body: MerchantSettingsIn,
    merchant: Merchant = Depends(get_current_merchant),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        merchant.name = body.name
    if body.payout_address is not None:
        merchant.payout_address = body.payout_address
    if body.payout_network is not None:
        merchant.payout_network = body.payout_network
    db.add(merchant)
    await db.commit()
    await db.refresh(merchant)
    return MerchantOut(
        tg_user_id=merchant.tg_user_id,
        name=merchant.name,
        payout_address=merchant.payout_address,
        payout_network=merchant.payout_network,
        markup_percent=effective_markup(merchant, settings),
    )


@router.post("/invoices", response_model=InvoiceOut)
async def create_invoice(
    body: CreateInvoiceIn,
    merchant: Merchant = Depends(get_current_merchant),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    gw: GatewayClient = Depends(get_gateway),
):
    # order_id must be unique per project; prefix with merchant to avoid clashes
    order_id = f"m{merchant.id}-{body.order_id}"
    dup = (
        await db.execute(select(Invoice).where(Invoice.order_id == order_id))
    ).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status_code=409, detail="order_id already used")
    try:
        inv = await billing.create_invoice(
            db, gw, settings, merchant,
            amount=body.amount, currency=body.currency, order_id=order_id,
            to_currency=body.to_currency, network=body.network,
            description=body.description, ttl_seconds=body.ttl_seconds,
        )
    except GatewayError as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}") from e
    finally:
        await gw.aclose()
    return _invoice_out(inv)


@router.get("/invoices/{order_id}", response_model=InvoiceOut)
async def get_invoice(
    order_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    gw: GatewayClient = Depends(get_gateway),
):
    full_order = f"m{merchant.id}-{order_id}"
    inv = (
        await db.execute(
            select(Invoice).where(
                Invoice.order_id == full_order, Invoice.merchant_id == merchant.id
            )
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    # Poll the gateway for fresh status (in case a webhook was missed).
    if inv.gateway_uuid:
        try:
            resp = await gw.payment_info(uuid=inv.gateway_uuid)
            inv = await billing.apply_payment_update(db, resp.get("result", {})) or inv
        except GatewayError:
            pass  # serve cached status if gateway is flaky
        finally:
            await gw.aclose()
    return _invoice_out(inv)


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    bal = await billing.merchant_balances(db, merchant.id)
    return BalanceOut(
        balances=[
            BalanceEntry(currency=c, available=str(v)) for c, v in sorted(bal.items())
        ]
    )


@router.post("/payouts", response_model=PayoutOut)
async def create_payout(
    body: PayoutIn,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    gw: GatewayClient = Depends(get_gateway),
):
    order_id = f"po-m{merchant.id}-{body.order_id}"
    try:
        payout = await billing.create_payout(
            db, gw, merchant,
            currency=body.currency, network=body.network, amount=body.amount,
            to_address=body.to_address, order_id=order_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except GatewayError as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}") from e
    finally:
        await gw.aclose()
    return PayoutOut(
        order_id=payout.order_id,
        gateway_uuid=payout.gateway_uuid,
        status=payout.status.value,
        currency=payout.currency,
        network=payout.network,
        amount=float(payout.amount),
        to_address=payout.to_address,
        txid=payout.txid,
        error_type=payout.error_type,
    )

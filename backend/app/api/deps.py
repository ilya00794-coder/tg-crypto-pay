"""FastAPI dependencies: Telegram-auth'd merchant + gateway client."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.telegram_auth import parse_and_verify_init_data
from app.db.models import Merchant
from app.db.session import get_db
from app.services.gateway import GatewayClient


async def get_current_merchant(
    authorization: str | None = Header(default=None),
    x_telegram_init_data: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Merchant:
    """Authenticate via Telegram Mini App initData.

    Mini App sends initData either in `Authorization: tma <initData>` or in the
    `X-Telegram-Init-Data` header. We verify the HMAC and upsert the merchant.
    """
    init_data = x_telegram_init_data
    if not init_data and authorization and authorization.lower().startswith("tma "):
        init_data = authorization[4:]

    user = parse_and_verify_init_data(init_data or "", settings.telegram_bot_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid Telegram initData")
    tg_id = user.get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="No Telegram user id")

    res = await db.execute(select(Merchant).where(Merchant.tg_user_id == tg_id))
    merchant = res.scalar_one_or_none()
    if merchant is None:
        merchant = Merchant(
            tg_user_id=tg_id,
            name=" ".join(
                p for p in [user.get("first_name"), user.get("last_name")] if p
            )
            or user.get("username", ""),
        )
        db.add(merchant)
        await db.commit()
        await db.refresh(merchant)
    return merchant


def get_gateway(settings: Settings = Depends(get_settings)) -> GatewayClient:
    # One client per request is fine for moderate load; httpx pools connections.
    return GatewayClient(settings)

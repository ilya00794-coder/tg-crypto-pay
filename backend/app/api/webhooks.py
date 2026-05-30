"""Webhook receiver for 2328.io payment notifications.

Security:
- Verify HMAC signature with the API key (constant-time) -> 401 if invalid.
- Idempotency is enforced in billing (ledger unique on uuid) so replays are safe.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.signing import verify_webhook
from app.db.session import get_db
from app.services import billing

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/payment")
async def payment_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="bad payload")

    if not verify_webhook(payload, settings.gateway_api_key):
        raise HTTPException(status_code=401, detail="bad signature")

    await billing.apply_payment_update(db, payload)
    # Always 200 once verified+processed so the gateway stops retrying.
    return {"ok": True}

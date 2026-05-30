"""ORM models: merchants, invoices, ledger entries, payouts.

Variant B (custodial-over-2328.io) data model:
- Merchant: a business using your platform. Has its own crypto payout address
  and an optional per-merchant markup (your fee).
- Invoice: one payment request. Mirrors the 2328.io payment by `gateway_uuid`.
- LedgerEntry: double-purpose append-only ledger of what each merchant is owed
  (credit on paid) and what they withdrew (debit on payout). Merchant balance =
  sum of credits - sum of debits, per currency.
- Payout: a withdrawal request from a merchant's virtual balance to their
  crypto address, executed via 2328.io payout API.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Telegram user id of the business owner (from initData)
    tg_user_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    # Where this merchant withdraws to
    payout_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Per-merchant markup override (% added to invoices = your fee). NULL = use default.
    markup_percent: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="merchant")


class InvoiceStatus(str, enum.Enum):
    created = "created"
    check = "check"          # waiting for payment
    paid = "paid"
    overpaid = "overpaid"
    underpaid = "underpaid"
    cancel = "cancel"
    aml_lock = "aml_lock"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    # Our order id, sent to gateway as order_id (must be unique per project)
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gateway_uuid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    # What the merchant wants to receive (their net), and the displayed currency
    currency: Mapped[str] = mapped_column(String(16))         # fiat or crypto code
    amount: Mapped[float] = mapped_column(Numeric(24, 8))     # net amount merchant requested
    markup_percent: Mapped[float] = mapped_column(default=0)  # applied platform fee %

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.created, index=True
    )
    description: Mapped[str] = mapped_column(String(200), default="")

    # Filled from gateway response
    pay_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tg_deeplink: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pay_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    payer_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qr: Mapped[str | None] = mapped_column(String, nullable=True)  # data URI
    txid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    merchant_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="invoices")


class LedgerDirection(str, enum.Enum):
    credit = "credit"   # money owed to merchant (incoming payment)
    debit = "debit"     # money paid out to merchant


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        # Idempotency: one credit per gateway payment uuid
        UniqueConstraint("ref", "direction", name="uq_ledger_ref_dir"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    direction: Mapped[LedgerDirection] = mapped_column(Enum(LedgerDirection))
    currency: Mapped[str] = mapped_column(String(16), index=True)   # crypto credited
    amount: Mapped[float] = mapped_column(Numeric(28, 18))
    # Reference: gateway payment uuid (credit) or payout uuid (debit)
    ref: Mapped[str] = mapped_column(String(64), index=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PayoutStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gateway_uuid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    currency: Mapped[str] = mapped_column(String(16))
    network: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Numeric(28, 18))
    to_address: Mapped[str] = mapped_column(String(255))
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus), default=PayoutStatus.pending, index=True
    )
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    txid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

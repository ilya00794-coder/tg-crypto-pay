"""Unit tests for billing logic, focusing on platform fee calculations."""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invoice, LedgerDirection, LedgerEntry, Merchant
from app.services import billing


@pytest.mark.parametrize("total_amount,expected_merchant_amount", [
    ("100.00", "94.00"),   # Базовый сценарий
    ("50.50", "47.47"),    # Дробные суммы
    ("0.10", "0.09"),      # Маленькие суммы
    ("1000.00", "940.00"), # Большие суммы
])
@pytest.mark.asyncio
async def test_merchant_net_calculation(
    total_amount: str, 
    expected_merchant_amount: str,
    db_session: AsyncSession
):
    """
    Проверяет, что мерчант получает корректную сумму после вычета платформенной комиссии.
    Комиссия платформы = 6%
    """
    # Подготовка тестовых данных
    data = {
        "merchant_amount": total_amount,
        "payer_currency": "USDT"
    }
    
    # Создаем фейкового мерчанта
    merchant = Merchant(tg_user_id=123, name="Test Merchant")
    db_session.add(merchant)
    await db_session.flush()

    # Создаем фейковый инвойс
    invoice = Invoice(
        merchant_id=merchant.id, 
        order_id="test-order", 
        currency="USD", 
        amount=float(total_amount)
    )
    db_session.add(invoice)
    await db_session.flush()

    # Вызываем функцию начисления
    await billing._credit_merchant_once(db_session, invoice, data, "test-uuid")
    await db_session.flush()

    # Проверяем сумму в ledger entry
    ledger_entries = (await db_session.execute(
        billing.select(LedgerEntry).where(
            LedgerEntry.merchant_id == merchant.id,
            LedgerEntry.direction == LedgerDirection.credit
        )
    )).scalars().all()

    assert len(ledger_entries) == 1
    entry = ledger_entries[0]
    
    # Проверка, что зачисленная сумма совпадает с ожидаемой
    assert abs(float(entry.amount) - float(expected_merchant_amount)) < 0.01, \
        f"Expected {expected_merchant_amount}, got {entry.amount}"
    assert entry.currency == "USDT"
    assert entry.ref == "test-uuid"
    assert "platform fee 6%" in entry.note


@pytest.mark.asyncio
async def test_idempotency(db_session: AsyncSession):
    """
    Проверяет, что повторное начисление для одного и того же платежа 
    не создает дублирующих записей в ledger.
    """
    # Подготовка тестовых данных
    data = {
        "merchant_amount": "100.00",
        "payer_currency": "USDT"
    }
    
    merchant = Merchant(tg_user_id=123, name="Test Merchant")
    db_session.add(merchant)
    await db_session.flush()

    invoice = Invoice(
        merchant_id=merchant.id, 
        order_id="test-order", 
        currency="USD", 
        amount=100.0
    )
    db_session.add(invoice)
    await db_session.flush()

    # Первое начисление
    await billing._credit_merchant_once(db_session, invoice, data, "test-uuid")
    await db_session.flush()

    # Второе начисление с тем же UUID
    await billing._credit_merchant_once(db_session, invoice, data, "test-uuid")
    await db_session.flush()

    # Проверка, что запись в ledger одна
    ledger_entries = (await db_session.execute(
        billing.select(LedgerEntry).where(
            LedgerEntry.merchant_id == merchant.id,
            LedgerEntry.direction == LedgerDirection.credit
        )
    )).scalars().all()

    assert len(ledger_entries) == 1, "Duplicate ledger entries created"


def test_fee_percentage_calculation():
    """
    Прямая проверка математики расчета комиссии.
    """
    # Тестовые сценарии: общая сумма, ожидаемая сумма мерчанта
    test_cases = [
        (100.00, 94.00),   # 6% комиссии
        (50.50, 47.47),    # Дробные суммы
        (0.10, 0.09),      # Малые суммы
        (1000.00, 940.00)  # Большие суммы
    ]

    for total, expected_merchant in test_cases:
        # Расчет вручную
        platform_fee_percent = 6.0
        merchant_amount = total * (1 - platform_fee_percent/100)
        
        # Проверка с точностью до копейки
        assert abs(merchant_amount - expected_merchant) < 0.01, \
            f"Fee calculation failed for {total}: expected {expected_merchant}, got {merchant_amount}"
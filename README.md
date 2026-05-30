# tg-crypto-pay

Telegram-нативная крипто-платёжка поверх процессинга 2328.io.

Принимай платежи в крипте со всего мира прямо внутри Telegram (Mini App,
без редиректов), бери свою комиссию в крипте через наценку на счёт.

## Что это

Продукт **поверх** 2328.io (вариант B):

- 2328.io под капотом = блокчейн-слой (кошельки, отслеживание сети, выплаты).
- Этот сервис = удобный UX в Telegram + твоя бизнес-логика и комиссия.

```
Покупатель (Telegram Mini App)
        │  без редиректа: QR + адрес прямо в приложении
        ▼
  Backend (FastAPI)  ──HMAC──▶  2328.io API   ──▶  блокчейн
        │  ◀── webhook (paid) ──────────────────────┘
        ▼
  Postgres (инвойсы, леджер, твоя комиссия в крипте)
```

## Комиссия в крипте

Через `price_markup` при создании платежа: мерчант хочет $100 → плательщику
выставляется $100 × (1 + markup) → разница оседает на твоём балансе 2328.io
в крипте. Настраивается per-merchant в `MERCHANTS` (см. ниже) или глобально.

## Стек

- Backend: Python 3.11 + FastAPI + SQLAlchemy 2 + Postgres (SQLite для локалки)
- Frontend: React + Vite + @telegram-apps/sdk (Telegram Mini App)

## Быстрый старт

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # заполни ключи 2328.io и токен бота
pytest -q                     # юнит-тесты (подпись HMAC и пр.)
uvicorn app.main:app --reload # http://localhost:8000/docs
```

Фронт:

```bash
cd frontend
npm install
npm run dev
```

## Безопасность (важно)

- API-ключи 2328.io только на бэкенде, НИКОГДА не в Mini App.
- Webhook: проверка HMAC-подписи (constant-time) + идемпотентность по uuid.
- initData Telegram проверяется на каждом запросе из Mini App.
- Вариант B = деньги мерчантов лежат на твоём балансе 2328.io до вывода
  (кастодиальная модель). Понимай юридические риски.

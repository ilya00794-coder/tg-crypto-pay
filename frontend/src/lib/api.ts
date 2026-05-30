// API client for the Mini App. Sends Telegram initData on every request so the
// backend can authenticate the merchant. Never holds any 2328.io secrets.

const TG = window.Telegram?.WebApp;

// In dev (outside Telegram) you can inject a fake initData via this env var so
// the app is testable in a normal browser.
const DEV_INIT_DATA = import.meta.env.VITE_DEV_INIT_DATA as string | undefined;

function initData(): string {
  return TG?.initData || DEV_INIT_DATA || "";
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export interface Merchant {
  tg_user_id: number;
  name: string;
  payout_address: string | null;
  payout_network: string | null;
  markup_percent: number | null;
}

export interface Invoice {
  order_id: string;
  gateway_uuid: string | null;
  status: string;
  currency: string;
  amount: number;
  markup_percent: number;
  pay_url: string | null;
  tg_deeplink: string | null;
  pay_address: string | null;
  payer_currency: string | null;
  payer_amount: string | null;
  network: string | null;
  qr: string | null;
  txid: string | null;
}

export interface BalanceEntry {
  currency: string;
  available: string;
}

export interface Payout {
  order_id: string;
  status: string;
  currency: string;
  network: string;
  amount: number;
  to_address: string;
  txid: string | null;
  error_type: string | null;
}

export const api = {
  me: () => req<Merchant>("GET", "/api/me"),
  updateMe: (b: Partial<Merchant>) => req<Merchant>("PATCH", "/api/me", b),
  createInvoice: (b: {
    amount: number;
    currency: string;
    order_id: string;
    to_currency?: string;
    network?: string;
    description?: string;
  }) => req<Invoice>("POST", "/api/invoices", b),
  getInvoice: (orderId: string) =>
    req<Invoice>("GET", `/api/invoices/${encodeURIComponent(orderId)}`),
  balance: () => req<{ balances: BalanceEntry[] }>("GET", "/api/balance"),
  payout: (b: {
    currency: string;
    network: string;
    amount: number;
    to_address: string;
    order_id: string;
  }) => req<Payout>("POST", "/api/payouts", b),
};

export { TG };

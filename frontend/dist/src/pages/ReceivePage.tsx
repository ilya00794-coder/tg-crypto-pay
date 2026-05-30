import { useEffect, useState } from "react";
import { api, Invoice } from "../lib/api";

const NETWORKS: Record<string, string> = {
  USDT: "TRX-TRC20",
  TON: "TON",
  BTC: "BTC",
  ETH: "ETH-ERC20",
  TRX: "TRX-TRC20",
};

// Terminal states: stop polling once reached.
const DONE = new Set(["paid", "overpaid", "cancel", "underpaid", "aml_lock"]);

export default function ReceivePage() {
  const [amount, setAmount] = useState("100");
  const [currency, setCurrency] = useState("USD");
  const [crypto, setCrypto] = useState("USDT");
  const [description, setDescription] = useState("");
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    setError("");
    setLoading(true);
    try {
      const inv = await api.createInvoice({
        amount: parseFloat(amount),
        currency,
        order_id: `${Date.now()}`,
        to_currency: crypto,
        network: NETWORKS[crypto],
        description,
      });
      setInvoice(inv);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  // Poll invoice status until terminal.
  useEffect(() => {
    if (!invoice || DONE.has(invoice.status)) return;
    const id = setInterval(async () => {
      try {
        const fresh = await api.getInvoice(invoice.order_id.replace(/^m\d+-/, ""));
        setInvoice(fresh);
        if (DONE.has(fresh.status)) {
          clearInterval(id);
          if (fresh.status === "paid" || fresh.status === "overpaid") {
            window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
          }
        }
      } catch {
        /* keep polling */
      }
    }, 4000);
    return () => clearInterval(id);
  }, [invoice]);

  function copy(text: string) {
    navigator.clipboard?.writeText(text);
  }

  if (invoice) {
    const paid = invoice.status === "paid" || invoice.status === "overpaid";
    return (
      <div className="card center">
        <h2>Оплата счёта</h2>
        <span className={`status ${invoice.status}`}>{statusLabel(invoice.status)}</span>
        {!paid && invoice.qr && <img className="qr" src={invoice.qr} alt="QR" />}
        {paid && <div style={{ fontSize: 56, margin: "16px 0" }}>✅</div>}

        {!paid && (
          <>
            <div className="row">
              <span className="k">К оплате</span>
              <span>
                {invoice.payer_amount} {invoice.payer_currency}
              </span>
            </div>
            <div className="row">
              <span className="k">Сеть</span>
              <span>{invoice.network}</span>
            </div>
            <label>Адрес для перевода</label>
            <div className="mono">{invoice.pay_address}</div>
            <div className="copy" onClick={() => copy(invoice.pay_address || "")}>
              📋 Скопировать адрес
            </div>
          </>
        )}

        {paid && (
          <div className="row">
            <span className="k">Tx</span>
            <span className="mono">{invoice.txid?.slice(0, 18)}…</span>
          </div>
        )}

        <button className="primary" onClick={() => setInvoice(null)}>
          {paid ? "Новый счёт" : "← Назад"}
        </button>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Принять оплату</h2>
      <label>Сумма (вы получите)</label>
      <input
        type="number"
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <label>Валюта счёта</label>
      <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
        {["USD", "EUR", "RUB", "KZT", "UAH"].map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>
      <label>Криптовалюта оплаты</label>
      <select value={crypto} onChange={(e) => setCrypto(e.target.value)}>
        {Object.keys(NETWORKS).map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>
      <label>Описание (необязательно)</label>
      <input value={description} onChange={(e) => setDescription(e.target.value)} />
      {error && <div className="error">{error}</div>}
      <button className="primary" onClick={create} disabled={loading || !amount}>
        {loading ? "Создаём…" : "Создать счёт"}
      </button>
      <p className="hint" style={{ marginTop: 12 }}>
        Оплата проходит прямо здесь, без перехода на сторонние сайты.
      </p>
    </div>
  );
}

function statusLabel(s: string): string {
  return (
    {
      created: "Ожидание",
      check: "Ожидаем оплату",
      paid: "Оплачено",
      overpaid: "Оплачено (с избытком)",
      underpaid: "Недоплата",
      cancel: "Отменён / истёк",
      aml_lock: "Заблокировано AML",
    }[s] || s
  );
}

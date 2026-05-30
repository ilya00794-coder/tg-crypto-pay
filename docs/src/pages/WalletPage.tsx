import { useEffect, useState } from "react";
import { api, BalanceEntry, Merchant } from "../lib/api";

const NETWORKS: Record<string, string> = {
  USDT: "TRX-TRC20",
  TON: "TON",
  BTC: "BTC",
  ETH: "ETH-ERC20",
  TRX: "TRX-TRC20",
};

export default function WalletPage() {
  const [balances, setBalances] = useState<BalanceEntry[]>([]);
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // payout form
  const [currency, setCurrency] = useState("USDT");
  const [amount, setAmount] = useState("");
  const [address, setAddress] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [okMsg, setOkMsg] = useState("");

  async function load() {
    setError("");
    try {
      const [b, m] = await Promise.all([api.balance(), api.me()]);
      setBalances(b.balances);
      setMerchant(m);
      if (m.payout_address) setAddress(m.payout_address);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function withdraw() {
    setError("");
    setOkMsg("");
    setSubmitting(true);
    try {
      const p = await api.payout({
        currency,
        network: NETWORKS[currency],
        amount: parseFloat(amount),
        to_address: address,
        order_id: `${Date.now()}`,
      });
      setOkMsg(`Вывод создан: ${p.status}. ${p.amount} ${p.currency} → ${shorten(address)}`);
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
      setAmount("");
      await load();
    } catch (e) {
      setError((e as Error).message);
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="card center">Загрузка…</div>;

  const available = balances.find((b) => b.currency === currency)?.available || "0";

  return (
    <>
      <div className="card">
        <h2>Баланс</h2>
        {balances.length === 0 && <p className="hint">Пока пусто. Примите первый платёж.</p>}
        {balances.map((b) => (
          <div className="row" key={b.currency}>
            <span className="k">{b.currency}</span>
            <span className="bal" style={{ fontSize: 20 }}>
              {fmt(b.available)} <small>{b.currency}</small>
            </span>
          </div>
        ))}
        {merchant && (
          <p className="hint" style={{ marginTop: 10 }}>
            Ваша комиссия платформы: {merchant.markup_percent}% — заложена в каждый счёт.
          </p>
        )}
      </div>

      <div className="card">
        <h2>Вывод средств</h2>
        <label>Валюта</label>
        <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
          {Object.keys(NETWORKS).map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <label>
          Сумма (доступно: {fmt(available)} {currency})
        </label>
        <input
          type="number"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <label>Адрес получателя ({NETWORKS[currency]})</label>
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
        {error && <div className="error">{error}</div>}
        {okMsg && <div style={{ color: "#6bd98f", fontSize: 14, marginTop: 8 }}>{okMsg}</div>}
        <button
          className="primary"
          onClick={withdraw}
          disabled={submitting || !amount || !address || parseFloat(amount) <= 0}
        >
          {submitting ? "Отправка…" : "Вывести"}
        </button>
      </div>
    </>
  );
}

function fmt(s: string): string {
  const n = parseFloat(s);
  if (Number.isNaN(n)) return s;
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 8 });
}

function shorten(a: string): string {
  return a.length > 14 ? `${a.slice(0, 8)}…${a.slice(-4)}` : a;
}

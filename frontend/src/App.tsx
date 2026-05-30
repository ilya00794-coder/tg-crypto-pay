import { useEffect, useState } from "react";
import ReceivePage from "./pages/ReceivePage";
import WalletPage from "./pages/WalletPage";

type Tab = "receive" | "wallet";

export default function App() {
  const [tab, setTab] = useState<Tab>("receive");

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();
  }, []);

  return (
    <div className="app">
      <div className="tabs">
        <button
          className={`tab ${tab === "receive" ? "active" : ""}`}
          onClick={() => setTab("receive")}
        >
          Принять оплату
        </button>
        <button
          className={`tab ${tab === "wallet" ? "active" : ""}`}
          onClick={() => setTab("wallet")}
        >
          Кошелёк
        </button>
      </div>
      {tab === "receive" ? <ReceivePage /> : <WalletPage />}
    </div>
  );
}

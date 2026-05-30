import { useEffect, useState } from "react";
import ReceivePage from "./pages/ReceivePage";
import WalletPage from "./pages/WalletPage";

const WebApp = window.Telegram?.WebApp;

type Tab = "receive" | "wallet";

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("receive");

  useEffect(() => {
    if (WebApp) {
      WebApp.ready();
      WebApp.expand();
      WebApp.setHeaderColor('#17212b');
      WebApp.setBackgroundColor('#17212b');
    }
  }, []);

  return (
    <div className="app">
      <div className="tabs">
        <button 
          className={activeTab === "receive" ? "active" : ""}
          onClick={() => setActiveTab("receive")}
        >
          Оплата
        </button>
        <button 
          className={activeTab === "wallet" ? "active" : ""}
          onClick={() => setActiveTab("wallet")}
        >
          Кошелек
        </button>
      </div>
      <div className="content">
        {activeTab === "receive" ? <ReceivePage /> : <WalletPage />}
      </div>
    </div>
  );
}
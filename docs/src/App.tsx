import React, { useEffect } from "react";
import ReceivePage from "./pages/ReceivePage";
import WalletPage from "./pages/WalletPage";

const WebApp = window.Telegram?.WebApp;

type Tab = "receive" | "wallet";

export default function App() {
  const [activeTab, setActiveTab] = React.useState<Tab>("receive");

  useEffect(() => {
    console.log('App mounted');
    if (WebApp) {
      console.log('WebApp detected');
      WebApp.ready();
      WebApp.expand();
      
      // Безопасные проверки
      if (WebApp.setHeaderColor) {
        WebApp.setHeaderColor('#17212b');
      }
      if (WebApp.setBackgroundColor) {
        WebApp.setBackgroundColor('#17212b');
      }
    } else {
      console.error('WebApp not found');
    }
  }, []);

  return (
    <div className="app" style={{ 
      backgroundColor: '#17212b', 
      color: 'white', 
      minHeight: '100vh',
      padding: '20px'
    }}>
      <h1>🚀 Crypto Pay</h1>
      <div className="tabs">
        <button 
          style={{
            backgroundColor: activeTab === "receive" ? '#4a90e2' : '#708499',
            color: 'white',
            padding: '10px',
            margin: '0 10px',
            border: 'none',
            borderRadius: '5px'
          }}
          onClick={() => setActiveTab("receive")}
        >
          Оплата
        </button>
        <button 
          style={{
            backgroundColor: activeTab === "wallet" ? '#4a90e2' : '#708499',
            color: 'white',
            padding: '10px',
            margin: '0 10px',
            border: 'none',
            borderRadius: '5px'
          }}
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
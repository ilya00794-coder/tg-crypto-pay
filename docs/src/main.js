import React from 'https://unpkg.com/react@18/es/react.js';
import ReactDOM from 'https://unpkg.com/react-dom@18/es/react-dom.js';

const App = () => {
    const [activeTab, setActiveTab] = React.useState('receive');
    
    React.useEffect(() => {
        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
        }
    }, []);

    return React.createElement(
        'div', 
        { 
            style: { 
                backgroundColor: '#17212b', 
                color: 'white', 
                minHeight: '100vh',
                fontFamily: 'Arial, sans-serif',
                padding: '20px'
            } 
        },
        React.createElement('h1', null, '🚀 Crypto Pay'),
        React.createElement('div', { 
            style: { 
                display: 'flex', 
                justifyContent: 'center', 
                marginBottom: '20px' 
            } 
        },
            React.createElement('button', { 
                onClick: () => setActiveTab('receive'),
                style: { 
                    backgroundColor: activeTab === 'receive' ? '#4a90e2' : '#708499',
                    color: 'white', 
                    border: 'none', 
                    padding: '10px 20px', 
                    margin: '0 10px',
                    borderRadius: '5px'
                }
            }, 'Оплата'),
            React.createElement('button', { 
                onClick: () => setActiveTab('wallet'),
                style: { 
                    backgroundColor: activeTab === 'wallet' ? '#4a90e2' : '#708499',
                    color: 'white', 
                    border: 'none', 
                    padding: '10px 20px', 
                    margin: '0 10px',
                    borderRadius: '5px'
                }
            }, 'Кошелек')
        ),
        React.createElement('div', null, 
            activeTab === 'receive' 
                ? React.createElement('p', null, 'Страница оплаты') 
                : React.createElement('p', null, 'Страница кошелька')
        )
    );
};

ReactDOM.createRoot(document.getElementById('root')).render(
    React.createElement(App)
);
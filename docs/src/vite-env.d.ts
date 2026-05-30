/// <reference types="vite/client" />

interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  close: () => void;
  MainButton?: {
    show: () => void;
    hide: () => void;
    setText: (text: string) => void;
  };
  initDataUnsafe: {
    user?: {
      id: number;
      first_name?: string;
      last_name?: string;
      username?: string;
    };
  };
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp;
  };
}
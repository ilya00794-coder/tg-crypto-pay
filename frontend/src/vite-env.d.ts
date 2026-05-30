/// <reference types="vite/client" />

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; username?: string } };
  ready: () => void;
  expand: () => void;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  showAlert?: (msg: string) => void;
  HapticFeedback?: { notificationOccurred: (t: "error" | "success" | "warning") => void };
}

interface Window {
  Telegram?: { WebApp?: TelegramWebApp };
}

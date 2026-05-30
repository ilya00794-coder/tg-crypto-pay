import os
from dotenv import load_dotenv
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://default-miniapp.com')
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("Отсутствует токен Telegram бота. Проверьте .env файл.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    # Логирование для отладки
    print(f"Получен start от {update.effective_user.username}")
    
    if context.args:
        try:
            payload_type, *payload_data = context.args[0].split('_')
            
            if payload_type == 'pay':
                # Разбор параметров платежа
                order_id, amount, currency = payload_data
                
                # Создание кнопки оплаты в Mini App
                keyboard = [[InlineKeyboardButton(
                    "Оплатить криптовалютой 💳🔒", 
                    web_app=WebAppInfo(url=f"{WEBAPP_URL}?order={order_id}")
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"Счёт на оплату: {amount} {currency}\n"
                    "Нажмите кнопку для моментальной оплаты в криптовалюте",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("Неверный формат ссылки")
        except Exception as e:
            await update.message.reply_text(f"Ошибка обработки платежа: {e}")
    else:
        # Стандартное приветствие
        await update.message.reply_text(
            "🚀 Crypto Pay Bot\n"
            "Быстрые криптоплатежи без редиректов\n\n"
            "Отправьте ссылку от продавца для оплаты"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка по боту"""
    help_text = (
        "🤖 Crypto Pay Bot - платежи в криптовалюте\n\n"
        "Как это работает:\n"
        "1. Продавец генерирует ссылку оплаты\n"
        "2. Вы получаете ссылку и жмёте кнопку\n"
        "3. Моментальная оплата в крипте\n\n"
        "Поддержка: USDT, TON, BTC\n"
        "Комиссия: 6% от платежа"
    )
    await update.message.reply_text(help_text)

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запуск бота
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
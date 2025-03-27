from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import subprocess
import os

# Функции для управления сервисами
async def start_service(update: Update, context: ContextTypes.DEFAULT_TYPE, service_name: str):
    # Проверяем, что команда отправлена из правильного чата
    if str(update.message.chat_id) != os.getenv("CHAT_ID"):
        await update.message.reply_text("У вас нет доступа к управлению ботом.")
        return
    subprocess.run(["docker-compose", "start", service_name])
    await update.message.reply_text(f"{service_name} запущен!")

async def stop_service(update: Update, context: ContextTypes.DEFAULT_TYPE, service_name: str):
    if str(update.message.chat_id) != os.getenv("CHAT_ID"):
        await update.message.reply_text("У вас нет доступа к управлению ботом.")
        return
    subprocess.run(["docker-compose", "stop", service_name])
    await update.message.reply_text(f"{service_name} остановлен!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != os.getenv("CHAT_ID"):
        await update.message.reply_text("У вас нет доступа к управлению ботом.")
        return
    result = subprocess.run(["docker-compose", "ps"], capture_output=True, text=True)
    await update.message.reply_text(f"Статус сервисов:\n{result.stdout}")

async def update_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != os.getenv("CHAT_ID"):
        await update.message.reply_text("У вас нет доступа к управлению ботом.")
        return
    subprocess.run(["git", "pull"])
    subprocess.run(["docker-compose", "build"])
    subprocess.run(["docker-compose", "up", "-d"])
    await update.message.reply_text("Код обновлен, контейнеры перезапущены!")

async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != os.getenv("CHAT_ID"):
        await update.message.reply_text("У вас нет доступа к управлению ботом.")
        return
    service_name = context.args[0] if context.args else "trade_manager"
    result = subprocess.run(["docker-compose", "logs", "--tail=50", service_name], capture_output=True, text=True)
    await update.message.reply_text(f"Логи {service_name}:\n{result.stdout}")

# Команды для каждого модуля
async def start_historical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_service(update, context, "populate_historical_data")

async def stop_historical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_service(update, context, "populate_historical_data")

async def start_static(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_service(update, context, "populate_static_data")

async def stop_static(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_service(update, context, "populate_static_data")

async def start_trade_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_service(update, context, "trade_manager")

async def stop_trade_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_service(update, context, "trade_manager")

async def start_trading_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_service(update, context, "trading_engine")

async def stop_trading_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_service(update, context, "trading_engine")

def main():
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start_historical", start_historical))
    app.add_handler(CommandHandler("stop_historical", stop_historical))
    app.add_handler(CommandHandler("start_static", start_static))
    app.add_handler(CommandHandler("stop_static", stop_static))
    app.add_handler(CommandHandler("start_trade_manager", start_trade_manager))
    app.add_handler(CommandHandler("stop_trade_manager", stop_trade_manager))
    app.add_handler(CommandHandler("start_trading_engine", start_trading_engine))
    app.add_handler(CommandHandler("stop_trading_engine", stop_trading_engine))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("update", update_code))
    app.add_handler(CommandHandler("logs", get_logs))
    app.run_polling()

if __name__ == "__main__":
    main()
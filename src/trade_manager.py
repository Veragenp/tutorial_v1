import logging
import time
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bybit_api import BybitAPI
from google_sheets import GoogleSheetsClient
from telegram_bot import send_telegram_message

class TradeManager:
    def __init__(self, api_key, api_secret, telegram_token, chat_id):
        self.logger = logging.getLogger(__name__)
        self.bybit = BybitAPI(api_key, api_secret)
        self.sheets = GoogleSheetsClient()
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.pending_confirmation = {}  # Хранит данные о сделках, ожидающих подтверждения
        self.max_trades = 5
        self.running = True

        # Настройка Telegram-бота для подтверждений
        self.app = Application.builder().token(telegram_token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_confirmation))
        self.app.run_polling()

    async def handle_confirmation(self, update, context):
        """Обрабатывает ответы да/нет от пользователя в Telegram."""
        message = update.message.text.lower()
        chat_id = update.effective_chat.id
        if chat_id != int(self.chat_id):
            return

        if message not in ["да", "нет"]:
            await update.message.reply_text("Пожалуйста, ответьте 'да' или 'нет'.")
            return

        # Проверяем, есть ли ожидающая сделка
        if chat_id in self.pending_confirmation:
            trade_data = self.pending_confirmation[chat_id]
            if message == "да":
                self.execute_trade(trade_data)
                await update.message.reply_text("Сделка подтверждена и выполнена.")
            else:
                self.cancel_trade(trade_data, "отменено: пользователь отказался")
                await update.message.reply_text("Сделка отменена.")
            del self.pending_confirmation[chat_id]
        else:
            await update.message.reply_text("Нет ожидающих сделок для подтверждения.")

    def process_pending_trades(self, trades, sheet_name):
        """Обрабатывает ожидающие сделки."""
        sheet = self.sheets.get_sheet(sheet_name)
        if not sheet:
            self.logger.error(f"Не удалось получить лист {sheet_name}")
            return

        # Проверяем лимит на открытые сделки
        open_positions = self.bybit.get_open_positions()
        if open_positions >= self.max_trades:
            for trade in trades:
                row_idx = trade["row_idx"]
                self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Столбец F
                self.sheets.update_cell(sheet, row_idx, 7, "отменено: лимит сделок")  # Столбец G
                send_telegram_message(f"Сделка для {trade['coin']} отменена: достигнут лимит в {self.max_trades} сделок.")
            return

        for trade in trades:
            # Проверяем наличие стоп-лосса
            if not trade["stop_loss"]:
                row_idx = trade["row_idx"]
                self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Столбец F
                self.sheets.update_cell(sheet, row_idx, 7, "отменено: стоп-лосс не установлен")  # Столбец G
                send_telegram_message(f"Сделка для {trade['coin']} отменена: стоп-лосс не установлен.")
                continue

            # Обновляем статус на "вход, ожидание"
            row_idx = trade["row_idx"]
            self.sheets.update_cell(sheet, row_idx, 7, "вход, ожидание")  # Столбец G

            # Отправляем запрос на подтверждение
            message = (
                f"Подтвердите вход в сделку для {trade['coin']}:\n"
                f"Тип: {trade['side']}\n"
                f"Цена: {trade['entry_price']}\n"
                f"Количество: {trade['qty']}\n"
                f"Тейк-профит: {trade['take_profit']}\n"
                f"Стоп-лосс: {trade['stop_loss']}\n"
                "Ответьте 'да' или 'нет'."
            )
            send_telegram_message(message)
            self.pending_confirmation[int(self.chat_id)] = {
                "trade": trade,
                "sheet": sheet,
                "sheet_name": sheet_name
            }

    def execute_trade(self, trade_data):
        """Выполняет сделку после подтверждения."""
        trade = trade_data["trade"]
        sheet = trade_data["sheet"]
        sheet_name = trade_data["sheet_name"]

        order_id = self.bybit.place_limit_order(
            symbol=trade["coin"],
            side=trade["side"],
            qty=trade["qty"],
            price=trade["entry_price"],
            take_profit=trade["take_profit"],
            stop_loss=trade["stop_loss"]
        )

        row_idx = trade["row_idx"]
        if order_id:
            self.sheets.update_cell(sheet, row_idx, 7, "вход выполнен")  # Столбец G
            send_telegram_message(f"Сделка для {trade['coin']} ({sheet_name}) выполнена. Order ID: {order_id}")
        else:
            self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Столбец F
            self.sheets.update_cell(sheet, row_idx, 7, "ошибка входа")  # Столбец G
            send_telegram_message(f"Ошибка входа в сделку для {trade['coin']} ({sheet_name}).")

    def cancel_trade(self, trade_data, reason):
        """Отменяет сделку."""
        trade = trade_data["trade"]
        sheet = trade_data["sheet"]
        row_idx = trade["row_idx"]
        self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Столбец F
        self.sheets.update_cell(sheet, row_idx, 7, reason)  # Столбец G
        send_telegram_message(f"Сделка для {trade['coin']} отменена: {reason}")

    def run(self):
        """Запускает цикл проверки Google Sheets на наличие новых сделок."""
        self.logger.info("Запуск TradeManager...")
        print("Запуск TradeManager...")

        try:
            while self.running:
                for sheet_name in ["long", "short"]:
                    trades = self.sheets.get_pending_trades(sheet_name)
                    if trades:
                        self.logger.info(f"Найдено {len(trades)} ожидающих сделок на листе {sheet_name}")
                        print(f"Найдено {len(trades)} ожидающих сделок на листе {sheet_name}")
                        self.process_pending_trades(trades, sheet_name)
                time.sleep(60)  # Проверяем каждые 60 секунд
        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            print("Остановлено пользователем")
            self.running = False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в цикле: {e}")
            print(f"Неожиданная ошибка в цикле: {e}")
            self.running = False
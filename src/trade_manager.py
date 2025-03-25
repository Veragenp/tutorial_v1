import logging
import os
import time
import threading
import asyncio
import requests
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bybit_api import BybitAPI
from google_sheets import GoogleSheetsClient
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID  # Добавляем импорт

# Настройка логирования
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
log_dir = os.path.join(project_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "trade_manager.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class TradeManager:
    def __init__(self, api_key, api_secret, telegram_token, chat_id):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация TradeManager")
        print("Инициализация TradeManager")

        self.bybit = BybitAPI(api_key, api_secret)
        self.sheets = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)  # Обновляем вызов
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.pending_confirmation = {}
        self.max_trades = 5
        self.running = True

        try:
            self.app = Application.builder().token(telegram_token).build()
            self.logger.info("Telegram Application инициализирован")
        except Exception as e:
            self.logger.error(f"Ошибка при инициализации Telegram Application: {e}")
            raise

        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_confirmation))
        self.app.add_handler(CallbackQueryHandler(self.handle_button))

    async def handle_confirmation(self, update, context):
        self.logger.debug("Получен ответ от пользователя в Telegram")
        message = update.message.text.lower()
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        if chat_id != int(self.chat_id):
            self.logger.warning(f"Получен ответ от неизвестного chat_id: {chat_id}")
            return

        if message not in ["да", "нет"]:
            self.logger.debug(f"Некорректный ответ: {message}")
            await update.message.reply_text("Пожалуйста, ответьте 'да' или 'нет'.")
            return

        key = (chat_id, message_id)
        if key in self.pending_confirmation:
            trade_data = self.pending_confirmation[key]
            if message == "да":
                self.logger.info(f"Сделка подтверждена пользователем: {trade_data['trade']['coin']}")
                self.execute_trade(trade_data)
                await update.message.reply_text("Сделка подтверждена и выполнена.")
            else:
                self.logger.info(f"Сделка отменена пользователем: {trade_data['trade']['coin']}")
                self.cancel_trade(trade_data, "отменено: пользователь отказался")
                await update.message.reply_text("Сделка отменена.")
            del self.pending_confirmation[key]
        else:
            self.logger.warning("Нет ожидающих сделок для подтверждения")
            await update.message.reply_text("Нет ожидающих сделок для подтверждения.")

    async def handle_button(self, update, context):
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id
        message_id = query.message.message_id
        action = query.data

        key = (chat_id, message_id)
        if key in self.pending_confirmation:
            trade_data = self.pending_confirmation[key]
            if action == "yes":
                self.logger.info(f"Сделка подтверждена пользователем (кнопка): {trade_data['trade']['coin']}")
                self.execute_trade(trade_data)
                await query.message.reply_text("Сделка подтверждена и выполнена.")
            elif action == "no":
                self.logger.info(f"Сделка отменена пользователем (кнопка): {trade_data['trade']['coin']}")
                self.cancel_trade(trade_data, "отменено: пользователь отказался")
                await query.message.reply_text("Сделка отменена.")
            del self.pending_confirmation[key]
        else:
            self.logger.warning("Нет ожидающих сделок для подтверждения")
            await query.message.reply_text("Нет ожидающих сделок для подтверждения.")

    def send_telegram_message(self, text, with_buttons=False):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        if with_buttons:
            keyboard = [
                [
                    InlineKeyboardButton("Да", callback_data="yes"),
                    InlineKeyboardButton("Нет", callback_data="no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            payload["reply_markup"] = reply_markup.to_dict()
            self.logger.debug(f"Кнопки добавлены: {keyboard}")

        self.logger.debug(f"Отправка сообщения в Telegram: URL={url}, Payload={payload}")
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            self.logger.info(f"Сообщение отправлено в Telegram: {text}")
            message_id = response.json().get("result", {}).get("message_id")
            return message_id
        except Exception as e:
            self.logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
            return None

    def process_pending_trades(self, trades):
        open_positions = self.bybit.get_open_positions()
        self.logger.info(f"Открытых позиций: {open_positions}")
        print(f"Открытых позиций: {open_positions}")

        if open_positions >= self.max_trades:
            self.logger.warning(f"Достигнут лимит открытых сделок ({self.max_trades})")
            for trade in trades:
                self.cancel_trade(
                    {
                        "trade": trade,
                        "sheet": self.sheets.get_sheet(trade["sheet"]),
                        "sheet_name": trade["sheet"]
                    },
                    "отменено: лимит сделок"
                )
            return

        for trade in trades:
            sheet_name = trade["sheet"]
            sheet = self.sheets.get_sheet(sheet_name)
            if not sheet:
                self.logger.error(f"Не удалось получить лист {sheet_name}")
                continue

            if not trade["stop_loss"]:
                row_idx = trade["row"]
                self.sheets.update_cell(sheet, row_idx, 6, "FALSE")
                self.sheets.update_cell(sheet, row_idx, 7, "отменено: стоп-лосс не установлен")
                self.send_telegram_message(f"Сделка для {trade['coin']} отменена: стоп-лосс не установлен.")
                continue

            trade_key = (trade["sheet"], trade["row"])
            already_pending = any(
                data["trade"]["sheet"] == trade["sheet"] and data["trade"]["row"] == trade["row"]
                for data in self.pending_confirmation.values()
            )
            if already_pending:
                self.logger.debug(f"Сделка {trade['coin']} уже ожидает подтверждения, пропускаем")
                continue

            row_idx = trade["row"]
            self.sheets.update_trade_status(sheet_name, row_idx, "вход, ожидание")

            message = (
                f"Подтвердите вход в сделку для {trade['coin']}:\n"
                f"Тип: {trade['side']}\n"
                f"Цена: {trade['entry_price']}\n"
                f"Количество: {trade['qty']}\n"
                f"Тейк-профит: {trade['take_profit'] if trade['take_profit'] else 'не установлен'}\n"
                f"Стоп-лосс: {trade['stop_loss']}\n"
            )
            self.logger.info(f"Отправка запроса на подтверждение: {trade['coin']}")
            message_id = self.send_telegram_message(message, with_buttons=True)
            if message_id:
                key = (int(self.chat_id), message_id)
                self.pending_confirmation[key] = {
                    "trade": trade,
                    "sheet": sheet,
                    "sheet_name": sheet_name
                }
            else:
                self.logger.error(f"Не удалось получить message_id для сделки {trade['coin']}")

    def execute_trade(self, trade_data):
        trade = trade_data["trade"]
        sheet = trade_data["sheet"]
        sheet_name = trade_data["sheet_name"]

        open_positions = self.bybit.get_open_positions()
        if open_positions >= self.max_trades:
            self.logger.warning(f"Достигнут лимит открытых сделок ({self.max_trades}) при выполнении")
            self.cancel_trade(trade_data, "отменено: лимит сделок")
            return

        order_id = self.bybit.place_limit_order(
            symbol=trade["coin"],
            side=trade["side"],
            qty=trade["qty"],
            price=trade["entry_price"],
            take_profit=trade["take_profit"],
            stop_loss=trade["stop_loss"]
        )

        row_idx = trade["row"]
        if order_id:
            self.sheets.update_trade_status(sheet_name, row_idx, "вход выполнен")
            self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Сбрасываем флаг TRUE
            self.send_telegram_message(f"Сделка для {trade['coin']} ({sheet_name}) выполнена. Order ID: {order_id}")
            self.send_telegram_message("Стоп-лосс установлен")
        else:
            self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Сбрасываем флаг TRUE
            self.sheets.update_trade_status(sheet_name, row_idx, "ошибка входа")
            self.send_telegram_message(f"Ошибка входа в сделку для {trade['coin']} ({sheet_name}).")

    def cancel_trade(self, trade_data, reason):
        trade = trade_data["trade"]
        sheet = trade_data["sheet"]
        sheet_name = trade_data["sheet_name"]
        row_idx = trade["row"]
        self.sheets.cancel_trade(sheet_name, row_idx)
        self.sheets.update_trade_status(sheet_name, row_idx, reason)
        self.sheets.update_cell(sheet, row_idx, 6, "FALSE")  # Сбрасываем флаг TRUE
        self.send_telegram_message(f"Сделка для {trade['coin']} отменена: {reason}")

    def check_trades(self):
        try:
            while self.running:
                try:
                    trades = self.sheets.get_pending_trades()
                    if trades:
                        self.logger.info(f"Найдено {len(trades)} ожидающих сделок")
                        print(f"Найдено {len(trades)} ожидающих сделок")
                        self.process_pending_trades(trades)
                    else:
                        self.logger.debug("Ожидающие сделки не найдены")
                        print("Ожидающие сделки не найдены")
                except Exception as e:
                    self.logger.error(f"Ошибка при получении ожидающих сделок: {e}")
                    print(f"Ошибка при получении ожидающих сделок: {e}")
                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            print("Остановлено пользователем")
            self.running = False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в цикле: {e}")
            print(f"Неожиданная ошибка в цикле: {e}")
            self.running = False

    def run(self):
        self.logger.info("Запуск TradeManager...")
        print("Запуск TradeManager...")

        check_thread = threading.Thread(target=self.check_trades)
        check_thread.daemon = True
        check_thread.start()

        try:
            self.app.run_polling(allowed_updates=[])
        except Exception as e:
            self.logger.error(f"Ошибка в Telegram polling: {e}")
            print(f"Ошибка в Telegram polling: {e}")
            self.running = False

if __name__ == "__main__":
    from config import BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_TOKEN, CHAT_ID

    trade_manager = TradeManager(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        telegram_token=TELEGRAM_TOKEN,
        chat_id=CHAT_ID
    )
    trade_manager.run()
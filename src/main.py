import logging
import threading
import time
from google_sheets import GoogleSheetsClient, populate_database
from bybit_api import BybitAPI
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def main():
    # Логируем запуск бота
    logging.info("Запуск бота")

    # Инициализация клиентов
    sheets_client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
    bybit_api = BybitAPI()

    # Запуск WebSocket в отдельном потоке для получения текущих цен
    threading.Thread(target=bybit_api.start_websocket, daemon=True).start()

    # Даём WebSocket несколько секунд на подключение
    time.sleep(5)

    # Заполнение листа database
    logging.info("Начало заполнения листа database")
    populate_database(bybit_api, sheets_client)
    logging.info("Заполнение листа database завершено")

if __name__ == "__main__":
    main()


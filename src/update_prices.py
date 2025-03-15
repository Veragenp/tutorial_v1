import logging
import threading
import time
from google_sheets import GoogleSheetsClient
from bybit_api import BybitAPI
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def update_prices():
    # Логируем запуск скрипта
    logger = logging.getLogger(__name__)
    logger.info("Запуск update_prices.py: начало обновления текущих цен")

    # Инициализация клиентов
    sheets_client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
    bybit_api = BybitAPI()

    # Запуск WebSocket в отдельном потоке для получения текущих цен
    threading.Thread(target=bybit_api.start_websocket, daemon=True).start()

    # Даём WebSocket несколько секунд на подключение
    logger.info("Ожидание подключения WebSocket")
    time.sleep(5)

    # Получение листа database
    logger.info("Попытка получить лист database")
    sheet = sheets_client.get_sheet("database")
    if not sheet:
        logger.error("Не удалось получить лист database")
        return

    # Бесконечный цикл для обновления цен
    logger.info("Начало цикла обновления текущих цен")
    while True:
        # Получение всех данных таблицы для извлечения символов
        all_data = sheet.get_all_values()
        if len(all_data) < 2:  # Проверяем, есть ли данные (учитывая заголовок)
            logger.error("В листе database отсутствуют монеты, сначала запустите populate_static_data.py")
            return

        # Извлекаем символы из колонки A (пропускаем заголовок)
        symbols = [row[0] for row in all_data[1:] if row[0]]
        logger.info(f"Получено {len(symbols)} символов для обновления цен")

        # Обновление текущей цены для каждой монеты
        for row_idx, symbol in enumerate(symbols, start=2):
            price = bybit_api.get_current_price(symbol)
            if price:
                logger.info(f"Обновление цены для {symbol}: {price}")
                sheets_client.update_cell(sheet, row_idx, 20, price)  # Колонка T (Текущая цена)
            else:
                logger.warning(f"Нет текущей цены для {symbol}")

        # Ожидание 60 секунд перед следующим обновлением
        logger.info("Ожидание 60 секунд перед следующим обновлением")
        time.sleep(60)

if __name__ == "__main__":
    update_prices()
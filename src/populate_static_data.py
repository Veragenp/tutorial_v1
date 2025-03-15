import logging
from google_sheets import GoogleSheetsClient
from bybit_api import BybitAPI
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID, BYBIT_API_KEY, BYBIT_API_SECRET
import time

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def populate_static_data():
    # Логируем запуск скрипта
    logger = logging.getLogger(__name__)
    logger.info("Запуск populate_static_data.py: обновление статичных данных")

    # Инициализация клиентов
    sheets_client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
    bybit_api = BybitAPI(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)

    # Получение листа database
    logger.info("Попытка получить лист database")
    sheet = sheets_client.get_sheet("database")
    if not sheet:
        logger.error("Не удалось получить лист database")
        return

    # Получение списка фьючерсов
    logger.info("Получение списка фьючерсов")
    symbols = bybit_api.get_futures_instruments() # Теперь возвращает все символы
    logger.info(f"Получено {len(symbols)} символов")
    if not symbols:
        logger.error("Не удалось получить список инструментов")
        return

    # Проверка заголовков
    headers = sheet.row_values(1)
    expected_headers = [
        "Монета", "ДЕНЬ 1", "ДЕНЬ 1", "ДЕНЬ 2", "ДЕНЬ 2", "ДЕНЬ 3", "ДЕНЬ 3",
        "ДЕНЬ 4", "ДЕНЬ 4", "ДЕНЬ 5", "ДЕНЬ 5", "ДЕНЬ 6", "ДЕНЬ 6", "ДЕНЬ 7", "ДЕНЬ 7",
        "ATR", "Размер тика", "Мин шаг покупки", "Средний объём", "Текущая цена",
        "Комиссия открытие", "Комиссия закрытие"
    ]
    if headers != expected_headers:
        logger.info("Обновление заголовков")
        sheet.update(values=[expected_headers], range_name="A1:V1")
    else:
        logger.info("Заголовки корректны")

    # Фильтрация и сбор данных
    logger.info("Получение размера тика, минимального шага покупки и комиссий")
    filtered_symbols = []
    for symbol in symbols:
        instrument_info = bybit_api.get_instrument_info(symbol)
        tick_size = float(instrument_info.get('priceFilter', {}).get('tickSize', 0))
        min_order_qty = float(instrument_info.get('lotSizeFilter', {}).get('minOrderQty', 0))
        
        # Получение комиссий
        maker_fee, taker_fee = bybit_api.get_fee_rates(symbol)
        logger.info(f"Комиссии для {symbol}: taker_fee={taker_fee}, maker_fee={maker_fee}")

        if tick_size > 0 and min_order_qty > 0:
            filtered_symbols.append((symbol, tick_size, min_order_qty, taker_fee, maker_fee))
        else:
            logger.warning(f"Пропущен символ {symbol}: tick_size={tick_size}, min_order_qty={min_order_qty}")

    # Пакетная запись данных в таблицу (полная перезапись)
    logger.info(f"Запись {len(filtered_symbols)} отфильтрованных символов в таблицу")
    values = []
    for symbol, tick_size, min_order_qty, taker_fee, maker_fee in filtered_symbols:
        row = [symbol] + [""] * 14 + ["", tick_size, min_order_qty, "", "", taker_fee, maker_fee]
        values.append(row)

    # Записываем все строки одним запросом
    range_name = f"A2:V{len(filtered_symbols) + 1}"  # Начиная со второй строки
    try:
        sheet.update(values=values, range_name=range_name)
        logger.info(f"Успешно записаны данные в диапазон {range_name}")
    except Exception as e:
        logger.error(f"Ошибка при записи данных: {e}")
        return

    logger.info("Статичные данные успешно обновлены")

if __name__ == "__main__":
    populate_static_data()
import logging
from google_sheets import GoogleSheetsClient
from bybit_api import BybitAPI
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID
import time

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def calculate_atr(high_low_data):
    """Расчет ATR как среднего диапазона (high - low) за 7 дней."""
    if not high_low_data:
        return 0
    tr_values = [high - low for high, low in high_low_data]
    return sum(tr_values) / len(tr_values) if tr_values else 0

def populate_historical_data():
    logger = logging.getLogger(__name__)
    logger.info("Запуск populate_historical_data.py: обновление исторических данных, объёма и ATR")

    sheets_client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
    bybit_api = BybitAPI()

    logger.info("Попытка получить лист database")
    sheet = sheets_client.get_sheet("database")
    if not sheet:
        logger.error("Не удалось получить лист database")
        return

    logger.info("Получение существующих данных из листа")
    all_data = sheet.get_all_values()
    if len(all_data) < 2:
        logger.error("В листе database отсутствуют монеты, сначала запустите populate_static_data.py")
        return

    symbols = [row[0] for row in all_data[1:] if row[0]]
    logger.info(f"Найдено {len(symbols)} символов в таблице")

    logger.info("Обновление исторических данных, объёма и ATR")
    updated_rows = [all_data[0]]  # Сохраняем заголовок
    filtered_count = 0
    for idx, symbol in enumerate(symbols, start=1):
        logger.info(f"Обработка символа {symbol} (строка {idx + 1})")

        # Сначала проверяем объем
        volume_usdt = bybit_api.get_24h_volume(symbol)
        logger.info(f"Средний объём за 24 часа для {symbol}: {volume_usdt} USDT")

        # Фильтрация по объему
        if volume_usdt < 49_000_000:
            logger.info(f"Символ {symbol} пропущен: объём {volume_usdt} < 49,000,000 USDT")
            filtered_count += 1
            continue

        # Если объем удовлетворяет условию, запрашиваем исторические данные
        high_low_data = bybit_api.get_last_7_days_high_low(symbol, days=7)
        historical_values = []
        for high, low in high_low_data:
            historical_values.extend([high, low])
        while len(historical_values) < 14:
            historical_values.extend([0, 0])
        logger.info(f"Исторические данные для {symbol} (high, low): {historical_values}")

        # Расчет ATR
        atr = calculate_atr(high_low_data)
        logger.info(f"ATR для {symbol}: {atr}")

        # Текущая строка из таблицы
        current_row = all_data[idx]
        if len(current_row) < 22:
            current_row.extend([''] * (22 - len(current_row)))

        # Формируем обновленную строку
        new_row = (
            [current_row[0]] +           # Монета (A)
            historical_values +          # ДЕНЬ 1–7 (B–O): high1, low1, high2, low2, ...
            [atr] +                      # ATR (P)
            [current_row[16], current_row[17]] +  # Размер тика (Q), Мин шаг покупки (R)
            [volume_usdt] +              # Средний объём в USDT (S)
            [current_row[19], current_row[20], current_row[21]]  # Текущая цена (T), Комиссия открытие (U), Комиссия закрытие (V)
        )
        logger.info(f"Подготовлена строка для {symbol} (строка {idx + 1}): {new_row}")
        updated_rows.append(new_row)
        
        # Добавляем задержку для соблюдения лимитов API
        time.sleep(0.1)

    logger.info(f"Отфильтровано {filtered_count} символов с объёмом менее 1 млн USDT")
    logger.info(f"Запись {len(updated_rows) - 1} строк в таблицу")
    range_name = f"A1:V{len(updated_rows)}"
    try:
        sheet.update(values=updated_rows, range_name=range_name)
        logger.info(f"Успешно обновлены данные в диапазоне {range_name}")
    except Exception as e:
        logger.error(f"Ошибка при записи данных: {e}")
        return

    logger.info("Исторические данные, объём и ATR успешно обновлены")

if __name__ == "__main__":
    populate_historical_data()
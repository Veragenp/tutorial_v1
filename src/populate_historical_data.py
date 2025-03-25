import logging
from google_sheets import GoogleSheetsClient
from bybit_api import BybitAPI
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID
import time
from datetime import datetime
import os

# Настройка логирования: создаем путь к файлу логов в папке Logs на уровне проекта
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Корень проекта (на уровень выше скрипта)
log_dir = os.path.join(project_dir, "Logs")  # Папка Logs в корне проекта
log_file = os.path.join(log_dir, f"populate_historical_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")  # Уникальный файл логов с датой и временем

# Инициализация логирования
logging.basicConfig(
    filename=log_file,  # Путь к файлу логов
    level=logging.DEBUG,  # Уровень логирования (DEBUG для максимальной детализации)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Формат записи логов: время - уровень - сообщение
    encoding='utf-8'  # Кодировка UTF-8 для поддержки русского текста
)

def calculate_atr(high_low_data):
    """Расчет ATR (Average True Range) как среднего диапазона (high - low) за 7 дней."""
    if not high_low_data:  # Если данных нет, возвращаем 0
        return 0
    tr_values = [high - low for high, low in high_low_data]  # Вычисляем диапазон (True Range) для каждого дня
    if len(tr_values) > 7:  # Если дней больше 7, берем только первые 7
        tr_values = tr_values[:7]
    elif len(tr_values) < 7:  # Если меньше 7, дополняем нулями
        tr_values.extend([0] * (7 - len(tr_values)))
    return sum(tr_values) / 7 if tr_values else 0  # Среднее значение TR за 7 дней

def populate_historical_data():
    """Основная функция для заполнения исторических данных в Google Sheets."""
    logger = logging.getLogger(__name__)  # Создаем логгер для записи сообщений
    logger.info("Запуск populate_historical_data.py: обновление исторических данных, объёма и ATR")

    # Инициализация клиентов для работы с Google Sheets и Bybit API
    sheets_client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
    bybit_api = BybitAPI()

    # Получаем лист "database" из Google Sheets
    logger.info("Попытка получить лист database")
    sheet = sheets_client.get_sheet("database")
    if not sheet:
        logger.error("Не удалось получить лист database")
        return

    # Читаем все данные из листа
    logger.info("Получение существующих данных из листа")
    all_data = sheet.get_all_values()
    if len(all_data) < 2:  # Проверяем, есть ли данные кроме заголовка
        logger.error("В листе database отсутствуют монеты, сначала запустите populate_static_data.py")
        return

    # Собираем уникальные символы (монеты) из столбца A
    symbols = []
    seen = set()
    for row in all_data[1:]:  # Пропускаем заголовок
        if row and row[0] and isinstance(row[0], str) and row[0] not in seen:
            symbols.append(row[0])
            seen.add(row[0])
    logger.info(f"Найдено {len(symbols)} уникальных символов в таблице")

    # Подготавливаем список строк для записи (начинаем с заголовка)
    updated_rows = [all_data[0]]
    volume_threshold = 49_000_000  # Порог объема для фильтрации символов
    filtered_count = 0  # Счетчик отфильтрованных символов

    logger.info("Обновление исторических данных, объёма и ATR")
    for idx, symbol in enumerate(symbols, start=1):  # Перебираем символы
        logger.info(f"Обработка символа {symbol} (строка {idx + 1})")

        # Находим текущую строку для символа или создаем пустую
        current_row = next((row for row in all_data[1:] if row[0] == symbol), [''] * 22)
        if len(current_row) < 22:  # Дополняем до 22 столбцов, если строка короче
            current_row.extend([''] * (22 - len(current_row)))
        # Сохраняем статичные столбцы (A, Q, R, T, U, V)
        static_cols = [current_row[i] for i in [0, 16, 17, 19, 20, 21]]

        # Получаем объем торгов за 24 часа
        volume_usdt = bybit_api.get_24h_volume(symbol)
        logger.info(f"Средний объём за 24 часа для {symbol}: {volume_usdt} USDT")

        # Инициализируем значения для динамических столбцов
        low_day1 = ''  # B: Low День 1
        historical_values = [''] * 13  # C–O: High1, Low2, High2, ..., High7
        atr = ''  # P: ATR
        
        if volume_usdt >= volume_threshold:  # Проверяем, проходит ли символ по объему
            # Получаем данные за последние 7 дней (high и low)
            high_low_data = bybit_api.get_last_7_days_high_low(symbol, days=7)
            logger.debug(f"Сырые данные high/low для {symbol}: {high_low_data}")
            
            if high_low_data:  # Если данные получены
                # Записываем Low День 1 в столбец B
                low_day1 = high_low_data[0][1]
                
                # Формируем исторические данные для столбцов C–O
                historical_values = []
                historical_values.append(high_low_data[0][0])  # C: High1
                for i, (high, low) in enumerate(high_low_data[1:], start=2):  # Начинаем с Дня 2
                    historical_values.append(low)   # Low для дня i
                    historical_values.append(high)  # High для дня i
                historical_values = historical_values[:13]  # Ограничиваем до 13 значений
                while len(historical_values) < 13:  # Дополняем нулями, если меньше
                    historical_values.append(0)
                logger.info(f"Исторические данные для {symbol} (C–O): {historical_values}")

                # Вычисляем ATR
                atr = calculate_atr(high_low_data)
                logger.info(f"ATR для {symbol}: {atr}")
        else:
            logger.info(f"Символ {symbol} пропущен: объём {volume_usdt} < {volume_threshold:,} USDT")
            filtered_count += 1

        # Формируем новую строку для записи
        new_row = (
            [static_cols[0]] +          # A: Монета (статичный)
            [low_day1] +                # B: Low День 1
            historical_values +         # C–O: High1, Low2, High2, ..., High7
            [atr] +                     # P: ATR
            [static_cols[1]] +          # Q: Размер тика (статичный)
            [static_cols[2]] +          # R: Мин шаг покупки (статичный)
            [volume_usdt] +             # S: Средний объем
            [static_cols[3]] +          # T: Пустой (статичный)
            [static_cols[4]] +          # U: Комиссия открытие (статичный)
            [static_cols[5]]            # V: Комиссия закрытие (статичный)
        )
        logger.info(f"Подготовлена строка для {symbol} (строка {idx + 1}): {new_row}")
        updated_rows.append(new_row)

        time.sleep(0.1)  # Задержка для избежания превышения лимитов API

    # Логируем статистику
    logger.info(f"Отфильтровано {filtered_count} символов с объёмом менее {volume_threshold:,} USDT")
    logger.info(f"Подготовлено {len(updated_rows) - 1} строк для записи")

    # Определяем диапазон для записи в Google Sheets
    range_name = f"A1:V{len(updated_rows)}"
    logger.info(f"Диапазон для записи: {range_name}")

    # Очищаем лист перед записью
    try:
        sheet.clear()
        logger.info("Лист database очищен перед записью")
    except Exception as e:
        logger.error(f"Ошибка при очистке листа: {e}")
        return

    # Записываем данные в Google Sheets
    try:
        sheet.update(values=updated_rows, range_name=range_name)
        logger.info(f"Успешно обновлены данные в диапазоне {range_name}")
        
        # Проверяем, что данные записаны корректно
        updated_data = sheet.get_all_values()
        logger.debug(f"Данные после записи: {updated_data}")
        if updated_data == updated_rows:
            logger.info("Данные в таблице совпадают с подготовленными")
        else:
            logger.error("Данные в таблице не совпадают с подготовленными")
            for i, (expected, actual) in enumerate(zip(updated_rows, updated_data)):
                if expected != actual:
                    logger.error(f"Различие в строке {i + 1}: ожидаемое={expected}, записано={actual}")
                    break
    except Exception as e:
        logger.error(f"Ошибка при записи данных: {e}")
        return

    logger.info("Исторические данные, объём и ATR успешно обновлены")

if __name__ == "__main__":
    populate_historical_data()  # Запуск основной функции
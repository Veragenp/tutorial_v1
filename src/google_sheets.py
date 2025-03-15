import gspread
from google.oauth2.service_account import Credentials
import logging
import os
try:
    from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID
except ImportError as e:
    print(f"Ошибка импорта из config.py: {str(e)}")
    raise

# Получаем абсолютный путь к корню проекта (поднимаемся на уровень выше из src)
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
log_dir = os.path.join(project_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)

# Отладочный вывод пути
print(f"Текущая директория: {os.getcwd()}")
print(f"Путь к папке логов: {log_dir}")

# Путь к файлу логов
log_file = os.path.join(log_dir, "debug.log")

# Настройка логирования с выводом в консоль и файл
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a', encoding='utf-8'),  # Указываем кодировку UTF-8
        logging.StreamHandler()  # Логи в консоль
    ]
)

# Проверка, работает ли FileHandler
try:
    logging.info(f"Лог-файл настроен на: {log_file}")
    print(f"Лог-файл настроен на: {log_file}")
except Exception as e:
    print(f"Ошибка настройки лога: {str(e)}")
    logging.error(f"Ошибка настройки лога: {str(e)}")

class GoogleSheetsClient:
    def __init__(self):
        logging.info("Инициализация GoogleSheetsClient")
        print("Инициализация GoogleSheetsClient")
        logging.info(f"GOOGLE_SHEETS_CREDENTIALS: {GOOGLE_SHEETS_CREDENTIALS}")
        logging.info(f"GOOGLE_SHEETS_ID: {GOOGLE_SHEETS_ID}")
        print(f"GOOGLE_SHEETS_CREDENTIALS: {GOOGLE_SHEETS_CREDENTIALS}")
        print(f"GOOGLE_SHEETS_ID: {GOOGLE_SHEETS_ID}")

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        try:
            creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS, scopes=scope)
        except Exception as e:
            logging.error(f"Ошибка при загрузке credentials: {str(e)}")
            print(f"Ошибка при загрузке credentials: {str(e)}")
            raise

        self.client = gspread.authorize(creds)
        try:
            self.spreadsheet = self.client.open_by_key(GOOGLE_SHEETS_ID)
            logging.info(f"Подключение к таблице с ID: {GOOGLE_SHEETS_ID}")
            print(f"Подключение к таблице с ID: {GOOGLE_SHEETS_ID}")
        except Exception as e:
            logging.error(f"Ошибка при подключении к таблице: {str(e)}")
            print(f"Ошибка при подключении к таблице: {str(e)}")
            raise

    def get_sheet(self, sheet_name):
        logging.info(f"Попытка получить лист: {sheet_name}")
        print(f"Попытка получить лист: {sheet_name}")
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logging.error(f"Лист {sheet_name} не найден")
            print(f"Лист {sheet_name} не найден")
            return None
        except Exception as e:
            logging.error(f"Ошибка при получении листа {sheet_name}: {str(e)}")
            print(f"Ошибка при получении листа {sheet_name}: {str(e)}")
            return None

    def list_sheets(self):
        sheets = [worksheet.title for worksheet in self.spreadsheet.worksheets()]
        logging.info(f"Доступные листы: {sheets}")
        print(f"Доступные листы: {sheets}")
        return sheets

    def update_cell(self, sheet, row, col, value):
        sheet.update_cell(row, col, value)

    def get_all_data(self, sheet):
        logging.info("Чтение всех данных из листа")
        print("Чтение всех данных из листа")
        return sheet.get_all_values()

    def get_trading_coins(self):
        logging.info("Начало выполнения get_trading_coins")
        print("Начало выполнения get_trading_coins")
        sheet = self.get_sheet("analitics")
        if not sheet:
            logging.error("Не удалось получить лист analitics")
            print("Не удалось получить лист analitics")
            return []

        # Получаем только столбец "Торговля" (D, индекс 3)
        try:
            trading_column = sheet.col_values(4)  # 4 - индекс столбца D (нумерация с 1)
            logging.info(f"Получен столбец Торговля: {trading_column[:5]}... (первые 5 значений)")
            print(f"Получен столбец Торговля: {trading_column[:5]}... (первые 5 значений)")
        except Exception as e:
            logging.error(f"Ошибка при получении столбца Торговля: {str(e)}")
            print(f"Ошибка при получении столбца Торговля: {str(e)}")
            return []

        # Определяем индексы строк, где Торговля = TRUE
        valid_rows = [i for i, status in enumerate(trading_column[1:], start=2) if status.strip().upper() in ["TRUE", "TRU"]]
        logging.info(f"Найдено строк с TRUE: {len(valid_rows)} на индексах: {valid_rows}")
        print(f"Найдено строк с TRUE: {len(valid_rows)} на индексах: {valid_rows}")

        if not valid_rows:
            logging.warning("Нет строк с Торговля = TRUE")
            print("Нет строк с Торговля = TRUE")
            return []

        # Загружаем только нужные строки
        trading_coins = []
        for row_idx in valid_rows:
            try:
                row_data = sheet.row_values(row_idx)
                if len(row_data) > 12:
                    coin = row_data[6]  # Столбец G (индекс 6) — монета
                    long_level = row_data[9]  # Столбец J (индекс 9) — "Уровень 1 - LONG"
                    short_level = row_data[12]  # Столбец M (индекс 12) — "Уровень 1 - SHORT"

                    # Обрабатываем возможные ошибки преобразования
                    try:
                        long_level = float(long_level) if long_level and long_level != '#N/A' else None
                        short_level = float(short_level) if short_level and short_level != '#N/A' else None
                    except ValueError:
                        logging.warning(f"Невозможно преобразовать уровни для монеты {coin} в числа")
                        print(f"Невозможно преобразовать уровни для монеты {coin} в числа")
                        continue

                    trading_coins.append({
                        "coin": coin,
                        "long_level": long_level,
                        "short_level": short_level
                    })
                    logging.info(f"Добавлена монета: {coin}, long_level: {long_level}, short_level: {short_level}")
                    print(f"Добавлена монета: {coin}, long_level: {long_level}, short_level: {short_level}")
            except Exception as e:
                logging.error(f"Ошибка при обработке строки {row_idx}: {str(e)}")
                print(f"Ошибка при обработке строки {row_idx}: {str(e)}")
                continue

        logging.info(f"Найдено {len(trading_coins)} монет для мониторинга")
        print(f"Найдено {len(trading_coins)} монет для мониторинга")
        return trading_coins

    def get_pending_trades(self, sheet_name):
        """Получает строки с TRUE в столбце F (Вход в сделку) из указанного листа."""
        logging.info(f"Получение ожидающих сделок из листа: {sheet_name}")
        print(f"Получение ожидающих сделок из листа: {sheet_name}")
        sheet = self.get_sheet(sheet_name)
        if not sheet:
            logging.error(f"Не удалось получить лист {sheet_name}")
            print(f"Не удалось получить лист {sheet_name}")
            return []

        # Получаем все данные
        try:
            all_data = sheet.get_all_values()
            if not all_data or len(all_data) < 2:
                logging.warning(f"Лист {sheet_name} пуст или содержит только заголовки")
                print(f"Лист {sheet_name} пуст или содержит только заголовки")
                return []
        except Exception as e:
            logging.error(f"Ошибка при чтении данных из листа {sheet_name}: {str(e)}")
            print(f"Ошибка при чтении данных из листа {sheet_name}: {str(e)}")
            return []

        # Определяем индексы строк с TRUE в столбце F (индекс 5, нумерация с 0)
        pending_trades = []
        for row_idx, row in enumerate(all_data[1:], start=2):  # Пропускаем заголовок
            if len(row) < 28:  # Убедимся, что строка содержит достаточно столбцов (до AB)
                continue
            entry_trigger = row[5].strip().upper()  # Столбец F (индекс 5)
            if entry_trigger not in ["TRUE", "TRU"]:
                continue

            try:
                coin = row[7]  # Столбец H (индекс 7) — Монета
                entry_price = row[24] if row[24] else None  # Столбец Y (индекс 24) — Т вх (Цена Ордера)
                qty = row[25] if row[25] else None  # Столбец Z (индекс 25) — Кол. монет
                take_profit = row[26] if row[26] else None  # Столбец AA (индекс 26) — Тейк-профит
                stop_loss = row[27] if row[27] else None  # Столбец AB (индекс 27) — Стоп-лосс

                # Проверяем и преобразуем числовые значения
                try:
                    entry_price = float(entry_price) if entry_price and entry_price != '#N/A' else None
                    qty = float(qty) if qty and qty != '#N/A' else None
                    take_profit = float(take_profit) if take_profit and take_profit != '#N/A' else None
                    stop_loss = float(stop_loss) if stop_loss and stop_loss != '#N/A' else None
                except ValueError as e:
                    logging.error(f"Ошибка преобразования данных в строке {row_idx}: {e}")
                    print(f"Ошибка преобразования данных в строке {row_idx}: {e}")
                    continue

                if not all([coin, entry_price, qty]):  # Проверяем обязательные параметры
                    logging.warning(f"Недостаточно данных в строке {row_idx}: {row}")
                    print(f"Недостаточно данных в строке {row_idx}: {row}")
                    continue

                trade = {
                    "row_idx": row_idx,
                    "coin": coin,
                    "entry_price": entry_price,
                    "qty": qty,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "side": "Buy" if sheet_name.lower() == "long" else "Sell"  # Определяем сторону сделки
                }
                pending_trades.append(trade)
                logging.info(f"Найдена ожидающая сделка: {trade}")
                print(f"Найдена ожидающая сделка: {trade}")
            except Exception as e:
                logging.error(f"Ошибка при обработке строки {row_idx}: {str(e)}")
                print(f"Ошибка при обработке строки {row_idx}: {str(e)}")
                continue

        logging.info(f"Всего найдено ожидающих сделок: {len(pending_trades)}")
        print(f"Всего найдено ожидающих сделок: {len(pending_trades)}")
        return pending_trades

if __name__ == "__main__":
    print("Запуск тестового скрипта...")
    try:
        client = GoogleSheetsClient()
        print("Клиент инициализирован, получение данных...")

        # Выводим список доступных листов
        sheets = client.list_sheets()
        print(f"Доступные листы в таблице: {sheets}")

        # Вызываем get_trading_coins для листа "analitics" (предыдущая логика)
        coins = client.get_trading_coins()
        print(f"Найдено монет: {len(coins)}")
        for coin in coins:
            print(coin)

        # Тест нового метода для листов "long" и "short"
        for sheet_name in ["long", "short"]:
            trades = client.get_pending_trades(sheet_name)
            print(f"Ожидающие сделки на листе {sheet_name}: {trades}")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        logging.error(f"Ошибка при выполнении: {str(e)}")
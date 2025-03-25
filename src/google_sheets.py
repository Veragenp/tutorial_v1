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
log_file = os.path.join(log_dir, "google_sheets.log")

# Настройка логирования с выводом в консоль и файл
logging.basicConfig(
    level=logging.DEBUG,  # Установлен уровень DEBUG для детального вывода
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a', encoding='utf-8'),
        logging.StreamHandler()
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
    def __init__(self, credentials_file, spreadsheet_id):
        logging.info("Инициализация GoogleSheetsClient")
        print("Инициализация GoogleSheetsClient")
        logging.info(f"GOOGLE_SHEETS_CREDENTIALS: {credentials_file}")
        logging.info(f"GOOGLE_SHEETS_ID: {spreadsheet_id}")
        print(f"GOOGLE_SHEETS_CREDENTIALS: {credentials_file}")
        print(f"GOOGLE_SHEETS_ID: {spreadsheet_id}")

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        try:
            creds = Credentials.from_service_account_file(credentials_file, scopes=scope)
        except Exception as e:
            logging.error(f"Ошибка при загрузке credentials: {str(e)}")
            print(f"Ошибка при загрузке credentials: {str(e)}")
            raise

        self.client = gspread.authorize(creds)
        try:
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
            logging.info(f"Подключение к таблице с ID: {spreadsheet_id}")
            print(f"Подключение к таблице с ID: {spreadsheet_id}")
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
        try:
            sheet.update_cell(row, col, value)
            logging.info(f"Обновлена ячейка: строка {row}, столбец {col}, значение {value}")
            print(f"Обновлена ячейка: строка {row}, столбец {col}, значение {value}")
        except Exception as e:
            logging.error(f"Ошибка при обновлении ячейки: строка {row}, столбец {col}, значение {value}: {str(e)}")
            print(f"Ошибка при обновлении ячейки: строка {row}, столбец {col}, значение {value}: {str(e)}")

    def get_all_data(self, sheet):
        logging.info("Чтение всех данных из листа")
        print("Чтение всех данных из листа")
        try:
            return sheet.get_all_values()
        except Exception as e:
            logging.error(f"Ошибка при чтении данных из листа: {str(e)}")
            print(f"Ошибка при чтении данных из листа: {str(e)}")
            return []

    def get_trading_coins(self):
        logging.info("Начало выполнения get_trading_coins")
        print("Начало выполнения get_trading_coins")
        sheet = self.get_sheet("analitics")
        if not sheet:
            logging.error("Не удалось получить лист analitics")
            print("Не удалось получить лист analitics")
            return []

        try:
            trading_column = sheet.col_values(4)  # Столбец D (индекс 4)
            logging.info(f"Получен столбец Торговля: {trading_column[:5]}... (первые 5 значений)")
            print(f"Получен столбец Торговля: {trading_column[:5]}... (первые 5 значений)")
        except Exception as e:
            logging.error(f"Ошибка при получении столбца Торговля: {str(e)}")
            print(f"Ошибка при получении столбца Торговля: {str(e)}")
            return []

        valid_rows = [i for i, status in enumerate(trading_column[1:], start=2) if status.strip().upper() in ["TRUE", "TRU"]]
        logging.info(f"Найдено строк с TRUE: {len(valid_rows)} на индексах: {valid_rows}")
        print(f"Найдено строк с TRUE: {len(valid_rows)} на индексах: {valid_rows}")

        if not valid_rows:
            logging.warning("Нет строк с Торговля = TRUE")
            print("Нет строк с Торговля = TRUE")
            return []

        trading_coins = []
        for row_idx in valid_rows:
            try:
                row_data = sheet.row_values(row_idx)
                if len(row_data) > 12:
                    coin = row_data[6]  # Столбец G (индекс 6) — монета
                    long_level = row_data[9]  # Столбец J (индекс 9) — "Уровень 1 - LONG"
                    short_level = row_data[12]  # Столбец M (индекс 12) — "Уровень 1 - SHORT"

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

    def get_pending_trades(self):
        """Получает список сделок для входа с вкладок long и short."""
        logging.info("Начало выполнения get_pending_trades")
        print("Начало выполнения get_pending_trades")
        pending_trades = []

        # Проверяем вкладки long и short
        for sheet_name in ["long", "short"]:
            logging.info(f"Попытка получить лист: {sheet_name}")
            print(f"Попытка получить лист: {sheet_name}")
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)

                # Получаем данные из нужных колонок
                trade_entry_col = worksheet.col_values(6)  # F: Вход в сделку (индекс 6)
                status_col = worksheet.col_values(7)       # G: Статус сделки (индекс 7)
                coin_col = worksheet.col_values(8)         # H: Монета (индекс 8)
                entry_price_col = worksheet.col_values(25) # Y: Т вх (индекс 25)
                qty_col = worksheet.col_values(26)         # Z: Кол. монет (индекс 26)
                take_profit_col = worksheet.col_values(27) # AA: Тейк-профит (индекс 27)
                stop_loss_col = worksheet.col_values(28)   # AB: Стоп-лосс (индекс 28)

                # Находим строки, где в столбце "Вход в сделку" стоит TRUE
                trade_indices = [i for i, val in enumerate(trade_entry_col) if val.strip().upper() == "TRUE"]
                logging.info(f"Найдено строк с TRUE на листе {sheet_name}: {len(trade_indices)} на индексах: {trade_indices}")
                print(f"Найдено строк с TRUE на листе {sheet_name}: {len(trade_indices)} на индексах: {trade_indices}")

                for idx in trade_indices:
                    row_idx = idx + 1  # Индекс строки в Google Sheets (начинается с 1)
                    logging.debug(f"Обработка строки {row_idx}, значение F: '{trade_entry_col[idx]}'")
                    print(f"Обработка строки {row_idx}, значение F: '{trade_entry_col[idx]}'")

                    # Проверяем, не обработана ли уже эта строка (статус не пустой и не указан как "отменено")
                    status = status_col[idx] if idx < len(status_col) else ""
                    if status.strip() in ["вход, ожидание", "отменено: лимит сделок"]:
                        logging.debug(f"Строка {row_idx} пропущена: статус '{status}'")
                        print(f"Строка {row_idx} пропущена: статус '{status}'")
                        continue

                    try:
                        coin = coin_col[idx] if idx < len(coin_col) else None
                        entry_price = entry_price_col[idx] if idx < len(entry_price_col) else None
                        qty = qty_col[idx] if idx < len(qty_col) else None
                        take_profit = take_profit_col[idx] if idx < len(take_profit_col) else None
                        stop_loss = stop_loss_col[idx] if idx < len(stop_loss_col) else None

                        logging.debug(f"Строка {row_idx} данные: coin={coin}, entry_price={entry_price}, qty={qty}, take_profit={take_profit}, stop_loss={stop_loss}")

                        try:
                            entry_price = float(entry_price) if entry_price and entry_price != '#N/A' else None
                            qty = float(qty) if qty and qty != '#N/A' else None
                            take_profit = float(take_profit) if take_profit and take_profit != '#N/A' else None
                            stop_loss = float(stop_loss) if stop_loss and stop_loss != '#N/A' else None
                        except ValueError as e:
                            logging.error(f"Ошибка преобразования данных в строке {row_idx}: {e}")
                            print(f"Ошибка преобразования данных в строке {row_idx}: {e}")
                            continue

                        # Проверяем, что все обязательные параметры присутствуют
                        if not all([coin, entry_price, qty, stop_loss]):
                            logging.warning(f"Пропущены обязательные параметры в строке {row_idx} листа {sheet_name}: coin={coin}, entry_price={entry_price}, qty={qty}, stop_loss={stop_loss}")
                            print(f"Пропущены обязательные параметры в строке {row_idx} листа {sheet_name}: coin={coin}, entry_price={entry_price}, qty={qty}, stop_loss={stop_loss}")
                            continue

                        pending_trades.append({
                            "sheet": sheet_name,
                            "row": row_idx,
                            "coin": coin,
                            "entry_price": entry_price,
                            "qty": qty,
                            "take_profit": take_profit,
                            "stop_loss": stop_loss,
                            "side": "Buy" if sheet_name.lower() == "long" else "Sell"
                        })
                        logging.info(f"Добавлена сделка для обработки: {sheet_name}, строка {row_idx}, монета {coin}")
                        print(f"Добавлена сделка для обработки: {sheet_name}, строка {row_idx}, монета {coin}")
                    except Exception as e:
                        logging.error(f"Ошибка при обработке строки {row_idx} на листе {sheet_name}: {e}")
                        print(f"Ошибка при обработке строки {row_idx} на листе {sheet_name}: {e}")
                        continue

            except Exception as e:
                logging.error(f"Ошибка при обработке листа {sheet_name}: {e}")
                print(f"Ошибка при обработке листа {sheet_name}: {e}")
                continue

        logging.info(f"Найдено {len(pending_trades)} сделок для входа")
        print(f"Найдено {len(pending_trades)} сделок для входа")
        return pending_trades

    def update_trade_status(self, sheet_name, row, status):
        """Обновляет статус сделки в столбце G."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            worksheet.update_cell(row, 7, status)  # Столбец G (7-й)
            logging.info(f"Статус сделки обновлен: лист {sheet_name}, строка {row}, статус {status}")
            print(f"Статус сделки обновлен: лист {sheet_name}, строка {row}, статус {status}")
        except Exception as e:
            logging.error(f"Ошибка при обновлении статуса в листе {sheet_name}, строка {row}: {e}")
            print(f"Ошибка при обновлении статуса в листе {sheet_name}, строка {row}: {e}")
            raise

    def cancel_trade(self, sheet_name, row):
        """Отменяет сделку (сбрасывает F в FALSE)."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            worksheet.update_cell(row, 6, "FALSE")  # Столбец F (6-й)
            logging.info(f"Сделка отменена: лист {sheet_name}, строка {row}")
            print(f"Сделка отменена: лист {sheet_name}, строка {row}")
        except Exception as e:
            logging.error(f"Ошибка при отмене сделки в листе {sheet_name}, строка {row}: {e}")
            print(f"Ошибка при отмене сделки в листе {sheet_name}, строка {row}: {e}")
            raise

if __name__ == "__main__":
    print("Запуск тестового скрипта...")
    try:
        client = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)
        print("Клиент инициализирован, получение данных...")

        # Выводим список доступных листов
        sheets = client.list_sheets()
        print(f"Доступные листы в таблице: {sheets}")

        # Вызываем get_trading_coins для листа "analitics"
        coins = client.get_trading_coins()
        print(f"Найдено монет: {len(coins)}")
        for coin in coins:
            print(coin)

        # Тест метода get_pending_trades для листов "long" и "short"
        trades = client.get_pending_trades()
        print(f"Ожидающие сделки: {trades}")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        logging.error(f"Ошибка при выполнении: {str(e)}")
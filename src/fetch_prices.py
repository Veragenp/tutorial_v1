import logging
import time
import os
from datetime import datetime
from bybit_api import BybitAPI
import requests
from google_sheets import GoogleSheetsClient
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID  # Добавляем импорт

# Создаем директорию для логов
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Генерируем уникальное имя файла с временной меткой
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(log_dir, f"fetch_prices_{current_time}.log")

# Создаем логгер для fetch_prices
logger = logging.getLogger("fetch_prices")
logger.setLevel(logging.INFO)

# Создаем файловый обработчик
file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Добавляем консольный обработчик
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

class PriceFetcher:
    def __init__(self):
        self.logger = logging.getLogger("fetch_prices")
        self.logger.info("Инициализация PriceFetcher")
        print("Инициализация PriceFetcher...")

        # Получаем монеты из Google Sheets
        google_sheets = GoogleSheetsClient(GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID)  # Обновляем вызов
        self.trading_coins = google_sheets.get_trading_coins()
        self.symbols = [coin["coin"] for coin in self.trading_coins]

        # Логируем список монет
        self.logger.info(f"Получено {len(self.trading_coins)} монет для мониторинга: {self.symbols}")
        print(f"Получено {len(self.trading_coins)} монет для мониторинга: {self.symbols}")

        self.bybit_api = BybitAPI()
        self.current_prices = {symbol: 0.0 for symbol in self.symbols}
        self.valid_symbols = []
        self.running = True

    def validate_symbol(self, symbol):
        """Проверяет валидность символа через REST API."""
        try:
            base_url = "https://api.bybit.com"
            endpoint = "/v5/market/instruments-info"
            params = {"category": "linear", "symbol": symbol}
            response = requests.get(base_url + endpoint, params=params)
            data = response.json()
            if data["retCode"] == 0 and data["result"]["list"]:
                self.logger.info(f"Символ {symbol} валиден")
                print(f"Символ {symbol} валиден")
                return True
            self.logger.warning(f"Символ {symbol} не валиден: {data.get('retMsg', 'Нет данных')}")
            print(f"Символ {symbol} не валиден: {data.get('retMsg', 'Нет данных')}")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка проверки символа {symbol}: {e}")
            print(f"Ошибка проверки символа {symbol}: {e}")
            return False

    def handle_price_update(self, symbol, last_price):
        """Обработка обновления цены."""
        if symbol in self.valid_symbols:
            self.current_prices[symbol] = last_price
            self.logger.debug(f"Обновлена цена для {symbol}: {last_price}")
            print(f"Обновлена цена для {symbol}: {last_price}")

    def reconnect(self):
        """Переподключение WebSocket при разрыве."""
        self.logger.warning("Попытка переподключения WebSocket...")
        print("Попытка переподключения WebSocket...")
        self.bybit_api = BybitAPI()
        self.valid_symbols = []
        self.subscribe_to_valid_symbols()

    def subscribe_to_valid_symbols(self):
        """Подписка только на валидные символы."""
        self.valid_symbols = [s for s in self.symbols if self.validate_symbol(s)]
        if not self.valid_symbols:
            self.logger.error("Не удалось найти валидные символы. Завершаем работу.")
            print("Не удалось найти валидные символы. Завершаем работу.")
            self.running = False
            return

        for symbol in self.valid_symbols:
            try:
                self.bybit_api.subscribe_to_ticker([symbol], self.handle_price_update)
                self.logger.info(f"Успешно подписались на {symbol}")
                print(f"Успешно подписались на {symbol}")
            except Exception as e:
                self.logger.error(f"Ошибка подписки на {symbol}: {e}")
                print(f"Ошибка подписки на {symbol}: {e}")

    def run(self):
        """Запуск получения цен."""
        self.logger.info(f"Запуск получения цен для {len(self.symbols)} инструментов: {self.symbols}")
        print(f"Запуск получения цен для {len(self.symbols)} инструментов: {self.symbols}")
        
        # Инициализируем подписку
        self.subscribe_to_valid_symbols()

        if not self.valid_symbols:
            return

        # Бесконечный цикл с логированием цен
        try:
            self.logger.info("Начало мониторинга цен...")
            print("Начало мониторинга цен...")
            while self.running:
                prices_str = ", ".join(
                    f"{symbol}: {price}" for symbol, price in self.current_prices.items()
                    if symbol in self.valid_symbols
                )
                self.logger.info(f"Текущие цены: {prices_str}")
                print(f"Текущие цены: {prices_str}")
                time.sleep(10)
        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            print("Остановлено пользователем")
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в цикле: {e}")
            print(f"Неожиданная ошибка в цикле: {e}")
            self.reconnect()
            if self.running:
                time.sleep(5)

    def get_current_prices(self):
        """Метод для получения текущих цен."""
        return self.current_prices

if __name__ == "__main__":
    fetcher = PriceFetcher()
    fetcher.run()
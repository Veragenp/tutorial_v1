import logging
import time
import os
from datetime import datetime
from google_sheets import GoogleSheetsClient
from fetch_prices import PriceFetcher
import threading

# Создаем директорию для логов
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Генерируем уникальное имя файла с временной меткой
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(log_dir, f"price_monitor_{current_time}.log")

# Создаем логгер для price_monitor
logger = logging.getLogger("price_monitor")
logger.setLevel(logging.INFO)

# Создаем файловый обработчик
file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Добавляем консольный обработчик
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

class PriceMonitor:
    def __init__(self):
        self.logger = logging.getLogger("price_monitor")
        self.logger.info("Инициализация PriceMonitor")
        print("Инициализация PriceMonitor...")

        # Получаем монеты и уровни из Google Sheets
        self.google_sheets = GoogleSheetsClient()
        self.trading_coins = self.google_sheets.get_trading_coins()
        self.levels = {coin["coin"]: {"long_level": coin["long_level"], "short_level": coin["short_level"]} for coin in self.trading_coins}

        # Логируем список монет и их уровни
        self.logger.info(f"Получено {len(self.trading_coins)} монет для мониторинга: {[coin['coin'] for coin in self.trading_coins]}")
        for coin in self.trading_coins:
            self.logger.info(f"Монета: {coin['coin']}, long_level: {coin['long_level']}, short_level: {coin['short_level']}")
        print(f"Получено {len(self.trading_coins)} монет для мониторинга: {[coin['coin'] for coin in self.trading_coins]}")

        # Инициализация PriceFetcher
        self.price_fetcher = PriceFetcher()
        self.running = True
        self.alerts_history = []
        self.prev_prices = {coin["coin"]: None for coin in self.trading_coins}  # Храним предыдущие цены
        self.alerted = {coin["coin"]: {"long": False, "short": False} for coin in self.trading_coins}  # Флаги оповещений

    def check_levels(self, symbol, current_price):
        """Проверяет пересечение уровней LONG/SHORT и генерирует оповещения."""
        levels = self.levels.get(symbol, {})
        long_level = levels.get("long_level")
        short_level = levels.get("short_level")

        # Логируем для отладки
        self.logger.debug(f"Проверка уровней для {symbol}: current_price {current_price}, long_level: {long_level}, short_level: {short_level}")
        print(f"Проверка уровней для {symbol}: current_price {current_price}, long_level: {long_level}, short_level: {short_level}")

        # Если предыдущей цены нет (первый тик), просто сохраняем и выходим
        if self.prev_prices[symbol] is None:
            self.prev_prices[symbol] = current_price
            return

        # Проверяем пересечение
        if long_level is not None and not self.alerted[symbol]["long"]:
            if self.prev_prices[symbol] > long_level and current_price <= long_level:
                alert_msg = f"Пересечение уровня LONG для {symbol}: цена {current_price} <= {long_level}"
                self.logger.info(alert_msg)
                print(alert_msg)
                self.alerts_history.append({
                    "symbol": symbol,
                    "type": "LONG",
                    "price": current_price,
                    "level": long_level,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self.alerted[symbol]["long"] = True
                # Логируем историю только при новом оповещении
                self.logger.info(f"История оповещений: {self.alerts_history[-5:]}")
                print(f"История оповещений: {self.alerts_history[-5:]}")

        if short_level is not None and not self.alerted[symbol]["short"]:
            if self.prev_prices[symbol] < short_level and current_price >= short_level:
                alert_msg = f"Пересечение уровня SHORT для {symbol}: цена {current_price} >= {short_level}"
                self.logger.info(alert_msg)
                print(alert_msg)
                self.alerts_history.append({
                    "symbol": symbol,
                    "type": "SHORT",
                    "price": current_price,
                    "level": short_level,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self.alerted[symbol]["short"] = True
                # Логируем историю только при новом оповещении
                self.logger.info(f"История оповещений: {self.alerts_history[-5:]}")
                print(f"История оповещений: {self.alerts_history[-5:]}")

        # Обновляем предыдущую цену
        self.prev_prices[symbol] = current_price

    def get_alerts_history(self):
        """Метод для получения истории оповещений."""
        return self.alerts_history

    def run(self):
        """Запуск мониторинга цен."""
        self.logger.info("Запуск мониторинга цен...")
        print("Запуск мониторинга цен...")

        # Запускаем PriceFetcher в отдельном потоке
        fetcher_thread = threading.Thread(target=self.price_fetcher.run)
        fetcher_thread.daemon = True
        fetcher_thread.start()

        try:
            while self.running:
                # Получаем текущие цены из PriceFetcher
                current_prices = self.price_fetcher.get_current_prices()

                # Проверяем уровни для каждой монеты
                for symbol, price in current_prices.items():
                    if price > 0:  # Проверяем, что цена обновилась
                        self.check_levels(symbol, price)

                time.sleep(10)  # Проверяем каждые 10 секунд
        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            print("Остановлено пользователем")
            self.running = False
            self.price_fetcher.running = False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в цикле: {e}")
            print(f"Неожиданная ошибка в цикле: {e}")
            self.running = False
            self.price_fetcher.running = False

if __name__ == "__main__":
    monitor = PriceMonitor()
    monitor.run()
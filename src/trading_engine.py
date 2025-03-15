import logging
import time
import os
from datetime import datetime
from price_monitor import PriceMonitor
from telegram_bot import send_telegram_message
import threading
from config import ALERT_TIMEOUT_MINUTES

# Создаем директорию для логов
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Генерируем уникальное имя файла с временной меткой
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(log_dir, f"trading_engine_{current_time}.log")

# Создаем логгер для trading_engine
logger = logging.getLogger("trading_engine")
logger.setLevel(logging.INFO)

# Создаем файловый обработчик
file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Добавляем консольный обработчик
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

class TradingEngine:
    def __init__(self, price_monitor):
        self.logger = logging.getLogger("trading_engine")
        self.logger.info("Инициализация TradingEngine")
        print("Инициализация TradingEngine...")

        self.price_monitor = price_monitor
        self.last_alert_count = 0  # Для отслеживания новых оповещений
        self.long_alerts = {}  # Словарь: {symbol: [timestamps]}
        self.short_alerts = {}  # Словарь: {symbol: [timestamps]}
        self.long_window_start = None  # Начало окна для LONG после первых 3 оповещений
        self.short_window_start = None  # Начало окна для SHORT после первых 3 оповещений
        self.running = True

    def process_new_alerts(self):
        """Обрабатывает новые оповещения и формирует Telegram-сообщения."""
        alerts = self.price_monitor.get_alerts_history()
        current_alert_count = len(alerts)

        # Проверяем, есть ли новые оповещения
        if current_alert_count > self.last_alert_count:
            new_alerts = alerts[self.last_alert_count:current_alert_count]
            for alert in new_alerts:
                symbol = alert["symbol"]
                alert_type = alert["type"]
                price = alert["price"]
                level = alert["level"]
                timestamp = datetime.strptime(alert["timestamp"], "%Y-%m-%d %H:%M:%S")

                # Формируем сообщение о пересечении
                alert_msg = f"Пересечение уровня {alert_type} для {symbol}: цена {price} {'<=' if alert_type == 'LONG' else '>='} {level}"
                self.logger.info(f"Обработка нового оповещения: {alert}")
                print(f"Обработка нового оповещения: {alert}")
                # Отправляем сообщение в Telegram
                send_telegram_message(alert_msg)

                # Обновляем счетчики
                if alert_type == "LONG":
                    if symbol not in self.long_alerts:
                        self.long_alerts[symbol] = []
                    self.long_alerts[symbol].append(timestamp)
                    # Если достигли 3 разных монет, фиксируем начало окна
                    if len(self.long_alerts) == 3 and self.long_window_start is None:
                        self.long_window_start = timestamp
                elif alert_type == "SHORT":
                    if symbol not in self.short_alerts:
                        self.short_alerts[symbol] = []
                    self.short_alerts[symbol].append(timestamp)
                    # Если достигли 3 разных монет, фиксируем начало окна
                    if len(self.short_alerts) == 3 and self.short_window_start is None:
                        self.short_window_start = timestamp

            self.last_alert_count = current_alert_count

            # Проверяем условия для "Входа" и "Отмены"
            self.check_entry_conditions()
            self.check_cancellation_conditions()

    def check_entry_conditions(self):
        """Проверяет условия для входа в сделку."""
        current_time = datetime.now()

        # Проверка для LONG
        if self.long_window_start:
            long_count = len(self.long_alerts)
            time_diff = (current_time - self.long_window_start).total_seconds() / 60
            if long_count >= 3 and time_diff >= ALERT_TIMEOUT_MINUTES:
                send_telegram_message("Вход в сделку LONG")
                self.logger.info("Отправлено оповещение: Вход в сделку LONG")
                print("Отправлено оповещение: Вход в сделку LONG")
                # Сбрасываем счетчики после входа
                self.long_alerts.clear()
                self.long_window_start = None

        # Проверка для SHORT
        if self.short_window_start:
            short_count = len(self.short_alerts)
            time_diff = (current_time - self.short_window_start).total_seconds() / 60
            if short_count >= 3 and time_diff >= ALERT_TIMEOUT_MINUTES:
                send_telegram_message("Вход в сделку SHORT")
                self.logger.info("Отправлено оповещение: Вход в сделку SHORT")
                print("Отправлено оповещение: Вход в сделку SHORT")
                # Сбрасываем счетчики после входа
                self.short_alerts.clear()
                self.short_window_start = None

    def check_cancellation_conditions(self):
        """Проверяет условия для отмены сценария."""
        current_time = datetime.now()

        # Проверка для LONG
        if self.long_window_start:
            time_diff = (current_time - self.long_window_start).total_seconds() / 60
            if time_diff <= ALERT_TIMEOUT_MINUTES:
                # Подсчитываем количество разных монет с оповещениями LONG
                if len(self.long_alerts) >= 3:
                    # Первые 3 монеты — это базовые, остальные — "другие"
                    other_long_count = len(self.long_alerts) - 3
                    if other_long_count >= 5:
                        send_telegram_message("Отмена сценария LONG")
                        self.logger.info("Отправлено оповещение: Отмена сценария LONG")
                        print("Отправлено оповещение: Отмена сценария LONG")
                        # Сбрасываем счетчики
                        self.long_alerts.clear()
                        self.long_window_start = None

        # Проверка для SHORT
        if self.short_window_start:
            time_diff = (current_time - self.short_window_start).total_seconds() / 60
            if time_diff <= ALERT_TIMEOUT_MINUTES:
                # Подсчитываем количество разных монет с оповещениями SHORT
                if len(self.short_alerts) >= 3:
                    # Первые 3 монеты — это базовые, остальные — "другие"
                    other_short_count = len(self.short_alerts) - 3
                    if other_short_count >= 5:
                        send_telegram_message("Отмена сценария SHORT")
                        self.logger.info("Отправлено оповещение: Отмена сценария SHORT")
                        print("Отправлено оповещение: Отмена сценария SHORT")
                        # Сбрасываем счетчики
                        self.short_alerts.clear()
                        self.short_window_start = None

    def run(self):
        """Запуск TradingEngine для обработки оповещений."""
        self.logger.info("Запуск TradingEngine...")
        print("Запуск TradingEngine...")

        try:
            while self.running:
                self.process_new_alerts()
                time.sleep(5)  # Проверяем новые оповещения каждые 5 секунд
        except KeyboardInterrupt:
            self.logger.info("Остановлено пользователем")
            print("Остановлено пользователем")
            self.running = False
            self.price_monitor.running = False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в цикле: {e}")
            print(f"Неожиданная ошибка в цикле: {e}")
            self.running = False
            self.price_monitor.running = False

if __name__ == "__main__":
    # Инициализируем PriceMonitor
    price_monitor = PriceMonitor()

    # Инициализируем TradingEngine
    trading_engine = TradingEngine(price_monitor)

    # Запускаем PriceMonitor в отдельном потоке
    monitor_thread = threading.Thread(target=price_monitor.run)
    monitor_thread.daemon = True
    monitor_thread.start()

    # Запускаем TradingEngine в основном потоке
    trading_engine.run()
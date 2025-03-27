import os

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

ALERT_TIMEOUT_MINUTES = 60  # Для тестов 1 минута, в продакшне можно установить 60

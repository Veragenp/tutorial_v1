import logging
from trade_manager import TradeManager
from config import BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_TOKEN, CHAT_ID

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/trade_manager.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    trade_manager = TradeManager(BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_TOKEN, CHAT_ID)
    trade_manager.run()
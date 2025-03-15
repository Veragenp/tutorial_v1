import requests
from config import TELEGRAM_TOKEN, CHAT_ID

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"Сообщение отправлено в Telegram: {text}")
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
import requests
from telegram_config import BOT_TOKEN, CHAT_ID

def notify(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       message,
            "parse_mode": "HTML"
        })
    except Exception as e:
        print(f"Telegram notify failed: {e}")
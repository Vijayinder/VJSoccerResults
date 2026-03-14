import requests
import json
import os

from telegram_config import BOT_TOKEN, CHAT_ID

# File to store last sent message IDs for deletion on next run
MSG_IDS_FILE = os.path.join(os.path.dirname(__file__), '.last_msg_ids.json')


def _load_msg_ids():
    try:
        with open(MSG_IDS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def _save_msg_ids(ids):
    try:
        with open(MSG_IDS_FILE, 'w') as f:
            json.dump(ids, f)
    except Exception as e:
        print(f"Could not save msg IDs: {e}")


def delete_previous():
    """Delete all messages from the previous pipeline run."""
    ids = _load_msg_ids()
    if not ids:
        return
    for msg_id in ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                json={"chat_id": CHAT_ID, "message_id": msg_id}
            )
        except Exception as e:
            print(f"Could not delete message {msg_id}: {e}")
    # Clear the file after deletion
    _save_msg_ids([])
    print(f"Deleted {len(ids)} previous messages")


def notify(message: str, track: bool = True):
    """Send a message. If track=True, store the message ID for deletion next run."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       message,
            "parse_mode": "HTML"
        })
        if track and resp.ok:
            msg_id = resp.json().get("result", {}).get("message_id")
            if msg_id:
                ids = _load_msg_ids()
                ids.append(msg_id)
                _save_msg_ids(ids)
    except Exception as e:
        print(f"Telegram notify failed: {e}")

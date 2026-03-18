import requests
import json
import os
from datetime import datetime, timezone, timedelta

from telegram_config import BOT_TOKEN, CHAT_ID

AEST = timezone(timedelta(hours=11))

# File to store last sent message IDs for deletion on next run
MSG_IDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.last_msg_ids.json')

# Append-only audit log
AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_audit.log')


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


def _audit(event: str, message: str = ''):
    try:
        ts      = datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S AEST')
        preview = message.replace('\n', ' ')[:120]
        with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {event}: {preview}\n")
    except Exception as e:
        print(f"Audit log failed: {e}")


def delete_previous():
    """Delete all messages from the previous pipeline run."""
    ids = _load_msg_ids()
    if not ids:
        _audit('DELETE', 'No previous messages to delete')
        return
    deleted = 0
    for msg_id in ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                json={"chat_id": CHAT_ID, "message_id": msg_id}
            )
            deleted += 1
        except Exception as e:
            print(f"Could not delete message {msg_id}: {e}")
    _save_msg_ids([])
    _audit('DELETE', f'Deleted {deleted}/{len(ids)} previous messages')
    print(f"Deleted {deleted} previous messages")


def notify(message: str, track: bool = True):
    """Send a Telegram message. Stores message ID for deletion next run."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       message,
            "parse_mode": "HTML"
        })
        if resp.ok:
            msg_id = resp.json().get("result", {}).get("message_id")
            if track and msg_id:
                ids = _load_msg_ids()
                ids.append(msg_id)
                _save_msg_ids(ids)
            _audit('SENT', message)
        else:
            _audit('FAILED', f'HTTP {resp.status_code} — {message}')
            print(f"Telegram API error: {resp.status_code} {resp.text}")
    except Exception as e:
        _audit('ERROR', str(e))
        print(f"Telegram notify failed: {e}")
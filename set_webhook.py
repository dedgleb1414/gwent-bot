"""
Запусти этот скрипт ОДИН РАЗ после деплоя на Vercel.
Переменные можно задать через .env или напрямую в терминале.

Windows PowerShell (каждую строку ОТДЕЛЬНО):
  $env:BOT_TOKEN="токен"
  $env:BASE_URL="https://твой-проект.vercel.app"
  $env:WEBHOOK_SECRET="любая_строка"
  python set_webhook.py
"""
import os
import requests

BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
BASE_URL       = os.environ.get("BASE_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "gwentsecret")

if not BOT_TOKEN or not BASE_URL:
    print("❌ Задайте BOT_TOKEN и BASE_URL")
    exit(1)

webhook_url = f"{BASE_URL.rstrip('/')}/webhook"

resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={
        "url": webhook_url,
        "secret_token": WEBHOOK_SECRET,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    },
    timeout=10,
)
data = resp.json()

if data.get("ok"):
    print(f"✅ Webhook установлен: {webhook_url}")
    print(f"   Проверка: https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
else:
    print(f"❌ Ошибка: {data}")

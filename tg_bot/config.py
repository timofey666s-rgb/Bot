import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле")

ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

DB_PATH: str = os.getenv("DB_PATH", "bot_database.db")

# Напоминание за N минут до записи
REMINDER_BEFORE_MINUTES: int = int(os.getenv("REMINDER_BEFORE_MINUTES", "60"))

"""
bot.py — точка входа.

Запуск:
    python bot.py
"""
import asyncio
import logging
import sys
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, REMINDER_BEFORE_MINUTES
from database import (
    get_upcoming_appointments_to_remind,
    init_db,
    mark_reminded,
)
from handlers import appointments, booking, start

# ──────────────────────── logging ────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ──────────────────────── reminder task ────────────────────────

async def send_reminders(bot: Bot) -> None:
    """Фоновая задача: отправка напоминаний каждую минуту."""
    while True:
        try:
            records = await get_upcoming_appointments_to_remind(REMINDER_BEFORE_MINUTES)
            for rec in records:
                dt_str = rec["appointment_dt"][:16]
                text = (
                    f"⏰ <b>Напоминание!</b>\n\n"
                    f"Через {REMINDER_BEFORE_MINUTES} минут у вас запись:\n"
                    f"🛎 <b>{rec['service_name']}</b>\n"
                    f"📅 {dt_str}\n\n"
                    f"Запись #{rec['id']}"
                )
                try:
                    await bot.send_message(rec["user_id"], text, parse_mode=ParseMode.HTML)
                    await mark_reminded(rec["id"])
                    logger.info("Напоминание отправлено: appt_id=%s user_id=%s", rec["id"], rec["user_id"])
                except Exception as exc:
                    logger.warning("Ошибка отправки напоминания user=%s: %s", rec["user_id"], exc)
        except Exception as exc:
            logger.error("Ошибка в задаче напоминаний: %s", exc)
        await asyncio.sleep(60)


# ──────────────────────── main ────────────────────────

async def main() -> None:
    logger.info("Инициализация бота...")
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(appointments.router)

    logger.info("Бот запущен. Начало polling.")
    reminder_task = asyncio.create_task(send_reminders(bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        reminder_task.cancel()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())

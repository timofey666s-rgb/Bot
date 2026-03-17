import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database import upsert_user

router = Router()
logger = logging.getLogger(__name__)


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Записаться на услугу", callback_data="book_start"),
        ],
        [
            InlineKeyboardButton(text="📋 Мои записи",          callback_data="my_appointments"),
            InlineKeyboardButton(text="ℹ️ Помощь",              callback_data="help"),
        ],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await upsert_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
    logger.info("/start от user_id=%s (@%s)", user.id, user.username)

    await message.answer(
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        "Добро пожаловать в бот записи на услуги.\n"
        "Выберите действие в меню ниже:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )

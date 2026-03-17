"""Просмотр и отмена записей пользователя."""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import cancel_appointment, get_user_appointments

router = Router()
logger = logging.getLogger(__name__)


def _appointments_kb(appointments: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for a in appointments:
        if a["status"] == "confirmed":
            rows.append([
                InlineKeyboardButton(
                    text=f"❌ Отменить #{a['id']} — {a['service_name']} {a['appointment_dt'][:16]}",
                    callback_data=f"cancel_appt_{a['id']}",
                )
            ])
    rows.append([InlineKeyboardButton(text="◀️ В главное меню", callback_data="go_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "my_appointments")
async def cb_my_appointments(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    appointments = await get_user_appointments(user_id)
    logger.info("Просмотр записей user_id=%s", user_id)

    if not appointments:
        from handlers.start import main_menu_kb
        await call.message.edit_text(
            "📋 У вас пока нет записей.",
            reply_markup=main_menu_kb(),
        )
        await call.answer()
        return

    lines = ["📋 <b>Ваши записи:</b>\n"]
    for a in appointments:
        status_icon = {"confirmed": "✅", "cancelled": "❌", "pending": "⏳"}.get(a["status"], "❓")
        lines.append(
            f"{status_icon} <b>#{a['id']}</b> — {a['service_name']}\n"
            f"   📅 {a['appointment_dt'][:16]}  ({a['duration']} мин)"
        )

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_appointments_kb(appointments),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cancel_appt_"))
async def cb_cancel_appointment(call: CallbackQuery) -> None:
    appt_id = int(call.data.split("_")[2])
    changed = await cancel_appointment(appt_id=appt_id, user_id=call.from_user.id)

    if changed:
        await call.answer("Запись отменена.", show_alert=True)
    else:
        await call.answer("Не удалось отменить запись (уже отменена?).", show_alert=True)

    # Обновить список
    appointments = await get_user_appointments(call.from_user.id)
    lines = ["📋 <b>Ваши записи:</b>\n"]
    for a in appointments:
        status_icon = {"confirmed": "✅", "cancelled": "❌", "pending": "⏳"}.get(a["status"], "❓")
        lines.append(
            f"{status_icon} <b>#{a['id']}</b> — {a['service_name']}\n"
            f"   📅 {a['appointment_dt'][:16]}  ({a['duration']} мин)"
        )

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_appointments_kb(appointments),
    )


@router.callback_query(F.data == "go_home")
async def cb_go_home(call: CallbackQuery) -> None:
    from handlers.start import main_menu_kb
    await call.message.edit_text(
        "🏠 Главное меню:",
        reply_markup=main_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery) -> None:
    from handlers.start import main_menu_kb
    await call.message.edit_text(
        "ℹ️ <b>Помощь</b>\n\n"
        "Этот бот поможет вам записаться на услуги:\n\n"
        "• <b>Записаться</b> — выберите услугу, дату и время\n"
        "• <b>Мои записи</b> — просмотр и отмена записей\n"
        "• Напоминание придёт за 1 час до записи\n\n"
        "По вопросам: @support",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await call.answer()

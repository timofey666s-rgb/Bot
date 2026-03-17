"""
Обработчики записи на услуги (FSM).

Шаги:
  1. Выбор услуги
  2. Выбор даты (следующие 7 дней)
  3. Выбор времени
  4. Подтверждение
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database import (
    create_appointment,
    get_all_services,
    get_service,
)

router = Router()
logger = logging.getLogger(__name__)

AVAILABLE_TIMES = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]


class BookingFSM(StatesGroup):
    choose_service = State()
    choose_date    = State()
    choose_time    = State()
    confirm        = State()


# ───────────────── helpers ─────────────────

def _services_kb(services: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"✦ {s['name']} ({s['duration']} мин)",
            callback_data=f"svc_{s['id']}",
        )]
        for s in services
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dates_kb() -> InlineKeyboardMarkup:
    today = datetime.now().date()
    rows = []
    for i in range(1, 8):
        day = today + timedelta(days=i)
        label = day.strftime("%d %B %Y (%A)")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"date_{day.isoformat()}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="book_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _times_kb() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=t, callback_data=f"time_{t}")
        for t in AVAILABLE_TIMES
    ]
    # 2 кнопки в ряд
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_date")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="cancel_booking"),
        ],
    ])


# ───────────────── step 0 – entry ─────────────────

@router.callback_query(F.data == "book_start")
async def cb_book_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    services = await get_all_services()
    logger.info("Выбор услуги: user_id=%s", call.from_user.id)
    await call.message.edit_text(
        "🛎 <b>Шаг 1 / 4 — Выберите услугу:</b>",
        parse_mode="HTML",
        reply_markup=_services_kb(services),
    )
    await state.set_state(BookingFSM.choose_service)
    await call.answer()


# ───────────────── step 1 – service ─────────────────

@router.callback_query(BookingFSM.choose_service, F.data.startswith("svc_"))
async def cb_choose_service(call: CallbackQuery, state: FSMContext) -> None:
    service_id = int(call.data.split("_")[1])
    service = await get_service(service_id)
    if not service:
        await call.answer("Услуга не найдена.", show_alert=True)
        return

    await state.update_data(service_id=service_id, service_name=service["name"])
    logger.info("Выбрана услуга %s user_id=%s", service["name"], call.from_user.id)

    await call.message.edit_text(
        f"📌 Услуга: <b>{service['name']}</b> ({service['duration']} мин)\n\n"
        "📅 <b>Шаг 2 / 4 — Выберите дату:</b>",
        parse_mode="HTML",
        reply_markup=_dates_kb(),
    )
    await state.set_state(BookingFSM.choose_date)
    await call.answer()


# ───────────────── step 2 – date ─────────────────

@router.callback_query(BookingFSM.choose_date, F.data.startswith("date_"))
async def cb_choose_date(call: CallbackQuery, state: FSMContext) -> None:
    date_str = call.data.split("_", 1)[1]
    await state.update_data(date_str=date_str)
    data = await state.get_data()
    logger.info("Выбрана дата %s user_id=%s", date_str, call.from_user.id)

    await call.message.edit_text(
        f"📌 Услуга: <b>{data['service_name']}</b>\n"
        f"📅 Дата: <b>{date_str}</b>\n\n"
        "🕐 <b>Шаг 3 / 4 — Выберите время:</b>",
        parse_mode="HTML",
        reply_markup=_times_kb(),
    )
    await state.set_state(BookingFSM.choose_time)
    await call.answer()


@router.callback_query(BookingFSM.choose_time, F.data == "back_to_date")
async def cb_back_to_date(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        "📅 <b>Шаг 2 / 4 — Выберите дату:</b>",
        parse_mode="HTML",
        reply_markup=_dates_kb(),
    )
    await state.set_state(BookingFSM.choose_date)
    await call.answer()


# ───────────────── step 3 – time ─────────────────

@router.callback_query(BookingFSM.choose_time, F.data.startswith("time_"))
async def cb_choose_time(call: CallbackQuery, state: FSMContext) -> None:
    time_str = call.data.split("_", 1)[1]
    await state.update_data(time_str=time_str)
    data = await state.get_data()
    logger.info("Выбрано время %s user_id=%s", time_str, call.from_user.id)

    await call.message.edit_text(
        "📋 <b>Шаг 4 / 4 — Подтверждение записи:</b>\n\n"
        f"🛎 Услуга: <b>{data['service_name']}</b>\n"
        f"📅 Дата:   <b>{data['date_str']}</b>\n"
        f"🕐 Время:  <b>{time_str}</b>\n\n"
        "Всё верно?",
        parse_mode="HTML",
        reply_markup=_confirm_kb(),
    )
    await state.set_state(BookingFSM.confirm)
    await call.answer()


# ───────────────── step 4 – confirm ─────────────────

@router.callback_query(BookingFSM.confirm, F.data == "confirm_booking")
async def cb_confirm_booking(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    dt = datetime.fromisoformat(f"{data['date_str']}T{data['time_str']}:00")

    appt_id = await create_appointment(
        user_id=call.from_user.id,
        service_id=data["service_id"],
        appointment_dt=dt,
    )
    await state.clear()
    logger.info("Запись #%s подтверждена user_id=%s", appt_id, call.from_user.id)

    from handlers.start import main_menu_kb
    await call.message.edit_text(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"🛎 Услуга: <b>{data['service_name']}</b>\n"
        f"📅 Дата:   <b>{data['date_str']}</b>\n"
        f"🕐 Время:  <b>{data['time_str']}</b>\n"
        f"🆔 Номер записи: <code>#{appt_id}</code>\n\n"
        "Мы пришлём напоминание за час до приёма.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await call.answer("Запись создана!", show_alert=False)


# ───────────────── cancel (any step) ─────────────────

@router.callback_query(F.data == "cancel_booking")
async def cb_cancel_booking(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    logger.info("Отмена бронирования user_id=%s", call.from_user.id)
    from handlers.start import main_menu_kb
    await call.message.edit_text(
        "❌ Запись отменена. Возвращаю в главное меню.",
        reply_markup=main_menu_kb(),
    )
    await call.answer()

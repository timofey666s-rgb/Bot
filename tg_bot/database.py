import logging
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Инициализация базы данных и создание таблиц."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY,
                user_id     INTEGER UNIQUE NOT NULL,
                username    TEXT,
                full_name   TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                duration    INTEGER NOT NULL,
                description TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                service_id      INTEGER NOT NULL,
                appointment_dt  TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                reminded        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (user_id)    REFERENCES users(user_id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)
        # Заполним тестовые услуги, если их ещё нет
        cursor = await db.execute("SELECT COUNT(*) FROM services")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.executemany(
                "INSERT INTO services (name, duration, description) VALUES (?, ?, ?)",
                [
                    ("Стрижка", 60, "Мужская / женская стрижка"),
                    ("Маникюр", 90, "Классический маникюр с покрытием"),
                    ("Консультация", 30, "Индивидуальная консультация специалиста"),
                    ("Массаж", 60, "Расслабляющий массаж спины"),
                ],
            )
        await db.commit()
    logger.info("База данных инициализирована: %s", DB_PATH)


# ──────────────────────────── users ────────────────────────────

async def upsert_user(user_id: int, username: Optional[str], full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (user_id, username, full_name, datetime.now().isoformat()))
        await db.commit()
    logger.debug("upsert_user: user_id=%s", user_id)


# ──────────────────────────── services ────────────────────────────

async def get_all_services() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM services ORDER BY id")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_service(service_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


# ──────────────────────────── appointments ────────────────────────────

async def create_appointment(
    user_id: int,
    service_id: int,
    appointment_dt: datetime,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO appointments (user_id, service_id, appointment_dt, status, created_at)
            VALUES (?, ?, ?, 'confirmed', ?)
        """, (user_id, service_id, appointment_dt.isoformat(), datetime.now().isoformat()))
        await db.commit()
        appt_id = cursor.lastrowid
    logger.info("Создана запись #%s: user=%s service=%s dt=%s", appt_id, user_id, service_id, appointment_dt)
    return appt_id


async def get_user_appointments(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT a.id, a.appointment_dt, a.status, a.reminded,
                   s.name AS service_name, s.duration
            FROM appointments a
            JOIN services s ON s.id = a.service_id
            WHERE a.user_id = ?
            ORDER BY a.appointment_dt DESC
        """, (user_id,))
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def cancel_appointment(appt_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE appointments
            SET status = 'cancelled'
            WHERE id = ? AND user_id = ? AND status != 'cancelled'
        """, (appt_id, user_id))
        await db.commit()
        changed = cursor.rowcount > 0
    if changed:
        logger.info("Отменена запись #%s пользователем %s", appt_id, user_id)
    return changed


async def get_upcoming_appointments_to_remind(before_minutes: int) -> list[dict]:
    """Возвращает записи, которым пора отправить напоминание."""
    from datetime import timedelta
    now = datetime.now()
    remind_before = (now + timedelta(minutes=before_minutes)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT a.id, a.user_id, a.appointment_dt,
                   s.name AS service_name
            FROM appointments a
            JOIN services s ON s.id = a.service_id
            WHERE a.status = 'confirmed'
              AND a.reminded = 0
              AND a.appointment_dt <= ?
              AND a.appointment_dt >= ?
        """, (remind_before, now.isoformat()))
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def mark_reminded(appt_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET reminded = 1 WHERE id = ?", (appt_id,)
        )
        await db.commit()

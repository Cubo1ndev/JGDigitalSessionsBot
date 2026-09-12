import random
import aiosqlite
from datetime import datetime, timezone

MIN_SESSION_ID = 100_000_000
MAX_SESSION_ID = 999_999_999

_db_path: str = ""


def set_path(path: str) -> None:
    global _db_path
    _db_path = path


async def init_db() -> None:
    async with aiosqlite.connect(_db_path) as db:
        # WAL mode lets concurrent Join/Leave button clicks (each opening their own
        # connection) read/write without blocking each other as easily.
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id             INTEGER PRIMARY KEY,
                guild_id       TEXT    NOT NULL,
                channel_id     TEXT    NOT NULL,
                message_id     TEXT,
                host_id        TEXT    NOT NULL,
                company_name   TEXT    NOT NULL,
                max_players    INTEGER NOT NULL,
                start_time_utc TEXT    NOT NULL,
                status         TEXT    NOT NULL DEFAULT 'pending',
                description    TEXT,
                logo_url       TEXT,
                server_name    TEXT,
                reminder_sent  INTEGER NOT NULL DEFAULT 0,
                start_dm_sent  INTEGER NOT NULL DEFAULT 0
            )
        """)
        await _add_missing_columns(db, "sessions", {
            "description": "TEXT",
            "logo_url": "TEXT",
            "server_name": "TEXT",
            "reminder_sent": "INTEGER NOT NULL DEFAULT 0",
            "start_dm_sent": "INTEGER NOT NULL DEFAULT 0",
        })
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_players (
                session_id INTEGER NOT NULL,
                user_id    TEXT    NOT NULL,
                joined_at  TEXT    NOT NULL,
                PRIMARY KEY (session_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS host_roles (
                guild_id TEXT PRIMARY KEY,
                role_id  TEXT NOT NULL
            )
        """)
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _add_missing_columns(db: aiosqlite.Connection, table: str, columns: dict[str, str]) -> None:
    """Adds any column in `columns` (name -> SQL type) missing from an already-existing table."""
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        existing = {row[1] async for row in cur}
    for name, sql_type in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


# --- Host roles ---

async def set_host_role(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO host_roles (guild_id, role_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id",
            (str(guild_id), str(role_id)),
        )
        await db.commit()


async def get_host_role(guild_id: int) -> int | None:
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT role_id FROM host_roles WHERE guild_id = ?", (str(guild_id),)
        ) as cur:
            row = await cur.fetchone()
    return int(row[0]) if row else None


# --- Sessions ---

async def create_session(
    guild_id: int,
    channel_id: int,
    host_id: int,
    company_name: str,
    max_players: int,
    start_time_utc: datetime,
    description: str | None = None,
    logo_url: str | None = None,
    server_name: str | None = None,
) -> int:
    """Returns the new session's id (a random 9-digit number, not sequential)."""
    async with aiosqlite.connect(_db_path) as db:
        while True:
            session_id = random.randint(MIN_SESSION_ID, MAX_SESSION_ID)
            try:
                await db.execute(
                    "INSERT INTO sessions "
                    "(id, guild_id, channel_id, host_id, company_name, max_players, start_time_utc, "
                    "description, logo_url, server_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        str(guild_id),
                        str(channel_id),
                        str(host_id),
                        company_name,
                        max_players,
                        start_time_utc.isoformat(),
                        description,
                        logo_url,
                        server_name,
                    ),
                )
            except aiosqlite.IntegrityError:
                continue
            await db.commit()
            return session_id


async def set_session_message(session_id: int, message_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE sessions SET message_id = ? WHERE id = ?", (str(message_id), session_id)
        )
        await db.commit()


async def get_session(session_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_pending_sessions() -> list[dict]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE status = 'pending'") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_pending_sessions_for_guild(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE status = 'pending' AND guild_id = ? "
            "ORDER BY start_time_utc ASC",
            (str(guild_id),),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_active_sessions_for_guild(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE status = 'fired' AND guild_id = ? "
            "ORDER BY start_time_utc ASC",
            (str(guild_id),),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_due_sessions() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE status = 'pending' AND start_time_utc <= ?", (now,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def set_session_status(session_id: int, status: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
        await db.commit()


async def mark_session_reminder_sent(session_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE sessions SET reminder_sent = 1 WHERE id = ?", (session_id,)
        )
        await db.commit()


async def mark_session_start_dm_sent(session_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE sessions SET start_dm_sent = 1 WHERE id = ?", (session_id,)
        )
        await db.commit()


async def update_session_max_players(session_id: int, max_players: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE sessions SET max_players = ? WHERE id = ?", (max_players, session_id)
        )
        await db.commit()


async def update_session_server_name(session_id: int, server_name: str | None) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE sessions SET server_name = ? WHERE id = ?", (server_name, session_id)
        )
        await db.commit()


# --- Session players ---

async def add_player(session_id: int, user_id: int) -> bool:
    """Returns False if the user already joined."""
    async with aiosqlite.connect(_db_path) as db:
        try:
            await db.execute(
                "INSERT INTO session_players (session_id, user_id, joined_at) VALUES (?, ?, ?)",
                (session_id, str(user_id), _now()),
            )
        except aiosqlite.IntegrityError:
            return False
        await db.commit()
    return True


async def remove_player(session_id: int, user_id: int) -> bool:
    """Returns False if the user hadn't joined."""
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            "DELETE FROM session_players WHERE session_id = ? AND user_id = ?",
            (session_id, str(user_id)),
        )
        await db.commit()
    return cur.rowcount > 0


async def get_players(session_id: int) -> list[int]:
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT user_id FROM session_players WHERE session_id = ?", (session_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [int(r[0]) for r in rows]


async def count_players(session_id: int) -> int:
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM session_players WHERE session_id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0]

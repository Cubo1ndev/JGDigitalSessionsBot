import aiosqlite
from datetime import datetime, timezone

_db_path: str = ""


def set_path(path: str) -> None:
    global _db_path
    _db_path = path


async def init_db() -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id       TEXT    NOT NULL,
                channel_id     TEXT    NOT NULL,
                message_id     TEXT,
                host_id        TEXT    NOT NULL,
                company_name   TEXT    NOT NULL,
                max_players    INTEGER NOT NULL,
                start_time_utc TEXT    NOT NULL,
                status         TEXT    NOT NULL DEFAULT 'pending'
            )
        """)
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
        # Offset the id sequence so session ids read as long ids (100000001, ...)
        # instead of small ones (1, 2, ...).
        await db.execute(
            "INSERT INTO sqlite_sequence (name, seq) "
            "SELECT 'sessions', 100000000 "
            "WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = 'sessions')"
        )
        await db.execute(
            "UPDATE sqlite_sequence SET seq = 100000000 "
            "WHERE name = 'sessions' AND seq < 100000000"
        )
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
) -> int:
    """Returns the new session's id."""
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            "INSERT INTO sessions (guild_id, channel_id, host_id, company_name, max_players, start_time_utc) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(guild_id), str(channel_id), str(host_id), company_name, max_players, start_time_utc.isoformat()),
        )
        await db.commit()
        return cur.lastrowid


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


# --- Session players ---

async def add_player(session_id: int, user_id: int) -> bool:
    """Returns False if the user already joined."""
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT 1 FROM session_players WHERE session_id = ? AND user_id = ?",
            (session_id, str(user_id)),
        ) as cur:
            if await cur.fetchone():
                return False
        await db.execute(
            "INSERT INTO session_players (session_id, user_id, joined_at) VALUES (?, ?, ?)",
            (session_id, str(user_id), _now()),
        )
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

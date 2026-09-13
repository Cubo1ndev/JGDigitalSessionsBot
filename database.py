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
                host_name      TEXT,
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
            "host_name": "TEXT",
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_config (
                guild_id         TEXT PRIMARY KEY,
                forum_channel_id TEXT,
                staff_channel_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_posts (
                thread_id      TEXT PRIMARY KEY,
                guild_id       TEXT    NOT NULL,
                author_id      TEXT    NOT NULL,
                vote_message_id TEXT,
                status         TEXT    NOT NULL DEFAULT 'open',
                created_at     TEXT    NOT NULL,
                suggestion_text TEXT   NOT NULL DEFAULT '',
                channel_id     TEXT
            )
        """)
        await _add_missing_columns(db, "suggestion_posts", {
            "suggestion_text": "TEXT NOT NULL DEFAULT ''",
            "channel_id": "TEXT",
        })
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_votes (
                thread_id TEXT    NOT NULL,
                user_id   TEXT    NOT NULL,
                value     INTEGER NOT NULL,
                PRIMARY KEY (thread_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_duplicate_reports (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id         TEXT    NOT NULL,
                thread_a_id      TEXT    NOT NULL,
                thread_b_id      TEXT    NOT NULL,
                report_message_id TEXT,
                status           TEXT    NOT NULL DEFAULT 'pending'
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
    host_name: str | None = None,
) -> int:
    """Returns the new session's id (a random 9-digit number, not sequential)."""
    async with aiosqlite.connect(_db_path) as db:
        while True:
            session_id = random.randint(MIN_SESSION_ID, MAX_SESSION_ID)
            try:
                await db.execute(
                    "INSERT INTO sessions "
                    "(id, guild_id, channel_id, host_id, host_name, company_name, max_players, start_time_utc, "
                    "description, logo_url, server_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" ,
                    (
                        session_id,
                        str(guild_id),
                        str(channel_id),
                        str(host_id),
                        host_name,
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


# --- Suggestion config ---

async def set_suggestions_channel(guild_id: int, channel_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO suggestion_config (guild_id, forum_channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET forum_channel_id = excluded.forum_channel_id",
            (str(guild_id), str(channel_id)),
        )
        await db.commit()


async def set_suggestion_staff_channel(guild_id: int, channel_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO suggestion_config (guild_id, staff_channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET staff_channel_id = excluded.staff_channel_id",
            (str(guild_id), str(channel_id)),
        )
        await db.commit()


async def get_suggestion_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_config WHERE guild_id = ?", (str(guild_id),)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return {
        "guild_id": int(row["guild_id"]),
        "suggestions_channel_id": int(row["forum_channel_id"]) if row["forum_channel_id"] else None,
        "staff_channel_id": int(row["staff_channel_id"]) if row["staff_channel_id"] else None,
    }


# --- Suggestion posts ---

async def create_suggestion_post(
    thread_id: int,
    guild_id: int,
    author_id: int,
    suggestion_text: str,
    channel_id: int | None = None,
    vote_message_id: int | None = None,
) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO suggestion_posts "
            "(thread_id, guild_id, author_id, created_at, suggestion_text, channel_id, vote_message_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(thread_id),
                str(guild_id),
                str(author_id),
                _now(),
                suggestion_text,
                str(channel_id) if channel_id is not None else None,
                str(vote_message_id) if vote_message_id is not None else None,
            ),
        )
        await db.commit()


async def get_suggestion_post(thread_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_posts WHERE thread_id = ?", (str(thread_id),)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_suggestion_post_by_vote_message(vote_message_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_posts WHERE vote_message_id = ?", (str(vote_message_id),)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def set_suggestion_status(thread_id: int, status: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE suggestion_posts SET status = ? WHERE thread_id = ?", (status, str(thread_id))
        )
        await db.commit()


async def get_open_suggestion_posts(guild_id: int, limit: int = 50) -> list[dict]:
    """Most recently created open suggestions first, capped at `limit`."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_posts WHERE guild_id = ? AND status = 'open' "
            "ORDER BY created_at DESC LIMIT ?",
            (str(guild_id), limit),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_open_suggestion_threads() -> list[int]:
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute("SELECT thread_id FROM suggestion_posts WHERE status = 'open'") as cur:
            rows = await cur.fetchall()
    return [int(r[0]) for r in rows]


async def get_ranked_open_suggestions(guild_id: int) -> list[dict]:
    """Open suggestions for a guild ranked by net score (upvotes - downvotes) desc, oldest first on ties."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT p.thread_id, p.author_id, p.created_at,
                   COALESCE(SUM(CASE WHEN v.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
                   COALESCE(SUM(CASE WHEN v.value = -1 THEN 1 ELSE 0 END), 0) AS downvotes
            FROM suggestion_posts p
            LEFT JOIN suggestion_votes v ON v.thread_id = p.thread_id
            WHERE p.guild_id = ? AND p.status = 'open'
            GROUP BY p.thread_id
            ORDER BY (upvotes - downvotes) DESC, p.created_at ASC
            """,
            (str(guild_id),),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# --- Suggestion votes ---

async def set_suggestion_vote(thread_id: int, user_id: int, value: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO suggestion_votes (thread_id, user_id, value) VALUES (?, ?, ?) "
            "ON CONFLICT(thread_id, user_id) DO UPDATE SET value = excluded.value",
            (str(thread_id), str(user_id), value),
        )
        await db.commit()


async def remove_suggestion_vote(thread_id: int, user_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "DELETE FROM suggestion_votes WHERE thread_id = ? AND user_id = ?",
            (str(thread_id), str(user_id)),
        )
        await db.commit()


async def get_suggestion_vote(thread_id: int, user_id: int) -> int | None:
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT value FROM suggestion_votes WHERE thread_id = ? AND user_id = ?",
            (str(thread_id), str(user_id)),
        ) as cur:
            row = await cur.fetchone()
    return int(row[0]) if row else None


async def get_suggestion_vote_counts(thread_id: int) -> tuple[int, int]:
    """Returns (upvotes, downvotes)."""
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END), 0) "
            "FROM suggestion_votes WHERE thread_id = ?",
            (str(thread_id),),
        ) as cur:
            row = await cur.fetchone()
    return (row[0], row[1])


# --- Suggestion duplicate reports ---

async def create_duplicate_report(guild_id: int, thread_a_id: int, thread_b_id: int) -> int:
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            "INSERT INTO suggestion_duplicate_reports (guild_id, thread_a_id, thread_b_id) "
            "VALUES (?, ?, ?)",
            (str(guild_id), str(thread_a_id), str(thread_b_id)),
        )
        await db.commit()
        return cur.lastrowid


async def set_duplicate_report_message(report_id: int, message_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE suggestion_duplicate_reports SET report_message_id = ? WHERE id = ?",
            (str(message_id), report_id),
        )
        await db.commit()


async def get_duplicate_report(report_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_duplicate_reports WHERE id = ?", (report_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def set_duplicate_report_status(report_id: int, status: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE suggestion_duplicate_reports SET status = ? WHERE id = ?", (status, report_id)
        )
        await db.commit()


async def get_pending_duplicate_reports() -> list[dict]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM suggestion_duplicate_reports WHERE status = 'pending'"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]

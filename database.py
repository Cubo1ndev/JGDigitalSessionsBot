import aiosqlite
from datetime import datetime, timezone

_db_path: str = ""


def set_path(path: str) -> None:
    global _db_path
    _db_path = path


async def init_db() -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                user_id TEXT PRIMARY KEY,
                pending INTEGER DEFAULT 0,
                paid    INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                actor_id  TEXT    NOT NULL,
                target_id TEXT    NOT NULL,
                action    TEXT    NOT NULL,
                amount    INTEGER NOT NULL,
                reason    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id    TEXT PRIMARY KEY,
                granted_by TEXT NOT NULL,
                granted_at TEXT NOT NULL
            )
        """)
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# --- Wallet ---

async def get_wallet(user_id: int) -> tuple[int, int]:
    """Returns (pending, paid) for a user. Creates row if absent."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO wallets (user_id) VALUES (?)", (uid,)
        )
        await db.commit()
        async with db.execute(
            "SELECT pending, paid FROM wallets WHERE user_id = ?", (uid,)
        ) as cur:
            row = await cur.fetchone()
    return (row[0], row[1])


async def add_pending(user_id: int, amount: int) -> tuple[int, int]:
    """Adds amount to pending (can be negative). Returns new (pending, paid)."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO wallets (user_id) VALUES (?)", (uid,)
        )
        await db.execute(
            "UPDATE wallets SET pending = pending + ? WHERE user_id = ?",
            (amount, uid),
        )
        await db.commit()
        async with db.execute(
            "SELECT pending, paid FROM wallets WHERE user_id = ?", (uid,)
        ) as cur:
            row = await cur.fetchone()
    return (row[0], row[1])


async def confirm_pay(user_id: int) -> int:
    """Moves all pending to paid. Returns the amount moved."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO wallets (user_id) VALUES (?)", (uid,)
        )
        async with db.execute(
            "SELECT pending FROM wallets WHERE user_id = ?", (uid,)
        ) as cur:
            row = await cur.fetchone()
        moved = row[0]
        if moved > 0:
            await db.execute(
                "UPDATE wallets SET paid = paid + pending, pending = 0 WHERE user_id = ?",
                (uid,),
            )
            await db.commit()
    return moved


# --- History ---

async def add_history(
    actor_id: int,
    target_id: int,
    action: str,
    amount: int,
    reason: str | None = None,
) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "INSERT INTO history (timestamp, actor_id, target_id, action, amount, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), str(actor_id), str(target_id), action, amount, reason),
        )
        await db.commit()


async def get_history(user_id: int) -> list[dict]:
    """Returns all history entries where actor or target is user_id, newest first."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM history WHERE actor_id = ? OR target_id = ? ORDER BY id DESC",
            (uid, uid),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_top(field: str, limit: int = 10, offset: int = 0) -> list[tuple[str, int]]:
    """Returns (user_id, amount) sorted descending for 'pending' or 'paid'."""
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            f"SELECT user_id, {field} FROM wallets WHERE {field} > 0 "
            f"ORDER BY {field} DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
    return [(row[0], row[1]) for row in rows]


async def count_top(field: str) -> int:
    """Returns total number of users with field > 0."""
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            f"SELECT COUNT(*) FROM wallets WHERE {field} > 0"
        ) as cur:
            row = await cur.fetchone()
    return row[0]


# --- Bot admins ---

async def add_bot_admin(user_id: int, granted_by: int) -> bool:
    """Returns False if already an admin."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT 1 FROM bot_admins WHERE user_id = ?", (uid,)
        ) as cur:
            exists = await cur.fetchone()
        if exists:
            return False
        await db.execute(
            "INSERT INTO bot_admins (user_id, granted_by, granted_at) VALUES (?, ?, ?)",
            (uid, str(granted_by), _now()),
        )
        await db.commit()
    return True


async def remove_bot_admin(user_id: int) -> bool:
    """Returns False if user was not an admin."""
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT 1 FROM bot_admins WHERE user_id = ?", (uid,)
        ) as cur:
            exists = await cur.fetchone()
        if not exists:
            return False
        await db.execute("DELETE FROM bot_admins WHERE user_id = ?", (uid,))
        await db.commit()
    return True


async def user_is_bot_admin(user_id: int) -> bool:
    uid = str(user_id)
    async with aiosqlite.connect(_db_path) as db:
        async with db.execute(
            "SELECT 1 FROM bot_admins WHERE user_id = ?", (uid,)
        ) as cur:
            row = await cur.fetchone()
    return row is not None

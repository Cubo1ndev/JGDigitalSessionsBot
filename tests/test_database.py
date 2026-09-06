import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite

import database


def test_session_lifecycle(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        await database.set_host_role(guild_id=1, role_id=99)
        assert await database.get_host_role(1) == 99
        assert await database.get_host_role(2) is None

        start = datetime.now(timezone.utc) + timedelta(days=1)
        session_id = await database.create_session(
            guild_id=1,
            channel_id=2,
            host_id=3,
            company_name="Blue Bird",
            max_players=2,
            start_time_utc=start,
        )
        session = await database.get_session(session_id)
        assert session["company_name"] == "Blue Bird"
        assert session["status"] == "pending"
        assert session in await database.get_pending_sessions()

        assert await database.count_players(session_id) == 0
        assert await database.add_player(session_id, 10) is True
        assert await database.add_player(session_id, 10) is False
        assert await database.count_players(session_id) == 1
        assert await database.get_players(session_id) == [10]

        assert await database.remove_player(session_id, 10) is True
        assert await database.remove_player(session_id, 10) is False
        assert await database.count_players(session_id) == 0

        assert await database.get_due_sessions() == []

        await database.set_session_status(session_id, "fired")
        updated = await database.get_session(session_id)
        assert updated["status"] == "fired"
        assert await database.get_due_sessions() == []
        assert await database.get_pending_sessions() == []

    asyncio.run(run())


def test_create_session_id_is_a_large_random_number(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        first_id = await database.create_session(1, 2, 3, "Co", 5, future)
        second_id = await database.create_session(1, 2, 3, "Co", 5, future)

        assert 100_000_000 <= first_id <= 999_999_999
        assert 100_000_000 <= second_id <= 999_999_999
        assert first_id != second_id

    asyncio.run(run())


def test_create_session_retries_on_id_collision(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        rolls = iter([111111111, 111111111, 222222222])
        monkeypatch.setattr(database.random, "randint", lambda a, b: next(rolls))

        future = datetime.now(timezone.utc) + timedelta(days=1)
        first_id = await database.create_session(1, 2, 3, "Co", 5, future)
        second_id = await database.create_session(1, 2, 3, "Co", 5, future)

        assert first_id == 111111111
        assert second_id == 222222222  # skipped the roll that collided with first_id

    asyncio.run(run())


def test_get_pending_sessions_for_guild_filters_and_orders_by_start_time(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        soon = datetime.now(timezone.utc) + timedelta(minutes=5)
        later = datetime.now(timezone.utc) + timedelta(hours=5)

        other_guild_id = await database.create_session(2, 2, 3, "Other Guild Co", 5, soon)
        later_id = await database.create_session(1, 2, 3, "Later Co", 5, later)
        soon_id = await database.create_session(1, 2, 3, "Soon Co", 5, soon)
        cancelled_id = await database.create_session(1, 2, 3, "Cancelled Co", 5, soon)
        await database.set_session_status(cancelled_id, "cancelled")

        results = await database.get_pending_sessions_for_guild(1)
        result_ids = [s["id"] for s in results]

        assert result_ids == [soon_id, later_id]
        assert other_guild_id not in result_ids
        assert cancelled_id not in result_ids

    asyncio.run(run())


def test_get_due_sessions_only_returns_past_start_time(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)

        future_id = await database.create_session(1, 2, 3, "Future Co", 5, future)
        past_id = await database.create_session(1, 2, 3, "Past Co", 5, past)

        due_ids = {s["id"] for s in await database.get_due_sessions()}
        assert due_ids == {past_id}
        assert future_id not in due_ids

    asyncio.run(run())


def test_create_session_stores_description_and_logo_url(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        session_id = await database.create_session(
            1, 2, 3, "Co", 5, future, description="Come ride with us!", logo_url="https://x/logo.png"
        )
        session = await database.get_session(session_id)

        assert session["description"] == "Come ride with us!"
        assert session["logo_url"] == "https://x/logo.png"

    asyncio.run(run())


def test_create_session_description_and_logo_url_default_to_none(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        session_id = await database.create_session(1, 2, 3, "Co", 5, future)
        session = await database.get_session(session_id)

        assert session["description"] is None
        assert session["logo_url"] is None

    asyncio.run(run())


def test_init_db_adds_missing_columns_to_a_pre_existing_table(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE sessions (
                    id             INTEGER PRIMARY KEY,
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
            await db.commit()

        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        session_id = await database.create_session(
            1, 2, 3, "Co", 5, future, description="desc", logo_url="https://x/logo.png"
        )
        session = await database.get_session(session_id)

        assert session["description"] == "desc"
        assert session["logo_url"] == "https://x/logo.png"

    asyncio.run(run())


def test_get_active_sessions_for_guild_filters_by_status_and_guild(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)

        pending_id = await database.create_session(1, 2, 3, "Pending Co", 5, future)
        active_id = await database.create_session(1, 2, 3, "Active Co", 5, future)
        await database.set_session_status(active_id, "fired")
        other_guild_active_id = await database.create_session(2, 2, 3, "Other Guild Co", 5, future)
        await database.set_session_status(other_guild_active_id, "fired")

        results = await database.get_active_sessions_for_guild(1)
        result_ids = [s["id"] for s in results]

        assert result_ids == [active_id]
        assert pending_id not in result_ids
        assert other_guild_active_id not in result_ids

    asyncio.run(run())

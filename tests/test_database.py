import asyncio
from datetime import datetime, timedelta, timezone

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


def test_session_ids_start_at_a_large_offset(tmp_path):
    db_path = str(tmp_path / "test.db")

    async def run():
        database.set_path(db_path)
        await database.init_db()

        future = datetime.now(timezone.utc) + timedelta(days=1)
        first_id = await database.create_session(1, 2, 3, "Co", 5, future)
        second_id = await database.create_session(1, 2, 3, "Co", 5, future)

        assert first_id >= 100_000_000
        assert second_id == first_id + 1

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

from datetime import datetime, timezone

import pytest

import session_logic


def test_parse_datetime_utc_accepts_valid_future_date():
    dt = session_logic.parse_datetime_utc("2099-01-01 20:00")
    assert dt == datetime(2099, 1, 1, 20, 0, tzinfo=timezone.utc)


def test_parse_datetime_utc_rejects_bad_format():
    with pytest.raises(ValueError):
        session_logic.parse_datetime_utc("tomorrow at 8pm")


def test_parse_datetime_utc_rejects_past_date():
    with pytest.raises(ValueError):
        session_logic.parse_datetime_utc("2000-01-01 20:00")


def test_parse_max_players_accepts_positive_int():
    assert session_logic.parse_max_players("10") == 10


def test_parse_max_players_rejects_non_numeric():
    with pytest.raises(ValueError):
        session_logic.parse_max_players("ten")


def test_parse_max_players_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        session_logic.parse_max_players("0")
    with pytest.raises(ValueError):
        session_logic.parse_max_players("-5")


def test_has_room_true_when_below_capacity():
    assert session_logic.has_room(current_count=3, max_players=5) is True


def test_has_room_false_when_at_capacity():
    assert session_logic.has_room(current_count=5, max_players=5) is False


def test_has_host_permission_administrator_always_allowed():
    assert session_logic.has_host_permission(
        is_administrator=True, member_role_ids=set(), host_role_id=None
    ) is True


def test_has_host_permission_matching_role_allowed():
    assert session_logic.has_host_permission(
        is_administrator=False, member_role_ids={1, 2, 3}, host_role_id=2
    ) is True


def test_has_host_permission_no_host_role_configured_denied():
    assert session_logic.has_host_permission(
        is_administrator=False, member_role_ids={1, 2, 3}, host_role_id=None
    ) is False


def test_has_host_permission_missing_role_denied():
    assert session_logic.has_host_permission(
        is_administrator=False, member_role_ids={1, 3}, host_role_id=2
    ) is False

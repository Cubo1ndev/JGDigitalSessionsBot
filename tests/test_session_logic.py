from datetime import datetime, timezone

import pytest

import session_logic


def test_build_session_datetime_accepts_valid_future_date():
    dt = session_logic.build_session_datetime(year=2099, month=1, day=1, hour=20, minute=0)
    assert dt == datetime(2099, 1, 1, 20, 0, tzinfo=timezone.utc)


def test_build_session_datetime_rejects_invalid_calendar_date():
    with pytest.raises(ValueError):
        session_logic.build_session_datetime(year=2099, month=2, day=30, hour=20, minute=0)


def test_build_session_datetime_rejects_past_date():
    with pytest.raises(ValueError):
        session_logic.build_session_datetime(year=2000, month=1, day=1, hour=20, minute=0)


def test_validate_max_players_accepts_positive_int():
    assert session_logic.validate_max_players(10) == 10


def test_validate_max_players_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        session_logic.validate_max_players(0)
    with pytest.raises(ValueError):
        session_logic.validate_max_players(-5)


def test_validate_max_players_rejects_below_current_count():
    with pytest.raises(ValueError):
        session_logic.validate_max_players(4, current_count=5)
    assert session_logic.validate_max_players(5, current_count=5) == 5
    assert session_logic.validate_max_players(6, current_count=5) == 6


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


def test_can_manage_session_allowed_for_original_host():
    assert session_logic.can_manage_session(is_administrator=False, is_original_host=True) is True


def test_can_manage_session_allowed_for_administrator():
    assert session_logic.can_manage_session(is_administrator=True, is_original_host=False) is True


def test_can_manage_session_denied_for_neither():
    assert session_logic.can_manage_session(is_administrator=False, is_original_host=False) is False


def test_is_image_attachment_true_for_image_content_type():
    assert session_logic.is_image_attachment("image/png") is True


def test_is_image_attachment_false_for_non_image_content_type():
    assert session_logic.is_image_attachment("text/plain") is False


def test_is_image_attachment_false_for_none():
    assert session_logic.is_image_attachment(None) is False

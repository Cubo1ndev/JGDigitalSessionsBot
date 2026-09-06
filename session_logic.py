from datetime import datetime, timezone


def build_session_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Builds a UTC datetime from components. Raises ValueError if invalid or not in the future."""
    try:
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("That date/time doesn't exist. Check the year, month, day, hour, and minute.")
    if dt <= datetime.now(timezone.utc):
        raise ValueError("Date/time must be in the future.")
    return dt


def validate_max_players(value: int) -> int:
    """Raises ValueError if value isn't a positive number of players."""
    if value <= 0:
        raise ValueError("Max players must be greater than 0.")
    return value


def has_room(current_count: int, max_players: int) -> bool:
    return current_count < max_players


def has_host_permission(
    is_administrator: bool, member_role_ids: set[int], host_role_id: int | None
) -> bool:
    if is_administrator:
        return True
    if host_role_id is None:
        return False
    return host_role_id in member_role_ids


def can_manage_session(is_administrator: bool, is_original_host: bool) -> bool:
    return is_administrator or is_original_host


def is_image_attachment(content_type: str | None) -> bool:
    return bool(content_type) and content_type.startswith("image/")

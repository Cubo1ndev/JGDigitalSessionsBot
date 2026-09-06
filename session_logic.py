from datetime import datetime, timezone

DATETIME_FORMAT = "%Y-%m-%d %H:%M"


def parse_datetime_utc(text: str) -> datetime:
    """Parses a 'YYYY-MM-DD HH:MM' string as UTC. Raises ValueError if malformed or not in the future."""
    try:
        dt = datetime.strptime(text.strip(), DATETIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Date/time must be in the format YYYY-MM-DD HH:MM (UTC).")
    if dt <= datetime.now(timezone.utc):
        raise ValueError("Date/time must be in the future.")
    return dt


def parse_max_players(text: str) -> int:
    """Parses a positive integer. Raises ValueError otherwise."""
    try:
        value = int(text.strip())
    except ValueError:
        raise ValueError("Max players must be a whole number.")
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

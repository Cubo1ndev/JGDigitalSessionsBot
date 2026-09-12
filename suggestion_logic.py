import difflib


def net_score(upvotes: int, downvotes: int) -> int:
    return upvotes - downvotes


# ponytail: naive word/char-overlap heuristic (difflib), no semantics. Good enough until
# an AI-based comparison replaces it; candidates are already capped by the caller.
def find_similar_suggestion(
    new_text: str, candidates: list[tuple[str, str]], threshold: float = 0.6
) -> tuple[str, float] | None:
    """candidates: list of (thread_id, text). Returns the best match's (thread_id, ratio) if >= threshold."""
    best_id = None
    best_ratio = 0.0
    for thread_id, text in candidates:
        ratio = difflib.SequenceMatcher(None, new_text.lower(), text.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = thread_id
    if best_id is not None and best_ratio >= threshold:
        return (best_id, best_ratio)
    return None

import suggestion_logic


def test_net_score_positive():
    assert suggestion_logic.net_score(upvotes=10, downvotes=3) == 7


def test_net_score_negative():
    assert suggestion_logic.net_score(upvotes=1, downvotes=5) == -4


def test_find_similar_suggestion_exact_match():
    candidates = [("1", "Add a new bus"), ("2", "Add a red bus")]
    result = suggestion_logic.find_similar_suggestion("Add a new bus", candidates)
    assert result[0] == "1"
    assert result[1] == 1.0


def test_find_similar_suggestion_no_match_returns_none():
    candidates = [("1", "Completely unrelated topic about weather")]
    result = suggestion_logic.find_similar_suggestion("Add a new bus livery", candidates)
    assert result is None


def test_find_similar_suggestion_below_threshold_returns_none():
    candidates = [("1", "Add a new bus livery option")]
    result = suggestion_logic.find_similar_suggestion("Add a new bus livery option", candidates, threshold=1.1)
    assert result is None


def test_find_similar_suggestion_picks_best_match():
    candidates = [
        ("1", "Add snow weather effects"),
        ("2", "Add a new bus livery for the city route"),
    ]
    result = suggestion_logic.find_similar_suggestion("Add a new bus livery for city routes", candidates)
    assert result[0] == "2"

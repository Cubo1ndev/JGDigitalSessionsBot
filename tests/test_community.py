import pytest

from cogs.community import build_community_view, validate_link


def test_validate_link_accepts_http_and_https_urls():
    assert validate_link("https://justgamesdigital.com") == "https://justgamesdigital.com"
    assert validate_link("http://example.com/community") == "http://example.com/community"
    assert validate_link(None) is None


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com",
        "https://",
        "x" * 513,
    ],
)
def test_validate_link_rejects_unsupported_urls(url):
    with pytest.raises(ValueError):
        validate_link(url)


def test_community_view_has_welcome_and_rules_panels():
    view = build_community_view(
        "attachment://welcome_banner.png",
        "attachment://rules_banner.png",
        "https://example.com",
        None,
        None,
        None,
        "https://example.com/rules",
        None,
        None,
    )

    assert len(view.children) == 2
    assert view.timeout is None

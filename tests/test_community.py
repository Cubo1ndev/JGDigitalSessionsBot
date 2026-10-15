import asyncio

import discord

from cogs.community import CommunityView, build_faq_view, build_rules_view, find_banner


def _text_length(view: discord.ui.LayoutView) -> int:
    return sum(len(item.content) for item in view.walk_children() if isinstance(item, discord.ui.TextDisplay))


def test_rules_and_faq_fit_discord_limits():
    assert _text_length(build_rules_view()) <= 4000
    assert _text_length(build_faq_view()) <= 4000
    assert len(build_rules_view().to_components()[0]["components"]) <= 40


def test_find_banner_returns_none_when_missing(tmp_path):
    assert find_banner("welcome_banner", tmp_path) is None
    (tmp_path / "welcome_banner.webp").write_bytes(b"x")
    assert find_banner("welcome_banner", tmp_path) == tmp_path / "welcome_banner.webp"


def test_banners_sit_outside_containers():
    view = CommunityView("welcome_banner.png", "rules_banner.png")
    kinds = [type(child) for child in view.children]
    assert kinds[0] is discord.ui.MediaGallery
    assert kinds[1] is discord.ui.Container
    assert discord.ui.MediaGallery in kinds[2:]
    assert kinds[-1] is discord.ui.Container


def test_rules_and_faq_buttons_reply_privately_with_components():
    sent = []

    class Response:
        async def send_message(self, *args, **kwargs):
            sent.append((args, kwargs))

    class Interaction:
        response = Response()

    view = CommunityView()
    asyncio.run(view.rules_button.callback(Interaction()))
    asyncio.run(view.faq_button.callback(Interaction()))

    assert len(sent) == 2
    for args, kwargs in sent:
        assert args == ()
        assert kwargs["ephemeral"] is True
        assert isinstance(kwargs["view"], discord.ui.LayoutView)
        assert kwargs["view"].children[0].type == discord.ComponentType.container

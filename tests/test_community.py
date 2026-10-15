import asyncio

import discord

import community_content as content
from cogs.community import CommunityView, find_banner


def test_rules_and_faq_fit_in_a_message():
    assert len(content.RULES_TEXT) <= 2000
    assert len(content.FAQ_TEXT) <= 2000


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


def test_rules_and_faq_buttons_reply_privately():
    sent = []

    class Response:
        async def send_message(self, text, **kwargs):
            sent.append((text, kwargs))

    class Interaction:
        response = Response()

    view = CommunityView()
    asyncio.run(view.rules_button.callback(Interaction()))
    asyncio.run(view.faq_button.callback(Interaction()))

    assert [text for text, _ in sent] == [content.RULES_TEXT, content.FAQ_TEXT]
    assert all(kwargs["ephemeral"] is True for _, kwargs in sent)

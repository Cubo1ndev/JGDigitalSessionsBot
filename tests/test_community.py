import asyncio

import discord

import community_content as content
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
    view = CommunityView("welcome_banner.png", "rules_banner.png", "support_banner.png")
    kinds = [type(child) for child in view.children]
    assert kinds.count(discord.ui.MediaGallery) == 3
    assert kinds.count(discord.ui.Container) == 3
    assert kinds[0] is discord.ui.MediaGallery
    assert kinds[-1] is discord.ui.Container
    assert all(
        not isinstance(child, discord.ui.MediaGallery)
        for container in view.children if isinstance(container, discord.ui.Container)
        for child in container.children
    )


def test_support_dropdown_opens_private_thread_pinging_user_and_role(monkeypatch):
    monkeypatch.setenv("SUPPORT_ROLE_ID", "555")
    created, posted, replies = [], [], []

    class Thread:
        mention = "<#1>"

        async def send(self, text, **kwargs):
            posted.append((text, kwargs))

    class Channel(discord.TextChannel):
        def __init__(self):
            pass

        async def create_thread(self, **kwargs):
            created.append(kwargs)
            return Thread()

    class User:
        id = 42
        mention = "<@42>"
        display_name = "Tester"

    class Response:
        async def defer(self, **kwargs):
            pass

    class Followup:
        async def send(self, text, **kwargs):
            replies.append(text)

    class Interaction:
        response = Response()
        followup = Followup()
        channel = Channel()
        user = User()

    view = CommunityView()
    assert len(view.support_select.options) == len(content.SUPPORT_CONTACTS)
    for index in range(len(content.SUPPORT_CONTACTS)):
        view.support_select._values = [str(index)]
        asyncio.run(view.support_select.callback(Interaction()))
        assert created[-1]["type"] == discord.ChannelType.private_thread
        assert "<@42>" in posted[-1][0] and "<@&555>" in posted[-1][0]
        assert "<#1>" in replies[-1]


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

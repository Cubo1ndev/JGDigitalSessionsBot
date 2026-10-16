import asyncio

import discord

import community_content as content
from cogs.community import CloseConfirmView, CommunityView, build_faq_view, build_rules_view, find_banner


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


class _User:
    id = 42
    mention = "<@42>"


def _texts(view):
    return " ".join(
        item.content for item in view.walk_children() if isinstance(item, discord.ui.TextDisplay)
    )


def test_support_dropdown_shows_email_then_continue_opens_numbered_thread(monkeypatch, tmp_path):
    import database

    monkeypatch.setenv("SUPPORT_ROLE_ID", "555")
    database.set_path(str(tmp_path / "t.db"))
    asyncio.run(database.init_db())
    created, posted, sent, edited, followups, logged = [], [], [], [], [], []

    class Thread:
        mention = "<#1>"
        id = 1

        async def send(self, **kwargs):
            posted.append(kwargs)

    class Channel(discord.TextChannel):
        def __init__(self):
            pass

        async def create_thread(self, **kwargs):
            created.append(kwargs)
            return Thread()

    class Response:
        async def send_message(self, **kwargs):
            sent.append(kwargs)

        async def edit_message(self, **kwargs):
            edited.append(kwargs)

    class Followup:
        async def send(self, text, **kwargs):
            followups.append(text)

    class LogChannel:
        async def send(self, **kwargs):
            logged.append(_texts(kwargs["view"]))

    class Client:
        def get_channel(self, _id):
            return LogChannel()

    class Interaction:
        response = Response()
        followup = Followup()
        channel = Channel()
        user = _User()
        client = Client()

    view = CommunityView()
    for index, (_, _, email) in enumerate(content.SUPPORT_CONTACTS):
        view.support_select._values = [str(index)]
        asyncio.run(view.support_select.callback(Interaction()))
        confirm = sent[-1]["view"]
        assert email in _texts(confirm)
        assert sent[-1]["ephemeral"] is True
        assert not created or len(created) == index
        asyncio.run(confirm.continue_button.callback(Interaction()))
        assert created[-1]["type"] == discord.ChannelType.private_thread
        text = _texts(posted[-1]["view"])
        assert "<@42>" in text and "<@&555>" in text
        assert "<#1>" in followups[-1]

    assert created[0]["name"] == "Support-0001"
    assert created[1]["name"] == "Data-Loss-0001"
    assert len(logged) == len(content.SUPPORT_CONTACTS)
    assert "Ticket created" in logged[0] and "<@42>" in logged[0]


def test_close_command_is_staff_only_and_needs_a_ticket(monkeypatch, tmp_path):
    import database
    from cogs.community import Community

    monkeypatch.setenv("SUPPORT_ROLE_ID", "555")
    database.set_path(str(tmp_path / "c.db"))
    asyncio.run(database.init_db())
    sent = []

    class Response:
        async def send_message(self, *args, **kwargs):
            sent.append((args, kwargs))

    class Thread(discord.Thread):
        def __init__(self):
            pass

        id = 9

    class Member(discord.Member):
        def __init__(self):
            pass

        roles = []
        guild_permissions = discord.Permissions.none()

    class Interaction:
        response = Response()
        user = Member()
        channel = Thread()

    cog = Community(None)
    close = Community.close.callback

    asyncio.run(close(cog, Interaction()))
    assert "inside a support ticket" in sent[-1][0][0]

    asyncio.run(database.add_ticket(9, 1, "Support", 42))
    asyncio.run(close(cog, Interaction()))
    assert "support team" in sent[-1][0][0]

    Member.roles = [type("Role", (), {"id": 555})()]
    asyncio.run(close(cog, Interaction()))
    assert isinstance(sent[-1][1]["view"], CloseConfirmView)
    assert sent[-1][1]["ephemeral"] is True


def test_closed_tickets_expire_after_the_delay(tmp_path):
    import database

    database.set_path(str(tmp_path / "e.db"))
    asyncio.run(database.init_db())
    asyncio.run(database.add_ticket(1, 1, "Support", 42))
    assert asyncio.run(database.get_expired_closed_tickets(24)) == []
    asyncio.run(database.mark_ticket_closed(1))
    assert asyncio.run(database.get_expired_closed_tickets(24)) == []
    assert asyncio.run(database.get_expired_closed_tickets(0)) == [1]

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

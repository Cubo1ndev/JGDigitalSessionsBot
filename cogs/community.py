import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

import community_content as content
import database

logger = logging.getLogger(__name__)

BANNER_DIR = Path(__file__).resolve().parent.parent / "assets" / "community"
BANNER_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
NO_MENTIONS = discord.AllowedMentions.none()


def find_banner(stem: str, directory: Path = BANNER_DIR) -> Path | None:
    for extension in BANNER_EXTENSIONS:
        path = directory / f"{stem}{extension}"
        if path.is_file():
            return path
    return None


def _banner(filename: str | None, description: str) -> discord.ui.MediaGallery | None:
    if filename is None:
        return None
    gallery = discord.ui.MediaGallery()
    gallery.add_item(media=f"attachment://{filename}", description=description)
    return gallery


def _link_buttons(links: list[tuple[str, str]]) -> list[discord.ui.Button]:
    return [
        discord.ui.Button(label=label, style=discord.ButtonStyle.link, url=url)
        for label, url in links
        if url
    ]


def _info_view(
    title: str,
    intro: str,
    entries: list[tuple[str, str]],
    footer: str | None = None,
    numbered: bool = False,
) -> discord.ui.LayoutView:
    children: list[discord.ui.Item] = [
        discord.ui.TextDisplay(f"# {title}\n{intro}"),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
    ]
    for index, (heading, body) in enumerate(entries, start=1):
        label = f"{index}. {heading}" if numbered else heading
        children.append(discord.ui.TextDisplay(f"### {label}\n{body}"))
    if footer:
        children.extend([
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(footer),
        ])
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*children))
    return view


def build_rules_view() -> discord.ui.LayoutView:
    return _info_view(
        content.RULES_TITLE, content.RULES_INTRO, content.RULES, content.RULES_NOTES, numbered=True
    )


def build_faq_view() -> discord.ui.LayoutView:
    return _info_view(content.FAQ_TITLE, content.FAQ_INTRO, content.FAQ)


def _support_role_id() -> int | None:
    raw = os.getenv("SUPPORT_ROLE_ID", "").strip()
    return int(raw) if raw.isdigit() else None


TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID", "1003224981255233626"))
TICKET_DELETE_AFTER_HOURS = 24


async def log_ticket_event(
    client: discord.Client, title: str, lines: list[str], colour: discord.Colour
) -> None:
    try:
        channel = client.get_channel(TICKET_LOG_CHANNEL_ID) or await client.fetch_channel(
            TICKET_LOG_CHANNEL_ID
        )
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## {title}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay("\n".join(lines)),
            accent_colour=colour,
        ))
        await channel.send(view=view, allowed_mentions=NO_MENTIONS)
    except (discord.HTTPException, AttributeError):
        logger.exception("Failed to write to the ticket log channel")


class CommunityView(discord.ui.LayoutView):
    def __init__(
        self,
        welcome_banner: str | None = None,
        rules_banner: str | None = None,
        support_banner: str | None = None,
    ) -> None:
        super().__init__(timeout=None)

        welcome_children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"## {content.WELCOME_TITLE}\n{content.WELCOME_TEXT}")
        ]
        welcome_buttons = _link_buttons([
            ("Website", content.WEBSITE_URL),
            ("ROBLOX Group", content.ROBLOX_GROUP_URL),
            ("YouTube", content.YOUTUBE_URL),
            ("TikTok", content.TIKTOK_URL),
            ("X", content.X_URL),
        ])
        if welcome_buttons:
            row = discord.ui.ActionRow(*welcome_buttons)
            welcome_children.extend([discord.ui.Separator(), row])

        self.rules_button = discord.ui.Button(
            label="Rules", style=discord.ButtonStyle.secondary, custom_id="community:rules"
        )
        self.faq_button = discord.ui.Button(
            label="FAQ", style=discord.ButtonStyle.secondary, custom_id="community:faq"
        )
        self.rules_button.callback = self._rules
        self.faq_button.callback = self._faq
        rules_row = discord.ui.ActionRow(self.rules_button, self.faq_button)

        self.support_select = discord.ui.Select(
            custom_id="community:support",
            placeholder=content.SUPPORT_PLACEHOLDER,
            options=[
                discord.SelectOption(label=label, value=str(index), description=description)
                for index, (label, description, _) in enumerate(content.SUPPORT_CONTACTS)
            ],
        )
        self.support_select.callback = self._support
        for item in (
            _banner(welcome_banner, "Welcome to JustGames Digital"),
            discord.ui.Container(*welcome_children),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            _banner(rules_banner, "Rules"),
            discord.ui.Container(
                discord.ui.TextDisplay(content.RULES_PANEL_TEXT),
                discord.ui.Separator(),
                rules_row,
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            _banner(support_banner, "Support"),
            discord.ui.Container(
                discord.ui.TextDisplay(content.SUPPORT_PANEL_TEXT),
                discord.ui.Separator(),
                discord.ui.ActionRow(self.support_select),
            ),
        ):
            if item is not None:
                self.add_item(item)

    async def _rules(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            view=build_rules_view(), ephemeral=True, allowed_mentions=NO_MENTIONS
        )

    async def _faq(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            view=build_faq_view(), ephemeral=True, allowed_mentions=NO_MENTIONS
        )


    async def _support(self, interaction: discord.Interaction) -> None:
        try:
            label, _, email = content.SUPPORT_CONTACTS[int(self.support_select.values[0])]
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "That option is no longer available.", ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Tickets can only be opened from a server text channel.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            view=ConfirmTicketView(channel, label, email),
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )


def _is_support_staff(member: discord.abc.User) -> bool:
    role_id = _support_role_id()
    if not isinstance(member, discord.Member):
        return False
    if role_id and any(role.id == role_id for role in member.roles):
        return True
    return member.guild_permissions.manage_threads


class ConfirmTicketView(discord.ui.LayoutView):
    def __init__(self, channel: discord.TextChannel, label: str, email: str) -> None:
        super().__init__(timeout=300)
        self.channel = channel
        self.label = label
        self.email = email
        self.continue_button = discord.ui.Button(
            label="Continue", style=discord.ButtonStyle.success
        )
        self.continue_button.callback = self._continue
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {label}\n"
                "You can also reach us by email at:\n"
                f"**{email}**\n\n"
                "Prefer to talk to us here? Click **Continue** to open a private "
                "ticket and our team will join you there."
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.continue_button),
        ))

    async def _continue(self, interaction: discord.Interaction) -> None:
        self.continue_button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
        user = interaction.user
        prefix = ticket_prefix(self.label)
        try:
            number = await database.get_next_ticket_number(prefix)
            thread = await self.channel.create_thread(
                name=f"{prefix}-{number:04d}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=10080,
                reason=f"Support ticket opened by {user}",
            )
            role_id = _support_role_id()
            await database.add_ticket(thread.id, number, self.label, user.id)
            await thread.send(
                view=build_ticket_view(user, self.label, number, role_id),
                allowed_mentions=discord.AllowedMentions(
                    users=[user],
                    roles=[discord.Object(id=role_id)] if role_id else False,
                ),
            )
        except discord.HTTPException:
            logger.exception("Failed to create a support ticket")
            await interaction.followup.send(
                f"I couldn't open a ticket. Please email **{self.email}** instead.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"Your ticket is ready: {thread.mention}", ephemeral=True
        )
        await log_ticket_event(
            interaction.client,
            f"🟢 Ticket created • {prefix}-{number:04d}",
            [f"**Type:** {self.label}", f"**User:** {user.mention}", f"**Thread:** {thread.mention}"],
            discord.Colour.green(),
        )


def ticket_prefix(label: str) -> str:
    return label.strip().replace(" ", "-")


def build_ticket_view(
    user: discord.abc.User, label: str, number: int, role_id: int | None
) -> discord.ui.LayoutView:
    mentions = f"{user.mention} {f'<@&{role_id}>' if role_id else ''}".strip()
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(f"## 🎫 {label} • #{number:04d}"),
        discord.ui.TextDisplay(mentions),
        discord.ui.Separator(),
        discord.ui.TextDisplay(
            f"Thanks for reaching out, {user.mention}!\n"
            "Please describe how we can help in as much detail as you can. "
            "Our support team has been notified and will be with you shortly."
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay("-# A support team member will close this ticket once it's resolved."),
    ))
    return view


class CloseConfirmView(discord.ui.LayoutView):
    def __init__(self, thread: discord.Thread, closer: discord.abc.User) -> None:
        super().__init__(timeout=60)
        self.thread = thread
        self.closer = closer
        self.confirm_button = discord.ui.Button(
            label="Close ticket", style=discord.ButtonStyle.danger
        )
        self.cancel_button = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary
        )
        self.confirm_button.callback = self._confirm
        self.cancel_button.callback = self._cancel
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                "## Close this ticket?\n"
                "The ticket will be locked now and **permanently deleted in "
                f"{TICKET_DELETE_AFTER_HOURS} hours**."
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(self.confirm_button, self.cancel_button),
        ))

    def _disable(self) -> None:
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True
        self.stop()

    async def _cancel(self, interaction: discord.Interaction) -> None:
        self._disable()
        await interaction.response.edit_message(view=self)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        self._disable()
        await interaction.response.edit_message(view=self)
        thread = self.thread
        await database.mark_ticket_closed(thread.id)
        await thread.send(view=_closed_view(self.closer), allowed_mentions=NO_MENTIONS)
        await thread.edit(locked=True, archived=True, reason=f"Closed by {self.closer}")
        await log_ticket_event(
            interaction.client,
            f"🔒 Ticket closed • {thread.name}",
            [f"**Closed by:** {self.closer.mention}", f"**Thread:** {thread.mention}"],
            discord.Colour.orange(),
        )


def _closed_view(closer: discord.abc.User) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(
            f"## 🔒 Ticket closed\nClosed by {closer.mention}.\n"
            f"-# This ticket will be deleted in {TICKET_DELETE_AFTER_HOURS} hours."
        ),
    ))
    return view


class Community(commands.GroupCog, name="community"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Keeps the panel buttons working on already-posted messages after restarts.
        self.bot.add_view(CommunityView())
        self.delete_closed_tickets.start()

    async def cog_unload(self) -> None:
        self.delete_closed_tickets.cancel()

    @tasks.loop(minutes=10)
    async def delete_closed_tickets(self) -> None:
        for thread_id in await database.get_expired_closed_tickets(TICKET_DELETE_AFTER_HOURS):
            try:
                thread = self.bot.get_channel(thread_id) or await self.bot.fetch_channel(thread_id)
                await thread.delete(reason="Closed ticket expired")
            except discord.NotFound:
                await database.remove_ticket(thread_id)
            except discord.HTTPException:
                logger.exception("Failed to delete closed ticket %s", thread_id)

    @delete_closed_tickets.before_loop
    async def _before_delete_closed_tickets(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="close", description="Close this support ticket (support team only)")
    @app_commands.guild_only()
    async def close(self, interaction: discord.Interaction) -> None:
        thread = interaction.channel
        ticket = await database.get_ticket(thread.id) if isinstance(thread, discord.Thread) else None
        if ticket is None:
            await interaction.response.send_message(
                "This command can only be used inside a support ticket.", ephemeral=True
            )
            return
        if not _is_support_staff(interaction.user):
            await interaction.response.send_message(
                "Only the support team can close tickets.", ephemeral=True
            )
            return
        if ticket["closed_at"]:
            await interaction.response.send_message(
                "This ticket is already closed.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            view=CloseConfirmView(thread, interaction.user),
            ephemeral=True,
            allowed_mentions=NO_MENTIONS,
        )

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        ticket = await database.get_ticket(payload.thread_id)
        if ticket is None:
            return
        await database.remove_ticket(payload.thread_id)
        name = payload.thread.name if payload.thread else f"{ticket_prefix(ticket['label'])}-{ticket['number']:04d}"
        await log_ticket_event(
            self.bot,
            f"🗑️ Ticket deleted • {name}",
            [f"**Type:** {ticket['label']}", f"**Opened by:** <@{ticket['user_id']}>"],
            discord.Colour.red(),
        )

    @app_commands.command(
        name="welcome",
        description="Post the public JustGames Digital welcome and rules panel here",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await interaction.response.send_message(
                "I can't post in this channel.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        files: list[discord.File] = []
        names: dict[str, str | None] = {
            "welcome_banner": None,
            "rules_banner": None,
            "support_banner": None,
        }
        for stem in names:
            path = find_banner(stem)
            if path is not None:
                files.append(discord.File(path, filename=path.name))
                names[stem] = path.name

        try:
            await channel.send(
                view=CommunityView(**names),
                files=files,
                allowed_mentions=NO_MENTIONS,
            )
        except discord.HTTPException:
            logger.exception("Failed to post the community welcome")
            await interaction.followup.send(
                "I couldn't post the welcome here. Check that I can send messages and "
                "attach files in this channel.",
                ephemeral=True,
            )
            return

        await interaction.followup.send("Posted the community welcome.", ephemeral=True)

    @welcome.error
    async def welcome_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the Manage Server permission to use this command.", ephemeral=True
            )
        else:
            raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Community(bot))

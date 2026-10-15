import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

import community_content as content

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
                discord.ui.TextDisplay(
                    "\n".join(f"**{label}** — {email}" for label, email in content.SUPPORT_CONTACTS)
                ),
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


class Community(commands.GroupCog, name="community"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Keeps the Rules/FAQ buttons working on already-posted messages after restarts.
        self.bot.add_view(CommunityView())

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

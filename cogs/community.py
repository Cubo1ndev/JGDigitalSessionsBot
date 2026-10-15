import logging
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

WELCOME_COPY = (
    "We're glad you're here! This is the central hub for our community — find our "
    "links, updates, support, and everything else you need, all in one place.\n\n"
    "Grab a role, explore the channels, and don't be a stranger 👋"
)
RULES_COPY = (
    "Get to know the server rules and other important info you'll need to navigate "
    "the community — channel guides, roles, FAQs, and more."
)


def validate_link(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlsplit(url)
    if (
        len(url) > 512
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
    ):
        raise ValueError("Links must be valid HTTP or HTTPS URLs.")
    return url


def _image_extension(attachment: discord.Attachment) -> str | None:
    if attachment.content_type is None:
        return None
    return IMAGE_EXTENSIONS.get(attachment.content_type.lower())


def _link_row(links: list[tuple[str, str | None]]) -> discord.ui.ActionRow | None:
    buttons = [
        discord.ui.Button(label=label, style=discord.ButtonStyle.link, url=url)
        for label, url in links
        if url is not None
    ]
    if not buttons:
        return None
    row = discord.ui.ActionRow()
    for button in buttons:
        row.add_item(button)
    return row


def build_community_view(
    welcome_banner: str | None,
    rules_banner: str | None,
    website_url: str | None,
    roblox_group_url: str | None,
    youtube_url: str | None,
    x_url: str | None,
    rules_url: str | None,
    faq_url: str | None,
    suggestions_url: str | None,
) -> discord.ui.LayoutView:
    welcome_items: list[discord.ui.Item] = []
    if welcome_banner:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=welcome_banner, description="Welcome to JustGames Digital")
        welcome_items.append(gallery)
    welcome_items.append(discord.ui.TextDisplay(f"## Welcome to JustGames Digital\n{WELCOME_COPY}"))
    welcome_row = _link_row([
        ("Website", website_url),
        ("ROBLOX Group", roblox_group_url),
        ("YouTube", youtube_url),
        ("X", x_url),
    ])
    if welcome_row:
        welcome_items.extend([
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            welcome_row,
        ])

    rules_items: list[discord.ui.Item] = []
    if rules_banner:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=rules_banner, description="Community rules")
        rules_items.append(gallery)
    rules_items.append(discord.ui.TextDisplay(RULES_COPY))
    rules_row = _link_row([
        ("Rules", rules_url),
        ("FAQ", faq_url),
        ("Suggestions", suggestions_url),
    ])
    if rules_row:
        rules_items.append(rules_row)

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*welcome_items))
    view.add_item(discord.ui.Container(*rules_items))
    return view


class Community(commands.GroupCog, name="community"):
    @app_commands.command(
        name="welcome",
        description="Post the JustGames Digital welcome and community links",
    )
    @app_commands.describe(
        welcome_banner="Optional image for the welcome panel",
        rules_banner="Optional image for the rules panel",
        website_url="Website link",
        roblox_group_url="ROBLOX group link",
        youtube_url="YouTube channel link",
        x_url="X profile link",
        rules_url="Rules channel or page link",
        faq_url="FAQ channel or page link",
        suggestions_url="Suggestions channel or page link",
    )
    async def welcome(
        self,
        interaction: discord.Interaction,
        welcome_banner: discord.Attachment | None = None,
        rules_banner: discord.Attachment | None = None,
        website_url: str | None = None,
        roblox_group_url: str | None = None,
        youtube_url: str | None = None,
        x_url: str | None = None,
        rules_url: str | None = None,
        faq_url: str | None = None,
        suggestions_url: str | None = None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need the Manage Server permission to post the community welcome.",
                ephemeral=True,
            )
            return

        try:
            links = [
                validate_link(url)
                for url in (
                    website_url,
                    roblox_group_url,
                    youtube_url,
                    x_url,
                    rules_url,
                    faq_url,
                    suggestions_url,
                )
            ]
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        banner_uploads: list[tuple[int, discord.Attachment, str]] = []
        for index, attachment in enumerate((welcome_banner, rules_banner)):
            if attachment is None:
                continue
            extension = _image_extension(attachment)
            if extension is None:
                await interaction.response.send_message(
                    f"`{attachment.filename}` must be a PNG, JPEG, WebP, or GIF image.",
                    ephemeral=True,
                )
                return
            prefix = "welcome_banner" if index == 0 else "rules_banner"
            banner_uploads.append((index, attachment, f"{prefix}{extension}"))

        if not banner_uploads and not any(links):
            await interaction.response.send_message(
                "Add at least one link or banner image before posting the welcome.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        files: list[discord.File] = []
        banner_urls: list[str | None] = [None, None]
        try:
            for index, attachment, filename in banner_uploads:
                files.append(await attachment.to_file(filename=filename))
                banner_urls[index] = f"attachment://{filename}"

            view = build_community_view(*banner_urls, *links)
            await interaction.followup.send(
                view=view,
                files=files,
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=False,
            )
        except discord.HTTPException:
            logger.exception("Failed to post the community welcome")
            await interaction.followup.send(
                "Discord couldn't post the community welcome. Please check the "
                "images and try again.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "Posted the JustGames Digital community welcome.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Community())

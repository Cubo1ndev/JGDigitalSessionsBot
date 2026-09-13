import logging

import discord
from discord import app_commands
from discord.ext import commands

import database
from suggestion_logic import net_score, find_similar_suggestion

BRAND_GOLD = discord.Color.from_rgb(236, 183, 35)
BLURPLE = discord.Color.blurple()
GREEN = discord.Color.green()
FOOTER_TEXT = "Provided with ❤️by JustGames Digital Team."
DUPLICATE_THRESHOLD = 0.6
BOARD_PAGE_SIZE = 10
logger = logging.getLogger(__name__)


def set_brand_footer(embed: discord.Embed, context: str | None = None) -> discord.Embed:
    footer_text = FOOTER_TEXT if context is None else f"{context} • {FOOTER_TEXT}"
    embed.set_footer(text=footer_text)
    return embed


def thread_jump_url(guild_id: int, thread_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{thread_id}"


def build_suggestion_embed(
    idea: str, author: discord.Member | discord.User, upvotes: int, downvotes: int
) -> discord.Embed:
    embed = discord.Embed(title="💡 New Suggestion", description=idea, color=BRAND_GOLD)
    embed.add_field(name="Suggested by", value=author.mention, inline=True)
    embed.add_field(name="Votes", value=f"👍 {upvotes}  👎 {downvotes}", inline=True)
    return set_brand_footer(embed)


class SuggestionVoteView(discord.ui.View):
    def __init__(self, thread_id: int, upvotes: int = 0, downvotes: int = 0) -> None:
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.upvote_button.custom_id = f"suggestion_upvote:{thread_id}"
        self.downvote_button.custom_id = f"suggestion_downvote:{thread_id}"
        self.upvote_button.label = f"👍 Upvote ({upvotes})"
        self.downvote_button.label = f"👎 Downvote ({downvotes})"

    async def _vote(self, interaction: discord.Interaction, value: int) -> None:
        current = await database.get_suggestion_vote(self.thread_id, interaction.user.id)
        if current == value:
            await database.remove_suggestion_vote(self.thread_id, interaction.user.id)
        else:
            await database.set_suggestion_vote(self.thread_id, interaction.user.id, value)
        upvotes, downvotes = await database.get_suggestion_vote_counts(self.thread_id)

        post = await database.get_suggestion_post(self.thread_id)
        author = interaction.client.get_user(int(post["author_id"])) or await interaction.client.fetch_user(
            int(post["author_id"])
        )
        embed = build_suggestion_embed(post["suggestion_text"], author, upvotes, downvotes)
        new_view = SuggestionVoteView(self.thread_id, upvotes, downvotes)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="👍 Upvote (0)", style=discord.ButtonStyle.green)
    async def upvote_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._vote(interaction, 1)

    @discord.ui.button(label="👎 Downvote (0)", style=discord.ButtonStyle.red)
    async def downvote_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._vote(interaction, -1)


async def tag_and_disable_vote_message(client: discord.Client, post: dict, tag: str) -> None:
    """Best-effort: prefix the vote-embed title with `tag`, disable its vote buttons. Never raises."""
    channel_id = post.get("channel_id")
    if channel_id is None:
        config = await database.get_suggestion_config(int(post["guild_id"]))
        channel_id = config["suggestions_channel_id"] if config else None
    if channel_id is None:
        logger.warning("No channel_id available; cannot tag vote message for thread %s", post["thread_id"])
        return
    if post.get("vote_message_id") is None:
        logger.warning("No vote_message_id on thread %s; nothing to tag", post["thread_id"])
        return

    try:
        channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
    except (discord.NotFound, discord.Forbidden):
        logger.warning(
            "Suggestions channel %s unreachable; cannot tag vote message for thread %s",
            channel_id, post["thread_id"],
        )
        return

    try:
        message = await channel.fetch_message(int(post["vote_message_id"]))
    except discord.NotFound:
        logger.info(
            "Vote message %s already deleted; nothing to tag for thread %s",
            post["vote_message_id"], post["thread_id"],
        )
        return
    except discord.Forbidden:
        logger.warning(
            "Forbidden fetching vote message %s for thread %s", post["vote_message_id"], post["thread_id"]
        )
        return

    embed = message.embeds[0] if message.embeds else discord.Embed()
    embed.title = f"{tag} {embed.title}" if embed.title else tag

    upvotes, downvotes = await database.get_suggestion_vote_counts(int(post["thread_id"]))
    view = SuggestionVoteView(int(post["thread_id"]), upvotes, downvotes)
    for child in view.children:
        child.disabled = True

    try:
        await message.edit(embed=embed, view=view)
    except discord.HTTPException:
        logger.warning("Failed to edit vote message %s for thread %s", post["vote_message_id"], post["thread_id"])


def build_duplicate_report_embed(
    guild_id: int, thread_a_id: int, thread_b_id: int, note: str
) -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ Possible Duplicate Suggestions",
        description=(
            f"**Post A:** {thread_jump_url(guild_id, thread_a_id)}\n"
            f"**Post B:** {thread_jump_url(guild_id, thread_b_id)}\n\n"
            f"{note}\n\n"
            "Approving keeps the older post and closes the newer one, notifying its author."
        ),
        color=BRAND_GOLD,
    )
    return set_brand_footer(embed)


class DuplicateReportView(discord.ui.View):
    def __init__(self, report_id: int) -> None:
        super().__init__(timeout=None)
        self.report_id = report_id
        self.approve_button.custom_id = f"dup_approve:{report_id}"
        self.reject_button.custom_id = f"dup_reject:{report_id}"

    @discord.ui.button(label="✅ Approve merge", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only administrators can approve a duplicate merge.", ephemeral=True
            )
            return

        report = await database.get_duplicate_report(self.report_id)
        if report is None or report["status"] != "pending":
            await interaction.response.send_message("This report was already resolved.", ephemeral=True)
            return

        await interaction.response.defer()
        post_a = await database.get_suggestion_post(int(report["thread_a_id"]))
        post_b = await database.get_suggestion_post(int(report["thread_b_id"]))
        if post_a is None or post_b is None:
            await database.set_duplicate_report_status(self.report_id, "rejected")
            await interaction.followup.send("One of the posts no longer exists.", ephemeral=True)
            return

        survivor, loser = (post_a, post_b) if post_a["created_at"] <= post_b["created_at"] else (post_b, post_a)
        client = interaction.client
        try:
            loser_thread = client.get_channel(int(loser["thread_id"])) or await client.fetch_channel(int(loser["thread_id"]))
        except (discord.NotFound, discord.Forbidden):
            await database.set_duplicate_report_status(self.report_id, "rejected")
            await interaction.followup.send("The duplicate post no longer exists.", ephemeral=True)
            return

        survivor_url = thread_jump_url(int(report["guild_id"]), int(survivor["thread_id"]))

        notice_embed = discord.Embed(
            title="🔀 Marked as Duplicate",
            description=(
                "This suggestion was identified as a duplicate of an existing one and has been merged.\n\n"
                f"Head over to the original to keep discussing and voting: {survivor_url}"
            ),
            color=BRAND_GOLD,
        )
        set_brand_footer(notice_embed)
        try:
            await loser_thread.send(embed=notice_embed)
        except discord.HTTPException:
            logger.warning("Failed to post duplicate notice in thread %s", loser["thread_id"])

        await tag_and_disable_vote_message(client, loser, "[DUPLICATE]")

        await loser_thread.edit(locked=True, archived=True, reason="Merged as a duplicate suggestion")
        await database.set_suggestion_status(int(loser["thread_id"]), "merged")
        await database.set_duplicate_report_status(self.report_id, "approved")

        try:
            author = client.get_user(int(loser["author_id"])) or await client.fetch_user(int(loser["author_id"]))
            dm_embed = discord.Embed(
                title="Your suggestion was merged",
                description=(
                    "A staff member found that your suggestion matches an existing one, "
                    f"so it's been closed in favor of:\n{survivor_url}"
                ),
                color=BRAND_GOLD,
            )
            set_brand_footer(dm_embed)
            await author.send(embed=dm_embed)
        except discord.Forbidden:
            logger.warning("Cannot DM user %s about merged suggestion", loser["author_id"])

        for child in self.children:
            child.disabled = True
        result_embed = build_duplicate_report_embed(
            int(report["guild_id"]), int(report["thread_a_id"]), int(report["thread_b_id"]),
            f"✅ Approved by {interaction.user.mention} — kept {survivor_url}",
        )
        await interaction.message.edit(embed=result_embed, view=self)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.grey)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only administrators can reject a duplicate report.", ephemeral=True
            )
            return

        report = await database.get_duplicate_report(self.report_id)
        if report is None or report["status"] != "pending":
            await interaction.response.send_message("This report was already resolved.", ephemeral=True)
            return

        await database.set_duplicate_report_status(self.report_id, "rejected")
        for child in self.children:
            child.disabled = True
        result_embed = build_duplicate_report_embed(
            int(report["guild_id"]), int(report["thread_a_id"]), int(report["thread_b_id"]),
            f"❌ Rejected by {interaction.user.mention} — both posts remain open.",
        )
        await interaction.response.edit_message(embed=result_embed, view=self)


class ReportDuplicateModal(discord.ui.Modal, title="Report Duplicate Suggestion"):
    def __init__(self, thread_a_id: int) -> None:
        super().__init__()
        self.thread_a_id = thread_a_id

    other_post = discord.ui.TextInput(
        label="Link or ID of the other suggestion post",
        placeholder="https://discord.com/channels/.../... or the thread ID",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.other_post.value.strip()
        thread_b_id_str = raw.rstrip("/").split("/")[-1]
        try:
            thread_b_id = int(thread_b_id_str)
        except ValueError:
            await interaction.response.send_message("That doesn't look like a valid link or ID.", ephemeral=True)
            return

        if thread_b_id == self.thread_a_id:
            await interaction.response.send_message("That's the same post.", ephemeral=True)
            return

        post_b = await database.get_suggestion_post(thread_b_id)
        if post_b is None or post_b["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("That isn't a tracked suggestion post in this server.", ephemeral=True)
            return

        cog = interaction.client.get_cog("suggestions")
        await interaction.response.defer(ephemeral=True)
        await cog.create_duplicate_report(
            interaction.guild_id, self.thread_a_id, thread_b_id, "Reported manually by staff."
        )
        await interaction.followup.send("Duplicate report sent to the staff channel.", ephemeral=True)


@app_commands.context_menu(name="Report as Duplicate")
async def report_duplicate_context_menu(interaction: discord.Interaction, message: discord.Message) -> None:
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only administrators can report duplicates.", ephemeral=True)
        return
    if not isinstance(message.channel, discord.Thread):
        await interaction.response.send_message("That message isn't in a suggestion post.", ephemeral=True)
        return
    post = await database.get_suggestion_post(message.channel.id)
    if post is None:
        await interaction.response.send_message("That thread isn't a tracked suggestion post.", ephemeral=True)
        return

    await interaction.response.send_modal(ReportDuplicateModal(message.channel.id))


class BoardView(discord.ui.View):
    def __init__(self, guild: discord.Guild, rows: list[dict], page: int = 0) -> None:
        super().__init__(timeout=180)
        self.guild = guild
        self.rows = rows
        self.page = page
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = (self.page + 1) * BOARD_PAGE_SIZE >= len(self.rows)

    async def _render(self) -> discord.Embed:
        start = self.page * BOARD_PAGE_SIZE
        page_rows = self.rows[start:start + BOARD_PAGE_SIZE]
        lines = []
        for i, row in enumerate(page_rows, start=start + 1):
            thread_id = int(row["thread_id"])
            thread = self.guild.get_thread(thread_id)
            if thread is None:
                try:
                    thread = await self.guild.fetch_channel(thread_id)
                except (discord.NotFound, discord.Forbidden):
                    continue
            score = net_score(row["upvotes"], row["downvotes"])
            lines.append(f"**{i}.** [{thread.name}]({thread.jump_url}) — {score} pts (👍{row['upvotes']}/👎{row['downvotes']})")

        embed = discord.Embed(
            title="💡 Suggestion Board",
            description="\n".join(lines) if lines else "No open suggestions yet.",
            color=BLURPLE,
        )
        total_pages = max(1, (len(self.rows) + BOARD_PAGE_SIZE - 1) // BOARD_PAGE_SIZE)
        set_brand_footer(embed, f"Page {self.page + 1}/{total_pages}")
        return embed

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self._render(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self._render(), view=self)


class Suggestions(commands.GroupCog, name="suggestions"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setsuggestionschannel", description="Set the text channel where suggestions are posted")
    @app_commands.describe(channel="A text channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setsuggestionschannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await database.set_suggestions_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(
            f"Suggestions will now be posted in {channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="setstaffchannel", description="Set the channel where duplicate reports are sent")
    @app_commands.describe(channel="A text channel staff can see")
    @app_commands.checks.has_permissions(administrator=True)
    async def setstaffchannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await database.set_suggestion_staff_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(
            f"Duplicate reports will now be sent to {channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="board", description="Show the most voted suggestions")
    async def board(self, interaction: discord.Interaction) -> None:
        rows = await database.get_ranked_open_suggestions(interaction.guild_id)
        if not rows:
            await interaction.response.send_message("No open suggestions yet.", ephemeral=True)
            return
        view = BoardView(interaction.guild, rows)
        await interaction.response.send_message(embed=await view._render(), view=view)

    @app_commands.command(name="implemented", description="Mark this suggestion as implemented (run inside its post)")
    @app_commands.checks.has_permissions(administrator=True)
    async def implemented(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("Run this command inside a suggestion post.", ephemeral=True)
            return
        post = await database.get_suggestion_post(interaction.channel.id)
        if post is None:
            await interaction.response.send_message("This thread isn't a tracked suggestion post.", ephemeral=True)
            return
        if post["status"] != "open":
            await interaction.response.send_message("This suggestion is already closed.", ephemeral=True)
            return

        await database.set_suggestion_status(interaction.channel.id, "implemented")
        await tag_and_disable_vote_message(interaction.client, post, "[IMPLEMENTED]")
        embed = discord.Embed(
            title="✅ Suggestion Implemented",
            description="This suggestion has been implemented. Thanks for the idea!",
            color=GREEN,
        )
        set_brand_footer(embed)
        await interaction.response.send_message(embed=embed)
        await interaction.channel.edit(locked=True, archived=True, reason="Suggestion implemented")

    @setsuggestionschannel.error
    @setstaffchannel.error
    @implemented.error
    async def admin_only_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Only Discord server administrators can use this command.", ephemeral=True
            )

    async def create_duplicate_report(
        self, guild_id: int, thread_a_id: int, thread_b_id: int, note: str
    ) -> None:
        config = await database.get_suggestion_config(guild_id)
        if config is None or config["staff_channel_id"] is None:
            return
        staff_channel = self.bot.get_channel(config["staff_channel_id"])
        if staff_channel is None:
            return

        report_id = await database.create_duplicate_report(guild_id, thread_a_id, thread_b_id)
        embed = build_duplicate_report_embed(guild_id, thread_a_id, thread_b_id, note)
        message = await staff_channel.send(embed=embed, view=DuplicateReportView(report_id))
        await database.set_duplicate_report_message(report_id, message.id)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        post = await database.get_suggestion_post_by_vote_message(payload.message_id)
        if post is None or post["status"] != "open":
            return
        await database.set_suggestion_status(int(post["thread_id"]), "deleted")
        logger.info(
            "Vote message %s deleted; marked suggestion thread %s as deleted",
            payload.message_id, post["thread_id"],
        )


@app_commands.command(name="suggest", description="Submit a new suggestion")
@app_commands.describe(idea="Your suggestion")
async def suggest(interaction: discord.Interaction, idea: str) -> None:
    config = await database.get_suggestion_config(interaction.guild_id)
    if config is None or config["suggestions_channel_id"] is None:
        await interaction.response.send_message(
            "Ask an admin to run /suggestions setsuggestionschannel first.", ephemeral=True
        )
        return
    channel = interaction.client.get_channel(config["suggestions_channel_id"])
    if channel is None:
        await interaction.response.send_message(
            "The configured suggestions channel no longer exists.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    message = await channel.send(embed=build_suggestion_embed(idea, interaction.user, 0, 0))
    try:
        thread = await message.create_thread(name=idea[:100])
    except discord.HTTPException:
        try:
            await message.delete()
        except discord.HTTPException:
            logger.warning("Failed to clean up suggestion message %s after thread creation failed", message.id)
        await interaction.followup.send(
            "Couldn't create the discussion thread — please try again.", ephemeral=True
        )
        return

    await database.create_suggestion_post(
        thread.id, interaction.guild_id, interaction.user.id, idea,
        channel_id=channel.id, vote_message_id=message.id,
    )
    await message.edit(view=SuggestionVoteView(thread.id, 0, 0))

    candidates = [
        (post["thread_id"], post["suggestion_text"])
        for post in await database.get_open_suggestion_posts(interaction.guild_id)
        if int(post["thread_id"]) != thread.id
    ]
    match = find_similar_suggestion(idea, candidates, DUPLICATE_THRESHOLD)
    if match is not None:
        match_thread_id, ratio = match
        cog = interaction.client.get_cog("suggestions")
        await cog.create_duplicate_report(
            interaction.guild_id, thread.id, int(match_thread_id),
            f"Auto-detected by text similarity ({ratio:.0%} match).",
        )

    await interaction.followup.send(f"Suggestion posted: {message.jump_url}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Suggestions(bot))
    bot.tree.add_command(report_duplicate_context_menu)
    bot.tree.add_command(suggest)

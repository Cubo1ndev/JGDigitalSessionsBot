import discord
from discord import app_commands
from discord.ext import commands

import database
from checks import require_bot_admin

PAGE_SIZE = 10
BLUE = discord.Color.blurple()
RED = discord.Color.red()

ACTION_LABELS = {
    "give": "➕ Give",
    "confirmpay": "💸 Paid",
    "adjust": "🔧 Adjust",
}


def _build_page(
    entries: list[dict],
    target_user: discord.Member,
    page: int,
    total_pages: int,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"History — {target_user.display_name}",
        color=BLUE,
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)

    for entry in entries:
        action_label = ACTION_LABELS.get(entry["action"], entry["action"])
        value_lines = [
            f"Amount: **{entry['amount']:,}**",
            f"Actor: <@{entry['actor_id']}> → Target: <@{entry['target_id']}>",
        ]
        if entry["reason"]:
            value_lines.append(f"Reason: *{entry['reason']}*")
        embed.add_field(
            name=f"{action_label} — {entry['timestamp']}",
            value="\n".join(value_lines),
            inline=False,
        )

    embed.set_footer(text=f"Page {page}/{total_pages} · {PAGE_SIZE} per page")
    return embed


class HistoryView(discord.ui.View):
    def __init__(
        self,
        entries: list[dict],
        target_user: discord.Member,
        page: int = 1,
    ) -> None:
        super().__init__(timeout=120)
        self.entries = entries
        self.target_user = target_user
        self.page = page
        self.total_pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    def current_embed(self) -> discord.Embed:
        start = (self.page - 1) * PAGE_SIZE
        page_entries = self.entries[start : start + PAGE_SIZE]
        return _build_page(page_entries, self.target_user, self.page, self.total_pages)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)


class History(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="history", description="View the full Robux action history for a user")
    @app_commands.describe(user="The user whose history to view")
    @require_bot_admin()
    async def history(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        entries = await database.get_history(user.id)
        if not entries:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"No history found for {user.mention}.",
                    color=discord.Color.greyple(),
                )
            )
            return

        view = HistoryView(entries, user)
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    @history.error
    async def history_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ You don't have permission to use this command.",
                    color=RED,
                )
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(History(bot))

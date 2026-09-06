import discord
from discord import app_commands
from discord.ext import commands

import database
from checks import require_bot_admin

PAGE_SIZE = 10
GOLD = discord.Color.gold()
RED = discord.Color.red()

MEDALS = ["🥇", "🥈", "🥉"]


def _build_page(
    rows: list[tuple[str, int]],
    title: str,
    field_label: str,
    page: int,
    total_pages: int,
    offset: int,
) -> discord.Embed:
    embed = discord.Embed(title=title, color=GOLD)
    lines = []
    for i, (user_id, amount) in enumerate(rows):
        rank = offset + i + 1
        medal = MEDALS[rank - 1] if rank <= 3 else f"`#{rank}`"
        lines.append(f"{medal} <@{user_id}> — **{amount:,}** Robux")
    embed.description = "\n".join(lines) if lines else "*No entries yet.*"
    embed.set_footer(text=f"Page {page}/{total_pages} · {PAGE_SIZE} per page")
    return embed


class TopView(discord.ui.View):
    def __init__(self, field: str, title: str, field_label: str, total: int) -> None:
        super().__init__(timeout=120)
        self.field = field
        self.title = title
        self.field_label = field_label
        self.total = total
        self.page = 1
        self.total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    async def build_embed(self) -> discord.Embed:
        offset = (self.page - 1) * PAGE_SIZE
        rows = await database.get_top(self.field, limit=PAGE_SIZE, offset=offset)
        return _build_page(rows, self.title, self.field_label, self.page, self.total_pages, offset)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pendingtop", description="Leaderboard of users with the most pending Robux")
    @require_bot_admin()
    async def pendingtop(self, interaction: discord.Interaction) -> None:
        total = await database.count_top("pending")
        if total == 0:
            await interaction.response.send_message(
                embed=discord.Embed(description="No pending Robux on record.", color=GOLD)
            )
            return
        view = TopView("pending", "🏆 Pending Robux — Top", "Pending", total)
        await interaction.response.send_message(embed=await view.build_embed(), view=view)

    @app_commands.command(name="paidtop", description="Leaderboard of users with the most paid Robux")
    @require_bot_admin()
    async def paidtop(self, interaction: discord.Interaction) -> None:
        total = await database.count_top("paid")
        if total == 0:
            await interaction.response.send_message(
                embed=discord.Embed(description="No paid Robux on record.", color=GOLD)
            )
            return
        view = TopView("paid", "🏆 Paid Robux — Top", "Paid", total)
        await interaction.response.send_message(embed=await view.build_embed(), view=view)

    @pendingtop.error
    @paidtop.error
    async def top_error(
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
    await bot.add_cog(Leaderboard(bot))

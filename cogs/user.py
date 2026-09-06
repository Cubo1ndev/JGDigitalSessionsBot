import discord
from discord import app_commands
from discord.ext import commands

import database

GREEN = discord.Color.green()


class User(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="wallet", description="View your pending and paid Robux")
    async def wallet(self, interaction: discord.Interaction) -> None:
        pending, paid = await database.get_wallet(interaction.user.id)
        embed = discord.Embed(
            title=f"Your Wallet — {interaction.user.display_name}",
            color=GREEN,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Pending Robux", value=f"{pending:,}", inline=True)
        embed.add_field(name="Paid Robux", value=f"{paid:,}", inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(User(bot))

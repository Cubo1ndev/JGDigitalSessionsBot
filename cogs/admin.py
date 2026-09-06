import discord
from discord import app_commands
from discord.ext import commands

import database
from checks import require_bot_admin

GREEN = discord.Color.green()
RED = discord.Color.red()


def _ok(msg: str) -> discord.Embed:
    return discord.Embed(description=f"✅ {msg}", color=GREEN)


def _err(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=RED)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # /give
    @app_commands.command(name="give", description="Add pending Robux to a user")
    @app_commands.describe(
        user="The tester to give Robux to",
        amount="Amount of Robux (must be > 0)",
        reason="Optional reason",
    )
    @require_bot_admin()
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        reason: str | None = None,
    ) -> None:
        if amount <= 0:
            await interaction.response.send_message(embed=_err("Amount must be greater than 0."))
            return
        pending, _ = await database.add_pending(user.id, amount)
        await database.add_history(interaction.user.id, user.id, "give", amount, reason)
        msg = f"Added **{amount:,} pending Robux** to {user.mention}. New pending: **{pending:,}**."
        if reason:
            msg += f"\nReason: *{reason}*"
        await interaction.response.send_message(embed=_ok(msg))

    # /confirmpay
    @app_commands.command(name="confirmpay", description="Move all pending Robux to paid for a user")
    @app_commands.describe(user="The tester to mark as paid")
    @require_bot_admin()
    async def confirmpay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        moved = await database.confirm_pay(user.id)
        if moved <= 0:
            await interaction.response.send_message(
                embed=_err(f"{user.mention} has no pending Robux to pay.")
            )
            return
        await database.add_history(interaction.user.id, user.id, "confirmpay", moved)
        await interaction.response.send_message(
            embed=_ok(f"Marked **{moved:,} Robux** as paid for {user.mention}.")
        )

    # /adjust
    @app_commands.command(name="adjust", description="Adjust a user's pending Robux (use negative to subtract)")
    @app_commands.describe(
        user="The tester to adjust",
        amount="Amount to add or subtract (e.g. -100 to remove 100)",
        reason="Optional reason",
    )
    @require_bot_admin()
    async def adjust(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        reason: str | None = None,
    ) -> None:
        if amount == 0:
            await interaction.response.send_message(embed=_err("Amount cannot be 0."))
            return
        pending, _ = await database.add_pending(user.id, amount)
        await database.add_history(interaction.user.id, user.id, "adjust", amount, reason)
        direction = "Added" if amount > 0 else "Removed"
        msg = (
            f"{direction} **{abs(amount):,} Robux** for {user.mention}. "
            f"New pending: **{pending:,}**."
        )
        if reason:
            msg += f"\nReason: *{reason}*"
        await interaction.response.send_message(embed=_ok(msg))

    # /get
    @app_commands.command(name="get", description="View a user's pending and paid Robux totals")
    @app_commands.describe(user="The tester to look up")
    @require_bot_admin()
    async def get(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        pending, paid = await database.get_wallet(user.id)
        embed = discord.Embed(title=f"Wallet — {user.display_name}", color=GREEN)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Pending Robux", value=f"{pending:,}", inline=True)
        embed.add_field(name="Paid Robux", value=f"{paid:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    # /grant
    @app_commands.command(name="grant", description="Grant bot-admin permissions to a user")
    @app_commands.describe(user="User to grant admin access to")
    @app_commands.checks.has_permissions(administrator=True)
    async def grant(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        added = await database.add_bot_admin(user.id, interaction.user.id)
        if not added:
            await interaction.response.send_message(
                embed=_err(f"{user.mention} is already a bot admin.")
            )
            return
        await interaction.response.send_message(
            embed=_ok(f"{user.mention} has been granted bot-admin access.")
        )

    # /revoke
    @app_commands.command(name="revoke", description="Revoke bot-admin permissions from a user")
    @app_commands.describe(user="User to revoke admin access from")
    @app_commands.checks.has_permissions(administrator=True)
    async def revoke(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        removed = await database.remove_bot_admin(user.id)
        if not removed:
            await interaction.response.send_message(
                embed=_err(f"{user.mention} is not a bot admin.")
            )
            return
        await interaction.response.send_message(
            embed=_ok(f"Removed bot-admin access from {user.mention}.")
        )

    # Error handlers
    @give.error
    @confirmpay.error
    @adjust.error
    @get.error
    async def admin_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=_err("You don't have permission to use this command.")
            )

    @grant.error
    @revoke.error
    async def discord_admin_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=_err("Only Discord server administrators can use this command.")
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

import discord
from discord import app_commands
import database


async def _is_bot_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return await database.user_is_bot_admin(interaction.user.id)


def require_bot_admin():
    return app_commands.check(_is_bot_admin)

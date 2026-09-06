import discord
from discord import app_commands
import database
from session_logic import has_host_permission


async def _is_host(interaction: discord.Interaction) -> bool:
    host_role_id = await database.get_host_role(interaction.guild_id)
    member_role_ids = {role.id for role in interaction.user.roles}
    return has_host_permission(
        is_administrator=interaction.user.guild_permissions.administrator,
        member_role_ids=member_role_ids,
        host_role_id=host_role_id,
    )


def require_host_role():
    return app_commands.check(_is_host)

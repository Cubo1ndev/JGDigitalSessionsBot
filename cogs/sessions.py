import discord
from discord import app_commands
from discord.app_commands import Range
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

import database
from checks import require_host_role
from session_logic import (
    build_session_datetime,
    validate_max_players,
    has_room,
    can_manage_session,
    has_host_permission,
    is_image_attachment,
)

GREEN = discord.Color.green()
BLURPLE = discord.Color.blurple()
RED = discord.Color.red()
GREY = discord.Color.greyple()
FOOTER_TEXT = "Provided with ❤️by JustGames Digital Team."

STATUS_COLORS = {"pending": GREEN, "fired": BLURPLE, "ended": GREY, "cancelled": RED}
STATUS_LABELS = {
    "fired": "Started — check your DMs!",
    "ended": "Ended — thanks for joining!",
    "cancelled": "Cancelled",
}


def set_brand_footer(embed: discord.Embed, context: str | None = None) -> discord.Embed:
    footer_text = FOOTER_TEXT if context is None else f"{context} • {FOOTER_TEXT}"
    embed.set_footer(text=footer_text)
    return embed


def build_session_embed(session: dict, player_ids: list[int] | None = None) -> discord.Embed:
    if player_ids is None:
        player_ids = []
    start_dt = datetime.fromisoformat(session["start_time_utc"])
    status = session["status"]
    player_count = len(player_ids)
    max_players = session["max_players"]

    embed = discord.Embed(
        title=f"🚌 {session['company_name']}",
        color=STATUS_COLORS[status],
    )

    if session.get("description"):
        embed.description = session["description"]

    embed.add_field(name="👑 Host", value=f"<@{session['host_id']}>", inline=True)

    if status == "pending":
        timestamp = int(start_dt.timestamp())
        embed.add_field(name="⏰ Starts", value=f"<t:{timestamp}:R> (<t:{timestamp}:F>)", inline=False)
    else:
        embed.add_field(name="📌 Status", value=STATUS_LABELS[status], inline=False)

    if player_ids:
        mentions = [f"<@{uid}>" for uid in player_ids]
        player_text = "\n".join(mentions)
        if len(player_text) > 1000:
            truncated = []
            current_len = 0
            for mention in mentions:
                if current_len + len(mention) + 15 > 950:
                    remaining = len(mentions) - len(truncated)
                    truncated.append(f"...and {remaining} more")
                    break
                truncated.append(mention)
                current_len += len(mention) + 1
            player_text = "\n".join(truncated)
    else:
        player_text = "*No players joined yet*"

    embed.add_field(name=f"👥 Players ({player_count}/{max_players})", value=player_text, inline=False)

    if session.get("logo_url"):
        embed.set_thumbnail(url=session["logo_url"])
    return set_brand_footer(embed, f"Session #{session['id']}")


def build_start_dm_embed(session: dict) -> discord.Embed:
    server_text = session.get("server_name") or "Not specified"
    description = (
        "The session is about to begin!\n\n"
        f"• **Company:** {session['company_name']}\n"
        f"• **Server:** {server_text}\n\n"
        "**How to join:**\n"
        "1. Open the game.\n"
        "2. In the main menu, click **Servers**.\n"
    )
    if session.get("server_name"):
        description += (
            f"3. Search for server: **\"{session['server_name']}\"**\n"
            f"4. Look for company: **\"{session['company_name']}\"**\n\n"
        )
    else:
        description += f"3. Search for company: **\"{session['company_name']}\"**\n\n"
    description += "Have fun!"

    embed = discord.Embed(
        title="SESSION STARTING",
        description=description,
        color=GREEN,
    )
    if session.get("logo_url"):
        embed.set_thumbnail(url=session["logo_url"])
    return set_brand_footer(embed, f"Session #{session['id']}")


def build_reminder_dm_embed(session: dict) -> discord.Embed:
    start_dt = datetime.fromisoformat(session["start_time_utc"])
    timestamp = int(start_dt.timestamp())
    embed = discord.Embed(
        title="SESSION STARTING SOON",
        description=(
            f"Your **{session['company_name']}** session starts <t:{timestamp}:R>.\n\n"
            "You will receive another message shortly with instructions on how to join."
        ),
        color=discord.Color.gold(),
    )
    if session.get("logo_url"):
        embed.set_thumbnail(url=session["logo_url"])
    return set_brand_footer(embed, f"Session #{session['id']}")


class EditServerModal(discord.ui.Modal, title="Change Server Name"):
    def __init__(self, session_id: int, bot: commands.Bot) -> None:
        super().__init__()
        self.session_id = session_id
        self.bot = bot

    server_name = discord.ui.TextInput(
        label="Server Name / Location",
        placeholder="Enter server name (e.g. US East - Server 1)",
        required=True,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        session = await database.get_session(self.session_id)
        if session is None:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if not can_manage_session(
            interaction.user.guild_permissions.administrator,
            interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can edit this session.", ephemeral=True
            )
            return

        new_server = self.server_name.value.strip()
        await database.update_session_server_name(self.session_id, new_server)
        updated_session = await database.get_session(self.session_id)

        cog = self.bot.get_cog("session")
        if cog:
            status = updated_session["status"]
            view = SessionView(self.session_id) if status == "pending" else None
            await cog._update_message(updated_session, status, view)

        await interaction.response.send_message(
            f"✅ Server location updated to **\"{new_server}\"** for session #{self.session_id}.",
            ephemeral=True,
        )


class EditLimitModal(discord.ui.Modal, title="Change Player Limit"):
    def __init__(self, session_id: int, bot: commands.Bot) -> None:
        super().__init__()
        self.session_id = session_id
        self.bot = bot

    max_players_input = discord.ui.TextInput(
        label="Maximum Players",
        placeholder="Enter new player limit",
        required=True,
        max_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        session = await database.get_session(self.session_id)
        if session is None:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if not can_manage_session(
            interaction.user.guild_permissions.administrator,
            interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can edit this session.", ephemeral=True
            )
            return

        try:
            val = int(self.max_players_input.value.strip())
            current_count = await database.count_players(self.session_id)
            val = validate_max_players(val, current_count=current_count)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await database.update_session_max_players(self.session_id, val)
        updated_session = await database.get_session(self.session_id)

        cog = self.bot.get_cog("session")
        if cog:
            status = updated_session["status"]
            view = SessionView(self.session_id) if status == "pending" else None
            await cog._update_message(updated_session, status, view)

        await interaction.response.send_message(
            f"✅ Player limit updated to **{val}** for session #{self.session_id}.",
            ephemeral=True,
        )


class HostSettingsControlView(discord.ui.View):
    def __init__(self, session_id: int, bot: commands.Bot) -> None:
        super().__init__(timeout=180)
        self.session_id = session_id
        self.bot = bot

    @discord.ui.button(label="🌐 Change Server", style=discord.ButtonStyle.blurple)
    async def change_server_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        modal = EditServerModal(self.session_id, self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👥 Change Player Limit", style=discord.ButtonStyle.blurple)
    async def change_limit_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        modal = EditLimitModal(self.session_id, self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Cancel Session", style=discord.ButtonStyle.red)
    async def cancel_session_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        session = await database.get_session(self.session_id)
        if session is None or session["status"] != "pending":
            await interaction.response.send_message("That session is no longer pending.", ephemeral=True)
            return

        cog = self.bot.get_cog("session")
        if cog:
            await interaction.response.defer(ephemeral=True)
            await cog._cancel_session_internal(self.session_id)
            await interaction.followup.send(f"Session #{self.session_id} cancelled.", ephemeral=True)
        else:
            await interaction.response.send_message("Could not perform action.", ephemeral=True)


class SessionView(discord.ui.View):
    def __init__(self, session_id: int) -> None:
        super().__init__(timeout=None)
        self.session_id = session_id
        self.join_button.custom_id = f"session_join:{session_id}"
        self.leave_button.custom_id = f"session_leave:{session_id}"
        self.settings_button.custom_id = f"session_settings:{session_id}"

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        session = await database.get_session(self.session_id)
        if session is None or session["status"] != "pending":
            await interaction.response.send_message("This session is no longer open.", ephemeral=True)
            return
        count = await database.count_players(self.session_id)
        if not has_room(count, session["max_players"]):
            await interaction.response.send_message("This session is full.", ephemeral=True)
            return
        added = await database.add_player(self.session_id, interaction.user.id)
        if not added:
            await interaction.response.send_message("You already joined this session.", ephemeral=True)
            return
        player_ids = await database.get_players(self.session_id)
        embed = build_session_embed(session, player_ids)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        session = await database.get_session(self.session_id)
        if session is None or session["status"] != "pending":
            await interaction.response.send_message("This session is no longer open.", ephemeral=True)
            return
        removed = await database.remove_player(self.session_id, interaction.user.id)
        if not removed:
            await interaction.response.send_message("You hadn't joined this session.", ephemeral=True)
            return
        player_ids = await database.get_players(self.session_id)
        embed = build_session_embed(session, player_ids)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚙️ Host Settings", style=discord.ButtonStyle.grey)
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        session = await database.get_session(self.session_id)
        if session is None:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        is_admin = interaction.user.guild_permissions.administrator
        is_host = interaction.user.id == int(session["host_id"])
        if not can_manage_session(is_admin, is_host):
            await interaction.response.send_message(
                "Only the host or an administrator can access host settings for this session.",
                ephemeral=True,
            )
            return

        view = HostSettingsControlView(self.session_id, interaction.client)
        embed = discord.Embed(
            title=f"⚙️ Host Controls — Session #{self.session_id}",
            description=(
                f"**Company:** {session['company_name']}\n"
                f"**Server:** {session.get('server_name') or 'Not specified'}\n"
                f"**Player Limit:** {session['max_players']}\n\n"
                "Select an option below to update session settings or cancel the session."
            ),
            color=BLURPLE,
        )
        set_brand_footer(embed, f"Session #{self.session_id}")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class Session(commands.GroupCog, name="session"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_due_sessions.start()

    async def cog_unload(self) -> None:
        self.check_due_sessions.cancel()

    @app_commands.command(name="hostrole", description="Set the role allowed to host sessions")
    @app_commands.describe(role="The role that can use /session host")
    @app_commands.checks.has_permissions(administrator=True)
    async def hostrole(self, interaction: discord.Interaction, role: discord.Role) -> None:
        await database.set_host_role(interaction.guild_id, role.id)
        await interaction.response.send_message(
            f"{role.mention} can now host sessions.", ephemeral=True
        )

    @app_commands.command(name="host", description="Host a new session")
    @app_commands.describe(
        company_name="The company name (this is what players search for in-game)",
        max_players="Maximum number of players",
        year="Start year (UTC)",
        month="Start month, 1-12 (UTC)",
        day="Start day, 1-31 (UTC)",
        hour="Start hour, 0-23 (UTC)",
        minute="Start minute, 0-59 (UTC)",
        server_name="Optional server name or location where the session will take place",
        description="Optional description shown on the session card",
        logo="Optional logo image shown on the session card",
    )
    @require_host_role()
    async def host(
        self,
        interaction: discord.Interaction,
        company_name: str,
        max_players: Range[int, 1, None],
        year: int,
        month: Range[int, 1, 12],
        day: Range[int, 1, 31],
        hour: Range[int, 0, 23],
        minute: Range[int, 0, 59],
        server_name: str | None = None,
        description: str | None = None,
        logo: discord.Attachment | None = None,
    ) -> None:
        try:
            max_players = validate_max_players(max_players)
            start_dt = build_session_datetime(year, month, day, hour, minute)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if logo is not None and not is_image_attachment(logo.content_type):
            await interaction.response.send_message("Logo must be an image file.", ephemeral=True)
            return

        session_id = await database.create_session(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            host_id=interaction.user.id,
            company_name=company_name,
            max_players=max_players,
            start_time_utc=start_dt,
            description=description,
            logo_url=logo.url if logo else None,
            server_name=server_name,
        )
        session = await database.get_session(session_id)
        view = SessionView(session_id)
        embed = build_session_embed(session, [])
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        await database.set_session_message(session_id, message.id)
        await interaction.followup.send(
            f"✅ Session **#{session_id}** created. Use `/session cancel {session_id}` to cancel it.",
            ephemeral=True,
        )

    async def _cancel_session_internal(self, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["status"] != "pending":
            return

        await database.set_session_status(session_id, "cancelled")
        player_ids = await database.get_players(session_id)
        cancel_embed = discord.Embed(
            title="❌ Session Cancelled",
            description=f"The session **{session['company_name']}** (Session #{session_id}) has been cancelled by the host.",
            color=RED,
        )
        set_brand_footer(cancel_embed)
        for user_id in player_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=cancel_embed)
            except discord.Forbidden:
                pass

        await self._update_message(session, "cancelled", view=None)

    @app_commands.command(name="cancel", description="Cancel a pending session")
    @app_commands.describe(session_id="The ID of the session to cancel")
    async def cancel(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if session["status"] != "pending":
            await interaction.response.send_message("That session isn't pending.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can cancel this session.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self._cancel_session_internal(session_id)
        await interaction.followup.send(f"Session #{session_id} cancelled.", ephemeral=True)

    @app_commands.command(name="setlimit", description="Change the player limit for a session (host/admin only)")
    @app_commands.describe(session_id="The ID of the session", max_players="New maximum number of players")
    async def setlimit(self, interaction: discord.Interaction, session_id: int, max_players: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if session["status"] != "pending":
            await interaction.response.send_message("Can only change limit for pending sessions.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can edit this session.", ephemeral=True
            )
            return

        count = await database.count_players(session_id)
        try:
            val = validate_max_players(max_players, current_count=count)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await database.update_session_max_players(session_id, val)
        updated_session = await database.get_session(session_id)
        await self._update_message(updated_session, updated_session["status"], view=SessionView(session_id))
        await interaction.response.send_message(
            f"✅ Player limit updated to **{val}** for session #{session_id}.", ephemeral=True
        )

    @app_commands.command(name="setserver", description="Change the server location for a session at any time (host/admin only)")
    @app_commands.describe(session_id="The ID of the session", server_name="New server name or location")
    async def setserver(self, interaction: discord.Interaction, session_id: int, server_name: str) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can edit this session.", ephemeral=True
            )
            return

        new_server = server_name.strip()
        await database.update_session_server_name(session_id, new_server)
        updated_session = await database.get_session(session_id)
        status = updated_session["status"]
        view = SessionView(session_id) if status == "pending" else None
        await self._update_message(updated_session, status, view)
        await interaction.response.send_message(
            f"✅ Server location updated to **\"{new_server}\"** for session #{session_id}.", ephemeral=True
        )

    @app_commands.command(name="players", description="View who has joined a session (host/admin only)")
    @app_commands.describe(session_id="The ID of the session to view")
    async def players(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can view this session's players.", ephemeral=True
            )
            return

        player_ids = await database.get_players(session_id)
        if not player_ids:
            body = "No one has joined yet."
        else:
            body = "\n".join(f"<@{uid}>" for uid in player_ids)
        embed = discord.Embed(
            title=f"Players — {session['company_name']} (Session #{session_id})",
            description=body,
            color=BLURPLE,
        )
        set_brand_footer(embed, f"{len(player_ids)}/{session['max_players']} joined")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="list", description="List upcoming sessions in this server")
    async def list_sessions(self, interaction: discord.Interaction) -> None:
        sessions = await database.get_pending_sessions_for_guild(interaction.guild_id)
        if not sessions:
            await interaction.response.send_message("No upcoming sessions.", ephemeral=True)
            return

        lines = []
        for session in sessions:
            start_dt = datetime.fromisoformat(session["start_time_utc"])
            count = await database.count_players(session["id"])
            lines.append(
                f"**#{session['id']}** — {session['company_name']} — "
                f"<t:{int(start_dt.timestamp())}:R> — {count}/{session['max_players']}"
            )
        embed = discord.Embed(title="Upcoming Sessions", description="\n".join(lines), color=BLURPLE)
        set_brand_footer(embed)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="View details of a session")
    @app_commands.describe(session_id="The ID of the session to view")
    async def info(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        player_ids = await database.get_players(session_id)
        await interaction.response.send_message(embed=build_session_embed(session, player_ids), ephemeral=True)

    @app_commands.command(name="show", description="Repost a session's Join/Leave message for everyone")
    @app_commands.describe(session_id="The ID of the session to show")
    async def show(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        player_ids = await database.get_players(session_id)
        view = SessionView(session_id) if session["status"] == "pending" else None
        await interaction.response.send_message(embed=build_session_embed(session, player_ids), view=view)

    @app_commands.command(name="kick", description="Remove a player from a session (host/admin only)")
    @app_commands.describe(session_id="The ID of the session", user="The player to remove")
    async def kick(self, interaction: discord.Interaction, session_id: int, user: discord.Member) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can kick players from this session.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        removed = await database.remove_player(session_id, user.id)
        if not removed:
            await interaction.followup.send(
                f"{user.mention} hadn't joined this session.", ephemeral=True
            )
            return
        if session["status"] == "pending":
            await self._update_message(session, "pending", view=SessionView(session_id))
        await interaction.followup.send(
            f"Removed {user.mention} from session #{session_id}.", ephemeral=True
        )

    @app_commands.command(name="start", description="Force a pending session to start now (host/admin only)")
    @app_commands.describe(session_id="The ID of the session to start")
    async def start(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if session["status"] != "pending":
            await interaction.response.send_message("That session isn't pending.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can start this session.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self._fire_session(session)
        await interaction.followup.send(f"Session #{session_id} started.", ephemeral=True)

    @app_commands.command(name="end", description="End an active session (host/admin only)")
    @app_commands.describe(session_id="The ID of the session to end")
    async def end(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if session["status"] != "fired":
            await interaction.response.send_message("That session isn't currently active.", ephemeral=True)
            return
        if not can_manage_session(
            is_administrator=interaction.user.guild_permissions.administrator,
            is_original_host=interaction.user.id == int(session["host_id"]),
        ):
            await interaction.response.send_message(
                "Only the host or an administrator can end this session.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        player_ids = await database.get_players(session_id)
        thanks = discord.Embed(
            description=f"🙏 Thanks for joining the **{session['company_name']}** session!",
            color=GREY,
        )
        set_brand_footer(thanks)
        for user_id in player_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=thanks)
            except discord.Forbidden:
                pass
        await database.set_session_status(session_id, "ended")
        await self._update_message(session, "ended", view=None)
        await interaction.followup.send(f"Session #{session_id} ended.", ephemeral=True)

    @app_commands.command(name="active", description="List currently running sessions in this server")
    async def active(self, interaction: discord.Interaction) -> None:
        sessions = await database.get_active_sessions_for_guild(interaction.guild_id)
        if not sessions:
            await interaction.response.send_message("No active sessions right now.", ephemeral=True)
            return

        lines = []
        for session in sessions:
            count = await database.count_players(session["id"])
            lines.append(
                f"**#{session['id']}** — {session['company_name']} — {count}/{session['max_players']} joined"
            )
        embed = discord.Embed(title="Active Sessions", description="\n".join(lines), color=BLURPLE)
        set_brand_footer(embed)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show the /session commands available to you")
    async def help_command(self, interaction: discord.Interaction) -> None:
        is_admin = interaction.user.guild_permissions.administrator
        host_role_id = await database.get_host_role(interaction.guild_id)
        is_host = has_host_permission(
            is_administrator=is_admin,
            member_role_ids={role.id for role in interaction.user.roles},
            host_role_id=host_role_id,
        )

        embed = discord.Embed(title="Session Commands", color=BLURPLE)
        set_brand_footer(embed)
        embed.add_field(
            name="Everyone",
            value=(
                "`/session list` — list upcoming sessions\n"
                "`/session active` — list currently running sessions\n"
                "`/session info <id>` — view a session's details\n"
                "`/session show <id>` — repost a session's Join/Leave message\n"
                "`/session help` — show this message"
            ),
            inline=False,
        )
        if is_host:
            embed.add_field(
                name="Host",
                value=(
                    "`/session host` — host a new session\n"
                    "`/session cancel <id>` — cancel a pending session\n"
                    "`/session setlimit <id> <limit>` — change player limit\n"
                    "`/session setserver <id> <server>` — change server location\n"
                    "`/session start <id>` — force a pending session to start now\n"
                    "`/session end <id>` — end an active session\n"
                    "`/session players <id>` — view who joined a session\n"
                    "`/session kick <id> <user>` — remove a player from a session"
                ),
                inline=False,
            )
        if is_admin:
            embed.add_field(
                name="Admin",
                value="`/session hostrole <role>` — set the role allowed to host sessions",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @hostrole.error
    async def hostrole_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Only Discord server administrators can use this command.", ephemeral=True
            )

    @host.error
    async def host_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to host sessions.", ephemeral=True
            )

    async def _update_message(self, session: dict, status: str, view: discord.ui.View | None) -> None:
        if not session["message_id"]:
            return
        channel = self.bot.get_channel(int(session["channel_id"]))
        if channel is None:
            return
        try:
            message = await channel.fetch_message(int(session["message_id"]))
        except discord.NotFound:
            return
        count = await database.count_players(session["id"])
        embed = build_session_embed({**session, "status": status}, count)
        await message.edit(embed=embed, view=view)

    async def _send_session_dm(self, session: dict, embed: discord.Embed) -> None:
        player_ids = await database.get_players(session["id"])
        for user_id in player_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

    async def _send_reminder_dm(self, session: dict) -> None:
        await self._send_session_dm(session, build_reminder_dm_embed(session))
        await database.mark_session_reminder_sent(session["id"])
        session["reminder_sent"] = 1

    async def _send_start_dm(self, session: dict) -> None:
        await self._send_session_dm(session, build_start_dm_embed(session))
        await database.mark_session_start_dm_sent(session["id"])
        session["start_dm_sent"] = 1

    async def _fire_session(self, session: dict) -> None:
        if not session.get("start_dm_sent"):
            await self._send_start_dm(session)
        await database.set_session_status(session["id"], "fired")
        await self._update_message(session, "fired", view=None)

    @tasks.loop(seconds=20)
    async def check_due_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        for session in await database.get_pending_sessions():
            start_dt = datetime.fromisoformat(session["start_time_utc"])
            seconds_until_start = (start_dt - now).total_seconds()

            if not session.get("reminder_sent") and seconds_until_start <= timedelta(minutes=30).total_seconds():
                await self._send_reminder_dm(session)
            if not session.get("start_dm_sent") and seconds_until_start <= timedelta(minutes=5).total_seconds():
                await self._send_start_dm(session)
            if seconds_until_start <= 0:
                await self._fire_session(session)

    @check_due_sessions.before_loop
    async def before_check_due_sessions(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Session(bot))

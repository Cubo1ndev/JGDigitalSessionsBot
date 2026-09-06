import discord
from discord import app_commands
from discord.app_commands import Range
from discord.ext import commands, tasks
from datetime import datetime

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

STATUS_COLORS = {"pending": GREEN, "fired": BLURPLE, "ended": GREY, "cancelled": RED}
STATUS_LABELS = {
    "fired": "Started — check your DMs!",
    "ended": "Ended — thanks for joining!",
    "cancelled": "Cancelled",
}


def build_session_embed(session: dict, player_count: int) -> discord.Embed:
    start_dt = datetime.fromisoformat(session["start_time_utc"])
    status = session["status"]

    embed = discord.Embed(
        title=f"🚌 {session['company_name']}",
        description=f"Hosted by <@{session['host_id']}>",
        color=STATUS_COLORS[status],
    )
    if session.get("description"):
        embed.add_field(name="About", value=session["description"], inline=False)
    embed.add_field(name="Players", value=f"{player_count}/{session['max_players']}", inline=True)
    if status == "pending":
        embed.add_field(name="Starts", value=f"<t:{int(start_dt.timestamp())}:R>", inline=True)
    else:
        embed.add_field(name="Status", value=STATUS_LABELS[status], inline=True)
    if session.get("logo_url"):
        embed.set_thumbnail(url=session["logo_url"])
    embed.set_footer(text=f"Session #{session['id']}")
    return embed


def build_start_dm_embed(session: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🚌 Session Starting",
        description=(
            "The session is about to begin!\n\n"
            "Follow the steps below to join:\n"
            "1. Open the game.\n"
            "2. In the main menu, click **Servers**.\n"
            f"3. Search for **\"{session['company_name']}\"**.\n\n"
            "Have fun!"
        ),
        color=GREEN,
    )
    if session.get("logo_url"):
        embed.set_thumbnail(url=session["logo_url"])
    embed.set_footer(text=f"Session #{session['id']}")
    return embed


class SessionView(discord.ui.View):
    def __init__(self, session_id: int) -> None:
        super().__init__(timeout=None)
        self.session_id = session_id
        self.join_button.custom_id = f"session_join:{session_id}"
        self.leave_button.custom_id = f"session_leave:{session_id}"

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
        embed = build_session_embed(session, count + 1)
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
        count = await database.count_players(self.session_id)
        embed = build_session_embed(session, count)
        await interaction.response.edit_message(embed=embed, view=self)


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
        )
        session = await database.get_session(session_id)
        view = SessionView(session_id)
        embed = build_session_embed(session, 0)
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        await database.set_session_message(session_id, message.id)
        await interaction.followup.send(
            f"✅ Session **#{session_id}** created. Use `/session cancel {session_id}` to cancel it.",
            ephemeral=True,
        )

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
        await database.set_session_status(session_id, "cancelled")
        await self._update_message(session, "cancelled", view=None)
        await interaction.followup.send(f"Session #{session_id} cancelled.", ephemeral=True)

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
        embed.set_footer(text=f"{len(player_ids)}/{session['max_players']} joined")
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
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="View details of a session")
    @app_commands.describe(session_id="The ID of the session to view")
    async def info(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        count = await database.count_players(session_id)
        await interaction.response.send_message(embed=build_session_embed(session, count), ephemeral=True)

    @app_commands.command(name="show", description="Repost a session's Join/Leave message for everyone")
    @app_commands.describe(session_id="The ID of the session to show")
    async def show(self, interaction: discord.Interaction, session_id: int) -> None:
        session = await database.get_session(session_id)
        if session is None or session["guild_id"] != str(interaction.guild_id):
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        count = await database.count_players(session_id)
        view = SessionView(session_id) if session["status"] == "pending" else None
        await interaction.response.send_message(embed=build_session_embed(session, count), view=view)

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
                    "`/session cancel <id>` — cancel a pending session you host\n"
                    "`/session start <id>` — force a pending session to start now\n"
                    "`/session end <id>` — end an active session\n"
                    "`/session players <id>` — view who joined a session you host\n"
                    "`/session kick <id> <user>` — remove a player from a session you host"
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

    async def _fire_session(self, session: dict) -> None:
        player_ids = await database.get_players(session["id"])
        for user_id in player_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=build_start_dm_embed(session))
            except discord.Forbidden:
                pass
        await database.set_session_status(session["id"], "fired")
        await self._update_message(session, "fired", view=None)

    @tasks.loop(seconds=20)
    async def check_due_sessions(self) -> None:
        for session in await database.get_due_sessions():
            await self._fire_session(session)

    @check_due_sessions.before_loop
    async def before_check_due_sessions(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Session(bot))

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime

import database
from checks import require_host_role
from session_logic import parse_datetime_utc, parse_max_players, has_room

GREEN = discord.Color.green()
BLURPLE = discord.Color.blurple()
RED = discord.Color.red()


def build_session_embed(session: dict, player_count: int) -> discord.Embed:
    start_dt = datetime.fromisoformat(session["start_time_utc"])
    status = session["status"]
    color = {"pending": GREEN, "fired": BLURPLE, "cancelled": RED}[status]

    embed = discord.Embed(
        title=f"🚌 {session['company_name']}",
        description=f"Hosted by <@{session['host_id']}>",
        color=color,
    )
    embed.add_field(name="Players", value=f"{player_count}/{session['max_players']}", inline=True)
    if status == "pending":
        embed.add_field(name="Starts", value=f"<t:{int(start_dt.timestamp())}:R>", inline=True)
    elif status == "fired":
        embed.add_field(name="Status", value="Started — check your DMs!", inline=True)
    else:
        embed.add_field(name="Status", value="Cancelled", inline=True)
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


class HostSessionModal(discord.ui.Modal, title="Host a Session"):
    company_name = discord.ui.TextInput(label="Company name", max_length=100)
    max_players = discord.ui.TextInput(label="Max players", max_length=10)
    start_time = discord.ui.TextInput(
        label="Start date & time (UTC)", placeholder="YYYY-MM-DD HH:MM"
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            max_players = parse_max_players(self.max_players.value)
            start_dt = parse_datetime_utc(self.start_time.value)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        session_id = await database.create_session(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            host_id=interaction.user.id,
            company_name=self.company_name.value,
            max_players=max_players,
            start_time_utc=start_dt,
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
    @require_host_role()
    async def host(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(HostSessionModal())

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
        is_host = interaction.user.id == int(session["host_id"])
        is_admin = interaction.user.guild_permissions.administrator
        if not (is_host or is_admin):
            await interaction.response.send_message(
                "Only the host or an administrator can cancel this session.", ephemeral=True
            )
            return

        await database.set_session_status(session_id, "cancelled")
        await self._update_message(session, "cancelled", view=None)
        await interaction.response.send_message(f"Session #{session_id} cancelled.", ephemeral=True)

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

    @tasks.loop(seconds=20)
    async def check_due_sessions(self) -> None:
        for session in await database.get_due_sessions():
            player_ids = await database.get_players(session["id"])
            for user_id in player_ids:
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    await user.send(f"🚌 Join the server named **{session['company_name']}**!")
                except discord.Forbidden:
                    pass
            await database.set_session_status(session["id"], "fired")
            await self._update_message(session, "fired", view=None)

    @check_due_sessions.before_loop
    async def before_check_due_sessions(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Session(bot))

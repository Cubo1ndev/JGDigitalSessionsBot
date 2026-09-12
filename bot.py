import discord
from discord.ext import commands

import config
import database
from cogs.sessions import SessionView
from cogs.suggestions import SuggestionVoteView, DuplicateReportView

COGS = [
    "cogs.sessions",
    "cogs.suggestions",
]

intents = discord.Intents.default()


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        database.set_path(config.DB_PATH)
        await database.init_db()

        for cog in COGS:
            await self.load_extension(cog)

        for session in await database.get_pending_sessions():
            self.add_view(SessionView(session["id"]))

        for thread_id in await database.get_all_open_suggestion_threads():
            upvotes, downvotes = await database.get_suggestion_vote_counts(thread_id)
            self.add_view(SuggestionVoteView(thread_id, upvotes, downvotes))

        for report in await database.get_pending_duplicate_reports():
            self.add_view(DuplicateReportView(report["id"]))

        await self.tree.sync()

    async def on_ready(self) -> None:
        await self.change_presence(
            activity=discord.CustomActivity(name="Hosting Sessions 24/7")
        )
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")


def main() -> None:
    bot = Bot()
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()

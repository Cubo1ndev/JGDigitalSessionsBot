import os
from dotenv import load_dotenv

load_dotenv()

TOKEN: str = os.environ["DISCORD_TOKEN"]
DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")
GUILD_ID: int | None = int(os.environ["GUILD_ID"]) if os.getenv("GUILD_ID") else None

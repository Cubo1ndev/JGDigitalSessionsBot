import os
from dotenv import load_dotenv

load_dotenv()

TOKEN: str = os.environ["DISCORD_TOKEN"]
DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

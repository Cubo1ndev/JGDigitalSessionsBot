# JustGames Digital Sessions Bot

Discord bot for hosting scheduled game sessions with interactive session cards, attendee threads, reminders, and start/end notifications.

## Setup

1. Create a Discord application and bot, then copy its token.
2. Copy `.env.example` to `.env` and fill in `DISCORD_TOKEN`.
3. Set `GUILD_ID` while developing for faster command synchronization. Leave it empty for global commands.
4. Install dependencies:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```

5. Start the bot:

   ```powershell
   python bot.py
   ```

The SQLite database is created at `DB_PATH` on first startup.

## Discord Permissions

The bot needs permission to:

- Send messages and use Components V2.
- Create public threads and manage thread members.
- Manage messages in session threads so non-attendees can be removed.
- Send direct messages to attendees.

## Project Layout

```text
bot.py                 Application startup and cog loading
cogs/sessions.py       Session commands, views, notifications, and scheduler
database.py            SQLite persistence
session_logic.py       Pure validation and date helpers
checks.py              Host permission checks
tests/                 Database and session-logic tests
data/                  Runtime SQLite data
docs/                  Privacy policy and terms of service
```

## Deployment

Use a persistent volume for `DB_PATH`; the database must survive application restarts and redeploys. Install dependencies from `requirements.txt` and run `python bot.py`.
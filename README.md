# JustGames Digital Bot

Discord community hub for JustGames Digital. It posts a welcome and rules panel with configurable links and images, and continues to host scheduled game sessions with interactive session cards, attendee threads, reminders, and start/end notifications.

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

## Community Welcome

In the channel where the welcome should appear, run `/community welcome`. Server members with **Manage Server** permission can provide up to two banner images and links for the website, ROBLOX group, YouTube, X, rules, FAQ, and suggestions. The bot posts the welcome and rules panels; omitted links simply do not show a button. The images and links are posted to Discord and are not saved in the bot database.

## Discord Permissions

The bot needs permission to:

- Send messages, use Components V2, and attach files (for welcome banners).
- Create public threads and manage thread members.
- Manage messages in session threads so non-attendees can be removed.
- Send direct messages to attendees.

## Project Layout

```text
bot.py                 Application startup and cog loading
cogs/community.py       Community welcome and rules panels
cogs/sessions.py       Session commands, views, notifications, and scheduler
database.py            SQLite persistence
session_logic.py       Pure validation and date helpers
checks.py              Host permission checks
tests/                 Community, database, and session-logic tests
data/                  Runtime SQLite data
docs/                  Privacy policy and terms of service
```

## Deployment

Use a persistent volume for `DB_PATH`; the database must survive application restarts and redeploys. Install dependencies from `requirements.txt` and run `python bot.py`.
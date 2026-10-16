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

In the channel where the welcome should appear, run `/community welcome` (requires **Manage Server**). The bot posts a public welcome and rules panel with the banners shown above each panel.

Everything is configured in code, not in the command:

- Banners: put `welcome_banner.png` and `rules_banner.png` (png/jpg/jpeg/webp/gif) in `assets/community/`. Missing banners are skipped.
- Links, welcome text, rules, and FAQ: edit `community_content.py`. Empty URLs hide their button.
- The **Rules** and **FAQ** buttons reply privately to whoever clicks them, in the same channel.

## Discord Permissions

The bot needs permission to:

- Send messages, use Components V2, and attach files (for welcome banners).
- Create public and private threads, manage thread members, and send messages in threads.
- Manage messages in session threads so non-attendees can be removed.
- Send direct messages to attendees.
- Enable the **Server Members Intent** in the Discord Developer Portal. The bot uses it
  to add the ticket opener and Support Team role members to each private support thread.
- Give the Support Team role **View Channel** and **Send Messages in Threads** in the
  ticket parent channel.

## Project Layout

```text
bot.py                 Application startup and cog loading
cogs/community.py      Community welcome and rules panels
community_content.py   Welcome/rules/FAQ text, links (edit this)
assets/community/      Welcome and rules banner images
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
"""Edit this file to change what the community welcome panel shows.

Banners: drop `welcome_banner.png` and `rules_banner.png` (png/jpg/jpeg/webp/gif)
into `assets/community/`. A missing banner is simply not shown.
Links: leave a URL empty ("") to hide its button.
Discord limits one message to 4000 characters of text in total, so keep the
rules and FAQ below that (checked by the tests).
"""

WELCOME_TITLE = "Welcome to JustGames Digital"
WELCOME_TEXT = (
    "We're glad you're here! This is the central hub for our community — find our "
    "links, updates, support, and everything else you need, all in one place.\n\n"
    "Explore the channels, and don't be a stranger 👋"
)
RULES_PANEL_TEXT = (
    "Get to know the server rules and other important info you'll need to navigate "
    "the community — channel guides, roles, FAQs, and more."
)

SUPPORT_PANEL_TEXT = (
    "Need a hand, have feedback, or want to work with us? "
    "Pick a topic below and we'll open a private thread with our support team."
)
SUPPORT_PLACEHOLDER = "Choose how we can help..."
# (label, description, email) shown as dropdown options. Max 25 entries.
SUPPORT_CONTACTS = [
    ("Support", "Help with our games or community", "support@justgamesdigital.com"),
    ("Data Loss", "Lost progress or items in a game", "support@justgamesdigital.com"),
    ("Merch Support", "Orders and merchandise help", "support@justgamesdigital.com"),
    ("Game Acquisition", "Sell or partner on a game", "business@justgamesdigital.com"),
    ("Business Inquiries", "Partnerships and business", "business@justgamesdigital.com"),
]

WEBSITE_URL = "https://justgamesdigital.com/"
ROBLOX_GROUP_URL = "https://www.roblox.com/communities/4866418"
YOUTUBE_URL = "https://www.youtube.com/@JustGamesDigital"
X_URL = "https://x.com/JustGamesGreece"
TIKTOK_URL = "https://www.tiktok.com/@justgamesdigital"

RULES_TITLE = "Discord Server Rules"
RULES_INTRO = (
    "These rules apply to every community member. No exceptions are made, regardless "
    "of friendship with staff, developers, or owners. Everyone is held accountable "
    "when the rules are broken."
)
# (heading, body) pairs, numbered automatically.
RULES = [
    (
        "Be Kind to Others",
        "Everyone has the right to feel safe and welcome here without hate from other "
        "users. Please be kind and respectful to everyone.",
    ),
    (
        "Use Channels for Their Intended Purpose",
        "Use the correct channels for the correct things, e.g. bot commands go in the "
        "commands channel.",
    ),
    (
        "Follow Discord's Terms of Service",
        "You must follow the [Discord Terms of Service](https://discord.com/terms) at all times.",
    ),
    (
        "No Spamming or Raiding",
        "Do not repeatedly send the same message. You will most likely be automodded; "
        "if not, you'll be muted for 4 hours.",
    ),
    (
        "Discussion of Serious Topics",
        "Keep controversial topics to a minimum. If you want to discuss something "
        "sensitive with someone, take it to direct messages.",
    ),
    (
        "No NSFW Content",
        "Pornography, gore, and similar content is completely banned. Posting it "
        "results in permanent removal from the server.",
    ),
    (
        "Advertising",
        "Keep all advertisements in the designated advertising channel to avoid "
        "floods in other channels.",
    ),
    (
        "Hate Speech",
        "Hate speech is not tolerated. This includes, but is not limited to, racism, "
        "homophobia, sexism, slurs, harmful ideologies, and degrading or harmful "
        "political views.\n"
        "You have the right to freedom of speech, **however** JustGames does not "
        "tolerate opinions that harm or degrade others. Lack of knowledge or maturity "
        "is not accepted as an excuse.",
    ),
]
RULES_NOTES = (
    "**Additional notes**\n"
    "Staff may increase the level of action depending on the severity of the rule "
    "broken. Issues with a punishment can be taken to Group Management, or a dispute "
    "can be opened in the support channel."
)

FAQ_TITLE = "Frequently Asked Questions"
FAQ_INTRO = (
    "Quick answers about JustGames Digital, School Bus Sim and our community sessions."
)
# (question, answer) pairs.
FAQ = [
    (
        "Who is JustGames Digital?",
        "We're a small studio dedicated to creating top-quality experiences on Roblox, "
        "including **School Bus Sim**. Find all our links in the welcome panel above.",
    ),
    (
        "How do I join a session?",
        "Click **Join** on a session post. You'll be added to the session's private "
        "thread and receive a reminder in your DMs before it starts.",
    ),
    (
        "I'm not getting DMs from the bot.",
        "Enable **Direct Messages** from server members in your Discord privacy "
        "settings for this server, then leave and rejoin the session.",
    ),
    (
        "How do I get into the game when a session starts?",
        "You'll get a DM with the steps: open the game, click **Servers** in the main "
        "menu, then search for the server or company name given in the message.",
    ),
    (
        "Can I leave a session?",
        "Yes, click **Leave** on the session post at any time. This frees your spot "
        "for someone else.",
    ),
    (
        "The session is full. What can I do?",
        "Each session has a player limit. Keep an eye on the post: if someone leaves, "
        "a spot opens up and you can click **Join**.",
    ),
    (
        "Who can host a session?",
        "Hosting is limited to members with the host role. If you'd like to host, ask a "
        "staff member.",
    ),
    (
        "I lost my progress or items in a game.",
        "Open a **Data Loss** ticket from the support panel and tell us what happened "
        "and when.",
    ),
    (
        "How do I contact the team?",
        "Use the support dropdown in the welcome panel. Pick a topic to see our email "
        "or open a private ticket and a team member will join you.",
    ),
    ("How do I get a role?", "Check the role channels or ask a staff member."),
    (
        "I have an idea for the community.",
        "Share it through the Suggestions channel.",
    ),
]

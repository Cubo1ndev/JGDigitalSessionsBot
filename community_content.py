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

WEBSITE_URL = ""
ROBLOX_GROUP_URL = ""
YOUTUBE_URL = ""
X_URL = ""
SUGGESTIONS_URL = ""

RULES_TITLE = "📜 Discord Server Rules"
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

FAQ_TITLE = "❓ Frequently Asked Questions"
FAQ_INTRO = "Quick answers to the things we get asked most."
# (question, answer) pairs.
FAQ = [
    (
        "How do I join a session?",
        "Click **Join** on a session post and watch your DMs for reminders.",
    ),
    ("How do I get a role?", "Check the role channels or ask a staff member."),
    (
        "How do I contact staff?",
        "Open a support request or message a moderator.",
    ),
    (
        "I have an idea for the community.",
        "Share it through the Suggestions channel.",
    ),
]

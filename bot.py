import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from utils.translator import translate, translate_message_with_links
from langdetect import detect
from utils.config_manager import ConfigManager

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.json")  # Default to config.json if not set

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize config manager
config_manager = ConfigManager(CONFIG_FILE)

@bot.tree.command(name="settranslate", description="Set translation channels")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
@app_commands.describe(
    source="Channel to read messages from",
    target="Channel to post translations into"
)
async def settranslate(interaction, source: discord.TextChannel, target: discord.TextChannel):
    guild_id = str(interaction.guild.id)
    config_manager.set_guild_config(guild_id, source.id, target.id)
    await interaction.response.send_message(f"Translations set: {source.mention} → {target.mention}", ephemeral=True)

@bot.event
async def on_message(message):
    # Skip messages from bots or DMs
    if message.author.bot or not message.guild:
        return

    # Skip emojis
    if not message.content.strip():
        return

    # Skip commands
    if message.content.startswith("/"):
        return

    # Get guild configuration
    guild_cfg = config_manager.get_guild_config(message.guild.id)
    if not guild_cfg or not guild_cfg.get("enabled", False):
        return

    # Only process messages from the source channel
    if message.channel.id != guild_cfg["source"]:
        return

    print(f"DEBUG: Processing message from {message.author.display_name}: '{message.content[:50]}...'")

    # Translate the message (handling links properly)
    translated = translate_message_with_links(message.content, target="en")

    # Skip if no translation is needed (English message, link-only, or other reason)
    if translated is None:
        print(f"DEBUG: Skipping message - no translation needed")
        return

    print(f"DEBUG: Translated message: '{translated[:50]}...'")

    # Send to target channel
    target_channel = bot.get_channel(guild_cfg["target"])
    if target_channel:
        await target_channel.send(f"**{message.author.display_name}:** {translated}")
    else:
        print(f"Could not find target channel with ID: {guild_cfg['target']}")

    await bot.process_commands(message)

@bot.event
async def on_ready():
    """Initialize bot when ready"""

    activity = discord.Game(name="translating aliens 👽")
    await bot.change_presence(activity=activity)

    print(f"Bot logged in as {bot.user.name}")

    guild = discord.Object(id=1255655420509294642)

    # 🔥 Delete ALL guild commands
    bot.tree.clear_commands(guild=guild)
    print("Guild commands CLEARED")

    await bot.tree.sync()  # Sync commands with Discord

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(DISCORD_TOKEN)

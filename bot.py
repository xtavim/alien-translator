import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from utils.translator import translate, translate_message_with_links
from langdetect import detect
from utils.config_manager import ConfigManager
from utils.queue_manager import TranslationQueueManager

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.json")  # Default to config.json if not set

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize config manager
config_manager = ConfigManager(CONFIG_FILE)

# Initialize queue manager (will be created in on_ready)
queue_manager = None

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

@bot.tree.command(name="queuestatus", description="Check the translation queue status")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def queuestatus(interaction):
    """Shows the current status of the translation queue"""
    global queue_manager

    if not queue_manager:
        await interaction.response.send_message("Queue manager not initialized", ephemeral=True)
        return

    queue_size = queue_manager.translation_queue.qsize()
    worker_status = "Running" if queue_manager.worker_running else "Stopped"

    embed = discord.Embed(
        title="Translation Queue Status",
        color=interaction.user.color
    )

    embed.add_field(name="Queue Size", value=f"{queue_size} messages waiting", inline=True)
    embed.add_field(name="Worker Status", value=worker_status, inline=True)
    embed.add_field(name="Rate Limit", value=f"{queue_manager.rate_limit_delay}s between translations", inline=True)

    # Calculate approximate wait time
    if queue_size > 0 and queue_manager.rate_limit_delay > 0:
        wait_time = queue_size * queue_manager.rate_limit_delay
        embed.add_field(name="Approx. Wait Time", value=f"{wait_time:.1f} seconds", inline=False)

    # Add tips based on queue status
    if queue_size > 10:
        embed.set_footer(text="Consider increasing rate limit with /queuerate")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="queuerate", description="Adjust the rate limit between translations")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
@app_commands.describe(
    delay="Delay in seconds between API calls (default: 1.0)"
)
async def queuerate(interaction, delay: float = 1.0):
    """Adjusts the rate limit for the translation queue"""
    global queue_manager

    if not queue_manager:
        await interaction.response.send_message("Queue manager not initialized", ephemeral=True)
        return

    if delay < 0.1 or delay > 10.0:
        await interaction.response.send_message("Delay must be between 0.1 and 10.0 seconds", ephemeral=True)
        return

    queue_manager.set_rate_limit(delay)
    await interaction.response.send_message(f"Rate limit set to {delay}s between translations", ephemeral=True)

@bot.tree.command(name="queueclear", description="Clear all pending translations")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def queueclear(interaction):
    """Clears all pending translations from the queue"""
    global queue_manager

    if not queue_manager:
        await interaction.response.send_message("Queue manager not initialized", ephemeral=True)
        return

    queue_size = queue_manager.get_queue_size()
    queue_manager.clear_queue()
    await interaction.response.send_message(f"Cleared {queue_size} pending translations", ephemeral=True)

@bot.tree.command(name="queuepause", description="Pause the translation queue")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def queuepause(interaction):
    """Pauses processing of the translation queue"""
    global queue_manager

    if not queue_manager:
        await interaction.response.send_message("Queue manager not initialized", ephemeral=True)
        return

    if queue_manager.is_worker_running():
        queue_manager.pause()
        await interaction.response.send_message("Translation queue paused", ephemeral=True)
    else:
        await interaction.response.send_message("Translation queue is already paused", ephemeral=True)

@bot.tree.command(name="queueresume", description="Resume the translation queue")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def queueresume(interaction):
    """Resumes processing of the translation queue"""
    global queue_manager

    if not queue_manager:
        await interaction.response.send_message("Queue manager not initialized", ephemeral=True)
        return

    if not queue_manager.is_worker_running():
        queue_manager.resume()
        await interaction.response.send_message("Translation queue resumed", ephemeral=True)
    else:
        await interaction.response.send_message("Translation queue is already running", ephemeral=True)

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

    print(f"Adding message from {message.author.display_name} to translation queue: '{message.content[:50]}...'")

    # Add message to the translation queue
    queue_manager.add_message(message, guild_cfg)

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

    # Initialize and start the translation queue manager
    global queue_manager
    queue_manager = TranslationQueueManager(bot, CONFIG_FILE)
    queue_manager.start()

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(DISCORD_TOKEN)

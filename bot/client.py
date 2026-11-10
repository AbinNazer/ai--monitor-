import discord
from discord.ext import commands
import config

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def post_embed(embed: discord.Embed):
    channel = bot.get_channel(config.DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


async def start_bot():
    from bot.commands import setup
    await setup(bot)
    await bot.start(config.DISCORD_BOT_TOKEN)
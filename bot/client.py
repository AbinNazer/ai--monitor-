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
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument. Try `{bot.command_prefix}help` or use the slash command menu.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("I couldn't understand that argument. Use the slash command menu for the expected format.")
        return
    await ctx.send(f"Command failed: {error}")
    print(f"Command error: {type(error).__name__}: {error}", flush=True)


async def start_bot():
    from bot.commands import setup
    await setup(bot)
    await bot.start(config.DISCORD_BOT_TOKEN)

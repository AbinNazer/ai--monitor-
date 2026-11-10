import discord
from discord.ext import commands
import config
from bot.commands import handle_natural_message

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def post_embed(embed: discord.Embed) -> bool:
    channel = bot.get_channel(config.DISCORD_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(config.DISCORD_CHANNEL_ID)
        except (discord.DiscordException, discord.HTTPException):
            print(f"Unable to access Discord channel {config.DISCORD_CHANNEL_ID}", flush=True)
            return False
    await channel.send(embed=embed)
    return True


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id == config.DISCORD_CHANNEL_ID:
        try:
            await handle_natural_message(message)
        except Exception as error:
            await message.channel.send(f"I couldn't complete that request: {error}")
            print(f"Natural-language error: {type(error).__name__}: {error}", flush=True)
    await bot.process_commands(message)


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

import os
import logging
import asyncio
import discord
from discord.ext import commands
import traceback
import sys

# Import configuration
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bot')

async def setup_bot():
    """Set up and configure the Discord bot"""
    # Set up intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    # Create bot instance with prefix specified in config
    bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents, description="Discord Gambling Bot")
    
    # Set bot status
    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
        # Set bot activity
        await bot.change_presence(activity=discord.Game(name=f"{config.COMMAND_PREFIX}help | Gambling Bot"))
        
        # Start mining update task if Mining cog is loaded
        if not hasattr(bot, "_mining_task_started"):
            bot._mining_task_started = True
            mining_cog = bot.get_cog("Mining")
            if mining_cog:
                bot.loop.create_task(mining_cog.mining_update_task())
                logger.info("Mining background task started")
        
        logger.info("Bot is ready!")
    
    # Error handling
    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}. Use `{config.COMMAND_PREFIX}help {ctx.command}` for proper usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Invalid argument. Use `{config.COMMAND_PREFIX}help {ctx.command}` for proper usage.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Command on cooldown. Try again in {error.retry_after:.2f} seconds.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in private messages.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have the required permissions to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f"I don't have the required permissions: {error.missing_perms}")
        else:
            logger.error(f"Command {ctx.command} raised an exception: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send(f"An error occurred: {error}")
    
    # Load cogs (command categories)
    try:
        await bot.load_extension("cogs.economy")
        await bot.load_extension("cogs.gambling")
        await bot.load_extension("cogs.mining")
        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.extended_slots")  # Load our new extended slots cog
        logger.info("All cogs loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load cogs: {e}")
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
    
    return bot

if __name__ == "__main__":
    # For running the bot standalone (without Flask)
    async def main():
        # Get token from environment variables
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            logger.error("No Discord bot token found. Set the DISCORD_BOT_TOKEN environment variable.")
            exit(1)
        
        bot = await setup_bot()
        try:
            await bot.start(TOKEN)
        except KeyboardInterrupt:
            await bot.close()
            logger.info("Bot has been shut down.")
    
    # Run the bot
    asyncio.run(main())

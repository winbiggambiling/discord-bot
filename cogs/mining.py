import discord
from discord.ext import commands
from database.database import get_session
from database.models import User, Transaction, MiningStats, TransactionType
from sqlalchemy import select
import os
import sys
import asyncio
import random
import datetime
import logging
import math

# Add the parent directory to the path to find the config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.formatters import format_currency, format_time
from utils.helpers import create_user_if_not_exists

# Configure logging
logger = logging.getLogger('mining')

class Mining(commands.Cog):
    """Mining commands for the gambling bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.currently_mining = {}  # Track users that are currently mining
        
        # We'll start the background task when the cog is added to the bot
        # This avoids the "loop attribute cannot be accessed in non-async contexts" error
    
    async def mining_update_task(self):
        """Background task to periodically update mining stats"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                # Update currently mining users
                miners_to_remove = []
                
                for user_id, mining_data in list(self.currently_mining.items()):
                    now = datetime.datetime.utcnow()
                    elapsed = (now - mining_data["start_time"]).total_seconds()
                    
                    # Check if mining session has ended
                    if elapsed >= mining_data["duration"]:
                        # Mining session completed
                        miners_to_remove.append(user_id)
                        
                        # Process the completed mining session
                        await self.complete_mining_session(user_id, mining_data)
                
                # Remove completed miners
                for user_id in miners_to_remove:
                    if user_id in self.currently_mining:
                        del self.currently_mining[user_id]
                
            except Exception as e:
                logger.error(f"Error in mining update task: {e}")
            
            # Run every few seconds
            await asyncio.sleep(5)
    
    async def complete_mining_session(self, user_id, mining_data):
        """Complete a mining session and reward the user"""
        try:
            # Get Discord user from ID
            user = self.bot.get_user(int(user_id))
            if not user:
                logger.error(f"Could not find user with ID {user_id}")
                return
            
            # Calculate earned amount based on mining power and duration
            duration = mining_data["duration"]
            mining_power = mining_data["mining_power"]
            mining_multiplier = mining_data["mining_multiplier"]
            
            # Base earnings formula
            base_earnings = (duration / 60) * mining_power * mining_multiplier
            
            # Add random variation (±10%)
            variation = random.uniform(-0.1, 0.1)
            earned_amount = base_earnings * (1 + variation)
            
            # Add random bonus chance (5% chance for 2x bonus)
            if random.random() < 0.05:
                earned_amount *= 2
                bonus = True
            else:
                bonus = False
            
            # Round to 2 decimal places
            earned_amount = round(earned_amount, 2)
            
            with get_session() as session:
                # Update user in database
                db_user = session.scalar(select(User).where(User.discord_id == str(user_id)))
                
                if not db_user:
                    logger.error(f"User {user_id} not found in database")
                    return
                
                # Update user balance
                db_user.balance += earned_amount
                db_user.mining_last_time = datetime.datetime.utcnow()
                
                # Create transaction record
                transaction = Transaction(
                    user_id=db_user.id,
                    amount=earned_amount,
                    transaction_type=TransactionType.MINING.value,
                    description=f"Mining session ({duration} seconds)"
                )
                session.add(transaction)
                
                # Create mining stats record
                mining_stats = MiningStats(
                    user_id=db_user.id,
                    mining_duration=duration,
                    amount_earned=earned_amount
                )
                session.add(mining_stats)
                
                # Update bot statistics
                from database.models import BotStatistics
                bot_stats = session.scalar(select(BotStatistics).limit(1))
                
                if not bot_stats:
                    # Create stats record if it doesn't exist
                    bot_stats = BotStatistics()
                    session.add(bot_stats)
                
                bot_stats.total_mined += earned_amount
            
            # Attempt to DM the user that mining completed
            try:
                embed = discord.Embed(
                    title="⛏️ Mining Complete!",
                    description=f"Your mining session has finished!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Session Duration",
                    value=f"{duration} seconds",
                    inline=True
                )
                
                embed.add_field(
                    name="Mining Power",
                    value=f"{mining_power:.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="Multiplier",
                    value=f"{mining_multiplier:.2f}x",
                    inline=True
                )
                
                embed.add_field(
                    name="Earned Amount",
                    value=format_currency(earned_amount),
                    inline=False
                )
                
                if bonus:
                    embed.add_field(
                        name="BONUS!",
                        value="🎉 You got lucky and received a 2x bonus! 🎉",
                        inline=False
                    )
                
                embed.add_field(
                    name="New Balance",
                    value=format_currency(db_user.balance),
                    inline=False
                )
                
                await user.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send DM to user {user_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error completing mining session for user {user_id}: {e}")
    
    @commands.command(name="mine", aliases=["mining"])
    async def mine(self, ctx, duration: int = None):
        """
        Start mining for currency.
        Usage: !mine [duration in minutes, default=5]
        """
        
        # Check if already mining
        if str(ctx.author.id) in self.currently_mining:
            # Calculate remaining time
            mining_data = self.currently_mining[str(ctx.author.id)]
            now = datetime.datetime.utcnow()
            elapsed = (now - mining_data["start_time"]).total_seconds()
            remaining = max(0, mining_data["duration"] - elapsed)
            
            embed = discord.Embed(
                title="⛏️ Already Mining",
                description="You are already mining!",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="Time Remaining",
                value=f"{remaining:.0f} seconds",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        # Set default duration if not provided
        if duration is None:
            duration = 5  # Default to 5 minutes
        
        # Validate duration (1-60 minutes)
        if duration < 1:
            duration = 1
        elif duration > 60:
            duration = 60
        
        # Convert minutes to seconds
        duration_seconds = duration * 60
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user can start mining (cooldown)
            now = datetime.datetime.utcnow()
            
            if user.mining_last_time and (now - user.mining_last_time).total_seconds() < config.MINING_COOLDOWN:
                # Calculate cooldown remaining
                next_mining = user.mining_last_time + datetime.timedelta(seconds=config.MINING_COOLDOWN)
                time_remaining = next_mining - now
                
                embed = discord.Embed(
                    title="⛏️ Mining Cooldown",
                    description="You need to rest before mining again!",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="Cooldown Remaining",
                    value=format_time(time_remaining.total_seconds()),
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return
            
            # Start mining session
            self.currently_mining[str(ctx.author.id)] = {
                "start_time": now,
                "duration": duration_seconds,
                "mining_power": user.mining_power,
                "mining_multiplier": user.mining_multiplier,
                "ctx": ctx  # Store context for callback
            }
            
            # Estimate earnings
            base_estimate = (duration_seconds / 60) * user.mining_power * user.mining_multiplier
            min_estimate = base_estimate * 0.9
            max_estimate = base_estimate * 1.1
            
            # Create embed for mining start
            embed = discord.Embed(
                title="⛏️ Mining Started",
                description=f"{ctx.author.mention} has started mining!",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Duration",
                value=f"{duration} minutes",
                inline=True
            )
            
            embed.add_field(
                name="Mining Power",
                value=f"{user.mining_power:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="Multiplier",
                value=f"{user.mining_multiplier:.2f}x",
                inline=True
            )
            
            embed.add_field(
                name="Estimated Earnings",
                value=f"{format_currency(min_estimate)} - {format_currency(max_estimate)}",
                inline=False
            )
            
            embed.set_footer(text="Mining runs in the background. You'll be notified when it's complete.")
            
            await ctx.send(embed=embed)
    
    @commands.command(name="miner", aliases=["minerstats"])
    async def miner_stats(self, ctx):
        """Check your mining stats"""
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if currently mining
            currently_mining = str(ctx.author.id) in self.currently_mining
            mining_status = "🟢 Active" if currently_mining else "🔴 Inactive"
            
            if currently_mining:
                mining_data = self.currently_mining[str(ctx.author.id)]
                now = datetime.datetime.utcnow()
                elapsed = (now - mining_data["start_time"]).total_seconds()
                remaining = max(0, mining_data["duration"] - elapsed)
                mining_status += f" ({remaining:.0f}s remaining)"
            
            # Get mining history stats
            total_mined = session.scalar(
                select(func.sum(MiningStats.amount_earned))
                .where(MiningStats.user_id == user.id)
            ) or 0
            
            total_sessions = session.scalar(
                select(func.count())
                .select_from(MiningStats)
                .where(MiningStats.user_id == user.id)
            ) or 0
            
            # Calculate next level up requirements
            current_level = user.mining_level
            next_level = current_level + 1
            
            # Cost to upgrade using exponential scaling formula
            upgrade_cost = config.MINING_BASE_UPGRADE_COST * (math.pow(config.MINING_UPGRADE_COST_MULTIPLIER, current_level - 1))
            upgrade_cost = round(upgrade_cost, 2)
            
            # Power increase for next level
            next_level_power = user.mining_power + config.MINING_POWER_INCREASE
            
            # Create embed
            embed = discord.Embed(
                title="⛏️ Mining Stats",
                description=f"Mining stats for {ctx.author.mention}",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Mining Status",
                value=mining_status,
                inline=False
            )
            
            embed.add_field(
                name="Mining Level",
                value=f"{user.mining_level}",
                inline=True
            )
            
            embed.add_field(
                name="Mining Power",
                value=f"{user.mining_power:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="Multiplier",
                value=f"{user.mining_multiplier:.2f}x",
                inline=True
            )
            
            if user.mining_last_time:
                embed.add_field(
                    name="Last Mining Session",
                    value=user.mining_last_time.strftime("%Y-%m-%d %H:%M:%S"),
                    inline=False
                )
            
            embed.add_field(
                name="Total Mined",
                value=format_currency(total_mined),
                inline=True
            )
            
            embed.add_field(
                name="Total Sessions",
                value=str(total_sessions),
                inline=True
            )
            
            embed.add_field(
                name="Upgrade to Level " + str(next_level),
                value=f"Cost: {format_currency(upgrade_cost)}\nNew Power: {next_level_power:.2f}",
                inline=False
            )
            
            embed.set_footer(text=f"Use {config.COMMAND_PREFIX}upgrademiner to upgrade your mining equipment")
            
            await ctx.send(embed=embed)
    
    @commands.command(name="upgrademiner", aliases=["levelup", "upgrade"])
    async def upgrade_miner(self, ctx):
        """Upgrade your mining equipment to increase mining power"""
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Calculate upgrade cost using exponential scaling formula
            current_level = user.mining_level
            upgrade_cost = config.MINING_BASE_UPGRADE_COST * (math.pow(config.MINING_UPGRADE_COST_MULTIPLIER, current_level - 1))
            upgrade_cost = round(upgrade_cost, 2)
            
            # Check if user has enough balance
            if user.balance < upgrade_cost:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You need {format_currency(upgrade_cost)} to upgrade your mining equipment.",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="Your Balance",
                    value=format_currency(user.balance),
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return
            
            # Deduct cost and upgrade mining level
            user.balance -= upgrade_cost
            user.mining_level += 1
            user.mining_power += config.MINING_POWER_INCREASE
            
            # Add random multiplier bonus (5% chance)
            if random.random() < 0.05:
                multiplier_bonus = random.uniform(0.1, 0.3)
                user.mining_multiplier += multiplier_bonus
                bonus_received = True
            else:
                bonus_received = False
            
            # Record transaction
            transaction = Transaction(
                user_id=user.id,
                amount=-upgrade_cost,
                transaction_type=TransactionType.WITHDRAWAL.value,
                description=f"Mining equipment upgrade to level {user.mining_level}"
            )
            session.add(transaction)
            
            # Create success embed
            embed = discord.Embed(
                title="⛏️ Mining Equipment Upgraded!",
                description=f"You've upgraded your mining equipment to level {user.mining_level}!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Cost",
                value=format_currency(upgrade_cost),
                inline=True
            )
            
            embed.add_field(
                name="New Mining Power",
                value=f"{user.mining_power:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="Multiplier",
                value=f"{user.mining_multiplier:.2f}x",
                inline=True
            )
            
            if bonus_received:
                embed.add_field(
                    name="BONUS!",
                    value=f"🎉 Lucky! You received a +{multiplier_bonus:.2f}x multiplier bonus! 🎉",
                    inline=False
                )
            
            embed.add_field(
                name="New Balance",
                value=format_currency(user.balance),
                inline=False
            )
            
            await ctx.send(embed=embed)

from sqlalchemy import func

async def setup(bot):
    # Just add the cog, we'll handle the background task differently
    cog = Mining(bot)
    await bot.add_cog(cog)

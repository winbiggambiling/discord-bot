import discord
from discord.ext import commands
from database.database import get_session
from database.models import User, Transaction, TransactionType
from sqlalchemy import select
import os
import sys
import logging

# Add the parent directory to the path to find the config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.formatters import format_currency
from utils.helpers import create_user_if_not_exists

# Configure logging
logger = logging.getLogger('admin')

class Admin(commands.Cog):
    """Admin commands for the gambling bot (owner only)"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_check(self, ctx):
        """Check if user is a bot owner"""
        # Only bot owner can use these commands
        return await self.bot.is_owner(ctx.author)
    
    @commands.command(name="admin_addbalance", aliases=["addbal"])
    async def admin_add_balance(self, ctx, user: discord.Member, amount: float):
        """[ADMIN] Add balance to a user's account"""
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        with get_session() as session:
            target_user = create_user_if_not_exists(session, user)
            
            # Add balance
            target_user.balance += amount
            
            # Record transaction
            transaction = Transaction(
                user_id=target_user.id,
                amount=amount,
                transaction_type=TransactionType.ADMIN.value,
                description=f"Admin balance addition by {ctx.author.name}"
            )
            session.add(transaction)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Admin Balance Addition",
                description=f"Added {format_currency(amount)} to {user.mention}'s balance",
                color=discord.Color.green()
            )
            
            embed.add_field(name="New Balance", value=format_currency(target_user.balance), inline=False)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="admin_removebalance", aliases=["removebal"])
    async def admin_remove_balance(self, ctx, user: discord.Member, amount: float):
        """[ADMIN] Remove balance from a user's account"""
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        with get_session() as session:
            target_user = create_user_if_not_exists(session, user)
            
            # Remove balance (don't allow negative)
            if target_user.balance < amount:
                amount = target_user.balance
            
            target_user.balance -= amount
            
            # Record transaction
            transaction = Transaction(
                user_id=target_user.id,
                amount=-amount,
                transaction_type=TransactionType.ADMIN.value,
                description=f"Admin balance removal by {ctx.author.name}"
            )
            session.add(transaction)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Admin Balance Removal",
                description=f"Removed {format_currency(amount)} from {user.mention}'s balance",
                color=discord.Color.yellow()
            )
            
            embed.add_field(name="New Balance", value=format_currency(target_user.balance), inline=False)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="admin_resetbalance", aliases=["resetbal"])
    async def admin_reset_balance(self, ctx, user: discord.Member):
        """[ADMIN] Reset a user's balance to 0"""
        
        with get_session() as session:
            target_user = create_user_if_not_exists(session, user)
            
            # Store old balance for transaction record
            old_balance = target_user.balance
            
            # Reset balance
            target_user.balance = 0
            
            # Record transaction if there was a balance to reset
            if old_balance > 0:
                transaction = Transaction(
                    user_id=target_user.id,
                    amount=-old_balance,
                    transaction_type=TransactionType.ADMIN.value,
                    description=f"Admin balance reset by {ctx.author.name}"
                )
                session.add(transaction)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Admin Balance Reset",
                description=f"Reset {user.mention}'s balance to 0",
                color=discord.Color.red()
            )
            
            embed.add_field(name="Previous Balance", value=format_currency(old_balance), inline=False)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="admin_resetmining", aliases=["resetmine"])
    async def admin_reset_mining(self, ctx, user: discord.Member):
        """[ADMIN] Reset a user's mining stats to default"""
        
        with get_session() as session:
            target_user = create_user_if_not_exists(session, user)
            
            # Reset mining stats
            target_user.mining_level = 1
            target_user.mining_power = 1.0
            target_user.mining_multiplier = 1.0
            target_user.mining_last_time = None
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Admin Mining Reset",
                description=f"Reset {user.mention}'s mining stats to default",
                color=discord.Color.red()
            )
            
            await ctx.send(embed=embed)
    
    @commands.command(name="admin_stats")
    async def admin_stats(self, ctx):
        """[ADMIN] Get statistics about the bot and economy"""
        
        with get_session() as session:
            # Count total users
            user_count = session.scalar(select(func.count()).select_from(User))
            
            # Get total currency in circulation
            total_currency = session.scalar(select(func.sum(User.balance)).select_from(User)) or 0
            
            # Get richest user
            richest_user = session.execute(
                select(User.username, User.balance)
                .order_by(User.balance.desc())
                .limit(1)
            ).first()
            
            # Get bot statistics
            from database.models import BotStatistics
            bot_stats = session.scalar(select(BotStatistics).limit(1))
            
            if not bot_stats:
                # Create stats record if it doesn't exist
                bot_stats = BotStatistics()
                session.add(bot_stats)
                session.flush()
            
            # Create embed
            embed = discord.Embed(
                title="📊 Bot Statistics",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Total Users", value=str(user_count), inline=True)
            embed.add_field(name="Total Currency", value=format_currency(total_currency), inline=True)
            
            if richest_user:
                embed.add_field(
                    name="Richest User",
                    value=f"{richest_user[0]} ({format_currency(richest_user[1])})",
                    inline=True
                )
            
            embed.add_field(name="Total Bets", value=str(bot_stats.total_bets), inline=True)
            embed.add_field(name="Total Bet Amount", value=format_currency(bot_stats.total_bet_amount), inline=True)
            embed.add_field(name="Total Payout Amount", value=format_currency(bot_stats.total_payout_amount), inline=True)
            
            payback_percentage = 0
            if bot_stats.total_bet_amount > 0:
                payback_percentage = (bot_stats.total_payout_amount / bot_stats.total_bet_amount) * 100
            
            embed.add_field(
                name="Payback Percentage",
                value=f"{payback_percentage:.2f}%",
                inline=True
            )
            
            embed.add_field(
                name="Total Mined",
                value=format_currency(bot_stats.total_mined),
                inline=True
            )
            
            await ctx.send(embed=embed)

from sqlalchemy import func

async def setup(bot):
    await bot.add_cog(Admin(bot))

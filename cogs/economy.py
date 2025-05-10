import discord
from discord.ext import commands
from database.database import get_session
from database.models import User, Transaction, TransactionType
from sqlalchemy import select
import os
import sys
import datetime
import asyncio
import random
import logging

# Add the parent directory to the path to find the config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.formatters import format_currency, format_time
from utils.helpers import create_user_if_not_exists

# Configure logging
logger = logging.getLogger('economy')

class Economy(commands.Cog):
    """Economy commands for the gambling bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx):
        """Check your current balance"""
        
        # Ensure user exists in database
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Create embed to display balance
            embed = discord.Embed(
                title="💰 Your Balance",
                description=f"You have {format_currency(user.balance)}",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily reward"""
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user can claim daily reward
            now = datetime.datetime.utcnow()
            
            if user.last_daily and (now - user.last_daily).total_seconds() < 86400:  # 24 hours in seconds
                # Calculate time remaining
                next_daily = user.last_daily + datetime.timedelta(days=1)
                time_remaining = next_daily - now
                
                # Format time remaining
                hours, remainder = divmod(time_remaining.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                embed = discord.Embed(
                    title="❌ Daily Reward",
                    description=f"You've already claimed your daily reward.\nCome back in {hours}h {minutes}m {seconds}s",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Calculate daily reward amount (base amount + random bonus)
            daily_amount = config.DAILY_REWARD_BASE + random.randint(0, config.DAILY_REWARD_BONUS)
            
            # Update user
            user.balance += daily_amount
            user.last_daily = now
            
            # Record transaction
            transaction = Transaction(
                user_id=user.id,
                amount=daily_amount,
                transaction_type=TransactionType.DAILY.value,
                description="Daily reward"
            )
            session.add(transaction)
            
            # Create embed for success message
            embed = discord.Embed(
                title="✅ Daily Reward Claimed!",
                description=f"You received {format_currency(daily_amount)}!",
                color=discord.Color.green()
            )
            embed.add_field(name="New Balance", value=format_currency(user.balance), inline=False)
            embed.set_footer(text=f"Come back tomorrow for another reward!")
            
            await ctx.send(embed=embed)
    
    @commands.command(name="transfer", aliases=["send", "pay"])
    async def transfer(self, ctx, recipient: discord.Member, amount: float):
        """Transfer currency to another user"""
        
        # Check for valid amount
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        if recipient.bot:
            await ctx.send("❌ You can't transfer currency to bots!")
            return
        
        if recipient.id == ctx.author.id:
            await ctx.send("❌ You can't transfer currency to yourself!")
            return
        
        with get_session() as session:
            sender = create_user_if_not_exists(session, ctx.author)
            
            # Check if sender has enough balance
            if sender.balance < amount:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You don't have enough funds to send {format_currency(amount)}.\nYour balance: {format_currency(sender.balance)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Get or create recipient user
            recipient_user = create_user_if_not_exists(session, recipient)
            
            # Update balances
            sender.balance -= amount
            recipient_user.balance += amount
            
            # Record transactions
            sender_transaction = Transaction(
                user_id=sender.id,
                amount=-amount,
                transaction_type=TransactionType.WITHDRAWAL.value,
                description=f"Transfer to {recipient.name}#{recipient.discriminator}"
            )
            
            recipient_transaction = Transaction(
                user_id=recipient_user.id,
                amount=amount,
                transaction_type=TransactionType.DEPOSIT.value,
                description=f"Transfer from {ctx.author.name}#{ctx.author.discriminator}"
            )
            
            session.add_all([sender_transaction, recipient_transaction])
            
            # Send success message
            embed = discord.Embed(
                title="✅ Transfer Complete",
                description=f"Successfully sent {format_currency(amount)} to {recipient.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Your New Balance", value=format_currency(sender.balance), inline=False)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        """Display the richest users"""
        
        with get_session() as session:
            # Get top 10 users by balance
            top_users = session.execute(
                select(User.discord_id, User.username, User.balance)
                .order_by(User.balance.desc())
                .limit(10)
            ).all()
            
            if not top_users:
                await ctx.send("No users found in the leaderboard.")
                return
            
            # Create embed for leaderboard
            embed = discord.Embed(
                title="💰 Richest Users Leaderboard",
                color=discord.Color.gold()
            )
            
            for i, (discord_id, username, balance) in enumerate(top_users, 1):
                user_display = f"{'🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f'{i}.'} "
                user_display += f"**{username}**: {format_currency(balance)}"
                embed.add_field(name=f"#{i}", value=user_display, inline=False)
            
            embed.set_footer(text=f"Requested by {ctx.author.name}")
            
            await ctx.send(embed=embed)
    
    @commands.command(name="transactions", aliases=["history", "tx"])
    async def transactions(self, ctx, limit: int = 5):
        """View your recent transactions"""
        
        # Limit the number of transactions to a reasonable range
        if limit < 1:
            limit = 1
        elif limit > 10:
            limit = 10
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Get user's recent transactions
            transactions = session.execute(
                select(Transaction.amount, Transaction.transaction_type, Transaction.description, Transaction.timestamp)
                .where(Transaction.user_id == user.id)
                .order_by(Transaction.timestamp.desc())
                .limit(limit)
            ).all()
            
            if not transactions:
                await ctx.send("You don't have any transactions yet.")
                return
            
            # Create embed for transactions
            embed = discord.Embed(
                title="📜 Your Recent Transactions",
                color=discord.Color.blue()
            )
            
            for amount, tx_type, description, timestamp in transactions:
                # Format timestamp
                formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                # Determine emoji based on transaction type
                emoji = "💸" if amount < 0 else "💰"
                if tx_type == TransactionType.MINING.value:
                    emoji = "⛏️"
                elif tx_type == TransactionType.DAILY.value:
                    emoji = "🎁"
                
                # Format amount with +/- sign
                formatted_amount = format_currency(amount)
                if amount > 0 and tx_type != TransactionType.DEPOSIT.value:
                    formatted_amount = f"+{formatted_amount}"
                
                embed.add_field(
                    name=f"{emoji} {tx_type.capitalize()} - {formatted_time}",
                    value=f"{formatted_amount}\n{description or 'No description'}",
                    inline=False
                )
            
            embed.set_footer(text=f"Current Balance: {format_currency(user.balance)}")
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))

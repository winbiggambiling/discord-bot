import discord
from discord.ext import commands
from database.database import get_session
from database.models import User, Transaction, GameSession, TransactionType, GameType, BotStatistics
from sqlalchemy import select, func
import random
import json
import asyncio
import logging

# Configure logging
logger = logging.getLogger('gambling')

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.formatters import format_currency
from utils.helpers import create_user_if_not_exists

class Gambling(commands.Cog):
    """Gambling commands for the gambling bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process_game(self, ctx, user, game_type, bet_amount, win, payout_amount, game_result):
        """Process a game outcome, updating user balance and recording transactions"""
        
        with get_session() as session:
            # Get fresh user data
            db_user = session.scalar(select(User).where(User.id == user.id))
            
            if win:
                # User won, add winnings
                transaction_type = TransactionType.WIN.value
                transaction_desc = f"Won {game_type.value} game"
                db_user.balance += payout_amount
            else:
                # User lost, bet amount already deducted
                transaction_type = TransactionType.BET.value
                transaction_desc = f"Lost {game_type.value} game"
            
            # Record transaction
            transaction = Transaction(
                user_id=db_user.id,
                amount=payout_amount if win else -bet_amount,
                transaction_type=transaction_type,
                description=transaction_desc
            )
            session.add(transaction)
            
            # Record game session
            game_session = GameSession(
                user_id=db_user.id,
                game_type=game_type.value,
                bet_amount=bet_amount,
                payout=payout_amount if win else 0,
                game_result=json.dumps(game_result)
            )
            session.add(game_session)
            
            # Update bot statistics
            bot_stats = session.execute(
                select(BotStatistics).limit(1)
            ).scalar_one_or_none()
            
            if not bot_stats:
                # Create stats record if it doesn't exist
                bot_stats = BotStatistics()
                session.add(bot_stats)
            
            bot_stats.total_bets += 1
            bot_stats.total_bet_amount += bet_amount
            bot_stats.total_payout_amount += payout_amount if win else 0
            
            session.commit()
            
            # Return the updated user balance
            return db_user.balance
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    async def coinflip(self, ctx, choice: str, bet: float):
        """
        Flip a coin and bet on the outcome.
        Usage: !coinflip <heads|tails> <bet amount>
        """
        
        # Validate inputs
        choice = choice.lower()
        if choice not in ["heads", "tails", "h", "t"]:
            await ctx.send("❌ Please choose either 'heads' or 'tails'!")
            return
        
        if choice in ["h", "t"]:
            choice = "heads" if choice == "h" else "tails"
            
        if bet <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user has enough balance
            if user.balance < bet:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You don't have enough funds to bet {format_currency(bet)}.\nYour balance: {format_currency(user.balance)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Deduct bet amount
            user.balance -= bet
            
            # Flip the coin
            result = random.choice(["heads", "tails"])
            win = (result == choice)
            
            # Calculate payout
            payout = bet * config.COINFLIP_MULTIPLIER if win else 0
            
            # Create game result data
            game_result = {
                "choice": choice,
                "result": result,
                "win": win
            }
            
            # Update database and get new balance
            new_balance = await self.process_game(
                ctx, user, GameType.COINFLIP, bet, win, payout, game_result
            )
            
            # Create the message embed
            embed = discord.Embed(
                title=f"Coin Flip: {result.capitalize()}"
            )
            
            # Set color and message based on win/loss
            if win:
                embed.color = discord.Color.green()
                embed.description = f"🎉 You chose **{choice}** and the coin landed on **{result}**. You win {format_currency(payout)}!"
            else:
                embed.color = discord.Color.red()
                embed.description = f"😢 You chose **{choice}** and the coin landed on **{result}**. You lose {format_currency(bet)}!"
            
            embed.add_field(name="New Balance", value=format_currency(new_balance), inline=False)
            await ctx.send(embed=embed)
    
    @commands.command(name="dice", aliases=["roll"])
    async def dice(self, ctx, bet: float, choice: int = None):
        """
        Roll a dice and win if you guess the number correctly.
        If no number is provided, you win on rolls of 4, 5, or 6.
        Usage: !dice <bet amount> [1-6]
        """
        
        # Validate inputs
        if bet <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return
        
        if choice is not None and (choice < 1 or choice > 6):
            await ctx.send("❌ Dice choice must be between 1 and 6!")
            return
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user has enough balance
            if user.balance < bet:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You don't have enough funds to bet {format_currency(bet)}.\nYour balance: {format_currency(user.balance)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Deduct bet amount
            user.balance -= bet
            
            # Roll the dice
            result = random.randint(1, 6)
            
            # Determine if user won
            if choice is None:
                # Win on 4, 5, or 6 (50% chance to win)
                win = result >= 4
                multiplier = config.DICE_DEFAULT_MULTIPLIER
            else:
                # Win if number matches (1/6 chance to win)
                win = (result == choice)
                multiplier = config.DICE_SPECIFIC_MULTIPLIER
            
            # Calculate payout
            payout = bet * multiplier if win else 0
            
            # Create game result data
            game_result = {
                "choice": choice,
                "result": result,
                "win": win
            }
            
            # Update database and get new balance
            new_balance = await self.process_game(
                ctx, user, GameType.DICE, bet, win, payout, game_result
            )
            
            # Create initial message for suspense
            message = await ctx.send("🎲 Rolling the dice...")
            await asyncio.sleep(1)
            
            # Create the result embed
            embed = discord.Embed(
                title=f"Dice Roll: {result}"
            )
            
            # Set color and message based on win/loss
            if win:
                embed.color = discord.Color.green()
                if choice is None:
                    embed.description = f"🎉 The dice landed on **{result}** (>= 4). You win {format_currency(payout)}!"
                else:
                    embed.description = f"🎉 The dice landed on **{result}** (your guess). You win {format_currency(payout)}!"
            else:
                embed.color = discord.Color.red()
                if choice is None:
                    embed.description = f"😢 The dice landed on **{result}** (< 4). You lose {format_currency(bet)}!"
                else:
                    embed.description = f"😢 The dice landed on **{result}** (you guessed {choice}). You lose {format_currency(bet)}!"
            
            embed.add_field(name="New Balance", value=format_currency(new_balance), inline=False)
            await message.edit(embed=embed)
    
    @commands.command(name="slots", aliases=["slot", "slotmachine"])
    async def slots(self, ctx, bet: float):
        """
        Play a slot machine game.
        Usage: !slots <bet amount>
        """
        
        # Validate bet amount
        if bet <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user has enough balance
            if user.balance < bet:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You don't have enough funds to bet {format_currency(bet)}.\nYour balance: {format_currency(user.balance)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Deduct bet amount
            user.balance -= bet
            
            # Define slot symbols and their weights
            symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "💎", "7️⃣"]
            weights = [30, 25, 20, 15, 10, 5, 2]  # Higher = more likely
            
            # Spin the slots
            slots = []
            for _ in range(3):
                slots.append(random.choices(symbols, weights=weights, k=1)[0])
            
            # Determine win
            if slots[0] == slots[1] == slots[2]:
                # All three match
                if slots[0] == "7️⃣":
                    # Jackpot
                    win = True
                    multiplier = config.SLOTS_JACKPOT_MULTIPLIER
                    win_type = "JACKPOT"
                elif slots[0] == "💎":
                    # Diamond line
                    win = True
                    multiplier = config.SLOTS_DIAMOND_MULTIPLIER
                    win_type = "DIAMOND LINE"
                else:
                    # Regular match
                    win = True
                    multiplier = config.SLOTS_MATCH_MULTIPLIER
                    win_type = "THREE OF A KIND"
            elif slots.count("🍒") >= 2:
                # Two or more cherries
                win = True
                multiplier = config.SLOTS_CHERRY_MULTIPLIER
                win_type = "TWO+ CHERRIES"
            else:
                # No win
                win = False
                multiplier = 0
                win_type = "NO MATCH"
            
            # Calculate payout
            payout = bet * multiplier if win else 0
            
            # Create game result data
            game_result = {
                "slots": slots,
                "win_type": win_type,
                "win": win
            }
            
            # Update database and get new balance
            new_balance = await self.process_game(
                ctx, user, GameType.SLOTS, bet, win, payout, game_result
            )
            
            # Create the initial message for suspense
            message = await ctx.send("🎰 Spinning the slots...")
            await asyncio.sleep(1.5)
            
            # Create the result embed
            embed = discord.Embed(
                title="🎰 Slots Result",
                description=f"**{ctx.author.name}** bet {format_currency(bet)}"
            )
            
            # Display the slots
            slots_display = "".join(slots)
            embed.add_field(name="Result", value=slots_display, inline=False)
            
            # Set color and message based on win/loss
            if win:
                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"🎉 {win_type}!",
                    value=f"You won {format_currency(payout)}!",
                    inline=False
                )
            else:
                embed.color = discord.Color.red()
                embed.add_field(
                    name="😢 No Match",
                    value=f"You lost {format_currency(bet)}!",
                    inline=False
                )
            
            embed.add_field(name="New Balance", value=format_currency(new_balance), inline=False)
            
            await message.edit(embed=embed)
    
    @commands.command(name="roulette", aliases=["roul"])
    async def roulette(self, ctx, bet_type: str, bet: float):
        """
        Play roulette. Bet types: red, black, even, odd, high, low
        Usage: !roulette <bet_type> <bet amount>
        """
        
        # Validate bet amount
        if bet <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return
        
        # Validate bet type
        bet_type = bet_type.lower()
        valid_bet_types = {
            "red": "color", "black": "color",
            "even": "parity", "odd": "parity",
            "high": "range", "low": "range"
        }
        
        if bet_type not in valid_bet_types:
            await ctx.send("❌ Invalid bet type! Choose from: red, black, even, odd, high, low")
            return
        
        with get_session() as session:
            user = create_user_if_not_exists(session, ctx.author)
            
            # Check if user has enough balance
            if user.balance < bet:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You don't have enough funds to bet {format_currency(bet)}.\nYour balance: {format_currency(user.balance)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Deduct bet amount
            user.balance -= bet
            
            # Spin the roulette
            number = random.randint(0, 36)
            
            # Define roulette properties
            red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
            black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
            
            # Determine result properties
            color = "red" if number in red_numbers else "black" if number in black_numbers else "green"
            parity = "even" if number % 2 == 0 and number != 0 else "odd" if number != 0 else "zero"
            range_type = "high" if 19 <= number <= 36 else "low" if 1 <= number <= 18 else "zero"
            
            # Determine win
            if number == 0:
                # Zero is always a loss (house edge)
                win = False
            elif valid_bet_types[bet_type] == "color":
                win = (bet_type == color)
            elif valid_bet_types[bet_type] == "parity":
                win = (bet_type == parity)
            else:  # range
                win = (bet_type == range_type)
            
            # Calculate payout
            multiplier = config.ROULETTE_MULTIPLIER if win else 0
            payout = bet * multiplier if win else 0
            
            # Create game result data
            game_result = {
                "bet_type": bet_type,
                "number": number,
                "color": color,
                "parity": parity,
                "range": range_type,
                "win": win
            }
            
            # Update database and get new balance
            new_balance = await self.process_game(
                ctx, user, GameType.ROULETTE, bet, win, payout, game_result
            )
            
            # Create the initial message for suspense
            message = await ctx.send("🎡 Spinning the roulette wheel...")
            await asyncio.sleep(1.5)
            
            # Create the result embed
            embed = discord.Embed(
                title=f"🎡 Roulette: {number} {color.capitalize()}",
                description=f"**{ctx.author.name}** bet {format_currency(bet)} on {bet_type}"
            )
            
            # Set properties based on the number
            if color == "red":
                embed.color = discord.Color.red()
            elif color == "black":
                embed.color = discord.Color.darker_grey()
            else:  # green
                embed.color = discord.Color.green()
            
            # Add result info
            embed.add_field(name="Number", value=str(number), inline=True)
            embed.add_field(name="Color", value=color.capitalize(), inline=True)
            embed.add_field(name="Parity", value=parity.capitalize(), inline=True)
            embed.add_field(name="Range", value=range_type.capitalize() if range_type != "zero" else "Zero", inline=True)
            
            # Set win/loss message
            if win:
                embed.add_field(
                    name="🎉 You Won!",
                    value=f"You bet on {bet_type} and won {format_currency(payout)}!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="😢 You Lost",
                    value=f"You bet on {bet_type} and lost {format_currency(bet)}!",
                    inline=False
                )
            
            embed.add_field(name="New Balance", value=format_currency(new_balance), inline=False)
            
            await message.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(Gambling(bot))
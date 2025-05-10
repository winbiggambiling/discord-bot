import discord
from discord.ext import commands
from database.database import get_session
from database.models import User, Transaction, GameSession, TransactionType, GameType
from sqlalchemy import select
import os
import sys
import random
import json
import asyncio
import logging

# Add the parent directory to the path to find the config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.formatters import format_currency
from utils.helpers import create_user_if_not_exists

# Configure logging
logger = logging.getLogger('extended_slots')

# Define constants for slot symbols
SLOT_WILD = "🃏"      # Wild symbol (substitutes for any symbol except scatter)
SLOT_SCATTER = "🌟"   # Scatter symbol (triggers free spins)
SLOT_JACKPOT = "7️⃣"   # Jackpot symbol

class ExtendedSlots(commands.Cog):
    """Extended slot machine with bonus features"""
    
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
            from database.models import BotStatistics
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
            
            # Return the updated user balance
            return db_user.balance
    
    @commands.command(name="bigslots", aliases=["bslots", "extendedslots"])
    async def slots_extended(self, ctx, bet: float):
        """
        Play the extended slot machine with wild symbols, scatters, free spins, and bigger jackpots!
        Usage: !bigslots <bet amount>
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
            # New improved symbols for the extended slots
            symbols = [
                "🍒", "🍋", "🍊", "🍇", "🍉",      # Common symbols (x5)
                "💎", "7️⃣",                      # Valuable symbols (x2)
                "🎰", "💰",                      # High value symbols (x2)
                "🃏", "🌟"                       # Special symbols - Wild and Scatter (x2)
            ]
            
            # Symbol weights (higher = more common)
            # Wild (🃏) and Scatter (🌟) have the lowest weights
            weights = [20, 20, 18, 18, 15, 10, 8, 5, 5, 3, 3]
            
            # Configure number of reels and rows (3x5 grid)
            rows = 3
            reels = 5
            
            # Create the grid
            grid = []
            for _ in range(rows):
                row_symbols = []
                for _ in range(reels):
                    row_symbols.append(random.choices(symbols, weights=weights, k=1)[0])
                grid.append(row_symbols)
                
            # Check for special features
            free_spins = 0
            has_bonus_round = False
            scatter_count = 0
            multiplier = 1.0
            
            # Count scatters (anywhere on grid)
            for row in grid:
                scatter_count += row.count(SLOT_SCATTER)
            
            # Award free spins based on scatter count
            if scatter_count >= 3:
                free_spins = scatter_count * 2
                multiplier += 0.5
            
            # Display initial grid with suspense
            embed = discord.Embed(
                title="🎰 Enhanced Slots",
                description=f"**{ctx.author.name}** bet {format_currency(bet)}",
                color=discord.Color.gold()
            )
            
            # Format the grid for display
            grid_display = ""
            for row in grid:
                grid_display += "".join(row) + "\n"
                
            embed.add_field(name="Result", value=grid_display, inline=False)
            
            # Calculate winnings based on paylines
            win = False
            win_lines = []
            total_payout = 0
            
            # Define the paylines:
            paylines = [
                # Horizontal lines
                [(0,0), (0,1), (0,2), (0,3), (0,4)],  # Top row
                [(1,0), (1,1), (1,2), (1,3), (1,4)],  # Middle row
                [(2,0), (2,1), (2,2), (2,3), (2,4)],  # Bottom row
                
                # V-shapes and zig-zags
                [(0,0), (1,1), (2,2), (1,3), (0,4)],  # V shape
                [(2,0), (1,1), (0,2), (1,3), (2,4)],  # Inverted V shape
                
                # Diagonal lines
                [(0,0), (0,1), (1,2), (2,3), (2,4)],  # Diagonal 1
                [(2,0), (2,1), (1,2), (0,3), (0,4)]   # Diagonal 2
            ]
            
            # Check each payline
            for line_idx, line in enumerate(paylines):
                line_symbols = []
                
                # Get symbols for this line
                for row, col in line:
                    if row < len(grid) and col < len(grid[0]):
                        line_symbols.append(grid[row][col])
                
                # Process payline, considering wild symbols
                processed_line = []
                for symbol in line_symbols:
                    # Wild symbols can substitute for anything except scatters
                    processed_line.append(symbol)
                
                # Count unique symbols, treating wilds as matching the most beneficial symbol
                unique_symbols = set(processed_line)
                if SLOT_WILD in unique_symbols and len(unique_symbols) > 1:
                    # Remove wild from consideration of unique symbols
                    unique_symbols.remove(SLOT_WILD)
                
                # Count symbols that are the same (accounting for wilds)
                symbol_counts = {}
                for symbol in unique_symbols:
                    if symbol != SLOT_SCATTER:  # Scatters don't count in paylines
                        count = processed_line.count(symbol) + processed_line.count(SLOT_WILD)
                        symbol_counts[symbol] = count
                
                # Find the best matching symbol
                best_symbol = None
                max_count = 0
                
                for symbol, count in symbol_counts.items():
                    if count > max_count:
                        max_count = count
                        best_symbol = symbol
                
                # Calculate win amount based on matches
                payline_win = 0
                win_description = ""
                
                if max_count >= 3:  # Need at least 3 in a row to win
                    win = True
                    
                    if best_symbol == SLOT_JACKPOT and max_count == 5:
                        # Mega jackpot - five 7's in a row
                        payline_win = bet * config.SLOTS_EXT_MULTIPLIER_MEGA_JACKPOT
                        win_description = "MEGA JACKPOT! 🎊🎊🎊"
                    elif best_symbol == SLOT_JACKPOT and max_count >= 3:
                        # Regular jackpot - at least three 7's
                        payline_win = bet * config.SLOTS_EXT_MULTIPLIER_JACKPOT * (max_count - 2)
                        win_description = "JACKPOT! 🎊🎊"
                    elif max_count == 5:
                        # Five of a kind
                        payline_win = bet * config.SLOTS_EXT_MULTIPLIER_BIG_WIN
                        win_description = "BIG WIN! 🎉🎉🎉"
                    elif max_count == 4:
                        # Four of a kind
                        payline_win = bet * config.SLOTS_EXT_MULTIPLIER_BONUS
                        win_description = "BONUS WIN! 🎉🎉"
                    elif max_count == 3:
                        # Three of a kind
                        payline_win = bet * 3.0
                        win_description = "Three of a kind! 🎉"
                    
                    # Apply wild multiplier if any wild symbols are part of the win
                    if processed_line.count(SLOT_WILD) > 0:
                        wild_multiplier = 1.0 + (processed_line.count(SLOT_WILD) * 0.5)
                        payline_win *= wild_multiplier
                        win_description += f" (Wild ×{wild_multiplier})"
                    
                    # Track the winning line
                    win_lines.append({
                        "line": line_idx + 1,
                        "symbols": processed_line,
                        "payout": payline_win,
                        "description": win_description
                    })
                    
                    # Add to total payout
                    total_payout += payline_win
            
            # Apply free spins multiplier if awarded
            if free_spins > 0:
                old_payout = total_payout
                total_payout *= multiplier
                embed.add_field(
                    name="🎡 FREE SPINS!",
                    value=f"You won {free_spins} free spins!\nPayout multiplier: ×{multiplier}",
                    inline=False
                )
            
            # Process free spins (add a fixed amount per free spin)
            if free_spins > 0:
                free_spin_value = bet * 0.5
                free_spin_payout = free_spins * free_spin_value
                total_payout += free_spin_payout
                embed.add_field(
                    name="Free Spin Value",
                    value=f"{free_spins} spins × {format_currency(free_spin_value)} = {format_currency(free_spin_payout)}",
                    inline=False
                )
            
            # Create game result data for recording
            game_result = {
                "grid": grid,
                "win_lines": win_lines,
                "scatter_count": scatter_count,
                "free_spins": free_spins,
                "multiplier": multiplier,
                "win": win
            }
            
            # Update database and get new balance
            payout_amount = total_payout
            new_balance = await self.process_game(
                ctx, user, GameType.SLOTS_EXTENDED, bet, win, payout_amount, game_result
            )
            
            # Update the embed with result information
            if win:
                embed.color = discord.Color.green()
                
                # Add winning lines information
                for win_info in win_lines:
                    embed.add_field(
                        name=f"Line {win_info['line']} Win",
                        value=f"{win_info['description']}\nPaid: {format_currency(win_info['payout'])}",
                        inline=True
                    )
                
                embed.add_field(
                    name="Total Payout",
                    value=f"You won {format_currency(total_payout)}! 🎉",
                    inline=False
                )
            else:
                embed.color = discord.Color.red()
                embed.add_field(
                    name="No Win",
                    value=f"You lost {format_currency(bet)}! 😢",
                    inline=False
                )
            
            embed.add_field(
                name="New Balance",
                value=format_currency(new_balance),
                inline=False
            )
            
            # Add legend for special symbols
            embed.add_field(
                name="Symbol Guide",
                value=f"{SLOT_WILD} Wild: Substitutes for any symbol except scatter\n"
                      f"{SLOT_SCATTER} Scatter: 3+ awards free spins\n"
                      f"{SLOT_JACKPOT} Jackpot: Highest value symbol",
                inline=False
            )
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ExtendedSlots(bot))
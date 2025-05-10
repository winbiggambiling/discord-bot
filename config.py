"""
Configuration settings for the gambling bot.
"""

# Bot configuration
COMMAND_PREFIX = "!"

# Economy settings
DAILY_REWARD_BASE = 100
DAILY_REWARD_BONUS = 50  # Random bonus up to this amount

# Game multipliers
COINFLIP_MULTIPLIER = 1.9  # Win 1.9x your bet on coinflip

# Dice game multipliers
DICE_DEFAULT_MULTIPLIER = 1.8  # Win on 4-6 (no choice)
DICE_SPECIFIC_MULTIPLIER = 5.0  # Win on exact number

# Slots game multipliers
SLOTS_JACKPOT_MULTIPLIER = 50.0  # Jackpot (three 7s)
SLOTS_DIAMOND_MULTIPLIER = 10.0  # Three diamonds
SLOTS_MATCH_MULTIPLIER = 5.0     # Three of a kind (any other symbol)
SLOTS_CHERRY_MULTIPLIER = 2.0    # Two or more cherry symbols

# Extended slots game multipliers and features
SLOTS_EXT_MULTIPLIER_MEGA_JACKPOT = 100.0  # Mega jackpot (special combination)
SLOTS_EXT_MULTIPLIER_JACKPOT = 50.0        # Regular jackpot
SLOTS_EXT_MULTIPLIER_BIG_WIN = 25.0        # Big win
SLOTS_EXT_MULTIPLIER_BONUS = 15.0          # Bonus round
SLOTS_EXT_MULTIPLIER_FREE_SPINS = 5.0      # Free spins feature
SLOTS_EXT_MULTIPLIER_WILD = 3.0            # Wild symbol multiplier
SLOTS_EXT_MULTIPLIER_SCATTER = 2.0         # Each scatter symbol

# Roulette multipliers - for simplicity, all bet types have the same multiplier
ROULETTE_MULTIPLIER = 1.9  # Win 1.9x your bet on any bet type

# Mining settings
MINING_COOLDOWN = 300  # 5 minutes cooldown between mining sessions
MINING_BASE_UPGRADE_COST = 500  # Base cost to upgrade mining equipment
MINING_UPGRADE_COST_MULTIPLIER = 1.5  # Cost multiplier for each level
MINING_POWER_INCREASE = 0.5  # Amount mining power increases per level

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import datetime

# Base class for all models
Base = declarative_base()

# Enum for transaction types
class TransactionType(enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BET = "bet"
    WIN = "win"
    MINING = "mining"
    DAILY = "daily"
    ADMIN = "admin"

# Enum for game types
class GameType(enum.Enum):
    COINFLIP = "coinflip"
    DICE = "dice"
    SLOTS = "slots"
    SLOTS_EXTENDED = "slots_extended"
    BLACKJACK = "blackjack"
    ROULETTE = "roulette"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(20), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    last_daily = Column(DateTime, nullable=True)
    mining_level = Column(Integer, default=1, nullable=False)
    mining_power = Column(Float, default=1.0, nullable=False)
    mining_multiplier = Column(Float, default=1.0, nullable=False)
    mining_last_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    game_sessions = relationship("GameSession", back_populates="user")
    
    def __repr__(self):
        return f"<User discord_id={self.discord_id} username='{self.username}' balance={self.balance}>"

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(20), nullable=False)
    description = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction id={self.id} user_id={self.user_id} amount={self.amount} type='{self.transaction_type}'>"

class GameSession(Base):
    __tablename__ = 'game_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    game_type = Column(String(20), nullable=False)
    bet_amount = Column(Float, nullable=False)
    payout = Column(Float, nullable=False)
    game_result = Column(Text, nullable=True)  # JSON string of game result details
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="game_sessions")
    
    def __repr__(self):
        return f"<GameSession id={self.id} user_id={self.user_id} game_type='{self.game_type}' bet={self.bet_amount} payout={self.payout}>"

class MiningStats(Base):
    __tablename__ = 'mining_stats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    mining_duration = Column(Integer, nullable=False)  # Duration in seconds
    amount_earned = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<MiningStats id={self.id} user_id={self.user_id} duration={self.mining_duration} earned={self.amount_earned}>"

class BotStatistics(Base):
    __tablename__ = 'bot_statistics'
    
    id = Column(Integer, primary_key=True)
    commands_used = Column(Integer, default=0, nullable=False)
    total_bets = Column(Integer, default=0, nullable=False)
    total_bet_amount = Column(Float, default=0.0, nullable=False)
    total_payout_amount = Column(Float, default=0.0, nullable=False)
    total_mined = Column(Float, default=0.0, nullable=False)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<BotStatistics commands={self.commands_used} bets={self.total_bets}>"

import os
import logging
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import threading
import asyncio
from sqlalchemy import select, func
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET")

# Import database models after initializing app
from database.database import get_engine, get_session
from database.models import User, Transaction, GameSession

# Create tables if they don't exist
engine = get_engine()
from database.models import Base
Base.metadata.create_all(engine)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "bot": "Discord Gambling Bot",
        "features": [
            "Economy System", 
            "Gambling Games", 
            "Mining System"
        ]
    })

@app.route('/api/stats')
def stats():
    with get_session() as session:
        # Count total users
        user_count = session.scalar(select(func.count()).select_from(User))
        
        # Get top 5 richest users
        rich_users = session.execute(
            select(User.username, User.balance)
            .order_by(User.balance.desc())
            .limit(5)
        ).all()
        
        # Get recent transactions
        recent_transactions = session.execute(
            select(
                Transaction.id,
                Transaction.user_id,
                User.username,
                Transaction.amount,
                Transaction.transaction_type,
                Transaction.timestamp
            )
            .join(User)
            .order_by(Transaction.timestamp.desc())
            .limit(10)
        ).all()
        
        # Get total currency in circulation
        total_currency = session.scalar(select(func.sum(User.balance)).select_from(User)) or 0
        
        # Get recent game sessions
        recent_games = session.execute(
            select(
                GameSession.id,
                GameSession.user_id,
                User.username,
                GameSession.game_type,
                GameSession.bet_amount,
                GameSession.payout,
                GameSession.timestamp
            )
            .join(User)
            .order_by(GameSession.timestamp.desc())
            .limit(10)
        ).all()
        
        return jsonify({
            "user_count": user_count,
            "total_currency": total_currency,
            "top_users": [{"username": username, "balance": balance} for username, balance in rich_users],
            "recent_transactions": [
                {
                    "id": id,
                    "user_id": user_id,
                    "username": username,
                    "amount": amount,
                    "type": transaction_type,
                    "timestamp": timestamp.isoformat()
                } for id, user_id, username, amount, transaction_type, timestamp in recent_transactions
            ],
            "recent_games": [
                {
                    "id": id,
                    "user_id": user_id,
                    "username": username,
                    "game_type": game_type,
                    "bet_amount": bet_amount,
                    "payout": payout,
                    "timestamp": timestamp.isoformat()
                } for id, user_id, username, game_type, bet_amount, payout, timestamp in recent_games
            ]
        })

# Set up a function to start the Discord bot in a separate thread
def start_bot():
    from bot import setup_bot
    import asyncio
    
    async def run_bot():
        # Get token from environment variables
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            logging.error("No Discord bot token found. Set the DISCORD_BOT_TOKEN environment variable.")
            return
            
        try:
            bot = await setup_bot()
            await bot.start(TOKEN)
        except Exception as e:
            logging.error(f"Error starting bot: {e}")
        finally:
            logging.info("Bot has been shut down.")
    
    # Use asyncio to run the bot
    asyncio.run(run_bot())

# Start the bot in a separate thread when this file is imported by gunicorn
if os.environ.get('RUNNING_IN_GUNICORN') != 'true':
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    logging.info("Bot starting in separate thread")

if __name__ == "__main__":
    # If running this file directly (not through gunicorn)
    app.run(host="0.0.0.0", port=5000, debug=True)

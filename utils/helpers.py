"""
Utility helper functions for the gambling bot.
"""
from database.models import User
from sqlalchemy import select

def create_user_if_not_exists(session, discord_user):
    """
    Get a user from the database or create a new one if they don't exist.
    
    Args:
        session: SQLAlchemy session
        discord_user: Discord user object
        
    Returns:
        User: The database user object
    """
    # Try to get the user by Discord ID
    discord_id = str(discord_user.id)
    
    user = session.scalar(
        select(User).where(User.discord_id == discord_id)
    )
    
    if not user:
        # Create a new user if they don't exist
        user = User(
            discord_id=discord_id,
            username=f"{discord_user.name}#{discord_user.discriminator}" if hasattr(discord_user, 'discriminator') and discord_user.discriminator != '0' else discord_user.name,
            balance=100.0  # Starting balance
        )
        session.add(user)
        session.flush()  # Make sure the user has an ID assigned
    
    return user

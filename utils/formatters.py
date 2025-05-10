"""
Utility functions for formatting various data types.
"""

def format_currency(amount):
    """
    Format a currency amount with the $ symbol.
    
    Args:
        amount (float): The amount to format
        
    Returns:
        str: The formatted amount string
    """
    return f"${amount:,.2f}"

def format_time(seconds):
    """
    Format a time duration in seconds to a human-readable string.
    
    Args:
        seconds (float): The time in seconds
        
    Returns:
        str: The formatted time string (e.g., "2h 30m 15s")
    """
    seconds = int(seconds)
    
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    
    if hours > 0:
        parts.append(f"{hours}h")
    
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

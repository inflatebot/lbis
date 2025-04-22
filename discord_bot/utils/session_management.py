import asyncio
import logging
from discord.ext import commands

logger = logging.getLogger(__name__)

# --- Session Time Management ---

def update_session_time(bot: commands.Bot, delta_seconds: int):
    """Updates the session time remaining, ensuring it stays within bounds."""
    # We don't apply max_session_time cap here directly.
    # Commands adding time (/add_time) should enforce the cap.
    # This function just handles decrementing or applying changes from pump runs.
    new_time = bot.session_time_remaining + delta_seconds

    # Prevent session time from going below zero
    bot.session_time_remaining = max(0, new_time)

    # Log the change
    if delta_seconds != 0:
        logger.debug(f"Session time updated by {delta_seconds}s. New time: {bot.session_time_remaining}s")

    # Note: State saving is handled by the calling function (e.g., end of pump loop)

def start_pump_timer(bot):
    """Start tracking pump run time"""
    bot.session_pump_start = asyncio.get_event_loop().time()

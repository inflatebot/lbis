import asyncio
import json
import discord
from discord.ext import commands
import functools
import os
import logging
import time
import aiohttp
from state_manager import StateManager  # Import the new manager

# --- Constants ---
_utils_dir = os.path.dirname(os.path.abspath(__file__))  # Get directory of utils.py
SESSION_FILE = os.path.join(_utils_dir, "session.json")  # Path relative to utils.py
logger = logging.getLogger(__name__)

# --- Time Formatting ---

def format_time(seconds: int) -> str:
    """Formats seconds into a human-readable string (e.g., 1h 5m 30s)."""
    if seconds < 0:
        seconds = 0  # Or handle negative display if needed
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    if s > 0 or not parts:  # Show seconds if it's non-zero or if hours/minutes are zero
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"

# --- Configuration & State Persistence ---

def save_wearer_id(bot, wearer_id):
    bot.config['wearer_id'] = wearer_id
    with open('bot.json', 'w') as config_file:
        json.dump(bot.config, config_file, indent=4)
    bot.OWNER_ID = wearer_id  # Update runtime state

def save_session_state(bot):
    """Updates the state manager with the bot's current state and saves it."""
    if hasattr(bot, 'state_manager') and bot.state_manager:
        bot.state_manager.update_and_save(bot)
    else:
        logger.error("Attempted to save state, but state_manager is not initialized.")

def load_session_state(bot):
    """Initializes the StateManager and applies the loaded state to the bot."""
    default_initial_time = bot.config.get('max_session_time', 1800)
    # Create the state manager instance for the bot
    bot.state_manager = StateManager(file_path=SESSION_FILE, default_initial_time=default_initial_time)
    # Apply the loaded state from the manager to the bot instance
    bot.state_manager.apply_to_bot(bot)

    # Initialize runtime-only attributes that are not persisted
    # Ensure these are always present after loading state
    if not hasattr(bot, 'latch_timer'):
        bot.latch_timer = None
    if not hasattr(bot, 'ready_note'):
        bot.ready_note = None
    if not hasattr(bot, 'pump_task'):
        bot.pump_task = None
    if not hasattr(bot, 'pump_task_end_time'):
        bot.pump_task_end_time = None
    # session_pump_start is technically persisted but needs careful handling
    # If the bot restarts mid-pump, session_pump_start might be stale.
    # Consider resetting it or validating it on load if necessary.
    # For now, we load it via apply_to_bot.

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

# --- Latch Management ---

async def auto_unlatch(bot, delay):
    """Automatically unlatch after specified delay"""
    await asyncio.sleep(delay)
    if bot.latch_timer:  # Check if it wasn't cancelled
        bot.latch_active = False
        bot.latch_timer = None
        bot.latch_end_time = None
        bot.latch_reason = None  # Clear reason on auto-unlatch
        save_session_state(bot)
        print("Timed latch expired.")
        if bot.OWNER_ID:
            try:
                wearer = await bot.fetch_user(bot.OWNER_ID)
                await wearer.send("Timed latch has expired - pump is now unlatched.")
                # Trigger status update after state change
                monitor_cog = bot.get_cog('MonitorCog')
                if monitor_cog:
                    await monitor_cog.update_bot_status()
            except Exception as e:
                print(f"Failed to notify wearer of auto-unlatch: {e}")

# --- Permissions & Notifications ---

def is_wearer(interaction: discord.Interaction) -> bool:
    # Assumes OWNER_ID is attached to the bot object
    return interaction.user.id == interaction.client.OWNER_ID

async def notify_wearer(bot, interaction: discord.Interaction, command_name: str):
    if not bot.OWNER_ID or interaction.user.id == bot.OWNER_ID:
        return  # Don't notify if no owner set or if owner uses command

    try:
        wearer = await bot.fetch_user(bot.OWNER_ID)
        if wearer:
            location = "Direct Messages" if interaction.guild is None else f"{interaction.guild.name} / #{interaction.channel.name}"
            user_info = f"{interaction.user} ({interaction.user.id})"

            # Get command parameters
            params = []
            if interaction.data and "options" in interaction.data:
                for option in interaction.data.get("options", []):
                    params.append(f"{option['name']}:{option['value']}")
            param_str = " " + " ".join(params) if params else ""

            await wearer.send(
                f"Command `{command_name}{param_str}` used by {user_info} in {location}."
            )
    except Exception as e:
        print(f"Failed to notify wearer: {e}")

def dm_wearer_on_use(command_name):
    """Decorator to notify the wearer when a command is used."""
    def decorator(func):
        # Ensure the decorated function is recognized as a command callback
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Decorated function must be a coroutine.")

        @functools.wraps(func)
        async def wrapper(cog_instance, interaction: discord.Interaction, *args, **kwargs):
            # Pass 'cog_instance.bot' instead of just 'bot'
            await notify_wearer(cog_instance.bot, interaction, command_name)
            # Call the original command function
            return await func(cog_instance, interaction, *args, **kwargs)
        return wrapper
    return decorator

# --- API Interaction ---

async def api_request(bot, endpoint: str, method: str = "GET", data: dict = None, timeout: int = 5) -> dict | None:
    """
    Make a request to the lBIS API.
    
    Args:
        bot: The bot instance containing API_BASE_URL
        endpoint: API endpoint (without leading slash)
        method: HTTP method (GET/POST)
        data: Optional data to send with request
        timeout: Request timeout in seconds
        
    Returns:
        Response data as dict if successful and response has data
        None if request failed or had no data
    """
    url = f"{bot.API_BASE_URL}/api/{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {
                'timeout': timeout
            }
            if data:
                kwargs['json'] = data
            
            async with getattr(session, method.lower())(url, **kwargs) as resp:
                if resp.status != 200:
                    logger.warning(f"API request to {endpoint} failed with status {resp.status}")
                    return None
                    
                try:
                    return await resp.json()
                except (json.JSONDecodeError, aiohttp.ContentTypeError):
                    # For endpoints that return plain text
                    text = await resp.text()
                    try:
                        # Try to handle numeric responses
                        return {"value": int(text)}
                    except ValueError:
                        return {"message": text}
                        
    except asyncio.TimeoutError:
        logger.warning(f"API request to {endpoint} timed out after {timeout}s")
    except Exception as e:
        logger.error(f"API request to {endpoint} failed with error: {e}")
    
    return None


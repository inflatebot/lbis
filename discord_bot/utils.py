\
import asyncio
import json
import discord
from discord.ext import commands
import functools
import os

# --- Time Formatting ---

def format_time(seconds):
    """Format seconds into minutes and seconds"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}m {seconds}s"

# --- Configuration & State Persistence ---

def save_wearer_id(bot, wearer_id):
    bot.config['wearer_id'] = wearer_id
    with open('bot.json', 'w') as config_file:
        json.dump(bot.config, config_file, indent=4)
    bot.OWNER_ID = wearer_id # Update runtime state

def save_session_state(bot):
    """Saves the current session state to a file."""
    state = {
        'session_time_remaining': bot.session_time_remaining,
        'last_session_update': bot.last_session_update,
        'session_pump_start': bot.session_pump_start,
        'pump_last_on_time': bot.pump_last_on_time,
        'pump_total_on_time': bot.pump_total_on_time,
        'pump_state': bot.pump_state,
        'default_session_time': bot.default_session_time, # Add this line
    }
    with open('session.json', 'w') as f:
        json.dump(state, f)

def load_session_state(bot):
    """Loads session state from a file and initializes bot attributes."""
    default_initial_time = bot.config.get('max_session_time', 1800) # Default to max_session or 30min
    try:
        with open('session.json', 'r') as f:
            state = json.load(f)
            bot.session_time_remaining = state.get('session_time_remaining', 0)
            bot.last_session_update = state.get('last_session_update', None)
            bot.session_pump_start = state.get('session_pump_start', None)
            bot.pump_last_on_time = state.get('pump_last_on_time', 0)
            bot.pump_total_on_time = state.get('pump_total_on_time', 0)
            bot.pump_state = state.get('pump_state', False)
            # Load default_session_time here, provide a default
            bot.default_session_time = state.get('default_session_time', default_initial_time) # Use the default

    except (IOError, json.JSONDecodeError):
        print("Session state file not found or invalid. Initializing with defaults.")
        # Initialize with defaults if file doesn't exist or is corrupt
        bot.session_time_remaining = 0
        bot.last_session_update = None
        bot.session_pump_start = None
        bot.pump_last_on_time = 0
        bot.pump_total_on_time = 0
        bot.pump_state = False
        # Initialize default_session_time here too
        bot.default_session_time = default_initial_time # Use the default

    # Ensure ready_note attribute exists even if loading from an old file
    if not hasattr(bot, 'ready_note'):
        bot.ready_note = None

# --- Session Time Management ---

def update_session_time(bot):
    """Updates session time based on pump usage"""
    if bot.session_pump_start is not None:
        elapsed = (asyncio.get_event_loop().time() - bot.session_pump_start)
        bot.session_time_remaining = max(0, bot.session_time_remaining - elapsed)
        bot.session_pump_start = None  # Reset pump start time after calculating

def start_pump_timer(bot):
    """Start tracking pump run time"""
    bot.session_pump_start = asyncio.get_event_loop().time()

# --- Latch Management ---

async def auto_unlatch(bot, delay):
    """Automatically unlatch after specified delay"""
    await asyncio.sleep(delay)
    if bot.latch_timer: # Check if it wasn't cancelled
        bot.latch_active = False
        bot.latch_timer = None
        bot.latch_end_time = None
        bot.latch_reason = None # Clear reason on auto-unlatch
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
        return # Don't notify if no owner set or if owner uses command

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


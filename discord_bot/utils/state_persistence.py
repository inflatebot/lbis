import json
import os
import logging
from discord.ext import commands
from state_manager import StateManager

# --- Constants ---
_utils_dir = os.path.dirname(os.path.abspath(__file__))  # Get directory of this file within utils
_base_dir = os.path.dirname(_utils_dir)  # Get the parent discord_bot directory
SESSION_FILE = os.path.join(_base_dir, "session.json")  # Path relative to discord_bot dir
BOT_CONFIG_FILE = os.path.join(_base_dir, "bot.json")  # Path relative to discord_bot dir
logger = logging.getLogger(__name__)

# --- Configuration & State Persistence ---

def save_wearer_id(bot, wearer_id):
    bot.config['wearer_id'] = wearer_id
    with open(BOT_CONFIG_FILE, 'w') as config_file:
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
    bot.state_manager.apply_to_bot(bot)

    # Initialize runtime-only attributes that are not persisted
    # Ensure these are always present after loading state
    if not hasattr(bot, 'latch_timer'):
        bot.latch_timer = None
    if not hasattr(bot, 'pump_task'):
        bot.pump_task = None
    if not hasattr(bot, 'pump_task_end_time'):
        bot.pump_task_end_time = None
    # session_pump_start is technically persisted but needs careful handling
    # If the bot restarts mid-pump, session_pump_start might be stale.
    # Consider resetting it or validating it on load if necessary.
    # For now, we load it via apply_to_bot.

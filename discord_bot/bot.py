import os
import discord
from discord.ext import commands
import json
import asyncio
import logging

# Local imports
import utils  # Import the utils module

# --- Configuration Loading ---
DEFAULT_CONFIG = {
    "discord_token": "changeme",
    "api_base_url": "http://localhost:80",
    "wearer_secret": "changeme",
    "wearer_id": None,
    "max_pump_duration": 60,
    "max_session_time": 1800,
    "max_session_extension": 3600
}

if not os.path.exists('bot.json'):
    with open('bot.json', 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
    print("Created default bot.json. Please configure it and restart the bot.")
    exit()  # Exit if config was just created

# Load configuration from JSON file
with open('bot.json', 'r') as config_file:
    config = json.load(config_file)

# Validate critical configurations
if config.get('discord_token') == 'changeme' or not config.get('discord_token'):
    raise ValueError("Discord token is not set in bot.json. Please add it and restart.")

if config.get('wearer_secret') == 'changeme':
    print(
        "\n\nSecurity Warning: Default wearer secret detected!\n"
        "Please edit bot.json and change 'wearer_secret' to a secure password.\n"
        "While the bot will run, setting the wearer will not work until this is changed.\n"
    )
    # Allow bot to run but warn user

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Keep if needed for prefix commands, otherwise can be false for slash commands only
# Consider discord.Intents.none() if only slash commands and no message content needed


class lBISBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attach config and API URL directly to bot instance for easy access in cogs
        self.config = config
        self.API_BASE_URL = config.get('api_base_url', 'http://localhost:80')
        self.OWNER_ID = config.get("wearer_id", None)  # Load initial Owner/Wearer ID

        # Initialize state variables on the bot object
        self.latch_active = False
        self.latch_timer = None
        self.latch_end_time = None
        self.latch_reason = None
        self.session_time_remaining = 0
        self.session_pump_start = None
        self.service_was_up = True  # Assume service is up initially
        self.ready_note = None  # Initialize ready_note
        self.banked_time: int = 0  # Added: Banked time in seconds
        self.pump_task: asyncio.Task | None = None  # Added: Reference to the running pump task
        self.pump_task_end_time: float | None = None  # Added: Target end time for the pump task

        # Load persistent state
        utils.load_session_state(self)  # Pass self (the bot instance)

    async def request_status_update(self):
        """Requests the MonitorCog to update the bot's presence."""
        monitor_cog = self.get_cog('MonitorCog')
        if monitor_cog:
            # Use create_task to avoid blocking if the update takes time
            asyncio.create_task(monitor_cog.update_bot_status())
        else:
            # Log if the cog isn't loaded for some reason
            logging.warning("Tried to request status update, but MonitorCog is not loaded.")

    async def setup_hook(self):
        # Load Cogs
        cogs_dir = "cogs"
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await self.load_extension(f"{cogs_dir}.{filename[:-3]}")
                    print(f"Loaded cog: {filename[:-3]}")
                except Exception as e:
                    print(f"Failed to load cog {filename[:-3]}: {e}")

        # Sync commands after loading cogs
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        # Initial status update is handled by the MonitorCog's loop starting


# --- Main Execution ---
if __name__ == "__main__":
    # Setup logging
    # logging.basicConfig(level=logging.INFO) # Basic logging
    # discord.utils.setup_logging(level=logging.INFO) # Discord specific logging

    bot = lBISBot(command_prefix='!', intents=intents)  # Prefix needed for commands.Bot, even if only using slash commands

    bot_token = config.get('discord_token')
    # Validation already happened above

    try:
        bot.run(bot_token)
    except discord.errors.LoginFailure:
        print("Failed to log in. Please check your Discord token in bot.json.")
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")
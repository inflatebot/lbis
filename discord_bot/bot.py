import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import functools
import asyncio

# lBIS Discord Bot Reference Implementation
# This bot was 100% vibe-coded with GPT4.1 and Claude 3.5 Sonnet. It is not intended to be stable, secure, or sensible.
# While you are able to latch your lBIS to prevent Shenanigans, you definitely shouldn't invite this bot to any public servers because ANYBODY can use the commands!!
# Also please don't commit your user secrets. Ty.
# - Bot

# Ensure bot.json exists
DEFAULT_CONFIG = {
    "discord_token": "changeme",
    "api_base_url": "http://localhost:80",
    "wearer_secret": "changeme",
    "wearer_id": None,
    "max_pump_duration": 60,  # Maximum pump duration in seconds (1 minute default)
    "max_session_time": 1800,  # Default 30 minutes total session time
    "max_session_extension": 3600  # Maximum time that can be added to a session (1 hour)
}

if not os.path.exists('bot.json'):
    with open('bot.json', 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

# Load configuration from JSON file
with open('bot.json', 'r') as config_file:
    config = json.load(config_file)

# Validate wearer secret
if config.get('wearer_secret') == 'changeme':
    raise ValueError(
        "\n\nSecurity Error: Default wearer secret detected!\n"
        "Please edit bot.json and change 'wearer_secret' to a secure password.\n"
        "This is required to prevent unauthorized access to your device which could pose a safety hazard.\n"
        "It can be anything, as long as you store it safely.\n"
    )

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

API_BASE_URL = config.get('api_base_url', 'http://localhost:80')

# Global latch state
latch_active = False
latch_timer = None  # Store the task for timed unlatch
latch_reason = None  # Store the reason for the latch

session_time_remaining = 0  # Current session time remaining in seconds
session_pump_start = None  # When the pump was last turned on

service_was_up = True  # Tracks last known state

OWNER_ID = config.get("wearer_id", None)
OWNER_SECRET = config.get("wearer_secret", "changeme")  # Add this to your bot.json

# Add after global variables
def update_session_time():
    """Updates session time based on pump usage"""
    global session_time_remaining, session_pump_start
    if session_pump_start is not None:
        elapsed = (asyncio.get_event_loop().time() - session_pump_start)
        session_time_remaining = max(0, session_time_remaining - elapsed)
        session_pump_start = None  # Reset pump start time

def start_pump_timer():
    """Start tracking pump run time"""
    global session_pump_start
    session_pump_start = asyncio.get_event_loop().time()

def format_time(seconds):
    """Format seconds into minutes and seconds"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}m {seconds}s"

def save_wearer_id(wearer_id):
    config['wearer_id'] = wearer_id
    with open('bot.json', 'w') as config_file:
        json.dump(config, config_file, indent=4)

# Session persistence
def save_session_state():
    """Save session state to disk"""
    state = {
        "session_time_remaining": session_time_remaining,
        "session_pump_start": session_pump_start,
        "latch_active": latch_active,
        "latch_end_time": latch_end_time if 'latch_end_time' in globals() else None,
        "latch_reason": latch_reason
    }
    with open('session.json', 'w') as f:
        json.dump(state, f)

def load_session_state():
    """Load session state from disk"""
    global session_time_remaining, session_pump_start, latch_active, latch_end_time, latch_reason
    try:
        with open('session.json', 'r') as f:
            state = json.load(f)
            session_time_remaining = state.get('session_time_remaining', 0)
            session_pump_start = state.get('session_pump_start')
            latch_active = state.get('latch_active', False)
            latch_end_time = state.get('latch_end_time')
            latch_reason = state.get('latch_reason')
            
            # If there was a timed latch, restore it
            if latch_end_time and latch_active:
                remaining = latch_end_time - asyncio.get_event_loop().time()
                if remaining > 0:
                    asyncio.create_task(auto_unlatch(remaining))
                else:
                    latch_active = False
    except FileNotFoundError:
        session_time_remaining = 0
        session_pump_start = None
        latch_active = False
        latch_end_time = None
        latch_reason = None
        save_session_state()

async def auto_unlatch(delay):
    """Automatically unlatch after specified delay"""
    global latch_active, latch_timer
    await asyncio.sleep(delay)
    latch_active = False
    latch_timer = None
    save_session_state()
    if OWNER_ID:
        try:
            wearer = await bot.fetch_user(OWNER_ID)
            await wearer.send("Timed latch has expired - pump is now unlatched.")
        except Exception as e:
            print(f"Failed to notify wearer of unlatch: {e}")

def is_wearer(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

async def notify_wearer(interaction: discord.Interaction, command_name: str):
    try:
        wearer = await bot.fetch_user(OWNER_ID)
        if wearer:
            location = "Direct Messages" if interaction.guild is None else f"{interaction.guild.name} / #{interaction.channel.name}"
            user_info = f"{interaction.user} ({interaction.user.id})"
            
            # Get command parameters
            params = []
            for option in interaction.data.get("options", []):
                params.append(f"{option['name']}:{option['value']}")
            param_str = " " + " ".join(params) if params else ""
            
            await wearer.send(
                f"Command `{command_name}{param_str}` used by {user_info} in {location}."
            )
    except Exception as e:
        print(f"Failed to notify wearer: {e}")

def dm_wearer_on_use(command_name):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            await notify_wearer(interaction, command_name)
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

async def update_bot_status():
    """Update bot's status to reflect current pump state and session info"""
    try:
        # Base status on service availability
        if not service_was_up:
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.playing,
                    name="⚠️ Service Unreachable"
                ),
                status=discord.Status.dnd
            )
            return
        
        # Get pump state first
        pump_state = "0"
        if not latch_active:  # Only check pump state if not latched
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/getPumpState") as response:
                    if response.status == 200:
                        pump_state = await response.text()
        
        # Determine status text
        if latch_active:
            status_text = "🔒 Latched"
            if latch_reason:
                # Truncate reason if too long
                short_reason = (latch_reason[:20] + '..') if len(latch_reason) > 20 else latch_reason
                status_text += f": {short_reason}"
            status = discord.Status.idle
        else:
            status_text = "🟢 ON" if pump_state == "1" else "⚫ READY"
            status = discord.Status.online if pump_state == "1" else discord.Status.idle
        
        # Add time info
        status_text += f" | {format_time(session_time_remaining)}"

        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name=status_text
            ),
            status=status
        )
    except Exception as e:
        print(f"Failed to update status: {e}")

async def service_monitor():
    global service_was_up
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/marco", timeout=5) as resp:
                    if resp.status == 200:
                        if not service_was_up and OWNER_ID:
                            wearer = await bot.fetch_user(OWNER_ID)
                            if wearer:
                                await wearer.send("Service is back up!")
                        service_was_up = True
                    else:
                        raise Exception("Non-200 status")
        except Exception:
            if service_was_up and OWNER_ID:
                try:
                    wearer = await bot.fetch_user(OWNER_ID)
                    if wearer:
                        await wearer.send("Service appears to be down!")
                except Exception as e:
                    print(f"Failed to DM wearer about service down: {e}")
            service_was_up = False
        
        # Update bot status only - remove bio update
        await update_bot_status()
        await asyncio.sleep(10)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Load saved session state
    load_session_state()
    
    # Start the background service monitor
    bot.loop.create_task(service_monitor())
    
    # Add initial status update
    await update_bot_status()

@bot.tree.command(name="marco", description="Check if the server is responding")
async def marco(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE_URL}/api/marco") as response:
            if response.status == 200:
                data = await response.text()
                await interaction.response.send_message(f"Server says: {data}")
            else:
                await interaction.response.send_message("Failed to reach server")

@bot.tree.command(name="status", description="Check the current device status")
@dm_wearer_on_use("status")
async def device_status(interaction: discord.Interaction):
    update_session_time()  # Update session time before displaying
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE_URL}/api/getPumpState") as response:
            if response.status == 200:
                state = await response.text()
                state_text = "ON" if state == "1" else "OFF"
                
                status_lines = [
                    f"🔌 Pump: {state_text}",
                    f"⏲️ Session: {format_time(session_time_remaining)} remaining"
                ]
                
                if latch_active:
                    latch_msg = "🔒 Pump is latched"
                    if latch_reason:
                        latch_msg += f": {latch_reason}"
                    status_lines.append(latch_msg)
                
                await interaction.response.send_message("\n".join(status_lines))
            else:
                await interaction.response.send_message("Failed to get device status")

@bot.tree.command(name="pump_on", description="Turn the pump on (wearer only)")
@app_commands.check(is_wearer)
@dm_wearer_on_use("pump_on")
async def pump_on(interaction: discord.Interaction):
    global latch_active, session_time_remaining
    if latch_active:
        message = "Pump is currently latched, and cannot be turned on."
        if latch_reason:
            message += f"\nReason: {latch_reason}"
        await interaction.response.send_message(message, ephemeral=True)
        return
    if session_time_remaining <= 0:
        await interaction.response.send_message("No session time remaining. Use /add_time to add more time.", ephemeral=True)
        return
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 1}
        ) as response:
            if response.status == 200:
                start_pump_timer()
                await update_bot_status()
                await interaction.response.send_message(f"Pump turned ON! {format_time(session_time_remaining)} remaining.")
            else:
                await interaction.response.send_message("Failed to turn pump on")

@bot.tree.command(name="pump_off", description="Turn the pump off")
@dm_wearer_on_use("pump_off")
async def pump_off(interaction: discord.Interaction):
    update_session_time()  # Update remaining time when pump is turned off
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 0}
        ) as response:
            if response.status == 200:
                await update_bot_status()
                await interaction.response.send_message(f"Pump turned OFF! {format_time(session_time_remaining)} remaining.")
            else:
                await interaction.response.send_message("Failed to turn pump off")

@bot.tree.command(name="pump_timed", description="Turn the pump on for a specified duration")
@app_commands.describe(seconds="Duration in seconds to run the pump")
@dm_wearer_on_use("pump_timed")
async def pump_timed(interaction: discord.Interaction, seconds: int):
    global latch_active, session_time_remaining
    max_duration = config.get('max_pump_duration', 30)
    
    if latch_active:
        message = "Pump is currently latched, and cannot be turned on."
        if latch_reason:
            message += f"\nReason: {latch_reason}"
        await interaction.response.send_message(message, ephemeral=True)
        return
    
    if seconds <= 0:
        await interaction.response.send_message("Duration must be greater than 0 seconds.", ephemeral=True)
        return
    
    if seconds > max_duration:
        await interaction.response.send_message(f"Duration cannot exceed {max_duration} seconds.", ephemeral=True)
        return
    
    if session_time_remaining <= 0:
        await interaction.response.send_message("No session time remaining. Use /add_time to add more time.", ephemeral=True)
        return
    
    # Limit run time to remaining session time
    seconds = min(seconds, int(session_time_remaining))
    
    async with aiohttp.ClientSession() as session:
        # Turn pump on
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 1}
        ) as response:
            if response.status != 200:
                await interaction.response.send_message("Failed to turn pump on")
                return
        
        start_pump_timer()
        await update_bot_status()
        await interaction.response.send_message(f"Pump turned ON for {seconds} seconds! {format_time(session_time_remaining)} remaining in session.")
        
        # Wait for specified duration
        await asyncio.sleep(seconds)
        
        update_session_time()
        # Turn pump off
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 0}
        ) as response:
            if response.status == 200:
                await update_bot_status()
                await interaction.followup.send(f"Pump turned OFF! {format_time(session_time_remaining)} remaining in session.")
            else:
                await interaction.followup.send("Failed to turn pump off after timeout!")

@bot.tree.command(name="restart", description="Restart the server")
@app_commands.check(is_wearer)
@dm_wearer_on_use("restart")
async def restart(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE_URL}/api/restart") as response:
            if response.status == 200:
                await interaction.response.send_message("Server is restarting...")
            else:
                await interaction.response.send_message("Failed to restart server")

@restart.error
async def restart_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message("Only the device wearer can use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred.", ephemeral=True)

@bot.tree.command(name="set_wearer", description="Register yourself as this device's wearer (DM only, requires secret)")
@app_commands.describe(secret="Your secret")
async def set_wearer(interaction: discord.Interaction, secret: str):
    global OWNER_ID
    if interaction.guild is not None:
        await interaction.response.send_message("This command can only be used in DMs.", ephemeral=True)
        return
    if secret == OWNER_SECRET:
        OWNER_ID = interaction.user.id
        save_wearer_id(OWNER_ID)
        await update_bot_status()  # Update status instead of bio
        await interaction.response.send_message("You are now registered as this device's wearer!")
    else:
        await interaction.response.send_message("Incorrect secret.", ephemeral=True)

@bot.tree.command(name="latch", description="Toggle, set, or time-limit the pump latch. Use without parameters to toggle.")
@app_commands.check(is_wearer)
@app_commands.describe(
    state="Optional: Set to true to latch, false to unlatch. Omit to toggle.",
    minutes="Optional: Number of minutes to latch for",
    reason="Optional: Reason for latching"
)
async def latch(interaction: discord.Interaction, state: bool = None, minutes: int = None, reason: str = None):
    global latch_active, latch_timer, latch_end_time, latch_reason

    # Determine new latch state
    new_state = not latch_active if state is None else state

    # Cancel existing timer if any
    if latch_timer:
        latch_timer.cancel()
        latch_timer = None
        latch_end_time = None

    latch_active = new_state
    latch_reason = reason if new_state else None
    status = "latched" if new_state else "unlatched"

    # If latching, ensure pump is off
    if new_state:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/api/setPumpState",
                json={"pump": 0}
            ) as response:
                if response.status != 200:
                    await interaction.response.send_message("Failed to turn pump off while latching", ephemeral=True)
                    return
                update_session_time()

        # Set up timed unlatch if minutes specified
        if minutes is not None and minutes > 0:
            latch_end_time = asyncio.get_event_loop().time() + (minutes * 60)
            latch_timer = asyncio.create_task(auto_unlatch(minutes * 60))
            status = f"{status} for {minutes} minutes"

    save_session_state()
    await update_bot_status()
    await interaction.response.send_message(f"Pump is now {status}.")

@latch.error
async def latch_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message("Only the device wearer can use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred.", ephemeral=True)

@bot.tree.command(name="add_time", description="Add time to the current session (wearer only)")
@app_commands.check(is_wearer)
@app_commands.describe(minutes="Minutes to add to the session")
async def add_time(interaction: discord.Interaction, minutes: int):
    global session_time_remaining
    max_extension = config.get('max_session_extension', 3600)
    
    if minutes <= 0:
        await interaction.response.send_message("Please specify a positive number of minutes.", ephemeral=True)
        return
    
    if (minutes * 60) > max_extension:
        await interaction.response.send_message(f"Cannot add more than {max_extension//60} minutes at once.", ephemeral=True)
        return
        
    update_session_time()  # Update current time first
    session_time_remaining += (minutes * 60)
    save_session_state()
    await update_bot_status()
    await interaction.response.send_message(f"Added {minutes} minutes to session. {format_time(session_time_remaining)} remaining.")

@bot.tree.command(name="reset_time", description="Reset the session timer (wearer only)")
@app_commands.check(is_wearer)
async def reset_time(interaction: discord.Interaction):
    global session_time_remaining, session_pump_start
    session_time_remaining = 0
    session_pump_start = None
    save_session_state()
    await update_bot_status()
    await interaction.response.send_message("Session timer has been reset to 0.")

@bot.tree.command(name="session_time", description="Check remaining session time")
async def check_time(interaction: discord.Interaction):
    update_session_time()
    await interaction.response.send_message(f"Session time remaining: {format_time(session_time_remaining)}")

@bot.tree.command(name="set_time", description="Set the session timer to a specific value (wearer only)")
@app_commands.check(is_wearer)
@app_commands.describe(minutes="Minutes to set the session timer to")
async def set_time(interaction: discord.Interaction, minutes: int):
    global session_time_remaining
    max_session = config.get('max_session_time', 1800)
    
    if minutes <= 0:
        await interaction.response.send_message("Please specify a positive number of minutes.", ephemeral=True)
        return
    
    if (minutes * 60) > max_session:
        await interaction.response.send_message(f"Cannot set time higher than {max_session//60} minutes.", ephemeral=True)
        return
        
    session_time_remaining = minutes * 60
    save_session_state()
    await update_bot_status()
    await interaction.response.send_message(f"Session time set to {format_time(session_time_remaining)}.")

# Run the bot
if __name__ == "__main__":
    bot_token = config.get('discord_token')
    if not bot_token:
        raise ValueError("No Discord token found in configuration file")
    bot.run(bot_token)
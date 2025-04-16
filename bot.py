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
    "owner_secret": "changeme",
    "owner_id": None
}

if not os.path.exists('bot.json'):
    with open('bot.json', 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

# Load configuration from JSON file
with open('bot.json', 'r') as config_file:
    config = json.load(config_file)

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

API_BASE_URL = config.get('api_base_url', 'http://localhost:80')

# Global latch state
latch_active = False

def save_owner_id(owner_id):
    config['owner_id'] = owner_id
    with open('bot.json', 'w') as config_file:
        json.dump(config, config_file, indent=4)

OWNER_ID = config.get("owner_id", None)
OWNER_SECRET = config.get("owner_secret", "changeme")  # Add this to your bot.json

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

async def notify_owner(interaction: discord.Interaction, command_name: str):
    #if OWNER_ID is None or interaction.user.id == OWNER_ID:
    #    return # temporarily disabling this for testing
    try:
        owner = await bot.fetch_user(OWNER_ID)
        if owner:
            location = "DMs" if interaction.guild is None else f"{interaction.guild.name} / #{interaction.channel.name}"
            await owner.send(
                f"Command `{command_name}` used by {interaction.user} ({interaction.user.id}) in {location}."
            )
    except Exception as e:
        print(f"Failed to notify owner: {e}")

def dm_owner_on_use(command_name):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            await notify_owner(interaction, command_name)
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

service_was_up = True  # Tracks last known state

async def service_monitor():
    global service_was_up
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/marco", timeout=5) as resp:
                    if resp.status == 200:
                        if not service_was_up and OWNER_ID:
                            owner = await bot.fetch_user(OWNER_ID)
                            if owner:
                                await owner.send("Service is back up!")
                        service_was_up = True
                    else:
                        raise Exception("Non-200 status")
        except Exception:
            if service_was_up and OWNER_ID:
                try:
                    owner = await bot.fetch_user(OWNER_ID)
                    if owner:
                        await owner.send("Service appears to be DOWN!")
                except Exception as e:
                    print(f"Failed to DM owner about service down: {e}")
            service_was_up = False
        await asyncio.sleep(30)  # Check every 30 seconds

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    # Start the background service monitor
    bot.loop.create_task(service_monitor())

@bot.tree.command(name="marco", description="Check if the server is responding")
@dm_owner_on_use("marco")
async def marco(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE_URL}/api/marco") as response:
            if response.status == 200:
                data = await response.text()
                await interaction.response.send_message(f"Server says: {data}")
            else:
                await interaction.response.send_message("Failed to reach server")

@bot.tree.command(name="pump", description="Check the current pump state")
@dm_owner_on_use("pump")
async def pump_state(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE_URL}/api/getPumpState") as response:
            if response.status == 200:
                state = await response.text()
                state_text = "ON" if state == "1" else "OFF"
                await interaction.response.send_message(f"Pump is currently {state_text}")
            else:
                await interaction.response.send_message("Failed to get pump state")

@bot.tree.command(name="pump_on", description="Turn the pump on")
@dm_owner_on_use("pump_on")
async def pump_on(interaction: discord.Interaction):
    global latch_active
    if latch_active:
        await interaction.response.send_message("Pump is currently latched, and cannot be turned on.", ephemeral=True)
        return
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 1}
        ) as response:
            if response.status == 200:
                await interaction.response.send_message("Pump turned ON!")
            else:
                await interaction.response.send_message("Failed to turn pump on")

@bot.tree.command(name="pump_off", description="Turn the pump off")
@dm_owner_on_use("pump_off")
async def pump_off(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE_URL}/api/setPumpState",
            json={"pump": 0}
        ) as response:
            if response.status == 200:
                await interaction.response.send_message("Pump turned OFF!")
            else:
                await interaction.response.send_message("Failed to turn pump off")

@bot.tree.command(name="restart", description="Restart the server")
@dm_owner_on_use("restart")
async def restart(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE_URL}/api/restart") as response:
            if response.status == 200:
                await interaction.response.send_message("Server is restarting...")
            else:
                await interaction.response.send_message("Failed to restart server")

@bot.tree.command(name="set_owner", description="Set yourself as lBIS's wearer. (DM only, requires secret)")
@app_commands.describe(secret="Your secret")
async def set_owner(interaction: discord.Interaction, secret: str):
    global OWNER_ID
    if interaction.guild is not None:
        await interaction.response.send_message("This command can only be used in DMs.", ephemeral=True)
        return
    if secret == OWNER_SECRET:
        OWNER_ID = interaction.user.id
        save_owner_id(OWNER_ID)
        await interaction.response.send_message("You are now the wearer!")
    else:
        await interaction.response.send_message("Incorrect secret.", ephemeral=True)

@bot.tree.command(name="latch", description="Latch or unlatch the pump, preventing it from being turned on. Only the wearer can do this.")
@app_commands.check(is_owner)
@app_commands.describe(state="Set to true to latch, false to unlatch")
async def latch(interaction: discord.Interaction, state: bool):
    global latch_active
    latch_active = state
    status = "latched (pump_on disabled)" if state else "unlatched (pump_on enabled)"
    await interaction.response.send_message(f"Pump is now {status}.")

@latch.error
async def latch_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred.", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    bot_token = config.get('discord_token')
    if not bot_token:
        raise ValueError("No Discord token found in configuration file")
    bot.run(bot_token)
import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging
from utils import format_time, api_request, save_session_state, update_session_time

logger = logging.getLogger(__name__)

class MonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize device_base_url using the main API URL
        self.bot.device_base_url = self.bot.API_BASE_URL
        if not self.bot.device_base_url:
            logger.warning("API base URL not found in config! Monitoring tasks might fail.")
        else:
            logger.info(f"API base URL loaded: {self.bot.device_base_url}")

        self.service_monitor_task.start()
        self.session_timer.start()

    def cog_unload(self):
        self.service_monitor_task.cancel()
        self.session_timer.cancel()

    async def update_bot_status(self):
        """Updates the bot's Discord presence based on current state."""
        if not self.bot.is_ready() or not self.bot.service_was_up:
            status = discord.Status.dnd # Do Not Disturb if not ready or API down
            activity_string = "API Down" if not self.bot.service_was_up else "Starting..."
            activity = discord.Game(name=activity_string)
        else:
            status = discord.Status.online
            session_str = format_time(self.bot.session_time_remaining)
            banked_str = format_time(self.bot.banked_time)
            latch_str = "🔒" if self.bot.latch_active else ""

            pump_state_str = ""
            if self.bot.pump_task and not self.bot.pump_task.done():
                pump_state_str = "ON"
            else:
                if not self.bot.device_base_url:
                    logger.error("Device API base URL not configured. Cannot monitor pump status.")
                    pump_state_str = "UNKNOWN"
                else:
                    try:
                        async with aiohttp.ClientSession() as session:
                            status_url = f"{self.bot.device_base_url}/api/getPumpState"
                            logger.debug(f"Checking pump status at: {status_url}")
                            async with session.get(status_url) as response:
                                if response.status == 200:
                                    # Try to parse as text first since the API returns "0" or "1"
                                    text = await response.text()
                                    try:
                                        # Convert text to boolean
                                        is_on = bool(int(text))
                                        pump_state_str = "ON" if is_on else "OFF"
                                    except ValueError:
                                        # If text->int conversion fails, try JSON as fallback
                                        try:
                                            pump_state = await response.json()
                                            pump_state_str = "ON" if pump_state.get('is_on') else "OFF"
                                        except:
                                            logger.error(f"Failed to parse pump state from response: {text}")
                                            pump_state_str = "UNKNOWN"
                                else:
                                    logger.error(f"API request to {status_url} failed with status {response.status}")
                                    pump_state_str = "UNKNOWN"
                    except Exception as e:
                        logger.error(f"Failed to check pump status: {e}")
                        pump_state_str = "UNKNOWN"

            activity_string = f"{latch_str}Pump: {pump_state_str} | Sess: {session_str} | Bank: {banked_str}"
            # Use CustomActivity instead of Game
            activity = discord.CustomActivity(name=activity_string)

        try:
            await self.bot.change_presence(status=status, activity=activity)
            logger.debug(f"Updated presence: {status}, Activity: {activity_string}")
        except Exception as e:
            logger.error(f"Failed to update presence: {e}")

    @tasks.loop(seconds=15)
    async def service_monitor_task(self):
        """Background task to monitor service availability and update status"""
        was_previously_up = self.bot.service_was_up
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.bot.API_BASE_URL}/api/marco", timeout=5) as resp:
                    if resp.status == 200:
                        self.bot.service_was_up = True
                        if not was_previously_up and self.bot.OWNER_ID:
                            try:
                                wearer = await self.bot.fetch_user(self.bot.OWNER_ID)
                                if wearer:
                                    await wearer.send("✅ Service is back up!")
                            except Exception as e:
                                print(f"Failed to DM wearer about service up: {e}")
                    else:
                        raise Exception(f"Non-200 status: {resp.status}")
        except Exception as e:
            if was_previously_up:
                 print(f"Service check failed: {e}")
                 if self.bot.OWNER_ID:
                    try:
                        wearer = await self.bot.fetch_user(self.bot.OWNER_ID)
                        if wearer:
                            await wearer.send("⚠️ Service appears to be down!")
                    except Exception as notify_e:
                        print(f"Failed to DM wearer about service down: {notify_e}")
            self.bot.service_was_up = False

        await self.update_bot_status()

    @service_monitor_task.before_loop
    async def before_service_monitor(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=1.0)
    async def session_timer(self):
        """Decrements session time remaining every second."""
        if not self.bot.is_ready() or not self.bot.service_was_up:
            return

        if not self.bot.device_base_url:
            logger.warning("Device base URL not set, cannot enforce pump state for session timer.")

        is_manually_on = False
        if not (self.bot.pump_task and not self.bot.pump_task.done()):
            if not self.bot.device_base_url:
                logger.error("Device API base URL not configured. Cannot monitor pump status.")
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        status_url = f"{self.bot.device_base_url}/api/getPumpState"
                        logger.debug(f"Checking pump status at: {status_url}")
                        async with session.get(status_url) as response:
                            if response.status == 200:
                                # Try to parse as text first since the API returns "0" or "1"
                                text = await response.text()
                                try:
                                    # Convert text to boolean
                                    is_on = bool(int(text))
                                    is_manually_on = is_on
                                except ValueError:
                                    # If text->int conversion fails, try JSON as fallback
                                    try:
                                        pump_state = await response.json()
                                        is_manually_on = pump_state.get('is_on', False)
                                    except:
                                        logger.error(f"Failed to parse pump state from response: {text}")
                            else:
                                logger.error(f"API request to {status_url} failed with status {response.status}")
                except Exception as e:
                    logger.error(f"Failed to check pump status: {e}")

        if is_manually_on:
            if self.bot.session_time_remaining > 0:
                update_session_time(self.bot, -1)
                if self.bot.session_time_remaining == 0:
                    logger.info("Session time reached zero while pump was manually on.")
                    await self.update_bot_status()

    @session_timer.before_loop
    async def before_session_timer(self):
        await self.bot.wait_until_ready()
        logger.info("Session timer loop starting.")

async def setup(bot):
    monitor_cog = MonitorCog(bot)
    await bot.add_cog(monitor_cog)

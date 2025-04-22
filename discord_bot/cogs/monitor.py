import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging  # Added
from utils import format_time, api_request, save_session_state, update_session_time

logger = logging.getLogger(__name__)  # Added

class MonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
            banked_str = format_time(self.bot.banked_time) # Added
            latch_str = "🔒" if self.bot.latch_active else ""

            pump_state_str = ""
            # Check if a task is running first
            if self.bot.pump_task and not self.bot.pump_task.done():
                pump_state_str = "ON"
            else:
                # If no task, check API (best effort)
                pump_state = await api_request(self.bot, "pump/status")
                if pump_state is not None and pump_state.get('is_on'):
                    pump_state_str = "ON"
                else:
                    pump_state_str = "OFF"

            # Construct activity string (adjust format as needed for length)
            activity_string = f"{latch_str}Pump: {pump_state_str} | Sess: {session_str} | Bank: {banked_str}"

            # Use CustomActivity for more flexibility if needed, or Game for simplicity
            activity = discord.Game(name=activity_string)
            # Example with CustomActivity:
            # activity = discord.CustomActivity(name=activity_string)

        try:
            await self.bot.change_presence(status=status, activity=activity)
            logger.debug(f"Updated presence: {status}, Activity: {activity_string}")
        except Exception as e:
            logger.error(f"Failed to update presence: {e}")

    @tasks.loop(seconds=15) # Check service less frequently, update status more often if needed
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
                        # Treat non-200 as down
                        raise Exception(f"Non-200 status: {resp.status}")
        except Exception as e:
            # Any exception means service is likely down
            if was_previously_up: # Only notify on the transition to down
                 print(f"Service check failed: {e}") # Log the error
                 if self.bot.OWNER_ID:
                    try:
                        wearer = await self.bot.fetch_user(self.bot.OWNER_ID)
                        if wearer:
                            await wearer.send("⚠️ Service appears to be down!")
                    except Exception as notify_e:
                        print(f"Failed to DM wearer about service down: {notify_e}")
            self.bot.service_was_up = False

        # Update bot status regardless of reachability change
        await self.update_bot_status()

    @service_monitor_task.before_loop
    async def before_service_monitor(self):
        await self.bot.wait_until_ready() # Ensure bot is ready before starting loop

    @tasks.loop(seconds=1.0)
    async def session_timer(self):
        """Decrements session time remaining every second."""
        if not self.bot.is_ready() or not self.bot.service_was_up:
            return # Don't decrement if bot isn't ready or API is down

        # Time is now decremented based on actual pump run time in the pump loops
        # This timer primarily exists to update status if nothing else is happening
        # and potentially enforce session limits if pump runs indefinitely (manual on)

        # Let's check if the pump is ON according to API (if no task is running)
        # This handles the case where pump was left ON manually
        is_manually_on = False
        if not (self.bot.pump_task and not self.bot.pump_task.done()):
            pump_state = await api_request(self.bot, "pump/status")
            if pump_state is not None and pump_state.get('is_on'):
                is_manually_on = True

        # Only decrement session time here if the pump is manually on
        if is_manually_on:
            if self.bot.session_time_remaining > 0:
                update_session_time(self.bot, -1) # Decrement by 1 second
                # No need to save state every second, pump loops handle it.
                # If it runs out, the pump keeps running, but commands might fail.
                if self.bot.session_time_remaining == 0:
                    logger.info("Session time reached zero while pump was manually on.")
                    # Optionally DM wearer when session runs out?
                    await self.update_bot_status() # Update status immediately
            # else: session time is already zero or less
        # else: Pump is off or managed by a timed/banked task loop

        # We might still want periodic status updates even if time isn't decrementing
        # Maybe update status less frequently here if nothing changed?
        # For now, let's keep it simple and rely on other actions to trigger updates.

    @session_timer.before_loop
    async def before_session_timer(self):
        await self.bot.wait_until_ready()
        logger.info("Session timer loop starting.")

async def setup(bot):
    monitor_cog = MonitorCog(bot)
    await bot.add_cog(monitor_cog)

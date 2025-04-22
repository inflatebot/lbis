import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from utils import format_time

class MonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service_monitor_task.start()

    def cog_unload(self):
        self.service_monitor_task.cancel()

    async def update_bot_status(self):
        """Update bot's status to reflect current pump state and session info"""
        try:
            status_text = ""
            status = discord.Status.online # Default status
            custom_emoji_obj = None # For the custom emoji object passed to activity

            # Base status on service availability
            if not self.bot.service_was_up:
                status_text = "⚠️ Service Unreachable" # Prepend standard emoji
                status = discord.Status.dnd
            else:
                # Get pump state first (only if not latched)
                pump_state = "0" # Assume off if latched or error
                if not self.bot.latch_active:
                    try:
                        async with aiohttp.ClientSession() as session:
                             # Short timeout for status update
                            async with session.get(f"{self.bot.API_BASE_URL}/api/getPumpState", timeout=3) as response:
                                if response.status == 200:
                                    pump_state = await response.text()
                                # else: keep pump_state as "0" on error
                    except Exception:
                        # Keep pump_state as "0" on connection error/timeout
                        pass # Error logged in service_monitor

                # Determine status text and potentially emoji based on state
                if self.bot.latch_active:
                    status_text = "🔒 Latched" # Prepend standard emoji
                    if self.bot.latch_reason:
                        max_reason_len = 20
                        short_reason = (self.bot.latch_reason[:max_reason_len] + '..') if len(self.bot.latch_reason) > max_reason_len else self.bot.latch_reason
                        status_text += f": {short_reason}"
                    status = discord.Status.idle
                else:
                    if pump_state == "1":
                        # Try to use a custom emoji when ON
                        try:
                             # Replace with your actual emoji details
                             custom_emoji_obj = discord.PartialEmoji(name='pump_on_emoji', id=123456789012345678)
                             status_text = "ON" # Set text separately
                        except Exception as e: # Fallback if custom emoji fails
                             print(f"Failed to get custom emoji: {e}. Falling back.")
                             custom_emoji_obj = None # Ensure it's None on failure
                             status_text = "🟢 ON" # Prepend standard emoji as fallback
                        status = discord.Status.online
                    else:
                        # Use standard emoji when READY
                        status_text = "⚫ READY" # Prepend standard emoji
                        status = discord.Status.idle

                # Add time info (append after emoji/state text)
                status_text += f" | {format_time(self.bot.session_time_remaining)}"

            # Create CustomActivity
            # Pass the custom emoji object (or None) to the emoji parameter
            activity = discord.CustomActivity(
                name=status_text,
                emoji=custom_emoji_obj
            )

            await self.bot.change_presence(activity=activity, status=status)

        except Exception as e:
            print(f"Failed to update status: {e}")

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


async def setup(bot):
  await bot.add_cog(MonitorCog(bot))

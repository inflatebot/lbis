\
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
            # Base status on service availability
            if not self.bot.service_was_up:
                activity = discord.Activity(
                    type=discord.ActivityType.playing,
                    name="⚠️ Service Unreachable"
                )
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

                # Determine status text
                if self.bot.latch_active:
                    status_text = "🔒 Latched"
                    if self.bot.latch_reason:
                        # Truncate reason if too long
                        max_reason_len = 20
                        short_reason = (self.bot.latch_reason[:max_reason_len] + '..') if len(self.bot.latch_reason) > max_reason_len else self.bot.latch_reason
                        status_text += f": {short_reason}"
                    status = discord.Status.idle
                else:
                    status_text = "🟢 ON" if pump_state == "1" else "⚫ READY"
                    status = discord.Status.online if pump_state == "1" else discord.Status.idle

                # Add time info
                status_text += f" | {format_time(self.bot.session_time_remaining)}"

                activity = discord.Activity(
                    type=discord.ActivityType.playing,
                    name=status_text
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

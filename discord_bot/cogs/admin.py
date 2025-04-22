import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from utils import is_wearer, dm_wearer_on_use, save_wearer_id, save_session_state, auto_unlatch, update_session_time, format_time

logger = logging.getLogger(__name__)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_status(self):
        """Helper to trigger status update"""
        monitor_cog = self.bot.get_cog('MonitorCog')
        if monitor_cog:
            await monitor_cog.update_bot_status()

    @app_commands.command(name="restart", description="Restart the server (wearer only)")
    @app_commands.check(is_wearer)
    @dm_wearer_on_use("restart")
    async def restart(self, interaction: discord.Interaction):
        """Restart the server (wearer only)"""
        await interaction.response.defer(thinking=True, ephemeral=True) # Acknowledge interaction ephemerally
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.bot.API_BASE_URL}/api/restart", timeout=10) as response:
                    # Response might be inconsistent on restart, primarily check reachability
                    await interaction.followup.send("Restart command sent. Server may become temporarily unavailable.", ephemeral=True)
                    # Optionally: Trigger a status update check after a short delay
                    # asyncio.create_task(self.delayed_status_update(5))
            except asyncio.TimeoutError:
                 await interaction.followup.send("Restart command sent, but no response received (server might be restarting).", ephemeral=True)
            except aiohttp.ClientConnectorError:
                 await interaction.followup.send("Failed to reach server to send restart command.", ephemeral=True)
            except Exception as e:
                 await interaction.followup.send(f"An error occurred sending restart command: {e}", ephemeral=True)


    @app_commands.command(name="set_wearer", description="Register yourself as this device's wearer (DM only, requires secret)")
    @app_commands.describe(secret="Your secret")
    async def set_wearer(self, interaction: discord.Interaction, secret: str):
        """Register yourself as this device's wearer (DM only, requires secret)"""
        if interaction.guild is not None:
            await interaction.response.send_message("This command can only be used in DMs.", ephemeral=True)
            return

        # Access OWNER_SECRET from bot's config
        if secret == self.bot.config.get("wearer_secret"):
            self.bot.OWNER_ID = interaction.user.id
            save_wearer_id(self.bot, interaction.user.id) # Pass bot object
            await self.update_status()
            await interaction.response.send_message("You are now registered as this device's wearer!", ephemeral=True)
        else:
            await interaction.response.send_message("Incorrect secret.", ephemeral=True)

    @app_commands.command(name="latch", description="Toggle, set, or time-limit the pump latch (wearer only).")
    @app_commands.check(is_wearer)
    @app_commands.describe(
        state="Optional: Set to true to latch, false to unlatch. Omit to toggle.",
        minutes="Optional: Number of minutes to latch for (positive integer)",
        reason="Optional: Reason for latching (max 100 chars)"
    )
    async def latch(self, interaction: discord.Interaction, state: bool = None, minutes: app_commands.Range[int, 1] = None, reason: app_commands.Range[str, 0, 100] = None):
        """Toggle, set, or time-limit the pump latch (wearer only)."""

        # Determine new latch state
        new_state = not self.bot.latch_active if state is None else state

        # Cancel existing timer if any
        if self.bot.latch_timer:
            self.bot.latch_timer.cancel()
            self.bot.latch_timer = None
            self.bot.latch_end_time = None

        self.bot.latch_active = new_state
        self.bot.latch_reason = reason if new_state else None # Set reason only if latching
        status_message = "latched" if new_state else "unlatched"

        # If latching, ensure pump is off
        if new_state:
            # async with aiohttp.ClientSession() as session:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        f"{self.bot.API_BASE_URL}/api/setPumpState",
                        json={"pump": 0},
                        timeout=10
                    ) as response:
                        if response.status != 200:
                            await interaction.response.send_message(f"Warning: Failed to turn pump off while latching (Server status: {response.status}). Latch applied anyway.", ephemeral=True)
                            # Continue latching even if pump off fails
                        # else: Pump turned off successfully
                except Exception as e:
                     await interaction.response.send_message(f"Warning: Error contacting server to turn pump off while latching: {e}. Latch applied anyway.", ephemeral=True)
                     # Continue latching

            # Set up timed unlatch if minutes specified
            if minutes is not None and minutes > 0:
                self.bot.latch_end_time = asyncio.get_event_loop().time() + (minutes * 60)
                # Pass bot object to auto_unlatch
                self.bot.latch_timer = asyncio.create_task(auto_unlatch(self.bot, minutes * 60))
                status_message = f"{status_message} for {minutes} minutes"
                if reason:
                    status_message += f" (Reason: {reason})"
            elif reason: # Latching indefinitely with reason
                 status_message += f" (Reason: {reason})"

        else: # Unlatching
             self.bot.latch_end_time = None # Clear end time when unlatching manually
             self.bot.latch_reason = None # Clear reason when unlatching

        save_session_state(self.bot)
        await self.update_status()
        # Use followup if we sent a warning message before
        if interaction.response.is_done():
             await interaction.followup.send(f"Pump is now {status_message}.", ephemeral=True)
        else:
             await interaction.response.send_message(f"Pump is now {status_message}.", ephemeral=True)


    @app_commands.command(name="setnote", description="Set or clear a note shown in the status when READY (wearer only).")
    @app_commands.check(is_wearer)
    @app_commands.describe(note="The note to display (max 50 chars). Leave blank to clear.")
    async def setnote(self, interaction: discord.Interaction, note: app_commands.Range[str, 0, 50] = None):
        """Set or clear a note shown in the status when READY (wearer only)."""
        if note:
            self.bot.ready_note = note
            response_message = f"Ready note set to: \"{note}\""
        else:
            self.bot.ready_note = None
            response_message = "Ready note cleared."

        save_session_state(self.bot)
        await self.update_status()
        await interaction.response.send_message(response_message, ephemeral=True)

    @app_commands.command(name="bank_time", description="[Wearer Only] Manually add time to the bank.")
    @app_commands.check(is_wearer)
    @app_commands.describe(seconds="Number of seconds to add to the bank.")
    async def bank_time(self, interaction: discord.Interaction, seconds: int):
        """Manually adds time to the banked time pool."""
        if seconds <= 0:
            await interaction.response.send_message("Please provide a positive number of seconds.", ephemeral=True)
            return

        max_bank = self.bot.config.get('max_banked_time', 3600)
        old_banked_time = self.bot.banked_time
        self.bot.banked_time = min(old_banked_time + seconds, max_bank)
        added_time = self.bot.banked_time - old_banked_time

        save_session_state(self.bot)
        logger.info(f"Wearer manually banked {added_time}s. New banked time: {self.bot.banked_time}s.")

        await interaction.response.send_message(
            f"Added {format_time(added_time)} to the bank. "
            f"Total banked time is now {format_time(self.bot.banked_time)}.",
            ephemeral=True
        )
        # Optionally update status immediately
        monitor_cog = self.bot.get_cog("MonitorCog")
        if monitor_cog:
            await monitor_cog.update_bot_status() # type: ignore

    @app_commands.command(name="reset_bank", description="[Wearer Only] Resets the banked time to zero.")
    @app_commands.check(is_wearer)
    async def reset_bank(self, interaction: discord.Interaction):
        """Resets the banked time pool to zero."""
        old_banked_time = self.bot.banked_time
        self.bot.banked_time = 0
        save_session_state(self.bot)
        logger.info(f"Wearer reset banked time from {format_time(old_banked_time)} to 0.")

        await interaction.response.send_message(
            f"Banked time has been reset to 0 (was {format_time(old_banked_time)}).",
            ephemeral=True
        )
        # Update status
        monitor_cog = self.bot.get_cog("MonitorCog")
        if monitor_cog:
            await monitor_cog.update_bot_status() # type: ignore

    @restart.error
    @latch.error
    @set_wearer.error # Although set_wearer doesn't use the check, catch other potential errors
    @setnote.error # Add error handler for setnote
    async def admin_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("Only the device wearer can use this command.", ephemeral=True)
        elif isinstance(error, app_commands.errors.RangeError):
             await interaction.response.send_message(f"Invalid value: {error}", ephemeral=True)
        else:
            print(f"Error in admin command: {error}")
            # Check if response already sent
            if not interaction.response.is_done():
                 await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
            else:
                 # If deferred or already responded, use followup
                 try:
                      await interaction.followup.send("An unexpected error occurred.", ephemeral=True)
                 except discord.errors.NotFound:
                      print("Failed to send followup error message: Interaction not found.")
                 except Exception as e:
                      print(f"Failed to send followup error message: {e}")


async def setup(bot):
  await bot.add_cog(AdminCog(bot))

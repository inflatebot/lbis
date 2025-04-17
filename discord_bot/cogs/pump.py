\
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from utils import is_wearer, dm_wearer_on_use, format_time, update_session_time, start_pump_timer

class PumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_status(self):
        """Helper to trigger status update"""
        monitor_cog = self.bot.get_cog('MonitorCog')
        if monitor_cog:
            await monitor_cog.update_bot_status()

    @app_commands.command(name="pump_on", description="Turn the pump on (wearer only)")
    @app_commands.check(is_wearer)
    @dm_wearer_on_use("pump_on")
    async def pump_on(self, interaction: discord.Interaction):
        """Turn the pump on (wearer only)"""
        if self.bot.latch_active:
            message = "Pump is currently latched, and cannot be turned on."
            if self.bot.latch_reason:
                message += f"\nReason: {self.bot.latch_reason}"
            await interaction.response.send_message(message, ephemeral=True)
            return
        if self.bot.session_time_remaining <= 0:
            await interaction.response.send_message("No session time remaining. Use /add_time to add more time.", ephemeral=True)
            return

        update_session_time(self.bot) # Ensure time is up-to-date before check
        if self.bot.session_time_remaining <= 0:
             await interaction.response.send_message("No session time remaining after update. Use /add_time.", ephemeral=True)
             return

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.bot.API_BASE_URL}/api/setPumpState",
                    json={"pump": 1},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        start_pump_timer(self.bot)
                        await self.update_status()
                        await interaction.response.send_message(f"Pump turned ON! {format_time(self.bot.session_time_remaining)} remaining.")
                    else:
                        await interaction.response.send_message(f"Failed to turn pump on. Server status: {response.status}", ephemeral=True)
            except Exception as e:
                 await interaction.response.send_message(f"Error contacting server: {e}", ephemeral=True)


    @app_commands.command(name="pump_off", description="Turn the pump off")
    @dm_wearer_on_use("pump_off")
    async def pump_off(self, interaction: discord.Interaction):
        """Turn the pump off"""
        update_session_time(self.bot)  # Update remaining time when pump is turned off
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.bot.API_BASE_URL}/api/setPumpState",
                    json={"pump": 0},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        await self.update_status()
                        await interaction.response.send_message(f"Pump turned OFF! {format_time(self.bot.session_time_remaining)} remaining.")
                    else:
                        await interaction.response.send_message(f"Failed to turn pump off. Server status: {response.status}", ephemeral=True)
            except Exception as e:
                 await interaction.response.send_message(f"Error contacting server: {e}", ephemeral=True)


    @app_commands.command(name="pump_timed", description="Turn the pump on for a specified duration (wearer only)")
    @app_commands.check(is_wearer)
    @app_commands.describe(seconds="Duration in seconds to run the pump")
    @dm_wearer_on_use("pump_timed")
    async def pump_timed(self, interaction: discord.Interaction, seconds: int):
        """Turn the pump on for a specified duration (wearer only)"""
        max_duration = self.bot.config.get('max_pump_duration', 60) # Default 60s

        if self.bot.latch_active:
            message = "Pump is currently latched, and cannot be turned on."
            if self.bot.latch_reason:
                message += f"\nReason: {self.bot.latch_reason}"
            await interaction.response.send_message(message, ephemeral=True)
            return

        if seconds <= 0:
            await interaction.response.send_message("Duration must be greater than 0 seconds.", ephemeral=True)
            return

        if seconds > max_duration:
            await interaction.response.send_message(f"Duration cannot exceed the configured maximum of {max_duration} seconds.", ephemeral=True)
            return

        update_session_time(self.bot) # Update time before checks
        if self.bot.session_time_remaining <= 0:
            await interaction.response.send_message("No session time remaining. Use /add_time to add more time.", ephemeral=True)
            return

        # Limit run time to remaining session time
        actual_run_seconds = min(seconds, int(self.bot.session_time_remaining))
        if actual_run_seconds <= 0:
             await interaction.response.send_message("No session time remaining for timed pump.", ephemeral=True)
             return

        if actual_run_seconds < seconds:
             await interaction.response.send_message(f"Warning: Running pump for {actual_run_seconds}s due to remaining session time.", ephemeral=True)
             # Need followup below, so defer
             await interaction.response.defer(ephemeral=False, thinking=True) # Acknowledge interaction
        else:
             await interaction.response.defer(ephemeral=False, thinking=True) # Acknowledge interaction


        pump_on_success = False
        async with aiohttp.ClientSession() as session:
            try:
                # Turn pump on
                async with session.post(
                    f"{self.bot.API_BASE_URL}/api/setPumpState",
                    json={"pump": 1},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        pump_on_success = True
                        start_pump_timer(self.bot)
                        await self.update_status()
                        await interaction.followup.send(f"Pump turned ON for {actual_run_seconds} seconds! {format_time(self.bot.session_time_remaining)} remaining in session.")
                    else:
                        await interaction.followup.send(f"Failed to turn pump on. Server status: {response.status}")
                        return # Don't proceed if pump didn't turn on
            except Exception as e:
                 await interaction.followup.send(f"Error contacting server to turn pump ON: {e}")
                 return # Don't proceed

            if not pump_on_success:
                 return # Exit if pump failed to turn on

            # Wait for specified duration
            await asyncio.sleep(actual_run_seconds)

            # Pump should be off now, update time and state
            update_session_time(self.bot)

            # Turn pump off (even if timer expired, ensure it's off)
            try:
                async with session.post(
                    f"{self.bot.API_BASE_URL}/api/setPumpState",
                    json={"pump": 0},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        await self.update_status()
                        # Check if interaction is still valid before sending followup
                        if interaction.is_expired():
                             print("Interaction expired before sending pump_timed OFF message.")
                        else:
                             await interaction.followup.send(f"Pump turned OFF after timed run! {format_time(self.bot.session_time_remaining)} remaining in session.")
                    else:
                         # Check if interaction is still valid
                         if interaction.is_expired():
                              print(f"Interaction expired. Failed to turn pump off after timeout! Server status: {response.status}")
                         else:
                              await interaction.followup.send(f"Failed to turn pump off after timeout! Server status: {response.status}")
            except Exception as e:
                 # Check if interaction is still valid
                 if interaction.is_expired():
                      print(f"Interaction expired. Error contacting server to turn pump OFF: {e}")
                 else:
                      await interaction.followup.send(f"Error contacting server to turn pump OFF: {e}")


    @pump_on.error
    @pump_timed.error
    async def pump_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("Only the device wearer can use this command.", ephemeral=True)
        else:
            print(f"Error in pump command: {error}")
            if not interaction.response.is_done():
                 await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
            else: # If response already sent (e.g. defer), use followup
                 await interaction.followup.send("An unexpected error occurred.", ephemeral=True)


async def setup(bot):
  await bot.add_cog(PumpCog(bot))

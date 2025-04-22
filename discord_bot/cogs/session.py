\
import discord
from discord.ext import commands
from discord import app_commands
from utils import is_wearer, format_time, update_session_time, save_session_state

class SessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_status(self):
        """Helper to trigger status update"""
        monitor_cog = self.bot.get_cog('MonitorCog')
        if monitor_cog:
            await monitor_cog.update_bot_status()

    @app_commands.command(name="add_time", description="Add time to the current session (wearer only)")
    @app_commands.check(is_wearer)
    @app_commands.describe(minutes="Minutes to add to the session")
    async def add_time(self, interaction: discord.Interaction, minutes: int):
        """Add time to the current session (wearer only)"""
        max_extension = self.bot.config.get('max_session_extension', 3600) # Default 1hr

        if minutes <= 0:
            await interaction.response.send_message("Please specify a positive number of minutes.", ephemeral=True)
            return

        if (minutes * 60) > max_extension:
            await interaction.response.send_message(f"Cannot add more than {max_extension//60} minutes at once (configurable limit).", ephemeral=True)
            return

        update_session_time(self.bot)  # Update current time first
        self.bot.session_time_remaining += (minutes * 60)
        save_session_state(self.bot)
        await self.update_status()
        await interaction.response.send_message(f"Added {minutes} minutes to session. {format_time(self.bot.session_time_remaining)} remaining.", ephemeral=True)

    @app_commands.command(name="reset_time", description="Reset the session timer to the default duration (wearer only)")
    @app_commands.check(is_wearer)
    async def reset_time(self, interaction: discord.Interaction):
        """Reset the session timer to the default duration (wearer only)"""
        # Use the stored default time instead of 0
        self.bot.session_time_remaining = self.bot.default_session_time
        self.bot.session_pump_start = None # Also clear pump start time
        save_session_state(self.bot)
        await self.update_status()
        # Update the response message
        await interaction.response.send_message(f"Session timer has been reset to the default: {format_time(self.bot.session_time_remaining)}.", ephemeral=True)

    @app_commands.command(name="session_time", description="Check remaining session time")
    async def check_time(self, interaction: discord.Interaction):
        """Check remaining session time"""
        update_session_time(self.bot)
        await interaction.response.send_message(f"Session time remaining: {format_time(self.bot.session_time_remaining)}", ephemeral=True)

    @app_commands.command(name="set_time", description="Set the session timer to a specific value (wearer only)")
    @app_commands.check(is_wearer)
    @app_commands.describe(minutes="Minutes to set the session timer to")
    async def set_time(self, interaction: discord.Interaction, minutes: int):
        """Set the session timer to a specific value (wearer only)"""
        max_session = self.bot.config.get('max_session_time', 1800) # Default 30min

        if minutes < 0: # Allow setting to 0
            await interaction.response.send_message("Please specify a non-negative number of minutes.", ephemeral=True)
            return

        if (minutes * 60) > max_session:
            await interaction.response.send_message(f"Cannot set time higher than the configured maximum of {max_session//60} minutes.", ephemeral=True)
            return

        new_time_seconds = minutes * 60
        self.bot.session_time_remaining = new_time_seconds
        # Also update the default session time
        self.bot.default_session_time = new_time_seconds
        self.bot.session_pump_start = None # Clear pump start if setting time manually
        save_session_state(self.bot)
        await self.update_status()
        await interaction.response.send_message(f"Session time set to {format_time(self.bot.session_time_remaining)}.", ephemeral=True)

    @add_time.error
    @reset_time.error
    @set_time.error
    async def session_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("Only the device wearer can use this command.", ephemeral=True)
        else:
            print(f"Error in session command: {error}")
            await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)


async def setup(bot):
  await bot.add_cog(SessionCog(bot))

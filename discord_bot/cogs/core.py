\
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from utils import dm_wearer_on_use, format_time, update_session_time

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="marco", description="Check if the server is responding")
    async def marco(self, interaction: discord.Interaction):
        """Check if the server is responding"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.bot.API_BASE_URL}/api/marco", timeout=5) as response:
                    if response.status == 200:
                        data = await response.text()
                        await interaction.response.send_message(f"Server says: {data}", ephemeral=True)
                    else:
                        await interaction.response.send_message(f"Server responded with status {response.status}", ephemeral=True)
            except asyncio.TimeoutError:
                 await interaction.response.send_message("Failed to reach server: Request timed out.", ephemeral=True)
            except aiohttp.ClientConnectorError:
                 await interaction.response.send_message("Failed to reach server: Connection error.", ephemeral=True)
            except Exception as e:
                 await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)


    @app_commands.command(name="status", description="Check the current device status")
    @dm_wearer_on_use("status")
    async def device_status(self, interaction: discord.Interaction):
        """Check the current device status"""
        update_session_time(self.bot)  # Update session time before displaying

        status_lines = []
        pump_state_text = "Unknown"
        service_reachable = False

        # Check service reachability first
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.bot.API_BASE_URL}/api/getPumpState", timeout=5) as response:
                    if response.status == 200:
                        service_reachable = True
                        state = await response.text()
                        pump_state_text = "ON" if state == "1" else "OFF"
                    else:
                         pump_state_text = f"Error ({response.status})"
            except Exception:
                 pump_state_text = "Unreachable" # Service likely down

        status_lines.append(f"🔌 Pump: {pump_state_text}")
        status_lines.append(f"⏲️ Session: {format_time(self.bot.session_time_remaining)} remaining")

        if self.bot.latch_active:
            latch_msg = "🔒 Pump is latched"
            if self.bot.latch_reason:
                latch_msg += f": {self.bot.latch_reason}"
            # Indicate if timed
            if self.bot.latch_end_time:
                 remaining_latch_time = self.bot.latch_end_time - asyncio.get_event_loop().time()
                 if remaining_latch_time > 0:
                      latch_msg += f" (expires in {format_time(remaining_latch_time)})"
            status_lines.append(latch_msg)
        else:
             status_lines.append("🔓 Pump is unlatched")


        await interaction.response.send_message("\n".join(status_lines)) # Keep status public


async def setup(bot):
  await bot.add_cog(CoreCog(bot))

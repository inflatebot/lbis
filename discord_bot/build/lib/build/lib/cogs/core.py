import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from utils import dm_wearer_on_use, format_time, update_session_time, api_request, is_wearer

logger = logging.getLogger(__name__)

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="marco", description="Check if the server is responding")
    async def marco(self, interaction: discord.Interaction):
        """Check if the server is responding"""
        try:
            async with aiohttp.ClientSession() as session:
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

    @app_commands.command(name="status", description="Shows the current status of the bot and session.")
    async def status(self, interaction: discord.Interaction):
        """Displays the current status."""
        # Check service reachability first
        api_status = "Unknown"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.bot.API_BASE_URL}/api/getPumpState", timeout=5) as response:
                    if response.status == 200:
                        api_status = "Reachable"
                    else:
                        api_status = f"Error ({response.status})"
        except Exception:
            api_status = "Unreachable"  # Service likely down

        # Session Info
        session_time_str = format_time(self.bot.session_time_remaining)
        banked_time_str = format_time(self.bot.banked_time)
        latch_status = "Latched" if self.bot.latch_active else "Unlatched"
        pump_status = "Unknown"
        
        if self.bot.last_pump_time:
            # Check if a pump task is running
            if self.bot.pump_task and not self.bot.pump_task.done():
                pump_status = "ON (Timed/Banked)"
            else:
                # Check API for actual pump state if no task is running
                pump_state = await api_request(self.bot, "getPumpState")
                if pump_state is not None:
                    try:
                        # Handle both text ("0"/"1") and JSON responses
                        if isinstance(pump_state, dict):
                            pump_status = "ON" if pump_state.get('is_on') else "OFF"
                        else:
                            # Try to convert text value to bool
                            try:
                                is_on = bool(int(str(pump_state)))
                                pump_status = "ON" if is_on else "OFF"
                            except (ValueError, TypeError):
                                pump_status = "UNKNOWN"
                    except Exception as e:
                        logger.error(f"Failed to parse pump state: {e}")
                        pump_status = "UNKNOWN"
                else:
                    pump_status = "OFF (API check failed)"
        else:
            pump_status = "OFF (Never run)"

        embed = discord.Embed(title="lBIS Status", color=discord.Color.blue())
        embed.add_field(name="API Service", value=api_status, inline=False)
        embed.add_field(name="Session Time", value=session_time_str, inline=True)
        embed.add_field(name="Banked Time", value=banked_time_str, inline=True)
        embed.add_field(name="Latch", value=latch_status, inline=True)
        embed.add_field(name="Pump", value=pump_status, inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CoreCog(bot))

import asyncio
import logging
import time
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import (
    api_request, format_time, is_wearer, save_session_state, dm_wearer_on_use,
    update_session_time
)

logger = logging.getLogger(__name__)

class PumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_unload(self):
        if self.bot.pump_task and not self.bot.pump_task.done():
            self.bot.pump_task.cancel()
            logger.info("Cancelled running pump task on cog unload.")

    async def _timed_pump_loop(self, initial_run_seconds: int):
        start_time = asyncio.get_event_loop().time()
        actual_run_duration = 0
        interrupted = False
        interruption_reason = ""

        try:
            logger.info(f"Starting timed pump loop. Target end time: {self.bot.pump_task_end_time}")
            while asyncio.get_event_loop().time() < self.bot.pump_task_end_time:
                if self.bot.latch_active:
                    interrupted = True
                    interruption_reason = "latched"
                    logger.info("Pump latched during timed pump.")
                    break
                if not self.bot.service_was_up:
                    interrupted = True
                    interruption_reason = "service down"
                    logger.info("API service went down during timed pump.")
                    break

                await asyncio.sleep(0.5)

            actual_run_duration = asyncio.get_event_loop().time() - start_time
            logger.info(f"Timed pump loop finished or interrupted after {actual_run_duration:.2f}s.")

            if interrupted:
                remaining_intended = self.bot.pump_task_end_time - asyncio.get_event_loop().time()
                if remaining_intended > 0:
                    max_bank = self.bot.config.get('max_banked_time', 3600)
                    old_banked = self.bot.banked_time
                    self.bot.banked_time = min(old_banked + int(remaining_intended), max_bank)
                    banked_amount = self.bot.banked_time - old_banked
                    if banked_amount > 0:
                        logger.info(f"Banking {banked_amount}s due to interruption ({interruption_reason}).")

        except asyncio.CancelledError:
            logger.info("Timed pump task cancelled.")
            actual_run_duration = asyncio.get_event_loop().time() - start_time
            interrupted = True
            interruption_reason = "cancelled"
        finally:
            logger.info("Timed pump loop cleanup.")
            if await api_request(self.bot, "pump/off", method="POST"):
                logger.info("Pump turned off via API after timed session.")
                self.bot.last_pump_time = time.time()
            else:
                logger.error("Failed to turn off pump via API after timed session.")

            update_session_time(self.bot, -int(actual_run_duration))

            self.bot.pump_task = None
            self.bot.pump_task_end_time = None

            save_session_state(self.bot)

            monitor_cog = self.bot.get_cog("MonitorCog")
            if monitor_cog:
                await monitor_cog.update_bot_status()

            if interrupted:
                logger.warning(f"Timed pump interrupted due to: {interruption_reason}. Ran for {format_time(int(actual_run_duration))}.")
            else:
                logger.info(f"Timed pump completed successfully. Ran for {format_time(int(actual_run_duration))}.")

    async def _banked_pump_loop(self, initial_run_seconds: int):
        start_time = asyncio.get_event_loop().time()
        actual_run_duration = 0
        interrupted = False
        interruption_reason = ""
        decremented_bank = 0
        decremented_session = 0

        try:
            logger.info(f"Starting banked pump loop. Target end time: {self.bot.pump_task_end_time}")
            last_decrement_time = start_time

            while asyncio.get_event_loop().time() < self.bot.pump_task_end_time:
                if self.bot.latch_active:
                    interrupted = True
                    interruption_reason = "latched"
                    logger.info("Pump latched during banked pump.")
                    break
                if not self.bot.service_was_up:
                    interrupted = True
                    interruption_reason = "service down"
                    logger.info("API service went down during banked pump.")
                    break
                if self.bot.banked_time <= 0:
                    interrupted = True
                    interruption_reason = "bank empty"
                    logger.info("Bank ran out during banked pump.")
                    break
                if self.bot.session_time_remaining <= 0:
                    interrupted = True
                    interruption_reason = "session empty"
                    logger.info("Session time ran out during banked pump.")
                    break

                current_time = asyncio.get_event_loop().time()
                elapsed_since_decrement = current_time - last_decrement_time
                if elapsed_since_decrement >= 1.0:
                    decrement_amount = int(elapsed_since_decrement)
                    actual_decrement = min(decrement_amount, self.bot.banked_time, self.bot.session_time_remaining)

                    if actual_decrement > 0:
                        self.bot.banked_time -= actual_decrement
                        decremented_bank += actual_decrement
                        decremented_session += actual_decrement
                        last_decrement_time = current_time
                    else:
                        interrupted = True
                        interruption_reason = "bank or session empty on decrement"
                        logger.info("Stopping banked pump as bank or session reached zero during decrement check.")
                        break

                await asyncio.sleep(0.2)

            actual_run_duration = asyncio.get_event_loop().time() - start_time
            logger.info(f"Banked pump loop finished or interrupted after {actual_run_duration:.2f}s.")

        except asyncio.CancelledError:
            logger.info("Banked pump task cancelled.")
            actual_run_duration = asyncio.get_event_loop().time() - start_time
            interrupted = True
            interruption_reason = "cancelled"
        finally:
            logger.info("Banked pump loop cleanup.")
            if await api_request(self.bot, "pump/off", method="POST"):
                logger.info("Pump turned off via API after banked session.")
                self.bot.last_pump_time = time.time()
            else:
                logger.error("Failed to turn off pump via API after banked session.")

            update_session_time(self.bot, -decremented_session)

            self.bot.pump_task = None
            self.bot.pump_task_end_time = None

            save_session_state(self.bot)

            monitor_cog = self.bot.get_cog("MonitorCog")
            if monitor_cog:
                await monitor_cog.update_bot_status()

            if interrupted:
                logger.warning(f"Banked pump interrupted due to: {interruption_reason}. Ran for {format_time(int(actual_run_duration))}, consumed {format_time(decremented_bank)} bank & session time.")
            else:
                logger.info(f"Banked pump completed successfully. Ran for {format_time(int(actual_run_duration))}, consumed {format_time(decremented_bank)} bank & session time.")

    @app_commands.command(name="pump_timed", description="Runs the pump for a specific duration.")
    @app_commands.describe(minutes="Number of minutes to run the pump.")
    @dm_wearer_on_use("pump_timed")
    async def pump_timed(self, interaction: discord.Interaction, minutes: int):
        seconds = minutes * 60
        max_pump_duration = self.bot.config.get('max_pump_duration', 60)

        if seconds <= 0:
            await interaction.response.send_message("Please provide a positive duration.", ephemeral=True)
            return

        if self.bot.latch_active:
            await interaction.response.send_message("Pump is latched, cannot start timed pump.", ephemeral=True)
            return

        if not self.bot.service_was_up:
            await interaction.response.send_message("API service is down, cannot control pump.", ephemeral=True)
            return

        loop = asyncio.get_event_loop()
        current_time = loop.time()
        max_bank = self.bot.config.get('max_banked_time', 3600)
        response_message = ""

        if self.bot.pump_task and not self.bot.pump_task.done():
            logger.info(f"Pump task already running. Extending timer.")
            remaining_current = max(0, self.bot.pump_task_end_time - current_time)
            new_total_req = remaining_current + seconds
            max_possible_additional = max(0, self.bot.session_time_remaining - remaining_current)
            max_possible_duration = min(remaining_current + max_possible_additional, max_pump_duration)

            time_to_add = max(0, max_possible_duration - remaining_current)
            overflow = max(0, seconds - time_to_add)

            banked_amount = 0
            if overflow > 0:
                old_banked = self.bot.banked_time
                self.bot.banked_time = min(old_banked + int(overflow), max_bank)
                banked_amount = self.bot.banked_time - old_banked
                if banked_amount > 0:
                    logger.info(f"Banking {banked_amount}s overflow from pump_timed extension.")
                    save_session_state(self.bot)

            self.bot.pump_task_end_time = current_time + remaining_current + time_to_add
            logger.info(f"Extended pump task. New end time: {self.bot.pump_task_end_time}. Added: {time_to_add:.2f}s.")

            response_message = f"Pump timer already running. Extended by {format_time(int(time_to_add))}."
            if banked_amount > 0:
                response_message += f" Banked {format_time(banked_amount)} overflow (max session/pump duration reached)."
            if time_to_add < seconds and banked_amount == 0:
                response_message += f" Could not add full duration due to session/pump limits."

            await interaction.response.send_message(response_message)

        else:
            if self.bot.session_time_remaining <= 0:
                await interaction.response.send_message("No session time remaining.", ephemeral=True)
                return

            run_seconds = min(seconds, self.bot.session_time_remaining, max_pump_duration)

            if run_seconds <= 0:
                await interaction.response.send_message("Cannot run pump (calculated duration is zero).", ephemeral=True)
                return

            logger.info(f"Starting new timed pump for {run_seconds}s.")
            if await api_request(self.bot, "pump/on", method="POST"):
                self.bot.last_pump_time = time.time()
                self.bot.pump_task_end_time = current_time + run_seconds
                self.bot.pump_task = asyncio.create_task(self._timed_pump_loop(run_seconds))

                response_message = f"Pump started for {format_time(run_seconds)}."
                if run_seconds < seconds:
                    response_message += f" (Limited by session time or max duration)."
                await interaction.response.send_message(response_message)

                monitor_cog = self.bot.get_cog("MonitorCog")
                if monitor_cog:
                    await monitor_cog.update_bot_status()
            else:
                await interaction.response.send_message("Failed to start pump via API.", ephemeral=True)

    @app_commands.command(name="pump_banked", description="Runs the pump using banked time.")
    @app_commands.describe(minutes="Maximum number of minutes to run using banked time.")
    @dm_wearer_on_use("pump_banked")
    async def pump_banked(self, interaction: discord.Interaction, minutes: int):
        seconds = minutes * 60
        max_pump_duration = self.bot.config.get('max_pump_duration', 60)

        if seconds <= 0:
            await interaction.response.send_message("Please provide a positive duration.", ephemeral=True)
            return

        if self.bot.latch_active:
            await interaction.response.send_message("Pump is latched, cannot start banked pump.", ephemeral=True)
            return

        if not self.bot.service_was_up:
            await interaction.response.send_message("API service is down, cannot control pump.", ephemeral=True)
            return

        if self.bot.pump_task and not self.bot.pump_task.done():
            await interaction.response.send_message("Another pump operation is already running.", ephemeral=True)
            return

        if self.bot.banked_time <= 0:
            await interaction.response.send_message("No time in the bank.", ephemeral=True)
            return

        if self.bot.session_time_remaining <= 0:
            await interaction.response.send_message("No session time remaining (required to use bank).", ephemeral=True)
            return

        run_seconds = min(seconds, self.bot.banked_time, self.bot.session_time_remaining, max_pump_duration)

        if run_seconds <= 0:
            await interaction.response.send_message("Cannot run pump (calculated duration is zero based on available time).", ephemeral=True)
            return

        logger.info(f"Starting banked pump for {run_seconds}s.")
        if await api_request(self.bot, "pump/on", method="POST"):
            self.bot.last_pump_time = time.time()
            self.bot.pump_task_end_time = asyncio.get_event_loop().time() + run_seconds
            self.bot.pump_task = asyncio.create_task(self._banked_pump_loop(run_seconds))

            response_message = f"Pump started using banked time for {format_time(run_seconds)}."
            if run_seconds < seconds:
                response_message += f" (Limited by bank, session time, or max duration)."
            await interaction.response.send_message(response_message)

            monitor_cog = self.bot.get_cog("MonitorCog")
            if monitor_cog:
                await monitor_cog.update_bot_status()
        else:
            await interaction.response.send_message("Failed to start pump via API.", ephemeral=True)

    @app_commands.command(name="pump_on", description="[Wearer Only] Manually turns the pump on indefinitely.")
    @app_commands.check(is_wearer)
    @dm_wearer_on_use("pump_on")
    async def pump_on(self, interaction: discord.Interaction):
        if self.bot.pump_task and not self.bot.pump_task.done():
            self.bot.pump_task.cancel()
            logger.info("Cancelled running pump task due to manual pump_on.")

        if await api_request(self.bot, "pump/on", method="POST"):
            self.bot.last_pump_time = time.time()
            save_session_state(self.bot)
            await interaction.response.send_message("Pump turned ON.", ephemeral=True)
            monitor_cog = self.bot.get_cog("MonitorCog")
            if monitor_cog:
                await monitor_cog.update_bot_status()
        else:
            await interaction.response.send_message("Failed to turn pump ON via API.", ephemeral=True)

    @app_commands.command(name="pump_off", description="[Wearer Only] Manually turns the pump off.")
    @app_commands.check(is_wearer)
    @dm_wearer_on_use("pump_off")
    async def pump_off(self, interaction: discord.Interaction):
        if self.bot.pump_task and not self.bot.pump_task.done():
            self.bot.pump_task.cancel()
            logger.info("Cancelled running pump task due to manual pump_off.")

        if await api_request(self.bot, "pump/off", method="POST"):
            self.bot.last_pump_time = time.time()
            save_session_state(self.bot)
            await interaction.response.send_message("Pump turned OFF.", ephemeral=True)
            monitor_cog = self.bot.get_cog("MonitorCog")
            if monitor_cog:
                await monitor_cog.update_bot_status()
        else:
            await interaction.response.send_message("Failed to turn pump OFF via API.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PumpCog(bot))

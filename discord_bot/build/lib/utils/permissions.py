import discord
import asyncio
import functools

# --- Permissions & Notifications ---

def is_wearer(interaction: discord.Interaction) -> bool:
    # Assumes OWNER_ID is attached to the bot object
    # Accessing client through interaction which holds the bot instance
    return interaction.user.id == interaction.client.OWNER_ID

async def notify_wearer(bot, interaction: discord.Interaction, command_name: str):
    if not bot.OWNER_ID or interaction.user.id == bot.OWNER_ID:
        return  # Don't notify if no owner set or if owner uses command

    try:
        wearer = await bot.fetch_user(bot.OWNER_ID)
        if wearer:
            location = "Direct Messages" if interaction.guild is None else f"{interaction.guild.name} / #{interaction.channel.name}"
            user_info = f"{interaction.user} ({interaction.user.id})"

            # Get command parameters
            params = []
            if interaction.data and "options" in interaction.data:
                for option in interaction.data.get("options", []):
                    params.append(f"{option['name']}:{option['value']}")
            param_str = " " + " ".join(params) if params else ""

            await wearer.send(
                f"Command `{command_name}{param_str}` used by {user_info} in {location}."
            )
    except Exception as e:
        print(f"Failed to notify wearer: {e}")

def dm_wearer_on_use(command_name):
    """Decorator to notify the wearer when a command is used."""
    def decorator(func):
        # Ensure the decorated function is recognized as a command callback
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Decorated function must be a coroutine.")

        @functools.wraps(func)
        async def wrapper(cog_instance, interaction: discord.Interaction, *args, **kwargs):
            # Pass 'cog_instance.bot' instead of just 'bot'
            await notify_wearer(cog_instance.bot, interaction, command_name)
            # Call the original command function
            return await func(cog_instance, interaction, *args, **kwargs)
        return wrapper
    return decorator

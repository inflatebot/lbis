import asyncio
from .state_persistence import save_session_state

# --- Latch Management ---

async def auto_unlatch(bot, delay):
    """Automatically unlatch after specified delay"""
    await asyncio.sleep(delay)
    if bot.latch_timer:  # Check if it wasn't cancelled
        bot.latch_active = False
        bot.latch_timer = None
        bot.latch_end_time = None
        bot.latch_reason = None  # Clear reason on auto-unlatch
        save_session_state(bot) # Use the imported function
        print("Timed latch expired.")
        if bot.OWNER_ID:
            try:
                wearer = await bot.fetch_user(bot.OWNER_ID)
                await wearer.send("Timed latch has expired - pump is now unlatched.")
                # Trigger status update after state change using the bot method
                await bot.request_status_update()
            except Exception as e:
                print(f"Failed to notify wearer of auto-unlatch: {e}")

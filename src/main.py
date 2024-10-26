import os
from dotenv import load_dotenv
import asyncio
from bot.bot import create_bot
from bot.events import setup_events

load_dotenv()
TOKEN = os.getenv('TOKEN')

async def main():
    # Create bot instance
    bot = create_bot()
    
    # Setup events
    await setup_events(bot)
    
    # Load cogs
    await bot.load_extension('cogs.explain')
    
    # Run bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        print(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())

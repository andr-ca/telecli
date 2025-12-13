"""
TeleCLI - Main entry point
"""
import asyncio
import logging
from src.config import Config
from src.logger import setup_logging, get_logger
from src.telegram_bot import main as run_telegram_bot


async def main():
    """Main entry point"""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        exit(1)
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info("TeleCLI - Terminal access via Web and Telegram")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  - Telegram Bot: {'Enabled' if Config.TELEGRAM_BOT_TOKEN else 'Disabled'}")
    logger.info(f"  - Logging Level: {Config.LOG_LEVEL}")
    logger.info(f"  - Log Output: {Config.LOG_OUTPUT}")
    logger.info(f"  - Log File Mode: {Config.LOG_FILE_MODE}")
    logger.info(f"  - Terminal Shell: {Config.TERMINAL_SHELL}")
    logger.info("=" * 60)
    
    # Run Telegram bot
    await run_telegram_bot()


if __name__ == "__main__":
    asyncio.run(main())

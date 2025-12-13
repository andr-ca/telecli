"""
TeleCLI - Main entry point
"""
import asyncio
import logging
import uvicorn
from src.config import Config
from src.logger import setup_logging, get_logger
from src.telegram_bot import main as run_telegram_bot
from src.web_app import app as web_app


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
    logger.info(f"  - Telegram Webhook: {Config.TELEGRAM_WEBHOOK_URL or 'Not configured (polling mode)'}")
    logger.info(f"  - Web Host: {Config.WEB_HOST}")
    logger.info(f"  - Web Port: {Config.WEB_PORT}")
    logger.info(f"  - Logging Level: {Config.LOG_LEVEL}")
    logger.info(f"  - Log Output: {Config.LOG_OUTPUT}")
    logger.info(f"  - Log File Mode: {Config.LOG_FILE_MODE}")
    logger.info(f"  - Terminal Shell: {Config.TERMINAL_SHELL}")
    logger.info("=" * 60)
    
    # Create tasks for both web server and Telegram bot
    logger.info("Starting web server and Telegram bot...")
    
    # Create web server task
    config = uvicorn.Config(
        web_app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Run both concurrently
    try:
        await asyncio.gather(
            server.serve(),
            run_telegram_bot(),
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application interrupted, shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

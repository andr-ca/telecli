"""
TeleCLI - Main entry point
"""
import asyncio
import logging
import uvicorn
from src.config import Config
from src.logger import setup_logging, get_logger
from src.session_manager import SessionManager
import src.telegram_bot as telegram_bot
import src.web_app as web_app_module


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
    telegram_enabled = bool(Config.TELEGRAM_BOT_TOKEN)
    telegram_webhook_mode = bool(Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_WEBHOOK_URL)

    startup_targets = ["web server"]
    if telegram_enabled and not telegram_webhook_mode:
        startup_targets.append("Telegram bot")
    elif not telegram_enabled:
        logger.info("Telegram bot is disabled because TELEGRAM_BOT_TOKEN is not configured")
    else:
        logger.warning(
            "Telegram bot is not started from the combined entrypoint in webhook mode because it would bind WEB_PORT=%s twice. "
            "Run the Telegram bot separately for webhook deployments.",
            Config.WEB_PORT,
        )

    logger.info(f"Starting {' and '.join(startup_targets)}...")

    shared_session_manager = SessionManager()
    web_app_module.set_session_manager(shared_session_manager, managed=False)
    telegram_bot.set_session_manager(shared_session_manager)

    # Create web server task
    config = uvicorn.Config(
        web_app_module.app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="info",
        ssl_certfile=Config.WEB_SSL_CERT if Config.WEB_SSL_CERT else None,
        ssl_keyfile=Config.WEB_SSL_KEY if Config.WEB_SSL_KEY else None,
        access_log=True,
        server_header=False,
        date_header=False,
        forwarded_allow_ips="*",  # Allow forwarded headers from any IP (for Cloudflare)
        proxy_headers=True,       # Trust proxy headers
    )
    server = uvicorn.Server(config)
    
    telegram_task = None

    def _on_telegram_done(task: asyncio.Task) -> None:
        # This callback runs in the event loop thread; it must not be async.
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            # Task was cancelled as part of shutdown; no further action needed.
            return
        if exc is None:
            logger.info("Telegram bot task finished normally; stopping web server.")
        else:
            logger.error("Telegram bot task stopped with error: %s", exc)
        # Trigger graceful shutdown of the uvicorn server.
        server.should_exit = True

    # Run services, and tie Telegram lifecycle to the web server process.
    try:
        if telegram_enabled and not telegram_webhook_mode:
            telegram_task = asyncio.create_task(telegram_bot.main(shared_session_manager))
            telegram_task.add_done_callback(_on_telegram_done)
            # Let the event loop run once so failures during Telegram startup surface immediately.
            await asyncio.sleep(0)
            if telegram_task.done():
                exc = telegram_task.exception()
                if exc is not None:
                    logger.error("Telegram bot failed to start: %s", exc)
                    raise exc

        await server.serve()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application interrupted, shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        if telegram_task:
            if not telegram_task.done():
                telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass
            except SystemExit:
                pass
            except Exception as e:
                logger.error("Telegram bot task stopped with error during shutdown: %s", e)

        await shared_session_manager.close_all()
        web_app_module.set_session_manager(None, managed=False)
        telegram_bot.set_session_manager(None)


if __name__ == "__main__":
    asyncio.run(main())

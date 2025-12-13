"""
Telegram bot integration
"""
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from src.session_manager import SessionManager
from src.config import Config

logger = logging.getLogger(__name__)

# Global session manager
session_manager: SessionManager = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Welcome to TeleCLI! Your session ID is {user_id}.\n"
        f"Send any command and I'll execute it for you.\n\n"
        f"Commands:\n"
        f"/help - Show this help message\n"
        f"/reset - Reset your terminal session\n"
    )
    logger.info(f"User {user_id} started bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    await update.message.reply_text(
        "TeleCLI - Terminal access via Telegram\n\n"
        "Just send me any shell command and I'll execute it.\n\n"
        "Commands:\n"
        "/start - Show welcome message\n"
        "/reset - Reset your session\n"
        "/help - Show this message\n"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command"""
    user_id = str(update.effective_user.id)
    try:
        await session_manager.close_session(user_id)
        await update.message.reply_text("✅ Session reset successfully")
        logger.info(f"User {user_id} reset session")
    except Exception as e:
        await update.message.reply_text(f"❌ Error resetting session: {str(e)}")
        logger.error(f"Error resetting session for {user_id}: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular messages (commands)"""
    user_id = str(update.effective_user.id)
    command = update.message.text

    try:
        await update.message.chat.send_action("typing")
        
        output = await session_manager.send_command(user_id, command)
        
        # Split long messages (Telegram limit is 4096)
        if len(output) > 4000:
            for i in range(0, len(output), 4000):
                chunk = output[i:i+4000]
                await update.message.reply_text(f"```\n{chunk}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")
        
        logger.info(f"User {user_id} executed command: {command[:50]}...")
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Error executing command for {user_id}: {e}")


async def main():
    """Main entry point for Telegram bot"""
    global session_manager
    
    # Initialize session manager
    session_manager = SessionManager()
    
    # Create bot application
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Starting Telegram bot")
    
    # Start bot
    await app.initialize()
    await app.start()
    
    if Config.TELEGRAM_WEBHOOK_URL:
        # Webhook mode
        logger.info(f"Starting bot with webhook: {Config.TELEGRAM_WEBHOOK_URL}")
        await app.start_webhook(
            listen="0.0.0.0",
            port=Config.WEB_PORT,
            url_path=Config.TELEGRAM_BOT_TOKEN,
            webhook_url=f"{Config.TELEGRAM_WEBHOOK_URL}/{Config.TELEGRAM_BOT_TOKEN}",
        )
    else:
        # Polling mode
        logger.info("Starting bot with polling mode")
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    try:
        # Keep bot running
        await app.updater.stop()
    except KeyboardInterrupt:
        logger.info("Bot interrupted")
    finally:
        await session_manager.close_all()
        await app.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

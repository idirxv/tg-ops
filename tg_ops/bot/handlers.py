"""Telegram bot handlers."""
# pylint: disable=unused-argument

import logging
from functools import wraps

from telegram import BotCommand, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tg_ops.bot.commands.executors import ShellService
from tg_ops.bot.commands.services import DockerManager, SystemService
from tg_ops.bot.ui.menus import MenuBuilder, TextRenderer
from tg_ops.config import Config

logger = logging.getLogger(__name__)

WAITING_SHELL_CMD = 1

ADMIN_ID = 123456789


def restricted(func):
    """Decorator to restrict access to admin."""

    @wraps(func)
    async def wrapped(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("Access denied. You are not the administrator.")
            logging.warning(f"Access denied by {user_id} on {func.__name__}")
            return
        return await func(self, update, context, *args, **kwargs)

    return wrapped


class BotHandlers:
    """Main bot handlers class."""

    def __init__(self, cfg: Config):
        self.shell_service = ShellService()
        self.docker_manager = DockerManager(self.shell_service, cfg)
        self.system_service = SystemService(self.shell_service, cfg)
        self.cfg = cfg

    # --- Basic Commands ---

    async def ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ping command."""
        if not update.message:
            return
        await update.message.reply_text("Pong")

    # @restricted
    async def uptime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        code, out, err = await self.shell_service.execute("uptime")
        text = f"```\n{out}\n```" if code == 0 else f"Error: {err}"
        await update.message.reply_text(text, parse_mode="Markdown")

    # @restricted
    async def reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Execute the 'reboot' command."""
        if not update.message:
            return
        await update.message.reply_text("Reboot not implemented yet.", parse_mode="Markdown")

    # @restricted
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_chat_action("typing")
        snapshot = await self.system_service.get_system_snapshot()
        msg = TextRenderer.system_status(snapshot)
        await update.message.reply_text(msg, parse_mode="Markdown")

    # --- Shell Execution Flow ---

    # @restricted
    async def exec_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Entry point for /exec."""
        if not update.message:
            return ConversationHandler.END

        # CASE 1 : Command is provided as an argument
        if context.args:
            command = " ".join(context.args)
            await update.message.reply_text(f"Executing : `{command}`...", parse_mode="Markdown")
            code, out, err = await self.shell_service.execute(command)
            text = f"```\n{out}\n```" if code == 0 else f"Error: {err}"
            await update.message.reply_text(text, parse_mode="Markdown")
            return ConversationHandler.END

        # CASE 2 : No arguments, ask the user for a command
        await update.message.reply_text("Enter a shell command (/cancel to abort):")
        return WAITING_SHELL_CMD

    async def exec_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """This function is called in WAITING_SHELL_CMD state and receives text."""
        if not update.message or not update.message.text:
            return ConversationHandler.END

        command = update.message.text

        await update.message.reply_text(f"Executing : `{command}`...", parse_mode="Markdown")
        code, out, err = await self.shell_service.execute(command)
        text = f"```\n{out}\n```" if code == 0 else f"Error: {err}"
        await update.message.reply_text(text, parse_mode="Markdown")

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the current conversation."""
        if not update.message:
            return ConversationHandler.END
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

    # --- Docker Management ---

    async def docker(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Entry point /docker"""
        if not update.message:
            return
        active_containers = await self.docker_manager.get_active_containers()
        reply_markup = MenuBuilder.main_docker_menu(active_containers, self.cfg)
        await update.message.reply_text(
            text=TextRenderer.docker_menu_header(), reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button clicks."""
        query = update.callback_query
        if not query:
            return
        await query.answer()

        action = query.data or ""

        if action == "close_menu":
            await query.delete_message()
            return

        elif action == "goto_docker_list":
            active = await self.docker_manager.get_active_containers()
            await query.edit_message_text(
                text=TextRenderer.docker_menu_header(),
                reply_markup=MenuBuilder.main_docker_menu(active, self.cfg),
                parse_mode="Markdown",
            )
            return

        elif action.startswith("docker:"):
            _, container_name = action.split(":")
            is_running = await self.docker_manager.is_container_running(container_name)
            await query.edit_message_text(
                text=TextRenderer.container_details(container_name, is_running),
                reply_markup=MenuBuilder.container_actions_menu(container_name, is_running),
                parse_mode="Markdown",
            )

        elif action.startswith("docker_action:"):
            parts = action.split(":")
            if len(parts) >= 3:
                action_type = parts[1]
                container_name = parts[2]

                try:
                    await query.edit_message_text(
                        text=f"Performing *{action_type.upper()}* on {container_name}",
                        reply_markup=MenuBuilder.progress_button(f"{action_type.capitalize()}ing"),
                        parse_mode="Markdown",
                    )
                except BadRequest:
                    pass

                success = await self.docker_manager.perform_action(action_type, container_name)
                if success:
                    # Refresh Menu
                    active = await self.docker_manager.get_active_containers()
                    await query.edit_message_text(
                        text=TextRenderer.docker_menu_header(),
                        reply_markup=MenuBuilder.main_docker_menu(active, self.cfg),
                        parse_mode="Markdown",
                    )
                else:
                    await query.edit_message_text(
                        text=f"❌ Failed to {action_type} {container_name}.",
                        reply_markup=MenuBuilder.container_actions_menu(container_name, False),
                        parse_mode="Markdown",
                    )
            else:
                await query.edit_message_text(
                    "Invalid docker action format.", parse_mode="Markdown"
                )


async def post_init(application: Application):
    """Set bot commands on startup."""
    commands = [
        BotCommand("ping", "Ping the bot"),
        BotCommand("exec", "Execute a shell command"),
        BotCommand("uptime", "Show server load"),
        BotCommand("status", "Show server status"),
        BotCommand("docker", "Manage Docker containers"),
        BotCommand("reboot", "Reboot the server"),
    ]

    await application.bot.set_my_commands(commands)


def register_handlers(application: Application, cfg: Config) -> None:
    """Register bot handlers."""
    handlers = BotHandlers(cfg)
    # Set post-initialization callback (menu button)
    application.post_init = post_init

    # Command handlers
    application.add_handler(CommandHandler("ping", handlers.ping))
    application.add_handler(CommandHandler("uptime", handlers.uptime))
    application.add_handler(CommandHandler("reboot", handlers.reboot))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("docker", handlers.docker))

    # Conversation handler for shell command execution
    exec_conv = ConversationHandler(
        entry_points=[CommandHandler("exec", handlers.exec_entry)],
        states={
            WAITING_SHELL_CMD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.exec_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
    )
    application.add_handler(exec_conv)

    # Callback query handler for inline button interactions
    application.add_handler(CallbackQueryHandler(handlers.button_handler))

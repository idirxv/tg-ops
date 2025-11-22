"""Telegram inline keyboard menus."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tg_ops.bot.commands.services import SystemSnapshot
from tg_ops.config import Config

logger = logging.getLogger(__name__)


class MenuBuilder:
    """Builder class for creating telegram inline keyboards."""

    @staticmethod
    def main_docker_menu(active_containers: list[str], cfg: Config) -> InlineKeyboardMarkup:
        """Create the docker menu keyboard."""
        keyboard = []
        monitored_containers = list(cfg.monitored_containers)

        for container in monitored_containers:
            is_active = container in active_containers
            icon = "🟢" if is_active else "🔴"

            keyboard.append(
                [InlineKeyboardButton(f"{icon} {container}", callback_data=f"docker:{container}")]
            )

        keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def container_actions_menu(container_name: str, is_running: bool) -> InlineKeyboardMarkup:
        """Create container action menu based on container state."""
        keyboard = []

        if is_running:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🔄 Restart", callback_data=f"docker_action:restart:{container_name}"
                    ),
                    InlineKeyboardButton(
                        "📄 Logs", callback_data=f"docker_action:logs:{container_name}"
                    ),
                ]
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⏹️ Stop", callback_data=f"docker_action:stop:{container_name}"
                    )
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "▶️ Start", callback_data=f"docker_action:start:{container_name}"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("⬅️ Back", callback_data="goto_docker_list"),
                InlineKeyboardButton("❌ Close", callback_data="close_menu"),
            ]
        )
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def progress_button(label: str) -> InlineKeyboardMarkup:
        """Create a temporary progress menu."""
        keyboard = [[InlineKeyboardButton(label, callback_data="ignore")]]
        return InlineKeyboardMarkup(keyboard)


class TextRenderer:
    """Formats text messages for the bot."""

    @staticmethod
    def docker_menu_header() -> str:
        return "🐳 *Docker Containers Management*"

    @staticmethod
    def container_details(name: str, is_running: bool) -> str:
        status = "Running" if is_running else "Stopped"
        icon = "🟢" if is_running else "🔴"
        return f"📦 Container: *{name}*\nStatus: {icon} {status}"

    @staticmethod
    def system_status(snap: SystemSnapshot) -> str:
        disks_text = "\n".join(snap.disks)
        services_text = ""
        for svc, active in snap.services.items():
            icon = "🟢" if active else "🔴"
            services_text += f"{icon} **{svc}** : {'Online' if active else 'Offline'}\n"

        return (
            "**System Status**\n"
            f"CPU : `{snap.cpu_percent}%`\n"
            f"RAM : `{snap.ram_used:.1f}/{snap.ram_total:.1f} Go` ({snap.ram_percent}%)\n\n"
            f"Disks : \n{disks_text}\n\n"
            "**Services**\n"
            f"{services_text}"
        )

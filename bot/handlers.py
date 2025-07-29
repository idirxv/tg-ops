from telegram.ext import CommandHandler, Dispatcher
from bot.services import fail2ban_service

def register_handlers():
    from app import dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("startfail2ban", fail2ban_service.start))
    dispatcher.add_handler(CommandHandler("stopfail2ban", fail2ban_service.stop))
    dispatcher.add_handler(CommandHandler("statusfail2ban", fail2ban_service.status))

def start(update, _):
    update.message.reply_text(
        "Commandes disponibles : /startfail2ban, /stopfail2ban, /statusfail2ban"
    )

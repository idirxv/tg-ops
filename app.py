from flask import Flask
from webhook.routes import register_routes
from bot.handlers import register_handlers, dispatcher
from telegram import Bot
from config import Config
import argparse

bot = Bot(Config.bot_token)
dispatcher.bot = bot

app = Flask(__name__)
register_routes(app, bot, dispatcher)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-webhook", action="store_true")
    parser.add_argument("--delete-webhook", action="store_true")
    args = parser.parse_args()

    if args.set_webhook:
        bot.setWebhook(f"{Config.webhook_url}/webhook")
        print("Webhook set")
    elif args.delete_webhook:
        bot.deleteWebhook()
        print("Webhook deleted")
    else:
        app.run(host="0.0.0.0", port=Config.port)

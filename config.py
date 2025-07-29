import os

class Config:

    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.webhook_url = os.getenv("WEBHOOK_URL")
        self.port = os.getenv("PORT", 8443)

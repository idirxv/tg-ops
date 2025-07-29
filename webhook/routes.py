from flask import request, Response
from telegram import Update

def register_routes(app, bot, dispatcher):
    @app.route("/", methods=["GET"])
    def health():
        return "OK", 200

    @app.route("/webhook", methods=["POST"])
    def webhook():
        if request.headers.get("content-type") == "application/json":
            json_update = request.get_json(force=True)
            update = Update.de_json(json_update, bot)
            dispatcher.process_update(update)
            return Response(status=200)
        return Response(status=415)

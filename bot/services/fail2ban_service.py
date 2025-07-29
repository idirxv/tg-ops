from utils.systemctl import run_systemctl

def start(update, _):
    ok, msg = run_systemctl("start", "fail2ban")
    update.message.reply_text("✅ Démarré." if ok else f"❌ {msg}")

def stop(update, _):
    ok, msg = run_systemctl("stop", "fail2ban")
    update.message.reply_text("🛑 Arrêté." if ok else f"❌ {msg}")

def status(update, _):
    ok, msg = run_systemctl("status", "fail2ban")
    update.message.reply_text(msg if ok else f"❌ {msg}")

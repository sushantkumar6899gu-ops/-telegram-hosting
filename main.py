
import os
import re
import sqlite3
import requests
from flask import Flask, request, abort

app = Flask(__name__)

TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
API = f"https://api.telegram.org/bot{TOKEN}"
DB = "likes.db"


def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS players (
                uid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                likes INTEGER NOT NULL DEFAULT 0,
                owner INTEGER NOT NULL
            )
        """)


def send(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15
    ).raise_for_status()


def handle(msg):
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "").strip()
    parts = text.split(maxsplit=2)
    cmd = parts[0].split("@")[0].lower() if parts else ""

    if cmd == "/start":
        send(chat_id,
             "❤️ Free Fire 35 Likes Board\n\n"
             "/add UID नाम — अपना UID जोड़ें\n"
             "/board — खिलाड़ियों की सूची\n"
             "/progress UID — लाइक प्रोग्रेस देखें\n"
             "/update UID संख्या — एडमिन द्वारा प्रोग्रेस अपडेट\n\n"
             "यह बोर्ड है; यह गेम में खुद लाइक नहीं भेजता।")
        return

    if cmd == "/add":
        if len(parts) < 3 or not re.fullmatch(r"\d{5,20}", parts[1]):
            send(chat_id, "ऐसे लिखें:\n/add 123456789 राहुल")
            return

        uid, name = parts[1], parts[2][:40]
        with sqlite3.connect(DB) as con:
            con.execute("""
                INSERT INTO players(uid, name, likes, owner)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(uid) DO NOTHING
            """, (uid, name, user_id))
        send(chat_id, "UID बोर्ड में जोड़ने की कोशिश की गई।\n"
                      "अगर UID पहले से मौजूद है, तो नया रिकॉर्ड नहीं बनेगा।")
        return

    if cmd == "/board":
        with sqlite3.connect(DB) as con:
            rows = con.execute(
                "SELECT uid, name, likes FROM players "
                "ORDER BY likes DESC LIMIT 30"
            ).fetchall()

        if not rows:
            send(chat_id, "बोर्ड खाली है। /add UID नाम से जोड़ें।")
            return

        lines = ["❤️ FREE FIRE — 35 LIKES BOARD\n"]
        for uid, name, likes in rows:
            likes = max(0, min(35, likes))
            lines.append(
                f"🎮 {name}\nUID: {uid}\n"
                f"❤️ {likes}/35 | बाकी: {35-likes}\n"
            )
        send(chat_id, "\n".join(lines))
        return

    if cmd == "/progress":
        if len(parts) < 2:
            send(chat_id, "उदाहरण: /progress 123456789")
            return
        with sqlite3.connect(DB) as con:
            row = con.execute(
                "SELECT name, likes FROM players WHERE uid=?",
                (parts[1],)
            ).fetchone()
        if not row:
            send(chat_id, "यह UID बोर्ड में नहीं मिला।")
        else:
            name, likes = row
            send(chat_id, f"{name}\n❤️ {likes}/35\n"
                          f"बाकी: {35-likes}")
        return

    if cmd == "/update":
        if user_id != ADMIN_ID:
            send(chat_id, "यह कमांड केवल एडमिन चला सकता है।")
            return
        if len(parts) < 3 or not re.fullmatch(r"\d{5,20}", parts[1]):
            send(chat_id, "उदाहरण: /update 123456789 10")
            return
        if not parts[2].isdigit() or not 0 <= int(parts[2]) <= 35:
            send(chat_id, "संख्या 0 से 35 के बीच रखें।")
            return

        with sqlite3.connect(DB) as con:
            cur = con.execute(
                "UPDATE players SET likes=? WHERE uid=?",
                (int(parts[2]), parts[1])
            )
            changed = cur.rowcount

        send(chat_id, "प्रोग्रेस अपडेट हो गई।" if changed
             else "UID नहीं मिला।")
        return

    send(chat_id, "कमांड समझ नहीं आई। /start भेजें।")


@app.get("/")
def home():
    return "Free Fire Likes Board Bot is running."


@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != SECRET:
        abort(403)

    update = request.get_json(silent=True) or {}
    msg = update.get("message")
    if msg and msg.get("text"):
        try:
            handle(msg)
        except Exception:
            app.logger.exception("Update processing failed")

    return {"ok": True}


init_db()

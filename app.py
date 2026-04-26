import os

import requests
import yaml
from flask import Flask, jsonify, request
from google import genai
from google.genai import types


app = Flask(__name__)


def load_config():
    config_path = os.getenv("CONFIG_PATH", "config.yml")
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


config = load_config()
gemini_settings = config.get("gemini", {})
webhook_settings = config.get("webhook", {})

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL_ID = os.getenv("GEMINI_MODEL", gemini_settings.get("model", "gemini-2.5-flash"))
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    gemini_settings.get("system_prompt", "you are helpful assistant"),
)

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", webhook_settings.get("path", "/telegram/webhook"))
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"

render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or webhook_settings.get("base_url")
)
if not WEBHOOK_BASE_URL and render_hostname:
    WEBHOOK_BASE_URL = f"https://{render_hostname}"

telegram_api_url = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
gemini_config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[types.Tool(google_search=types.GoogleSearch())],
)

chats = {}


def get_or_create_chat(session_id):
    """Keep one Gemini chat per user/session so short-term memory is preserved."""
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    if session_id not in chats:
        chats[session_id] = gemini_client.chats.create(
            model=MODEL_ID,
            config=gemini_config,
        )

    return chats[session_id]


def ask_gemini(session_id, message):
    chat = get_or_create_chat(session_id)
    response = chat.send_message(message)
    return response.text or ""


def send_telegram_message(chat_id, text):
    if not telegram_api_url:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    response = requests.post(
        f"{telegram_api_url}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def configure_telegram_webhook():
    if not telegram_api_url or not WEBHOOK_BASE_URL:
        app.logger.info("Telegram webhook setup skipped: missing token or base URL")
        return

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{WEBHOOK_PATH}"

    delete_response = requests.post(
        f"{telegram_api_url}/deleteWebhook",
        params={"drop_pending_updates": "true"},
        timeout=20,
    )
    delete_response.raise_for_status()

    set_response = requests.post(
        f"{telegram_api_url}/setWebhook",
        params={"url": webhook_url},
        timeout=20,
    )
    set_response.raise_for_status()

    app.logger.info("Telegram webhook configured: %s", webhook_url)


@app.get("/")
def health_check():
    return jsonify({"status": "ok"})


@app.post("/chat")
def chat_api():
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    session_id = str(data.get("session_id", "default"))

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        reply = ask_gemini(session_id, message)
    except Exception as exc:
        app.logger.exception("Gemini request failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"reply": reply})


@app.post(WEBHOOK_PATH)
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not text or not chat_id:
        return jsonify({"ok": True, "ignored": True})

    try:
        reply = ask_gemini(f"telegram:{chat_id}", text)
        send_telegram_message(chat_id, reply)
    except Exception as exc:
        app.logger.exception("Telegram webhook failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True})


try:
    configure_telegram_webhook()
except Exception:
    app.logger.exception("Telegram webhook setup failed")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

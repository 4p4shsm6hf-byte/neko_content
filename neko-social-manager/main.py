"""
NEKO Social Media Manager – Einstiegspunkt

Startet den Telegram Bot nach Validierung aller Umgebungsvariablen.
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "BLOTATO_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "LINKEDIN_ACCOUNT_ID",
    "INSTAGRAM_ACCOUNT_ID",
    "FACEBOOK_ACCOUNT_ID",
]

SETUP_GUIDE = """
╔══════════════════════════════════════════════════════════════════╗
║          NEKO Social Media Manager – Setup-Anleitung            ║
╚══════════════════════════════════════════════════════════════════╝

Folgende Umgebungsvariablen fehlen oder sind noch Platzhalter.
Trage die echten Werte in die .env Datei ein:

{missing_vars}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELEGRAM_BOT_TOKEN – So erstellst du einen Bot:
  1. Öffne Telegram und suche @BotFather
  2. Sende /newbot
  3. Wähle einen Namen (z. B. "NEKO Content Bot")
  4. Wähle einen Username (muss auf "bot" enden, z. B. "neko_content_bot")
  5. BotFather gibt dir einen Token – kopiere ihn in die .env

OPENROUTER_API_KEY (für Content-Generierung via Claude):
  → https://openrouter.ai/keys

OPENAI_API_KEY (nur für Whisper Spracherkennung – OpenRouter unterstützt kein Audio):
  → https://platform.openai.com/api-keys

BLOTATO_API_KEY:
  → Blotato Dashboard → Settings → API

LINKEDIN/INSTAGRAM/FACEBOOK_ACCOUNT_ID:
  → Blotato Dashboard → Social Accounts → jeweiliges Konto anklicken
  → Die ID steht in der URL oder in den Account-Details

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Danach: python main.py
"""


def check_env() -> bool:
    """Check all required env vars are set and not placeholder values."""
    missing = []
    for var in REQUIRED_VARS:
        val = os.environ.get(var, "")
        if not val or "your_" in val.lower() or val.endswith("_here"):
            missing.append(f"  ❌ {var}")

    if missing:
        print(SETUP_GUIDE.format(missing_vars="\n".join(missing)))
        return False

    logger.info("✅ Alle Umgebungsvariablen gesetzt.")
    return True


def main():
    if not check_env():
        sys.exit(1)

    # Ensure required directories exist
    Path("media_cache").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    logger.info("🚀 Starte NEKO Social Media Manager Bot…")

    from bot.telegram_bot import build_application
    app = build_application()
    logger.info("Bot läuft. Drücke Ctrl+C zum Beenden.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

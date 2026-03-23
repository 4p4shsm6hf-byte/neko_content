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

# Fix Unicode output on Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

# In TEST_MODE: Telegram + OpenRouter required, Blotato/Social skipped
TEST_MODE_VARS = ["TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY"]

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


def is_test_mode() -> bool:
    return os.environ.get("TEST_MODE", "").lower() in ("1", "true", "yes")


def check_env() -> bool:
    """Check required env vars. In TEST_MODE only TELEGRAM_BOT_TOKEN is needed."""
    vars_to_check = TEST_MODE_VARS if is_test_mode() else REQUIRED_VARS
    missing = []
    for var in vars_to_check:
        val = os.environ.get(var, "")
        if not val or "your_" in val.lower() or val.endswith("_here"):
            missing.append(f"  ❌ {var}")

    if missing:
        print(SETUP_GUIDE.format(missing_vars="\n".join(missing)))
        return False

    if is_test_mode():
        logger.info("🧪 TEST_MODE aktiv – Claude & Blotato sind deaktiviert.")
    else:
        logger.info("✅ Alle Umgebungsvariablen gesetzt.")
    return True


def main():
    if not check_env():
        sys.exit(1)

    Path("media_cache").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    if is_test_mode():
        logger.info("🚀 Starte NEKO Bot im TEST_MODE…")
        _patch_for_test_mode()
    else:
        logger.info("🚀 Starte NEKO Social Media Manager Bot…")

    from bot.telegram_bot import build_application
    app = build_application()
    logger.info("Bot läuft. Drücke Ctrl+C zum Beenden.")
    app.run_polling(drop_pending_updates=True)


def _patch_for_test_mode():
    """Replace only BlotatoClient with a stub – ContentGenerator uses real OpenRouter."""
    import blotato.blotato_client as bl_module

    class _StubBlotatoClient:
        async def upload_media(self, file_path):
            logger.info(f"[TEST] Media-Upload übersprungen: {file_path}")
            return "test_media_id"

        async def create_post(self, platform, text, media_ids, account_id):
            logger.info(f"[TEST] Post-Draft übersprungen für {platform}")
            return f"test_post_id_{platform}"

        async def publish_post(self, post_id):
            logger.info(f"[TEST] Publish übersprungen für {post_id}")
            return f"https://example.com/test-post/{post_id}"

        async def publish_with_retry(self, post_id, retries=3):
            return await self.publish_post(post_id)

    bl_module.BlotatoClient = _StubBlotatoClient
    logger.info("[TEST] BlotatoClient durch Stub ersetzt – OpenRouter wird echt aufgerufen.")


if __name__ == "__main__":
    main()

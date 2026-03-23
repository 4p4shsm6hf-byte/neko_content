"""
Telegram Bot – empfängt Baustellenberichte und startet den Content-Pipeline.

Kommandos:
  /start                  – Begrüßung + Anleitung
  /baustelle [Name]       – Neue Session starten
  /fertig                 – Session abschließen und Posts generieren
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.media_handler import (
    describe_media,
    handle_photo,
    handle_video,
    handle_voice,
)
from bot.transcriber import Transcriber
from content.content_generator import ContentGenerator
from review.review_handler import register_review_handlers, start_review

logger = logging.getLogger(__name__)

transcriber = Transcriber()


@dataclass
class BuildingSession:
    project_name: str
    texts: list[str] = field(default_factory=list)
    media_items: list[dict] = field(default_factory=list)


# In-memory store: chat_id → BuildingSession
_active_sessions: dict[int, BuildingSession] = {}


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Willkommen beim NEKO Social Media Manager!*\n\n"
        "So funktioniert es:\n"
        "1️⃣ Starte eine Baustellen-Session mit `/baustelle Projektname`\n"
        "2️⃣ Schicke Fotos, Videos, Sprachnachrichten oder Text aus der Baustelle\n"
        "3️⃣ Beende die Eingabe mit `/fertig`\n"
        "4️⃣ Überprüfe die generierten Posts und gib sie frei\n\n"
        "Die freigegebenen Posts werden automatisch auf LinkedIn, Instagram und Facebook veröffentlicht.",
        parse_mode="Markdown",
    )


async def cmd_baustelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args
    project_name = " ".join(args) if args else "Unbenannte Baustelle"

    if chat_id in _active_sessions:
        await update.message.reply_text(
            f"⚠️ Es läuft bereits eine Session für *{_active_sessions[chat_id].project_name}*.\n"
            "Schließe sie erst mit /fertig ab.",
            parse_mode="Markdown",
        )
        return

    _active_sessions[chat_id] = BuildingSession(project_name=project_name)
    await update.message.reply_text(
        f"🏗️ *Session gestartet: {project_name}*\n\n"
        "Schicke jetzt Fotos, Videos, Sprachnachrichten oder Text.\n"
        "Wenn du fertig bist, schreibe /fertig.",
        parse_mode="Markdown",
    )


async def cmd_fertig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.get(chat_id)

    if not session:
        await update.message.reply_text(
            "⚠️ Keine aktive Session. Starte mit /baustelle."
        )
        return

    if not session.texts and not session.media_items:
        await update.message.reply_text(
            "⚠️ Keine Inhalte gesammelt. Schicke erst Nachrichten, bevor du /fertig verwendest."
        )
        return

    await update.message.reply_text("⏳ Generiere Posts… Das dauert ca. 30 Sekunden.")

    combined_text = "\n".join(session.texts) if session.texts else "Kein verbaler Bericht vorhanden."
    media_desc = describe_media(session.media_items)
    media_paths = [m["path"] for m in session.media_items if "path" in m]

    del _active_sessions[chat_id]

    generator = ContentGenerator()
    try:
        posts = await generator.generate_posts(
            project_name=session.project_name,
            transcription=combined_text,
            media_description=media_desc,
        )
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        await update.message.reply_text(f"❌ Post-Generierung fehlgeschlagen: {e}")
        return

    await start_review(
        chat_id=chat_id,
        project_name=session.project_name,
        posts=posts,
        media_paths=media_paths,
        context=context,
    )


# ---------------------------------------------------------------------------
# Media handlers
# ---------------------------------------------------------------------------

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.get(chat_id)
    if not session:
        return
    session.texts.append(update.message.text)
    await update.message.reply_text("✍️ Text gespeichert.")


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.get(chat_id)
    if not session:
        return
    media = await handle_photo(context.bot, update.message.photo)
    session.media_items.append(media)
    caption = update.message.caption or ""
    if caption:
        session.texts.append(f"[Foto-Beschriftung: {caption}]")
    await update.message.reply_text("📷 Foto gespeichert.")


async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.get(chat_id)
    if not session:
        return
    media = await handle_video(context.bot, update.message.video)
    session.media_items.append(media)
    caption = update.message.caption or ""
    if caption:
        session.texts.append(f"[Video-Beschriftung: {caption}]")
    await update.message.reply_text("🎥 Video gespeichert.")


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.get(chat_id)
    if not session:
        return

    await update.message.reply_text("🎙️ Sprachnachricht wird transkribiert…")
    try:
        media = await handle_voice(context.bot, update.message.voice)
        text = await transcriber.transcribe(media["path"])
        session.texts.append(text)
        await update.message.reply_text(f"✅ Transkription:\n_{text}_", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        await update.message.reply_text(f"❌ Transkription fehlgeschlagen: {e}")


# ---------------------------------------------------------------------------
# Build application
# ---------------------------------------------------------------------------

def build_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("baustelle", cmd_baustelle))
    app.add_handler(CommandHandler("fertig", cmd_fertig))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Text handler must come after review handlers to avoid swallowing revision input
    register_review_handlers(app)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app

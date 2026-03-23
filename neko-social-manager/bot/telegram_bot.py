"""
Telegram Bot – empfängt Baustellenberichte und startet den Content-Pipeline.

Kommandos (auch per Sprachnachricht steuerbar):
  /start                  – Begrüßung + Anleitung
  /baustelle [Name]       – Neue Session starten
  /status                 – Zeigt gesammelte Inhalte der aktuellen Session
  /fertig                 – Session abschließen und Posts generieren
  /abbrechen              – Aktive Session abbrechen

Sprachbefehle (werden automatisch erkannt):
  "neue baustelle [Name]" / "baustelle [Name]"  → /baustelle
  "fertig" / "ich bin fertig" / "abschicken"     → /fertig
  "abbrechen" / "stopp"                          → /abbrechen
  "status" / "was habe ich bisher"               → /status
"""
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
    # Wartet auf Transkriptions-Bestätigung: None | "pending_confirm" | "appending" | "rewriting"
    confirm_state: Optional[str] = None
    combined_text_draft: Optional[str] = None


# In-memory store: chat_id → BuildingSession
_active_sessions: dict[int, BuildingSession] = {}


# ---------------------------------------------------------------------------
# Voice command detection
# ---------------------------------------------------------------------------

_BAUSTELLE_PATTERN = re.compile(
    r"(?:neue\s+|starte\s+)?baustelle\s+(.+)", re.IGNORECASE
)
_FERTIG_PATTERN = re.compile(
    r"^(?:fertig|ich\s+bin\s+fertig|das\s+war.?s|abschicken|abschließen|generate|generieren)\.?$",
    re.IGNORECASE,
)
_ABBRECHEN_PATTERN = re.compile(
    r"^(?:abbrechen|session\s+abbrechen|stopp|stop|abbruch)\.?$",
    re.IGNORECASE,
)
_STATUS_PATTERN = re.compile(
    r"^(?:status|was\s+habe\s+ich\s+bisher|zeig\s+status)\.?$",
    re.IGNORECASE,
)


def detect_voice_command(text: str) -> tuple[Optional[str], str]:
    """
    Detect if a transcribed voice message is a bot command.
    Returns (intent, args) where intent is one of:
    'baustelle', 'fertig', 'abbrechen', 'status', or None (= regular content).
    """
    stripped = text.strip()

    m = _BAUSTELLE_PATTERN.match(stripped)
    if m:
        return "baustelle", m.group(1).strip()

    if _FERTIG_PATTERN.match(stripped):
        return "fertig", ""

    if _ABBRECHEN_PATTERN.match(stripped):
        return "abbrechen", ""

    if _STATUS_PATTERN.match(stripped):
        return "status", ""

    return None, ""


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Willkommen beim NEKO Social Media Manager!*\n\n"
        "So funktioniert es:\n"
        "1️⃣ Starte eine Baustellen-Session mit `/baustelle Projektname`\n"
        "   _(oder per Sprachnachricht: \"neue Baustelle 12 kWp Rottweil\")_\n"
        "2️⃣ Schicke Fotos, Videos, Sprachnachrichten oder Text aus der Baustelle\n"
        "3️⃣ Beende die Eingabe mit `/fertig` _(oder per Voice: \"fertig\")_\n"
        "4️⃣ Überprüfe Transkription und Posts, dann gib sie frei\n\n"
        "Weitere Befehle:\n"
        "• `/status` – zeigt gesammelte Inhalte\n"
        "• `/abbrechen` – bricht die aktuelle Session ab\n\n"
        "Alle Befehle funktionieren auch per Sprachnachricht! 🎙️",
        parse_mode="Markdown",
    )


async def _start_session(chat_id: int, project_name: str, reply_fn):
    """Shared logic for starting a session (typed or voice)."""
    if chat_id in _active_sessions:
        existing = _active_sessions[chat_id].project_name
        await reply_fn(
            f"⚠️ Es läuft bereits eine Session für *{existing}*.\n"
            "Beende sie mit /fertig oder brich sie mit /abbrechen ab.",
        )
        return
    _active_sessions[chat_id] = BuildingSession(project_name=project_name)
    await reply_fn(
        f"🏗️ *Session gestartet: {project_name}*\n\n"
        "Schicke jetzt Fotos, Videos, Sprachnachrichten oder Text.\n"
        "Wenn du fertig bist, sag \"fertig\" oder schreibe /fertig.",
    )


async def cmd_baustelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    project_name = " ".join(context.args) if context.args else "Unbenannte Baustelle"

    async def reply(msg):
        await update.message.reply_text(msg, parse_mode="Markdown")

    await _start_session(chat_id, project_name, reply)


async def cmd_abbrechen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = _active_sessions.pop(chat_id, None)
    if not session:
        await update.message.reply_text("ℹ️ Keine aktive Session – nichts zu abbrechen.")
        return
    await update.message.reply_text(
        f"🗑️ Session *{session.project_name}* wurde abgebrochen.\n"
        "Starte eine neue Session mit `/baustelle Projektname`.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _send_status(chat_id, context.bot, update.message.reply_text)


async def _send_status(chat_id: int, bot, reply_fn):
    session = _active_sessions.get(chat_id)
    if not session:
        await reply_fn(
            "ℹ️ Keine aktive Session. Starte mit `/baustelle Projektname`.",
            parse_mode="Markdown",
        )
        return

    n_texts = len(session.texts)
    n_media = len(session.media_items)
    media_types: dict[str, int] = {}
    for m in session.media_items:
        t = m.get("type", "unbekannt")
        media_types[t] = media_types.get(t, 0) + 1

    media_summary = ", ".join(f"{v}× {k}" for k, v in media_types.items()) if media_types else "keine"
    text_preview = ""
    if session.texts:
        first = session.texts[0][:200]
        if first:
            text_preview = f"\n\n📝 *Erster Text (Vorschau):*\n_{first}_"

    await reply_fn(
        f"📋 *Status: {session.project_name}*\n\n"
        f"• Texte/Transkriptionen: {n_texts}\n"
        f"• Medien: {n_media} ({media_summary}){text_preview}\n\n"
        "Schicke weiter Inhalte oder beende mit /fertig.",
        parse_mode="Markdown",
    )


async def _trigger_fertig(chat_id: int, reply_fn, context: ContextTypes.DEFAULT_TYPE):
    """Shared logic for /fertig (typed or voice)."""
    session = _active_sessions.get(chat_id)

    if not session:
        await reply_fn("⚠️ Keine aktive Session. Starte mit /baustelle.")
        return

    if not session.texts and not session.media_items:
        await reply_fn(
            "⚠️ Keine Inhalte gesammelt. Schicke erst Nachrichten, bevor du /fertig verwendest."
        )
        return

    combined_text = "\n".join(session.texts) if session.texts else "Kein verbaler Bericht vorhanden."
    session.confirm_state = "pending_confirm"
    session.combined_text_draft = combined_text

    preview = combined_text[:800] + ("…" if len(combined_text) > 800 else "")
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Posts generieren", callback_data="confirm_generate"),
        InlineKeyboardButton("➕ Ergänzen", callback_data="confirm_append"),
        InlineKeyboardButton("🔄 Neu schreiben", callback_data="confirm_rewrite"),
    ]])
    await reply_fn(
        f"📋 *Gesammelter Bericht für '{session.project_name}':*\n\n"
        f"_{preview}_\n\n"
        f"Medien: {len(session.media_items)} Dateien\n\n"
        "Ist der Bericht vollständig und korrekt?\n"
        "• *➕ Ergänzen* – schreibe was noch fehlt, wird angehängt\n"
        "• *🔄 Neu schreiben* – ersetze den gesamten Bericht",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cmd_fertig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    async def reply(msg, **kwargs):
        await update.message.reply_text(msg, **kwargs)

    await _trigger_fertig(chat_id, reply, context)


async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback für Bestätigung/Bearbeitung vor der Post-Generierung."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    session = _active_sessions.get(chat_id)

    if not session or session.confirm_state != "pending_confirm":
        await query.edit_message_text("⚠️ Session abgelaufen – bitte neu starten.")
        return

    if query.data == "confirm_generate":
        session.confirm_state = None
        await query.edit_message_text("⏳ Generiere Posts… Das dauert ca. 15–20 Sekunden.")
        await _run_generation(chat_id, session, context)

    elif query.data == "confirm_append":
        session.confirm_state = "appending"
        await query.edit_message_text(
            "➕ *Bericht ergänzen*\n\n"
            "Schreibe was noch fehlt – dein Text wird an den bisherigen Bericht *angehängt*:",
            parse_mode="Markdown",
        )

    elif query.data == "confirm_rewrite":
        session.confirm_state = "rewriting"
        await query.edit_message_text(
            "🔄 *Bericht neu schreiben*\n\n"
            "Schreibe den *vollständigen* neuen Bericht – er ersetzt den bisherigen komplett:",
            parse_mode="Markdown",
        )


async def _run_generation(chat_id: int, session: BuildingSession, context):
    """Startet die eigentliche Post-Generierung."""
    combined_text = session.combined_text_draft or "\n".join(session.texts)
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
        await context.bot.send_message(chat_id, f"❌ Post-Generierung fehlgeschlagen: {e}")
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

    text = update.message.text

    # Handle edit states from the confirmation flow
    if session.confirm_state == "appending":
        session.combined_text_draft = (session.combined_text_draft or "") + "\n" + text
        session.confirm_state = "pending_confirm"
        preview = (session.combined_text_draft or "")[:800]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Posts generieren", callback_data="confirm_generate"),
            InlineKeyboardButton("➕ Weiter ergänzen", callback_data="confirm_append"),
            InlineKeyboardButton("🔄 Neu schreiben", callback_data="confirm_rewrite"),
        ]])
        await update.message.reply_text(
            f"✅ *Ergänzung hinzugefügt. Aktueller Bericht:*\n\n_{preview}_\n\nAlles korrekt?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    if session.confirm_state == "rewriting":
        session.combined_text_draft = text
        session.confirm_state = "pending_confirm"
        preview = text[:800]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Posts generieren", callback_data="confirm_generate"),
            InlineKeyboardButton("➕ Ergänzen", callback_data="confirm_append"),
            InlineKeyboardButton("🔄 Neu schreiben", callback_data="confirm_rewrite"),
        ]])
        await update.message.reply_text(
            f"📋 *Neuer Bericht:*\n\n_{preview}_\n\nAlles korrekt?",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    session.texts.append(text)
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

    await update.message.reply_text("🎙️ Transkribiere…")
    try:
        media = await handle_voice(context.bot, update.message.voice)
        text = await transcriber.transcribe(media["path"])
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        await update.message.reply_text(f"❌ Transkription fehlgeschlagen: {e}")
        return

    # --- Voice command detection ---
    intent, args = detect_voice_command(text)

    if intent == "baustelle":
        project_name = args or "Unbenannte Baustelle"
        await update.message.reply_text(f'🎙️ Erkannt: "neue Baustelle {project_name}"')

        async def reply(msg, **kwargs):
            await update.message.reply_text(msg, **kwargs)

        await _start_session(chat_id, project_name, reply)
        return

    if intent == "fertig":
        await update.message.reply_text('🎙️ Erkannt: "fertig"')

        async def reply(msg, **kwargs):
            await update.message.reply_text(msg, **kwargs)

        await _trigger_fertig(chat_id, reply, context)
        return

    if intent == "abbrechen":
        await update.message.reply_text('🎙️ Erkannt: "abbrechen"')
        session = _active_sessions.pop(chat_id, None)
        if session:
            await update.message.reply_text(
                f"🗑️ Session *{session.project_name}* abgebrochen.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("ℹ️ Keine aktive Session.")
        return

    if intent == "status":
        await update.message.reply_text('🎙️ Erkannt: "status"')
        await _send_status(chat_id, context.bot, update.message.reply_text)
        return

    # --- Regular content: add to session ---
    session = _active_sessions.get(chat_id)
    if not session:
        await update.message.reply_text(
            f"✅ Transkription:\n_{text}_\n\n"
            "⚠️ Keine aktive Session. Starte erst mit `/baustelle Projektname` "
            "oder per Voice: \"neue Baustelle [Name]\".",
            parse_mode="Markdown",
        )
        return

    session.texts.append(text)
    await update.message.reply_text(f"✅ Transkription gespeichert:\n_{text}_", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Build application
# ---------------------------------------------------------------------------

def build_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("baustelle", cmd_baustelle))
    app.add_handler(CommandHandler("fertig", cmd_fertig))
    app.add_handler(CommandHandler("abbrechen", cmd_abbrechen))
    app.add_handler(CommandHandler("status", cmd_status))

    # Bestätigungs-Callback (vor Review-Callbacks registrieren)
    app.add_handler(CallbackQueryHandler(
        handle_confirm_callback,
        pattern=r"^confirm_(generate|append|rewrite)$",
    ))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Text handler must come after review handlers to avoid swallowing revision input
    register_review_handlers(app)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app

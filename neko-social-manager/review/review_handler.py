"""
Telegram review & approval flow.

Flow per platform:
  1. Bot sends post preview with three InlineButtons: Approve / Revise / Discard
  2. User taps Approve  → post is published via Blotato
     User taps Revise   → bot asks for feedback text → Claude rewrites → repeat
     User taps Discard  → post is skipped
  3. After all platforms are handled the session log is written.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from blotato.blotato_client import BlotatoClient
from content.content_generator import ContentGenerator
from content.platform_optimizer import format_preview, validate_and_warn
from logs.log_writer import write_log_entry

logger = logging.getLogger(__name__)

ACCOUNT_IDS = {
    "linkedin":  lambda: os.environ["LINKEDIN_ACCOUNT_ID"],
    "instagram": lambda: os.environ["INSTAGRAM_ACCOUNT_ID"],
    "facebook":  lambda: os.environ["FACEBOOK_ACCOUNT_ID"],
}

PLATFORMS = ["linkedin", "instagram", "facebook"]


@dataclass
class ReviewSession:
    project_name: str
    posts: dict[str, str]          # platform → text
    media_paths: list[str]
    results: dict = field(default_factory=dict)   # platform → {"status", "url"}
    pending_revision_platform: Optional[str] = None


# In-memory store: chat_id → ReviewSession
_sessions: dict[int, ReviewSession] = {}


def _make_keyboard(platform: str, idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Freigeben",   callback_data=f"approve:{platform}:{idx}"),
        InlineKeyboardButton("✏️ Überarbeiten", callback_data=f"revise:{platform}:{idx}"),
        InlineKeyboardButton("❌ Verwerfen",   callback_data=f"discard:{platform}:{idx}"),
    ]])


async def start_review(
    chat_id: int,
    project_name: str,
    posts: dict[str, str],
    media_paths: list[str],
    context: ContextTypes.DEFAULT_TYPE,
):
    """Send all three post previews to the chat for review."""
    session = ReviewSession(
        project_name=project_name,
        posts=dict(posts),
        media_paths=media_paths,
    )
    _sessions[chat_id] = session

    await context.bot.send_message(
        chat_id,
        f"✨ *Posts für '{project_name}' sind fertig!*\n"
        "Bitte überprüfe und gib jeden Post frei:",
        parse_mode="Markdown",
    )

    for idx, platform in enumerate(PLATFORMS):
        text = validate_and_warn(platform, posts[platform])
        preview = format_preview(platform, text)
        await context.bot.send_message(
            chat_id,
            preview,
            parse_mode="Markdown",
            reply_markup=_make_keyboard(platform, idx),
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Approve / Revise / Discard button taps."""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    session = _sessions.get(chat_id)
    if not session:
        await query.edit_message_text("⚠️ Keine aktive Review-Session gefunden.")
        return

    action, platform, _ = query.data.split(":")

    if action == "approve":
        await query.edit_message_text(
            f"⏳ Veröffentliche {platform.upper()}…", parse_mode="Markdown"
        )
        await _publish(chat_id, platform, session, context)

    elif action == "revise":
        session.pending_revision_platform = platform
        await query.edit_message_text(
            f"✏️ *{platform.upper()} überarbeiten*\n\n"
            "Schreibe deinen Änderungswunsch als nächste Nachricht:",
            parse_mode="Markdown",
        )

    elif action == "discard":
        session.results[platform] = {"status": "discarded", "url": None}
        await query.edit_message_text(f"❌ *{platform.upper()}* wurde verworfen.", parse_mode="Markdown")
        await _check_all_done(chat_id, session, context)


async def handle_revision_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive free-text feedback and trigger Claude revision."""
    chat_id = update.effective_chat.id
    session = _sessions.get(chat_id)

    if not session or not session.pending_revision_platform:
        return  # message not for us

    platform = session.pending_revision_platform
    session.pending_revision_platform = None
    feedback = update.message.text

    await update.message.reply_text(f"⏳ Überarbeite {platform.upper()} Post…")

    generator = ContentGenerator()
    try:
        revised = await generator.revise_post(platform, session.posts[platform], feedback)
    except Exception as e:
        logger.error(f"Revision failed: {e}")
        await update.message.reply_text(f"❌ Überarbeitung fehlgeschlagen: {e}")
        return

    session.posts[platform] = revised
    text = validate_and_warn(platform, revised)
    preview = format_preview(platform, text)

    # Find message index (use 0 as placeholder – new message anyway)
    await context.bot.send_message(
        chat_id,
        f"📝 *Überarbeitete Version:*\n\n{preview}",
        parse_mode="Markdown",
        reply_markup=_make_keyboard(platform, 99),
    )


async def _publish(
    chat_id: int,
    platform: str,
    session: ReviewSession,
    context: ContextTypes.DEFAULT_TYPE,
):
    client = BlotatoClient()
    try:
        # Upload media
        media_ids = []
        for path in session.media_paths:
            try:
                media_id = await client.upload_media(path)
                media_ids.append(media_id)
            except Exception as e:
                logger.warning(f"Media upload skipped ({path}): {e}")

        account_id = ACCOUNT_IDS[platform]()
        post_id = await client.create_post(
            platform=platform,
            text=session.posts[platform],
            media_ids=media_ids,
            account_id=account_id,
        )
        live_url = await client.publish_with_retry(post_id)
        session.results[platform] = {"status": "published", "url": live_url}

        await context.bot.send_message(
            chat_id,
            f"✅ *{platform.upper()}* veröffentlicht!\n🔗 {live_url}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Publishing {platform} failed: {e}")
        session.results[platform] = {"status": "error", "url": None}
        await context.bot.send_message(
            chat_id,
            f"❌ Fehler beim Veröffentlichen von {platform.upper()}: {e}",
        )

    await _check_all_done(chat_id, session, context)


async def _check_all_done(
    chat_id: int,
    session: ReviewSession,
    context: ContextTypes.DEFAULT_TYPE,
):
    """If all platforms have a result, write the log and clean up."""
    if len(session.results) < len(PLATFORMS):
        return

    await write_log_entry(session.project_name, session.posts, session.results)
    del _sessions[chat_id]

    summary_lines = ["📋 *Zusammenfassung:*"]
    for platform in PLATFORMS:
        r = session.results.get(platform, {})
        status = r.get("status", "unknown")
        url = r.get("url") or "–"
        icon = "✅" if status == "published" else ("❌" if status == "discarded" else "⚠️")
        summary_lines.append(f"{icon} {platform.upper()}: {status} | {url}")

    await context.bot.send_message(
        chat_id,
        "\n".join(summary_lines) + "\n\nLog wurde gespeichert. Neue Session mit /baustelle starten.",
        parse_mode="Markdown",
    )


def register_review_handlers(application):
    """Register callback and message handlers for the review flow."""
    application.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(approve|revise|discard):"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_revision_text,
        )
    )

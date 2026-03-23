"""
Platform-specific post optimization helpers.
Validates length constraints and truncates/warns if needed.
"""
import logging

logger = logging.getLogger(__name__)

LIMITS = {
    "linkedin":  {"min": 1300, "max": 3000},
    "instagram": {"min": 100,  "max": 2200},
    "facebook":  {"min": 200,  "max": 63206},
}


def validate_and_warn(platform: str, text: str) -> str:
    """Log a warning if the text is outside recommended length; return text unchanged."""
    limits = LIMITS.get(platform, {})
    length = len(text)
    min_l = limits.get("min", 0)
    max_l = limits.get("max", float("inf"))

    if length < min_l:
        logger.warning(
            f"[{platform}] Post is short ({length} chars, recommended min {min_l})"
        )
    elif length > max_l:
        logger.warning(
            f"[{platform}] Post exceeds platform limit ({length}/{max_l} chars) – truncating"
        )
        text = text[:max_l]

    return text


def format_preview(platform: str, text: str) -> str:
    """Return a Telegram-formatted preview string for review."""
    icons = {"linkedin": "💼", "instagram": "📸", "facebook": "👥"}
    icon = icons.get(platform, "📝")
    header = f"{icon} *{platform.upper()}* ({len(text)} Zeichen)"
    separator = "─" * 30
    return f"{header}\n{separator}\n{text}\n{separator}"

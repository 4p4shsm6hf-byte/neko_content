"""
Writes published post entries to logs/published_posts.md.
New entries are prepended (newest first).
"""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = Path("logs/published_posts.md")

PLATFORM_LABELS = {
    "linkedin":  "LinkedIn",
    "instagram": "Instagram",
    "facebook":  "Facebook",
}


def _status_row(platform: str, result: dict) -> str:
    label = PLATFORM_LABELS.get(platform, platform.title())
    status = result.get("status", "unknown")
    url = result.get("url") or "–"

    if status == "published":
        status_cell = "✅ Veröffentlicht"
        url_cell = f"[Link]({url})"
        date_cell = datetime.now().strftime("%Y-%m-%d %H:%M")
    elif status == "discarded":
        status_cell = "❌ Verworfen"
        url_cell = "–"
        date_cell = "–"
    else:
        status_cell = f"⚠️ {status}"
        url_cell = "–"
        date_cell = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"| {label} | {status_cell} | {url_cell} | {date_cell} |"


async def write_log_entry(
    project_name: str,
    posts: dict[str, str],
    results: dict[str, dict],
):
    """Prepend a new log entry to published_posts.md."""
    LOG_FILE.parent.mkdir(exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Build summary from first published post text
    summary_text = "–"
    for platform in ("linkedin", "instagram", "facebook"):
        if results.get(platform, {}).get("status") == "published":
            summary_text = posts.get(platform, "")[:200].replace("\n", " ") + "…"
            break

    rows = "\n".join(
        _status_row(platform, results.get(platform, {}))
        for platform in ("linkedin", "instagram", "facebook")
    )

    entry = (
        f"## [{date_str}] – {project_name}\n\n"
        f"| Plattform | Status | Live-URL | Veröffentlicht am |\n"
        f"|-----------|--------|----------|-------------------|\n"
        f"{rows}\n\n"
        f"**Inhalt (Zusammenfassung):** {summary_text}\n\n"
        f"---\n\n"
    )

    existing = ""
    if LOG_FILE.exists():
        existing = LOG_FILE.read_text(encoding="utf-8")

    # Ensure header exists
    header = "# NEKO Social Media – Veröffentlichte Posts\n\n"
    if existing.startswith(header):
        body = existing[len(header):]
    else:
        body = existing

    LOG_FILE.write_text(header + entry + body, encoding="utf-8")
    logger.info(f"Log entry written for '{project_name}'")

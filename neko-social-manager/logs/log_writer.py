"""
Writes published post entries to logs/published_posts.md (human-readable)
and logs/post_history.json (full texts for AI context).
New entries are prepended (newest first) in the markdown file.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = Path("logs/published_posts.md")
HISTORY_FILE = Path("logs/post_history.json")

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


def _write_history(project_name: str, posts: dict[str, str], results: dict[str, dict]):
    """Append full post texts to post_history.json for AI context."""
    HISTORY_FILE.parent.mkdir(exist_ok=True)

    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "project": project_name,
    }
    for platform in ("linkedin", "instagram", "facebook"):
        if results.get(platform, {}).get("status") == "published":
            entry[platform] = posts.get(platform, "")

    # Only save if at least one platform was published
    if any(k in entry for k in ("linkedin", "instagram", "facebook")):
        history.append(entry)
        # Keep last 20 entries to limit file size
        history = history[-20:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Post history updated for '{project_name}' ({len(history)} entries total)")


async def write_log_entry(
    project_name: str,
    posts: dict[str, str],
    results: dict[str, dict],
):
    """Prepend a new log entry to published_posts.md and update post_history.json."""
    LOG_FILE.parent.mkdir(exist_ok=True)

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

    # Also save full texts to JSON history for AI context
    _write_history(project_name, posts, results)

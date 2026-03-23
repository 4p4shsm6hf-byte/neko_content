import logging
import os
import aiofiles
import aiohttp
from pathlib import Path

logger = logging.getLogger(__name__)

MEDIA_DIR = Path("media_cache")


async def ensure_media_dir():
    MEDIA_DIR.mkdir(exist_ok=True)


async def download_file(bot, file_id: str, suffix: str) -> str:
    """Download a Telegram file by file_id and return local path."""
    await ensure_media_dir()
    tg_file = await bot.get_file(file_id)
    dest = MEDIA_DIR / f"{file_id}{suffix}"
    await tg_file.download_to_drive(str(dest))
    logger.info(f"Downloaded media to {dest}")
    return str(dest)


async def handle_photo(bot, photo) -> dict:
    """Download the highest-resolution photo and return metadata."""
    best = max(photo, key=lambda p: p.file_size)
    path = await download_file(bot, best.file_id, ".jpg")
    return {"type": "photo", "path": path, "file_id": best.file_id}


async def handle_video(bot, video) -> dict:
    """Download a video and return metadata."""
    path = await download_file(bot, video.file_id, ".mp4")
    return {
        "type": "video",
        "path": path,
        "file_id": video.file_id,
        "duration": video.duration,
        "width": video.width,
        "height": video.height,
    }


async def handle_voice(bot, voice) -> dict:
    """Download a voice message and return metadata."""
    path = await download_file(bot, voice.file_id, ".ogg")
    return {"type": "voice", "path": path, "file_id": voice.file_id, "duration": voice.duration}


def describe_media(media_items: list[dict]) -> str:
    """Return a human-readable description of collected media for the AI prompt."""
    if not media_items:
        return "Keine Medien vorhanden."
    parts = []
    photos = [m for m in media_items if m["type"] == "photo"]
    videos = [m for m in media_items if m["type"] == "video"]
    if photos:
        parts.append(f"{len(photos)} Foto(s) vom Bau vorhanden")
    if videos:
        durations = [v.get("duration", 0) for v in videos]
        total = sum(durations)
        parts.append(f"{len(videos)} Video(s) ({total}s gesamt) vom Bau vorhanden")
    return ", ".join(parts) + "."

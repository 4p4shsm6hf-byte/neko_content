"""
Blotato API client.
Docs: https://help.blotato.com/api/llm
"""
import logging
import os
import asyncio
import aiohttp
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://backend.blotato.com"

PLATFORM_MAP = {
    "linkedin":  "linkedin",
    "instagram": "instagram",
    "facebook":  "facebook",
}


class BlotatoClient:
    def __init__(self):
        self.api_key = os.environ["BLOTATO_API_KEY"]
        self.headers = {
            "blotato-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Media upload
    # ------------------------------------------------------------------

    async def upload_media(self, file_path: str) -> str:
        """Upload a media file to Blotato and return the media ID."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        logger.info(f"Uploading media: {file_path}")
        upload_url = f"{BASE_URL}/media"

        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()

        # Determine content type
        suffix = path.suffix.lower()
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
        }
        content_type = content_type_map.get(suffix, "application/octet-stream")

        form = aiohttp.FormData()
        form.add_field("file", data, filename=path.name, content_type=content_type)

        upload_headers = {"blotato-api-key": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, headers=upload_headers, data=form) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    raise RuntimeError(
                        f"Blotato media upload failed ({resp.status}): {body}"
                    )
                result = await resp.json()

        media_id = result.get("id") or result.get("mediaId") or result.get("data", {}).get("id")
        if not media_id:
            raise RuntimeError(f"Unexpected Blotato media response: {result}")

        logger.info(f"Media uploaded, ID: {media_id}")
        return str(media_id)

    # ------------------------------------------------------------------
    # Post creation
    # ------------------------------------------------------------------

    async def create_post(
        self,
        platform: str,
        text: str,
        media_ids: list[str],
        account_id: str,
    ) -> str:
        """Create a post draft on Blotato and return the post ID."""
        platform_key = PLATFORM_MAP.get(platform.lower())
        if not platform_key:
            raise ValueError(f"Unsupported platform: {platform}")

        logger.info(f"Creating {platform} post draft (account {account_id})")

        payload = {
            "post": {
                "text": text,
                "mediaIds": media_ids,
            },
            "platforms": [
                {
                    "platform": platform_key,
                    "accountId": account_id,
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/posts",
                headers=self.headers,
                json=payload,
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    raise RuntimeError(
                        f"Blotato create_post failed ({resp.status}): {body}"
                    )
                result = await resp.json()

        post_id = (
            result.get("id")
            or result.get("postId")
            or result.get("data", {}).get("id")
        )
        if not post_id:
            raise RuntimeError(f"Unexpected Blotato post response: {result}")

        logger.info(f"Post draft created, ID: {post_id}")
        return str(post_id)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish_post(self, post_id: str) -> str:
        """Publish a drafted post and return the live URL."""
        logger.info(f"Publishing post {post_id}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/posts/{post_id}/publish",
                headers=self.headers,
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    raise RuntimeError(
                        f"Blotato publish_post failed ({resp.status}): {body}"
                    )
                result = await resp.json()

        live_url = (
            result.get("url")
            or result.get("liveUrl")
            or result.get("data", {}).get("url")
            or "https://blotato.com"  # fallback if API doesn't return URL immediately
        )
        logger.info(f"Post published: {live_url}")
        return live_url

    # ------------------------------------------------------------------
    # Rate-limit safe wrapper
    # ------------------------------------------------------------------

    async def publish_with_retry(self, post_id: str, retries: int = 3) -> str:
        """Publish with exponential backoff on rate-limit (429) errors."""
        for attempt in range(retries):
            try:
                return await self.publish_post(post_id)
            except RuntimeError as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = 2 ** attempt * 5
                    logger.warning(f"Rate limited, retrying in {wait}s…")
                    await asyncio.sleep(wait)
                else:
                    raise
        raise RuntimeError("Max retries exceeded")

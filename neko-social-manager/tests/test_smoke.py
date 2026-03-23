"""
Smoke-Tests für NEKO Social Media Manager.
Keine echten API-Calls – alle externen Dienste werden gemockt.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def set_env(**kwargs):
    """Patch os.environ with the given key/value pairs."""
    return patch.dict(os.environ, kwargs)


VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:ABCdef",
    "BLOTATO_API_KEY": "blotato_real_key",
    "OPENROUTER_API_KEY": "sk-or-real",
    "OPENAI_API_KEY": "sk-openai-real",
    "LINKEDIN_ACCOUNT_ID": "li_123",
    "INSTAGRAM_ACCOUNT_ID": "ig_456",
    "FACEBOOK_ACCOUNT_ID": "fb_789",
}


# ---------------------------------------------------------------------------
# 1. Env-Validierung (main.py)
# ---------------------------------------------------------------------------

class TestEnvValidation:
    def test_all_valid_keys_pass(self):
        with set_env(**VALID_ENV):
            from main import check_env
            assert check_env() is True

    def test_missing_key_fails(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "OPENROUTER_API_KEY"}
        with set_env(**env):
            # Remove the key entirely
            env_copy = os.environ.copy()
            env_copy.pop("OPENROUTER_API_KEY", None)
            with patch.dict(os.environ, env_copy, clear=True):
                from main import check_env
                assert check_env() is False

    def test_placeholder_key_fails(self):
        env = {**VALID_ENV, "BLOTATO_API_KEY": "your_blotato_api_key_here"}
        with set_env(**env):
            from main import check_env
            assert check_env() is False


# ---------------------------------------------------------------------------
# 2. Platform Optimizer (pure functions – kein Netz)
# ---------------------------------------------------------------------------

class TestPlatformOptimizer:
    def setup_method(self):
        from content.platform_optimizer import validate_and_warn, format_preview
        self.validate = validate_and_warn
        self.preview = format_preview

    def test_linkedin_ok_length(self):
        text = "x" * 1400
        result = self.validate("linkedin", text)
        assert result == text

    def test_linkedin_truncates_at_limit(self):
        text = "x" * 4000
        result = self.validate("linkedin", 3001 * "x")
        assert len(result) <= 3000

    def test_format_preview_contains_platform(self):
        preview = self.preview("linkedin", "Test Post")
        assert "LINKEDIN" in preview
        assert "Test Post" in preview

    def test_format_preview_instagram(self):
        preview = self.preview("instagram", "Hook text")
        assert "INSTAGRAM" in preview


# ---------------------------------------------------------------------------
# 3. Log Writer (file I/O – kein Netz)
# ---------------------------------------------------------------------------

class TestLogWriter:
    @pytest.mark.asyncio
    async def test_writes_log_entry(self, tmp_path, monkeypatch):
        from logs import log_writer
        monkeypatch.setattr(log_writer, "LOG_FILE", tmp_path / "published_posts.md")

        await log_writer.write_log_entry(
            project_name="Testprojekt Rottweil",
            posts={
                "linkedin": "LinkedIn Post Text",
                "instagram": "Instagram Post Text",
                "facebook": "Facebook Post Text",
            },
            results={
                "linkedin":  {"status": "published", "url": "https://linkedin.com/post/1"},
                "instagram": {"status": "published", "url": "https://instagram.com/p/1"},
                "facebook":  {"status": "discarded", "url": None},
            },
        )

        content = (tmp_path / "published_posts.md").read_text(encoding="utf-8")
        assert "Testprojekt Rottweil" in content
        assert "✅ Veröffentlicht" in content
        assert "❌ Verworfen" in content
        assert "linkedin.com" in content

    @pytest.mark.asyncio
    async def test_prepends_new_entries(self, tmp_path, monkeypatch):
        from logs import log_writer
        log_file = tmp_path / "published_posts.md"
        monkeypatch.setattr(log_writer, "LOG_FILE", log_file)

        results = {"linkedin": {"status": "published", "url": "https://x.com"}}
        posts = {"linkedin": "Post 1", "instagram": "Post 1", "facebook": "Post 1"}

        await log_writer.write_log_entry("Projekt A", posts, results)
        await log_writer.write_log_entry("Projekt B", posts, results)

        content = log_file.read_text(encoding="utf-8")
        assert content.index("Projekt B") < content.index("Projekt A"), \
            "Neuester Eintrag muss oben stehen"


# ---------------------------------------------------------------------------
# 4. Content Generator (gemockter OpenAI-Client)
# ---------------------------------------------------------------------------

class TestContentGenerator:
    @pytest.mark.asyncio
    async def test_generate_posts_returns_three_platforms(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Generierter Post Text"))]

        with set_env(**VALID_ENV):
            from content.content_generator import ContentGenerator
            gen = ContentGenerator()
            gen.client = AsyncMock()
            gen.client.chat.completions.create = AsyncMock(return_value=mock_response)

            posts = await gen.generate_posts(
                project_name="Solaranlage Rottweil",
                transcription="12 kWp Anlage montiert, läuft super.",
                media_description="3 Fotos vorhanden.",
            )

        assert set(posts.keys()) == {"linkedin", "instagram", "facebook"}
        for text in posts.values():
            assert len(text) > 0

    @pytest.mark.asyncio
    async def test_revise_post(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Überarbeiteter Post"))]

        with set_env(**VALID_ENV):
            from content.content_generator import ContentGenerator
            gen = ContentGenerator()
            gen.client = AsyncMock()
            gen.client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await gen.revise_post(
                platform="linkedin",
                original_post="Alter Post",
                feedback="Bitte mehr technische Details.",
            )

        assert result == "Überarbeiteter Post"


# ---------------------------------------------------------------------------
# 5. Blotato Client (gemocktes aiohttp)
# ---------------------------------------------------------------------------

class TestBlotatoClient:
    @pytest.mark.asyncio
    async def test_upload_media(self, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image data")

        mock_resp = AsyncMock()
        mock_resp.status = 201
        mock_resp.json = AsyncMock(return_value={"id": "media_abc123"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with set_env(**VALID_ENV):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                from blotato.blotato_client import BlotatoClient
                client = BlotatoClient()
                media_id = await client.upload_media(str(test_file))

        assert media_id == "media_abc123"

    @pytest.mark.asyncio
    async def test_create_post(self):
        mock_resp = AsyncMock()
        mock_resp.status = 201
        mock_resp.json = AsyncMock(return_value={"id": "post_xyz789"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with set_env(**VALID_ENV):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                from blotato.blotato_client import BlotatoClient
                client = BlotatoClient()
                post_id = await client.create_post(
                    platform="linkedin",
                    text="Test Post",
                    media_ids=[],
                    account_id="li_123",
                )

        assert post_id == "post_xyz789"

    @pytest.mark.asyncio
    async def test_publish_post(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"url": "https://linkedin.com/post/live"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with set_env(**VALID_ENV):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                from blotato.blotato_client import BlotatoClient
                client = BlotatoClient()
                url = await client.publish_post("post_xyz789")

        assert url == "https://linkedin.com/post/live"

    @pytest.mark.asyncio
    async def test_unsupported_platform_raises(self):
        with set_env(**VALID_ENV):
            from blotato.blotato_client import BlotatoClient
            client = BlotatoClient()
            with pytest.raises(ValueError, match="Unsupported platform"):
                await client.create_post("tiktok", "text", [], "acc_1")

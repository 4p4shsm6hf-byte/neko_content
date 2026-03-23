import logging
import os
import aiofiles
import aiohttp
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def transcribe(self, audio_file_path: str) -> str:
        """Transcribe an audio file using OpenAI Whisper API."""
        logger.info(f"Transcribing audio file: {audio_file_path}")
        try:
            async with aiofiles.open(audio_file_path, "rb") as f:
                audio_bytes = await f.read()

            # openai async client expects a file-like object; use sync open via executor
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._transcribe_sync, audio_file_path)
            return result
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def _transcribe_sync(self, audio_file_path: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        with open(audio_file_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="de",
            )
        logger.info("Transcription successful")
        return response.text

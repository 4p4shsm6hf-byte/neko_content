import asyncio
import json
import logging
import os
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Modell über .env konfigurierbar – Standardwert ist ein zuverlässiges kostenloses Modell.
# Empfehlungen: meta-llama/llama-3.1-8b-instruct:free, google/gemma-3-9b-it:free
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

# Feste NEKO-Hashtag-Bibliothek für Instagram – kein Modell erfindet Hashtags neu
NEKO_HASHTAGS = (
    "#NEKO #NEKOGmbH #Energieberatung #Nachhaltigkeit #Energiewende #Photovoltaik "
    "#Solar #PVAnlage #Solarenergie #Wärmepumpe #Heizung #Sanitär #KfWFörderung "
    "#Fördermittel #Rottweil #Deisslingen #Schwarzwald #RegionalerHandwerker "
    "#GreenEnergy #Klimaschutz #ErneuerbareEnergien #Energieeffizienz #SmartHome "
    "#Hausenergie #Eigenheim #EnergieSparen #Zukunft #Innovation"
)

SYSTEM_PROMPT = """Du bist der Social Media Manager der NEKO GmbH aus Deisslingen/Lauffen bei Rottweil.
NEKO steht für NEue KOnzepte – ganzheitliche Energieberatung mit den Leistungen Bad, Wärme & Strom.
Gegründet 2021 von Björn Fischer und Fabian Bahr. Leitgedanke: "Von der Idee zur Realität."
Werte: Integrität, Innovation, Qualität, Nachhaltigkeit, Effizienz, Kreativität, Vertrauen, Wohlbefinden.
Schreibe alle Posts auf Deutsch. Ton: professionell aber menschlich, inspirierend, nachhaltigkeitsfokussiert.
Themen: Photovoltaik/Solar, Wärmepumpen, Heizung, Sanitär/Bad, Energieberatung, Fördermittel.
WICHTIG: Erfinde keine Informationen die nicht im Rohmaterial stehen. Verwende nur die bereitgestellten Fakten."""

HISTORY_FILE = Path("logs/post_history.json")
# How many past posts per platform to include for variety guidance
HISTORY_CONTEXT_COUNT = 3


def _load_recent_posts(platform: str) -> list[str]:
    """Load the last HISTORY_CONTEXT_COUNT published posts for a platform."""
    if not HISTORY_FILE.exists():
        return []
    try:
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        texts = [entry[platform] for entry in history if platform in entry]
        return texts[-HISTORY_CONTEXT_COUNT:]
    except (json.JSONDecodeError, OSError, KeyError):
        return []


PLATFORM_INSTRUCTIONS = {
    "linkedin": """Erstelle einen LinkedIn-Post:
- Länge: 1.300–1.500 Zeichen
- Stil: Professionell, fachkundig, Fokus auf Expertise und Nachhaltigkeit
- Struktur: Einleitender Aufhänger, ggf. Bullet Points für technische Details, Abschluss
- Hashtags: 3–5 relevante Hashtags am Ende
- Keine Emojis außer sparsam am Anfang als Aufmerksamkeit
Antworte NUR mit dem fertigen Post-Text, kein Kommentar davor oder danach.""",

    "instagram": """Erstelle einen Instagram-Post:
- Haupttext: 150–300 Zeichen, visuell, emotional, nahbar
- Erster Satz: Starker Hook der sofort Aufmerksamkeit erzeugt
- Emojis erlaubt und erwünscht
- Darunter ZWEI Leerzeilen, dann die Hashtags aus der bereitgestellten Liste (wähle 20–25 passende aus)
- Format: [Haupttext]\n\n.\n\n[#hashtag1 #hashtag2 ...]
- WICHTIG: Verwende jeden Hashtag nur EINMAL, keine Duplikate
Antworte NUR mit dem fertigen Post-Text, kein Kommentar davor oder danach.""",

    "facebook": """Erstelle einen Facebook-Post:
- Länge: 300–500 Zeichen
- Stil: Locker, nahbar, Community-Fokus
- Abschluss: Eine Frage ans Publikum
- Hashtags: 3–5 am Ende
- Wenige Emojis optional
Antworte NUR mit dem fertigen Post-Text, kein Kommentar davor oder danach.""",
}


class ContentGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=OPENROUTER_BASE_URL,
        )

    async def _chat(self, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=8192,  # reasoning models consume tokens internally before outputting
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(
                f"Leere Antwort vom Modell '{OPENROUTER_MODEL}'. "
                "Prüfe ob der Modellname auf openrouter.ai korrekt ist."
            )
        return content.strip()

    async def generate_posts(
        self,
        project_name: str,
        transcription: str,
        media_description: str,
    ) -> dict[str, str]:
        """Generate LinkedIn, Instagram and Facebook posts from raw input (parallel)."""
        raw_content = (
            f"Projektname/Baustelle: {project_name}\n\n"
            f"Bericht vom Team (transkribiert): {transcription}\n\n"
            f"Medien: {media_description}"
        )

        platforms = list(PLATFORM_INSTRUCTIONS.keys())

        def build_prompt(platform: str) -> str:
            instruction = PLATFORM_INSTRUCTIONS[platform]
            extra = ""
            if platform == "instagram":
                extra = f"\n\nVerfügbare Hashtags (wähle 20–25 passende aus, keine Duplikate):\n{NEKO_HASHTAGS}"

            recent = _load_recent_posts(platform)
            history_block = ""
            if recent:
                examples = "\n---\n".join(recent)
                history_block = (
                    f"\n\n--- BEREITS VERÖFFENTLICHTE {platform.upper()}-POSTS (zur Orientierung) ---\n"
                    f"Vermeide ähnliche Einstiege, Formulierungen und Strukturen wie in diesen Posts:\n"
                    f"{examples}"
                )

            return f"{instruction}{extra}{history_block}\n\n--- ROHMATERIAL ---\n{raw_content}"

        logger.info(f"Generating posts for '{project_name}' (all platforms in parallel)")
        prompts = [build_prompt(p) for p in platforms]
        results = await asyncio.gather(*[self._chat(prompt) for prompt in prompts])

        posts = {}
        for platform, text in zip(platforms, results):
            posts[platform] = text
            logger.info(f"{platform} post generated ({len(text)} chars)")

        return posts

    async def revise_post(
        self,
        platform: str,
        original_post: str,
        feedback: str,
    ) -> str:
        """Revise a single post based on user feedback."""
        logger.info(f"Revising {platform} post based on feedback")
        instruction = PLATFORM_INSTRUCTIONS[platform]
        extra = ""
        if platform == "instagram":
            extra = f"\n\nVerfügbare Hashtags:\n{NEKO_HASHTAGS}"
        user_prompt = (
            f"{instruction}{extra}\n\n"
            f"--- ORIGINAL POST ---\n{original_post}\n\n"
            f"--- ÄNDERUNGSWUNSCH DES NUTZERS ---\n{feedback}\n\n"
            f"Überarbeite den Post entsprechend dem Feedback. Halte alle Plattform-Vorgaben ein."
        )
        return await self._chat(user_prompt)

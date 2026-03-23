import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/free"

SYSTEM_PROMPT = """Du bist der Social Media Manager der NEKO GmbH aus Deisslingen/Lauffen bei Rottweil.
NEKO steht für NEue KOnzepte – ganzheitliche Energieberatung mit den Leistungen Bad, Wärme & Strom.
Gegründet 2021 von Björn Fischer und Fabian Bahr. Leitgedanke: "Von der Idee zur Realität."
Werte: Integrität, Innovation, Qualität, Nachhaltigkeit, Effizienz, Kreativität, Vertrauen, Wohlbefinden.
Schreibe alle Posts auf Deutsch. Ton: professionell aber menschlich, inspirierend, nachhaltigkeitsfokussiert.
Themen: Photovoltaik/Solar, Wärmepumpen, Heizung, Sanitär/Bad, Energieberatung, Fördermittel."""

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
- Darunter ZWEI Leerzeilen, dann 20–30 relevante Hashtags in einem Block
- Format: [Haupttext]\n\n.\n\n[#hashtag1 #hashtag2 ...]
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
        """Generate LinkedIn, Instagram and Facebook posts from raw input."""
        raw_content = (
            f"Projektname/Baustelle: {project_name}\n\n"
            f"Bericht vom Team (transkribiert): {transcription}\n\n"
            f"Medien: {media_description}"
        )

        posts = {}
        for platform, instruction in PLATFORM_INSTRUCTIONS.items():
            logger.info(f"Generating {platform} post for '{project_name}'")
            user_prompt = f"{instruction}\n\n--- ROHMATERIAL ---\n{raw_content}"
            posts[platform] = await self._chat(user_prompt)
            logger.info(f"{platform} post generated ({len(posts[platform])} chars)")

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
        user_prompt = (
            f"{instruction}\n\n"
            f"--- ORIGINAL POST ---\n{original_post}\n\n"
            f"--- ÄNDERUNGSWUNSCH DES NUTZERS ---\n{feedback}\n\n"
            f"Überarbeite den Post entsprechend dem Feedback. Halte alle Plattform-Vorgaben ein."
        )
        return await self._chat(user_prompt)

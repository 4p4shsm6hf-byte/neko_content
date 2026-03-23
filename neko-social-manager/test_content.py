"""
Einmaliger Content-Test – generiert Posts für ein Beispiel-Projekt
und zeigt was an Blotato übergeben würde.
"""
import asyncio
import os
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

# TEST_MODE überschreiben damit der echte Generator läuft
os.environ["TEST_MODE"] = "false"

from content.content_generator import ContentGenerator


async def main():
    gen = ContentGenerator()

    print("⏳ Generiere Posts für '12 kWp PV-Anlage im Herzen Rottweils'...")
    print("=" * 60)

    posts = await gen.generate_posts(
        project_name="12 kWp PV-Anlage Rottweil Stadtmitte",
        transcription=(
            "Heute haben wir eine 12 kWp Photovoltaikanlage auf einem "
            "Einfamilienhaus mitten in Rottweil fertiggestellt. "
            "24 Module, Wechselrichter von SMA, Ausrichtung Süd. "
            "Der Kunde war super zufrieden, Inbetriebnahme lief reibungslos. "
            "Erwarteter Jahresertrag ca. 10.800 kWh – das deckt den Großteil "
            "des Haushaltsstroms. Förderung über KfW wurde optimal genutzt."
        ),
        media_description="3 Fotos vom Dach während der Montage vorhanden.",
    )

    for platform, text in posts.items():
        print(f"\n{'='*60}")
        print(f"  {platform.upper()}  ({len(text)} Zeichen)")
        print("="*60)
        print(text)

    print("\n" + "="*60)
    print("✅ Fertig – diese Texte würden an Blotato übergeben.")

asyncio.run(main())

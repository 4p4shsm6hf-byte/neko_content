# Skill: Neko Energiekonzepte Content

KI-gestützter Social Media Manager für die **NEKO GmbH** (Deisslingen/Lauffen bei Rottweil).
Wandelt Baustellenberichte automatisch in plattformoptimierte Posts für LinkedIn, Instagram und Facebook um.

---

## Architektur

```
Telegram (Baustellenbericht)
       │
       ▼
  media_handler.py  ──────────────────────────────────────┐
  transcriber.py (Whisper STT)                            │
       │                                                  │
       ▼                                                  │
  content_generator.py (Claude Sonnet)                   │
       │  LinkedIn / Instagram / Facebook Posts           │
       ▼                                                  │
  review_handler.py (Telegram Inline-Buttons)            │
       │  ✅ Freigabe                                     │
       ▼                                                  ▼
  blotato_client.py ──► upload_media ──► create_post ──► publish
       │
       ▼
  log_writer.py ──► logs/published_posts.md
```

**Komponenten:**
| Datei | Aufgabe |
|-------|---------|
| `bot/telegram_bot.py` | Empfang aller Medientypen, Session-Management |
| `bot/transcriber.py` | OpenAI Whisper → Transkription |
| `bot/media_handler.py` | Download & Beschreibung von Fotos/Videos |
| `content/content_generator.py` | Claude API → drei plattformoptimierte Posts |
| `content/platform_optimizer.py` | Längenvalidierung, Vorschau-Formatierung |
| `blotato/blotato_client.py` | Blotato REST API (Upload, Erstellen, Publizieren) |
| `review/review_handler.py` | Telegram Inline-Review & Überarbeitungsflow |
| `logs/log_writer.py` | Markdown-Log aller veröffentlichten Posts |

---

## Setup

### 1. Repository klonen & Dependencies installieren

```bash
git clone https://github.com/4p4shsm6hf-byte/neko_content.git
cd neko-social-manager
pip install -r requirements.txt
```

### 2. .env befüllen

```bash
cp .env.example .env
```

Öffne `.env` und trage alle Keys ein (siehe Anleitung unten).

### 3. Telegram Bot erstellen (via @BotFather)

1. Öffne Telegram → suche **@BotFather**
2. Sende `/newbot`
3. Name eingeben: z. B. `NEKO Content Bot`
4. Username eingeben (muss auf `bot` enden): z. B. `neko_content_bot`
5. Token kopieren → in `.env` als `TELEGRAM_BOT_TOKEN` eintragen

### 4. API Keys beschaffen

| Variable | Quelle |
|----------|--------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `BLOTATO_API_KEY` | Blotato Dashboard → Settings → API |

### 5. Blotato Account-IDs ermitteln

1. Im Blotato Dashboard einloggen
2. Navigiere zu **Social Accounts**
3. Klicke auf den jeweiligen Account (LinkedIn/Instagram/Facebook)
4. Die Account-ID findest du in der URL-Leiste oder in den Account-Details
5. Trage die IDs in `.env` ein

### 6. Bot starten

```bash
python main.py
```

---

## Verwendung

### Workflow

```
/baustelle Solaranlage Rottweil
  → Fotos senden 📷
  → Sprachnachricht aufnehmen 🎙️
  → Ggf. Text tippen ✍️
/fertig
  → Bot generiert 3 Posts (ca. 30s)
  → Review via Inline-Buttons
  → Freigabe → automatische Veröffentlichung
```

### Kommandos

| Kommando | Funktion |
|----------|----------|
| `/start` | Begrüßung & Anleitung |
| `/baustelle [Name]` | Neue Baustellen-Session starten |
| `/fertig` | Session beenden & Posts generieren |

### Review-Optionen pro Post

| Button | Aktion |
|--------|--------|
| ✅ Freigeben | Sofortige Veröffentlichung via Blotato |
| ✏️ Überarbeiten | Feedback eingeben → Claude überarbeitet den Post |
| ❌ Verwerfen | Post wird nicht veröffentlicht |

---

## Publish Log

Jeder veröffentlichte Post wird in `logs/published_posts.md` protokolliert:

```markdown
## [2025-06-01] – Solaranlage Rottweil

| Plattform | Status | Live-URL | Veröffentlicht am |
|-----------|--------|----------|-------------------|
| LinkedIn  | ✅ Veröffentlicht | [Link](https://...) | 2025-06-01 14:32 |
| Instagram | ✅ Veröffentlicht | [Link](https://...) | 2025-06-01 14:33 |
| Facebook  | ❌ Verworfen | – | – |
```

---

## Troubleshooting

### Bot antwortet nicht
- Token in `.env` prüfen
- `python main.py` ausgabe prüfen – alle Keys gesetzt?

### Transkription fehlgeschlagen
- `OPENAI_API_KEY` korrekt?
- Sprachnachricht-Dateiformat: `.ogg` (Telegram-Standard) wird unterstützt

### Blotato Fehler 401
- `BLOTATO_API_KEY` abgelaufen oder falsch

### Blotato Fehler 429
- Rate Limit – der Client wartet automatisch mit Exponential Backoff (bis 3 Versuche)

### Account-ID falsch
- In Blotato Dashboard → Social Accounts → Account-Details prüfen
- IDs sind case-sensitiv

### Posts zu kurz / zu lang
- `content/platform_optimizer.py` gibt Warnungen ins Log
- Claude-Prompt anpassen in `content/content_generator.py` → `PLATFORM_INSTRUCTIONS`

---
name: neko-telegram-bot
description: Telegram-Bot-Entwickler für den internen NEKO Vertriebs-Bot. Verwende diesen Skill immer wenn der Telegram-Bot gebaut, erweitert oder debuggt werden soll — dazu gehören Lead-Alerts, Nachfass-Erinnerungen, Pipeline-Tracking, Tagesreports, Montage-Koordination und alle Bot-Commands. Auch bei Fragen zur Telegram Bot API, grammy-Framework, Webhook-Setup, Inline-Keyboards, Supabase-Anbindung für Lead-Notifications, Cron-Jobs für scheduled Messages oder Integration mit dem bestehenden neko-tools Backend triggert dieser Skill. Der Bot ist ein INTERNES Tool für das NEKO-Team (nicht kundengerichtet) und lebt im gleichen Repository wie die Rechner-Tools.
---

# NEKO Telegram Vertriebs-Bot

Du bist der Entwickler des internen Telegram-Bots für das NEKO GmbH Vertriebsteam. Der Bot ist die Kommandozentrale für das 12-köpfige NEKO-Team: er pusht Lead-Alerts, erinnert an Follow-ups, zeigt die Pipeline und liefert Tagesreports.

## Kontext

NEKO ist ein Handwerksbetrieb aus Deißlingen bei Rottweil (Bad, Wärme, Strom) mit ~12 Mitarbeitern. Der Bot ist KEIN Kunden-Tool — NEKOs Endkunden (Hauseigentümer 35-65 Jahre) nutzen WhatsApp, nicht Telegram. Der Bot dient ausschließlich der internen Vertriebssteuerung.

Der Bot lebt im **gleichen Repository** wie die Rechner-Tools (Förder-Rechner, ROI-Simulator). Er nutzt die **gleiche Supabase-Datenbank** und den **gleichen Tech-Stack**. Die drei bestehenden Skills (neko-backend-dev, neko-frontend-dev, neko-qa-engineer) definieren die Architektur — dieser Skill erweitert sie um den Telegram-Kanal.

## Deine Rolle

Du baust und pflegst den Telegram-Bot: Commands, Inline-Keyboards, Webhook-Empfang für Lead-Events, Scheduled Messages (Cron), und die Supabase-Queries für Pipeline-Daten. Du arbeitest eng mit den anderen Skills zusammen:

- **neko-backend-dev**: Liefert die Lead-Daten via Supabase und die API-Endpunkte. Wenn ein Lead erfasst wird, triggert der Backend-Service den Bot (nicht umgekehrt).
- **neko-qa-engineer**: Schreibt Tests für die Bot-Commands und die Notification-Logik.
- **neko-frontend-dev**: Kein direkter Kontakt — der Bot hat kein Web-Frontend.

## Tech-Stack

- **Bot-Framework**: grammy (TypeScript, leichtgewichtig, exzellente Telegram Bot API Abdeckung)
- **Runtime**: Node.js >= 18 (gleich wie Backend)
- **Deployment**: Vercel Serverless Functions (Webhook-Modus, kein Long-Polling) ODER ein kleiner separater Prozess auf dem gleichen Server
- **Datenbank**: Supabase (gleiche Instanz wie die Rechner-Tools, erweiterte Tabellen)
- **Scheduled Jobs**: Vercel Cron ODER node-cron für Tagesreports und Erinnerungen
- **Sprache**: TypeScript (gleich wie das gesamte Projekt)

## Projektstruktur im bestehenden Repo

Der Bot wird NICHT als separates Repo gebaut, sondern als Modul im bestehenden `neko-tools/` Repository:

```
neko-tools/
├── api/                          # Bestehende Serverless Functions
│   ├── foerder-rechner/          # (besteht bereits)
│   ├── roi-simulator/            # (besteht bereits)
│   ├── telegram/                 # NEU: Telegram-spezifische Endpunkte
│   │   ├── webhook.ts            # POST /api/telegram/webhook — empfängt Telegram Updates
│   │   └── cron.ts               # GET /api/telegram/cron — Vercel Cron Endpunkt
│   └── shared/
│       ├── lead-service.ts       # (besteht bereits) → ERWEITERN um notifyTelegram()
│       ├── foerder-data.ts       # (besteht bereits)
│       └── ...
├── bot/                          # NEU: Bot-Logik
│   ├── index.ts                  # Bot-Instanz, Middleware, Command-Registration
│   ├── commands/
│   │   ├── start.ts              # /start — Begrüßung + Hilfe
│   │   ├── pipeline.ts           # /pipeline — Aktuelle Pipeline-Übersicht
│   │   ├── leads.ts              # /leads — Offene Leads auflisten
│   │   ├── heute.ts              # /heute — Heutige Termine und Aufgaben
│   │   ├── stats.ts              # /stats — Wochenstatistiken
│   │   └── hilfe.ts              # /hilfe — Befehlsübersicht
│   ├── notifications/
│   │   ├── lead-alert.ts         # Neue Lead-Benachrichtigung formatieren + senden
│   │   ├── follow-up.ts          # Nachfass-Erinnerungen prüfen + senden
│   │   └── daily-report.ts       # Tagesreport generieren + senden
│   ├── keyboards/
│   │   ├── lead-actions.ts       # Inline-Keyboard: "Anrufen" / "Termin" / "Erledigt"
│   │   ├── pipeline-filter.ts    # Inline-Keyboard: Filter nach Status
│   │   └── confirm.ts            # Bestätigungs-Keyboard: "Ja" / "Nein"
│   ├── callbacks/
│   │   ├── lead-callback.ts      # Callback-Handler für Lead-Action-Buttons
│   │   └── pipeline-callback.ts  # Callback-Handler für Pipeline-Filter
│   ├── middleware/
│   │   ├── auth.ts               # Nur autorisierte NEKO-Team-Mitglieder
│   │   └── error.ts              # Fehlerbehandlung + Logging
│   └── utils/
│       ├── format.ts             # Nachrichten-Formatierung (Markdown)
│       ├── supabase.ts           # Supabase-Client (gemeinsam mit Backend)
│       └── constants.ts          # Bot-Konfiguration, Chat-IDs
├── db/
│   ├── schema.sql                # (besteht bereits) → ERWEITERN
│   └── migrations/
│       └── 002_telegram_bot.sql  # NEU: Zusätzliche Tabellen/Spalten
├── lib/                          # (besteht bereits, shared Business-Logik)
├── tests/
│   ├── bot/                      # NEU: Bot-Tests
│   │   ├── commands.test.ts
│   │   ├── notifications.test.ts
│   │   └── callbacks.test.ts
│   └── ...                       # (bestehende Tests)
└── vercel.json                   # Cron-Config ergänzen
```

## Datenbank-Erweiterungen

Die bestehende `leads`-Tabelle aus dem Backend-Skill wird erweitert, plus neue Tabellen für den Bot:

```sql
-- Migration 002_telegram_bot.sql

-- Bestehende leads-Tabelle erweitern
ALTER TABLE leads ADD COLUMN status VARCHAR(30) DEFAULT 'neu';
-- Status-Werte: 'neu' | 'kontaktiert' | 'termin_geplant' | 'angebot_erstellt' | 'nachfassen' | 'gewonnen' | 'verloren'
ALTER TABLE leads ADD COLUMN zugewiesen_an VARCHAR(100);
-- Telegram-Username des zuständigen Team-Mitglieds
ALTER TABLE leads ADD COLUMN telegram_notified BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN letzte_aktion TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN naechste_aktion TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN notizen TEXT;

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_naechste_aktion ON leads(naechste_aktion);

-- Team-Mitglieder (autorisierte Bot-Nutzer)
CREATE TABLE team (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  telegram_user_id BIGINT UNIQUE NOT NULL,
  telegram_username VARCHAR(100),
  name VARCHAR(255) NOT NULL,
  rolle VARCHAR(50) NOT NULL,       -- 'vertrieb' | 'montage' | 'geschaeftsfuehrung'
  aktiv BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Aktivitätslog (wer hat was mit welchem Lead gemacht)
CREATE TABLE lead_aktivitaeten (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
  team_member_id UUID REFERENCES team(id),
  aktion VARCHAR(50) NOT NULL,      -- 'kontaktiert' | 'termin_geplant' | 'angebot_gesendet' | 'nachfass' | 'notiz'
  details TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_aktivitaeten_lead ON lead_aktivitaeten(lead_id);

-- Montage-Termine
CREATE TABLE termine (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  lead_id UUID REFERENCES leads(id),
  typ VARCHAR(30) NOT NULL,         -- 'aufmass' | 'angebot_bespr' | 'montage'
  datum DATE NOT NULL,
  uhrzeit_von TIME,
  uhrzeit_bis TIME,
  adresse TEXT,
  zugewiesen_an UUID REFERENCES team(id),
  notizen TEXT,
  erledigt BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_termine_datum ON termine(datum);
```

## Bot-Setup und Konfiguration

### Umgebungsvariablen

```env
# Telegram
TELEGRAM_BOT_TOKEN=             # Von @BotFather
TELEGRAM_WEBHOOK_SECRET=        # Selbst generierter Secret für Webhook-Verifizierung
NEKO_TEAM_CHAT_ID=              # Gruppen-Chat-ID des NEKO-Teams

# Supabase (gleich wie Backend)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=      # Service-Role, NICHT anon-key

# Optional
NEKO_GF_CHAT_IDS=               # Komma-separierte Chat-IDs der Geschäftsführer (für spezielle Alerts)
```

### Bot-Instanz (bot/index.ts)

```typescript
import { Bot, webhookCallback } from 'grammy';

const bot = new Bot(process.env.TELEGRAM_BOT_TOKEN!);

// Middleware
bot.use(authMiddleware);    // Nur Team-Mitglieder
bot.use(errorMiddleware);   // Fehler loggen, User informieren

// Commands registrieren
bot.command('start', startCommand);
bot.command('pipeline', pipelineCommand);
bot.command('leads', leadsCommand);
bot.command('heute', heuteCommand);
bot.command('stats', statsCommand);
bot.command('hilfe', hilfeCommand);

// Callback-Queries (Inline-Keyboard-Buttons)
bot.callbackQuery(/^lead:/, leadCallbackHandler);
bot.callbackQuery(/^pipeline:/, pipelineCallbackHandler);

export { bot };
export const handleWebhook = webhookCallback(bot, 'std/http');
```

### Webhook-Endpunkt (api/telegram/webhook.ts)

```typescript
import { handleWebhook } from '../../bot';

export default async function handler(req, res) {
  // Webhook-Secret prüfen
  const secret = req.headers['x-telegram-bot-api-secret-token'];
  if (secret !== process.env.TELEGRAM_WEBHOOK_SECRET) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  await handleWebhook(req, res);
}
```

## Die 5 Kernfunktionen im Detail

### 1. Lead-Alerts (notifications/lead-alert.ts)

Wird aufgerufen wenn ein neuer Lead in der Datenbank landet. Der Trigger kommt aus dem **bestehenden Backend** — erweitere `api/shared/lead-service.ts`:

```typescript
// In lead-service.ts — nach Supabase-Insert ERGÄNZEN:
import { sendLeadAlert } from '../../bot/notifications/lead-alert';

async function saveLead(data: LeadInput): Promise<Lead> {
  const lead = await supabase.from('leads').insert(data).select().single();
  
  // Bestehend: E-Mail an NEKO
  await sendLeadEmail(lead);
  
  // NEU: Telegram-Alert
  await sendLeadAlert(lead);
  
  return lead;
}
```

Die Lead-Alert-Nachricht soll so aussehen:

```
🔔 Neuer Lead — Förder-Rechner

👤 Max Mustermann
📧 max@example.com
📞 +49 173 1234567
📍 78652 Deißlingen

💡 Wärmepumpe EFH (Bj. 1985)
💰 Förderbetrag: 14.000 € (70%)
📄 PDF heruntergeladen: Ja

⏰ Vor 2 Minuten

[📞 Anrufen] [📅 Termin] [✅ Erledigt]
```

Die drei Buttons am Ende sind ein Inline-Keyboard. Beim Klick:
- **Anrufen**: Setzt Status auf "kontaktiert", loggt Aktivität, fragt nach Notiz
- **Termin**: Fragt nach Datum/Uhrzeit, erstellt Termin in der DB
- **Erledigt**: Markiert Lead als bearbeitet

### 2. Nachfass-Erinnerungen (notifications/follow-up.ts)

Läuft als Cron-Job alle 2 Stunden. Prüft:

```typescript
async function checkFollowUps() {
  // Leads die seit > 24h im Status 'neu' sind
  const unbearbeitete = await supabase
    .from('leads')
    .select('*')
    .eq('status', 'neu')
    .lt('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString());
  
  // Leads mit überfälligem naechste_aktion
  const ueberfaellige = await supabase
    .from('leads')
    .select('*')
    .eq('status', 'nachfassen')
    .lt('naechste_aktion', new Date().toISOString());
  
  // Leads 3 Tage nach Aufmaß ohne Follow-up
  const nachAufmass = await supabase
    .from('termine')
    .select('*, leads(*)')
    .eq('typ', 'aufmass')
    .eq('erledigt', true)
    .filter('leads.status', 'eq', 'termin_geplant');
    // → 3 Tage nach Termin prüfen
  
  for (const lead of unbearbeitete) {
    await sendFollowUpReminder(lead, 'unbearbeitet');
  }
  // ... analog für überfällige und nach-Aufmaß
}
```

Nachricht:

```
⚠️ Nachfass-Erinnerung

👤 Max Mustermann — seit 2 Tagen unbearbeitet
📞 +49 173 1234567
💡 Wärmepumpe, 14.000 € Förderung

[📞 Jetzt anrufen] [⏰ Morgen erinnern] [❌ Kein Interesse]
```

### 3. Pipeline-Überblick (commands/pipeline.ts)

Per `/pipeline` zeigt der Bot:

```
📊 NEKO Pipeline — Stand 24.03.2026

🆕 Neu:              7 Leads
📞 Kontaktiert:       4 Leads  
📅 Termin geplant:    3 Leads
📝 Angebot erstellt:  2 Leads
🔄 Nachfassen:        1 Lead
✅ Gewonnen (Monat):  5 Leads
❌ Verloren (Monat):  2 Leads

💰 Potenzial offen: ~87.000 €

[🆕 Neue anzeigen] [📅 Termine] [📊 Details]
```

Die Buttons filtern die Ansicht. "Neue anzeigen" listet die 7 neuen Leads mit je einem Inline-Keyboard.

Die Potenzial-Berechnung: Summe der Investitionskosten aller offenen Leads (Status != gewonnen/verloren).

### 4. Tages-Report (notifications/daily-report.ts)

Jeden Morgen um 7:30 via Cron-Job:

```typescript
// api/telegram/cron.ts
import { sendDailyReport } from '../../bot/notifications/daily-report';

export default async function handler(req, res) {
  // Cron-Secret prüfen (Vercel setzt CRON_SECRET Header)
  if (req.headers.authorization !== `Bearer ${process.env.CRON_SECRET}`) {
    return res.status(401).end();
  }
  
  await sendDailyReport();
  res.status(200).json({ ok: true });
}
```

```json
// vercel.json (ergänzen)
{
  "crons": [
    {
      "path": "/api/telegram/cron",
      "schedule": "30 5 * * 1-5"
    }
  ]
}
```

(5:30 UTC = 7:30 MEZ, Mo-Fr)

Nachricht:

```
☀️ Guten Morgen NEKO-Team!

📅 Termine heute (24.03.):
  09:00 — Aufmaß bei Müller, Rottweil (Ben)
  14:00 — Angebot Bespr. Schmidt, VS (Lars)

🔔 Offene Aktionen:
  3× Leads unbearbeitet (> 24h)
  1× Nachfass überfällig (Meier)

📊 Gestern:
  2 neue Leads (1× PV, 1× Wärmepumpe)
  1 Angebot erstellt
  0 Abschlüsse

[📊 Pipeline öffnen] [📋 Alle Termine]
```

### 5. Montage-Koordination (über /heute und Termin-System)

Einfache Terminverwaltung per Bot:

```
/heute
```

Zeigt alle Termine des Tages, gruppiert nach Team-Mitglied. Jeder Termin hat Buttons:

```
📅 Heute — 24.03.2026

🔧 Ben:
  09:00-11:00 Aufmaß Müller
  Musterstraße 5, 78628 Rottweil
  [✅ Erledigt] [📝 Notiz]

🔧 Lars:
  14:00-15:00 Angebot Schmidt
  Hauptstr. 12, 78050 VS
  [✅ Erledigt] [📝 Notiz]

Keine weiteren Termine heute.
```

## Auth-Middleware (bot/middleware/auth.ts)

Nur autorisierte Team-Mitglieder dürfen den Bot nutzen:

```typescript
import { supabase } from '../utils/supabase';

async function authMiddleware(ctx, next) {
  const userId = ctx.from?.id;
  if (!userId) return;
  
  const { data: member } = await supabase
    .from('team')
    .select('*')
    .eq('telegram_user_id', userId)
    .eq('aktiv', true)
    .single();
  
  if (!member) {
    await ctx.reply('⛔ Du bist nicht als NEKO-Team-Mitglied registriert. Kontaktiere die Geschäftsführung.');
    return;
  }
  
  // Team-Member an Context anhängen für spätere Nutzung
  ctx.teamMember = member;
  await next();
}
```

Team-Mitglieder werden einmalig in der `team`-Tabelle angelegt. Neue Mitglieder registriert die Geschäftsführung per `/register @username Name Rolle`.

## Nachrichten-Formatierung (bot/utils/format.ts)

Alle Nachrichten nutzen Telegram MarkdownV2. Zentrale Formatierungsfunktionen:

```typescript
function formatEuro(betrag: number): string {
  return betrag.toLocaleString('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
}

function formatLeadSummary(lead: Lead): string {
  const tool = lead.tool === 'foerder-rechner' ? 'Förder-Rechner' : 'ROI-Simulator';
  const massnahme = lead.eingabedaten?.massnahme || 'k.A.';
  const betrag = lead.ergebnis?.foerderbetrag 
    ? formatEuro(lead.ergebnis.foerderbetrag) 
    : lead.ergebnis?.gesamtersparnis_25j 
      ? formatEuro(lead.ergebnis.gesamtersparnis_25j) + ' (25J)'
      : 'k.A.';
  
  return [
    `👤 *${escapeMarkdown(lead.name || 'Unbekannt')}*`,
    lead.email ? `📧 ${escapeMarkdown(lead.email)}` : null,
    lead.telefon ? `📞 ${escapeMarkdown(lead.telefon)}` : null,
    lead.postleitzahl ? `📍 ${escapeMarkdown(lead.postleitzahl)}` : null,
    '',
    `💡 ${escapeMarkdown(massnahme)} \\(${escapeMarkdown(tool)}\\)`,
    `💰 ${escapeMarkdown(betrag)}`,
    lead.pdf_generiert ? '📄 PDF heruntergeladen: Ja' : null,
  ].filter(Boolean).join('\n');
}

function escapeMarkdown(text: string): string {
  return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
}
```

## Integration mit dem bestehenden Backend

### Trigger-Punkt: lead-service.ts erweitern

Die zentrale Änderung am bestehenden Code ist minimal — eine Funktion am Ende von `saveLead()`:

```typescript
// api/shared/lead-service.ts — BESTEHENDE Datei, ERGÄNZEN

import { sendLeadAlert } from '../../bot/notifications/lead-alert';

// Am Ende von saveLead():
try {
  await sendLeadAlert(lead);
} catch (err) {
  // Telegram-Fehler dürfen den Lead-Save NICHT blockieren
  console.error('Telegram notification failed:', err);
}
```

Wichtige Regel: **Telegram-Fehler dürfen niemals die Lead-Erfassung blockieren.** Der try/catch ist Pflicht. Wenn der Bot down ist, kommen die Leads trotzdem rein und die E-Mail geht raus.

### Gleicher Supabase-Client

Der Bot nutzt den gleichen Supabase-Client wie das Backend:

```typescript
// bot/utils/supabase.ts
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // Service-Role für vollen Zugriff
);
```

## Webhook-Setup (einmalig)

Nach dem Deployment muss der Webhook bei Telegram registriert werden:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://tools.neko-bws.de/api/telegram/webhook",
    "secret_token": "${TELEGRAM_WEBHOOK_SECRET}",
    "allowed_updates": ["message", "callback_query"]
  }'
```

## Bot-Commands Übersicht

Registriere diese Commands bei @BotFather für die Autovervollständigung:

```
start - Bot starten und Hilfe anzeigen
pipeline - Aktuelle Vertriebs-Pipeline
leads - Offene Leads auflisten
heute - Heutige Termine und Aufgaben
stats - Wochenstatistiken
hilfe - Alle Befehle anzeigen
```

## Sicherheitsregeln

1. **Webhook-Secret immer prüfen** — jeder Request an /api/telegram/webhook MUSS den Secret-Header haben
2. **Auth-Middleware auf ALLEN Commands** — kein Befehl ohne Team-Mitglied-Check
3. **Keine Kundendaten in Gruppen-Nachrichten loggen** — Lead-Details nur in den Team-Chat, nie in öffentliche Gruppen
4. **Supabase Service-Role-Key nur serverseitig** — nie im Client-Code
5. **Rate Limiting für Bot-Commands** — max. 5 Commands pro User pro Minute (Spam-Schutz falls Account kompromittiert)
6. **DSGVO**: Leads werden mit Einwilligung erfasst (via Rechner-Tools). Team-interne Verarbeitung ist durch berechtigtes Interesse gedeckt. Keine Weiterleitung an Dritte.

## Zusammenarbeit mit den anderen Skills

- **neko-backend-dev**: Erweitert `lead-service.ts` um den Telegram-Trigger. Erweitert das DB-Schema um die Migration `002_telegram_bot.sql`. Alle Supabase-Queries im Bot nutzen die gleichen Typen und Schemas.
- **neko-qa-engineer**: Schreibt Tests für Bot-Commands (Mocking der grammy Bot-API), Notification-Logik (Cron-Trigger simulieren), und Callback-Handler. Nutzt die bestehenden Fixtures aus `tests/fixtures/testpersonen.json`.
- **neko-frontend-dev**: Kein direkter Kontakt. Aber: Die Lead-Daten die der Bot anzeigt kommen aus den gleichen API-Responses wie die Rechner-Widgets — Konsistenz der Datenformate ist wichtig.

## Erweiterbarkeit

Der Bot ist bewusst einfach gehalten. Spätere Erweiterungen:

- **WhatsApp Business API** für Kunden-Follow-ups (der Bot könnte das triggern)
- **Google Calendar Sync** für Termine
- **Automatische Angebots-Erstellung** per Bot-Command
- **KI-gestützte Lead-Bewertung** (Lead-Scoring basierend auf Eingabedaten)
- **Montage-Foto-Upload** direkt per Telegram → Referenz-Seite

Aber: **Erst die 5 Kernfunktionen stabil bauen**, dann erweitern.

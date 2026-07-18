"""
KI-Generierung von Server-Bauplänen (Kategorien, Kanäle, Rollen) per Groq.

Modell: openai/gpt-oss-20b - Nachfolger von llama-3.1-8b-instant, das Groq
am 17.06.2026 als veraltet markiert hat. gpt-oss-20b liefert bessere
Ergebnisse bei ähnlicher Geschwindigkeit.

Ein "Plan" ist immer ein Dict in diesem Format:
{
  "categories": [
    {"name": "📋 INFORMATIONEN", "channels": [
        {"name": "regeln", "type": "text", "topic": "Kurze Beschreibung"},
        {"name": "team-chat", "type": "text", "visible_to": ["Teamleitung"]}
    ]},
    ...
  ],
  "roles": [
    {"name": "Admin", "color": "#e74c3c", "hoist": true},
    ...
  ]
}

"topic" (optional) wird als Kanalbeschreibung gesetzt (nur bei Textkanälen).
"visible_to" (optional) ist eine Liste von Rollennamen aus demselben Plan -
ist es gesetzt, wird der Kanal für @everyone unsichtbar gemacht und nur für
die genannten Rollen sichtbar (z.B. für Team-/Admin-interne Kanäle).

Dieses Format wird sowohl von der KI-Generierung als auch von den
vorgefertigten Templates (templates.py) und von Backups (storage.py)
verwendet, damit apply_plan() in bot.py überall gleich funktioniert.
"""

import os
import json
import asyncio
import logging

try:
    from groq import Groq
except ImportError:
    Groq = None

log = logging.getLogger("server-setup-bot")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if (Groq and GROQ_API_KEY) else None

MODEL = "openai/gpt-oss-20b"

# Whitelist der Berechtigungen, die die KI/Vorlagen Rollen zuweisen dürfen.
# Bewusst kuratiert statt "alles erlaubt" - keine gefährlichen/seltenen Flags
# wie z.B. "administrator" leichtfertig an zu viele Rollen vergeben zu lassen.
ALLOWED_ROLE_PERMISSIONS = {
    "administrator",       # nur für die eine echte Top-Leitungsrolle gedacht
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_messages",
    "manage_nicknames",
    "manage_webhooks",
    "manage_events",
    "kick_members",
    "ban_members",
    "moderate_members",    # Timeout/Mute per Discord-eigenem System
    "mute_members",
    "deafen_members",
    "move_members",
    "mention_everyone",
    "view_audit_log",
    "create_instant_invite",
    "change_nickname",
}

SCHEMA_HINWEIS = """Antworte AUSSCHLIESSLICH mit validem JSON, keine Markdown-Codeblöcke,
kein Fließtext davor oder danach. Halte dich exakt an dieses Format:

{
  "categories": [
    {"name": "📋 KATEGORIE-NAME", "channels": [
        {"name": "📜-kanal-name", "type": "text", "topic": "Kurze Beschreibung, max. 10 Wörter"},
        {"name": "🎙️-sprachkanal-name", "type": "voice"},
        {"name": "team-interner-kanal", "type": "text", "visible_to": ["Rollen-Name"]}
    ]}
  ],
  "roles": [
    {"name": "Rollen-Name", "color": "#RRGGBB", "hoist": true, "permissions": ["kick_members", "ban_members"]}
  ]
}

Regeln:
- Maximal 6 Kategorien, maximal 6 Kanäle pro Kategorie, maximal 10 Rollen
- Kanalnamen klein geschrieben, mit Bindestrichen statt Leerzeichen (Discord-Konvention)
- "type" ist entweder "text" oder "voice"
- "topic" ist optional, nur bei "text"-Kanälen sinnvoll, kurz und beschreibt den Zweck des Kanals
- EMOJIS: Jede Kategorie bekommt IMMER genau ein passendes Emoji am Anfang des Namens
  (z.B. "🚔 EINSATZBEREICH"). Bei Kanälen: wähle für die wichtigsten/auffälligsten Kanäle
  (Regeln, Ankündigungen, Support, besondere Voice-Channels, Highlights) ein treffendes,
  thematisch cleveres Emoji als Präfix (z.B. "📜-regeln", "🚨-notruf", "🎙️-funkverkehr").
  Bei normalen/alltäglichen Chat-Kanälen (allgemein, off-topic) reicht ein einfacher Name
  ohne Emoji. Übertreibe es nicht - Qualität und thematische Treffsicherheit vor Quantität.
- "visible_to" ist optional: eine Liste mit GENAU den Rollennamen aus dem "roles"-Array
  (Groß-/Kleinschreibung muss exakt übereinstimmen). Nutze das NUR für wirklich interne/sensible
  Kanäle (z.B. Team-Besprechungen, interne Berichte, Admin-Logs) - nicht für normale/öffentliche Kanäle.
  Die meisten Kanäle brauchen KEIN "visible_to".
- "color" ist ein Hex-Code, sinnvoll passend zur Rolle (z.B. rot für Admin/Leitung)
- "hoist" = true bei wichtigen/sichtbaren Rollen (Leitung, Team), sonst false
- "permissions" ist optional, eine Liste ECHTER Discord-Berechtigungen für diese Rolle,
  NUR aus dieser erlaubten Liste: administrator, manage_guild, manage_roles, manage_channels,
  manage_messages, manage_nicknames, manage_webhooks, manage_events, kick_members, ban_members,
  moderate_members, mute_members, deafen_members, move_members, mention_everyone, view_audit_log,
  create_instant_invite, change_nickname.
  Vergib "administrator" NUR an die eine echte oberste Leitungsrolle (z.B. Owner/CEO/Präsident),
  niemals an mehrere Rollen. Moderations-Rollen bekommen eine sinnvolle Kombination wie
  kick_members + ban_members + manage_messages + moderate_members. Normale Mitglieder-Rollen
  bekommen meist GAR KEINE "permissions" (leeres Array oder Feld weglassen) - nur Standardrechte.
- Passe Kategorien, Kanäle, Rollen UND Topics inhaltlich sinnvoll und kreativ an das
  gewünschte Thema an - denk dir zum Thema passende, konkrete Details aus statt generischer
  Standardnamen. Ein Polizei-Server braucht andere Kanäle als eine Anime-Community.
"""


def _clean_json(raw: str) -> str:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    # Falls trotz Anweisung noch Text vor/nach dem JSON steht (z.B. Reasoning-Reste),
    # das erste vollstaendige {...}-Objekt herausschneiden statt komplett zu scheitern.
    if cleaned and not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    return cleaned


def _validate_and_clean_plan(plan: dict) -> dict:
    """Stellt sicher, dass 'visible_to' nur auf tatsächlich existierende Rollen im
    selben Plan verweist - falls die KI sich einen Rollennamen ausdenkt, der gar
    nicht existiert, wird die Einschränkung sicherheitshalber verworfen statt
    einen kaputten Verweis zu erzeugen. Filtert außerdem 'permissions' auf die
    Whitelist und lässt 'administrator' nur bei maximal einer Rolle zu."""
    role_names = {r.get("name") for r in plan.get("roles", [])}
    for cat in plan.get("categories", []):
        for ch in cat.get("channels", []):
            if "visible_to" in ch:
                ch["visible_to"] = [r for r in ch["visible_to"] if r in role_names]
                if not ch["visible_to"]:
                    del ch["visible_to"]

    admin_already_vergeben = False
    for role in plan.get("roles", []):
        perms = role.get("permissions", [])
        if not isinstance(perms, list):
            perms = []
        perms = [p for p in perms if p in ALLOWED_ROLE_PERMISSIONS]

        if "administrator" in perms:
            if admin_already_vergeben:
                perms.remove("administrator")  # nur die erste Rolle darf Administrator behalten
            else:
                admin_already_vergeben = True

        if perms:
            role["permissions"] = perms
        elif "permissions" in role:
            del role["permissions"]

    return plan


async def _call_groq(prompt: str, temperature: float) -> dict:
    async def _once(reasoning_effort: str, max_tokens: int) -> str:
        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,  # "low" laesst mehr Tokens fuer die eigentliche Antwort statt fuers interne "Nachdenken"
        )
        return completion.choices[0].message.content

    raw = await _once("low", 4000)
    if not raw or not raw.strip():
        # gpt-oss-Modelle koennen bei knappem Budget ihr komplettes Token-Limit fuers
        # interne Reasoning verbrauchen und dann keine sichtbare Antwort mehr liefern.
        # Ein zweiter Versuch mit noch mehr Spielraum behebt das in den allermeisten Faellen.
        log.warning("Leere KI-Antwort erhalten, versuche es erneut mit mehr Token-Budget...")
        raw = await _once("low", 6000)

    if not raw or not raw.strip():
        raise RuntimeError(
            "Die KI hat keine verwertbare Antwort geliefert (auch nach Wiederholung). "
            "Versuch es bitte nochmal, evtl. mit einem kuerzeren/einfacheren Thema."
        )

    plan = json.loads(_clean_json(raw))
    return _validate_and_clean_plan(plan)


async def generate_plan(thema: str) -> dict:
    """Erstellt per KI einen kompletten Serverplan zu einem freien Thema."""
    if not groq_client:
        raise RuntimeError("Kein GROQ_API_KEY konfiguriert - KI-Generierung nicht verfügbar.")

    prompt = f"""Erstelle einen durchdachten, kreativen Discord-Server-Bauplan für
folgendes Thema: "{thema}"

Denk dir konkrete, zum Thema passende Kanäle und Rollen aus - keine generischen
Platzhalter. Nutze "topic" für Kanalbeschreibungen und "visible_to" für wirklich
interne Kanäle (Team-Besprechungen, Berichte, Logs).

{SCHEMA_HINWEIS}"""

    return await _call_groq(prompt, temperature=0.7)


async def adjust_plan(thema: str, previous_plan: dict, adjustment: str) -> dict:
    """Passt einen bestehenden Plan anhand einer Anweisung des Nutzers an."""
    if not groq_client:
        raise RuntimeError("Kein GROQ_API_KEY konfiguriert - KI-Generierung nicht verfügbar.")

    prompt = f"""Ursprüngliches Thema: "{thema}"

Aktueller Bauplan (JSON):
{json.dumps(previous_plan, ensure_ascii=False)}

Der Nutzer möchte folgende Änderung: "{adjustment}"

Gib den KOMPLETTEN aktualisierten Bauplan zurück (nicht nur die Änderung),
mit der Anpassung eingearbeitet. Behalte gute bestehende Topics/visible_to-
Einstellungen bei, wo sie noch sinnvoll sind.

{SCHEMA_HINWEIS}"""

    return await _call_groq(prompt, temperature=0.5)

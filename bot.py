"""
Server-Setup-Bot - globaler Discord-Bot für automatischen Server-Aufbau
=========================================================================
Läuft auf beliebig vielen Servern gleichzeitig (globaler Bot, keine
serverspezifische Konfiguration nötig).

Funktionen:
1. /server-erstellen thema:<text> - KI erstellt einen Bauplan (Kategorien,
   Kanäle, Rollen) passend zum Thema (z.B. "Polizei-Server"). Vorschau wird
   gezeigt, Nutzer bestätigt, passt an oder bricht ab, bevor irgendwas
   angelegt wird.
2. /server-vorlagen - Bibliothek fertiger Vorlagen (Polizei, Gaming,
   Support, Wirtschaft, Community) zur direkten Anwendung.
3. /server-backup-erstellen name:<text> - sichert die aktuelle Struktur
   (Kategorien, Kanäle, Rollen) des Servers unter einem Namen.
4. /server-backup-liste - zeigt gespeicherte Backups für diesen Server.
5. /server-backup-anwenden name:<text> - wendet ein gespeichertes Backup an.
   Ergänzt nur fehlende Kanäle/Rollen, löscht nie etwas Bestehendes.
6. /server-backup-loeschen name:<text> - löscht ein gespeichertes Backup.
7. /server-loeschen ziel:<Auswahl> - löscht Kanäle/Kategorien/Rollen oder
   alles auf einmal. Zeigt IMMER erst eine Vorschau, bei "Alles löschen"
   muss zusätzlich das Wort "LÖSCHEN" eingetippt werden, damit nichts aus
   Versehen passiert. Braucht Administrator-Rechte (höhere Hürde als die
   anderen Befehle, wegen der destruktiven Wirkung).
8. /genesis-stats - zeigt die globale Statistik (wie viele Server, Kanäle
   und Rollen Genesis insgesamt über alle Server hinweg erschaffen hat).
9. /genesis-level - zeigt den Level-Stand DIESES Servers jederzeit (nicht
   nur direkt nach dem Bauen sichtbar wie im Abschluss-Embed).
10. /credits - zeigt Infos zum Entwickler, Tech-Stack und weiteren Links.

Jeder erfolgreiche Build bekommt außerdem ein generiertes Bild-Zertifikat
(siehe certificate.py) im Cyberpunk-Look als Anhang zum Abschluss-Embed.

Alle erstellenden Befehle brauchen "Server verwalten" beim ausführenden
Nutzer. Der Bot selbst braucht "Kanäle verwalten" + "Rollen verwalten"
(am einfachsten: Administrator) als Server-Berechtigung.

Stack: discord.py 2.7+, Groq API (Llama 3.1) für die KI-Generierung,
JSON-Storage für Backups (siehe storage.py).
"""

import os
import random
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import ai
import templates
import storage
import certificate

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # deine Discord-User-ID fuer Owner-only Befehle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("server-setup-bot")

def is_owner(user_id: int) -> bool:
    return OWNER_ID != 0 and user_id == OWNER_ID


class MaintenanceActive(app_commands.CheckFailure):
    pass


class GuildBlacklisted(app_commands.CheckFailure):
    pass


class SecureCommandTree(app_commands.CommandTree):
    """Eigene CommandTree-Klasse, damit ein globaler Sicherheits-Check vor
    JEDEM Slash-Command laeuft. discord.py bietet dafuer keinen einfachen
    @tree.check-Decorator wie bei prefix commands.Bot - der korrekte Weg ist
    das Ueberschreiben von interaction_check() in einer eigenen Tree-Klasse."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_owner(interaction.user.id):
            return True
        if interaction.guild_id and await storage.is_blacklisted(interaction.guild_id):
            raise GuildBlacklisted("Dieser Server wurde von der Nutzung ausgeschlossen.")
        if await storage.get_maintenance_mode():
            raise MaintenanceActive("Genesis befindet sich gerade im Wartungsmodus. Bitte später erneut versuchen.")
        return True


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents, tree_cls=SecureCommandTree)


# ---------------------------------------------------------------------------
# Plan anwenden (gemeinsam für KI-Pläne, Vorlagen und Backups)
# ---------------------------------------------------------------------------

def _hex_to_color(hex_str: str) -> discord.Color:
    try:
        return discord.Color(int(hex_str.lstrip("#"), 16))
    except (ValueError, AttributeError):
        return discord.Color.default()


def _permissions_from_list(names: list) -> discord.Permissions:
    """Baut ein discord.Permissions-Objekt aus einer Liste von Berechtigungsnamen.
    Nutzt dieselbe Whitelist wie ai.py (ai.ALLOWED_ROLE_PERMISSIONS) als
    einzige Quelle der Wahrheit, damit KI-Pläne und Vorlagen konsistent geprüft werden."""
    perms = discord.Permissions.none()
    for name in names or []:
        if name in ai.ALLOWED_ROLE_PERMISSIONS and hasattr(discord.Permissions, name):
            setattr(perms, name, True)
    return perms


BUILD_QUIPS = [
    "Kalibriere Hierarchie-Matrix...",
    "Male Rollen in Neonfarben...",
    "Verlege digitale Kabel...",
    "Bestechen die Rate-Limit-Gnome...",
    "Falte den Server-Raum...",
    "Gieße das Fundament aus reinem Cyan...",
    "Frage die KI nach der Postleitzahl...",
    "Poliere die Kanal-Icons...",
    "Synchronisiere Paralleluniversen...",
    "Verhandle mit der Discord-API...",
]


LEVEL_TITLES = [
    (0, "🌱 Rookie Architect"),
    (20, "🔧 Structural Engineer"),
    (50, "🏗️ Master Builder"),
    (100, "💎 Elite Architect"),
    (200, "👑 GENESIS LEGEND"),
]


def _level_for(total_items: int) -> tuple[int, str, int, int | None]:
    """Gibt (Level-Nummer, Titel, aktuelle Schwelle, nächste Schwelle) zurück."""
    level = 1
    title = LEVEL_TITLES[0][1]
    current_threshold = 0
    next_threshold = LEVEL_TITLES[1][0] if len(LEVEL_TITLES) > 1 else None
    for i, (threshold, name) in enumerate(LEVEL_TITLES):
        if total_items >= threshold:
            level = i + 1
            title = name
            current_threshold = threshold
            next_threshold = LEVEL_TITLES[i + 1][0] if i + 1 < len(LEVEL_TITLES) else None
    return level, title, current_threshold, next_threshold


def _tier_for(total_items: int) -> tuple[str, discord.Color]:
    if total_items >= 25:
        return "🌌 S-TIER SERVER", discord.Color.from_rgb(155, 107, 255)
    if total_items >= 15:
        return "🔥 A-TIER SERVER", discord.Color.from_rgb(45, 212, 238)
    if total_items >= 8:
        return "✨ B-TIER SERVER", discord.Color.from_rgb(52, 211, 153)
    return "🌱 STARTER SERVER", discord.Color.from_rgb(125, 134, 153)


def build_progress_bar(done: int, total: int, width: int = 18) -> str:
    total = max(total, 1)
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * done / total)
    return f"`{bar}` **{pct}%**"


def build_progress_embed(title: str, done: int, total: int, current_label: str) -> discord.Embed:
    quip = random.choice(BUILD_QUIPS)
    embed = discord.Embed(
        title=title,
        description=(
            f"{build_progress_bar(done, total)}\n\n"
            f"⚙️ Gerade erstellt: **{current_label}**\n"
            f"*{quip}*"
        ),
        color=discord.Color.from_rgb(45, 212, 238),
    )
    embed.set_footer(text=f"{done}/{total} Schritte abgeschlossen")
    return embed


def build_success_embed(
    guild: discord.Guild, counts: dict, global_stats: dict | None = None, guild_lifetime: dict | None = None
) -> discord.Embed:
    total_items = counts["roles"] + counts["categories"] + counts["channels"]
    tier_label, tier_color = _tier_for(total_items)

    critical = random.random() < 0.1  # 10% Chance auf einen besonderen Moment
    if critical:
        tier_label = "🌈 CRITICAL BUILD — LEGENDARY!"
        tier_color = discord.Color.gold()

    description = f"**{guild.name}** wurde erfolgreich erschaffen.\n\n{tier_label}"
    if critical:
        description += "\n*Ein kosmischer Zufall hat diesen Server außergewöhnlich gemacht.*"

    embed = discord.Embed(
        title="⚡ GENESIS ABGESCHLOSSEN",
        description=description,
        color=tier_color,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="📁 Kategorien", value=str(counts["categories"]), inline=True)
    embed.add_field(name="# Kanäle", value=str(counts["channels"]), inline=True)
    embed.add_field(name="🎭 Rollen", value=str(counts["roles"]), inline=True)
    if counts.get("skipped"):
        embed.add_field(name="⏭️ Übersprungen (bereits vorhanden)", value=str(counts["skipped"]), inline=False)

    if guild_lifetime:
        level, title, cur, nxt = _level_for(guild_lifetime["total_items"])
        if nxt is not None:
            progress_in_level = guild_lifetime["total_items"] - cur
            level_span = nxt - cur
            xp_bar = build_progress_bar(progress_in_level, level_span, width=14)
            xp_text = f"{xp_bar}\n{guild_lifetime['total_items']}/{nxt} Elemente insgesamt"
        else:
            xp_text = f"Maximalstufe erreicht - {guild_lifetime['total_items']} Elemente insgesamt erschaffen"
        embed.add_field(
            name=f"🧬 Server-Level {level} — {title}",
            value=xp_text,
            inline=False,
        )

    if global_stats:
        embed.add_field(
            name="🌐 Genesis-Rekord",
            value=f"Server-Erschaffung Nr. **{global_stats['runs']}** insgesamt · "
                  f"{global_stats['channels']} Kanäle über alle Server hinweg erschaffen",
            inline=False,
        )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Genesis · Phil7442 × Developer Studio")
    return embed, critical, total_items


async def apply_plan(guild: discord.Guild, plan: dict, merge: bool = False, progress=None) -> dict:
    """
    Erstellt Rollen, Kategorien und Kanäle aus einem Plan.
    merge=True: bereits existierende Rollen/Kanäle (gleicher Name) werden
    übersprungen statt dupliziert - wichtig für Backup-Wiederherstellung,
    damit nichts Bestehendes verdoppelt oder überschrieben wird.
    progress: optionaler async Callback progress(done, total, label) für
    eine Live-Fortschrittsanzeige während der Erstellung.
    """
    counts = {"roles": 0, "categories": 0, "channels": 0, "skipped": 0}
    total = len(plan.get("roles", [])) + sum(len(c.get("channels", [])) + 1 for c in plan.get("categories", []))
    done = 0
    role_map: dict[str, discord.Role] = {}  # Name -> Role-Objekt, für visible_to-Berechtigungen
    admin_bereits_vergeben = False  # Defense-in-Depth: unabhängig von der Planquelle max. 1x Administrator

    async def tick(label: str):
        nonlocal done
        done += 1
        if progress:
            await progress(done, total, label)

    for role_spec in plan.get("roles", []):
        name = role_spec.get("name", "Neue Rolle")[:100]
        existing = discord.utils.get(guild.roles, name=name)
        if merge and existing:
            role_map[name] = existing
            counts["skipped"] += 1
            await tick(f"🎭 {name} (übersprungen)")
            continue

        role_perms = list(role_spec.get("permissions", []) or [])
        if "administrator" in role_perms:
            if admin_bereits_vergeben:
                role_perms = [p for p in role_perms if p != "administrator"]
            else:
                admin_bereits_vergeben = True

        try:
            new_role = await guild.create_role(
                name=name,
                color=_hex_to_color(role_spec.get("color", "#99aab5")),
                hoist=bool(role_spec.get("hoist", False)),
                permissions=_permissions_from_list(role_perms),
                reason="Server-Setup-Bot: Rolle aus Plan erstellt",
            )
            role_map[name] = new_role
            counts["roles"] += 1
            perm_icon = " ⚡" if role_perms else ""
            await tick(f"🎭 Rolle {name}{perm_icon}")
        except discord.Forbidden:
            log.warning(f"Keine Berechtigung, Rolle '{name}' zu erstellen.")
            await tick(f"🎭 {name} (Fehler)")

    for cat_spec in plan.get("categories", []):
        cat_name = cat_spec.get("name", "Kategorie")[:100]
        category = discord.utils.get(guild.categories, name=cat_name) if merge else None

        if category is None:
            try:
                category = await guild.create_category(
                    cat_name, reason="Server-Setup-Bot: Kategorie aus Plan erstellt"
                )
                counts["categories"] += 1
                await tick(f"📁 {cat_name}")
            except discord.Forbidden:
                log.warning(f"Keine Berechtigung, Kategorie '{cat_name}' zu erstellen.")
                await tick(f"📁 {cat_name} (Fehler)")
                continue
        else:
            await tick(f"📁 {cat_name} (vorhanden)")

        for ch_spec in cat_spec.get("channels", []):
            ch_name = ch_spec.get("name", "kanal")[:100]
            ch_type = ch_spec.get("type", "text")
            topic = ch_spec.get("topic")
            visible_to = ch_spec.get("visible_to")

            if merge and discord.utils.get(category.channels, name=ch_name):
                counts["skipped"] += 1
                await tick(f"# {ch_name} (übersprungen)")
                continue

            # Berechtigungen vorbereiten, falls der Kanal auf bestimmte Rollen beschränkt sein soll
            # Discord's API verlangt IMMER ein Dict (auch leer), None fuehrt zu TypeError
            overwrites = {}
            if visible_to:
                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                for role_name in visible_to:
                    role_obj = role_map.get(role_name) or discord.utils.get(guild.roles, name=role_name)
                    if role_obj:
                        overwrites[role_obj] = discord.PermissionOverwrite(view_channel=True)

            try:
                if ch_type == "voice":
                    await category.create_voice_channel(
                        ch_name, reason="Server-Setup-Bot", overwrites=overwrites
                    )
                else:
                    await category.create_text_channel(
                        ch_name, topic=topic, reason="Server-Setup-Bot", overwrites=overwrites
                    )
                counts["channels"] += 1
                lock_icon = "🔒" if visible_to else ""
                await tick(f"{'🔊' if ch_type == 'voice' else '#'} {ch_name}{lock_icon}")
            except discord.Forbidden:
                log.warning(f"Keine Berechtigung, Kanal '{ch_name}' zu erstellen.")
                await tick(f"# {ch_name} (Fehler)")

    return counts


def scan_current_server(guild: discord.Guild) -> dict:
    """Baut einen Plan aus der aktuellen Serverstruktur (für Backups)."""
    categories = []
    for cat in guild.categories:
        channels = []
        for ch in cat.channels:
            if isinstance(ch, discord.TextChannel):
                channels.append({"name": ch.name, "type": "text"})
            elif isinstance(ch, discord.VoiceChannel):
                channels.append({"name": ch.name, "type": "voice"})
        categories.append({"name": cat.name, "channels": channels})

    uncategorized = [
        ch for ch in guild.channels
        if ch.category is None and isinstance(ch, (discord.TextChannel, discord.VoiceChannel))
    ]
    if uncategorized:
        categories.append({
            "name": "Ohne Kategorie",
            "channels": [
                {"name": ch.name, "type": "text" if isinstance(ch, discord.TextChannel) else "voice"}
                for ch in uncategorized
            ],
        })

    roles = []
    for r in guild.roles:
        if r.is_default() or r.managed:
            continue
        perms = [name for name in ai.ALLOWED_ROLE_PERMISSIONS if getattr(r.permissions, name, False)]
        role_entry = {
            "name": r.name,
            "color": f"#{r.color.value:06x}" if r.color.value else "#99aab5",
            "hoist": r.hoist,
        }
        if perms:
            role_entry["permissions"] = perms
        roles.append(role_entry)

    return {"categories": categories, "roles": roles}


# ---------------------------------------------------------------------------
# Löschen (mit Vorschau + Bestätigung, siehe DeleteConfirmView weiter unten)
# ---------------------------------------------------------------------------

DELETE_MODES = {
    "kategorie": "Eine bestimmte Kategorie (inkl. ihrer Kanäle)",
    "alle_kanaele": "Alle Kanäle und Kategorien (Rollen bleiben erhalten)",
    "alle_rollen": "Alle selbst erstellten Rollen (Kanäle bleiben erhalten)",
    "alles": "ALLES - Kanäle, Kategorien und Rollen (kompletter Reset)",
}


def plan_selbst_erstellte_rollen(guild: discord.Guild) -> list[discord.Role]:
    """Rollen, die grundsätzlich löschbar sind - nie @everyone oder von Discord/Bots verwaltete Rollen."""
    return [r for r in guild.roles if not r.is_default() and not r.managed]


def scan_delete_preview(guild: discord.Guild, mode: str, category_name: str | None = None) -> dict:
    """Ermittelt, was bei einem Löschmodus konkret betroffen wäre - für die Vorschau."""
    if mode == "kategorie":
        cat = discord.utils.get(guild.categories, name=category_name) if category_name else None
        if not cat:
            return {"categories": [], "channels": [], "roles": []}
        return {
            "categories": [cat.name],
            "channels": [ch.name for ch in cat.channels],
            "roles": [],
        }
    if mode == "alle_kanaele":
        return {
            "categories": [c.name for c in guild.categories],
            "channels": [ch.name for ch in guild.channels if isinstance(ch, (discord.TextChannel, discord.VoiceChannel))],
            "roles": [],
        }
    if mode == "alle_rollen":
        return {"categories": [], "channels": [], "roles": [r.name for r in plan_selbst_erstellte_rollen(guild)]}
    if mode == "alles":
        return {
            "categories": [c.name for c in guild.categories],
            "channels": [ch.name for ch in guild.channels if isinstance(ch, (discord.TextChannel, discord.VoiceChannel))],
            "roles": [r.name for r in plan_selbst_erstellte_rollen(guild)],
        }
    return {"categories": [], "channels": [], "roles": []}


async def execute_delete(guild: discord.Guild, mode: str, category_name: str | None = None) -> dict:
    """Führt das eigentliche Löschen aus. Wird erst nach expliziter Bestätigung aufgerufen."""
    counts = {"categories": 0, "channels": 0, "roles": 0, "fehler": 0}

    async def delete_channels_and_categories(categories: list[discord.CategoryChannel]):
        for cat in categories:
            for ch in list(cat.channels):
                try:
                    await ch.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                    counts["channels"] += 1
                except discord.Forbidden:
                    counts["fehler"] += 1
            try:
                await cat.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                counts["categories"] += 1
            except discord.Forbidden:
                counts["fehler"] += 1

    if mode == "kategorie":
        cat = discord.utils.get(guild.categories, name=category_name) if category_name else None
        if cat:
            await delete_channels_and_categories([cat])

    elif mode == "alle_kanaele":
        await delete_channels_and_categories(list(guild.categories))
        # Kanäle ohne Kategorie separat behandeln
        for ch in list(guild.channels):
            if ch.category is None and isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    await ch.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                    counts["channels"] += 1
                except discord.Forbidden:
                    counts["fehler"] += 1

    elif mode == "alle_rollen":
        for role in plan_selbst_erstellte_rollen(guild):
            try:
                await role.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                counts["roles"] += 1
            except discord.Forbidden:
                counts["fehler"] += 1

    elif mode == "alles":
        await delete_channels_and_categories(list(guild.categories))
        for ch in list(guild.channels):
            if ch.category is None and isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    await ch.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                    counts["channels"] += 1
                except discord.Forbidden:
                    counts["fehler"] += 1
        for role in plan_selbst_erstellte_rollen(guild):
            try:
                await role.delete(reason="Server-Setup-Bot: Löschung bestätigt")
                counts["roles"] += 1
            except discord.Forbidden:
                counts["fehler"] += 1

    return counts



def build_preview_embed(title: str, plan: dict) -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.blurple())

    for cat in plan.get("categories", []):
        lines = []
        for ch in cat.get("channels", []):
            icon = "🔊" if ch.get("type") == "voice" else "#"
            lock = " 🔒" if ch.get("visible_to") else ""
            lines.append(f"{icon} {ch.get('name')}{lock}")
        embed.add_field(
            name=cat.get("name", "Kategorie"),
            value="\n".join(lines) if lines else "*(keine Kanäle)*",
            inline=True,
        )

    roles = plan.get("roles", [])
    if roles:
        role_lines = [f"● {r.get('name')}" for r in roles]
        embed.add_field(name="🎭 Rollen", value="\n".join(role_lines)[:1024], inline=False)

    locked_channels = [
        ch.get("name") for cat in plan.get("categories", []) for ch in cat.get("channels", []) if ch.get("visible_to")
    ]
    if locked_channels:
        embed.add_field(
            name="🔒 Eingeschränkt sichtbar",
            value=", ".join(locked_channels)[:1024],
            inline=False,
        )

    total_channels = sum(len(c.get("channels", [])) for c in plan.get("categories", []))
    embed.set_footer(
        text=f"{len(plan.get('categories', []))} Kategorien · {total_channels} Kanäle · {len(roles)} Rollen"
    )
    return embed


def build_delete_preview_embed(mode: str, preview: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ Löschvorschau - bitte genau prüfen!",
        description=f"**Modus:** {DELETE_MODES.get(mode, mode)}\n\nDas hier wird **unwiderruflich gelöscht**:",
        color=discord.Color.red(),
    )
    if preview["categories"]:
        embed.add_field(
            name=f"📁 Kategorien ({len(preview['categories'])})",
            value="\n".join(preview["categories"])[:1024] or "-",
            inline=True,
        )
    if preview["channels"]:
        embed.add_field(
            name=f"# Kanäle ({len(preview['channels'])})",
            value="\n".join(preview["channels"])[:1024] or "-",
            inline=True,
        )
    if preview["roles"]:
        embed.add_field(
            name=f"🎭 Rollen ({len(preview['roles'])})",
            value="\n".join(preview["roles"])[:1024] or "-",
            inline=True,
        )
    if not preview["categories"] and not preview["channels"] and not preview["roles"]:
        embed.add_field(name="Nichts gefunden", value="Es gibt nichts zu löschen für diese Auswahl.", inline=False)
    embed.set_footer(text="Diese Aktion kann NICHT rückgängig gemacht werden.")
    return embed


# ---------------------------------------------------------------------------
# Views: Vorschau bestätigen / anpassen / abbrechen
# ---------------------------------------------------------------------------

class AdjustModal(discord.ui.Modal, title="Plan anpassen"):
    adjustment = discord.ui.TextInput(
        label="Was soll geändert werden?",
        style=discord.TextStyle.paragraph,
        placeholder="z.B. 'Füge einen Voice-Channel für Streife hinzu' oder 'Entferne die Rolle Anwärter'",
        required=True,
        max_length=300,
    )

    def __init__(self, thema: str, plan: dict, parent_view: "PlanPreviewView"):
        super().__init__()
        self.thema = thema
        self.plan = plan
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            new_plan = await ai.adjust_plan(self.thema, self.plan, self.adjustment.value)
        except Exception as e:
            await interaction.followup.send(f"Anpassung fehlgeschlagen: {e}", ephemeral=True)
            return

        new_view = PlanPreviewView(self.thema, new_plan, merge=self.parent_view.merge)
        embed = build_preview_embed(f"📋 Vorschau (angepasst): {self.thema}", new_plan)
        # interaction.message = die urspruengliche Nachricht mit dem Button, der das Modal
        # geoeffnet hat. edit_original_response wuerde stattdessen auf DIESE Modal-Interaktion
        # zielen, die keine eigene sichtbare Nachricht hat -> "Unknown Message"-Fehler.
        if interaction.message:
            await interaction.message.edit(embed=embed, view=new_view)
        else:
            await interaction.followup.send(embed=embed, view=new_view)


class PlanPreviewView(discord.ui.View):
    def __init__(self, thema: str, plan: dict, merge: bool = False):
        super().__init__(timeout=600)
        self.thema = thema
        self.plan = plan
        self.merge = merge
        if not ai.groq_client:
            # Ohne KI-Zugang kann nicht angepasst werden
            for item in list(self.children):
                if getattr(item, "custom_id", "") == "plan_anpassen":
                    self.remove_item(item)

    @discord.ui.button(label="✅ Erstellen", style=discord.ButtonStyle.success, custom_id="plan_erstellen")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # Kurze "Boot-Sequenz" fürs Cinematic-Gefühl, bevor der eigentliche Bau startet
        boot_lines = [
            "`> genesis.core --init`",
            "`> genesis.core --init`\n`> lade Bauplan-Module... OK`",
            "`> genesis.core --init`\n`> lade Bauplan-Module... OK`\n`> verbinde mit Discord-Gateway... OK`",
            "`> genesis.core --init`\n`> lade Bauplan-Module... OK`\n`> verbinde mit Discord-Gateway... OK`\n`> starte Konstruktionssequenz...`",
        ]
        for line in boot_lines:
            boot_embed = discord.Embed(description=line, color=discord.Color.from_rgb(45, 212, 238))
            try:
                await interaction.edit_original_response(embed=boot_embed, view=self)
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.45)

        last_edit = 0.0

        async def on_progress(done, total, label):
            nonlocal last_edit
            now = asyncio.get_event_loop().time()
            # Fortschritt höchstens alle ~1s aktualisieren, um Rate Limits zu schonen
            if now - last_edit < 1.0 and done < total:
                return
            last_edit = now
            embed = build_progress_embed(f"🛠️ Erschaffe {self.thema}...", done, total, label)
            try:
                await interaction.edit_original_response(embed=embed, view=self)
            except discord.HTTPException:
                pass

        counts = await apply_plan(interaction.guild, self.plan, merge=self.merge, progress=on_progress)

        global_stats = None
        guild_lifetime = None
        try:
            global_stats = await storage.record_creation(counts["roles"], counts["categories"], counts["channels"])
            guild_lifetime = await storage.record_guild_creation(
                interaction.guild.id, counts["roles"], counts["categories"], counts["channels"]
            )
            await storage.add_audit_entry(
                interaction.guild.id, interaction.guild.name, str(interaction.user),
                f"Plan '{self.thema}' erstellt ({counts['categories']} Kat., {counts['channels']} Kanäle, {counts['roles']} Rollen)",
            )
        except Exception as e:
            log.warning(f"Stats konnten nicht aktualisiert werden: {e}")

        success_embed, critical, total_items = build_success_embed(
            interaction.guild, counts, global_stats, guild_lifetime
        )

        # Bild-Zertifikat generieren und ins Embed einbetten
        if critical:
            cert_tier_label = "CRITICAL BUILD — LEGENDARY"
        else:
            cert_tier_label, _ = _tier_for(total_items)
        if guild_lifetime:
            cert_level, cert_level_title, _, _ = _level_for(guild_lifetime["total_items"])
        else:
            cert_level, cert_level_title = 1, LEVEL_TITLES[0][1]

        cert_file = None
        try:
            buffer = certificate.build_certificate(
                guild_name=interaction.guild.name,
                tier_label=cert_tier_label,
                level_title=cert_level_title,
                level_number=cert_level,
                counts=counts,
                critical=critical,
            )
            cert_file = discord.File(buffer, filename="genesis_certificate.png")
            success_embed.set_image(url="attachment://genesis_certificate.png")
        except Exception as e:
            log.warning(f"Zertifikat konnte nicht erstellt werden: {e}")

        if cert_file:
            msg = await interaction.edit_original_response(embed=success_embed, view=self, attachments=[cert_file])
        else:
            msg = await interaction.edit_original_response(embed=success_embed, view=self)

        # Feier-Reaktionen bei besonders großen Builds oder einem Critical Build
        if msg and (critical or total_items >= 15):
            for emoji in ("⚡", "🎉", "🚀"):
                try:
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    break

    @discord.ui.button(label="✏️ Anpassen", style=discord.ButtonStyle.secondary, custom_id="plan_anpassen")
    async def adjust(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdjustModal(self.thema, self.plan, self))

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.danger, custom_id="plan_abbrechen")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Abgebrochen, es wurde nichts erstellt.", view=self)


class TemplateSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=key)
            for key, label in templates.get_template_choices()
        ]
        super().__init__(placeholder="Vorlage auswählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        plan = templates.get_template_plan(self.values[0])
        label = dict(templates.get_template_choices())[self.values[0]]
        embed = build_preview_embed(f"📋 Vorschau: {label}", plan)
        view = PlanPreviewView(label, plan, merge=False)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class TemplateSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TemplateSelect())


class ConfirmAllModal(discord.ui.Modal, title="Endgültig alles löschen?"):
    bestaetigung = discord.ui.TextInput(
        label="Tippe LÖSCHEN um zu bestätigen",
        placeholder="LÖSCHEN",
        required=True,
        max_length=20,
    )

    def __init__(self, mode: str, category_name: str | None, parent_view: "DeleteConfirmView"):
        super().__init__()
        self.mode = mode
        self.category_name = category_name
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        if self.bestaetigung.value.strip().upper() != "LÖSCHEN":
            await interaction.response.send_message(
                "Abgebrochen - der eingegebene Text stimmte nicht mit 'LÖSCHEN' überein.", ephemeral=True
            )
            return
        await interaction.response.defer()
        counts = await execute_delete(interaction.guild, self.mode, self.category_name)
        try:
            await storage.add_audit_entry(
                interaction.guild.id, interaction.guild.name, str(interaction.user),
                f"Löschung ({self.mode}): {counts['categories']} Kat., {counts['channels']} Kanäle, {counts['roles']} Rollen",
            )
        except Exception as e:
            log.warning(f"Audit-Log fehlgeschlagen: {e}")
        for item in self.parent_view.children:
            item.disabled = True
        # Siehe Kommentar bei AdjustModal: interaction.message ist die urspruengliche
        # Nachricht mit dem "Endgueltig loeschen"-Button, nicht die Modal-Interaktion selbst.
        if interaction.message:
            await interaction.message.edit(view=self.parent_view)
        await interaction.followup.send(
            f"🗑️ Gelöscht: {counts['categories']} Kategorien, {counts['channels']} Kanäle, "
            f"{counts['roles']} Rollen." + (f" ({counts['fehler']} Fehler wegen fehlender Berechtigung)" if counts["fehler"] else ""),
            ephemeral=True,
        )


class DeleteConfirmView(discord.ui.View):
    def __init__(self, mode: str, category_name: str | None = None):
        super().__init__(timeout=120)
        self.mode = mode
        self.category_name = category_name

    @discord.ui.button(label="🗑️ Endgültig löschen", style=discord.ButtonStyle.danger, custom_id="delete_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Bei "alles" zusätzliche Tipp-Bestätigung verlangen - höchste Gefahrenstufe
        if self.mode == "alles":
            await interaction.response.send_modal(ConfirmAllModal(self.mode, self.category_name, self))
            return

        await interaction.response.defer()
        counts = await execute_delete(interaction.guild, self.mode, self.category_name)
        try:
            await storage.add_audit_entry(
                interaction.guild.id, interaction.guild.name, str(interaction.user),
                f"Löschung ({self.mode}): {counts['categories']} Kat., {counts['channels']} Kanäle, {counts['roles']} Rollen",
            )
        except Exception as e:
            log.warning(f"Audit-Log fehlgeschlagen: {e}")
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(
            f"🗑️ Gelöscht: {counts['categories']} Kategorien, {counts['channels']} Kanäle, "
            f"{counts['roles']} Rollen." + (f" ({counts['fehler']} Fehler wegen fehlender Berechtigung)" if counts["fehler"] else ""),
            ephemeral=True,
        )

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary, custom_id="delete_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Abgebrochen, es wurde nichts gelöscht.", view=self)


# ---------------------------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="server-erstellen", description="KI erstellt einen Serverbauplan zu einem freien Thema")
@app_commands.describe(thema="z.B. 'Polizei-Server', 'Anime-Community', 'Handwerksbetrieb RP'")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.guild_id)  # max. 1x pro 30s pro Server, schuetzt vor KI-Kosten-Missbrauch
async def server_erstellen(interaction: discord.Interaction, thema: str):
    await interaction.response.defer(thinking=True)
    try:
        plan = await ai.generate_plan(thema)
    except Exception as e:
        await interaction.followup.send(f"KI-Generierung fehlgeschlagen: {e}", ephemeral=True)
        return

    embed = build_preview_embed(f"📋 Vorschau: {thema}", plan)
    view = PlanPreviewView(thema, plan, merge=False)
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="server-vorlagen", description="Fertige Server-Vorlagen zur Auswahl")
@app_commands.checks.has_permissions(manage_guild=True)
async def server_vorlagen(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Wähl eine Vorlage aus der Liste:", view=TemplateSelectView(), ephemeral=True
    )


@bot.tree.command(name="server-backup-erstellen", description="Sichert die aktuelle Serverstruktur unter einem Namen")
@app_commands.describe(name="Name für dieses Backup, z.B. 'vor-umbau-2026'")
@app_commands.checks.has_permissions(manage_guild=True)
async def server_backup_erstellen(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    plan = scan_current_server(interaction.guild)
    await storage.save_backup(interaction.guild.id, name, plan)
    total_channels = sum(len(c["channels"]) for c in plan["categories"])
    await interaction.followup.send(
        f"✅ Backup **{name}** gespeichert ({len(plan['categories'])} Kategorien, "
        f"{total_channels} Kanäle, {len(plan['roles'])} Rollen).",
        ephemeral=True,
    )


@bot.tree.command(name="server-backup-liste", description="Zeigt gespeicherte Backups für diesen Server")
@app_commands.checks.has_permissions(manage_guild=True)
async def server_backup_liste(interaction: discord.Interaction):
    backups = await storage.list_backups(interaction.guild.id)
    if not backups:
        await interaction.response.send_message("Noch keine Backups für diesen Server gespeichert.", ephemeral=True)
        return
    lines = [f"**{b['name']}** — erstellt {b['created_at'][:10]}" for b in backups]
    await interaction.response.send_message("**Gespeicherte Backups:**\n" + "\n".join(lines), ephemeral=True)


async def backup_name_autocomplete(interaction: discord.Interaction, current: str):
    backups = await storage.list_backups(interaction.guild.id)
    return [
        app_commands.Choice(name=b["name"], value=b["name"])
        for b in backups if current.lower() in b["name"].lower()
    ][:25]


@bot.tree.command(name="server-backup-anwenden", description="Wendet ein gespeichertes Backup an (ergänzt nur Fehlendes)")
@app_commands.describe(name="Name des Backups")
@app_commands.autocomplete(name=backup_name_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def server_backup_anwenden(interaction: discord.Interaction, name: str):
    backup = await storage.get_backup(interaction.guild.id, name)
    if not backup:
        await interaction.response.send_message(f"Kein Backup namens '{name}' gefunden.", ephemeral=True)
        return
    embed = build_preview_embed(f"📋 Backup wiederherstellen: {name}", backup["plan"])
    embed.description = "Bereits vorhandene Kanäle/Rollen (gleicher Name) werden übersprungen, nichts wird gelöscht."
    view = PlanPreviewView(name, backup["plan"], merge=True)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="server-backup-loeschen", description="Löscht ein gespeichertes Backup")
@app_commands.describe(name="Name des Backups")
@app_commands.autocomplete(name=backup_name_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def server_backup_loeschen(interaction: discord.Interaction, name: str):
    deleted = await storage.delete_backup(interaction.guild.id, name)
    if deleted:
        await interaction.response.send_message(f"🗑️ Backup '{name}' gelöscht.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Kein Backup namens '{name}' gefunden.", ephemeral=True)


async def category_name_autocomplete(interaction: discord.Interaction, current: str):
    if not interaction.guild:
        return []
    return [
        app_commands.Choice(name=cat.name, value=cat.name)
        for cat in interaction.guild.categories
        if current.lower() in cat.name.lower()
    ][:25]


@bot.tree.command(name="genesis-level", description="Zeigt den Genesis-Level dieses Servers")
async def genesis_level(interaction: discord.Interaction):
    lifetime = await storage.get_guild_lifetime_stats(interaction.guild.id)
    total_items = lifetime.get("total_items", 0)
    level, title, cur, nxt = _level_for(total_items)

    embed = discord.Embed(
        title=f"🧬 Server-Level {level} — {title}",
        color=discord.Color.from_rgb(155, 107, 255),
    )
    if nxt is not None:
        progress_in_level = total_items - cur
        level_span = nxt - cur
        xp_bar = build_progress_bar(progress_in_level, level_span, width=18)
        embed.add_field(name="Fortschritt", value=f"{xp_bar}\n{total_items}/{nxt} Elemente insgesamt", inline=False)
    else:
        embed.add_field(name="Fortschritt", value=f"🏆 Maximalstufe erreicht - {total_items} Elemente insgesamt", inline=False)
    embed.add_field(name="Genesis-Läufe auf diesem Server", value=str(lifetime.get("runs", 0)), inline=True)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text="Level steigt mit jeder erfolgreichen Server-Erstellung/Wiederherstellung")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="credits", description="Zeigt Infos zum Entwickler und Tech-Stack von Genesis")
async def credits(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ GENESIS",
        description="KI-gestützter Server-Baumeister für Discord.",
        color=discord.Color.from_rgb(155, 107, 255),
    )
    embed.add_field(
        name="👤 Entwickelt von",
        value="**Phil7442 × Developer Studio**",
        inline=False,
    )
    embed.add_field(
        name="🛠️ Tech-Stack",
        value="discord.py · Groq (Llama 3.1) · PostgreSQL/JSON-Storage · Railway",
        inline=False,
    )
    embed.add_field(
        name="🌐 Mehr Infos",
        value="[genesis-bot1.netlify.app](https://genesis-bot1.netlify.app/)",
        inline=False,
    )
    embed.add_field(
        name="📋 Befehle",
        value="`/server-erstellen` · `/server-vorlagen` · `/server-backup-erstellen` · "
              "`/server-backup-liste` · `/server-backup-anwenden` · `/server-loeschen` · `/genesis-stats`",
        inline=False,
    )
    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text=f"Aktiv auf {len(bot.guilds)} Server(n)")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="genesis-stats", description="Zeigt die globale Genesis-Statistik über alle Server hinweg")
async def genesis_stats(interaction: discord.Interaction):
    stats = await storage.get_global_stats()
    embed = discord.Embed(
        title="🌐 Genesis — Globale Statistik",
        description="Was Genesis bisher über alle Server hinweg erschaffen hat:",
        color=discord.Color.from_rgb(155, 107, 255),
    )
    embed.add_field(name="⚡ Server-Erschaffungen", value=str(stats["runs"]), inline=True)
    embed.add_field(name="📁 Kategorien", value=str(stats["categories"]), inline=True)
    embed.add_field(name="# Kanäle", value=str(stats["channels"]), inline=True)
    embed.add_field(name="🎭 Rollen", value=str(stats["roles"]), inline=True)
    embed.add_field(name="🖥️ Aktive Server", value=str(len(bot.guilds)), inline=True)
    embed.set_footer(text="Genesis · Phil7442 × Developer Studio")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="server-loeschen", description="Löscht Kanäle, Rollen oder alles - mit Vorschau und Bestätigung")
@app_commands.describe(
    ziel="Was soll gelöscht werden?",
    kategorie="Nur nötig, wenn 'ziel' = Eine bestimmte Kategorie",
)
@app_commands.choices(ziel=[
    app_commands.Choice(name="Eine bestimmte Kategorie (inkl. ihrer Kanäle)", value="kategorie"),
    app_commands.Choice(name="Alle Kanäle und Kategorien (Rollen bleiben)", value="alle_kanaele"),
    app_commands.Choice(name="Alle selbst erstellten Rollen (Kanäle bleiben)", value="alle_rollen"),
    app_commands.Choice(name="ALLES - kompletter Reset", value="alles"),
])
@app_commands.autocomplete(kategorie=category_name_autocomplete)
@app_commands.checks.has_permissions(administrator=True)
async def server_loeschen(interaction: discord.Interaction, ziel: app_commands.Choice[str], kategorie: str = None):
    mode = ziel.value
    if mode == "kategorie" and not kategorie:
        await interaction.response.send_message(
            "Bei diesem Modus musst du auch eine Kategorie angeben.", ephemeral=True
        )
        return

    preview = scan_delete_preview(interaction.guild, mode, kategorie)
    if not preview["categories"] and not preview["channels"] and not preview["roles"]:
        await interaction.response.send_message("Es gibt nichts zu löschen für diese Auswahl.", ephemeral=True)
        return

    embed = build_delete_preview_embed(mode, preview)
    view = DeleteConfirmView(mode, kategorie)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# Fehlerbehandlung (fehlende Berechtigung etc.)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Owner-only Verwaltung (Wartungsmodus, Blacklist, Audit-Log)
# Nur fuer die Person mit der User-ID aus OWNER_ID nutzbar, unabhaengig von
# Server-Rollen - das ist bewusst getrennt von "Server verwalten", da es den
# Bot GLOBAL ueber alle Server hinweg steuert.
# ---------------------------------------------------------------------------

def _owner_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)
    return app_commands.check(predicate)


admin_group = app_commands.Group(name="genesis-admin", description="Owner-only: globale Steuerung von Genesis")


@admin_group.command(name="wartungsmodus", description="Wartungsmodus an/aus - waehrend aktiv reagiert Genesis auf keinem Server")
@app_commands.describe(status="An oder aus")
@app_commands.choices(status=[
    app_commands.Choice(name="An", value="on"),
    app_commands.Choice(name="Aus", value="off"),
])
@_owner_check()
async def admin_maintenance(interaction: discord.Interaction, status: app_commands.Choice[str]):
    await storage.set_maintenance_mode(status.value == "on")
    await interaction.response.send_message(f"🔧 Wartungsmodus ist jetzt **{status.name}**.", ephemeral=True)


@admin_group.command(name="blacklist-add", description="Sperrt einen Server für die Nutzung von Genesis")
@app_commands.describe(server_id="Die Server-ID, die gesperrt werden soll")
@_owner_check()
async def admin_blacklist_add(interaction: discord.Interaction, server_id: str):
    await storage.add_to_blacklist(int(server_id))
    await interaction.response.send_message(f"🚫 Server `{server_id}` wurde gesperrt.", ephemeral=True)


@admin_group.command(name="blacklist-remove", description="Hebt die Sperre eines Servers auf")
@app_commands.describe(server_id="Die Server-ID, die entsperrt werden soll")
@_owner_check()
async def admin_blacklist_remove(interaction: discord.Interaction, server_id: str):
    removed = await storage.remove_from_blacklist(int(server_id))
    msg = f"✅ Server `{server_id}` wurde entsperrt." if removed else f"Server `{server_id}` war nicht gesperrt."
    await interaction.response.send_message(msg, ephemeral=True)


@admin_group.command(name="blacklist-liste", description="Zeigt alle gesperrten Server")
@_owner_check()
async def admin_blacklist_list(interaction: discord.Interaction):
    bl = await storage.get_blacklist()
    if not bl:
        await interaction.response.send_message("Keine Server gesperrt.", ephemeral=True)
        return
    await interaction.response.send_message("🚫 Gesperrte Server:\n" + "\n".join(f"`{g}`" for g in bl), ephemeral=True)


@admin_group.command(name="audit-log", description="Zeigt die letzten Aktionen über alle Server hinweg")
@app_commands.describe(anzahl="Wie viele Einträge (Standard 20)")
@_owner_check()
async def admin_audit_log(interaction: discord.Interaction, anzahl: int = 20):
    entries = await storage.get_audit_log(anzahl)
    if not entries:
        await interaction.response.send_message("Noch keine Audit-Log-Einträge.", ephemeral=True)
        return
    lines = [
        f"`{e['timestamp'][:16]}` **{e['guild_name']}** — {e['user']}: {e['action']}"
        for e in entries
    ]
    await interaction.response.send_message("📋 **Audit-Log:**\n" + "\n".join(lines)[:1900], ephemeral=True)


@admin_group.command(name="verlassen", description="Lässt Genesis einen bestimmten Server verlassen")
@app_commands.describe(server_id="Die Server-ID, die Genesis verlassen soll")
@_owner_check()
async def admin_leave(interaction: discord.Interaction, server_id: str):
    guild = bot.get_guild(int(server_id))
    if not guild:
        await interaction.response.send_message("Genesis ist auf diesem Server nicht aktiv.", ephemeral=True)
        return
    name = guild.name
    await guild.leave()
    await interaction.response.send_message(f"✅ Genesis hat **{name}** verlassen.", ephemeral=True)


bot.tree.add_command(admin_group)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "Dafür brauchst du die Berechtigung 'Server verwalten'."
    elif isinstance(error, MaintenanceActive):
        msg = f"🔧 {error}"
    elif isinstance(error, GuildBlacklisted):
        msg = f"🚫 {error}"
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Bitte warte noch {error.retry_after:.0f} Sekunden, bevor du das erneut nutzt."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "Dafür bist du nicht berechtigt."
    else:
        msg = f"Es ist ein Fehler aufgetreten: {error}"
        log.error(f"Command-Fehler: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# ---------------------------------------------------------------------------
# Bot Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        log.info(f"{len(synced)} Slash-Commands global synchronisiert (kann bis zu 1h dauern, bis sie überall sichtbar sind).")
    except Exception as e:
        log.error(f"Sync fehlgeschlagen: {e}")
    await update_presence()
    log.info(f"Eingeloggt als {bot.user} (ID: {bot.user.id}) - aktiv auf {len(bot.guilds)} Server(n).")


async def update_presence():
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} Server erschaffen ⚡ /server-erstellen",
    )
    await bot.change_presence(activity=activity, status=discord.Status.online)


@bot.event
async def on_guild_join(guild: discord.Guild):
    await update_presence()


@bot.event
async def on_guild_remove(guild: discord.Guild):
    await update_presence()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN fehlt in den Environment Variables!")
    bot.run(DISCORD_TOKEN)

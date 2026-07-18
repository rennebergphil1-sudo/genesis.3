"""
Speicherung von Server-Backups als JSON-Datei, pro Discord-Server (Guild) getrennt.
Atomare Writes über os.replace(), gleiches Pattern wie bei NEXUS.

Ein Backup ist ein gespeicherter Plan (siehe ai.py für das Format) mit Namen
und Zeitstempel, damit man ihn später wieder anwenden kann.

Hinweis: Diese Datei liegt im Container-Dateisystem. Auf Railway geht der
Inhalt bei jedem Redeploy verloren, wenn kein Volume gemountet ist (siehe
README). Für den Start reicht das meist aus.
"""

import os
import json
import asyncio
from datetime import datetime, timezone

DATA_FILE = os.getenv("BACKUPS_FILE", "backups.json")
_lock = asyncio.Lock()


def _load_raw() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_raw(data: dict) -> None:
    tmp_path = f"{DATA_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, DATA_FILE)


async def save_backup(guild_id: int, name: str, plan: dict) -> None:
    async with _lock:
        data = _load_raw()
        key = str(guild_id)
        data.setdefault(key, [])
        # Gleicher Name wird überschrieben, damit keine Duplikate entstehen
        data[key] = [b for b in data[key] if b["name"] != name]
        data[key].append({
            "name": name,
            "plan": plan,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        _save_raw(data)


async def list_backups(guild_id: int) -> list[dict]:
    async with _lock:
        data = _load_raw()
        return data.get(str(guild_id), [])


async def get_backup(guild_id: int, name: str) -> dict | None:
    backups = await list_backups(guild_id)
    for b in backups:
        if b["name"] == name:
            return b
    return None


async def delete_backup(guild_id: int, name: str) -> bool:
    async with _lock:
        data = _load_raw()
        key = str(guild_id)
        if key not in data:
            return False
        before = len(data[key])
        data[key] = [b for b in data[key] if b["name"] != name]
        _save_raw(data)
        return len(data[key]) < before


# ---------------------------------------------------------------------------
# Globale Statistik (über alle Server hinweg) - reservierter Schlüssel "_stats",
# kollidiert nie mit einer echten Guild-ID, da die immer numerisch sind.
# ---------------------------------------------------------------------------

_STATS_KEY = "_stats"


async def record_creation(roles: int, categories: int, channels: int) -> dict:
    """Zählt eine erfolgreiche Erstellung in die globale Statistik ein und gibt den neuen Stand zurück."""
    async with _lock:
        data = _load_raw()
        stats = data.setdefault(_STATS_KEY, {
            "runs": 0, "roles": 0, "categories": 0, "channels": 0,
        })
        stats["runs"] += 1
        stats["roles"] += roles
        stats["categories"] += categories
        stats["channels"] += channels
        _save_raw(data)
        return stats


async def get_global_stats() -> dict:
    async with _lock:
        data = _load_raw()
        return data.get(_STATS_KEY, {"runs": 0, "roles": 0, "categories": 0, "channels": 0})


# ---------------------------------------------------------------------------
# Lifetime-Statistik PRO Server (für das Genesis-Level-System) - reservierter
# Schlüssel "_guild_stats", getrennt von den Backup-Listen (die direkt unter
# der Guild-ID liegen), damit bestehende Backups nicht beeinflusst werden.
# ---------------------------------------------------------------------------

_GUILD_STATS_KEY = "_guild_stats"


async def record_guild_creation(guild_id: int, roles: int, categories: int, channels: int) -> dict:
    async with _lock:
        data = _load_raw()
        guild_stats = data.setdefault(_GUILD_STATS_KEY, {})
        key = str(guild_id)
        entry = guild_stats.setdefault(key, {"runs": 0, "total_items": 0})
        entry["runs"] += 1
        entry["total_items"] += roles + categories + channels
        _save_raw(data)
        return entry


async def get_guild_lifetime_stats(guild_id: int) -> dict:
    async with _lock:
        data = _load_raw()
        return data.get(_GUILD_STATS_KEY, {}).get(str(guild_id), {"runs": 0, "total_items": 0})


# ---------------------------------------------------------------------------
# Sicherheitssystem: Wartungsmodus, Server-Blacklist, Audit-Log.
# Alle unter eigenen reservierten Schlüsseln, kollidieren nie mit Guild-IDs.
# ---------------------------------------------------------------------------

_MAINTENANCE_KEY = "_maintenance"
_BLACKLIST_KEY = "_blacklist"
_AUDIT_KEY = "_audit_log"
_AUDIT_MAX_ENTRIES = 300


async def get_maintenance_mode() -> bool:
    async with _lock:
        data = _load_raw()
        return bool(data.get(_MAINTENANCE_KEY, {}).get("enabled", False))


async def set_maintenance_mode(enabled: bool) -> None:
    async with _lock:
        data = _load_raw()
        data[_MAINTENANCE_KEY] = {"enabled": enabled}
        _save_raw(data)


async def get_blacklist() -> list[str]:
    async with _lock:
        data = _load_raw()
        return data.get(_BLACKLIST_KEY, [])


async def is_blacklisted(guild_id: int) -> bool:
    return str(guild_id) in await get_blacklist()


async def add_to_blacklist(guild_id: int) -> None:
    async with _lock:
        data = _load_raw()
        bl = set(data.get(_BLACKLIST_KEY, []))
        bl.add(str(guild_id))
        data[_BLACKLIST_KEY] = sorted(bl)
        _save_raw(data)


async def remove_from_blacklist(guild_id: int) -> bool:
    async with _lock:
        data = _load_raw()
        bl = set(data.get(_BLACKLIST_KEY, []))
        existed = str(guild_id) in bl
        bl.discard(str(guild_id))
        data[_BLACKLIST_KEY] = sorted(bl)
        _save_raw(data)
        return existed


async def add_audit_entry(guild_id: int, guild_name: str, user: str, action: str) -> None:
    async with _lock:
        data = _load_raw()
        log = data.setdefault(_AUDIT_KEY, [])
        log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guild_id": str(guild_id),
            "guild_name": guild_name,
            "user": user,
            "action": action,
        })
        # Nur die letzten N Eintraege behalten, damit die Datei nicht unbegrenzt waechst
        data[_AUDIT_KEY] = log[-_AUDIT_MAX_ENTRIES:]
        _save_raw(data)


async def get_audit_log(limit: int = 50) -> list[dict]:
    async with _lock:
        data = _load_raw()
        log = data.get(_AUDIT_KEY, [])
        return list(reversed(log[-limit:]))

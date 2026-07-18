"""
Fertige Server-Vorlagen (Backups/Templates) im gleichen Planformat wie ai.py.
Jede Vorlage kann direkt per apply_plan() in bot.py angewendet werden.

Kanäle nutzen gezielt Emojis für die wichtigsten/auffälligsten Stellen
(Regeln, Ankündigungen, besondere Voice-Channels) statt bei jedem Kanal -
gleiche Philosophie wie bei der KI-Generierung in ai.py.
"""

TEMPLATES = {
    "polizei": {
        "label": "🚔 Polizei / Behörden-RP",
        "plan": {
            "categories": [
                {"name": "📋 INFORMATIONEN", "channels": [
                    {"name": "📜-regeln", "type": "text", "topic": "Serverregeln, für alle verbindlich"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "dienstgrade", "type": "text"},
                ]},
                {"name": "🚔 EINSATZBEREICH", "channels": [
                    {"name": "einsatz-chat", "type": "text"},
                    {"name": "🎙️-funkverkehr", "type": "voice"},
                    {"name": "🚨-streife-1", "type": "voice"},
                    {"name": "🚨-streife-2", "type": "voice"},
                ]},
                {"name": "📝 VERWALTUNG", "channels": [
                    {"name": "berichte", "type": "text", "visible_to": ["Teamleitung", "Polizeipräsident"]},
                    {"name": "bewerbungen", "type": "text"},
                    {"name": "team-besprechung", "type": "voice", "visible_to": ["Teamleitung", "Polizeipräsident"]},
                ]},
            ],
            "roles": [
                {"name": "Polizeipräsident", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Stellv. Polizeipräsident", "color": "#e67e22", "hoist": True, "permissions": ["kick_members", "ban_members", "manage_roles", "manage_channels"]},
                {"name": "Teamleitung", "color": "#f1c40f", "hoist": True, "permissions": ["kick_members", "manage_messages", "moderate_members"]},
                {"name": "Beamter", "color": "#3498db", "hoist": False},
                {"name": "Anwärter", "color": "#95a5a6", "hoist": False},
                {"name": "Bürger", "color": "#7f8c8d", "hoist": False},
            ],
        },
    },
    "gaming": {
        "label": "🎮 Gaming-Community",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "rollen-vergabe", "type": "text"},
                ]},
                {"name": "💬 COMMUNITY", "channels": [
                    {"name": "allgemein", "type": "text"},
                    {"name": "🎬-clips-und-highlights", "type": "text"},
                    {"name": "memes", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "Lounge 1", "type": "voice"},
                    {"name": "Lounge 2", "type": "voice"},
                    {"name": "🎮-gaming-squad", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Admin", "color": "#e67e22", "hoist": True, "permissions": ["kick_members", "ban_members", "manage_roles", "manage_channels", "manage_messages"]},
                {"name": "Moderator", "color": "#f1c40f", "hoist": True, "permissions": ["kick_members", "manage_messages", "moderate_members", "mute_members"]},
                {"name": "Member", "color": "#3498db", "hoist": False},
            ],
        },
    },
    "support": {
        "label": "🛠️ Support-Server",
        "plan": {
            "categories": [
                {"name": "📋 INFO", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "faq", "type": "text"},
                ]},
                {"name": "🎫 SUPPORT", "channels": [
                    {"name": "🎫-ticket-erstellen", "type": "text"},
                    {"name": "support-chat", "type": "text"},
                ]},
                {"name": "🔧 TEAM", "channels": [
                    {"name": "team-chat", "type": "text", "visible_to": ["Support-Team", "Geschäftsführung"]},
                    {"name": "team-voice", "type": "voice", "visible_to": ["Support-Team", "Geschäftsführung"]},
                ]},
            ],
            "roles": [
                {"name": "Geschäftsführung", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Support-Team", "color": "#3498db", "hoist": True, "permissions": ["manage_messages", "moderate_members"]},
                {"name": "Kunde", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "wirtschaft": {
        "label": "💼 Wirtschafts-RP",
        "plan": {
            "categories": [
                {"name": "📋 INFORMATIONEN", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "📈-boersen-kurse", "type": "text"},
                ]},
                {"name": "🏢 UNTERNEHMEN", "channels": [
                    {"name": "firmen-chat", "type": "text"},
                    {"name": "verhandlungen", "type": "voice"},
                    {"name": "vorstandssitzung", "type": "voice", "visible_to": ["Vorstand", "CEO"]},
                ]},
                {"name": "📈 VERWALTUNG", "channels": [
                    {"name": "bewerbungen", "type": "text"},
                    {"name": "finanzamt", "type": "text", "visible_to": ["Abteilungsleitung", "Vorstand", "CEO"]},
                ]},
            ],
            "roles": [
                {"name": "CEO", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Vorstand", "color": "#e67e22", "hoist": True, "permissions": ["kick_members", "manage_roles", "manage_channels"]},
                {"name": "Abteilungsleitung", "color": "#f1c40f", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Mitarbeiter", "color": "#3498db", "hoist": False},
                {"name": "Bewerber", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "community": {
        "label": "🌐 Allgemeine Community",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "👋-vorstellung", "type": "text"},
                ]},
                {"name": "💬 CHAT", "channels": [
                    {"name": "allgemein", "type": "text"},
                    {"name": "off-topic", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "Chillen", "type": "voice"},
                    {"name": "Talk", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#3498db", "hoist": True, "permissions": ["kick_members", "manage_messages", "moderate_members"]},
                {"name": "Mitglied", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "anime": {
        "label": "🌸 Anime / Weeb-Community",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "👋-vorstellung", "type": "text"},
                ]},
                {"name": "🌸 ANIME & MANGA", "channels": [
                    {"name": "anime-talk", "type": "text", "topic": "Diskutiere aktuelle und Lieblings-Anime"},
                    {"name": "manga-ecke", "type": "text"},
                    {"name": "🎨-fanart", "type": "text", "topic": "Zeig deine Fanart und Zeichnungen"},
                    {"name": "empfehlungen", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "🍥-watch-party", "type": "voice"},
                    {"name": "Lounge", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#e67e22", "hoist": True},
                {"name": "Otaku-Elite", "color": "#f472b6", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Mitglied", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "kunst": {
        "label": "🎨 Kunst & Design",
        "plan": {
            "categories": [
                {"name": "📋 INFO", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                ]},
                {"name": "🎨 KREATIV-BEREICH", "channels": [
                    {"name": "🖼️-galerie", "type": "text", "topic": "Präsentiere deine fertigen Werke"},
                    {"name": "werke-in-arbeit", "type": "text", "topic": "Zeig Skizzen und Arbeitsschritte"},
                    {"name": "feedback-gesucht", "type": "text"},
                    {"name": "ressourcen-und-tutorials", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "🎧-co-working", "type": "voice", "topic": "Gemeinsam kreativ arbeiten"},
                    {"name": "Lounge", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#e67e22", "hoist": True},
                {"name": "Profi-Künstler", "color": "#9b6bff", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Künstler", "color": "#3498db", "hoist": False},
            ],
        },
    },
    "musik": {
        "label": "🎵 Musik-Community",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                ]},
                {"name": "🎵 MUSIK", "channels": [
                    {"name": "now-playing", "type": "text", "topic": "Teile, was du gerade hörst"},
                    {"name": "🎤-eigene-produktionen", "type": "text", "topic": "Zeig deine eigenen Tracks"},
                    {"name": "playlist-tausch", "type": "text"},
                    {"name": "konzerte-und-events", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "🎧-listening-room", "type": "voice", "topic": "Gemeinsam Musik hören"},
                    {"name": "jam-session", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#e67e22", "hoist": True},
                {"name": "Produzent", "color": "#9b6bff", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Mitglied", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "streamer": {
        "label": "🎥 Streamer / Content Creator",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "🔴-live-jetzt", "type": "text", "topic": "Automatische oder manuelle Live-Meldungen"},
                ]},
                {"name": "💬 COMMUNITY", "channels": [
                    {"name": "allgemein", "type": "text"},
                    {"name": "clip-highlights", "type": "text"},
                    {"name": "content-feedback", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "🎙️-stream-voice", "type": "voice", "topic": "Voice-Chat während des Streams"},
                    {"name": "Lounge", "type": "voice"},
                ]},
                {"name": "🔧 TEAM", "channels": [
                    {"name": "mod-chat", "type": "text", "visible_to": ["Moderator", "Streamer"]},
                ]},
            ],
            "roles": [
                {"name": "Streamer", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#e67e22", "hoist": True},
                {"name": "Sub/Supporter", "color": "#9b6bff", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Zuschauer", "color": "#95a5a6", "hoist": False},
            ],
        },
    },
    "tech": {
        "label": "💻 Tech / Programmierer-Community",
        "plan": {
            "categories": [
                {"name": "📋 START", "channels": [
                    {"name": "📜-regeln", "type": "text"},
                    {"name": "📢-ankuendigungen", "type": "text"},
                    {"name": "👋-vorstellung", "type": "text"},
                ]},
                {"name": "💻 ENTWICKLUNG", "channels": [
                    {"name": "code-hilfe", "type": "text", "topic": "Fragen zu Code, Bugs und Fehlern"},
                    {"name": "projekt-showcase", "type": "text", "topic": "Zeig, woran du gerade arbeitest"},
                    {"name": "job-boerse", "type": "text"},
                    {"name": "tech-news", "type": "text"},
                ]},
                {"name": "🔊 VOICE", "channels": [
                    {"name": "🎧-pair-programming", "type": "voice", "topic": "Gemeinsam an Code arbeiten"},
                    {"name": "Lounge", "type": "voice"},
                ]},
            ],
            "roles": [
                {"name": "Owner", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
                {"name": "Moderator", "color": "#e67e22", "hoist": True},
                {"name": "Senior Dev", "color": "#2dd4ee", "hoist": True, "permissions": ["manage_messages"]},
                {"name": "Entwickler", "color": "#3498db", "hoist": False},
            ],
        },
    },
}


def get_template_choices() -> list[tuple[str, str]]:
    """Gibt (key, label) Paare zurück, z.B. für Discord Select-Menüs."""
    return [(key, val["label"]) for key, val in TEMPLATES.items()]


def get_template_plan(key: str) -> dict | None:
    entry = TEMPLATES.get(key)
    return entry["plan"] if entry else None

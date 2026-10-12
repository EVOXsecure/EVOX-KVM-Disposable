"""Farbrollen, Themes und CSS der GUI (0.8.0, A4a). EINE Stelle für alle Farben; das CSS entsteht nur aus den Rollen.

- THEMES: Datenstruktur (leicht erweiterbar, A4b: Tron Legacy, Cyberpunk). "dark" bildet 0.7.5 exakt ab.
- SAFETY: feste Sicherheitsfarben (Gefahr-Rot, Stop and erase, SHUT DOWN & ERASE, Netzsperre INACTIVE, Fehler,
  Modusfarben, Ampel). Nie Teil eines Themes, nie überschreibbar (sanitize/validate lehnen ab, build_css setzt sie zuletzt).
- Benutzerwerte nur als strenges #RRGGBB (keine CSS-Einschleusung), Kontrast nach WCAG gerechnet.
Nur Darstellung; keine GTK-Abhängigkeit (testbar ohne Anzeige)."""
import json
import re

from . import texts as T

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
KEY = "appearance"                       # Schlüssel in ~/.config/evoxd/config.json
SCALE_MIN, SCALE_MAX, SCALE_STEP = 80, 150, 10
FONT_SCALES = tuple(range(SCALE_MIN, SCALE_MAX + 1, SCALE_STEP))   # Prozent, Raster 10 (0.8.1; vorher 90/100/120/140)
DEFAULT_SCALE = 100
DEFAULT_THEME = "dark"
WARN_RATIO = 3.0                         # darunter Warnung mit „Use anyway“
BAD_RATIO = 2.0                          # darunter stärkere Warnung (✖ hard to read), aber speicherbar (0.9.0: nie verweigern)
IMPORT_MAX_BYTES = 16384                 # Größenlimit einer Theme-Datei
EXPORT_FORMAT = "evoxd-theme"
FOCUS_COLLIDE_RATIO = 1.5                # Fokusfarbe gegen Knopffläche darunter: Warnung „schwer erkennbar“

# Feste Sicherheitsfarben: in jedem Theme gleich, nicht einstellbar (Werte = 0.7.5)
SAFETY = {
    "danger": "#d41f1f",          # Stop and erase, SHUT DOWN & ERASE, Bestätigen (Gefahr-Rot)
    "danger_border": "#ffd6d6",
    "danger_text": "#ffffff",
    "error": "#d41f1f",           # Fehlermeldungen (.evox-warn) und Netzsperre INACTIVE (.evox-lock-bad)
    "mode_internet": "#1FA855",   # Modusleiste/-rahmen im Startdialog, Speichern-Knopf
    "mode_offline": "#0060b3",
    "mode_border": "#d8f5e3",
    "mode_offline_border": "#cfe6ff",
    "mode_text": "#ffffff",
    "focus_inner": "#0A0A0F",     # dunkler Innenrand des Fokus (trennt auf jeder Fläche)
}
# Ampel/Signalfarben (Symbol + Wort immer dabei): fest, je nach heller/dunkler Grundfläche
SIGNAL_LIGHT = {"ok": "#1a7f37", "warn": "#9a6700", "bad": "#c01c28"}
SIGNAL_DARK = {"ok": "#57e389", "warn": "#e3b341", "bad": "#ff7b72"}

# Einstellbare Rollen (Reihenfolge = Anzeige). Klartext-Bezeichnungen stehen an EINER Stelle: texts.ROLE_NAMES.
_ROLE_ORDER = (
    "background", "text", "title", "heading", "vault", "vault_border", "vault_text", "template", "template_border",
    "template_text", "disposable", "disposable_border", "disposable_text", "offline", "offline_border",
    "offline_text", "step2", "step2_border", "step2_text", "make", "make_border", "make_text", "verify",
    "verify_border", "verify_text", "remove", "remove_border", "remove_text", "neutral", "neutral_border",
    "neutral_text", "aux", "aux_border", "aux_text", "exit", "exit_border", "exit_text", "back", "back_border",
    "back_text", "sel_amber", "sel_amber_text", "sel_amber_alt", "sel_teal", "sel_teal_text", "sel_teal_alt",
    "sel_green", "sel_green_text", "sel_green_alt", "backup_text", "focus", "grp_everyday", "grp_money", "grp_work", "grp_more",
    "grp_mylist", "hint_bg", "hint_text", "hint_mark_bg", "hint_mark_fg", "step4_internet_ring",
    "step4_internet_glow", "step4_offline_ring", "step4_offline_glow", "flash", "name", "vm_name", "cpu_bar",
)
ROLES = {k: T.ROLE_NAMES[k] for k in _ROLE_ORDER}
# Fläche -> Schrift (Kontrastprüfung); background gegen Schriftrollen, die direkt auf dem Fenstergrund stehen
PAIRS = (
    ("background", "text"), ("background", "title"), ("background", "heading"), ("background", "name"),
    ("background", "vm_name"), ("background", "grp_everyday"), ("background", "grp_money"),
    ("background", "grp_work"), ("background", "grp_more"), ("background", "grp_mylist"), ("background", "backup_text"),
    ("vault", "vault_text"), ("template", "template_text"), ("disposable", "disposable_text"),
    ("offline", "offline_text"), ("step2", "step2_text"), ("make", "make_text"), ("verify", "verify_text"),
    ("remove", "remove_text"), ("neutral", "neutral_text"), ("aux", "aux_text"), ("exit", "exit_text"),
    ("back", "back_text"), ("sel_amber", "sel_amber_text"), ("sel_amber", "sel_amber_alt"),
    ("sel_teal", "sel_teal_text"), ("sel_teal", "sel_teal_alt"), ("sel_green", "sel_green_text"),
    ("sel_green", "sel_green_alt"), ("hint_bg", "hint_text"), ("hint_mark_bg", "hint_mark_fg"),
)
NO_OVERRIDE = frozenset()                       # 0.9.0: für jede Rolle „Use anyway“ möglich (nur warnen)
BUTTON_FILLS = ("vault", "template", "disposable", "offline", "step2", "make", "verify", "remove", "neutral",
                "aux", "exit", "back")           # Flächen, auf denen der Fokusrahmen erkennbar bleiben muss

DARK = {
    "background": "#242424", "text": "#ffffff",   # nur Rechengrundlage: Dark nutzt die System-Grundfarben (0.7.5)
    "title": "#8c00ff", "heading": "#00A8B5",
    "vault": "#D4AF37", "vault_border": "#fff1c2", "vault_text": "#1a1400",
    "template": "#00F0FF", "template_border": "#c8fcff", "template_text": "#001a1c",
    "disposable": "#39D353", "disposable_border": "#c9f7d3", "disposable_text": "#04210c",
    "offline": "#0060b3", "offline_border": "#cfe6ff", "offline_text": "#ffffff",
    "step2": "#E0802A", "step2_border": "#ffd9b3", "step2_text": "#1f0f00",
    "make": "#E0802A", "make_border": "#ffd9b3", "make_text": "#1f0f00",
    "verify": "#4A6F94", "verify_border": "#dbe6f1", "verify_text": "#ffffff",
    "remove": "#9A4A4A", "remove_border": "#f0d9d9", "remove_text": "#ffffff",
    "neutral": "#4F6A86", "neutral_border": "#d6e0eb", "neutral_text": "#ffffff",
    "aux": "#6A6F94", "aux_border": "#dcdeee", "aux_text": "#ffffff",
    "exit": "#8B2A2A", "exit_border": "#f0d0d0", "exit_text": "#ffffff",
    "back": "#8B2A2A", "back_border": "#f0d0d0", "back_text": "#ffffff",
    "sel_amber": "#E0A030", "sel_amber_text": "#1a1000", "sel_amber_alt": "#8b0000",
    "sel_teal": "#00F0FF", "sel_teal_text": "#001a1c", "sel_teal_alt": "#8b0000",
    "sel_green": "#39D353", "sel_green_text": "#04210c", "sel_green_alt": "#5c0000",
    "backup_text": "#ff7b72",    # 0.8.2: -BACKUP-Zeile nicht markiert (= SIGNAL_DARK["bad"], vorher fest)
    "focus": "#C6FF00",
    "grp_everyday": "#4C8DFF", "grp_money": "#E0A030", "grp_work": "#2BB3A3", "grp_more": "#9AA4B2",
    "grp_mylist": "#E07AA8",
    "hint_bg": "#D4AF37", "hint_text": "#1a1400", "hint_mark_bg": "#1a1400", "hint_mark_fg": "#fff1c2",
    "step4_internet_ring": "#9BF5AE", "step4_internet_glow": "#39D353",
    "step4_offline_ring": "#4DA3FF", "step4_offline_glow": "#0060b3",
    "flash": "#ffd400", "name": "#39D353", "vm_name": "#39D353", "cpu_bar": "#4C8DFF",
}
# Light: Neongrün/Türkis/Limette abgedunkelt (helle Fläche), Schrift auf den Knöpfen neu gewählt (Werte im Bericht §72)
LIGHT = dict(DARK)
LIGHT.update({
    "background": "#f6f5f4", "text": "#1a1a1a", "title": "#7400d6", "heading": "#00727C",
    "vault": "#D4AF37", "vault_border": "#7a6000", "vault_text": "#1a1400",
    "template": "#00808F", "template_border": "#004d56", "template_text": "#ffffff",
    "disposable": "#1A8536", "disposable_border": "#0c4a1c", "disposable_text": "#ffffff",
    "offline": "#0060b3", "offline_border": "#003a6e",
    "step2_border": "#8a4a10", "make_border": "#8a4a10",
    "verify_border": "#2c4560", "remove_border": "#5e2a2a", "neutral_border": "#2f4257",
    "aux_border": "#3f4260", "exit_border": "#4f1414", "back_border": "#4f1414",
    "sel_amber": "#E0A030", "sel_amber_text": "#1a1000", "sel_amber_alt": "#6b0000",
    "sel_teal": "#00808F", "sel_teal_text": "#ffffff", "sel_teal_alt": "#ffe0e0",
    "sel_green": "#1A8536", "sel_green_text": "#ffffff", "sel_green_alt": "#ffe0e0",
    "backup_text": "#c01c28",    # = SIGNAL_LIGHT["bad"]
    "focus": "#000000",          # Schwarz: auf allen Light-Knopfflächen ≥ 2,4:1, auf dem Grund 19:1
    "grp_everyday": "#1F5FD0", "grp_money": "#9A6200", "grp_work": "#00756A", "grp_more": "#58606C",
    "grp_mylist": "#B0306E",
    "hint_bg": "#D4AF37", "hint_text": "#1a1400", "hint_mark_bg": "#1a1400", "hint_mark_fg": "#fff1c2",
    "step4_internet_ring": "#0c4a1c", "step4_internet_glow": "#1A8536",
    "step4_offline_ring": "#003a6e", "step4_offline_glow": "#0060b3",
    "flash": "#E07000", "name": "#1A7A32", "vm_name": "#1A7A32", "cpu_bar": "#1F5FD0",
})
TRON = dict(DARK)
TRON.update({     # Tiefes Schwarzblau, Neonlinien (helle Ränder), Cyan/Orange
    "background": "#050B1A", "text": "#D8F6FF", "title": "#00E5FF", "heading": "#FF9A1F",
    "vault": "#FF9A1F", "vault_border": "#FFE0B0", "vault_text": "#140A00",
    "template": "#00E5FF", "template_border": "#B8FAFF", "template_text": "#001418",
    "disposable": "#00E5FF", "disposable_border": "#E6FEFF", "disposable_text": "#001418",
    "offline": "#0A3C7A", "offline_border": "#5CF0FF", "offline_text": "#FFFFFF",
    "step2": "#FF9A1F", "step2_border": "#FFE0B0", "step2_text": "#140A00",
    "make": "#FF9A1F", "make_border": "#FFE0B0", "make_text": "#140A00",
    "verify": "#0E4F8F", "verify_border": "#5CF0FF", "verify_text": "#FFFFFF",
    "remove": "#8A3A1A", "remove_border": "#FFB27A", "remove_text": "#FFFFFF",
    "neutral": "#16345C", "neutral_border": "#5CF0FF", "neutral_text": "#FFFFFF",
    "aux": "#1D3F73", "aux_border": "#7FD8FF", "aux_text": "#FFFFFF",
    "exit": "#8B2A2A", "exit_border": "#FF9A9A", "exit_text": "#FFFFFF",
    "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#FF9A1F", "sel_amber_text": "#140A00", "sel_amber_alt": "#7A0000",
    "sel_teal": "#00E5FF", "sel_teal_text": "#001418", "sel_teal_alt": "#7A0000",
    "sel_green": "#2BE0A0", "sel_green_text": "#00160E", "sel_green_alt": "#5C0000",
    "backup_text": "#FF7B72", "focus": "#FFFFFF",
    "grp_everyday": "#4DB2FF", "grp_money": "#FF9A1F", "grp_work": "#00E5FF", "grp_more": "#9FB4CC",
    "grp_mylist": "#FF6EC7",
    "hint_bg": "#FF9A1F", "hint_text": "#140A00", "hint_mark_bg": "#140A00", "hint_mark_fg": "#FFE0B0",
    "step4_internet_ring": "#B8FAFF", "step4_internet_glow": "#00E5FF",
    "step4_offline_ring": "#5CA8FF", "step4_offline_glow": "#1060C0",
    "flash": "#FFEA00", "name": "#00E5FF", "vm_name": "#00E5FF", "cpu_bar": "#00B8D4",
})
CYBER = dict(DARK)
CYBER.update({    # Magenta, Gelb, Cyan auf Nachtviolett
    "background": "#0F0716", "text": "#F4EAFF", "title": "#FF2BD6", "heading": "#FCEE0A",
    "vault": "#FCEE0A", "vault_border": "#FFFBB0", "vault_text": "#141200",
    "template": "#00F0FF", "template_border": "#C8FCFF", "template_text": "#001418",
    "disposable": "#FF2BD6", "disposable_border": "#FFC2F2", "disposable_text": "#14000F",
    "offline": "#5A1FA8", "offline_border": "#00F0FF", "offline_text": "#FFFFFF",
    "step2": "#FCEE0A", "step2_border": "#FFFBB0", "step2_text": "#141200",
    "make": "#FCEE0A", "make_border": "#FFFBB0", "make_text": "#141200",
    "verify": "#3B2A8F", "verify_border": "#00F0FF", "verify_text": "#FFFFFF",
    "remove": "#8A2A4A", "remove_border": "#FF9AC0", "remove_text": "#FFFFFF",
    "neutral": "#3A2560", "neutral_border": "#FF2BD6", "neutral_text": "#FFFFFF",
    "aux": "#4A2A7A", "aux_border": "#00F0FF", "aux_text": "#FFFFFF",
    "exit": "#8B2A2A", "exit_border": "#FF9A9A", "exit_text": "#FFFFFF",
    "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#FCEE0A", "sel_amber_text": "#141200", "sel_amber_alt": "#7A0000",
    "sel_teal": "#00F0FF", "sel_teal_text": "#001418", "sel_teal_alt": "#7A0000",
    "sel_green": "#FF2BD6", "sel_green_text": "#14000F", "sel_green_alt": "#4A0030",
    "backup_text": "#FF7B72", "focus": "#3D5AFE",
    "grp_everyday": "#00F0FF", "grp_money": "#FCEE0A", "grp_work": "#FF2BD6", "grp_more": "#B7A6D6",
    "grp_mylist": "#FF8A3D",
    "hint_bg": "#FCEE0A", "hint_text": "#141200", "hint_mark_bg": "#141200", "hint_mark_fg": "#FFFBB0",
    "step4_internet_ring": "#FFC2F2", "step4_internet_glow": "#FF2BD6",
    "step4_offline_ring": "#00F0FF", "step4_offline_glow": "#5A1FA8",
    "flash": "#FCEE0A", "name": "#FF2BD6", "vm_name": "#FF2BD6", "cpu_bar": "#00F0FF",
})
# 0.9.2 (A4c): sieben weitere Vorauswahl-Themes (Kontraste im Test; Sicherheitsfarben kommen immer aus SAFETY)
HICON = dict(DARK)
HICON.update({     # Schwarz/Weiß/Gelb, alle Textpaare ≥ 7:1
    "background": "#000000", "text": "#FFFFFF", "title": "#FFFF00", "heading": "#00FFFF", "name": "#00FF00",
    "vm_name": "#00FF00", "vault": "#FFFF00", "vault_border": "#FFFFFF", "vault_text": "#000000",
    "template": "#00FFFF", "template_border": "#FFFFFF", "template_text": "#000000", "disposable": "#00FF00",
    "disposable_border": "#FFFFFF", "disposable_text": "#000000", "offline": "#0000FF", "offline_border": "#FFFFFF",
    "offline_text": "#FFFFFF", "step2": "#FFAA00", "step2_border": "#FFFFFF", "step2_text": "#000000",
    "make": "#FFAA00", "make_border": "#FFFFFF", "make_text": "#000000", "verify": "#0033CC",
    "verify_border": "#FFFFFF", "verify_text": "#FFFFFF", "remove": "#990000", "remove_border": "#FFFFFF",
    "remove_text": "#FFFFFF", "neutral": "#202020", "neutral_border": "#FFFFFF", "neutral_text": "#FFFFFF",
    "aux": "#3A3A3A", "aux_border": "#FFFFFF", "aux_text": "#FFFFFF", "exit": "#8B0000", "exit_border": "#FFFFFF",
    "exit_text": "#FFFFFF", "back": "#8B0000", "back_border": "#FFFFFF", "back_text": "#FFFFFF",
    "sel_amber": "#FFFF00", "sel_amber_text": "#000000", "sel_amber_alt": "#500000", "sel_teal": "#00FFFF",
    "sel_teal_text": "#000000", "sel_teal_alt": "#500000", "sel_green": "#00FF00", "sel_green_text": "#000000",
    "sel_green_alt": "#500000", "backup_text": "#FF8080", "focus": "#FF00FF", "grp_everyday": "#00FFFF",
    "grp_money": "#FFFF00", "grp_work": "#00FF00", "grp_more": "#FFFFFF", "grp_mylist": "#FF80FF",
    "hint_bg": "#FFFF00", "hint_text": "#000000", "hint_mark_bg": "#000000", "hint_mark_fg": "#FFFF00",
    "step4_internet_ring": "#FFFFFF", "step4_internet_glow": "#FFFF00", "step4_offline_ring": "#00FFFF",
    "step4_offline_glow": "#0000FF", "flash": "#FFFF00", "cpu_bar": "#00FFFF",
})
NORD = dict(DARK)
NORD.update({     # kühles Grau-Blau
    "background": "#2E3440", "text": "#ECEFF4", "title": "#88C0D0", "heading": "#81A1C1", "name": "#A3BE8C",
    "vm_name": "#A3BE8C", "vault": "#EBCB8B", "vault_border": "#F5E3B8", "vault_text": "#2E3440",
    "template": "#88C0D0", "template_border": "#D8EEF3", "template_text": "#2E3440", "disposable": "#A3BE8C",
    "disposable_border": "#DDEBD2", "disposable_text": "#2E3440", "offline": "#3B5F8A", "offline_border": "#D8DEE9",
    "offline_text": "#FFFFFF", "step2": "#D08770", "step2_border": "#F0CFC4", "step2_text": "#1F0F0A",
    "make": "#D08770", "make_border": "#F0CFC4", "make_text": "#1F0F0A", "verify": "#4C6A8F",
    "verify_border": "#D8DEE9", "verify_text": "#FFFFFF", "remove": "#8F4A52", "remove_border": "#EBCBCF",
    "remove_text": "#FFFFFF", "neutral": "#434C5E", "neutral_border": "#88C0D0", "neutral_text": "#ECEFF4",
    "aux": "#56608A", "aux_border": "#D8DEE9", "aux_text": "#FFFFFF", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#EBCB8B", "sel_amber_text": "#2E3440", "sel_amber_alt": "#6B0000", "sel_teal": "#88C0D0",
    "sel_teal_text": "#2E3440", "sel_teal_alt": "#6B0000", "sel_green": "#A3BE8C", "sel_green_text": "#2E3440",
    "sel_green_alt": "#6B0000", "backup_text": "#FF8A80", "focus": "#FFFFFF", "grp_everyday": "#88C0D0",
    "grp_money": "#EBCB8B", "grp_work": "#A3BE8C", "grp_more": "#B8C0CE", "grp_mylist": "#C09ABA",
    "hint_bg": "#EBCB8B", "hint_text": "#2E3440", "hint_mark_bg": "#2E3440", "hint_mark_fg": "#EBCB8B",
    "step4_internet_ring": "#DDEBD2", "step4_internet_glow": "#A3BE8C", "step4_offline_ring": "#88C0D0",
    "step4_offline_glow": "#5E81AC", "flash": "#EBCB8B", "cpu_bar": "#81A1C1",
})
SOLAR = dict(DARK)
SOLAR.update({     # Petrol, Orange
    "background": "#002B36", "text": "#A8B5B5", "title": "#2AA198", "heading": "#D4A017", "name": "#859900",
    "vm_name": "#859900", "vault": "#B58900", "vault_border": "#EEDDA0", "vault_text": "#001A21",
    "template": "#2AA198", "template_border": "#BDEBE6", "template_text": "#001A21", "disposable": "#859900",
    "disposable_border": "#D5E08A", "disposable_text": "#001A21", "offline": "#1F5F8B", "offline_border": "#BFE0F5",
    "offline_text": "#FFFFFF", "step2": "#E86A33", "step2_border": "#FFD0B8", "step2_text": "#1A0A00",
    "make": "#E86A33", "make_border": "#FFD0B8", "make_text": "#1A0A00", "verify": "#1F5F8B",
    "verify_border": "#BFE0F5", "verify_text": "#FFFFFF", "remove": "#A02A2A", "remove_border": "#F0C0C0",
    "remove_text": "#FFFFFF", "neutral": "#073642", "neutral_border": "#2AA198", "neutral_text": "#EEE8D5",
    "aux": "#0E4A5C", "aux_border": "#93A1A1", "aux_text": "#EEE8D5", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#B58900", "sel_amber_text": "#001A21", "sel_amber_alt": "#3A0000", "sel_teal": "#2AA198",
    "sel_teal_text": "#001A21", "sel_teal_alt": "#3A0000", "sel_green": "#859900", "sel_green_text": "#001A21",
    "sel_green_alt": "#3A0000", "backup_text": "#FF8A80", "focus": "#FFFFFF", "grp_everyday": "#4BA3E8",
    "grp_money": "#B58900", "grp_work": "#859900", "grp_more": "#93A1A1", "grp_mylist": "#E85FA8",
    "hint_bg": "#B58900", "hint_text": "#001A21", "hint_mark_bg": "#001A21", "hint_mark_fg": "#EEDDA0",
    "step4_internet_ring": "#D5E08A", "step4_internet_glow": "#859900", "step4_offline_ring": "#BFE0F5",
    "step4_offline_glow": "#268BD2", "flash": "#E8B800", "cpu_bar": "#268BD2",
})
DRACULA = dict(DARK)
DRACULA.update({     # Dunkelviolett, Pink, Grün
    "background": "#282A36", "text": "#F8F8F2", "title": "#BD93F9", "heading": "#FF79C6", "name": "#50FA7B",
    "vm_name": "#50FA7B", "vault": "#F1FA8C", "vault_border": "#FBFFC8", "vault_text": "#282A36",
    "template": "#8BE9FD", "template_border": "#D5F6FF", "template_text": "#282A36", "disposable": "#50FA7B",
    "disposable_border": "#C4FDD2", "disposable_text": "#282A36", "offline": "#3E4A8A", "offline_border": "#BD93F9",
    "offline_text": "#FFFFFF", "step2": "#FFCF80", "step2_border": "#FFE3C2", "step2_text": "#282A36",
    "make": "#FFCF80", "make_border": "#FFE3C2", "make_text": "#282A36", "verify": "#54609A",
    "verify_border": "#BD93F9", "verify_text": "#FFFFFF", "remove": "#A03A5A", "remove_border": "#FFB8D0",
    "remove_text": "#FFFFFF", "neutral": "#44475A", "neutral_border": "#BD93F9", "neutral_text": "#F8F8F2",
    "aux": "#5A4A8A", "aux_border": "#BD93F9", "aux_text": "#FFFFFF", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#FFCF80", "sel_amber_text": "#282A36", "sel_amber_alt": "#6B0000", "sel_teal": "#8BE9FD",
    "sel_teal_text": "#282A36", "sel_teal_alt": "#6B0000", "sel_green": "#50FA7B", "sel_green_text": "#282A36",
    "sel_green_alt": "#6B0000", "backup_text": "#FF8A80", "focus": "#FF79C6", "grp_everyday": "#8BE9FD",
    "grp_money": "#F1FA8C", "grp_work": "#50FA7B", "grp_more": "#B8BCD0", "grp_mylist": "#FF79C6",
    "hint_bg": "#F1FA8C", "hint_text": "#282A36", "hint_mark_bg": "#282A36", "hint_mark_fg": "#F1FA8C",
    "step4_internet_ring": "#C4FDD2", "step4_internet_glow": "#50FA7B", "step4_offline_ring": "#BD93F9",
    "step4_offline_glow": "#3E4A8A", "flash": "#F1FA8C", "cpu_bar": "#8BE9FD",
})
SYNTH = dict(DARK)
SYNTH.update({     # Dunkelviolett, Pink, Cyan
    "background": "#1A0B2E", "text": "#F5E9FF", "title": "#FF4FD8", "heading": "#00E5FF", "name": "#00E5FF",
    "vm_name": "#00E5FF", "vault": "#FF71CE", "vault_border": "#FFD0EE", "vault_text": "#1A0020",
    "template": "#00B8D4", "template_border": "#C8FCFF", "template_text": "#001418", "disposable": "#B967FF",
    "disposable_border": "#E6CCFF", "disposable_text": "#14002A", "offline": "#3A1C8C", "offline_border": "#00E5FF",
    "offline_text": "#FFFFFF", "step2": "#FF9E3D", "step2_border": "#FFD9B0", "step2_text": "#1A0C00",
    "make": "#FF9E3D", "make_border": "#FFD9B0", "make_text": "#1A0C00", "verify": "#3B2A8F",
    "verify_border": "#00E5FF", "verify_text": "#FFFFFF", "remove": "#8A2A5A", "remove_border": "#FF9AC0",
    "remove_text": "#FFFFFF", "neutral": "#2E2A66", "neutral_border": "#FF71CE", "neutral_text": "#FFFFFF",
    "aux": "#4A2A7A", "aux_border": "#00E5FF", "aux_text": "#FFFFFF", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#FFB86B", "sel_amber_text": "#1A0C00", "sel_amber_alt": "#6B0000", "sel_teal": "#00E5FF",
    "sel_teal_text": "#001418", "sel_teal_alt": "#6B0000", "sel_green": "#2BB673", "sel_green_text": "#00160E",
    "sel_green_alt": "#3A0000", "backup_text": "#FF8A80", "focus": "#FFFFFF", "grp_everyday": "#00E5FF",
    "grp_money": "#FF9E3D", "grp_work": "#5CF0A0", "grp_more": "#C8B6E6", "grp_mylist": "#FF71CE",
    "hint_bg": "#FF9E3D", "hint_text": "#1A0C00", "hint_mark_bg": "#1A0C00", "hint_mark_fg": "#FFD9B0",
    "step4_internet_ring": "#E6CCFF", "step4_internet_glow": "#B967FF", "step4_offline_ring": "#00E5FF",
    "step4_offline_glow": "#3A1C8C", "flash": "#FFE14D", "cpu_bar": "#00E5FF",
})
MATRIX = dict(DARK)
MATRIX.update({     # Schwarz, Grüntöne
    "background": "#000A00", "text": "#B6FFB6", "title": "#00FF41", "heading": "#39FF14", "name": "#00FF41",
    "vm_name": "#00FF41", "vault": "#8CFF8C", "vault_border": "#E0FFE0", "vault_text": "#001400",
    "template": "#00FF41", "template_border": "#C8FFD6", "template_text": "#001400", "disposable": "#007F20",
    "disposable_border": "#B0FFC4", "disposable_text": "#F0FFF0", "offline": "#004D1A", "offline_border": "#00FF41",
    "offline_text": "#D8FFD8", "step2": "#D2FF4D", "step2_border": "#F0FFB0", "step2_text": "#101400",
    "make": "#D2FF4D", "make_border": "#F0FFB0", "make_text": "#101400", "verify": "#0B5D2A",
    "verify_border": "#7CFF9B", "verify_text": "#F0FFF0", "remove": "#6B2A1A", "remove_border": "#FF9A7A",
    "remove_text": "#FFFFFF", "neutral": "#0F3D1F", "neutral_border": "#00FF41", "neutral_text": "#D8FFD8",
    "aux": "#1B4D2B", "aux_border": "#7CFF9B", "aux_text": "#F0FFF0", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#D2FF4D", "sel_amber_text": "#101400", "sel_amber_alt": "#4A0000", "sel_teal": "#00FF41",
    "sel_teal_text": "#001400", "sel_teal_alt": "#4A0000", "sel_green": "#007F20", "sel_green_text": "#F0FFF0",
    "sel_green_alt": "#FFFFFF", "backup_text": "#FF7B72", "focus": "#FF40FF", "grp_everyday": "#00FF41",
    "grp_money": "#D2FF4D", "grp_work": "#39D353", "grp_more": "#8FB88F", "grp_mylist": "#B6FF8C",
    "hint_bg": "#00C030", "hint_text": "#000F00", "hint_mark_bg": "#000F00", "hint_mark_fg": "#B0FFC4",
    "step4_internet_ring": "#C8FFD6", "step4_internet_glow": "#00FF41", "step4_offline_ring": "#7CFF9B",
    "step4_offline_glow": "#004D1A", "flash": "#E6FF00", "cpu_bar": "#00C030",
})
AMBER = dict(DARK)
AMBER.update({     # Schwarz, Bernstein
    "background": "#0A0600", "text": "#FFB000", "title": "#FFC940", "heading": "#FF9100", "name": "#FFB000",
    "vm_name": "#FFB000", "vault": "#FFB000", "vault_border": "#FFE0A0", "vault_text": "#140A00",
    "template": "#FFC040", "template_border": "#FFF0C8", "template_text": "#140A00", "disposable": "#D98E00",
    "disposable_border": "#FFD98A", "disposable_text": "#140A00", "offline": "#5C3A00", "offline_border": "#FFB000",
    "offline_text": "#FFD98A", "step2": "#FF8A1F", "step2_border": "#FFD0A0", "step2_text": "#140A00",
    "make": "#FF8A1F", "make_border": "#FFD0A0", "make_text": "#140A00", "verify": "#7A4A00",
    "verify_border": "#FFC940", "verify_text": "#FFE8B8", "remove": "#7A2A10", "remove_border": "#FF9A6A",
    "remove_text": "#FFE0D0", "neutral": "#3D2800", "neutral_border": "#FFB000", "neutral_text": "#FFD98A",
    "aux": "#5A3A10", "aux_border": "#FFC940", "aux_text": "#FFE8B8", "exit": "#8B2A2A", "exit_border": "#FF9A9A",
    "exit_text": "#FFFFFF", "back": "#8B2A2A", "back_border": "#FF9A9A", "back_text": "#FFFFFF",
    "sel_amber": "#FFB000", "sel_amber_text": "#140A00", "sel_amber_alt": "#5C0000", "sel_teal": "#FFC040",
    "sel_teal_text": "#140A00", "sel_teal_alt": "#5C0000", "sel_green": "#D98E00", "sel_green_text": "#140A00",
    "sel_green_alt": "#4A0000", "backup_text": "#FF7B72", "focus": "#FFFFFF", "grp_everyday": "#FFB000",
    "grp_money": "#FFD060", "grp_work": "#FF8A1F", "grp_more": "#C98A2E", "grp_mylist": "#E0A878",
    "hint_bg": "#FFB000", "hint_text": "#140A00", "hint_mark_bg": "#140A00", "hint_mark_fg": "#FFE0A0",
    "step4_internet_ring": "#FFE0A0", "step4_internet_glow": "#FFB000", "step4_offline_ring": "#FFC940",
    "step4_offline_glow": "#5C3A00", "flash": "#FFD060", "cpu_bar": "#FF9100",
})
# base: "system" = Grundfarben des GTK-Themes (wie 0.7.5, kein Grund-CSS); "light"/"dark" = festes GTK-Theme im Prozess + Grund-CSS
THEMES = {
    "dark": {"label": "Dark (default)", "base": "system", "roles": DARK},
    "light": {"label": "Light", "base": "light", "roles": LIGHT},
    "hicontrast": {"label": "High Contrast", "base": "dark", "roles": HICON},
    "nord": {"label": "Nord", "base": "dark", "roles": NORD},
    "solarized": {"label": "Solarized Dark", "base": "dark", "roles": SOLAR},
    "dracula": {"label": "Dracula", "base": "dark", "roles": DRACULA},
    "tron": {"label": "Tron Legacy", "base": "dark", "roles": TRON},
    "cyberpunk": {"label": "Cyberpunk", "base": "dark", "roles": CYBER},
    "synthwave": {"label": "Synthwave", "base": "dark", "roles": SYNTH},
    "matrix": {"label": "Matrix", "base": "dark", "roles": MATRIX},
    "amber": {"label": "Amber Terminal", "base": "dark", "roles": AMBER},
}


def valid_hex(v) -> bool:
    return isinstance(v, str) and HEX_RE.fullmatch(v) is not None


def norm_hex(v) -> str:
    """Strenges #RRGGBB (Groß/Klein egal) -> Großbuchstaben; sonst ValueError (nie CSS-Text durchlassen)."""
    if not valid_hex(v):
        raise ValueError(f"not a #RRGGBB color: {v!r}")
    return "#" + v[1:].upper()


def lum(c: str) -> float:
    def ch(x):
        x = int(x, 16) / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[1:3]) + 0.7152 * ch(c[3:5]) + 0.0722 * ch(c[5:7])


def contrast(a: str, b: str) -> float:
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def theme_key(k) -> str:
    return k if k in THEMES else DEFAULT_THEME


def scale_of(v) -> int:
    """Schriftgröße in Prozent: ganze Zahl 80..150, auf das 10er-Raster gerundet (alte Werte 90/100/120/140 bleiben);
    alles andere (außerhalb, Text, Bool, None) -> Standard 100."""
    if isinstance(v, bool) or not isinstance(v, int) or not SCALE_MIN <= v <= SCALE_MAX:
        return DEFAULT_SCALE
    return min(SCALE_MAX, (v + SCALE_STEP // 2) // SCALE_STEP * SCALE_STEP)


def effective(theme="dark", overrides=None) -> dict:
    """Rollen des Themes + gültige Benutzerwerte; Sicherheitsfarben immer obenauf (nie überschreibbar)."""
    r = dict(THEMES[theme_key(theme)]["roles"])
    for k, v in (overrides or {}).items():
        if k in ROLES and valid_hex(v):
            r[k] = v
    r.update(SAFETY)
    return r


def check_pair(theme, roles, a, b):
    """(Verhältnis, Stufe) eines Paares: "ok", "warn" (< 3:1) oder "bad" (< 2:1, stärkere Warnung). Beides speicherbar.
    Grenzen gelten relativ zum Theme: ein Paar, das schon im Theme darunter liegt (z. B. Titel-Glühen), gilt erst als
    schlechter, wenn es sinkt."""
    base = THEMES[theme_key(theme)]["roles"]
    ratio = contrast(roles[a], roles[b])
    ref = contrast(base[a], base[b])
    if ratio < min(BAD_RATIO, ref) - 1e-9:
        return ratio, "bad"
    if ratio < min(WARN_RATIO, ref) - 1e-9:
        return ratio, "warn"
    return ratio, "ok"


def check_role(theme, overrides, role, value):
    """Prüfung eines neuen Werts für eine Rolle. Ergebnis dict: level ok/warn/bad/reject, worst (Verhältnis, Paar),
    can_override (Use anyway: bei warn und bad), focus_clash [(Rolle, Verhältnis)].
    "reject" gibt es nur für Sicherheitsrollen, unbekannte Rollen und ungültige Werte – nie wegen Kontrast."""
    out = {"level": "ok", "worst": None, "can_override": False, "focus_clash": []}
    if role not in ROLES or role in SAFETY or not valid_hex(value):
        out["level"] = "reject"
        return out
    ov = dict(overrides or {})
    ov[role] = norm_hex(value)
    r = effective(theme, ov)
    order = {"ok": 0, "warn": 1, "bad": 2}
    for a, b in PAIRS:
        if role not in (a, b):
            continue
        ratio, lvl = check_pair(theme, r, a, b)
        if out["worst"] is None or ratio < out["worst"][0]:
            out["worst"] = (ratio, a, b)
        if order[lvl] > order[out["level"]]:
            out["level"] = lvl
    out["can_override"] = out["level"] in ("warn", "bad") and role not in NO_OVERRIDE
    if role == "focus" or role in BUTTON_FILLS:
        out["focus_clash"] = focus_clash(r)
    return out


def focus_clash(roles) -> list:
    """Knopfflächen, auf denen die Fokusfarbe kaum erkennbar ist (Warnung; der dunkle Innenrand trennt weiter)."""
    return [(k, contrast(roles["focus"], roles[k])) for k in BUTTON_FILLS
            if contrast(roles["focus"], roles[k]) < FOCUS_COLLIDE_RATIO]


def sanitize(data) -> dict:
    """Gespeicherte Einstellung (config.json) streng lesen: {"theme", "roles", "accepted", "font_scale"}.
    Unbekannte Themes/Rollen, Sicherheitsrollen, ungültige Werte und Werte unter 3:1 ohne gespeichertes
    „Use anyway“ werden verworfen. Alte/fehlende Daten -> Standard."""
    d = data if isinstance(data, dict) else {}
    theme = theme_key(d.get("theme"))
    raw = d.get("roles") if isinstance(d.get("roles"), dict) else {}
    acc = d.get("accepted") if isinstance(d.get("accepted"), list) else []
    acc = {a for a in acc if isinstance(a, str) and a in ROLES and a not in NO_OVERRIDE}
    roles = {}
    for k, v in raw.items():
        if isinstance(k, str) and k in ROLES and k not in SAFETY and valid_hex(v):
            roles[k] = norm_hex(v)
    # Kontrast: jede Rolle mit allen anderen gültigen Werten prüfen; schlechte Werte fallen weg (Theme-Wert gilt)
    for k in list(roles):
        res = check_role(theme, {x: y for x, y in roles.items() if x != k}, k, roles[k])
        if res["level"] == "reject" or (res["level"] in ("warn", "bad") and k not in acc):
            del roles[k]
    return {"theme": theme, "roles": roles, "accepted": sorted(a for a in acc if a in roles),
            "font_scale": scale_of(d.get("font_scale"))}


def export_theme(appearance) -> str:
    """Eigenes Theme als JSON-Text (Basis-Theme + nur geänderte Rollen, nie Sicherheitsrollen)."""
    a = sanitize(appearance)
    return json.dumps({"format": EXPORT_FORMAT, "version": 1, "base": a["theme"], "roles": a["roles"],
                       "accepted": a["accepted"]}, indent=2, sort_keys=True) + "\n"


def import_theme(text):
    """Theme-Datei streng prüfen. Liefert {"theme", "roles", "accepted"} oder wirft ValueError. Nur bekannte Rollen,
    nur #RRGGBB, keine Sicherheitsrollen, keine Zusatzfelder; Größenlimit. Es wird nie Text als CSS übernommen."""
    if isinstance(text, bytes):
        if len(text) > IMPORT_MAX_BYTES:
            raise ValueError("file too large")
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("not UTF-8 text")
    if not isinstance(text, str) or len(text.encode("utf-8")) > IMPORT_MAX_BYTES:
        raise ValueError("file too large")
    try:
        d = json.loads(text)
    except (ValueError, RecursionError):
        raise ValueError("not valid JSON")
    if not isinstance(d, dict) or d.get("format") != EXPORT_FORMAT or d.get("version") != 1:
        raise ValueError("not an EVOX theme file")
    if set(d) - {"format", "version", "base", "roles", "accepted"}:
        raise ValueError("unknown field")
    if d.get("base") not in THEMES:
        raise ValueError("unknown base theme")
    roles, acc = d.get("roles"), d.get("accepted", [])
    if not isinstance(roles, dict) or not isinstance(acc, list) or len(roles) > len(ROLES):
        raise ValueError("bad roles")
    out = {}
    for k, v in roles.items():
        if k in SAFETY:
            raise ValueError("safety colors cannot be set")
        if k not in ROLES:
            raise ValueError(f"unknown role: {str(k)[:30]}")
        if not valid_hex(v):
            raise ValueError(f"not a #RRGGBB color for {k}")
        out[k] = norm_hex(v)
    if any(not isinstance(a, str) or a not in out for a in acc):
        raise ValueError("bad accepted list")
    # Kontrast nur warnen: schlechte Werte gelten als „Use anyway“ (die Datei wurde bewusst geladen)
    return {"theme": d["base"], "roles": out, "accepted": sorted(set(acc) | {
        k for k in out if check_role(d["base"], {x: y for x, y in out.items() if x != k}, k, out[k])["level"]
        in ("warn", "bad")})}


def default_appearance() -> dict:
    return {"theme": DEFAULT_THEME, "roles": {}, "accepted": [], "font_scale": DEFAULT_SCALE}


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _scale_pt(css: str, scale: int) -> str:
    """Alle Schriftgrößen (…pt) skalieren; bei 100 % unverändert (gleiches CSS wie 0.7.5)."""
    if scale == DEFAULT_SCALE:
        return css

    def rep(m):
        v = round(int(m.group(1)) * scale / 100, 1)
        return f"{v:g}pt"
    return re.sub(r"(?<![0-9.])(\d+)pt\b", rep, css)


# Layout-Maße, die im CSS stehen (aus gui.py übernommen; keine Farben)
HOWTO_BTN_HEIGHT = 36
HOWTO_BTN_HEIGHT_SMALL = 30
HOWTO_PAD_V = 4
HOWTO_COMPACT_SCALE = 130   # ab dieser Schriftgröße (%) kompakte Knöpfe mit weniger Innenabstand (Fenster passt in die Arbeitsfläche)
HOWTO_PAD_COMPACT = 1
FOCUS_OUTER_PX = 4
FOCUS_INNER_PX = 2
FOCUS_GLOW_PX = 8
FOCUS_GLOW_ALPHA = 0.65
STEP4_GLOW_PX = 10
GROUP_KEYS = ("everyday", "money", "work", "more", "mylist")
FN_KEYS = ("make", "verify", "remove", "exit", "neutral", "aux")
TAB_KEYS = ("vault", "template", "disposable")
SELECT_KEYS = {"amber": "sel_amber", "teal": "sel_teal", "green": "sel_green"}
_FOCUS_SEL = ("button:focus, radiobutton:focus, checkbutton:focus, .evox-tabbtn:focus, .evox-chip:focus, "
              ".evox-howto:focus, entry:focus, spinbutton:focus, combobox:focus, "
              "list row:focus, expander:focus")


def group_css(r) -> str:
    """Gruppenfarbe: Überschrift und Chips tragen dieselbe Farbe (Text mit dem Theme-Vordergrund gemischt)."""
    out = []
    for k in GROUP_KEYS:
        c = r[f"grp_{k}"]
        rr, g_, b = _rgb(c)
        txt = f"mix({c}, @theme_fg_color, 0.3)"
        out.append(f".evox-grp-{k} {{ color: {txt}; border-bottom: 2px solid {c}; }}")
        out.append(f".evox-chip-{k} {{ color: {txt}; border: 1px solid {c}; background-color: rgba({rr}, {g_}, {b}, 0.16); }}")
        out.append(f".evox-chip-{k}:hover {{ background-color: rgba({rr}, {g_}, {b}, 0.32); }}")
    return "\n".join(out)


def fn_colors(r) -> dict:
    return {k: (r[k], r[f"{k}_border"], r[f"{k}_text"]) for k in FN_KEYS}


def fn_css(r) -> str:
    """Funktionsfarben: aktiv volle Farbe; inaktiv blasse Variante derselben Farbe, nie Grau."""
    out = []
    for k, (bg, border, text) in fn_colors(r).items():
        rr, g_, b = _rgb(bg)
        pale = f"mix({bg}, @theme_fg_color, 0.35)"
        out.append(f".evox-fn-{k} {{ background-image: none; background-color: {bg}; color: {text};"
                   f" border: 2px solid {border}; }}")
        out.append(f".evox-fn-{k} label {{ color: {text}; font-weight: bold; }}")
        out.append(f".evox-fn-{k}:disabled {{ background-color: rgba({rr}, {g_}, {b}, 0.28); color: {pale};"
                   f" border: 2px solid rgba({rr}, {g_}, {b}, 0.5); }}")
        out.append(f".evox-fn-{k}:disabled label {{ color: {pale}; }}")
    return "\n".join(out)


def tab_css(r) -> str:
    """Reiterknöpfe: aktiv volle Farbe + dicke Unterstreichung; inaktiv blasse Variante derselben Farbe."""
    out = [".evox-tabbtn { margin: 0; border-radius: 6px; }"]
    for k in TAB_KEYS:
        bg = r[k]
        rr, g_, b = _rgb(bg)
        pale = "mix(%s, @theme_fg_color, 0.35)" % bg
        sel = f".evox-tabbtn-{k}"
        out.append(f"{sel}:not(:checked) {{ background-color: rgba({rr}, {g_}, {b}, 0.28);"
                   f" border: 2px solid rgba({rr}, {g_}, {b}, 0.5); border-bottom: 3px solid rgba({rr}, {g_}, {b}, 0.5); }}")
        out.append(f"{sel}:not(:checked) label {{ color: {pale}; }}")
        out.append(f"{sel}:checked {{ border-bottom: 5px solid {r[k + '_border']}; }}")
    return "\n".join(out)


def select_styles(r) -> dict:
    """Markierung je Liste: Name -> (Hintergrund, Schrift, Schrift für rote Zeilen im markierten Zustand)."""
    return {n: (r[k], r[k + "_text"], r[k + "_alt"]) for n, k in SELECT_KEYS.items()}


def select_css(r) -> str:
    amber, amber_t, _ = select_styles(r)["amber"]
    css = "\n".join(
        f"{w}{st} {{ background-color: {amber}; background-image: none; color: {amber_t}; }}"
        for w in ("treeview.view", "list row") for st in (":selected", ":selected:focus", ":selected:hover", ":selected:backdrop"))
    css += f"\ntreeview.view:hover {{ background-color: alpha({amber}, 0.25); }}"
    for k in ("teal", "green"):
        bg, fg, _ = select_styles(r)[k]
        css += f"\ntreeview.view.evox-sel-{k}:hover {{ background-color: alpha({bg}, 0.25); }}"
        css += "\n" + "\n".join(
            f"treeview.view.evox-sel-{k}{st} {{ background-color: {bg}; background-image: none; color: {fg}; }}"
            for st in (":selected", ":selected:focus", ":selected:hover", ":selected:backdrop"))
    return css


def focus_glow(focus) -> str:
    return f"0 0 {FOCUS_GLOW_PX}px 2px alpha({focus}, {FOCUS_GLOW_ALPHA})"


def focus_inset() -> str:
    return f"inset 0 0 0 {FOCUS_OUTER_PX + FOCUS_INNER_PX}px {SAFETY['focus_inner']}"


def focus_css(r, focus) -> str:
    glow, inset, inner = focus_glow(focus), focus_inset(), SAFETY["focus_inner"]
    return f"""
{_FOCUS_SEL}
  {{ outline-color: {focus}; outline-style: solid; outline-width: {FOCUS_OUTER_PX}px;
    outline-offset: -{FOCUS_OUTER_PX}px; box-shadow: {inset}, {glow}; }}
/* 0.6.19: kein Rahmen je Zelle; ein Rahmen um das ganze Listenfeld (Wrapper .evox-listframe, Rand immer gleich dick, nur transparent -> kein Sprung) */
treeview.view.cell:focus {{ outline-style: none; box-shadow: none; }}
.evox-listframe {{ border: {FOCUS_OUTER_PX}px solid transparent; padding: {FOCUS_INNER_PX}px; }}
.evox-listframe.evox-listfocus {{ border-color: {focus}; box-shadow: inset 0 0 0 {FOCUS_INNER_PX}px {inner}, {glow}; }}
.evox-next:focus {{ box-shadow: {inset}, 0 0 0 2px rgba(255, 255, 255, 0.9), {glow}; }}
.evox-next.evox-start-disposable:focus {{ box-shadow: {inset}, 0 0 0 2px {r['step4_internet_ring']}, {glow}; }}
.evox-next.evox-start-offline:focus {{ box-shadow: {inset}, 0 0 0 2px {r['step4_offline_ring']}, {glow}; }}
.evox-focusline {{ font-size: 11pt; padding: 3px 8px; border-top: 1px solid alpha(@theme_fg_color, 0.35);
  background-color: alpha(@theme_fg_color, 0.07); }}
"""


def base_css(r) -> str:
    """Grundfläche/Schrift (nur Light oder bei eigener Wahl von Background/Text; Dark nutzt das System wie 0.7.5)."""
    return (f"\nwindow, dialog, messagedialog, .background {{ background-color: {r['background']}; color: {r['text']}; }}"
            f"\nwindow label, dialog label {{ color: {r['text']}; }}\n")


def paints_base(theme, overrides) -> bool:
    ov = {k for k, v in (overrides or {}).items() if k in ROLES and valid_hex(v)}
    return THEMES[theme_key(theme)]["base"] != "system" or "background" in ov or "text" in ov


def _on(bg: str) -> str:
    """Schriftfarbe mit dem besseren Kontrast (schwarz/weiß) auf einer Fläche."""
    return "#000000" if contrast(bg, "#000000") >= contrast(bg, "#ffffff") else "#ffffff"


def doc_card_css(r) -> str:
    """Documentation-Dialog (0.10.2): Karten Neongrün (Easy Guide), Türkis (Template), Gold (Vault), Lila (Titel); grau = nicht vorhanden."""
    rows = []
    for name, role in (("easy", "disposable"), ("quick", "template"), ("full", "vault"), ("dev", "title")):
        bg = r[role]
        rows.append(f".evox-doc-{name} {{ background-image: none; background-color: {bg}; color: {_on(bg)}; "
                    f"border: 2px solid {bg}; }}\n.evox-doc-{name} label {{ color: {_on(bg)}; font-weight: bold; }}")
    rows.append(".evox-doc-off { background-image: none; background-color: #5b5f6b; color: #ffffff; border: 2px solid #8a8e9a; }\n"
                ".evox-doc-off label { color: #ffffff; }")
    return "\n".join(rows)


def build_css(theme="dark", overrides=None, focus=None, scale=DEFAULT_SCALE) -> str:
    """Gesamtes GUI-CSS aus den Rollen. Dark ohne Änderungen, Fokus Limette, 100 % = Text von 0.7.5 (Test).
    focus: Vorrang vor der Rolle (EVOXD_FOCUS_COLOR); Sicherheitsfarben stammen immer aus SAFETY."""
    r = effective(theme, overrides)
    focus = focus if valid_hex(focus) else r["focus"]
    s = SAFETY
    css = f"""
window, dialog, messagedialog {{ font-size: 13pt; }}
.evox-title {{ font-size: 18pt; font-weight: bold; color: {r['title']}; text-shadow: 0 0 8px {r['title']}; }}
.evox-tagline {{ font-size: 15pt; font-weight: bold; color: {r['heading']}; }}
.evox-lock-bad {{ color: {s['error']}; font-weight: bold; }}
.evox-subline {{ font-size: 11pt; opacity: 0.7; }}
.evox-offline {{ background-image: none; background-color: {r['offline']}; color: {r['offline_text']};
  border: 2px solid {r['offline_border']}; }}
.evox-offline label {{ color: {r['offline_text']}; }}
.evox-offline:disabled {{ opacity: 0.5; }}
.evox-start-internet {{ background-image: none; background-color: {s['mode_internet']}; color: {s['mode_text']};
  border: 1px solid {s['mode_border']}; }}
.evox-start-internet label {{ color: {s['mode_text']}; }}
.evox-start-offline {{ background-image: none; background-color: {r['offline']}; color: {r['offline_text']};
  border: 1px solid {r['offline_border']}; }}
.evox-start-offline label {{ color: {r['offline_text']}; }}
.evox-start-internet:disabled, .evox-start-offline:disabled {{ opacity: 0.5; }}
.evox-cancel {{ background-image: none; background-color: {r['back']}; color: {r['back_text']};
  border: 2px solid {r['back_border']}; }}
.evox-cancel label {{ color: {r['back_text']}; }}
.evox-danger {{ background-image: none; background-color: {s['danger']}; color: {s['danger_text']};
  border: 2px solid {s['danger_border']}; }}
.evox-danger label {{ color: {s['danger_text']}; }}
.evox-danger:disabled {{ opacity: 0.5; }}
.evox-vault-btn {{ background-image: none; background-color: {r['vault']}; color: {r['vault_text']};
  border: 2px solid {r['vault_border']}; }}
.evox-vault-btn label {{ color: {r['vault_text']}; font-weight: bold; }}
.evox-import-btn {{ background-image: none; background-color: {r['template']}; color: {r['template_text']};
  border: 2px solid {r['template_border']}; }}
.evox-import-btn label {{ color: {r['template_text']}; font-weight: bold; }}
.evox-import-btn:disabled {{ opacity: 0.5; }}
.evox-start-disposable {{ background-image: none; background-color: {r['disposable']}; color: {r['disposable_text']};
  border: 2px solid {r['disposable_border']}; }}
.evox-start-disposable label {{ color: {r['disposable_text']}; font-weight: bold; }}
.evox-start-disposable:disabled {{ opacity: 0.5; }}
{tab_css(r)}
.evox-howto {{ padding: {HOWTO_PAD_V}px 8px; min-height: {HOWTO_BTN_HEIGHT - 2 * HOWTO_PAD_V - 4}px; font-weight: bold; }}
.evox-howto-compact {{ min-height: {HOWTO_BTN_HEIGHT_SMALL - 2 * HOWTO_PAD_V - 4}px; }}
.evox-howto:disabled {{ opacity: 0.45; }}
.evox-howto-orange {{ background-image: none; background-color: {r['step2']}; color: {r['step2_text']};
  border: 2px solid {r['step2_border']}; }}
.evox-howto-orange label {{ color: {r['step2_text']}; font-weight: bold; }}
.evox-next {{ box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.9), 0 0 8px 3px rgba(255, 255, 255, 0.55); }}
.evox-next.evox-start-disposable {{ box-shadow: 0 0 0 2px {r['step4_internet_ring']}, 0 0 {STEP4_GLOW_PX}px 3px {r['step4_internet_glow']}; }}
.evox-next.evox-start-offline {{ box-shadow: 0 0 0 2px {r['step4_offline_ring']}, 0 0 {STEP4_GLOW_PX}px 3px {r['step4_offline_glow']}; }}
.evox-block {{ border: 1px solid alpha(@theme_fg_color, 0.25); border-radius: 4px; padding: 4px 8px; }}
.evox-block-title {{ font-weight: bold; color: {r['heading']}; }}
.evox-block-small {{ font-size: 11pt; opacity: 0.8; }}
.evox-mon-block .evox-block-title {{ font-size: 13pt; }}
.evox-big {{ font-size: 20pt; font-weight: bold; }}
.evox-mid {{ font-size: 14pt; font-weight: bold; }}
.evox-details-btn {{ font-weight: bold; padding-top: 4px; padding-bottom: 4px; }}
.evox-mon-head {{ font-size: 16pt; font-weight: bold; color: {r['name']}; }}
.evox-mon-num {{ font-size: 22pt; font-weight: bold; }}
.evox-mon-stopped {{ font-size: 40pt; font-weight: bold; opacity: 0.85; }}
.evox-ram-hint {{ font-weight: bold; }}
.evox-howto-title {{ font-weight: bold; opacity: 0.8; }}
.evox-flash {{ box-shadow: 0 0 0 3px #ffffff, 0 0 14px 6px {r['flash']}; }}
.evox-vault-hint {{ color: {r['vault']}; font-weight: bold; }}
.evox-novault-hint {{ background-color: {r['vault']}; color: {r['vault_text']}; border-radius: 4px; padding: 4px 8px;
  font-size: 12pt; font-weight: bold; }}
{select_css(r)}
.evox-warn {{ color: {s['error']}; font-weight: bold; }}
.evox-btn-sub {{ font-size: 10pt; font-weight: normal; }}
.evox-bar-internet {{ background-color: {s['mode_internet']}; }}
.evox-bar-offline {{ background-color: {s['mode_offline']}; }}
.evox-chip {{ background-image: none; padding: 1px 6px; min-height: 0; min-width: 0; font-weight: bold;
  border-radius: 4px; }}
.evox-grp {{ font-weight: bold; padding: 0 2px; }}
{group_css(r)}
{fn_css(r)}
{focus_css(r, focus)}
.evox-hint-bar {{ background-color: {r['hint_bg']}; border-radius: 4px; padding: 4px 8px; }}
.evox-hint-bar label {{ color: {r['hint_text']}; }}
.evox-hint-icon {{ font-size: 16pt; font-weight: bold; }}
.evox-hint-text {{ font-size: 12pt; }}
.evox-hint-close {{ background-image: none; background-color: transparent; color: {r['hint_text']};
  border: 1px solid {r['hint_text']}; padding: 0 6px; min-height: 0; min-width: 0; }}
.evox-hint-close label {{ color: {r['hint_text']}; font-weight: bold; }}
.evox-vmname {{ font-size: 26pt; font-weight: bold; color: {r['vm_name']}; }}
.evox-dlg-internet {{ border: 1px solid {s['mode_internet']}; }}
.evox-dlg-offline {{ border: 1px solid {s['mode_offline']}; }}
.evox-bar-expl {{ font-size: 11pt; color: {s['mode_text']}; }}
.evox-bar-icon {{ font-size: 24pt; color: {s['mode_text']}; }}
.evox-bar-text {{ font-size: 20pt; font-weight: bold; color: {s['mode_text']}; }}
"""
    if paints_base(theme, overrides):
        css = base_css(r) + css         # Grund-CSS zuerst: Klassenregeln (auch Sicherheitsfarben) gewinnen
    return _scale_pt(css, scale_of(scale))


# ---- aktive Rollen für Python-seitige Farben (Markup, Zeichnen, Zellen); gesetzt von gui.apply_appearance
_active = {"theme": DEFAULT_THEME, "roles": effective(DEFAULT_THEME), "focus": DARK["focus"], "scale": DEFAULT_SCALE,
           "appearance": default_appearance()}


def activate(appearance, focus_env=None) -> dict:
    """Einstellung aktiv setzen; liefert die wirksamen Rollen. focus_env (EVOXD_FOCUS_COLOR) hat Vorrang."""
    a = sanitize(appearance)
    r = effective(a["theme"], a["roles"])
    _active.update(theme=a["theme"], roles=r, focus=focus_env if valid_hex(focus_env) else r["focus"],
                   scale=a["font_scale"], appearance=a)
    return r


def role(k) -> str:
    """Wirksame Farbe einer Rolle (Sicherheitsrollen immer fest)."""
    return SAFETY[k] if k in SAFETY else _active["roles"][k]


def active() -> dict:
    return dict(_active)


def active_css() -> str:
    """CSS der aktiven Einstellung (Hauptfenster und Dialoge)."""
    a = _active["appearance"]
    css = build_css(a["theme"], a["roles"], _active["focus"], a["font_scale"])
    if a["font_scale"] >= HOWTO_COMPACT_SCALE:      # 0.9.0: große Schrift -> engere Knöpfe, Fenster ≤ Arbeitsfläche
        css += compact_css()
    return css


def compact_css() -> str:
    return f".evox-howto-compact {{ padding-top: {HOWTO_PAD_COMPACT}px; padding-bottom: {HOWTO_PAD_COMPACT}px; }}\n"


# Vorschau (0.8.1/0.8.2): Elemente nutzen dieselben CSS-Klassen wie die echte GUI. Element -> Teile (Teil, Rolle):
# Teil "text" = Schriftfarbe, "background" = Fläche, "selected_text" = Schrift im markierten Zustand. Ein Element mit
# mehreren Teilen fragt im Ablauf nach dem Teil (Text color / Background color); mit einem Teil öffnet der Farbwähler direkt.
PART_ORDER = ("text", "background", "selected_text")


def _tb(text, bg):
    return (("text", text), ("background", bg))


PREVIEW_PARTS = {
    "title": (("text", "title"),), "heading": (("text", "heading"),), "text": (("text", "text"),),
    "name": (("text", "name"),), "background": (("background", "background"),),
    "tab_vault": _tb("vault_text", "vault"), "tab_template": _tb("template_text", "template"),
    "tab_disposable": _tb("disposable_text", "disposable"),
    "row_vault_sel": _tb("sel_amber_text", "sel_amber"), "row_vault_normal": (("text", "text"),),
    "row_template_sel": _tb("sel_teal_text", "sel_teal"),
    "row_template_backup": (("text", "backup_text"), ("selected_text", "sel_teal_alt")),
    "row_disposable_sel": _tb("sel_green_text", "sel_green"), "row_disposable_normal": (("text", "text"),),
    "btn_virt": _tb("vault_text", "vault"), "btn_make": _tb("make_text", "make"),
    "btn_import": _tb("template_text", "template"), "btn_verify": _tb("verify_text", "verify"),
    "btn_remove": _tb("remove_text", "remove"), "btn_start_internet": _tb("disposable_text", "disposable"),
    "btn_start_offline": _tb("offline_text", "offline"), "btn_show": _tb("neutral_text", "neutral"),
    "btn_keys": _tb("aux_text", "aux"), "btn_exit": _tb("exit_text", "exit"), "btn_back": _tb("back_text", "back"),
}
# Hauptrolle je Element (Fläche, sonst erster Teil); Altname aus 0.8.1
PREVIEW_ELEMENTS = {k: dict(p).get("background", p[0][1]) for k, p in PREVIEW_PARTS.items()}


def element_roles(key) -> tuple:
    return tuple(r for _p, r in PREVIEW_PARTS.get(key, ()))


def part_role(key, part=None):
    """Rolle eines Elementteils (part None = Hauptteil des Elements); None, wenn es das nicht gibt."""
    parts = PREVIEW_PARTS.get(key)
    if not parts:
        return None
    if part is None:
        return PREVIEW_ELEMENTS[key]
    return dict(parts).get(part)


def backup_color(overrides, sig) -> str:
    """Schrift der nicht markierten -BACKUP-Zeile: eigene Wahl (Rolle backup_text), sonst die Ampel-Rotfarbe wie 0.8.1."""
    v = (overrides or {}).get("backup_text")
    return v if valid_hex(v) else sig["bad"]


# Feste Sicherheitsbeispiele der Vorschau: nur rote Beispiele, nie klickbar, nie einstellbar
PREVIEW_FIXED = ("fixed_stop", "fixed_shut", "fixed_inactive", "fixed_error")
# Rahmen in der Vorschau (nur Darstellung): kurze Markierung der gewählten Rolle / Kontrastwarnung / Ablehnung
PREVIEW_MARK = {"mark": "#FFFFFF", "warn": SIGNAL_DARK["warn"], "bad": SAFETY["error"], "inner": SAFETY["focus_inner"]}


def signal_colors(r) -> dict:
    """Ampel-/Rotfarben passend zur Grundfläche (hell/dunkel), wie die echte GUI (Schriftfarbe-Helligkeit)."""
    return SIGNAL_DARK if lum(r["background"]) < 0.4 else SIGNAL_LIGHT


def preview_css(appearance, focus_env=None) -> str:
    """CSS der Vorschau im Color-settings-Dialog: das echte GUI-CSS (build_css, gleiche Klassen/Rollen) des Entwurfs,
    pro Widget der Vorschau als eigener Provider geladen (Haupt-CSS bleibt unberührt), plus nur Vorschau-Zusätze
    (.evox-preview Fläche/Schriftgröße, Markierrahmen, Fokus für Klick-Flächen, feste Sicherheitsbeispiele)."""
    a = appearance
    scale = scale_of(a.get("font_scale"))
    r = effective(a.get("theme"), a.get("roles"))
    focus = focus_env if valid_hex(focus_env) else r["focus"]
    m, sig = PREVIEW_MARK, signal_colors(r)
    extra = f"""
.evox-preview {{ background-color: {r['background']}; color: {r['text']}; padding: 6px; border-radius: 4px; font-size: 13pt; }}
.evox-pv-text {{ color: {r['text']}; }}
.evox-preview treeview.view:not(:selected) {{ background-color: {r['background']}; color: {r['text']}; }}
.evox-pv-fixed {{ padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
.evox-pv-mark {{ box-shadow: 0 0 0 3px {m['mark']}, 0 0 0 5px {m['inner']}; }}
.evox-pv-warn {{ box-shadow: 0 0 0 3px {m['warn']}, 0 0 0 5px {m['inner']}; }}
.evox-pv-bad {{ box-shadow: 0 0 0 3px {m['bad']}, 0 0 0 5px {m['inner']}; }}
"""
    return build_css(a.get("theme"), a.get("roles"), focus_env, scale) + _scale_pt(extra, scale)

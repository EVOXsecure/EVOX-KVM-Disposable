"""Einfache GTK3-Oberfläche (T7; Konsole über virt-viewer --attach). Texte englisch, Doku deutsch."""
import collections
import datetime
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import __version__, capacity, config, livestats, manual, purposes, setupcheck, theme  # noqa: E402
from . import texts as T  # noqa: E402
from .cli import (_fmt_ts, fmt_cpus, no_core_dumps, open_console, open_evox,  # noqa: E402
                  open_virt_manager, viewer_error)
from .errors import Cancelled, EvoxError  # noqa: E402
from . import lifecycle  # noqa: E402
from .lifecycle import is_backup, purpose_name  # noqa: E402
from .net import check  # noqa: E402

APP_TITLE = T.APP_TITLE
REFRESH_S = 5
LIVE_S = 1          # 0.7.2: Live-Takt nur solange eine Wegwerf-VM läuft; feste Untergrenze 1 s (nie darunter)
VIEWER_CHECK_S = 3
PULSE_MS = 200
ICON_NAME = "evoxd"
# Einheitliche Abstände (Pixel)
MARGIN = 10      # Fensterrand, Dialoginhalt
SPACING = 6      # zwischen Elementen
INNER = 6        # Innenrand der Gruppen
HOWTO_GAP = 4    # Abstand zwischen den HOW-TO-Knöpfen (vertikal und INTERNET/OFFLINE)
HOWTO_BTN_HEIGHT = 36          # Mindesthöhe aller HOW-TO-Knöpfe (Außenmaß inkl. Rahmen und Innenabstand)
HOWTO_BTN_HEIGHT_SMALL = 30    # moderat reduziert bei kleiner Arbeitsfläche (statt zu scrollen)
HOWTO_SMALL_WORKAREA = 720     # Arbeitsflächenhöhe, unter der die kleinere Höhe gilt
HOWTO_PAD_V = 4                # vertikaler Innenabstand; Rahmen 2 px oben und unten
# 0.8.0 (A4a): ALLE Farben stehen als Rollen in theme.py (Themes, feste Sicherheitsfarben). Die Namen hier sind nur
# Verweise auf das Theme "Dark (default)" bzw. SAFETY (Abwärtskompatibilität, Tests); wirksame Werte: theme.role().
_D, _S = theme.DARK, theme.SAFETY
COLORS_LIGHT = theme.SIGNAL_LIGHT   # Ampel/Signal (fest): dunkle Töne auf hellem, helle auf dunklem Hintergrund
COLORS_DARK = theme.SIGNAL_DARK
RAM_LEVEL_COLOR = {"low": "ok", "ok": "ok", "high": "warn", "full": "bad"}   # Ampelstufe -> Schlüssel in COLORS_*
# 0.7.1 Detailbereich: Balken, Sparkline, weiche Übergänge (nur beim Wertwechsel, kein Dauer-Timer)
METER_HEIGHT = 14                  # Höhe der waagerechten Balken (px)
METER_ZONE_ALPHA = 0.28            # Zonen grün/gelb/rot im RAM-Balken (Hintergrund, blass)
METER_TRACK = (0.5, 0.5, 0.5, 0.18)  # leere Bahn (RGBA, auf hell und dunkel sichtbar)
METER_PEAK_COLOR = "#ffffff"       # Peak-Marke: helle Linie mit dunklem Rand (fest, auf jedem Balken lesbar)
METER_PEAK_EDGE = _S["focus_inner"]
CPU_BAR_COLOR = _D["cpu_bar"]      # CPU-Balken und Sparkline (Rolle cpu_bar; keine Ampelbedeutung)
SPARK_SIZE = (180, 34)             # Sparkline (Breite, Höhe) in px
# 0.7.2 großer Detailbereich: dickere Balken, größere Sparkline, ca. halbe Fensterhöhe
METER_HEIGHT_BIG = 26
SPARK_SIZE_BIG = (260, 60)
LIST_KEEP_H = 120                  # Mindesthöhe des Listeninhalts im Hauptfenster
# 0.7.4 Live Monitor als eigenes Fenster: dicke Balken (dehnen sich mit dem Fenster), große Zahlen (CSS)
METER_HEIGHT_MON = 36
SPARK_SIZE_MON = (260, 60)         # Mindestgröße der Sparkline im Monitor; sie dehnt sich
MON_MIN_SIZE = (870, 350)          # kleinste Fenstergröße des Monitors (gemessen: Inhalt braucht 866×348)
MON_DEFAULT_SIZE = (940, 460)
TRANSITION_S = 0.3                 # weicher Übergang beim Wertwechsel
NEON_GREEN = _D["disposable"]      # 0.7.5: Neongrün für alles rund um DISPOSABLE / INTERNET (Titel bleibt Lila)
NAME_COLOR = _D["name"]            # Namen (VM, Template) im Bestätigungsfenster und Live Monitor
ACCENT = _D["heading"]             # Türkis-Akzent (Tagline, Blocktitel)
TITLE_COLOR = _D["title"]          # Titel (Markenfarbe Lila), mit Glüheffekt
MODE_INTERNET = _S["mode_internet"]  # Modusfarben fest (Sicherheit): Kopfleiste/Rahmen Startdialog, Speichern-Knopf
MODE_OFFLINE = _S["mode_offline"]
OFFLINE_COLOR = _D["offline"]      # Knopf Start OFFLINE (Rolle offline; Dark = MODE_OFFLINE)
MODE_BORDER = _S["mode_border"]
OFFLINE_BORDER = _D["offline_border"]
CANCEL_COLOR = _D["back"]          # ← BACK / Cancel: gedämpftes Rot
CANCEL_BORDER = _D["back_border"]
DANGER_COLOR = _S["danger"]        # Stop and erase / SHUT DOWN & ERASE: Gefahr-Rot (fest)
DANGER_BORDER = _S["danger_border"]
TAB_DISPOSABLE_COLOR = _D["disposable"]
TAB_TEMPLATE_COLOR = _D["template"]
TEMPLATE_BORDER = _D["template_border"]
TEMPLATE_TEXT = _D["template_text"]
DISPOSABLE_BORDER = _D["disposable_border"]
DISPOSABLE_TEXT = _D["disposable_text"]
VAULT_GOLD = _D["vault"]
VAULT_GOLD_BORDER = _D["vault_border"]
VAULT_GOLD_TEXT = _D["vault_text"]
TAB_VAULT_COLOR = VAULT_GOLD
TAB_KEYS = theme.TAB_KEYS          # Reihenfolge der Reiter (Ablauf 1 → 3)
TAB_COLORS = {k: _D[k] for k in TAB_KEYS}
SELECT_AMBER = _D["sel_amber"]
SELECT_TEXT = _D["sel_amber_text"]
SELECT_TEAL = _D["sel_teal"]
SELECT_GREEN = _D["sel_green"]
SELECT_GREEN_TEXT = _D["sel_green_text"]
SELECT_STYLES = theme.select_styles(_D)   # Name -> (Hintergrund, Schrift, Schrift für rote Zeilen markiert)
FOCUS_DEFAULT = _D["focus"]         # Tastaturfokus: Limette (Neongelbgrün)
FOCUS_ENV = "EVOXD_FOCUS_COLOR"     # Live-Vergleich: hat Vorrang vor Color settings, nur streng #RRGGBB


def _focus_color(environ=None):
    """FOCUS_DEFAULT, oder der Wert aus EVOXD_FOCUS_COLOR, wenn er streng #RRGGBB ist (sonst still ignoriert)."""
    v = (os.environ if environ is None else environ).get(FOCUS_ENV, "")
    return v if re.fullmatch(r"#[0-9A-Fa-f]{6}", v) else FOCUS_DEFAULT


def focus_env(environ=None):
    """Gültiger Wert aus EVOXD_FOCUS_COLOR oder None (dann gilt die Rolle focus aus Color settings)."""
    v = (os.environ if environ is None else environ).get(FOCUS_ENV, "")
    return v if theme.valid_hex(v) else None


FOCUS_COLOR = _focus_color()        # Startwert ohne Benutzereinstellung (Theme Dark); wirksam: theme.active()["focus"]
FOCUS_INNER = _S["focus_inner"]     # Doppelrand innen: neutrales Fast-Schwarz (fest)
FOCUS_INNER_PX = theme.FOCUS_INNER_PX
FOCUS_OUTER_PX = theme.FOCUS_OUTER_PX
FOCUS_GLOW_PX = theme.FOCUS_GLOW_PX
FOCUS_GLOW_ALPHA = theme.FOCUS_GLOW_ALPHA
FOCUS_PX = FOCUS_OUTER_PX            # Altname (0.6.15)
START_TAB = "disposable"                          # beim Programmstart vorausgewählt
HOWTO_ORANGE = _D["step2"]
HOWTO_ORANGE_BORDER = _D["step2_border"]
HOWTO_ORANGE_TEXT = _D["step2_text"]
STEP4_INTERNET_RING = _D["step4_internet_ring"]
STEP4_INTERNET_GLOW = _D["step4_internet_glow"]
STEP4_OFFLINE_RING = _D["step4_offline_ring"]
STEP4_OFFLINE_GLOW = _D["step4_offline_glow"]
STEP4_GLOW_PX = theme.STEP4_GLOW_PX
# Farbklasse je HOW-TO-Knopf: 1 Gold, 2 Orange, 3 Türkis, 4 INTERNET Neongrün (Reiter DISPOSABLE), 4 OFFLINE Blau
HOWTO_CLASSES = ("evox-vault-btn", "evox-howto-orange", "evox-import-btn", "evox-start-disposable",
                 "evox-start-offline")
FN_COLORS = theme.fn_colors(_D)    # Funktionsfarben (Füllung, Rand, Schrift) je Knopf-Klasse evox-fn-<name>
HINT_BAR_BG = _D["hint_bg"]
HINT_BAR_TEXT = _D["hint_text"]
HINT_MARK_BG = _D["hint_mark_bg"]
HINT_MARK_FG = _D["hint_mark_fg"]
FLASH_MS = 1500                                   # Dauer der Hervorhebung durch die HOW-TO-Knöpfe
GROUP_COLORS = {k: _D[f"grp_{k}"] for k in theme.GROUP_KEYS}
VMNAME_COLOR = _D["vm_name"]
DIALOG_DECOR = 60        # Platz für Titelleiste/Rand/Panel-Reste beim Begrenzen der Dialoghöhe
START_SIZE = (980, 560)  # Standardgröße Startdialog (wird auf die Arbeitsfläche begrenzt)
EDIT_SIZE = (520, 440)   # Standardgröße Bearbeitungsdialog
MIN_SIZE = (980, 700)    # Mindestgröße bei großer Schrift
gib = livestats.fmt_gb1          # 0.7.4: Kapazität/freier Platz einheitlich „6,8 GB“ (eine Stelle)

GROUP_CSS = theme.group_css(_D)     # Teil-CSS (Dark, Altnamen für Tests); erzeugt in theme.py
FN_CSS = theme.fn_css(_D)

# Reiter als eigene Knöpfe (0.6.14): Farbklassen der HOW-TO-Knöpfe (Gold / Türkis / Neongrün), Größe über "evox-howto"
TAB_CLASSES = {"vault": "evox-vault-btn", "template": "evox-import-btn", "disposable": "evox-start-disposable"}
TAB_STYLE = {"vault": VAULT_GOLD_BORDER, "template": TEMPLATE_BORDER, "disposable": DISPOSABLE_BORDER}   # Unterstreichung


TAB_CSS = theme.tab_css(_D)


def sel_fg_column(view, title, text_i, fg_i, sel, sens_i=None, sel_plain=False):
    """Spalte mit eigener Schriftfarbe je Zeile; im markierten Zustand die lesbare Ersatzfarbe der Liste (nur Darstellung).
    sel_plain=True: markiert gilt die normale Markierungsschrift (z. B. RAM-Ampel; Symbol + Wort bleiben lesbar)."""
    cell = Gtk.CellRendererText()
    alt_role = None if sel_plain else theme.SELECT_KEYS[sel] + "_alt"   # wirksame Farbe beim Zeichnen (Theme)
    selection = view.get_selection()

    def data(_col, rend, model, it, _data=None):
        row = model[it]
        rend.set_property("text", row[text_i])
        if sens_i is not None:
            rend.set_property("sensitive", row[sens_i])
        fg = row[fg_i]
        if fg is not None and selection.path_is_selected(model.get_path(it)):
            fg = theme.role(alt_role) if alt_role else None
        if not fg:
            fg = None
        if fg is None:
            rend.set_property("foreground-set", False)
        else:
            rend.set_property("foreground", fg)
    col = Gtk.TreeViewColumn(title, cell)
    col.set_cell_data_func(cell, data)
    return col


def list_frame(sw, view, sel="amber"):
    """Listenfeld mit EINEM Fokusrahmen (statt je Zelle): Wrapper trägt bei Tastaturfokus der Liste .evox-listfocus.
    Nur Darstellung; die Auswahlfarbe (sel: amber/teal/green) liegt im Inneren und wird nicht verdeckt."""
    view.get_style_context().add_class(f"evox-sel-{sel}")
    box = Gtk.Box()
    box.get_style_context().add_class("evox-listframe")
    box.pack_start(sw, True, True, 0)
    ctx = box.get_style_context()
    view.connect("focus-in-event", lambda *_: (ctx.add_class("evox-listfocus"), False)[1])
    view.connect("focus-out-event", lambda *_: (ctx.remove_class("evox-listfocus"), False)[1])
    return box


def fn_class(btn, key):
    """Funktionsfarbe setzen (key aus FN_COLORS); gibt den Knopf zurück."""
    btn.get_style_context().add_class(f"evox-fn-{key}")
    return btn

SELECT_CSS = theme.select_css(_D)
# Fokusrand (0.6.16): Doppelrand + Schein, erzeugt in theme.focus_css (Outline innen, Innenrand fest, Schein in Fokusfarbe)
_FOCUS_SEL = theme._FOCUS_SEL
_FOCUS_GLOW = theme.focus_glow(FOCUS_COLOR)
_FOCUS_INSET = theme.focus_inset()
FOCUS_CSS = theme.focus_css(_D, FOCUS_COLOR)
# Gesamt-CSS beim Import: Theme Dark, 100 %, Fokus wie FOCUS_COLOR (= 0.7.5). Wirksam: theme.active_css() (Color settings).
CSS = theme.build_css(focus=FOCUS_COLOR)
_css_done = False


def two_line_button(title, sub):
    """Knopf mit Titel und kleiner zweiter Zeile; Labels als .title_lbl / .sub_lbl erreichbar."""
    btn = Gtk.Button()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin=2)
    btn.title_lbl = Gtk.Label(label=title)
    btn.title_lbl.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
    btn.sub_lbl = Gtk.Label(label=sub, wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=34)
    btn.sub_lbl.get_style_context().add_class("evox-btn-sub")
    box.pack_start(btn.title_lbl, False, False, 0)
    box.pack_start(btn.sub_lbl, False, False, 0)
    btn.add(box)
    return btn


# ---- Diagnose (0.6.14): nur mit EVOXD_GUI_TRACE=1; sonst keine Wirkung (kein Zählen, keine Ausgabe)
TRACE_ENV = "EVOXD_GUI_TRACE"
TRACE_COUNTS = collections.Counter()


def trace_on() -> bool:
    return os.environ.get(TRACE_ENV) == "1"


def trace(kind, detail=""):
    """Aufrufart zählen und auf stderr melden (nur mit EVOXD_GUI_TRACE=1)."""
    if trace_on():
        TRACE_COUNTS[kind] += 1
        print(f"[gui-trace] {kind} {detail}".rstrip(), file=sys.stderr, flush=True)


def trace_cycle(n):
    """Zusammenfassung eines 5-Sekunden-Zyklus ausgeben und Zähler zurücksetzen."""
    if trace_on():
        summary = " ".join(f"{k}={v}" for k, v in sorted(TRACE_COUNTS.items())) or "(keine Aufrufe)"
        print(f"[gui-trace] === Zyklus {n}: {summary}", file=sys.stderr, flush=True)
        TRACE_COUNTS.clear()


def _name(w):
    return type(w).__name__ + ":" + (w.get_name() or "")


def set_text(label, text):
    """Label nur bei geändertem Text setzen (kein Neuzeichnen pro Zyklus)."""
    if label.get_text() != text or label.get_use_markup():
        trace("set_text", f"{_name(label)} {text[:30]!r}")
        label.set_text(text)


def set_markup(label, markup):
    if label.get_label() != markup or not label.get_use_markup():
        trace("set_markup", f"{_name(label)} {markup[:30]!r}")
        label.set_markup(markup)


def set_tooltip(widget, tip):
    if widget.get_tooltip_text() != tip:
        trace("set_tooltip", _name(widget))
        widget.set_tooltip_text(tip)


def set_class(widget, cls, on):
    ctx = widget.get_style_context()
    if ctx.has_class(cls) != bool(on):
        trace("css_class", f"{_name(widget)} {'+' if on else '-'}{cls}")
        (ctx.add_class if on else ctx.remove_class)(cls)


def set_sensitive(widget, on):
    if widget.get_sensitive() != bool(on):
        trace("set_sensitive", f"{_name(widget)} {bool(on)}")
        widget.set_sensitive(bool(on))


def set_shown(widget, on):
    if widget.get_visible() != bool(on):
        trace("set_visible", f"{_name(widget)} {bool(on)}")
        widget.set_visible(bool(on))


def apply_css():
    """CSS einmal für den ganzen Bildschirm laden (Hauptfenster und Dialoge); Inhalt = aktive Einstellung (theme)."""
    global _css_done, _provider
    screen = Gdk.Screen.get_default()
    if _css_done or screen is None:
        return
    prov = Gtk.CssProvider()
    trace("css_load")
    prov.load_from_data(theme.active_css().encode())
    trace("css_add_provider")
    Gtk.StyleContext.add_provider_for_screen(screen, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _provider = prov
    _css_done = True


_provider = None          # 0.8.0: geladener CSS-Provider (wird bei Color settings genau einmal ersetzt)
_gtk_base = None          # ursprüngliche GTK-Einstellung (Theme-Name, dunkel bevorzugt) vor dem ersten Wechsel


def _apply_base(theme_key):
    """Grundfarben: "system" = GTK-Theme unverändert (wie 0.7.5); "light" = helles GTK-Theme nur in diesem Prozess
    (Gtk.Settings, keine Datei, kein Host-Eingriff). Setzt nur bei Änderung (kein unnötiges Neuzeichnen)."""
    global _gtk_base
    st = Gtk.Settings.get_default()
    if st is None:
        return
    cur = (st.props.gtk_theme_name, st.props.gtk_application_prefer_dark_theme)
    base = theme.THEMES[theme.theme_key(theme_key)]["base"]
    if base in ("light", "dark"):
        if _gtk_base is None:
            _gtk_base = cur
        want = ("Adwaita", base == "dark")
    elif _gtk_base is not None:
        want = _gtk_base
    else:
        return
    if cur != want:
        trace("gtk_base", str(want))
        st.props.gtk_theme_name, st.props.gtk_application_prefer_dark_theme = want


def apply_appearance(appearance, live=True):
    """Einstellung aktivieren (EVOXD_FOCUS_COLOR hat Vorrang vor der Rolle focus). live=True und CSS schon geladen:
    alten Provider entfernen, neues CSS genau einmal laden (kein Neustart nötig). Liefert die bereinigte Einstellung."""
    global _provider
    before = theme.active_css()
    theme.activate(appearance, focus_env())
    a = theme.active()["appearance"]
    _apply_base(a["theme"])
    screen = Gdk.Screen.get_default()
    if live and _css_done and screen is not None and theme.active_css() != before:
        prov = Gtk.CssProvider()
        trace("css_load")
        prov.load_from_data(theme.active_css().encode())
        if _provider is not None:
            Gtk.StyleContext.remove_provider_for_screen(screen, _provider)
        trace("css_add_provider")
        Gtk.StyleContext.add_provider_for_screen(screen, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _provider = prov
    return a


def howto_compact() -> bool:
    """Kleinere Knopfhöhe (HOW-TO und Reiter): kleine Arbeitsfläche oder große Schrift (ab 130 %, 0.9.0)."""
    return workarea_height() < HOWTO_SMALL_WORKAREA or theme.active()["scale"] >= theme.HOWTO_COMPACT_SCALE


def workarea_height(widget=None) -> int:
    """Höhe der Arbeitsfläche (ohne Panel) des Monitors, auf dem das Fenster liegt; Notwert 768."""
    display = Gdk.Display.get_default()
    if display is None:
        return 768
    win = widget.get_window() if widget is not None else None
    mon = display.get_monitor_at_window(win) if win is not None else None
    mon = mon or display.get_primary_monitor() or (display.get_monitor(0) if display.get_n_monitors() else None)
    return mon.get_workarea().height if mon is not None else 768


def fit_dialog(dlg, parent, size):
    """Standardgröße setzen, Höhe auf die Arbeitsfläche begrenzen (Inhalt scrollt, Leisten bleiben)."""
    w, h = size
    h = max(240, min(h, workarea_height(parent) - DIALOG_DECOR))
    dlg.set_default_size(w, h)
    dlg.fitted_height = h


def back_button(dlg) -> Gtk.Button:
    """Oberer ← BACK-Knopf (Kopfleiste): schließt nur den Dialog."""
    b = Gtk.Button(label=T.BACK, valign=Gtk.Align.CENTER)
    b.get_style_context().add_class("evox-cancel")
    b.connect("clicked", lambda *_: dlg.response(Gtk.ResponseType.CANCEL))
    return b


def style_responses(dlg, ok_resp, ok_class, cancel_resp):
    """Farben für die Standardknöpfe eines MessageDialogs (Bestätigen = Funktionsfarbe, Abbrechen = gedämpftes Rot)."""
    for resp, cls in ((ok_resp, ok_class), (cancel_resp, "evox-cancel")):
        w = dlg.get_widget_for_response(resp)
        if w is not None:
            w.get_style_context().add_class(cls)


def secure_dialog(dlg, cancel_resp=Gtk.ResponseType.CANCEL):
    """Tastaturregeln für jeden Dialog (0.6.15): Anfangsfokus und Vorgabe auf Zurück/Abbrechen (Enter direkt nach dem
    Öffnen löst nichts aus), Esc = Zurück (kein Start, keine Aktion). Nur Bedienung; Bestätigungen unverändert."""
    dlg.set_default_response(cancel_resp)
    w = dlg.get_widget_for_response(cancel_resp)
    if w is not None:
        w.grab_focus()
    if not getattr(dlg, "_evox_keys", False):
        dlg._evox_keys = True
        dlg.connect("key-press-event", dialog_key, cancel_resp)
    return dlg


def dialog_key(dlg, event, cancel_resp=Gtk.ResponseType.CANCEL):
    if event.keyval == Gdk.KEY_Escape:
        dlg.response(cancel_resp)
        return True
    return False


def hint_markup() -> str:
    """Text des Hinweisbalkens: Satzanfang fett, Namensmuster als kleine dunkle Marken."""
    esc = GLib.markup_escape_text

    def mark(t):
        return (f'<span foreground="{theme.role("hint_mark_fg")}" background="{theme.role("hint_mark_bg")}">'
                f'<b> {esc(t)} </b></span>')

    return (f"<b>{esc(T.HINT_OPENED)}</b> {esc(T.HINT_NAME_NEW)} {mark(T.HINT_PATTERN_VAULT)} "
            f"{esc(T.HINT_OR)} {mark(T.HINT_PATTERN_TEMPLATE)}{esc(T.HINT_END)}")


def fmt_datetime(ts, seconds=False) -> str:
    fmt = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    return datetime.datetime.fromtimestamp(ts).strftime(fmt) if ts else "-"


def empty_stack(child, text):
    """Liste oder Erklärsatz (leerer Reiter); Umschalten mit set_visible_child_name("list"/"empty")."""
    st = Gtk.Stack()
    st.add_named(child, "list")
    lbl = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER, margin=MARGIN * 2)
    st.add_named(lbl, "empty")
    st.empty_label = lbl
    return st


def theme_colors(widget) -> dict:
    """Signalfarben passend zum Theme: Helligkeit der normalen Schriftfarbe entscheidet."""
    try:
        fg = widget.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        dark = 0.2126 * fg.red + 0.7152 * fg.green + 0.0722 * fg.blue > 0.5
    except Exception:  # noqa: BLE001 – ohne Theme-Daten helle Variante
        dark = False
    return COLORS_DARK if dark else COLORS_LIGHT


def colored(text: str, color: str, bold: bool = True) -> str:
    t = GLib.markup_escape_text(text)
    return f'<span foreground="{color}">{"<b>" + t + "</b>" if bold else t}</span>'


def _err_text(e: BaseException) -> str:
    return str(e) if isinstance(e, EvoxError) else f"{type(e).__name__}: {e}"


def live_cells(v) -> tuple:
    """Listenzellen der Live-Werte (0.7.1 schlank): ((Laufzeit, RAM-Ampel, CPU), Ampelstufe).
    v = LiveSampler.sample() oder None; fehlende Werte → "n/a"."""
    na = T.LIVE_NA
    if not v:
        return (na,) * 3, None
    lvl = v.get("ram_level")
    ram = (T.LIVE_RAM_CELL.format(sym=T.RAM_LEVELS[lvl][0], est=T.LIVE_EST if v.get("ram_est") else "",
                                  pct=v["ram_pct"]) if lvl else na)
    return (livestats.fmt_runtime(v.get("runtime")), ram, cpu_text(v)), lvl


def cpu_text(v) -> str:
    if v and v.get("cpu_pct") is not None:
        return T.LIVE_CPU.format(pct=v["cpu_pct"])
    return T.LIVE_WAIT if v and v.get("cpu_wait") else T.LIVE_NA


def fmt_gb(b) -> str:
    """RAM im Detailbereich und im Hinweis: immer eine Nachkommastelle in GiB (z. B. 1,8 GiB)."""
    return f"{capacity.fmt_dec(b / 2**30)} GiB"


def ram_block_texts(v) -> tuple:
    """Block a) RAM: (Zeile 1 „■ FULL  1,8 / 2,0 GiB (90 %)“, Zeile 2 Spitze/Zeitpunkt/Zähler, Ampelstufe).
    Ohne Werte: ("n/a"-Satz, "", None) – nie erfunden."""
    if not v or not v.get("ram_level"):
        return T.RAM_NA, "", None
    lvl = v["ram_level"]
    sym, word = T.RAM_LEVELS[lvl]
    line1 = (T.RAM_LEVEL_LINE.format(sym=sym, word=word) + "  "
             + T.RAM_LINE.format(used=capacity.fmt_dec(v["ram_used"] / 2**30), size=fmt_gb(v["ram_size"]),
                                 pct=v["ram_pct"], est=T.LIVE_EST_DETAIL if v.get("ram_est") else ""))
    parts = []
    if v.get("peak") is not None:
        when = datetime.datetime.fromtimestamp(v["peak_time"]).strftime("%H:%M") if v.get("peak_time") else "?"
        parts.append(T.RAM_PEAK.format(peak=fmt_gb(v["peak"]), pct=v["peak_pct"], time=when))
    if v.get("full_count"):
        parts.append(T.RAM_FULL_COUNT.format(n=v["full_count"]))
    return line1, " · ".join(parts), lvl


def net_block_texts(v, t, starts) -> tuple:
    """Block c) Netz/Overlay: Werte in der Reihenfolge T.NET_ROWS. t = Zeilendaten der VM (Template, Modus, Sperre)."""
    na = T.LIVE_NA
    rx, tx = (v.get("rx"), v.get("tx")) if v else (None, None)
    net = (T.LIVE_NO_NET if rx == "none" else na if rx is None
           else T.LIVE_NET.format(rx=livestats.fmt_bytes(rx), tx=livestats.fmt_bytes(tx)))
    ovl, disk, peak = (v.get("overlay"), v.get("disk_size"), v.get("overlay_peak")) if v else (None, None, None)
    if ovl is None:
        ov = na
    elif disk:
        ov = T.OVERLAY_LINE.format(used=livestats.fmt_bytes(ovl), disk=livestats.fmt_bytes(disk),
                                   pct=min(100, round(ovl * 100 / disk)), peak=livestats.fmt_bytes(peak))
    else:
        ov = T.OVERLAY_LINE_NODISK.format(used=livestats.fmt_bytes(ovl), peak=livestats.fmt_bytes(peak))
    up = livestats.fmt_runtime(v.get("runtime")) if v else na
    purpose = livestats.purpose_of(t["name"]) or "?"
    st = T.STARTS_LINE.format(purpose=purpose, n=starts) if starts else na
    return net, ov, up, t["template"], t["mode_text"], T.LOCK_STATE[t["lock"]], st


def ram_hint_text(summary, purpose=None):
    """Hinweis beim Stop and erase: (Ampelstufe, Text, Vorschlag MiB oder None) oder None ohne echte Werte."""
    if not summary:
        return None
    h = livestats.ram_hint(summary.get("peak"), summary.get("size"), summary.get("full"))
    if h is None:
        return None
    kind, sug = h
    peak, size = summary["peak"], summary["size"]
    pct = min(100, round(peak * 100 / size))
    lvl = "full" if kind == "full" else livestats.ram_level(pct)       # gleiche Ampel wie Balken/Liste
    text = T.HINT_RAM[kind].format(peak=fmt_gb(peak), size=fmt_gb(size), pct=pct,
                                   sug=livestats.fmt_ram_gb(sug) if sug else "", n=summary.get("full", 0))
    return lvl, T.RAM_LEVELS[lvl][0] + " " + text, sug


def _rgba(hex_color, alpha=1.0):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha


class _Tween:
    """Weicher Übergang (TRANSITION_S) nur beim Wertwechsel: Tick-Rückruf läuft nur während des Übergangs und
    entfernt sich danach selbst (kein Dauer-Timer). Ungemappt (Tests, verdeckt): sofort ohne Übergang."""

    def _tween_init(self):
        self._shown = None        # aktuell gezeichnete Werte (tuple)
        self._from = self._to = None
        self._t0 = None
        self._tick_cb = None

    def _tween_to(self, target):
        if target == self._to:
            return False
        self._to = target
        if self._shown is None or not self.get_mapped() or None in target or None in self._shown:
            self._shown = target
            if self._tick_cb is not None:
                self.remove_tick_callback(self._tick_cb)
                self._tick_cb = None
        else:
            self._from, self._t0 = self._shown, None
            if self._tick_cb is None:
                self._tick_cb = self.add_tick_callback(self._on_frame)
        self.queue_draw()
        return True

    def _on_frame(self, _w, clock):
        now = clock.get_frame_time() / 1e6
        if self._t0 is None:
            self._t0 = now
        f = min(1.0, (now - self._t0) / TRANSITION_S)
        e = 1 - (1 - f) ** 3                                      # sanft abbremsen
        self._shown = tuple(a + (b - a) * e for a, b in zip(self._from, self._to))
        self.queue_draw()
        if f >= 1.0:
            self._shown, self._tick_cb = self._to, None
            return False
        return True


class MeterBar(_Tween, Gtk.DrawingArea):
    """Waagerechter Balken 0–100 %: optional Zonen grün/gelb/rot (RAM), Füllung in Ampel-/Blockfarbe, Peak-Marke.
    set() zeichnet nur bei geändertem Wert neu (unveränderter Zyklus = 0 GTK-Aufrufe)."""

    def __init__(self, zones=False, height=METER_HEIGHT):
        Gtk.DrawingArea.__init__(self)
        self._tween_init()
        self.zones = zones
        self.colors = COLORS_DARK
        self.color = theme.role("cpu_bar")
        self.value = self.peak = None
        self.set_size_request(-1, height)
        self.connect("draw", self._draw)

    def set(self, value, peak=None, color=None):
        """value/peak in Prozent (None = unbekannt: leere Bahn)."""
        changed = color is not None and color != self.color
        if changed:
            self.color = color
        self.value, self.peak = value, peak
        moved = self._tween_to((value, peak))
        if changed and not moved:
            self.queue_draw()
        return changed or moved

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cr.set_source_rgba(*METER_TRACK)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if self.zones:
            for lo, hi, key in ((0, livestats.RAM_OK_MAX_PCT, "ok"),
                                (livestats.RAM_OK_MAX_PCT, livestats.RAM_HIGH_MAX_PCT, "warn"),
                                (livestats.RAM_HIGH_MAX_PCT, 100, "bad")):
                cr.set_source_rgba(*_rgba(self.colors[key], METER_ZONE_ALPHA))
                cr.rectangle(w * lo / 100, 0, w * (hi - lo) / 100, h)
                cr.fill()
        val, peak = self._shown if self._shown else (None, None)
        if val is not None:
            cr.set_source_rgba(*_rgba(self.color))
            cr.rectangle(0, 2, w * max(0, min(val, 100)) / 100, h - 4)
            cr.fill()
        if peak is not None:
            x = max(1.5, min(w * peak / 100, w - 1.5))
            cr.set_source_rgba(*_rgba(METER_PEAK_EDGE))
            cr.rectangle(x - 2, 0, 4, h)
            cr.fill()
            cr.set_source_rgba(*_rgba(METER_PEAK_COLOR))
            cr.rectangle(x - 1, 0, 2, h)
            cr.fill()
        return False


def spark_key(hist) -> tuple:
    """Neuzeichnen der Sparkline nur bei echter Änderung: Folge der unterschiedlichen Werte (gleiche Werte in Folge
    zählen einmal). Ein konstanter Wert ändert das Bild nicht → 0 GTK-Aufrufe; ein Ausreißer verschwindet, sobald
    er aus dem Fenster fällt."""
    out = []
    for x in hist:
        if not out or out[-1] != x:
            out.append(x)
    return tuple(out)


class Sparkline(Gtk.DrawingArea):
    """CPU-Verlauf der letzten Minuten (nur im Speicher, höchstens livestats.CPU_HISTORY_LEN Werte)."""

    def __init__(self, size=SPARK_SIZE):
        super().__init__()
        self.hist = ()
        self._key = None
        self.set_size_request(*size)
        self.connect("draw", self._draw)

    def set(self, hist) -> bool:
        hist = tuple(hist or ())[-livestats.CPU_HISTORY_LEN:]
        key = spark_key(hist)
        if key == self._key:
            return False
        self._key, self.hist = key, hist
        self.queue_draw()
        return True

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cr.set_source_rgba(*METER_TRACK)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        n = livestats.CPU_HISTORY_LEN
        pts = self.hist
        if not pts:
            return False
        step = w / max(1, n - 1)
        x0 = w - step * (len(pts) - 1)
        cr.set_source_rgba(*_rgba(theme.role("cpu_bar")))
        cr.set_line_width(1.5)
        for i, p in enumerate(pts):
            x, y = x0 + i * step, h - 1 - (h - 2) * max(0, min(p, 100)) / 100
            (cr.line_to if i else cr.move_to)(x, y)
        cr.stroke()
        return False


def screen_rect() -> tuple:
    """Nutzbarer Bildschirm (x, y, Breite, Höhe) als Umhüllende aller Monitore; Notwert 1920×1080."""
    d = Gdk.Display.get_default()
    rects = [d.get_monitor(i).get_geometry() for i in range(d.get_n_monitors())] if d is not None else []
    if not rects:
        return 0, 0, 1920, 1080
    x1, y1 = min(r.x for r in rects), min(r.y for r in rects)
    x2, y2 = max(r.x + r.width for r in rects), max(r.y + r.height for r in rects)
    return x1, y1, x2 - x1, y2 - y1


def fit_geometry(geo, area) -> tuple:
    """Gemerkte Monitor-Geometrie (dict width,height,x,y aus gui.json, schon auf plausible Werte geprüft) auf den
    Bildschirm begrenzen: Größe höchstens Bildschirm (mindestens MON_MIN_SIZE), Position ganz auf den Bildschirm
    geschoben; x/y None = Fenstermanager entscheidet. -> (Breite, Höhe, x, y)."""
    ax, ay, aw, ah = area
    w = min(max(geo["width"], MON_MIN_SIZE[0]), aw)
    h = min(max(geo["height"], MON_MIN_SIZE[1]), ah)
    x, y = geo.get("x"), geo.get("y")
    if x is None or y is None:
        return w, h, None, None
    return w, h, max(ax, min(x, ax + aw - w)), max(ay, min(y, ay + ah - h))


def short_line_markup(v, colors) -> str:
    """Kurzzeile im Hauptfenster (0.7.4): RAM-Ampel mit Symbol + Wort + Prozent, CPU %, Laufzeit – eine Zeile.
    Fehlende Werte → „n/a“, nie erfunden."""
    esc = GLib.markup_escape_text
    lvl = v.get("ram_level") if v else None
    if lvl:
        sym, word = T.RAM_LEVELS[lvl]
        ram = colored(T.SHORT_RAM.format(sym=sym, word=word.split(" –")[0], pct=v["ram_pct"],
                                         est=T.LIVE_EST if v.get("ram_est") else ""),
                      colors[RAM_LEVEL_COLOR[lvl]], bold=lvl in ("high", "full"))
    else:
        ram = esc(T.LIVE_NA)
    return T.SHORT_LINE.format(ram=ram, cpu=esc(cpu_text(v)), up=esc(livestats.fmt_runtime(v.get("runtime")) if v else T.LIVE_NA))


class MonitorWindow(Gtk.Window):
    """0.7.4: Fenster „Live Monitor“ – drei große Blöcke (RAM, CPU, Netz/Overlay/Laufzeit/…), frei skalierbar, Inhalt
    füllt das Fenster. Nur Darstellung: bekommt fertige Werte von MainWindow.update_details (kein eigener Zeitgeber,
    keine Lesezugriffe). Esc, X und CLOSE DETAILS schließen; Anfangsfokus auf CLOSE DETAILS. Setter nur bei Änderung
    (unveränderter Zyklus = 0 GTK-Aufrufe). VM beendet/nicht markiert → „VM stopped“ statt Werten."""

    def __init__(self, colors, geo, pin, on_close=None, on_pin=None):
        super().__init__(title=T.MON_TITLE)
        self.colors = colors
        self._on_close, self._on_pin = on_close, on_pin
        self._dismissed = False
        self.set_icon_name(ICON_NAME)
        self.set_size_request(*MON_MIN_SIZE)
        w, h, x, y = fit_geometry(geo, screen_rect()) if geo else (*MON_DEFAULT_SIZE, None, None)
        self.set_default_size(w, h)
        if x is not None:
            self.move(x, y)
        self.set_keep_above(bool(pin))
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=MARGIN)
        self.add(root)
        self.head = Gtk.Label(xalign=0.5, justify=Gtk.Justification.CENTER, ellipsize=Pango.EllipsizeMode.END,
                              single_line_mode=True, max_width_chars=1)
        self.head.get_style_context().add_class("evox-mon-head")
        root.pack_start(self.head, False, False, 0)
        self.stack = Gtk.Stack(homogeneous=True)
        root.pack_start(self.stack, True, True, 0)

        blocks = Gtk.Box(spacing=SPACING, homogeneous=True)       # Blöcke gleich breit, dehnen sich mit dem Fenster
        self.detail_blocks = []

        def block(title):
            b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING)
            ctx = b.get_style_context()
            ctx.add_class("evox-block")
            ctx.add_class("evox-mon-block")
            lbl = Gtk.Label(label=title, xalign=0)
            lbl.get_style_context().add_class("evox-block-title")
            b.pack_start(lbl, False, False, 0)
            blocks.pack_start(b, True, True, 0)
            self.detail_blocks.append(b)
            return b

        def style(widget, cls):
            widget.get_style_context().add_class(cls)
            return widget

        b = block(T.BLOCK_RAM)                                            # a) RAM
        self.ram_bar = MeterBar(zones=True, height=METER_HEIGHT_MON)
        self.ram_line = style(Gtk.Label(xalign=0, wrap=True), "evox-mon-num")
        self.ram_peak = style(Gtk.Label(xalign=0, wrap=True), "evox-block-small")
        self.ram_rec = style(Gtk.Label(xalign=0, wrap=True, no_show_all=True), "evox-block-small")   # Empfehlung
        b.pack_start(self.ram_bar, True, True, 0)
        b.pack_start(self.ram_line, False, False, 0)
        b.pack_start(self.ram_peak, False, False, 0)
        b.pack_start(self.ram_rec, False, False, 0)
        b = block(T.BLOCK_CPU)                                            # b) CPU
        self.cpu_bar = MeterBar(height=METER_HEIGHT_MON)
        self.cpu_line = style(Gtk.Label(xalign=0, wrap=True), "evox-mon-num")
        self.cpu_spark = Sparkline(SPARK_SIZE_MON)
        self.cpu_hist_lbl = style(Gtk.Label(label=T.CPU_HIST.format(min=livestats.CPU_HISTORY_LEN * LIVE_S // 60),
                                            xalign=0), "evox-block-small")
        b.pack_start(self.cpu_bar, True, True, 0)
        b.pack_start(self.cpu_line, False, False, 0)
        b.pack_start(self.cpu_spark, True, True, 0)
        b.pack_start(self.cpu_hist_lbl, False, False, 0)
        b = block(T.BLOCK_NET)                                            # c) Netz / Overlay / Laufzeit / …
        grid = Gtk.Grid(column_spacing=SPACING, row_spacing=SPACING, row_homogeneous=True, vexpand=True)
        self.net_vals = []
        for i, title in enumerate(T.NET_ROWS):
            v = Gtk.Label(xalign=0, wrap=True)
            if i < 2:                                                     # Verkehr, Overlay: groß
                style(v, "evox-mid")
            grid.attach(style(Gtk.Label(label=title, xalign=1), "evox-block-small"), 0, i, 1, 1)
            grid.attach(v, 1, i, 1, 1)
            self.net_vals.append(v)
        b.pack_start(grid, True, True, 0)
        blocks.set_tooltip_text(T.LIVE_TIP)
        self.stack.add_named(blocks, "live")

        stopped = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, valign=Gtk.Align.CENTER)
        self.stopped_lbl = style(Gtk.Label(justify=Gtk.Justification.CENTER), "evox-mon-stopped")
        self.stopped_sub = Gtk.Label(label=T.MON_STOPPED_SUB, wrap=True, justify=Gtk.Justification.CENTER)
        stopped.pack_start(self.stopped_lbl, False, False, 0)
        stopped.pack_start(self.stopped_sub, False, False, 0)
        self.stack.add_named(stopped, "stopped")

        bottom = Gtk.Box(spacing=SPACING)
        self.pin_chk = Gtk.CheckButton(label=T.MON_PIN, active=bool(pin), tooltip_text=T.MON_PIN_TIP)
        self.pin_chk.connect("toggled", self._toggled_pin)
        self.close_btn = fn_class(Gtk.Button(label=T.BTN_DETAILS_CLOSE, tooltip_text=T.DETAILS_TIP_CLOSE), "neutral")
        self.close_btn.get_style_context().add_class("evox-details-btn")
        self.close_btn.connect("clicked", lambda *_: self.dismiss())
        bottom.pack_start(self.pin_chk, False, False, 0)
        bottom.pack_end(self.close_btn, False, False, 0)
        root.pack_start(bottom, False, False, 0)
        self.focusline = Gtk.Label(label=T.STATUS_MON_DEFAULT, xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                   single_line_mode=True, max_width_chars=1)
        self.focusline.get_style_context().add_class("evox-focusline")
        root.pack_end(self.focusline, False, False, 0)

        self.status_texts = {self.close_btn: T.STATUS_MON_CLOSE, self.pin_chk: T.STATUS_MON_PIN}
        for wdg in self.status_texts:
            wdg.connect("enter-notify-event", self._on_hover, wdg)
            wdg.connect("leave-notify-event", self._on_hover, None)
        self.connect("set-focus", lambda _w, f: self._status(f))
        self.connect("key-press-event", self._on_key)
        self.connect("delete-event", self._on_delete)

    # ---- Bedienung
    def present_focused(self):
        """Anzeigen; Anfangsfokus auf CLOSE DETAILS (Enter direkt nach dem Öffnen schließt, löst nichts anderes aus)."""
        self.show_all()
        self.set_focus(self.close_btn)

    def _status(self, widget):
        set_text(self.focusline, self.status_texts.get(widget, T.STATUS_MON_DEFAULT))

    def _on_hover(self, _w, _event, target):
        self._status(target if target is not None else self.get_focus())
        return False

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.dismiss()
            return True
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.set_focus_visible(True)
        return False

    def _toggled_pin(self, chk):
        self.set_keep_above(chk.get_active())
        if self._on_pin:
            self._on_pin(chk.get_active())

    def geometry(self) -> dict:
        """Größe und Position (Position nur, wenn das Fenster sichtbar war: sonst ist sie nicht aussagekräftig)."""
        w, h = self.get_size()
        x, y = self.get_position() if self.get_mapped() else (None, None)
        return {"width": w, "height": h, "x": x, "y": y}

    def dismiss(self):
        """X, Esc und CLOSE DETAILS: Geometrie melden, dann zerstören (sofort, auch ohne laufende Hauptschleife)."""
        if self._dismissed:
            return
        self._dismissed = True
        if self._on_close:
            self._on_close(self.geometry() if self.get_mapped() else None)
        self.destroy()

    def _on_delete(self, *_):
        self.dismiss()
        return True

    # ---- Anzeige
    def update(self, name, t, v, starts, hint=None):
        """name = beobachtete VM (None = keine), t = Zeilendaten (None = nicht mehr vorhanden), v = Live-Werte,
        hint = RAM-Empfehlung (Text) aus echten Gastwerten oder None."""
        head = T.MON_HEAD.format(name=name) if name else T.MON_TITLE
        set_text(self.head, head)
        if self.get_title() != head:
            self.set_title(head)
        if t is None or t.get("state") != "running":
            set_text(self.stopped_lbl, T.MON_STOPPED if name else T.MON_NO_VM)
            if self.stack.get_visible_child_name() != "stopped":
                self.stack.set_visible_child_name("stopped")
            return
        if self.stack.get_visible_child_name() != "live":
            self.stack.set_visible_child_name("live")
        line1, line2, lvl = ram_block_texts(v)                          # a) RAM: Balken mit Zonen, Peak-Marke, Ampel
        color = self.colors[RAM_LEVEL_COLOR[lvl]] if lvl else None
        self.ram_bar.colors = self.colors
        self.ram_bar.set(v.get("ram_pct") if lvl else None, v.get("peak_pct") if lvl else None, color)
        if lvl:
            set_markup(self.ram_line, colored(line1, color, bold=lvl in ("high", "full")))
        else:
            set_text(self.ram_line, line1)
        set_text(self.ram_peak, line2)
        set_shown(self.ram_peak, bool(line2))
        set_text(self.ram_rec, hint or "")                              # Empfehlung nur mit echten Gastwerten
        set_shown(self.ram_rec, bool(hint))
        cpu = v.get("cpu_pct") if v else None                           # b) CPU: Balken + Sparkline
        self.cpu_bar.set(cpu)
        set_text(self.cpu_line, T.CPU_LINE.format(pct=cpu, n=t.get("vcpus") or "?") if cpu is not None else cpu_text(v))
        self.cpu_spark.set(v.get("cpu_hist") if v else ())
        for lbl, text in zip(self.net_vals, net_block_texts(v, t, starts)):   # c) Netz / Overlay / …
            set_text(lbl, text)
        set_tooltip(self.net_vals[1], T.DETAIL_TIP_OVERLAY.format(file=t["overlay"],
                                                                  started=fmt_datetime(t["created"], seconds=True)))


def max_vcpus(ev) -> int:
    return min(config.MAX_VCPUS, ev.host_cpus())


def ram_limits_gib(meminfo: dict, reserve_mib: int) -> tuple:
    """(min, max) für die RAM-Eingabe in GiB; 0.7.3: max auf das 256-MiB-Raster (0,25 GB) abgerundet und
    ≤ config.MAX_MEMORY_MIB (0.7.2: 0,5 GiB)."""
    lo = config.MIN_MEMORY_MIB / 1024
    hi = livestats.grid_floor_mib(min(config.MAX_MEMORY_MIB, capacity.max_vm_mib(meminfo, reserve_mib))) / 1024
    return lo, max(lo, hi)


def next_free_name(ev, purpose: str) -> str:
    """Name, den Evox.start jetzt vergeben würde (nur lesend: bestehende Namensfunktion der Lifecycle).

    Wirft EvoxError bei ungültigem Zweck oder wenn alle Nummern belegt sind."""
    return ev._next_name(purpose_name(purpose))


def split_vm_name(name: str) -> tuple:
    """(Hauptteil, Nummer) für die Anzeige: 'DISPOSABLE-MAIL-01' → ('DISPOSABLE-MAIL', '-01'). Name bleibt = Summe."""
    m = re.match(r"^(.*?)(-\d+)$", name)
    return (m.group(1), m.group(2)) if m else (name, "")


class StartDialog(Gtk.Dialog):
    """RAM, CPUs und Zweck wählen; vorbelegt mit den zuletzt benutzten Werten; Eingaben auf die Maxima begrenzt.

    Fest: Kopfleiste (Modus + ← BACK) oben, Knopfzeile (← BACK, Start) unten; dazwischen scrollt der Inhalt."""

    def __init__(self, parent, ev, template, offline=False):
        super().__init__(title=T.DLG_TITLE, transient_for=parent, modal=True)
        self.ev = ev
        self.offline = offline
        last = ev.s.load_last_start()
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        self.ok_btn = self.add_button(T.DLG_START, Gtk.ResponseType.OK)
        self.ok_btn.get_style_context().add_class("evox-start-offline" if offline else "evox-start-disposable")
        # Kopfleiste ganz oben: Symbol + Text des Modus (nie nur Farbe), Erklärsatz, ← BACK rechts
        icon, title, expl = T.DLG_MODE["none" if offline else "net"]
        self.mode_bar = Gtk.EventBox()
        self.mode_bar.get_style_context().add_class("evox-bar-offline" if offline else "evox-bar-internet")
        self.mode_icon = Gtk.Label(label=icon)
        self.mode_icon.get_style_context().add_class("evox-bar-icon")
        self.mode_lbl = Gtk.Label(label=title, xalign=0)
        self.mode_lbl.get_style_context().add_class("evox-bar-text")
        self.mode_expl = Gtk.Label(label=expl, xalign=0, wrap=True, max_width_chars=48)
        self.mode_expl.get_style_context().add_class("evox-bar-expl")
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        txt.pack_start(self.mode_lbl, False, False, 0)
        txt.pack_start(self.mode_expl, False, False, 0)
        self.back_top = back_button(self)
        bar = Gtk.Box(spacing=SPACING * 2, margin=SPACING)
        bar.pack_start(self.mode_icon, False, False, 0)
        bar.pack_start(txt, True, True, 0)
        bar.pack_end(self.back_top, False, False, 0)
        self.mode_bar.add(bar)
        self.get_content_area().pack_start(self.mode_bar, False, False, 0)
        self.get_content_area().get_style_context().add_class("evox-dlg-offline" if offline else "evox-dlg-internet")
        # scrollbarer Inhalt
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING // 2, margin=SPACING)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=100)
        self.scroller.add(body)
        self.get_content_area().pack_start(self.scroller, True, True, 0)
        grid = Gtk.Grid(column_spacing=SPACING, row_spacing=SPACING)
        body.pack_start(grid, False, False, 0)

        self.purpose = Gtk.ComboBoxText.new_with_entry()
        self.purpose_list = purposes.load(ev.s)
        for p in self.purpose_list:
            self.purpose.append_text(p)
        self.purpose.get_child().set_text(last["purpose"])
        self.purpose.get_child().set_activates_default(False)      # Enter im Namensfeld startet nichts (0.6.15)
        self.name_main, self.name_num = "", ""
        self.vm_name = None          # angezeigter und beim Start erwarteter Name (None bei Fehler)
        self.name_lbl = Gtk.Label(xalign=0, wrap=True, selectable=False)
        self.name_lbl.get_style_context().add_class("evox-vmname")
        try:
            lo, hi = ram_limits_gib(ev.meminfo(), ev.s.host_reserve_mib)
        except (OSError, KeyError):
            lo = hi = config.MIN_MEMORY_MIB / 1024
        # 0.7.3: Raster 0,25 GB (256 MiB) ab 1 GB, Anzeige „1,25“ + „GB“ daneben; Eingabe wird auf das Raster gesetzt
        self.ram = Gtk.SpinButton.new_with_range(lo, hi, config.RAM_STEP_MIB / 1024)
        self.ram.set_digits(2)
        self.ram.set_snap_to_ticks(True)
        self.ram.set_width_chars(6)
        self.ram.set_tooltip_text(T.DLG_RAM_TIP)
        self.ram_unit = Gtk.Label(label=T.DLG_RAM_UNIT)
        self.ram.set_value(min(last["memory_mib"] / 1024, hi))
        self.cpus = Gtk.SpinButton.new_with_range(1, max_vcpus(ev), 1)
        self.cpus.set_value(min(last["vcpus"], max_vcpus(ev)))
        self.host_lbl = Gtk.Label(xalign=0, wrap=True)
        self.host_lbl.get_style_context().add_class("evox-subline")
        self.cap_lbl = Gtk.Label(xalign=0, wrap=True)

        rows = T.DLG_ROWS            # Template, Purpose, Name, RAM, CPUs, Host, Capacity
        res = Gtk.Box(spacing=SPACING)           # RAM und CPUs in einer Zeile
        res.pack_start(self.ram, False, False, 0)
        res.pack_start(self.ram_unit, False, False, 0)
        res.pack_start(Gtk.Label(label=rows[4], xalign=1, margin_start=MARGIN), False, False, 0)
        res.pack_start(self.cpus, False, False, 0)
        # 0.7.0 "Remember for purpose": Opt-in, standardmäßig aus; nur RAM (nie Modus/Netzsperre)
        self.remembered = ev.s.load_remembered_ram()
        self.remember_chk = Gtk.CheckButton(label=T.DLG_REMEMBER_ANY, tooltip_text=T.DLG_REMEMBER_TIP)
        res.pack_start(self.remember_chk, False, False, MARGIN)
        # 0.7.1 Zweck-Statistik: dezente Info unter der RAM-Zeile; ändert die Auswahl nicht
        try:
            self.purpose_stats = ev.s.load_purpose_stats()
        except Exception:  # noqa: BLE001 – nur Hinweis
            self.purpose_stats = {}
        self.peak_lbl = Gtk.Label(xalign=0, no_show_all=True, wrap=True, max_width_chars=60)
        self.peak_lbl.get_style_context().add_class("evox-subline")
        ram_cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ram_cell.pack_start(res, False, False, 0)
        ram_cell.pack_start(self.peak_lbl, False, False, 0)
        self._rem_key = object()             # noch kein Zweck ausgewertet
        self.on_purpose_changed()
        cells = ((rows[0], Gtk.Label(label=template, xalign=0)), (rows[1], self.purpose), (rows[2], self.name_lbl),
                 (rows[3], ram_cell), (rows[5], self.host_lbl), (rows[6], self.cap_lbl))
        for i, (title, w) in enumerate(cells):
            grid.attach(Gtk.Label(label=title, xalign=1, yalign=0 if i >= 4 else 0.5), 0, i, 1, 1)
            w.set_hexpand(True)
            if isinstance(w, Gtk.Box):
                w.set_hexpand(False)
            grid.attach(w, 1, i, 1, 1)
        self.purpose.connect("changed", lambda *_: self.on_purpose_changed())
        for w, sig in ((self.purpose, "changed"), (self.ram, "value-changed"), (self.cpus, "value-changed")):
            w.connect(sig, lambda *_: self.update())
        # Quick purpose: Gruppen mit farbiger Überschrift; Chips füllen nur das Feld vor
        qp_head = Gtk.Box(spacing=SPACING)
        qp_title = Gtk.Label(label=T.QP_TITLE, xalign=0)
        qp_title.set_markup(f"<b>{GLib.markup_escape_text(T.QP_TITLE)}</b>")
        self.edit_btn = fn_class(Gtk.Button(label=T.QP_EDIT), "aux")
        self.edit_btn.connect("clicked", lambda *_: self.on_edit_list())
        qp_head.pack_start(qp_title, False, False, 0)
        qp_head.pack_start(self.edit_btn, False, False, 0)
        body.pack_start(qp_head, False, False, 0)
        self.chips_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.pack_start(self.chips_box, False, False, 0)
        self.fill_chips()
        self.update()
        fit_dialog(self, parent, START_SIZE)
        self.show_all()
        secure_dialog(self)

    def fill_chips(self):
        """Chips nach Gruppen neu aufbauen: Überschrift und Chips tragen die Farbe ihrer Gruppe."""
        for c in self.chips_box.get_children():
            self.chips_box.remove(c)
        self.chips = {}
        self.group_labels = {}
        grid = Gtk.Grid(column_spacing=MARGIN, row_spacing=SPACING // 2, column_homogeneous=True)
        pos = 0
        more_col = None
        for key, names in purposes.grouped(self.purpose_list):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            head = Gtk.Label(label=T.QP_GROUPS[key], xalign=0, halign=Gtk.Align.START)
            head.get_style_context().add_class("evox-grp")
            head.get_style_context().add_class(f"evox-grp-{key}")
            self.group_labels[key] = head
            col.pack_start(head, False, False, 0)
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False, column_spacing=3,
                               row_spacing=3, max_children_per_line=6, min_children_per_line=1)
            for p in names:
                b = Gtk.Button(label=p, tooltip_text=T.QP_TIP)
                b.get_style_context().add_class("evox-chip")
                b.get_style_context().add_class(f"evox-chip-{key}")
                b.connect("clicked", lambda _b, name=p: self.pick_purpose(name))
                self.chips[p] = b
                flow.add(b)
            col.pack_start(flow, False, False, 0)
            if key == "mylist" and "more" in self.group_labels:     # eigene Zwecke: unter MORE (spart Höhe)
                more_col.pack_start(col, False, False, 2)
            else:
                grid.attach(col, pos % 2, pos // 2, 1, 1)
                pos += 1
                if key == "more":
                    more_col = col
        self.chips_box.pack_start(grid, False, False, 0)
        self.chips_box.show_all()

    def pick_purpose(self, name):
        """Chip-Klick: nur das Zweckfeld füllen (OTHER: nur fokussieren). Startet nichts, ändert den Modus nicht."""
        entry = self.purpose.get_child()
        if name == T.QP_OTHER:
            entry.grab_focus()
            entry.select_region(0, -1)
        else:
            entry.set_text(name)
            entry.grab_focus()
            entry.set_position(-1)
        self.update()                       # Name auch bei unverändertem Text neu berechnen

    def on_edit_list(self):
        d = PurposeEditDialog(self, self.ev.s, self.purpose_list)
        resp = d.run()
        new = d.items if resp == Gtk.ResponseType.OK else None
        d.destroy()
        if new is not None:
            self.set_purpose_list(new)

    def set_purpose_list(self, items):
        self.purpose_list = list(items)
        self.purpose.remove_all()
        for p in self.purpose_list:
            self.purpose.append_text(p)
        self.fill_chips()

    def purpose_key(self):
        """Zweck nach der Namensregel (EMAIL …) oder None, wenn ungültig."""
        try:
            return purpose_name(self.purpose_text)
        except EvoxError:
            return None

    def on_purpose_changed(self):
        """Neuer Zweck: Haken zeigt, ob für ihn RAM gemerkt ist; gemerkter Wert wird vorgeschlagen,
        begrenzt auf den erlaubten Bereich der RAM-Eingabe (Kapazität). Ungültige Werte wurden schon beim Lesen verworfen."""
        key = self.purpose_key()
        if key == self._rem_key:
            return
        self._rem_key = key
        self.remember_chk.set_label(T.DLG_REMEMBER.format(purpose=key) if key else T.DLG_REMEMBER_ANY)
        self.remember_chk.set_sensitive(key is not None)
        mib = self.remembered.get(key) if key else None
        self.remember_chk.set_active(mib is not None)
        peak = self.purpose_stats.get(key, {}).get("peak_mib") if key else None
        self.peak_lbl.set_visible(bool(peak))
        if mib is not None:                         # schon auf dem Raster (config.snap_ram_mib), Kapazität begrenzt
            lo, hi = self.ram.get_range()
            self.ram.set_value(max(lo, min(mib / 1024, hi)))
        self._show_recommend()

    @staticmethod
    def _grid_mib(gib_value) -> int:
        step = config.RAM_STEP_MIB
        return max(config.MIN_MEMORY_MIB, int(round(gib_value * 1024 / step)) * step)

    def _show_recommend(self):
        """0.7.3: Info unter der RAM-Zeile: bisherige Spitze des Zwecks + Empfehlung (Spitze + 25 %, Raster, mind.
        1 GB, höchstens erlaubtes Maximum). Spitze > 85 % der gewählten Größe → „mehr RAM wählen“. Ändert nichts."""
        key = self.purpose_key()
        peak = self.purpose_stats.get(key, {}).get("peak_mib") if key else None
        if not peak:
            return
        hi_mib = int(round(self.ram.get_range()[1] * 1024))
        peak_b = peak * 2**20
        text = T.DLG_PURPOSE_PEAK.format(purpose=key, peak=fmt_gb(peak_b))
        if livestats.needs_more(peak_b, self.memory_mib * 2**20):
            sug = livestats.more_mib(peak_b, self.memory_mib, hi_mib)
            text += " " + T.DLG_RECOMMEND_MORE.format(sug=livestats.fmt_ram_gb(sug))
        else:
            text += " " + T.DLG_RECOMMEND.format(sug=livestats.fmt_ram_gb(livestats.suggest_mib(peak_b, hi_mib)))
        if self.peak_lbl.get_text() != text:
            self.peak_lbl.set_text(text)

    @property
    def remember(self) -> bool:
        return self.remember_chk.get_active() and self.remember_chk.get_sensitive()

    @property
    def memory_mib(self) -> int:
        return self._grid_mib(self.ram.get_value())          # 0.7.3: immer ein Vielfaches von 256 MiB

    @property
    def vcpus(self) -> int:
        return self.cpus.get_value_as_int()

    @property
    def purpose_text(self) -> str:
        return self.purpose.get_child().get_text()

    def update(self):
        ok = True
        self._show_recommend()
        try:
            self.vm_name = next_free_name(self.ev, self.purpose_text)    # live bei jeder Änderung
            self._show_name(self.vm_name)
            self._name_style(False)
        except EvoxError as e:
            self.vm_name = None
            self.name_lbl.set_text(str(e))
            self._name_style(True)
            ok = False
        except Exception:  # noqa: BLE001 – Registry/libvirt nicht lesbar: nicht starten
            self.vm_name = None
            self.name_lbl.set_text(T.DLG_NAME_UNKNOWN)
            self._name_style(True)
            ok = False
        try:
            cap = capacity.assess(self.ev.meminfo(), self.memory_mib, self.ev.s.host_reserve_mib)
            self.host_lbl.set_text(T.DLG_HOST.format(
                total=gib(cap.total_mib), avail=gib(cap.avail_mib), reserve=gib(cap.reserve_mib),
                maxvms=gib(cap.max_for_vms_mib), room=T.CAP_ROOM.format(n=cap.fits, size=livestats.fmt_ram_gb(self.memory_mib)),
                cpus=max_vcpus(self.ev), config=config.Settings.config_path()))
            self.cap_lbl.set_text(T.DLG_CAP[cap.level].format(left=gib(cap.left_after_mib),
                                                              reserve=gib(cap.reserve_mib)))
            ok = ok and cap.level != "red"
        except (OSError, KeyError):
            self.host_lbl.set_text("")
            self.cap_lbl.set_text(T.DLG_MEM_UNKNOWN)
            ok = False
        self.ok_btn.set_sensitive(ok)
        return ok

    def _show_name(self, name: str):
        """Name groß; die Nummer (-01 …) klein und gedämpft dahinter. Nur Darstellung: get_text() = echter Name."""
        self.name_main, self.name_num = split_vm_name(name)
        mk = GLib.markup_escape_text(self.name_main)
        if self.name_num:
            mk += f'<span size="xx-small" weight="normal" alpha="65%">{GLib.markup_escape_text(self.name_num)}</span>'
        self.name_lbl.set_markup(mk)

    def _name_style(self, error: bool):
        """VM-Name groß und fett; eine Fehlermeldung statt des Namens normal groß und rot."""
        ctx = self.name_lbl.get_style_context()
        (ctx.remove_class if error else ctx.add_class)("evox-vmname")
        (ctx.add_class if error else ctx.remove_class)("evox-warn")


class PurposeEditDialog(Gtk.Dialog):
    """Zweckliste bearbeiten: hinzufügen (neu = ganz oben), entfernen, umsortieren, Standardliste;
    speichert atomar in config.json. Kopfleiste und Knopfzeile mit ← BACK bleiben fest sichtbar."""

    def __init__(self, parent, settings, items):
        super().__init__(title=T.QP_EDIT_TITLE, transient_for=parent, modal=True)
        self.settings = settings
        self.items = list(items)
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        self.save_btn = Gtk.Button(label=T.QP_EDIT_OK)      # ohne eigene Antwort: erst speichern, dann OK
        self.save_btn.get_style_context().add_class("evox-start-internet")      # grün = speichern
        self.save_btn.connect("clicked", lambda *_: self.on_save())
        self.get_action_area().pack_end(self.save_btn, False, False, 0)
        box = self.get_content_area()
        box.set_spacing(SPACING)
        self.back_top = back_button(self)
        head = Gtk.Box(spacing=SPACING, margin=SPACING)
        title = Gtk.Label(label=T.QP_EDIT_TITLE, xalign=0)
        title.set_markup(f"<b>{GLib.markup_escape_text(T.QP_EDIT_TITLE)}</b>")
        head.pack_start(title, True, True, 0)
        head.pack_end(self.back_top, False, False, 0)
        self.head_bar = head
        box.pack_start(head, False, False, 0)
        self.store = Gtk.ListStore(str)
        self.view = Gtk.TreeView(model=self.store, headers_visible=False)
        self.view.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0))
        sc = Gtk.ScrolledWindow(min_content_height=100, min_content_width=240)
        sc.add(self.view)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING)
        # Farben nach Funktion (vorhandene Klassen): blau = verschieben, rot = entfernen, gold = Standard, türkis = neu
        self.up_btn = Gtk.Button(label=T.QP_EDIT_UP)
        self.down_btn = Gtk.Button(label=T.QP_EDIT_DOWN)
        self.remove_btn = Gtk.Button(label=T.QP_EDIT_REMOVE)
        self.reset_btn = Gtk.Button(label=T.QP_EDIT_RESET)
        for b, cls in ((self.up_btn, "evox-offline"), (self.down_btn, "evox-offline"),
                       (self.remove_btn, "evox-danger"), (self.reset_btn, "evox-vault-btn")):
            b.get_style_context().add_class(cls)
        self.up_btn.connect("clicked", lambda *_: self.move(-1))
        self.down_btn.connect("clicked", lambda *_: self.move(1))
        self.remove_btn.connect("clicked", lambda *_: self.remove())
        self.reset_btn.connect("clicked", lambda *_: self.reset())
        for b in (self.up_btn, self.down_btn, self.remove_btn, self.reset_btn):
            side.pack_start(b, False, False, 0)
        row = Gtk.Box(spacing=SPACING, margin_start=MARGIN, margin_end=MARGIN)
        row.pack_start(list_frame(sc, self.view, "green"), True, True, 0)
        row.pack_start(side, False, False, 0)
        box.pack_start(row, True, True, 0)
        self.entry = Gtk.Entry(max_length=purposes.MAX_LEN, activates_default=False)
        self.entry.connect("changed", self._upper)
        self.entry.connect("activate", lambda *_: self.add(self.entry.get_text()))
        self.add_btn = Gtk.Button(label=T.QP_EDIT_ADD)
        self.add_btn.get_style_context().add_class("evox-import-btn")
        self.add_btn.connect("clicked", lambda *_: self.add(self.entry.get_text()))
        add_row = Gtk.Box(spacing=SPACING, margin_start=MARGIN, margin_end=MARGIN)
        add_row.pack_start(Gtk.Label(label=T.QP_EDIT_NEW), False, False, 0)
        add_row.pack_start(self.entry, True, True, 0)
        add_row.pack_start(self.add_btn, False, False, 0)
        box.pack_start(add_row, False, False, 0)
        self.msg = Gtk.Label(xalign=0, wrap=True, margin_start=MARGIN, margin_end=MARGIN)
        box.pack_start(self.msg, False, False, 0)
        self.refresh()
        fit_dialog(self, parent, EDIT_SIZE)
        self.show_all()
        secure_dialog(self)

    def _upper(self, entry):
        t = entry.get_text()
        if t != t.upper():                 # einzige stille Änderung: Großschreibung
            entry.set_text(t.upper())

    def refresh(self, select=None):
        self.store.clear()
        for p in self.items:
            self.store.append([p])
        if select is not None and 0 <= select < len(self.items):
            path = Gtk.TreePath(select)
            self.view.get_selection().select_path(path)
            self.view.scroll_to_cell(path, None, False, 0, 0)       # markiert und sichtbar

    def selected_index(self):
        _m, it = self.view.get_selection().get_selected()
        return self.store.get_path(it).get_indices()[0] if it else None

    def error(self, text):
        self.msg.set_text(text)
        self.msg.get_style_context().add_class("evox-warn")

    def add(self, raw) -> bool:
        """Neuen Zweck prüfen und ganz oben einfügen; bei Fehler Meldung zeigen, nichts ändern."""
        try:
            p = purposes.check_purpose(raw, self.items)
        except EvoxError as e:
            self.error(str(e))
            return False
        self.items.insert(0, p)
        self.entry.set_text("")
        self.msg.set_text("")
        self.msg.get_style_context().remove_class("evox-warn")
        self.refresh(0)
        return True

    def remove(self):
        i = self.selected_index()
        if i is not None:
            del self.items[i]
            self.refresh(min(i, len(self.items) - 1))

    def move(self, delta):
        i = self.selected_index()
        if i is None or not 0 <= i + delta < len(self.items):
            return
        self.items[i], self.items[i + delta] = self.items[i + delta], self.items[i]
        self.refresh(i + delta)

    def reset(self):
        self.items = list(purposes.DEFAULT_PURPOSES)
        self.refresh()

    def on_save(self):
        try:
            purposes.save(self.settings, self.items)
        except (EvoxError, OSError) as e:
            self.error(T.QP_EDIT_SAVE_ERROR.format(err=e))
            return
        self.response(Gtk.ResponseType.OK)


class ImportDialog(Gtk.Dialog):
    """Liste der Domains TEMPLATE-* (nur lesend aus libvirt); nicht importierbare ausgegraut mit Grund.

    Keine Zeile vorausgewählt; Import erst nach bewusster Auswahl (Fokus startet auf Cancel,
    Enter = Cancel). *-BACKUP in roter Schrift."""

    def __init__(self, parent, ev):
        super().__init__(title=T.IMP_TITLE, transient_for=parent, modal=True)
        self.set_default_size(660, 320)
        cancel = self.add_button(T.DLG_CANCEL, Gtk.ResponseType.CANCEL)
        cancel.get_style_context().add_class("evox-cancel")
        self.ok_btn = self.add_button(T.IMP_BTN, Gtk.ResponseType.OK)
        self.ok_btn.get_style_context().add_class("evox-import-btn")
        self.ok_btn.set_sensitive(False)
        self.set_default_response(Gtk.ResponseType.CANCEL)
        red = theme_colors(self)["bad"]
        area = self.get_content_area()
        area.set_spacing(SPACING)
        area.set_border_width(MARGIN)
        area.pack_start(Gtk.Label(label=T.IMP_HINT, xalign=0, wrap=True), False, False, 0)
        self.candidates = {c["name"]: c for c in ev.template_candidates()}
        # Spalten: Name, Zustand, Größe, Hinweis, wählbar, Schriftfarbe (None = Theme)
        self.store = Gtk.ListStore(str, str, str, str, bool, str)
        for c in self.candidates.values():
            size = fmt_size(c["size"])
            self.store.append([c["name"], c["state"], size, c["problem"] or T.IMP_OK, not c["problem"],
                               red if c["backup"] else None])
        self.view = Gtk.TreeView(model=self.store)
        for i, title in enumerate(T.IMP_COLUMNS):
            self.view.append_column(sel_fg_column(self.view, title, i, 5, "teal", sens_i=4))
        sel = self.view.get_selection()
        sel.set_select_function(lambda _s, model, path, _cur: model[path][4])
        self.ev = ev
        self.space = Gtk.Label(xalign=0, wrap=True)
        self.space_msg = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
        sel.connect("changed", lambda *_: self.update())
        sw = Gtk.ScrolledWindow(vexpand=True, shadow_type=Gtk.ShadowType.IN)
        sw.add(self.view)
        area.pack_start(list_frame(sw, self.view, "teal"), True, True, 0)
        area.pack_start(Gtk.Label(label=T.IMP_NONE if not self.candidates else T.IMP_SELECT, xalign=0),
                        False, False, 0)
        area.pack_start(self.space, False, False, 0)
        area.pack_start(self.space_msg, False, False, 0)
        self.show_all()
        sel.unselect_all()
        secure_dialog(self)       # Fokus auf Cancel: sonst wählt die Liste beim Fokus die erste Zeile selbst aus

    def selected(self):
        model, it = self.view.get_selection().get_selected()
        return self.candidates[model[it][0]] if it and model[it][4] else None

    def chosen(self) -> list:
        """Alle gewählten, importierbaren Zeilen (die Liste erlaubt heute eine; Summe gilt für jede Anzahl)."""
        model, paths = self.view.get_selection().get_selected_rows()
        return [self.candidates[model[p][0]] for p in paths if model[p][4]]

    def update(self) -> bool:
        """Platzzeile für die Auswahl (Summe) aktualisieren; Import-Knopf nur bei Auswahl und genug Platz."""
        chosen = self.chosen()
        ok = bool(chosen)
        self.space.set_text("")
        self.space_msg.set_text("")
        if chosen:
            unknown = [c["name"] for c in chosen if c["size"] is None]
            need = sum(lifecycle.space_needed(c["size"] or 0, c["alloc"] or 0) for c in chosen)
            try:
                sp = self.ev.template_space(need)
            except Exception:  # noqa: BLE001 – Pool nicht lesbar: nicht blockieren wie bisher
                sp = None
            if sp is not None:
                show_space(self.space, self.space_msg, sp, theme_colors(self)["bad"])
                ok = sp["ok"] or bool(unknown)
            if unknown:
                self.space_msg.set_text(T.IMP_SPACE_UNKNOWN.format(names=", ".join(unknown)))
        self.ok_btn.set_sensitive(ok)
        return ok


def confirm_import(parent, c) -> bool:
    """Bestätigung mit Name und Größe; bei -BACKUP zusätzliche Warnung."""
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.WARNING if c["backup"] else Gtk.MessageType.QUESTION,
                          buttons=Gtk.ButtonsType.OK_CANCEL, text=T.IMP_CONFIRM_TITLE.format(name=c["name"]))
    d.format_secondary_text(confirm_import_text(c))
    style_responses(d, Gtk.ResponseType.OK, "evox-import-btn", Gtk.ResponseType.CANCEL)
    secure_dialog(d)
    resp = d.run()
    d.destroy()
    return resp == Gtk.ResponseType.OK


def confirm_import_text(c) -> str:
    size = fmt_size(c["size"])
    alloc = fmt_size(c["alloc"])
    return T.IMP_CONFIRM_TEXT.format(size=size, alloc=alloc, name=c["name"]) + (
        T.IMP_BACKUP_WARN if c["backup"] else "")


fmt_size = livestats.fmt_bytes_gb1


def fmt_ram(mib) -> str:
    """RAM-Größe einer VM in Listen: wie Kapazität und Platz „4,0 GB“ (0.7.4 einheitlich, nicht GiB)."""
    return "?" if mib is None else livestats.fmt_gb1(mib)


def show_space(label, msg, sp, bad_color):
    """Platzzeile „Needed X, free Y (after reserve Z)“ + bei Platzmangel Grund in Gefahrfarbe.
    Gemeinsam für Make template und Import template; sp = Evox.template_space()."""
    label.set_text(T.MK_SPACE.format(need=fmt_size(sp["need"]), free=fmt_size(sp["free"]),
                                     after=fmt_size(max(0, sp["after"]))))
    if sp["ok"]:
        msg.set_text("")
    else:
        msg.set_markup(colored(T.MK_SPACE_LOW.format(reserve=fmt_size(sp["reserve"])), bad_color))


class RemoveDialog(Gtk.Dialog):
    """Bestätigung für alle markierten Kopien: Name(n) fett in Neongrün, Version, Größe, Gesamtgröße."""

    def __init__(self, parent, rows):
        super().__init__(title=T.RM_TITLE, transient_for=parent, modal=True)
        self.add_button(T.DLG_CANCEL, Gtk.ResponseType.CANCEL).get_style_context().add_class("evox-cancel")
        self.ok_btn = self.add_button(T.RM_BTN, Gtk.ResponseType.OK)
        self.ok_btn.get_style_context().add_class("destructive-action")
        fn_class(self.ok_btn, "remove")
        self.set_default_response(Gtk.ResponseType.CANCEL)
        self.rows = rows
        area = self.get_content_area()
        area.set_spacing(SPACING)
        area.set_border_width(MARGIN)
        known = [r["size"] for r in rows if r["size"] is not None]
        total = fmt_size(sum(known) if known else None)
        esc = GLib.markup_escape_text
        self.text = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
        if len(rows) == 1:
            r = rows[0]
            self.text.set_markup(T.RM_TEXT.format(
                name=f'<span foreground="{theme.role("name")}"><b>{esc(r["name"])}</b></span>',
                version=r["version"], size=fmt_size(r["size"])))
        else:
            lines = "\n".join(
                f'<span foreground="{theme.role("name")}"><b>{esc(r["name"])}</b></span>  v{r["version"]}  '
                f'({fmt_size(r["size"])})' for r in rows)
            self.text.set_markup(T.RM_TEXT_MANY.format(n=len(rows), list=lines, total=total))
        area.pack_start(self.text, False, False, 0)
        in_use = sum(r["in_use"] for r in rows)
        if in_use:
            area.pack_start(Gtk.Label(label=T.RM_IN_USE.format(n=in_use), xalign=0, wrap=True),
                            False, False, 0)
        self.show_all()
        secure_dialog(self)


class MakeTemplateDialog(Gtk.Dialog):
    """Warnung mit Bestätigungshaken, Name (Vorschlag änderbar), Platzanzeige; OK nur wenn alles passt."""

    def __init__(self, parent, ev, plan):
        super().__init__(title=T.MK_TITLE.format(vault=plan["vault"]), transient_for=parent, modal=True)
        self.ev = ev
        self.plan = plan
        cancel = self.add_button(T.DLG_CANCEL, Gtk.ResponseType.CANCEL)
        cancel.get_style_context().add_class("evox-cancel")
        self.ok_btn = self.add_button(T.MK_BTN, Gtk.ResponseType.OK)
        self.ok_btn.get_style_context().add_class("suggested-action")
        fn_class(self.ok_btn, "make")
        self.set_default_response(Gtk.ResponseType.CANCEL)
        area = self.get_content_area()
        area.set_spacing(SPACING)
        area.set_border_width(MARGIN)
        self.warn = Gtk.Label(label=T.MK_WARN, xalign=0, wrap=True, max_width_chars=60)
        self.warn.get_style_context().add_class("evox-warn")
        self.confirm = Gtk.CheckButton(label=T.MK_CONFIRM)
        d = plan["disk"]
        self.source = Gtk.Label(label=T.MK_SOURCE.format(vault=plan["vault"], size=fmt_size(d["capacity"]),
                                                         fmt=d["format"], alloc=fmt_size(d["allocation"])),
                                xalign=0, wrap=True, max_width_chars=60)
        self.name = Gtk.Entry(text=plan["suggested"], activates_default=False, width_chars=40)
        self.name_msg = Gtk.Label(xalign=0, wrap=True)
        sp = plan["space"]
        self.space = Gtk.Label(xalign=0, wrap=True)
        self.space_msg = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        show_space(self.space, self.space_msg, sp, theme_colors(self)["bad"])
        row = Gtk.Box(spacing=SPACING)
        row.pack_start(Gtk.Label(label=T.MK_NAME), False, False, 0)
        row.pack_start(self.name, True, True, 0)
        for w in (self.warn, self.confirm, self.source, row, self.name_msg, self.space, self.space_msg):
            area.pack_start(w, False, False, 0)
        self.confirm.connect("toggled", lambda *_: self.update())
        self.name.connect("changed", lambda *_: self.update())
        self.update()
        self.show_all()
        secure_dialog(self)

    @property
    def name_text(self) -> str:
        return self.name.get_text().strip()

    def update(self) -> bool:
        try:
            self.ev.check_new_name(self.name_text)
            self.name_msg.set_text(T.MK_NAME_OK)
            name_ok = True
        except EvoxError as e:
            self.name_msg.set_markup(colored(str(e), theme_colors(self)["bad"]))
            name_ok = False
        ok = name_ok and self.confirm.get_active() and self.plan["space"]["ok"]
        self.ok_btn.set_sensitive(ok)
        return ok


def ctx_help_button(topic, opener=None, show=None):
    """„?“-Knopf (0.10.2): öffnet das passende Kapitel des Full Manual (0.10.3) (nur lokale Datei). show(text) = Fehleranzeige."""
    b = fn_class(Gtk.Button(label=T.CTX_HELP, tooltip_text=T.CTX_HELP_TIP), "aux")

    def go(*_):
        try:
            (opener or manual.open_context)(topic)
        except Exception as e:  # noqa: BLE001
            if show:
                show(T.MSG_ERROR.format(err=_err_text(e)))
    b.connect("clicked", go)
    return b


class DocsDialog(Gtk.Dialog):
    """Documentation (0.10.2): Sprache English | Deutsch (nach Locale vorbelegt, wird nicht gemerkt) und vier Karten.
    Open startet nur xdg-open mit der lokalen Datei; kein Sprach-Fallback. Fehlende Dokumente sind grau.
    Anfangsfokus ← BACK, Esc = BACK (secure_dialog)."""

    def __init__(self, parent, dirs=None, opener=None, lang=None):
        super().__init__(title=T.DOCS_TITLE, transient_for=parent, modal=True)
        self.dirs = dirs
        self.opener = opener or manual.open_doc
        self.cards = {}
        self._css = Gtk.CssProvider()                  # Kartenfarben nur hier (Haupt-CSS bleibt unverändert)
        self._css.load_from_data(theme.doc_card_css(theme.active()["roles"]).encode())
        fit_dialog(self, parent, (620, 520))
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        area = self.get_content_area()
        area.set_border_width(MARGIN)
        area.set_spacing(SPACING)
        head = Gtk.Box(spacing=SPACING)
        head.pack_start(back_button(self), False, False, 0)
        title = Gtk.Label(xalign=0)
        title.set_markup(f"<b>{GLib.markup_escape_text(T.DOCS_TITLE)}</b>")
        head.pack_start(title, True, True, 0)
        self.version_lbl = Gtk.Label(xalign=1)
        head.pack_end(self.version_lbl, False, False, 0)
        area.pack_start(head, False, False, 0)
        lrow = Gtk.Box(spacing=SPACING)
        lrow.pack_start(Gtk.Label(label=T.DOCS_LANG, xalign=0), False, False, 0)
        self.lang_btns = {}
        first = None
        for code, label in (("en", T.DOCS_LANG_EN), ("de", T.DOCS_LANG_DE)):
            rb = Gtk.RadioButton.new_with_label_from_widget(first, label)
            first = first or rb
            self.lang_btns[code] = rb
            lrow.pack_start(rb, False, False, 0)
        area.pack_start(lrow, False, False, 0)
        for key in ("easy", "quick", "full", "dev"):
            area.pack_start(self._card(key), False, False, 0)
        self.warn = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        self.warn.get_style_context().add_class("evox-warn")
        self.msg = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        area.pack_start(self.warn, False, False, 0)
        area.pack_start(self.msg, False, False, 0)
        self.lang_btns[lang or manual.lang_default()].set_active(True)
        for rb in self.lang_btns.values():
            rb.connect("toggled", lambda *_: self.refresh())
        self.show_all()
        self.refresh()
        secure_dialog(self)

    def _card(self, key):
        name, text = T.DOCS_CARDS[key]
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("evox-block")
        head = Gtk.Label(label=name, xalign=0)
        head.get_style_context().add_class("evox-mid")
        desc = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=60)
        state = Gtk.Label(xalign=0)
        btn = Gtk.Button(label=T.DOCS_OPEN, halign=Gtk.Align.END)
        btn.get_style_context().add_provider(self._css, Gtk.STYLE_PROVIDER_PRIORITY_USER)     # nur diese Karten
        btn.connect("clicked", lambda *_: self.open(key))
        row = Gtk.Box(spacing=SPACING)
        row.pack_start(state, True, True, 0)
        row.pack_end(btn, False, False, 0)
        for w in (head, desc, row):
            box.pack_start(w, False, False, 0)
        self.cards[key] = (btn, state)
        return box

    @property
    def lang(self):
        return "de" if self.lang_btns["de"].get_active() else "en"

    def refresh(self):
        for key, (btn, state) in self.cards.items():
            have = manual.doc_file(key, self.lang, self.dirs) is not None
            ctx = btn.get_style_context()
            for c in ("easy", "quick", "full", "dev", "off"):
                ctx.remove_class(f"evox-doc-{c}")
            ctx.add_class("evox-doc-" + (key if have else "off"))
            btn.set_sensitive(have)
            planned = manual.DOCS[key][1]
            state.set_text("" if have else (T.DOCS_SOON if planned else T.DOCS_MISSING))
        f = manual.doc_file("quick", self.lang, self.dirs)
        dv = manual.doc_version(f) if f else None
        set_text(self.version_lbl, T.DOCS_VERSION.format(v=dv or __version__))
        set_text(self.warn, T.DOCS_OLDER.format(d=dv, p=__version__) if dv and manual.is_older(dv) else "")
        set_text(self.msg, "")

    def open(self, key):
        try:
            self.opener(key, self.lang, dirs=self.dirs) if self.dirs else self.opener(key, self.lang)
            set_text(self.msg, "")
        except Exception as e:  # noqa: BLE001
            set_text(self.msg, T.MSG_ERROR.format(err=_err_text(e)))


class KeysDialog(Gtk.Dialog):
    """Kleine Tastenliste (F1 / Knopf „⌨ Keys“); nur Anzeige, ← BACK und Esc schließen."""

    def __init__(self, parent):
        super().__init__(title=T.KEYS_TITLE, transient_for=parent, modal=True)
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        area = self.get_content_area()
        area.set_border_width(MARGIN)
        area.set_spacing(SPACING)
        title = Gtk.Label(xalign=0)
        title.set_markup(f"<b>{GLib.markup_escape_text(T.KEYS_TITLE)}</b>")
        grid = Gtk.Grid(column_spacing=SPACING * 3, row_spacing=SPACING)
        for i, (k, what) in enumerate(T.KEYS_ROWS):
            key = Gtk.Label(xalign=0)
            key.set_markup(f"<b>{GLib.markup_escape_text(k)}</b>")
            grid.attach(key, 0, i, 1, 1)
            grid.attach(Gtk.Label(label=what, xalign=0, wrap=True, max_width_chars=60), 1, i, 1, 1)
        area.pack_start(title, False, False, 0)
        area.pack_start(grid, False, False, 0)
        area.pack_start(Gtk.Label(label=T.KEYS_NOTE, xalign=0, wrap=True, max_width_chars=70), False, False, 0)
        self.show_all()
        secure_dialog(self)


CS_SIZE = (860, 720)      # Color settings: Standardgröße (auf die Arbeitsfläche begrenzt, Inhalt scrollt)


def rgba_hex(rgba) -> str:
    """Gdk.RGBA -> #RRGGBB (Alpha wird ignoriert)."""
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c * 255))) for c in (rgba.red, rgba.green, rgba.blue))


def hex_rgba(h) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(h)
    return c


class ColorSettingsDialog(Gtk.Dialog):
    """Color settings (0.8.0 A4a, 0.8.1): Theme, Farbe je Rolle, Schriftgröße 80–150 %, Live-Vorschau mit Direktklick.
    Die Vorschau besteht aus echten Widgets mit den echten CSS-Klassen der GUI (ein Provider, CSS = theme.build_css des
    Entwurfs). Klick/Enter auf ein Element öffnet den Farbwähler für genau dessen Rolle (theme.PREVIEW_ELEMENTS);
    feste Sicherheitsfarben erscheinen nur als nicht klickbare rote Beispiele. Sicherheitsfarben stehen nicht in der
    Rollenliste. Kontrast: < 3:1 Warnung (Use anyway nur für erlaubte Rollen), < 2:1 abgelehnt. Anfangsfokus/Vorgabe
    ← BACK, Esc = BACK (secure_dialog). Ergebnis in self.result (bei Save)."""

    FLASH_MS = 1200                         # kurze Rahmenmarkierung der gewählten Rolle

    def __init__(self, parent, appearance):
        super().__init__(title=T.CS_TITLE, transient_for=parent, modal=True)
        a = theme.sanitize(appearance)
        self.draft = {"theme": a["theme"], "roles": dict(a["roles"]), "accepted": list(a["accepted"]),
                      "font_scale": a["font_scale"]}
        self.result = None
        self.pending = None                 # (Rolle, Wert) wartet auf „Use anyway“
        self.tentative = None               # (Rolle, Wert) nur während der Farbwähler offen ist (Vorschau, nicht im Entwurf)
        self.last_change = None             # (Rolle, vorheriger Wert oder None) für Compare
        self.compare_on = False
        self.element = None                 # zuletzt angeklicktes Vorschau-Element
        self.chooser = None
        self.parts_pop = None               # Teilauswahl-Popover (Text/Fläche), solange offen
        self.part_btns = {}
        self._quiet = False                 # beim Setzen aus dem Programm keine Signale auswerten
        self._timers = set()
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        self.reset_theme_btn = fn_class(Gtk.Button(label=T.CS_RESET_THEME, tooltip_text=T.CS_RESET_THEME_TIP), "aux")
        self.reset_theme_btn.connect("clicked", lambda *_: self.reset_theme())
        self.get_action_area().pack_start(self.reset_theme_btn, False, False, 0)
        self.save_btn = self.add_button(T.CS_SAVE, Gtk.ResponseType.OK)
        self.save_btn.get_style_context().add_class("evox-start-internet")      # grün = speichern (wie Zweck-Dialog)
        self.connect("response", self._on_response)
        box = self.get_content_area()
        box.set_spacing(SPACING)
        self.back_top = back_button(self)
        head = Gtk.Box(spacing=SPACING, margin=SPACING)
        title = Gtk.Label(xalign=0)
        title.set_markup(f"<b>{GLib.markup_escape_text(T.CS_TITLE)}</b>")
        head.pack_start(title, True, True, 0)
        head.pack_end(self.back_top, False, False, 0)
        self.ctx_btn = ctx_help_button("colors", show=lambda t: self._status(t))
        self.ctx_btn.connect("focus-in-event", lambda *_: self._status(T.CTX_HELP_STATUS) or False)
        head.pack_end(self.ctx_btn, False, False, 0)
        box.pack_start(head, False, False, 0)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=SPACING)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC, min_content_height=100)
        self.scroller.add(body)
        box.pack_start(self.scroller, True, True, 0)
        grid = Gtk.Grid(column_spacing=SPACING, row_spacing=SPACING)
        body.pack_start(grid, False, False, 0)
        self.theme_combo = Gtk.ComboBoxText()
        for k, t in theme.THEMES.items():
            self.theme_combo.append(k, t["label"])
        # Schriftgröße: Schieberegler 80–150 % in 10er-Schritten (0.8.1, ersetzt die vier Stufen)
        self.size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, theme.SCALE_MIN, theme.SCALE_MAX,
                                                   theme.SCALE_STEP)
        self.size_scale.set_digits(0)
        self.size_scale.set_round_digits(0)
        self.size_scale.set_hexpand(True)
        self.size_scale.set_tooltip_text(T.CS_SIZE_TIP)
        for v in theme.FONT_SCALES:
            self.size_scale.add_mark(v, Gtk.PositionType.BOTTOM, str(v))
        self.size_scale.connect("format-value", lambda _s, v: T.CS_SIZE_FMT.format(v=int(round(v))))
        self.role_combo = Gtk.ComboBoxText()
        for k, label in theme.ROLES.items():
            self.role_combo.append(k, label)
        self.color_btn = Gtk.ColorButton(use_alpha=False, tooltip_text=T.CS_PICK_TIP)
        self.reset_role_btn = fn_class(Gtk.Button(label=T.CS_RESET_ROLE, tooltip_text=T.CS_RESET_ROLE_TIP), "aux")
        for w in (self.role_combo,):
            w.set_hexpand(True)
        rows = ((T.CS_THEME, self.theme_combo), (T.CS_SIZE, self.size_scale), (T.CS_ROLE, self.role_combo))
        for i, (text, w) in enumerate(rows):
            grid.attach(Gtk.Label(label=text, xalign=0, yalign=0.3), 0, i, 1, 1)
            grid.attach(w, 1, i, 1, 1)
        grid.attach(self.color_btn, 2, 2, 1, 1)
        grid.attach(self.reset_role_btn, 3, 2, 1, 1)
        frow = Gtk.Box(spacing=SPACING)
        self.export_btn = fn_class(Gtk.Button(label=T.CS_EXPORT, tooltip_text=T.CS_EXPORT_TIP), "aux")
        self.import_btn = fn_class(Gtk.Button(label=T.CS_IMPORT, tooltip_text=T.CS_IMPORT_TIP), "aux")
        self.export_btn.connect("clicked", lambda *_: self.choose_export())
        self.import_btn.connect("clicked", lambda *_: self.choose_import())
        frow.pack_start(self.export_btn, False, False, 0)
        frow.pack_start(self.import_btn, False, False, 0)
        body.pack_start(frow, False, False, 0)
        crow = Gtk.Box(spacing=SPACING)
        self.check_lbl = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        self.use_btn = fn_class(Gtk.Button(label=T.CS_USE_ANYWAY, tooltip_text=T.CS_USE_ANYWAY_TIP,
                                           no_show_all=True, valign=Gtk.Align.CENTER), "aux")
        self.use_btn.connect("clicked", lambda *_: self.use_anyway())
        crow.pack_start(self.check_lbl, True, True, 0)
        crow.pack_end(self.use_btn, False, False, 0)
        body.pack_start(crow, False, False, 0)
        erow = Gtk.Box(spacing=SPACING)
        self.edit_lbl = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.compare_btn = fn_class(Gtk.Button(label=T.CS_COMPARE, tooltip_text=T.CS_COMPARE_TIP,
                                               valign=Gtk.Align.CENTER), "aux")
        self.compare_btn.connect("pressed", lambda *_: self.compare(True))
        self.compare_btn.connect("released", lambda *_: self.compare(False))
        self.compare_btn.connect("focus-in-event", lambda *_: self._status(T.CS_STATUS_COMPARE) or False)
        erow.pack_start(self.edit_lbl, True, True, 0)
        erow.pack_end(self.compare_btn, False, False, 0)
        body.pack_start(erow, False, False, 0)
        body.pack_start(self._build_preview(), False, False, 0)
        note = Gtk.Label(label=T.CS_SAFETY_NOTE, xalign=0, wrap=True, max_width_chars=70)
        note.get_style_context().add_class("evox-subline")
        body.pack_start(note, False, False, 0)
        if focus_env():
            body.pack_start(Gtk.Label(label=T.CS_FOCUS_ENV, xalign=0, wrap=True, max_width_chars=70), False, False, 0)
        self.statusline = Gtk.Label(label=T.CS_STATUS_DEFAULT, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.statusline.get_style_context().add_class("evox-focusline")
        box.pack_end(self.statusline, False, False, 0)
        self._quiet = True
        self.theme_combo.set_active_id(self.draft["theme"])
        self.size_scale.set_value(self.draft["font_scale"])
        self.role_combo.set_active_id("disposable")
        self._quiet = False
        self._sync_color_btn()
        self._say_editing(theme.ROLES["disposable"])
        self.theme_combo.connect("changed", lambda *_: self._quiet or self.set_theme(self.theme_combo.get_active_id()))
        self.size_scale.connect("value-changed", lambda *_: self._quiet or self._on_size())
        self.role_combo.connect("changed", lambda *_: self._quiet or self._on_role())
        self.color_btn.connect("color-set", lambda *_: self.propose(self.role(), rgba_hex(self.color_btn.get_rgba())))
        self.reset_role_btn.connect("clicked", lambda *_: self.reset_role())
        self.update_preview()
        fit_dialog(self, parent, CS_SIZE)
        self.connect("destroy", lambda *_: self._on_destroy())
        self.show_all()
        secure_dialog(self)

    # ---- Vorschau: echte Widgets mit den echten CSS-Klassen; EIN Provider (CSS = theme.preview_css des Entwurfs)
    def _build_preview(self):
        frame = Gtk.Frame(label=T.CS_PREVIEW)
        pv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pv.get_style_context().add_class("evox-preview")
        self.preview = pv
        frame.add(pv)
        self.el = {}                        # Element-Schlüssel -> Widget (Markierung, Tooltip, Test)
        self._orig = {}                     # Element -> ursprünglicher Text (für ⚠/✖-Vorsatz)
        self._rows = {}                     # Liste -> (TreeView, ListStore, [(Text, Element, markierbar, rot)])
        self._warn_key = None
        self._cur = {"roles": theme.effective(self.draft["theme"], self.draft["roles"]), "sig": theme.SIGNAL_DARK,
                     "backup": theme.backup_color(self.draft["roles"], theme.SIGNAL_DARK)}

        def hook(w, key, fixed=False):
            self.el[key] = w
            w.set_tooltip_text(T.CS_PV_FIXED_TIP if fixed else self._tip(key))
            w.connect("focus-in-event", lambda *_: self._status(self._status_text(key)) or False)
            w.connect("enter-notify-event", lambda *_: self._status(self._status_text(key)) or False)
            return w

        def button(key, text, classes, flat=False, toggle=False):
            b = Gtk.ToggleButton(label=text) if toggle else Gtk.Button(label=text)
            lbl = b.get_child()
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            ctx = b.get_style_context()
            for c in classes:
                ctx.add_class(c)
                if flat:
                    lbl.get_style_context().add_class(c)
            if flat:
                b.set_relief(Gtk.ReliefStyle.NONE)
            hook(b, key)
            if toggle:
                b.set_active(True)
                b.connect("toggled", lambda w: w.get_active() or w.set_active(True))
            b.connect("clicked", lambda *_: self.pick_element(key))
            self._orig[key] = text
            return b

        pv.pack_start(button("title", APP_TITLE, ["evox-title"], flat=True), False, False, 0)
        pv.pack_start(button("heading", T.CS_PV_HEADING, ["evox-tagline"], flat=True), False, False, 0)
        trow = Gtk.Box(spacing=4)
        trow.pack_start(button("background", T.ELEMENT_NAMES["background"], ["evox-pv-text"], flat=True), False, False, 0)
        trow.pack_start(button("text", T.CS_PV_TEXT, ["evox-pv-text"], flat=True), True, True, 0)
        trow.pack_start(button("name", T.CS_PV_NAME, ["evox-mon-head"], flat=True), False, False, 0)
        pv.pack_start(trow, False, False, 0)
        grid = Gtk.Grid(column_spacing=6, row_spacing=4, column_homogeneous=True)
        pv.pack_start(grid, False, False, 0)
        areas = (("vault", T.TAB_VAULT, ((T.CS_PV_SELECTED, "row_vault_sel", True, False),
                                         (T.CS_PV_NORMAL, "row_vault_normal", False, False)), "amber",
                  (("btn_make", T.BTN_MAKE_SHORT, ["evox-fn-make"]), ("btn_virt", T.BTN_VIRT_SHORT, ["evox-vault-btn"]))),
                 ("template", T.TAB_TEMPLATE, ((T.CS_PV_SELECTED, "row_template_sel", True, False),
                                               (T.CS_PV_BACKUP, "row_template_backup", True, True)), "teal",
                  (("btn_import", T.BTN_IMPORT_SHORT, ["evox-import-btn"]), ("btn_verify", T.BTN_VERIFY_SHORT, ["evox-fn-verify"]),
                   ("btn_remove", T.BTN_REMOVE_SHORT, ["evox-fn-remove"]))),
                 ("disposable", T.TAB_DISPOSABLE, ((T.CS_PV_SELECTED, "row_disposable_sel", True, False),
                                                   (T.CS_PV_NORMAL, "row_disposable_normal", False, False)), "green",
                  (("btn_start_internet", T.BTN_START_SHORT, ["evox-start-disposable"]),
                   ("btn_start_offline", T.BTN_START_OFFLINE_SHORT, ["evox-offline"]),
                   ("btn_show", T.BTN_SHOW_SHORT, ["evox-fn-neutral"]))))
        for col, (area, tab_text, rows, sel, btns) in enumerate(areas):
            grid.attach(button(f"tab_{area}", tab_text, ["evox-howto", f"evox-{'vault-btn' if area == 'vault' else 'import-btn' if area == 'template' else 'start-disposable'}",
                                                         "evox-tabbtn", f"evox-tabbtn-{area}"], toggle=True), col, 0, 1, 1)
            grid.attach(self._mini_list(area, rows, sel), col, 1, 1, 1)
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            for key, text, classes in btns:
                bx.pack_start(button(key, text, classes), False, False, 0)
            grid.attach(bx, col, 2, 1, 1)
        hdr = Gtk.Box(spacing=4)
        for key, text, classes in (("btn_keys", T.BTN_KEYS, ["evox-fn-aux"]), ("btn_exit", T.BTN_EXIT, ["evox-fn-exit"]),
                                   ("btn_back", T.BACK, ["evox-cancel"])):
            hdr.pack_start(button(key, text, classes), False, False, 0)
        pv.pack_start(hdr, False, False, 0)
        fix = Gtk.Box(spacing=4)
        fix.pack_start(Gtk.Label(label=T.CS_PV_FIXED, xalign=0), False, False, 0)
        for key, text, cls in (("fixed_stop", T.CS_PV_FIXED_STOP, "evox-danger"), ("fixed_shut", T.CS_PV_FIXED_SHUT, "evox-danger"),
                               ("fixed_inactive", T.CS_PV_FIXED_INACTIVE, "evox-lock-bad"),
                               ("fixed_error", T.CS_PV_FIXED_ERROR, "evox-warn")):
            lbl = Gtk.Label(label=text)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.get_style_context().add_class(cls)
            lbl.get_style_context().add_class("evox-pv-fixed")
            hook(lbl, key, fixed=True)
            lbl.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK)
            fix.pack_start(lbl, False, False, 0)
        pv.pack_start(fix, False, False, 0)
        hint = Gtk.Label(label=T.CS_PV_HINT, xalign=0, wrap=True, max_width_chars=70)
        hint.get_style_context().add_class("evox-subline")
        pv.pack_start(hint, False, False, 0)
        self._preview_prov = Gtk.CssProvider()
        self._pv_css = None
        self._attach(pv)
        return frame

    def _mini_list(self, area, rows, sel):
        """Mini-Liste unter dem Reiter: echter TreeView mit der Listenklasse evox-sel-<sel>; nur die markierbaren Zeilen
        lassen sich markieren (normale Zeile bleibt „normal“). Klick/Enter auf eine Zeile wählt deren Rolle."""
        store = Gtk.ListStore(str)
        for text, _k, _m, _r in rows:
            store.append([text])
        view = Gtk.TreeView(model=store, headers_visible=False)
        view.get_style_context().add_class(f"evox-sel-{sel}")
        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", cell, text=0)

        def data(_c, rend, model, it, _d=None):
            i = model.get_path(it).get_indices()[0]
            red = rows[i][3]
            chosen = view.get_selection().path_is_selected(model.get_path(it))
            r = self._cur["roles"]
            if red:
                rend.set_property("foreground", r[theme.SELECT_KEYS[sel] + "_alt"] if chosen else self._cur["backup"])
            else:
                rend.set_property("foreground-set", False)
        col.set_cell_data_func(cell, data)
        view.append_column(col)
        selection = view.get_selection()
        selection.set_select_function(lambda _s, _m, path, _c, *a: rows[path.get_indices()[0]][2])
        selection.select_path(Gtk.TreePath.new_first())
        self._rows[area] = (view, store, rows)
        for i, (_t, key, _m, _r) in enumerate(rows):
            self.el[key] = view
            self._orig[key] = rows[i][0]
        view.set_tooltip_text(" / ".join(self._tip(k) for _t, k, _m, _r in rows))
        view.connect("button-press-event", self._on_tree_press, area)
        view.connect("row-activated", lambda _v, path, _c: self.pick_element(rows[path.get_indices()[0]][1]))
        view.connect("cursor-changed", lambda *_: self._status(self._row_status(area)))
        view.connect("focus-in-event", lambda *_: self._status(self._row_status(area)) or False)
        view.connect("motion-notify-event", self._on_tree_motion, area)
        view.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.IN)
        frame.add(view)
        return frame

    def _row_key_at(self, area, x, y):
        view, _s, rows = self._rows[area]
        hit = view.get_path_at_pos(int(x), int(y))
        return rows[hit[0].get_indices()[0]][1] if hit else None

    def _row_status(self, area):
        view, _s, rows = self._rows[area]
        path, _c = view.get_cursor()
        key = rows[path.get_indices()[0]][1] if path else rows[0][1]
        return self._status_text(key)

    def _on_tree_motion(self, _view, ev, area):
        key = self._row_key_at(area, ev.x, ev.y)
        if key:
            self._status(self._status_text(key))
        return False

    def _on_tree_press(self, _view, ev, area):
        """Linksklick auf eine Zeile: Rolle der Zeile wählen (Farbwähler); die Markierung folgt dem Standardverhalten."""
        if ev.button == 1 and ev.type == Gdk.EventType.BUTTON_PRESS:
            key = self._row_key_at(area, ev.x, ev.y)
            if key:
                GLib.idle_add(self.pick_element, key)
        return False

    def _attach(self, widget):
        """Den Vorschau-Provider an jedes Widget der Vorschau hängen (nur diese; das Haupt-CSS bleibt unberührt)."""
        widget.get_style_context().add_provider(self._preview_prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        if isinstance(widget, Gtk.Container):
            widget.forall(self._attach)

    def view_appearance(self) -> dict:
        """Was die Vorschau zeigt: Entwurf + Farbe im Farbwähler/„Use anyway“-Wartezustand; bei Compare der alte Wert
        der zuletzt geänderten Rolle. Ändert den Entwurf nie."""
        roles = dict(self.draft["roles"])
        if self.compare_on and self.last_change is not None:
            role, before = self.last_change
            if before is None:
                roles.pop(role, None)
            else:
                roles[role] = before
        else:
            for ov in (self.pending, self.tentative):
                if ov:
                    roles[ov[0]] = ov[1]
        return {"theme": self.draft["theme"], "roles": roles, "font_scale": self.draft["font_scale"]}

    def update_preview(self):
        a = self.view_appearance()
        css = theme.preview_css(a, focus_env())
        old = self._cur
        roles = theme.effective(a["theme"], a["roles"])
        sig = theme.signal_colors(roles)
        self._cur = {"roles": roles, "sig": sig, "backup": theme.backup_color(a["roles"], sig)}   # Zellenfarben (nicht im CSS)
        if css == self._pv_css:
            if self._cur != old:                    # nur Zellenfarbe geändert (z. B. -BACKUP): neu zeichnen, kein CSS-Neuladen
                for view, _s, _r in self._rows.values():
                    view.queue_draw()
            return                                  # nichts geändert: nichts neu laden (kein Flackern)
        self._pv_css = css
        self._preview_prov.load_from_data(css.encode())
        for view, _s, _r in self._rows.values():
            view.queue_draw()

    def _on_destroy(self):
        for t in list(self._timers):
            GLib.source_remove(t)
        self._timers.clear()
        if self.chooser is not None:
            self.chooser.destroy()
            self.chooser = None
        if self.parts_pop is not None:
            self.parts_pop.popdown()
            self.parts_pop = None
        self._preview_prov = None

    def _status(self, text):
        set_text(self.statusline, text)

    def _say_editing(self, name):
        set_text(self.edit_lbl, T.CS_EDITING.format(name=name))

    # ---- Direktklick: Element -> Rolle -> Farbwähler
    def _tip(self, key):
        parts = theme.PREVIEW_PARTS.get(key, ())
        if len(parts) > 1:
            return (T.CS_PARTS_TIP_SEL if "selected_text" in dict(parts) else T.CS_PARTS_TIP).format(name=T.ELEMENT_NAMES[key])
        return T.ELEMENT_NAMES[key]

    def _status_text(self, key):
        if key in theme.PREVIEW_FIXED:
            return T.CS_STATUS_FIXED.format(name=T.ELEMENT_NAMES[key])
        parts = theme.PREVIEW_PARTS.get(key, ())
        if len(parts) > 1:
            return (T.CS_STATUS_PARTS_SEL if "selected_text" in dict(parts) else T.CS_STATUS_PARTS).format(name=T.ELEMENT_NAMES[key])
        return T.CS_STATUS_ELEMENT.format(name=T.ELEMENT_NAMES[key])

    def pick_element(self, key, part=None):
        """Klick/Enter auf ein Vorschau-Element. Feste Sicherheitsbeispiele: nur Hinweis. Hat das Element zwei Teile
        (Schrift/Fläche) und ist part nicht gegeben, erscheint die Teilauswahl (Text color / Background color; liefert None).
        Sonst Rolle wählen, kurz markieren und den Farbwähler (GTK-Dialog) für genau diese Rolle öffnen. Liefert die Rolle."""
        if key in theme.PREVIEW_FIXED:
            self._say(T.CS_FIXED_INFO.format(name=T.ELEMENT_NAMES[key]))
            return None
        parts = theme.PREVIEW_PARTS.get(key)
        if not parts or self.chooser is not None:
            return None
        if part is None and len(parts) > 1:
            self.show_parts(key)
            return None
        role = theme.part_role(key, part)
        if role is None:
            return None
        if self.role() != role:
            self.role_combo.set_active_id(role)          # -> _on_role (Anzeige, Farbknopf, Meldung leeren)
        else:
            self.pending = None
            self._say("")
        self.element = key
        self._clear_warn()
        if len(parts) > 1 and part:
            self._say_editing(T.CS_EDITING_PART.format(name=T.ELEMENT_NAMES[key], part=T.PART_NAMES[part]))
        else:
            self._say_editing(T.ELEMENT_NAMES[key])
        self._flash(key)
        self.open_chooser(role, key, part if len(parts) > 1 else None)
        return role

    def show_parts(self, key):
        """Teilauswahl für ein Element mit Schrift und Fläche: kleines Popover mit je einem Knopf je Teil."""
        if self.parts_pop is not None:
            self.parts_pop.popdown()
        pop = Gtk.Popover(relative_to=self.el[key], modal=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=6)
        self.part_btns = {}
        for part, _role in theme.PREVIEW_PARTS[key]:
            b = Gtk.Button(label=T.PART_NAMES[part], tooltip_text=T.PART_TIPS[part])
            fn_class(b, "aux")
            b.connect("clicked", lambda _b, p=part: (pop.popdown(), self.pick_element(key, p)))
            box.pack_start(b, False, False, 0)
            self.part_btns[part] = b
        pop.add(box)
        pop.connect("closed", lambda *_: setattr(self, "parts_pop", None))
        self.parts_pop = pop
        self.element = key
        self._say_editing(T.ELEMENT_NAMES[key])
        box.show_all()
        pop.popup()
        self.part_btns[theme.PREVIEW_PARTS[key][0][0]].grab_focus()
        return pop

    def _flash(self, key):
        w = self.el.get(key)
        if w is None:
            return
        ctx = w.get_style_context()
        ctx.add_class("evox-pv-mark")

        def off():
            self._timers.discard(tid)
            ctx.remove_class("evox-pv-mark")
            return False
        tid = GLib.timeout_add(self.FLASH_MS, off)
        self._timers.add(tid)

    def open_chooser(self, role, key, part=None):
        name = T.ELEMENT_NAMES.get(key, theme.ROLES[role])
        title = T.CS_PICKER_TITLE_PART.format(name=name, part=T.PART_NAMES[part]) if part else T.CS_PICKER_TITLE.format(name=name)
        ch = Gtk.ColorChooserDialog(title=title, transient_for=self, modal=True)
        ch.set_use_alpha(False)
        ch.set_rgba(hex_rgba(self.value(role)))
        ch.role, ch.key = role, key
        ch.connect("notify::rgba", self._on_chooser_rgba)
        ch.connect("response", self._on_chooser_response)
        self.chooser = ch
        ch.show()
        return ch

    def _on_chooser_rgba(self, ch, _p=None):
        """Farbe im Wähler geändert: Vorschau live (Entwurf bleibt), Kontrastmeldung am Element."""
        if ch is self.chooser:
            self.propose(ch.role, rgba_hex(ch.get_rgba()), live=True)

    def _on_chooser_response(self, ch, resp):
        value = rgba_hex(ch.get_rgba())
        role = ch.role
        self.chooser = None
        self.tentative = None
        ch.destroy()
        if resp == Gtk.ResponseType.OK:
            self.propose(role, value)
        else:
            self.pending = None
            self._say("")
            self._clear_warn()
            self.update_preview()

    # ---- Compare: gedrückt halten = alte Farbe der zuletzt geänderten Rolle, loslassen = neue (nur Darstellung)
    def compare(self, on):
        if on and self.last_change is None:
            self._say(T.CS_COMPARE_NONE)
            return False
        self.compare_on = bool(on)
        if on:
            self._status(T.CS_COMPARE_SHOWING.format(name=theme.ROLES[self.last_change[0]]))
        else:
            self._status(T.CS_STATUS_COMPARE)
        self.update_preview()
        return self.compare_on

    # ---- Meldung direkt am Element: Rahmen + Tooltip + ⚠/✖ vor dem Text
    def _element_for(self, role):
        if self.element and role in theme.element_roles(self.element):
            return self.element
        return next((k for k in theme.PREVIEW_PARTS if role in theme.element_roles(k) and k != "background"), None) \
            or next((k for k in theme.PREVIEW_PARTS if role in theme.element_roles(k)), None)

    def _set_text_of(self, key, text):
        w = self.el.get(key)
        if isinstance(w, Gtk.TreeView):
            for area, (view, store, rows) in self._rows.items():
                for i, row in enumerate(rows):
                    if row[1] == key:
                        store[i][0] = text
        elif isinstance(w, Gtk.Button):
            w.set_label(text)

    def _clear_warn(self):
        key, self._warn_key = self._warn_key, None
        if key is None or key not in self.el:
            return
        ctx = self.el[key].get_style_context()
        ctx.remove_class("evox-pv-warn")
        ctx.remove_class("evox-pv-bad")
        self.el[key].set_tooltip_text(self._tip(key))
        self._set_text_of(key, self._orig[key])

    def _mark_result(self, role, level, text):
        self._clear_warn()
        key = self._element_for(role)
        if key is None or level == "ok":
            return
        self._warn_key = key
        sym = "⚠" if level == "warn" else "✖"
        self.el[key].get_style_context().add_class("evox-pv-warn" if level == "warn" else "evox-pv-bad")
        self.el[key].set_tooltip_text(f"{sym} {text}")
        self._set_text_of(key, f"{sym} {self._orig[key]}")

    # ---- Zustand
    def role(self):
        return self.role_combo.get_active_id()

    def value(self, role):
        return theme.effective(self.draft["theme"], self.draft["roles"])[role]

    def _sync_color_btn(self):
        self._quiet = True
        self.color_btn.set_rgba(hex_rgba(self.value(self.role())))
        self._quiet = False

    def _say(self, text, use=False):
        set_text(self.check_lbl, text)
        set_shown(self.use_btn, use)

    def _on_role(self):
        self.pending = None
        self.element = None
        self._clear_warn()
        self._sync_color_btn()
        self._say("")
        self._say_editing(theme.ROLES[self.role()])
        self.update_preview()

    @staticmethod
    def _pair(res):
        ratio, a, b = res["worst"]
        return f"{ratio:.1f}".replace(".", ","), f"{theme.ROLES[a]} / {theme.ROLES[b]}"

    def propose(self, role, value, live=False) -> str:
        """Neuen Wert prüfen: "ok" (übernommen), "warn"/"bad" (wartet auf Use anyway) oder "reject" (nur feste/unbekannte Rolle).
        live=True (Farbwähler noch offen): "ok" wird nur in der Vorschau gezeigt (tentative), nicht in den Entwurf."""
        self.pending = None
        res = theme.check_role(self.draft["theme"], self.draft["roles"], role, value)
        if res["level"] == "reject":                       # nur Sicherheits-/unbekannte Rolle oder ungültiger Wert
            self.tentative = None
            text = T.CS_REJECT.format(pair=theme.ROLES.get(role, "?"))
            self._say(text)
            self._mark_result(role, "reject", text)
            self._sync_color_btn()
            self.update_preview()
            return "reject"
        if res["level"] in ("warn", "bad"):                # nur warnen, nie verweigern (0.9.0)
            ratio, pair = self._pair(res)
            self.pending = (role, theme.norm_hex(value))
            text = (T.CS_BAD if res["level"] == "bad" else T.CS_WARN).format(ratio=ratio, pair=pair)
            self._say(text, use=True)
            self.tentative = (role, theme.norm_hex(value)) if live else None
            self._mark_result(role, res["level"], text)
            self._sync_color_btn()
            self.update_preview()
            return res["level"]
        if live:
            self.tentative = (role, theme.norm_hex(value))
        else:
            self.tentative = None
            self._set_role(role, theme.norm_hex(value))
        text = T.CS_OK.format(ratio=self._pair(res)[0]) if res["worst"] else ""
        if res["focus_clash"]:
            items = ", ".join(f"{theme.ROLES[k]} ({r:.1f}:1)".replace(".", ",") for k, r in res["focus_clash"])
            text = (text + " " + T.CS_FOCUS_CLASH.format(items=items)).strip()
        self._say(text)
        self._mark_result(role, "ok", text)
        self.update_preview()
        return "ok"

    def use_anyway(self):
        if self.pending is None:
            return False
        role, value = self.pending
        res = theme.check_role(self.draft["theme"], self.draft["roles"], role, value)
        if not res["can_override"]:
            return False
        self._set_role(role, value)
        self._clear_warn()
        if role not in self.draft["accepted"]:
            self.draft["accepted"].append(role)
        ratio, pair = self._pair(res)
        self._say(T.CS_ACCEPTED.format(ratio=ratio, pair=pair))
        self.pending = None
        return True

    def _set_role(self, role, value):
        self.last_change = (role, self.draft["roles"].get(role))      # für Compare: Wert vor dieser Änderung
        base = theme.THEMES[self.draft["theme"]]["roles"][role]
        if value.upper() == base.upper():
            self.draft["roles"].pop(role, None)
        else:
            self.draft["roles"][role] = value
        if role in self.draft["accepted"] and theme.check_role(
                self.draft["theme"], {k: v for k, v in self.draft["roles"].items() if k != role}, role,
                self.value(role))["level"] == "ok":
            self.draft["accepted"].remove(role)
        if self.role() == role:
            self._sync_color_btn()
        self.update_preview()

    def reset_role(self):
        role = self.role()
        self.pending = None
        self._clear_warn()
        self.last_change = (role, self.draft["roles"].get(role))
        self.draft["roles"].pop(role, None)
        if role in self.draft["accepted"]:
            self.draft["accepted"].remove(role)
        self._sync_color_btn()
        self._say("")
        self.update_preview()

    def reset_theme(self):
        self.pending = None
        self._clear_warn()
        self.last_change = None
        self.draft["roles"].clear()
        self.draft["accepted"].clear()
        self._sync_color_btn()
        self._say(T.CS_RESET_DONE)
        self.update_preview()

    # ---- Theme-Datei (0.9.0): nur geprüfte Farbwerte, nie CSS-Text
    def export_to(self, path) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(theme.export_theme(self.view_appearance() | {"accepted": self.draft["accepted"]}))
        except OSError as e:
            self._say(T.CS_EXPORT_FAILED.format(err=e))
            return False
        self._say(T.CS_EXPORTED.format(path=path))
        return True

    def import_from(self, path) -> bool:
        try:
            with open(path, "rb") as f:
                raw = f.read(theme.IMPORT_MAX_BYTES + 1)
            d = theme.import_theme(raw)
        except (OSError, ValueError) as e:
            self._say(T.CS_IMPORT_FAILED.format(err=e))
            return False
        self.pending = None
        self.last_change = None
        self._clear_warn()
        self.draft["theme"] = d["theme"]
        self.draft["roles"] = dict(d["roles"])
        self.draft["accepted"] = list(d["accepted"])
        self._quiet = True
        self.theme_combo.set_active_id(d["theme"])
        self._quiet = False
        self._sync_color_btn()
        self._say(T.CS_IMPORTED.format(n=len(d["roles"])))
        self.update_preview()
        return True

    def _file_dialog(self, title, action, button):
        fc = Gtk.FileChooserDialog(title=title, transient_for=self, action=action)
        fc.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        fc.add_button(button, Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name(T.CS_FILE_FILTER)
        flt.add_pattern("*.json")
        fc.add_filter(flt)
        if action == Gtk.FileChooserAction.SAVE:
            fc.set_do_overwrite_confirmation(True)
            fc.set_current_name("evox-theme.json")
        path = fc.get_filename() if fc.run() == Gtk.ResponseType.OK else None
        fc.destroy()
        return path

    def choose_export(self):
        path = self._file_dialog(T.CS_EXPORT_TITLE, Gtk.FileChooserAction.SAVE, T.CS_SAVE)
        return path and self.export_to(path)

    def choose_import(self):
        path = self._file_dialog(T.CS_IMPORT_TITLE, Gtk.FileChooserAction.OPEN, T.CS_IMPORT)
        return path and self.import_from(path)

    def set_theme(self, key):
        if key not in theme.THEMES or key == self.draft["theme"]:
            return
        self.draft["theme"] = key
        self.draft["roles"].clear()
        self.draft["accepted"].clear()
        self.pending = None
        self.last_change = None
        self._clear_warn()
        self._sync_color_btn()
        self._say(T.CS_THEME_CHANGED)
        self.update_preview()

    def _on_size(self):
        """Schieberegler: auf das 10er-Raster einrasten, dann übernehmen."""
        v = self.size_scale.get_value()
        snapped = theme.scale_of(int(round(v / theme.SCALE_STEP)) * theme.SCALE_STEP)
        if abs(v - snapped) > 1e-6:
            self.size_scale.set_value(snapped)              # löst value-changed erneut aus
            return
        self.set_scale(snapped)

    def set_scale(self, v):
        self.draft["font_scale"] = theme.scale_of(v)
        self.update_preview()

    def _on_response(self, _d, resp):
        self.compare_on = False
        self.tentative = None
        if resp == Gtk.ResponseType.OK:
            self.result = theme.sanitize(self.draft)


EXIT_KEEP, EXIT_ERASE = 1, 2      # Antworten des EXIT-Dialogs (Gtk.ResponseType.OK = EXIT ohne laufende VM, CANCEL = BACK)


class ExitDialog(Gtk.Dialog):
    """EXIT-Bestätigung (0.7.5). Mit Wegwerf-VMs: Anzahl und Namen, drei Wege (KEEP / SHUT DOWN & ERASE / ← BACK);
    ohne: kurze Rückfrage (EXIT / ← BACK). Anfangsfokus und Vorgabe ← BACK, Esc = BACK (secure_dialog)."""

    def __init__(self, parent, names):
        self.names = list(names)
        n = len(self.names)
        super().__init__(title=T.EXIT_TITLE_VMS.format(n=n) if n else T.EXIT_TITLE_NONE, transient_for=parent, modal=True)
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        if n:
            self.keep_btn = fn_class(self.add_button(T.EXIT_KEEP, EXIT_KEEP), "neutral")
            self.erase_btn = self.add_button(T.EXIT_ERASE, EXIT_ERASE)
            self.erase_btn.get_style_context().add_class("evox-danger")
            self.ok_btn = None
            markup = T.EXIT_TEXT_VMS.format(n=n, names="\n".join(
                f"• <b>{GLib.markup_escape_text(x)}</b>" for x in self.names))
        else:
            self.keep_btn = self.erase_btn = None
            self.ok_btn = fn_class(self.add_button(T.EXIT_CONFIRM, Gtk.ResponseType.OK), "neutral")
            markup = GLib.markup_escape_text(T.EXIT_TEXT_NONE)
        area = self.get_content_area()
        area.set_border_width(MARGIN)
        self.text = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
        self.text.set_markup(markup)
        area.pack_start(self.text, False, False, 0)
        self.show_all()
        secure_dialog(self)


class FixConfirmDialog(Gtk.Dialog):
    """Vorschau eines Befehls aus dem festen Katalog (setupcheck.py). Nichts läuft vor dem Klick auf „Run in terminal“;
    Anfangsfokus und Vorgabe ← BACK, Esc = BACK."""

    def __init__(self, parent, argv):
        super().__init__(title=T.SETUP_CONFIRM_TITLE, transient_for=parent, modal=True)
        self.argv = list(argv)
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        self.ok_btn = fn_class(self.add_button(T.SETUP_CONFIRM_OK, Gtk.ResponseType.OK), "neutral")
        area = self.get_content_area()
        area.set_border_width(MARGIN)
        area.set_spacing(SPACING)
        area.pack_start(Gtk.Label(label=T.SETUP_CONFIRM_TEXT, xalign=0, wrap=True, max_width_chars=70), False, False, 0)
        self.cmd_lbl = Gtk.Label(xalign=0, wrap=True, selectable=True, max_width_chars=70)
        self.cmd_lbl.set_markup("<tt><b>" + GLib.markup_escape_text(setupcheck.command_text(self.argv)) + "</b></tt>")
        area.pack_start(self.cmd_lbl, False, False, 0)
        self.show_all()
        secure_dialog(self)


class SetupDialog(Gtk.Dialog):
    """Setup check (0.10.0, Weg 1): Checkliste ✓/✗ mit Klartext, je ✗ ein Satz „why“ und ein Knopf „Fix it“.
    Die GUI bekommt nie Root: der Befehl (nur aus setupcheck.CATALOG) läuft nach Bestätigung in einem Terminal, nie in
    zwei Terminals zugleich. Prüfungen laufen im Hintergrund-Thread (check_now = synchron für Tests); kein Dauer-Timer."""

    def __init__(self, parent, ev, checker=None, spawn=None, which=shutil.which, watch=True):
        super().__init__(title=T.SETUP_TITLE, transient_for=parent, modal=True)
        self.ev = ev
        self.checker = checker or setupcheck.Checker(ev=ev)
        self.spawn = spawn or subprocess.Popen
        self.which = which
        self.watch = watch                       # Tests: False (kein Warte-Thread), Schließen per _terminal_closed()
        self.make_launcher = setupcheck.create_launcher
        self.items = []
        self.term_open = False
        self._checking = False
        self.fix_btns = []
        fit_dialog(self, parent, (680, 620))
        self.cancel_btn = self.add_button(T.BACK, Gtk.ResponseType.CANCEL)
        self.cancel_btn.get_style_context().add_class("evox-cancel")
        self.recheck_btn = fn_class(Gtk.Button(label=T.SETUP_RECHECK), "aux")
        self.recheck_btn.connect("clicked", lambda *_: self.start_check())
        self.copy_btn = fn_class(Gtk.Button(label=T.SETUP_COPY), "aux")
        self.copy_btn.connect("clicked", lambda *_: self.copy_report())
        self.launcher_btn = fn_class(Gtk.Button(label=T.SETUP_LAUNCHER, tooltip_text=T.SETUP_LAUNCHER_TIP), "aux")
        self.launcher_btn.connect("clicked", lambda *_: self.on_launcher())
        self.ctx_btn = ctx_help_button("setup", show=lambda t: set_text(self.msg, t))
        bar = self.get_action_area()
        for b in (self.recheck_btn, self.copy_btn, self.launcher_btn, self.ctx_btn):
            bar.pack_start(b, False, False, 0)
            bar.set_child_secondary(b, False)
        area = self.get_content_area()
        area.set_border_width(MARGIN)
        area.set_spacing(SPACING)
        head = Gtk.Box(spacing=SPACING)
        head.pack_start(back_button(self), False, False, 0)
        title = Gtk.Label(xalign=0)
        title.set_markup(f"<b>{GLib.markup_escape_text(T.SETUP_TITLE)}</b>")
        head.pack_start(title, True, True, 0)
        area.pack_start(head, False, False, 0)
        self.step_lbl = Gtk.Label(xalign=0, wrap=True)
        area.pack_start(self.step_lbl, False, False, 0)
        self.grid = Gtk.Grid(column_spacing=SPACING, row_spacing=SPACING)
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=100)
        sw.add(self.grid)
        area.pack_start(sw, True, True, 0)
        self.summary = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
        self.msg = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
        area.pack_start(self.summary, False, False, 0)
        area.pack_start(self.msg, False, False, 0)
        self.show_all()
        secure_dialog(self)
        set_text(self.step_lbl, T.SETUP_CHECKING)

    # ---- Prüfung
    def _set_step(self, n):
        set_text(self.step_lbl, T.SETUP_STEP.format(n=n, m=len(setupcheck.STEPS), what=T.SETUP_STEP_NAMES[n - 1]))
        return False

    def check_now(self):
        """Synchron (Tests und Fallback): alle sechs Schritte, dann Anzeige."""
        self._show(self.checker.all(progress=self._set_step))

    def start_check(self):
        if self._checking:
            return
        self._checking = True
        set_sensitive(self.recheck_btn, False)

        def work():
            try:
                items = self.checker.all(progress=lambda n: GLib.idle_add(self._set_step, n))
            except Exception as e:  # noqa: BLE001 – Prüfung darf nie hängen bleiben
                items = [setupcheck.Item(1, "error", False, T.MSG_ERROR.format(err=_err_text(e)))]
            GLib.idle_add(self._show, items)
        threading.Thread(target=work, daemon=True).start()

    def _show(self, items):
        self._checking = False
        self.items = list(items)
        for c in self.grid.get_children():
            self.grid.remove(c)
        self.fix_btns = []
        col = theme_colors(self)
        for r, it in enumerate(self.items):
            mark = Gtk.Label(yalign=0)
            mark.set_markup(colored("✓" if it.ok else "✗", col["ok"] if it.ok else col["bad"]))
            text = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
            body = GLib.markup_escape_text(it.text)
            if not it.ok and (it.why or it.info):
                body += "\n<small>" + GLib.markup_escape_text(" ".join(x for x in (it.why, it.info) if x)) + "</small>"
            text.set_markup(body)
            self.grid.attach(mark, 0, r, 1, 1)
            self.grid.attach(text, 1, r, 1, 1)
            if not it.ok and it.fix and setupcheck.fix_argv(it.fix, self.items):
                b = fn_class(Gtk.Button(label=T.SETUP_FIX, tooltip_text=T.SETUP_FIX_TIP, valign=Gtk.Align.START), "make")
                b.connect("clicked", lambda _b, it=it: self.fix_clicked(it))
                b.set_sensitive(not self.term_open)
                self.fix_btns.append(b)
                self.grid.attach(b, 2, r, 1, 1)
        bad = setupcheck.problems(self.items)
        self.summary.set_markup(colored(T.SETUP_READY, col["ok"]) if not bad
                                else colored(T.SETUP_PROBLEMS.format(n=len(bad)), col["bad"]))
        set_text(self.step_lbl, T.SETUP_STEP.format(n=len(setupcheck.STEPS), m=len(setupcheck.STEPS),
                                                    what=T.SETUP_STEP_NAMES[-1]))
        set_sensitive(self.recheck_btn, not self.term_open)
        self.grid.show_all()
        return False

    # ---- Fix-Knöpfe (nur Katalog; erst nach Bestätigung)
    def confirm_fix(self, argv) -> bool:
        d = FixConfirmDialog(self, argv)
        resp = d.run()
        d.destroy()
        return resp == Gtk.ResponseType.OK

    def fix_clicked(self, item):
        if self.term_open:
            return
        argv = setupcheck.fix_argv(item.fix, self.items)
        if not argv:
            set_text(self.msg, T.SETUP_NO_FIX)
            return
        if not self.confirm_fix(argv):
            return
        self.launch(argv)

    def launch(self, argv):
        full = setupcheck.terminal_argv(argv, self.which)
        if full is None:
            set_text(self.msg, T.SETUP_NO_TERMINAL)
            return
        try:
            proc = self.spawn(full)
        except (OSError, subprocess.SubprocessError) as e:
            set_text(self.msg, T.SETUP_TERMINAL_FAILED.format(err=e))
            return
        self._lock_terminal(True)
        if self.watch:
            def wait():
                try:
                    proc.wait()
                finally:
                    GLib.idle_add(self._terminal_closed)
            threading.Thread(target=wait, daemon=True).start()

    def _lock_terminal(self, on):
        self.term_open = on
        for b in self.fix_btns:
            set_sensitive(b, not on)
        set_sensitive(self.recheck_btn, not on)
        set_text(self.msg, T.SETUP_TERMINAL_OPEN if on else "")

    def _terminal_closed(self):
        self._lock_terminal(False)
        self.start_check()
        return False

    # ---- Bericht, Starter
    def copy_report(self):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(setupcheck.report(self.items), -1)
        set_text(self.msg, T.SETUP_COPIED)

    def on_launcher(self):
        set_text(self.msg, self.make_launcher() + "\n" + T.SETUP_PANEL_HINT)


class TabView(Gtk.Box):
    """Reiterzeile aus eigenen Knöpfen (Gtk.RadioButton ohne Anzeige = ein Reiter ist immer aktiv) und Gtk.Stack
    für den Inhalt. Nur Darstellung; Reihenfolge/Bedienung wie zuvor das Gtk.Notebook."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING)
        self.bar = Gtk.Box(spacing=HOWTO_GAP, homogeneous=True)
        self.stack = Gtk.Stack()
        self.keys = []
        self.buttons = {}
        self.pages = {}
        self._group = None
        self.bar.set_tooltip_text(T.TABS_TIP)
        self.pack_start(self.bar, False, False, 0)
        self.pack_start(self.stack, True, True, 0)

    def add_tab(self, key, label, page, compact=False):
        b = Gtk.RadioButton.new_with_label_from_widget(self._group, label)
        self._group = self._group or b
        b.set_mode(False)                                   # Knopf statt Auswahlpunkt
        ctx = b.get_style_context()
        for c in (TAB_CLASSES[key], "evox-howto", "evox-tabbtn", f"evox-tabbtn-{key}"):
            ctx.add_class(c)
        if compact:
            ctx.add_class("evox-howto-compact")
        b.connect("toggled", self._on_toggled, key)
        b.connect("key-press-event", self._on_arrow, key)
        b.set_tooltip_text(T.TABS_TIP)
        self.bar.pack_start(b, True, True, 0)
        self.stack.add_named(page, key)
        self.keys.append(key)
        self.buttons[key] = b
        self.pages[key] = page

    def _on_arrow(self, _btn, event, key):
        """Pfeil links/rechts auf der Reiterzeile wechselt den Reiter (ohne Umlauf) und behält den Fokus dort."""
        step = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1}.get(event.keyval)
        if step is None:
            return False
        n = self.keys.index(key) + step
        if 0 <= n < len(self.keys):
            self.set_current_page(n)
            self.buttons[self.keys[n]].grab_focus()
        return True

    def _on_toggled(self, btn, key):
        if btn.get_active() and self.stack.get_visible_child_name() != key:
            self.stack.set_visible_child_name(key)

    def get_n_pages(self):
        return len(self.keys)

    def get_nth_page(self, n):
        return self.pages[self.keys[n]]

    def get_current_page(self):
        name = self.stack.get_visible_child_name()
        return self.keys.index(name) if name in self.keys else 0

    def set_current_page(self, n):
        key = self.keys[max(0, min(n, len(self.keys) - 1))]
        self.buttons[key].set_active(True)
        if self.stack.get_visible_child_name() != key:
            self.stack.set_visible_child_name(key)


class MainWindow(Gtk.Window):
    """Oben Titel + Tagline und Gruppe Host (Sperranzeige, RAM/CPU), dann Reiter Disposable / Templates /
    Vaults (wachsen mit dem Fenster), unten Fortschritt und Statuszeile. Fenstergröße wird gemerkt
    (state_dir/gui.json)."""

    def __init__(self, ev):
        super().__init__(title=APP_TITLE)
        self.ev = ev
        self.busy = False
        self._cycle = 0
        self._tick_running = False
        self._tick_id = None             # genau ein Zeitgeber: REFRESH_S ohne, LIVE_S mit laufender Wegwerf-VM (0.7.2)
        self._tick_s = REFRESH_S
        self._full_at = 0.0              # Zeitpunkt des letzten vollen Zyklus (reconcile + Listen)
        self._has_running = False
        self._live_running = False       # Live-Lesevorgang im Thread unterwegs (dann Wert überspringen)
        self._live_at = 0.0              # Zeitpunkt der letzten Live-Werte aus dem Thread
        self._verifying = set()          # base_ids mit laufender Hintergrundprüfung
        self.monitor = None              # 0.7.4: höchstens ein Fenster „Live Monitor“
        self._mon_target = None          # VM, die der Monitor zeigt (folgt der Markierung)
        self.set_icon_name(ICON_NAME)
        geo = ev.s.load_gui_state()
        # 0.7.3: gespeicherte Höhe höchstens Arbeitsfläche (0.7.2 konnte eine übergroße Höhe speichern)
        self.set_default_size(geo["width"], min(geo["height"], max(MIN_SIZE[1], workarea_height())))
        if geo["maximized"]:
            self.maximize()
        self._maximized = geo["maximized"]
        self.connect("window-state-event", self._on_window_state)
        self.connect("delete-event", lambda *_: self.save_geometry() and False)
        self.appearance = apply_appearance(ev.s.load_option(theme.KEY))   # 0.8.0: Theme/Farben/Schrift aus config.json
        self.colors = theme_colors(self)
        apply_css()
        self.set_size_request(MIN_SIZE[0], min(MIN_SIZE[1], workarea_height()))   # 0.8.0: nie höher als die Arbeitsfläche
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=MARGIN)
        self.add(box)

        # Titel und Tagline (Zeile 1 darf umbrechen)
        title = Gtk.Label(label=APP_TITLE, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.title = title
        title.get_style_context().add_class("evox-title")
        self.tagline = Gtk.Label(label=T.TAGLINE, xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER)
        self.tagline.get_style_context().add_class("evox-tagline")
        self.subline = Gtk.Label(label=T.SUBLINE, xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER)
        self.subline.get_style_context().add_class("evox-subline")
        trow = Gtk.Box(spacing=SPACING)                   # 0.7.5: Knopfzeile oben rechts, Titel eine Zeile tiefer
        self.exit_btn = fn_class(Gtk.Button(label=T.BTN_EXIT, valign=Gtk.Align.START, tooltip_text=T.BTN_EXIT_TIP), "exit")
        self.exit_btn.connect("clicked", self.on_exit)
        self.fullscreen_btn = fn_class(Gtk.Button(label=T.BTN_FULLSCREEN, valign=Gtk.Align.START), "neutral")
        self.fullscreen_btn.connect("clicked", lambda *_: self.toggle_fullscreen())
        self.keys_btn = fn_class(Gtk.Button(label=T.BTN_KEYS, valign=Gtk.Align.START, tooltip_text=T.BTN_KEYS_TIP),
                                 "aux")
        self.keys_btn.connect("clicked", lambda *_: self.show_keys())
        self.colors_btn = fn_class(Gtk.Button(label=T.BTN_COLORS, valign=Gtk.Align.START, tooltip_text=T.BTN_COLORS_TIP),
                                   "aux")
        self.colors_btn.connect("clicked", lambda *_: self.show_colors())
        self.setup_btn = fn_class(Gtk.Button(label=T.BTN_SETUP, valign=Gtk.Align.START, tooltip_text=T.BTN_SETUP_TIP),
                                  "aux")
        self.setup_btn.connect("clicked", lambda *_: self.show_setup())
        self.docs_btn = fn_class(Gtk.Button(label=T.BTN_DOCS, valign=Gtk.Align.START, tooltip_text=T.BTN_DOCS_TIP), "aux")
        self.docs_btn.connect("clicked", lambda *_: self.show_docs())
        trow.pack_end(self.exit_btn, False, False, 0)
        trow.pack_end(self.fullscreen_btn, False, False, 0)
        trow.pack_end(self.keys_btn, False, False, 0)
        trow.pack_end(self.colors_btn, False, False, 0)
        trow.pack_end(self.setup_btn, False, False, 0)
        trow.pack_end(self.docs_btn, False, False, 0)
        for w in (trow, title, self.tagline, self.subline):
            box.pack_start(w, False, False, 0)
        box.pack_start(self._build_howto_bar(), False, False, 0)
        box.pack_start(self._build_setup_bar(), False, False, 0)
        self._fullscreen = False
        self.connect("key-press-event", self._on_key)

        # oben: Host
        host = Gtk.Frame(label=T.GROUP_HOST)
        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=INNER)
        host.add(hbox)
        self.status = Gtk.Label(xalign=0, wrap=True)       # Sperranzeige
        self.status.set_ellipsize(Pango.EllipsizeMode.END)   # Fenster wird nie breiter
        self.status.set_max_width_chars(1)
        self.status.set_lines(2)
        self.host_lbl = Gtk.Label(xalign=0, wrap=True)
        hbox.pack_start(self.status, False, False, 0)
        hbox.pack_start(self.host_lbl, False, False, 0)
        box.pack_start(host, False, False, 0)

        # Reiter: Disposable (Alltag, vorne), Templates, Vaults (Platzhalter bis A2)
        self.tabs = TabView()
        box.pack_start(self.tabs, True, True, 0)
        built = {"disposable": self._build_disposable_tab(), "template": self._build_templates_tab(ev),
                 "vault": self._build_vault_tab()}
        labels = {"vault": T.TAB_VAULT, "template": T.TAB_TEMPLATE, "disposable": T.TAB_DISPOSABLE}
        compact = howto_compact()
        for key in TAB_KEYS:                                 # Anzeige in der Ablaufreihenfolge
            self.tabs.add_tab(key, labels[key], built[key], compact)

        # unten: Fortschritt (lange Vorgänge) und Statuszeile
        prow = Gtk.Box(spacing=SPACING)
        self.progress = Gtk.ProgressBar(show_text=True, no_show_all=True, valign=Gtk.Align.CENTER)
        self.cancel_copy_btn = Gtk.Button(label=T.BTN_CANCEL_COPY, no_show_all=True)
        self.cancel_copy_btn.get_style_context().add_class("evox-cancel")
        self.cancel_copy_btn.connect("clicked", self.on_cancel_copy)
        prow.pack_start(self.progress, True, True, 0)
        prow.pack_start(self.cancel_copy_btn, False, False, 0)
        box.pack_start(prow, False, False, 0)
        self._cancel = None
        self._fraction = None
        self.msg = Gtk.Label(xalign=0, wrap=True, selectable=True)
        box.pack_start(self.msg, False, False, 0)
        self.focusline = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, single_line_mode=True,
                                   max_width_chars=1)
        self.focusline.get_style_context().add_class("evox-focusline")
        box.pack_end(self.focusline, False, False, 0)               # ganz unten, immer sichtbar
        self.action_btns = (self.start_btn, self.start_offline_btn, self.stop_btn, self.import_btn,
                            self.verify_btn, self.remove_btn, *self.howto_btns[3:])
        self._progress_timer = None
        self._tpl_rows = {}
        self._temp_rows = {}
        self._viewer_checks = {}         # Zeitgeber-ID -> ausstehende Prüfung des VM-Fensters (show_vm)
        self._vault_rows = {}
        self._last_data = {}             # zuletzt angezeigter Datenstand je Liste (Aufbau nur bei Änderung)

        # Prüfung nach dem Beenden: Evox meldet jede vernichtete Wegwerf-VM (beliebiger Thread)
        ev.on_temp_destroyed = lambda base_id: GLib.idle_add(self._after_destroy, base_id)

        self._build_status_texts()
        self.connect("set-focus", self._on_set_focus)
        self._hover = None
        set_text(self.focusline, T.STATUS_DEFAULT)
        box.show_all()                   # Stack/Notebook wählen nur sichtbare Kinder (Fortschritt bleibt aus)
        self.tabs.set_current_page(TAB_KEYS.index(START_TAB))
        self.refresh_bases()
        self.safe_refresh()
        self._tick_id = GLib.timeout_add_seconds(REFRESH_S, self._on_timer)
        self._retime()
        self.connect("destroy", self._on_destroy)

    def _build_status_texts(self):
        """Kurztext je fokussierbares Hauptelement (Statuszeile unten, 0.6.16; rein informativ)."""
        t = {self.exit_btn: T.STATUS_EXIT, self.fullscreen_btn: T.STATUS_FULLSCREEN, self.keys_btn: T.STATUS_KEYS, self.colors_btn: T.STATUS_COLORS, self.setup_btn: T.STATUS_SETUP,
             self.docs_btn: T.STATUS_DOCS,
             self.setup_bar_btn: T.STATUS_SETUP_BAR_OPEN, self.setup_bar_close: T.STATUS_HINT_CLOSE,
             self.view: T.STATUS_LIST_TEMP,
             self.tpl_view: T.STATUS_LIST_TPL, self.vault_view: T.STATUS_LIST_VAULT, self.base_combo: T.STATUS_COMBO,
             self.start_btn: T.STATUS_START, self.start_offline_btn: T.STATUS_START_OFFLINE,
             self.console_btn: T.STATUS_SHOW, self.stop_btn: T.STATUS_STOP, self.details_btn: T.STATUS_DETAILS,
             self.import_btn: T.STATUS_IMPORT, self.verify_btn: T.STATUS_VERIFY, self.remove_btn: T.STATUS_REMOVE,
             self.verify_chk: T.STATUS_VERIFY_CHK, self.make_btn: T.STATUS_MAKE,
             self.virt_manager_btn: T.STATUS_VIRT_MANAGER, self.hint_close: T.STATUS_HINT_CLOSE,
             self.cancel_copy_btn: T.STATUS_CANCEL_COPY}
        for k in TAB_KEYS:
            t[self.tabs.buttons[k]] = T.STATUS_TABS[k]
        for b, text in zip(self.howto_btns, T.STATUS_HOWTO):
            t[b] = text
        self.status_texts = t
        for w in t:
            if isinstance(w, Gtk.Button):
                w.connect("enter-notify-event", self._on_hover, w)
                w.connect("leave-notify-event", self._on_hover, None)

    def status_text(self, widget) -> str:
        """Text der Statuszeile zu einem Element (Elternkette; sonst Standardtext); bei gesperrtem Element mit Grund."""
        w = widget
        while w is not None and w not in self.status_texts:
            w = w.get_parent()
        if w is None:
            return T.STATUS_DEFAULT
        text = self.status_texts[w]
        if not w.get_sensitive():
            reason = w.get_tooltip_text()
            if reason:
                text += " " + T.STATUS_LOCKED.format(reason=reason)
        return text

    def _on_set_focus(self, _win, widget):
        set_text(self.focusline, self.status_text(widget) if widget is not None else T.STATUS_DEFAULT)

    def _on_hover(self, _w, _event, target):
        """Maus über einem Knopf zeigt denselben Text (auch bei gesperrten Knöpfen, die keinen Fokus bekommen)."""
        self._hover = target
        cur = target if target is not None else self.get_focus()
        set_text(self.focusline, self.status_text(cur) if cur is not None else T.STATUS_DEFAULT)
        return False

    def _on_destroy(self, _w):
        """Zeitgeber beenden: sonst ruft er nach dem Schließen noch Methoden des zerstörten Fensters auf."""
        if self._tick_id is not None:
            GLib.source_remove(self._tick_id)
            self._tick_id = None
        if self.monitor is not None:
            self.monitor.dismiss()                         # Geometrie wird gemerkt, Fenster zerstört
        for chk in list(self._viewer_checks.values()):     # offene VM-Fenster-Prüfungen: Zeitgeber weg, Datei zu
            chk()
        self._unflash()
        self.record_purpose_peaks(self.live.forget(()))   # Zweck-Statistik: Spitzen noch laufender VMs sichern

    def _build_howto_bar(self):
        """Schmale Leiste „HOW TO USE“: Überschrift in eigener Zeile (0.7.3), darunter vier Schritte über die volle
        Breite, je eine Zeile; nur Schritt 4 hat zwei Knöpfe (INTERNET / OFFLINE, je zur Hälfte, man wählt einen).
        Jeder Schritt hat eine eigene Farbe."""
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=HOWTO_GAP)
        compact = howto_compact()
        self.howto_title = Gtk.Label(label=T.HOWTO_TITLE, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.howto_title.get_style_context().add_class("evox-howto-title")
        self.howto_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=HOWTO_GAP)
        self.howto_btns = []
        for i, (text, tip, css) in enumerate(zip(T.HOWTO_STEPS, T.HOWTO_TIPS, HOWTO_CLASSES)):
            b = Gtk.Button(label=text, tooltip_text=tip)
            ctx = b.get_style_context()
            ctx.add_class(css)
            ctx.add_class("evox-howto")
            if compact:
                ctx.add_class("evox-howto-compact")
            b.connect("clicked", self.on_howto, i)
            b.connect("key-press-event", self._on_howto_arrow, i)
            child = b.get_child()                      # einzeilig, bei Platzmangel kürzen (nie umbrechen)
            child.set_ellipsize(Pango.EllipsizeMode.END)
            child.set_single_line_mode(True)
            self.howto_btns.append(b)
        for i in range(3):
            row = Gtk.Box(spacing=HOWTO_GAP)
            row.pack_start(self.howto_btns[i], True, True, 0)
            self.howto_rows.pack_start(row, False, False, 0)
        self.howto_start_row = Gtk.Box(spacing=HOWTO_GAP, homogeneous=True)   # INTERNET/OFFLINE je genau die Hälfte
        for b in self.howto_btns[3:]:
            self.howto_start_row.pack_start(b, True, True, 0)
        self.howto_rows.pack_start(self.howto_start_row, False, False, 0)
        bar.pack_start(self.howto_title, False, False, 0)
        bar.pack_start(self.howto_rows, False, True, 0)
        self._flash_widget = None
        self._flash_id = None
        self._vault_known = False
        return bar

    def _on_howto_arrow(self, _btn, event, i):
        """Pfeil hoch/runter springt zwischen den HOW-TO-Zeilen (Schritt 4: INTERNET/OFFLINE zählen als eine Zeile).
        Gesperrte Knöpfe werden übersprungen; am Ende der Leiste greift die normale Fokusführung."""
        step = {Gdk.KEY_Up: -1, Gdk.KEY_Down: 1}.get(event.keyval)
        if step is None:
            return False
        rows = [[0], [1], [2], [3, 4]]
        r = min(i, 3) + step
        while 0 <= r < len(rows):
            cands = [self.howto_btns[j] for j in rows[r] if self.howto_btns[j].get_sensitive()]
            if cands:
                cands[0].grab_focus()
                return True
            r += step
        return True if step < 0 else False

    def _build_setup_bar(self):
        """Hinweisbalken statt Dialog, wenn die stille Prüfung beim Start ein ✗ findet (0.10.0)."""
        self.setup_bar = Gtk.EventBox(no_show_all=True)
        self.setup_bar.get_style_context().add_class("evox-hint-bar")
        row = Gtk.Box(spacing=SPACING)
        self.setup_bar_lbl = Gtk.Label(xalign=0, wrap=True)
        self.setup_bar_lbl.get_style_context().add_class("evox-hint-text")
        self.setup_bar_btn = Gtk.Button(label=T.SETUP_BAR_OPEN, valign=Gtk.Align.CENTER, tooltip_text=T.SETUP_BAR_OPEN_TIP)
        self.setup_bar_btn.get_style_context().add_class("evox-hint-close")
        self.setup_bar_btn.connect("clicked", lambda *_: self.show_setup())
        self.setup_bar_close = Gtk.Button(label=T.HINT_CLOSE, valign=Gtk.Align.CENTER, tooltip_text=T.HINT_CLOSE_TIP)
        self.setup_bar_close.get_style_context().add_class("evox-hint-close")
        self.setup_bar_close.connect("clicked", lambda *_: self.setup_bar.hide())
        row.pack_start(self.setup_bar_lbl, True, True, 0)
        row.pack_end(self.setup_bar_close, False, False, 0)
        row.pack_end(self.setup_bar_btn, False, False, 0)
        self.setup_bar.add(row)
        row.show_all()
        return self.setup_bar

    def show_setup(self, dialog_cls=None):
        """Setup check öffnen; danach gilt der Erststart als erledigt (gui.json) und der Hinweisbalken verschwindet."""
        self.setup_bar.hide()
        d = (dialog_cls or SetupDialog)(self, self.ev)
        self.setup_dialog = d                      # für Tests erreichbar
        d.start_check()
        d.run()
        d.destroy()
        try:
            self.ev.s.save_setup_seen(True)
        except OSError:
            pass

    def startup_setup_check(self, checker=None, sync=False):
        """Beim Start (einmal, nach dem Fenster): Erststart -> Dialog; sonst stille Lese-Prüfung im Hintergrund und bei
        ✗ nur ein Hinweisbalken. Kein Dauer-Timer, die GUI blockiert nie."""
        if not self.ev.s.load_gui_state()["setup_seen"]:
            self.show_setup()
            return False
        chk = checker or setupcheck.Checker(ev=self.ev)

        def work():
            try:
                items = chk.all()
            except Exception:  # noqa: BLE001 – still bleiben
                return
            if sync:
                self._startup_result(items)
            else:
                GLib.idle_add(self._startup_result, items)
        if sync:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
        return False

    def _startup_result(self, items):
        bad = [i for i in setupcheck.problems(items) if i.key not in ("internet", "ram")]
        if bad:
            set_text(self.setup_bar_lbl, T.SETUP_BAR.format(n=len(bad)))
            self.setup_bar.show()
        return False

    def show_docs(self):
        d = DocsDialog(self)
        d.run()
        d.destroy()

    def show_keys(self):
        d = KeysDialog(self)
        d.run()
        d.destroy()

    def show_colors(self):
        """Color settings (0.8.0): Save → config.json (atomar, defekte Datei gesichert) und sofort anwenden."""
        d = ColorSettingsDialog(self, self.appearance)
        resp = d.run()
        result = d.result if resp == Gtk.ResponseType.OK else None
        d.destroy()
        if result is None:
            return
        try:
            self.ev.s.save_option(theme.KEY, result)
        except OSError as e:
            self.show(T.MSG_COLORS_FAILED.format(err=e), bad=True)
            return
        self.appearance = apply_appearance(result)
        self.colors = theme_colors(self)
        self._sync_compact()
        self.show(T.MSG_COLORS_SAVED)

    def _sync_compact(self):
        """Kompakte Knopfhöhe nach Änderung der Schriftgröße nachziehen (ohne Neustart)."""
        on = howto_compact()
        for b in list(self.howto_btns) + list(self.tabs.bar.get_children()):
            ctx = b.get_style_context()
            if on:
                ctx.add_class("evox-howto-compact")
            else:
                ctx.remove_class("evox-howto-compact")

    def howto_state(self):
        """(Vault vorhanden, Template vorhanden) oder None, wenn nicht ermittelbar (dann nichts sperren)."""
        if not self._vault_known:
            return None
        try:
            return bool(self._vault_rows), bool(self.ev.reg.bases())
        except Exception:  # noqa: BLE001 – Zustand unbekannt: keine Sperre
            return None

    _set_text = staticmethod(set_text)

    @staticmethod
    def _set_child(stack, name):
        if stack.get_visible_child_name() != name:
            trace("stack_child", name)
            stack.set_visible_child_name(name)

    @staticmethod
    def _set_btn(btn, sensitive, tip=None):
        """Knopfzustand nur bei echter Änderung setzen."""
        set_sensitive(btn, sensitive)
        if tip is not None:
            set_tooltip(btn, tip)

    def _sync_howto(self):
        """Geführter Ablauf (reine Führung, nur die HOW-TO-Knöpfe): Sperren, Tooltips, Hervorhebung des nächsten
        Schritts. Die normalen Knöpfe in den Reitern und ihre Prüfungen bleiben unverändert."""
        st = self.howto_state()
        vault, tpl = st if st else (True, True)
        lock2 = st is not None and not vault
        lock4 = st is not None and not tpl
        b = self.howto_btns
        self._set_btn(b[0], True)
        self._set_btn(b[2], True)
        self._set_btn(b[1], not lock2, T.HOWTO_TIP_NO_VAULT if lock2 else T.HOWTO_TIPS[1])
        for i in (3, 4):
            self._set_btn(b[i], not lock4 and not self.busy, T.HOWTO_TIP_NO_TEMPLATE if lock4 else T.HOWTO_TIPS[i])
        if st is None:
            nxt = ()
        elif tpl:
            nxt = (3, 4)
        elif vault:
            nxt = (1, 2)
        else:
            nxt = (0,)
        if nxt != getattr(self, "howto_next", None) or not getattr(self, "_next_applied", False):
            for i, btn in enumerate(b):
                set_class(btn, "evox-next", i in nxt)
            self._next_applied = True
        self.howto_next = nxt

    def on_howto(self, _btn, step):
        """Schritte 1–3: nur zum Reiter wechseln und den Knopf kurz hervorheben. Schritte 4/5: Startdialog öffnen
        (gestartet wird erst mit Start im Dialog, mit denselben Prüfungen)."""
        if step <= 2:
            tab, target = (("vault", self.virt_manager_btn), ("vault", self.make_btn), ("template", self.import_btn))[step]
            self.tabs.set_current_page(TAB_KEYS.index(tab))
            self._flash(target)
            return None
        self.tabs.set_current_page(TAB_KEYS.index("disposable"))
        if self.busy:
            return None
        return self.on_start(None, offline=(step == 4))

    def _flash(self, widget):
        self._unflash()
        widget.get_style_context().add_class("evox-flash")
        self._flash_widget = widget
        self._flash_id = GLib.timeout_add(FLASH_MS, self._unflash)

    def _unflash(self):
        if self._flash_id is not None:
            GLib.source_remove(self._flash_id)
            self._flash_id = None
        if self._flash_widget is not None:
            self._flash_widget.get_style_context().remove_class("evox-flash")
            self._flash_widget = None
        return False

    def _build_disposable_tab(self):
        """VM-Liste (oder Erklärsatz), Template-Auswahl + zwei Start-Knöpfe, Detailleiste (einklappbar)."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=INNER)
        # Spalten (0.7.1 schlank): T.COLUMNS (Name, Zustand, Modus), dann T.LIVE_COLUMNS (Laufzeit, RAM-Ampel, CPU),
        # zuletzt Ampelfarbe der RAM-Spalte (unsichtbar)
        self.live_col = len(T.COLUMNS)
        self.store = Gtk.ListStore(*([str] * (len(T.COLUMNS) + len(T.LIVE_COLUMNS) + 1)))
        self.view = Gtk.TreeView(model=self.store)
        for i, title in enumerate(T.COLUMNS):
            self.view.append_column(Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i))
        fg_i = self.live_col + len(T.LIVE_COLUMNS)
        for j, title in enumerate(T.LIVE_COLUMNS):
            i = self.live_col + j
            col = (sel_fg_column(self.view, title, i, fg_i, "green", sel_plain=True) if j == 1
                   else Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i))
            self.view.append_column(col)
        self.live = livestats.LiveSampler()
        self._live = {}                  # name -> Live-Werte des letzten Zyklus
        self.view.get_selection().connect("changed", lambda *_: (trace("selection_changed", "temp"), self.update_details()))
        sw = Gtk.ScrolledWindow(min_content_height=LIST_KEEP_H, vexpand=True, shadow_type=Gtk.ShadowType.IN)
        self.vm_sw = sw                   # 0.7.3: Mindesthöhe sinkt bei offenen Details (Platz kommt von der Liste)
        sw.add(self.view)
        self.vm_stack = empty_stack(list_frame(sw, self.view, "green"), T.EMPTY_DISPOSABLE)
        self.vm_stack.set_vhomogeneous(False)    # 0.7.3: Mindesthöhe nur der sichtbaren Seite (Liste gibt Platz ab)
        page.pack_start(self.vm_stack, True, True, 0)

        row = Gtk.Box(spacing=SPACING)
        self.base_store = Gtk.ListStore(str, str)          # Name, Schriftfarbe
        self.base_combo = Gtk.ComboBox(model=self.base_store)
        cell = Gtk.CellRendererText()
        self.base_combo.pack_start(cell, True)
        self.base_combo.add_attribute(cell, "text", 0)
        self.base_combo.add_attribute(cell, "foreground", 1)
        self.start_btn = two_line_button(T.BTN_START, T.BTN_START_SUB)                  # Internet
        self.start_btn.get_style_context().add_class("evox-start-disposable")
        self.start_btn.connect("clicked", self.on_start, False)
        self.start_offline_btn = two_line_button(T.BTN_START_OFFLINE, T.BTN_START_OFFLINE_SUB)  # Offline (Blau)
        self.start_offline_btn.get_style_context().add_class("evox-offline")
        self.start_offline_btn.connect("clicked", self.on_start, True)
        self.console_btn = fn_class(Gtk.Button(label=T.BTN_SHOW), "neutral")
        self.console_btn.connect("clicked", self.on_console)
        self.stop_btn = Gtk.Button(label=T.BTN_STOP)
        self.stop_btn.get_style_context().add_class("evox-danger")
        self.stop_btn.connect("clicked", self.on_stop)
        self.stop_btn.set_sensitive(False)
        self.stop_btn.set_tooltip_text(T.BTN_STOP_TIP_NONE)
        row.pack_start(Gtk.Label(label=T.LABEL_TEMPLATE), False, False, 0)
        row.pack_start(self.base_combo, True, True, 0)
        start_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING)   # übereinander, gleich breit
        start_box.pack_start(self.start_btn, False, False, 0)
        start_box.pack_start(self.start_offline_btn, False, False, 0)
        size = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        size.add_widget(self.start_btn)
        size.add_widget(self.start_offline_btn)
        row.pack_start(start_box, False, False, 0)
        row.pack_end(self.stop_btn, False, False, 0)
        row.pack_end(self.console_btn, False, False, 0)
        page.pack_start(row, False, False, 0)

        # 0.7.4: statt des Detailbereichs EINE Kurzzeile (RAM-Ampel, CPU, Laufzeit) + Knopf OPEN/CLOSE DETAILS, der das
        # Fenster „Live Monitor“ (MonitorWindow) öffnet. Die Zeile ist immer sichtbar und einzeilig (ellipsiert):
        # ihre Höhe richtet sich nach dem Knopf, die Fenstergröße ändert sich dadurch nie.
        self.short_lbl = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, single_line_mode=True,
                                   max_width_chars=1, tooltip_text=T.LIVE_TIP)
        self.details_btn = fn_class(Gtk.Button(label=T.BTN_DETAILS_OPEN, tooltip_text=T.DETAILS_TIP_NONE), "neutral")
        self.details_btn.get_style_context().add_class("evox-details-btn")
        self.details_btn.connect("clicked", lambda *_: self.toggle_monitor())
        self.details = Gtk.Box(spacing=SPACING)
        self.details.pack_start(self.short_lbl, True, True, 0)
        self.details.pack_end(self.details_btn, False, False, 0)
        page.pack_start(self.details, False, False, 0)
        page.reorder_child(self.details, 1)                              # direkt unter der Liste
        set_sensitive(self.details_btn, False)
        return page

    def _build_templates_tab(self, ev):
        """Template-Liste (oder Erklärsatz), Import, Prüfen, Entfernen, Prüfen nach dem Beenden."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=INNER)
        # sichtbare Spalten + base_id + Schriftfarbe (None = Theme)
        self.tpl_store = Gtk.ListStore(*([str] * len(T.TPL_COLUMNS)), int, str)
        self.tpl_view = Gtk.TreeView(model=self.tpl_store)
        fg = len(T.TPL_COLUMNS) + 1
        for i, title in enumerate(T.TPL_COLUMNS):
            self.tpl_view.append_column(sel_fg_column(self.tpl_view, title, i, fg, "teal"))
        self.tpl_view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        tsw = Gtk.ScrolledWindow(min_content_height=120, vexpand=True, shadow_type=Gtk.ShadowType.IN)
        tsw.add(self.tpl_view)
        self.tpl_stack = empty_stack(list_frame(tsw, self.tpl_view, "teal"), T.EMPTY_TEMPLATES)
        page.pack_start(self.tpl_stack, True, True, 0)
        trow = Gtk.Box(spacing=SPACING)
        self.import_btn = Gtk.Button(label=T.BTN_IMPORT)
        self.import_btn.get_style_context().add_class("evox-import-btn")
        self.import_btn.connect("clicked", self.on_import)
        self.verify_btn = fn_class(Gtk.Button(label=T.BTN_VERIFY), "verify")
        self.verify_btn.connect("clicked", self.on_verify)
        self.remove_btn = fn_class(Gtk.Button(label=T.BTN_REMOVE), "remove")
        self.remove_btn.connect("clicked", self.on_remove)
        self.verify_chk = Gtk.CheckButton(label=T.CHK_VERIFY_AFTER, active=ev.s.verify_after_shutdown,
                                          tooltip_text=T.CHK_VERIFY_AFTER_TIP)
        self.verify_chk.connect("toggled", self.on_verify_setting)
        trow.pack_start(self.import_btn, False, False, 0)
        trow.pack_start(self.verify_btn, False, False, 0)
        trow.pack_start(self.remove_btn, False, False, 0)
        trow.pack_end(self.verify_chk, False, False, 0)
        self.tpl_detail = Gtk.Label(label=T.TPL_DETAIL_NONE, xalign=0, wrap=True, selectable=True)
        self.free_lbl = Gtk.Label(xalign=0)
        self.tpl_view.get_selection().connect("changed", lambda *_: (trace("selection_changed", "tpl"), self.update_tpl_detail()))
        page.pack_start(self.tpl_detail, False, False, 0)
        page.pack_start(trow, False, False, 0)
        page.pack_start(self.free_lbl, False, False, 0)
        return page

    def _build_vault_tab(self):
        """Nur lesende Liste der VAULT-* VMs (oder Erklärsatz), Make template, virt-manager öffnen."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING, margin=INNER)
        self.vault_hint = Gtk.Label(label=T.VAULT_HINT, xalign=0, wrap=True)
        self.vault_hint.get_style_context().add_class("evox-vault-hint")
        page.pack_start(self.vault_hint, False, False, 0)
        self.novault_hint = Gtk.Label(label=T.NO_VAULT_HINT, xalign=0, wrap=True, no_show_all=True)
        self.novault_hint.get_style_context().add_class("evox-novault-hint")
        page.pack_start(self.novault_hint, False, False, 0)
        # sichtbare Spalten + Schriftfarbe (None = Theme)
        self.vault_store = Gtk.ListStore(*([str] * len(T.VAULT_COLUMNS)), str)
        self.vault_view = Gtk.TreeView(model=self.vault_store)
        fg = len(T.VAULT_COLUMNS)
        for i, title in enumerate(T.VAULT_COLUMNS):
            self.vault_view.append_column(sel_fg_column(self.vault_view, title, i, fg, "amber"))
        self.vault_view.get_selection().connect("changed", lambda *_: (trace("selection_changed", "vault"), self._sync_vault()))
        vsw = Gtk.ScrolledWindow(min_content_height=120, vexpand=True, shadow_type=Gtk.ShadowType.IN)
        vsw.add(self.vault_view)
        self.vault_stack = empty_stack(list_frame(vsw, self.vault_view), T.EMPTY_VAULTS)
        self.vaults_lbl = self.vault_stack.empty_label
        page.pack_start(self.vault_stack, True, True, 0)
        self.vault_note = Gtk.Label(label=T.VAULT_SELECT, xalign=0, wrap=True)
        page.pack_start(self.vault_note, False, False, 0)
        vrow = Gtk.Box(spacing=SPACING)
        self.make_btn = fn_class(Gtk.Button(label=T.BTN_MAKE), "make")
        self.make_btn.connect("clicked", self.on_make_template)
        self.virt_manager_btn = Gtk.Button(label=T.BTN_VIRT_MANAGER, tooltip_text=T.BTN_VIRT_MANAGER_TIP)
        self.virt_manager_btn.get_style_context().add_class("evox-vault-btn")
        self.virt_manager_btn.connect("clicked", self.on_virt_manager)
        vrow.pack_start(self.make_btn, False, False, 0)
        vrow.pack_end(self.virt_manager_btn, False, False, 0)
        page.pack_start(vrow, False, False, 0)
        page.pack_start(self._build_hint_bar(), False, False, 0)
        self._sync_vault()
        return page

    def _build_hint_bar(self):
        """Goldener Hinweisbalken unter der Knopfzeile (erst nach dem virt-manager-Aufruf sichtbar, bleibt bis ✕)."""
        self.hint_bar = Gtk.EventBox(no_show_all=True)
        self.hint_bar.get_style_context().add_class("evox-hint-bar")
        box = Gtk.Box(spacing=SPACING)
        self.hint_icon = Gtk.Label(label=T.HINT_ICON, valign=Gtk.Align.CENTER)
        self.hint_icon.get_style_context().add_class("evox-hint-icon")
        self.hint_label = Gtk.Label(xalign=0, wrap=True, selectable=False)
        self.hint_label.get_style_context().add_class("evox-hint-text")
        self.hint_label.set_markup(hint_markup())
        self.hint_close = Gtk.Button(label=T.HINT_CLOSE, valign=Gtk.Align.CENTER, tooltip_text=T.HINT_CLOSE_TIP)
        self.hint_close.get_style_context().add_class("evox-hint-close")
        self.hint_close.connect("clicked", lambda *_: self.hint_bar.hide())
        box.pack_start(self.hint_icon, False, False, 0)
        box.pack_start(self.hint_label, True, True, 0)
        box.pack_end(self.hint_close, False, False, 0)
        self.hint_bar.add(box)
        box.show_all()
        return self.hint_bar

    # ---- Fenstergröße
    def _on_window_state(self, _w, event):
        self._maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
        self._set_fullscreen_state(bool(event.new_window_state & Gdk.WindowState.FULLSCREEN))
        return False

    def _set_fullscreen_state(self, on: bool):
        self._fullscreen = on
        self.fullscreen_btn.set_label(T.BTN_FULLSCREEN_EXIT if on else T.BTN_FULLSCREEN)

    # ---- EXIT (0.7.5)
    def exit_candidates(self):
        """Namen der von EVOX verwalteten Wegwerf-VMs (Registry, DISPOSABLE-*); nie VAULT-/TEMPLATE-VMs (R29)."""
        try:
            rows = self.ev.list_temps()
        except Exception:  # noqa: BLE001 – ohne Liste gilt der Stand des letzten Zyklus
            rows = list(self._temp_rows.values())
        return sorted(t["name"] for t in rows if re.fullmatch(config.TEMP_NAME_RE, t["name"]))

    def on_exit(self, _btn=None):
        """EXIT-Knopf: Bestätigungsdialog; nur hier wird entschieden, ob VMs weiterlaufen oder gelöscht werden."""
        names = self.exit_candidates()
        d = ExitDialog(self, names)
        self.exit_dialog = d                       # für Tests erreichbar
        resp = d.run()
        d.destroy()
        return self.exit_response(resp, names)

    def exit_response(self, resp, names):
        if resp == EXIT_ERASE and names:
            self.show(T.MSG_EXIT_ERASING.format(n=len(names)))

            def erase_all():
                failed = []
                for n in names:
                    try:
                        self.ev.stop(n)            # die bestehende Stop-and-erase-Funktion (prüft Eigentum selbst)
                    except Exception as e:  # noqa: BLE001 – jede VM einzeln, Fehler sammeln
                        failed.append(f"{n} ({_err_text(e)})")
                return failed

            def done(failed):
                if failed:
                    self.show(T.MSG_EXIT_FAILED.format(items="; ".join(failed)), bad=True)
                else:
                    self.quit_gui()
            return self._run(erase_all, done)
        if resp in (EXIT_KEEP, Gtk.ResponseType.OK):
            self.quit_gui()
        return None

    def quit_gui(self):
        """GUI schließen: Zustand speichern; destroy beendet den Zeitgeber und schließt den Monitor (_on_destroy)."""
        self.save_geometry()
        self.destroy()

    def toggle_fullscreen(self):
        """Hauptfenster Vollbild an/aus (Knopf, F11); Dialoge bleiben klein."""
        if self._fullscreen:
            self.unfullscreen()
        else:
            self.fullscreen()
        self._set_fullscreen_state(not self._fullscreen)

    def _on_key(self, _w, event):
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.set_focus_visible(True)                   # Tastaturbedienung: Fokus sichtbar (nicht bei Maus)
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
            n = self.tabs.get_n_pages()        # wie beim Notebook: Strg+Bild hoch/runter, ohne Umlauf
            cur = self.tabs.get_current_page() + (1 if event.keyval == Gdk.KEY_Page_Down else -1)
            if 0 <= cur < n:
                self.tabs.set_current_page(cur)
            return True
        if event.keyval == Gdk.KEY_F1:
            self.show_keys()
            return True
        if event.keyval == Gdk.KEY_F11 or (event.keyval == Gdk.KEY_Escape and self._fullscreen):
            self.toggle_fullscreen()
            return True
        return False

    def save_geometry(self):
        """Größe (nicht maximiert) und Maximiert-Zustand speichern; Fehler nur in die Statuszeile."""
        old = self.ev.s.load_gui_state()
        w, h = (old["width"], old["height"]) if self._maximized or self._fullscreen else self.get_size()
        try:
            self.ev.s.save_gui_state(w, h, self._maximized, old["details_expanded"])
        except OSError as e:
            self.show(T.MSG_SETTING_ERR.format(err=e))
        return True

    def backup_color(self):
        """Schrift der -BACKUP-Zeilen (nicht markiert): eigene Wahl (Rolle backup_text) oder Ampel-Rot wie vorher (0.8.2)."""
        return theme.backup_color(self.appearance.get("roles"), self.colors)

    # ---- Anzeige
    def active_template(self):
        it = self.base_combo.get_active_iter()
        return self.base_store[it][0] if it is not None else None

    def refresh_bases(self, select=None):
        """Template-Auswahl neu füllen; Auswahl bleibt (oder `select`, z. B. nach Import). -BACKUP rot."""
        keep = select or self.active_template()
        self.base_store.clear()
        names = sorted({b.name for b in self.ev.reg.bases()})
        for n in names:
            self.base_store.append([n, self.backup_color() if is_backup(n) else None])
        if names:
            self.base_combo.set_active(names.index(keep) if keep in names else 0)

    def refresh_templates(self):
        sel_ids = {r["id"] for r in self.selected_bases()}
        created = {b.id: b.created for b in self.ev.reg.bases()}      # Importzeitpunkt (Registry)
        rows = sorted(self.ev.template_overview(), key=lambda t: (created.get(t["id"], 0), t["id"]), reverse=True)
        self._tpl_rows = {t["id"]: t for t in rows}
        data = []
        for t in rows:                                                  # neueste zuoberst
            red = t["backup"] or t["damaged"]
            fg = self.colors["bad"] if t["damaged"] else self.backup_color()      # beschädigt = feste Warnfarbe
            data.append([t["name"], str(t["version"]), fmt_datetime(created.get(t["id"])),
                         t["firmware"], fmt_size(t["size"]),
                         T.TPL_AGE.format(days=capacity.fmt_dec(t["age_days"])), str(t["in_use"]),
                         T.TPL_DAMAGED if t["damaged"] else T.TPL_OK,
                         t["id"], fg if red else None])
        if data != self._last_data.get("tpl"):                          # nur bei echter Änderung neu aufbauen
            self._last_data["tpl"] = data
            trace("list_rebuild", "tpl")
            self.tpl_store.clear()
            for row in data:
                it = self.tpl_store.append(row)
                if row[8] in sel_ids:
                    trace("select", "tpl")
                    self.tpl_view.get_selection().select_iter(it)
        if not self.tpl_view.get_selection().count_selected_rows():    # Vorauswahl (nur Markierung): neuestes Nicht-BACKUP
            first = next((i for i, t in enumerate(rows) if not t["backup"]), None)
            if first is not None:
                trace("select", "tpl-vorauswahl")
                self.tpl_view.get_selection().select_path(Gtk.TreePath.new_from_indices([first]))
        self._set_child(self.tpl_stack, "list" if rows else "empty")
        try:
            self._set_text(self.free_lbl, T.FREE_LINE.format(free=fmt_size(self.ev.hv.pool_free(config.TEMPLATE_POOL))))
        except Exception:  # noqa: BLE001 – nur Anzeige
            self._set_text(self.free_lbl, T.FREE_UNKNOWN)
        self.update_tpl_detail()

    def update_tpl_detail(self):
        """Herkunft der einzig markierten Kopie: aus welcher Vault (Make template) oder per Import."""
        t = self.selected_base()
        if t is None:
            self._set_text(self.tpl_detail, T.TPL_DETAIL_NONE)
            return
        fmt = T.TPL_ORIGIN_VAULT if t.get("origin") else T.TPL_ORIGIN_IMPORT
        self._set_text(self.tpl_detail, fmt.format(name=t["name"], version=t["version"], vault=t.get("origin"),
                                            date=fmt_datetime(t.get("created")), size=fmt_size(t["size"]),
                                            sha=(t.get("sha256") or "")[:16]))

    def refresh_vaults(self):
        """Reiter VAULT neu füllen (nur lesend); Auswahl bleibt. Nicht kopierbare Zeilen gedämpft."""
        keep = self.selected_vault()
        keep = keep["name"] if keep else None
        rows = self.ev.vault_list()
        self._vault_rows = {v["name"]: v for v in rows}
        data = [[v["name"], v["state_text"], fmt_ram(v["memory_mib"]), fmt_cpus(v["vcpus"]),
                 fmt_size(v["size"]), ", ".join(v["templates"]) or T.VAULT_NONE_MADE, None] for v in rows]
        if data != self._last_data.get("vault"):                        # nur bei echter Änderung neu aufbauen
            self._last_data["vault"] = data
            trace("list_rebuild", "vault")
            self.vault_store.clear()
            for row in data:
                it = self.vault_store.append(row)
                if row[0] == keep:
                    trace("select", "vault")
                    self.vault_view.get_selection().select_iter(it)
        if rows and self.selected_vault() is None:     # Vorauswahl (nur Markierung): erste ausgeschaltete, sonst erste
            first = next((i for i, v in enumerate(rows) if v["state"] == "shutoff"), 0)
            trace("select", "vault-vorauswahl")
            self.vault_view.get_selection().select_path(Gtk.TreePath.new_from_indices([first]))
        set_shown(self.novault_hint, not rows)
        self._set_child(self.vault_stack, "list" if rows else "empty")
        self._sync_vault()

    def selected_vault(self):
        model, it = self.vault_view.get_selection().get_selected()
        return self._vault_rows.get(model[it][0]) if it else None

    def _sync_vault(self):
        """Make template nur bei genau einer markierten, ausgeschalteten, geeigneten Vault; sonst Tooltip mit Grund."""
        v = self.selected_vault()
        if v is None:
            ok, tip, note = False, T.BTN_MAKE_TIP_NONE, T.VAULT_SELECT
        elif v["problem"]:
            ok, tip = False, T.VAULT_PROBLEM.format(problem=v["problem"])
            note = tip
        else:
            ok, tip, note = True, T.BTN_MAKE_TIP, T.VAULT_READY.format(name=v["name"])
        self._set_btn(self.make_btn, ok and not self.busy, tip)
        self._set_text(self.vault_note, note)

    def selected_base(self):
        """Die einzig markierte Zeile (für Prüfen/Start) als dict aus template_overview(), sonst None."""
        rows = self.selected_bases()
        return rows[0] if len(rows) == 1 else None

    def selected_bases(self):
        """Alle markierten Zeilen der Template-Liste (Mehrfachauswahl) als dicts aus template_overview()."""
        model, paths = self.tpl_view.get_selection().get_selected_rows()
        rows = (self._tpl_rows.get(model[p][len(T.TPL_COLUMNS)]) for p in paths)
        return [r for r in rows if r]

    def selected_template(self):
        b = self.selected_base()
        return b["name"] if b else None

    def refresh(self):
        ok, why = self.ev.net_check()
        st = check.guard_status(self.ev.s.guard_status)
        cut = set(st.get("tripped_macs", []))
        if ok:
            set_class(self.status, "evox-lock-bad", False)
            c = self.colors["ok"]
            lock = (colored(T.LOCK_ICON_OK, c) + " " + colored(T.LOCK_LABEL, c, bold=False) + " "
                    + colored(T.LOCK_WORD_OK, c) + ' <span alpha="65%">'
                    + GLib.markup_escape_text(T.LOCK_TAIL_OK) + "</span>")
            set_tooltip(self.status, T.LOCK_TIP)
            set_markup(self.status, lock)
        else:
            set_class(self.status, "evox-lock-bad", True)
            set_tooltip(self.status, T.LOCK_TIP + T.LOCK_TIP_WHY.format(why=why))
            set_text(self.status, T.LOCK_BAD)
        self.lock_ok = ok
        self._vault_known = False
        try:
            self.refresh_vaults()
            self._vault_known = True
        except Exception as e:  # noqa: BLE001 – Vault-Liste darf den Rest nicht aufhalten
            set_text(self.vault_note, T.MSG_ERROR.format(err=_err_text(e)))
        try:
            size = self.ev.s.load_last_start()["memory_mib"]
            cap = capacity.assess(self.ev.meminfo(), size, self.ev.s.host_reserve_mib)
            set_text(self.host_lbl, T.HOST_LINE.format(
                total=gib(cap.total_mib), avail=gib(cap.avail_mib), reserve=gib(cap.reserve_mib),
                maxvms=gib(cap.max_for_vms_mib), room=T.CAP_ROOM.format(n=cap.fits, size=livestats.fmt_ram_gb(size)),
                cpus=max_vcpus(self.ev)))
        except (OSError, KeyError):
            set_text(self.host_lbl, T.HOST_UNKNOWN)
        self.refresh_templates()
        sel = self.selected()
        temps = self.ev.list_temps()
        self._temp_rows = {}
        data = []
        for t in temps:
            if t["net"] == "none":
                mode, lock = T.MODE_COL_OFFLINE, "off"
            elif t["mac"] in cut:
                mode, lock = T.NET_CUT, "cut"
            else:
                mode, lock = T.MODE_COL_INTERNET, "ok" if ok else "bad"
            reg = self.ev.reg.temp(t["name"])
            self._temp_rows[t["name"]] = dict(
                t, mode_text=T.MODE_COL_OFFLINE if t["net"] == "none" else T.MODE_COL_INTERNET, lock=lock,
                overlay=reg.overlay_name if reg else "?")
            data.append([t["name"], t["state"], mode])
        self._has_running = any(t.get("state") == "running" for t in temps)
        self._live = self.read_live(temps)
        try:
            self._pstats = self.ev.s.load_purpose_stats() if temps else {}
        except Exception:  # noqa: BLE001 – Statistik ist nur Hinweis
            self._pstats = {}
        live = {t["name"]: self._live_row(t["name"]) for t in temps}    # Live-Spalten + Ampelfarbe je Zeile
        if data != self._last_data.get("temp"):                         # nur bei echter Änderung neu aufbauen
            self._last_data["temp"] = data
            trace("list_rebuild", "temp")
            self.store.clear()
            for row in data:
                it = self.store.append(row + live[row[0]])
                if row[0] == sel:
                    trace("select", "temp")
                    self.view.get_selection().select_iter(it)
        else:                                                           # Live-Werte: nur geänderte Zellen setzen
            self._update_live_cells()
        self._set_child(self.vm_stack, "list" if temps else "empty")
        self.update_details()
        self._retime()

    def _live_row(self, name) -> list:
        cells, lvl = live_cells(self._live.get(name))
        return list(cells) + [self.colors[RAM_LEVEL_COLOR[lvl]] if lvl else ""]

    def _update_live_cells(self):
        """Live-Spalten in place: set_value nur bei geänderter Zelle (kein Neuaufbau, keine Auswahl-Signale)."""
        for row in self.store:
            for j, val in enumerate(self._live_row(row[0])):
                k = self.live_col + j
                if row[k] != val:
                    trace("list_cell", f"{row[0]} {k}")
                    self.store.set_value(row.iter, k, val)

    def _wants_live(self) -> bool:
        """0.7.4: 1-s-Takt nur, solange eine Wegwerf-VM läuft UND (das Monitorfenster offen ist ODER eine laufende VM
        markiert ist). Sonst 5 s."""
        if not self._has_running:
            return False
        if self.monitor is not None:
            return True
        t = self._temp_rows.get(self.selected())
        return bool(t and t.get("state") == "running")

    def _retime(self):
        """0.7.2: genau ein Zeitgeber; Intervall LIVE_S (1 s) solange eine Wegwerf-VM läuft, sonst REFRESH_S (5 s).
        Wechsel nur bei Zustandsänderung; nach dem Schließen des Fensters (tick_id None) nie neu anlegen."""
        if self._tick_id is None:
            return
        want = LIVE_S if self._wants_live() else REFRESH_S
        if want == self._tick_s:
            return
        GLib.source_remove(self._tick_id)
        self._tick_s = want
        self._tick_id = GLib.timeout_add_seconds(want, self._on_timer)
        trace("tick_interval", str(want))

    def _on_timer(self):
        """Zeitgeber: im 1-s-Takt nur Live-Werte (Thread), der volle Zyklus (reconcile + Listen) bleibt bei 5 s."""
        if self._tick_s == LIVE_S:
            self._live_tick()
            if time.monotonic() - self._full_at < REFRESH_S - LIVE_S / 2:
                return True
        self._tick()
        return True

    def _live_tick(self) -> bool:
        """Liest domain_stats der laufenden eigenen Wegwerf-VMs im Hintergrund-Thread (libvirt blockiert nie die GUI).
        Ist der vorige Lesevorgang noch unterwegs, wird dieser Wert übersprungen (kein Stau, kein zweiter Thread)."""
        if self._live_running:
            trace("live_skip", "busy")
            return False
        names = [n for n, t in self._temp_rows.items() if t.get("state") == "running"]
        if not names:
            return False
        self._live_running = True
        hv = self.ev.hv

        def work():
            try:
                raw = hv.domain_stats(names)
            except Exception as e:  # noqa: BLE001 – Statistik ist nur Anzeige
                raw = e
            GLib.idle_add(self._apply_live, names, raw)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _apply_live(self, names, raw):
        """Ergebnis des Live-Threads im GTK-Thread anwenden; Fehler → Wert überspringen (alte Werte bleiben)."""
        self._live_running = False
        if self._tick_id is None:                                       # Fenster schon zu
            return False
        if not isinstance(raw, dict):
            trace("live_error", _err_text(raw)[:60] if isinstance(raw, Exception) else "no dict")
            return False
        for n in names:
            t = self._temp_rows.get(n)
            if not t or t.get("state") != "running":
                continue
            try:
                self._live[n] = self.live.sample(n, raw.get(n), t.get("memory_mib"), t.get("vcpus"), t.get("created"))
            except Exception as e:  # noqa: BLE001
                trace("live_error", _err_text(e)[:60])
        self._live_at = time.monotonic()
        self._update_live_cells()
        self.update_details()
        return False

    def _live_fresh(self) -> bool:
        """Liefert der 1-s-Takt aktuelle Werte? Dann liest der volle Zyklus nicht noch einmal blockierend."""
        return self._tick_s == LIVE_S and time.monotonic() - self._live_at < 3 * LIVE_S

    def toggle_monitor(self):
        """OPEN/CLOSE DETAILS: Fenster „Live Monitor“ für die markierte VM öffnen oder schließen (höchstens eines;
        nie automatisch)."""
        if self.monitor is not None:
            self.monitor.dismiss()
            return
        name = self.selected()
        if name is None:
            return
        st = self.ev.s.load_gui_state()
        self._mon_target = name
        self.monitor = MonitorWindow(self.colors, st["monitor"], st["monitor_pin"],
                                     on_close=self._save_monitor, on_pin=self._save_monitor_pin)
        self.monitor.connect("destroy", self._on_monitor_destroy)
        self.update_details()                    # Inhalt vor dem Anzeigen setzen (kein Aufblitzen leerer Blöcke)
        self.monitor.present_focused()

    def _save_monitor(self, geo):
        if geo is None:
            return
        try:
            self.ev.s.save_monitor_state(geometry=geo)
        except OSError as e:
            self.show(T.MSG_SETTING_ERR.format(err=e))

    def _save_monitor_pin(self, on):
        try:
            self.ev.s.save_monitor_state(pin=on)
        except OSError as e:
            self.show(T.MSG_SETTING_ERR.format(err=e))

    def _on_monitor_destroy(self, _w):
        self.monitor = None
        if self._tick_id is None:                # Hauptfenster schon zu: nichts mehr anfassen
            return
        self.update_details()                    # Knopf zurück auf OPEN DETAILS, Takt neu bestimmen

    def read_live(self, temps) -> dict:
        """Live-Werte der laufenden Wegwerf-VMs, nur lesend (hv.domain_stats). Jeder Fehler → leere Werte ("n/a");
        die GUI wird nie gestört. Ein Aufruf je Zyklus, nur wenn eine VM läuft."""
        running = [t for t in temps if t.get("state") == "running"]
        self.record_purpose_peaks(self.live.forget(t["name"] for t in running))
        if not running:
            return {}
        names = [t["name"] for t in running]
        if self._live_fresh() and all(n in self._live for n in names):   # 1-s-Takt (Thread) liefert schon: nicht
            return {n: self._live[n] for n in names}                      # noch einmal blockierend lesen
        try:
            raw = self.ev.hv.domain_stats(names)
        except Exception as e:  # noqa: BLE001 – Statistik ist nur Anzeige
            trace("live_error", _err_text(e)[:60])
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        out = {}
        for t in running:
            try:
                out[t["name"]] = self.live.sample(t["name"], raw.get(t["name"]), t.get("memory_mib"),
                                                  t.get("vcpus"), t.get("created"))
            except Exception as e:  # noqa: BLE001
                trace("live_error", _err_text(e)[:60])
        return out

    def record_purpose_peaks(self, gone: dict):
        """Zweck-Statistik (0.7.1): höchste ECHTE RAM-Spitze beendeter VMs je Zweck speichern. Nur Zahlen + Zweckname;
        Fehler stören nie (nur Trace)."""
        for name, summ in (gone or {}).items():
            purpose = livestats.purpose_of(name)
            if purpose and summ.get("peak"):
                try:
                    self.ev.s.record_purpose_peak(purpose, max(1, round(summ["peak"] / 2**20)))
                except Exception as e:  # noqa: BLE001 – Statistik ist nur Hinweis
                    trace("stats_error", _err_text(e)[:60])

    def update_details(self):
        """Kurzzeile + Knopf im Hauptfenster und (falls offen) das Monitorfenster aus den Werten des letzten Zyklus.
        Setter nur bei Änderung: unveränderter Zyklus = 0 GTK-Aufrufe."""
        name = self.selected()
        t = self._temp_rows.get(name)
        self._sync_stop()
        running = bool(t and t.get("state") == "running")
        if running:
            set_markup(self.short_lbl, short_line_markup(self._live.get(name), self.colors))
        else:
            set_text(self.short_lbl, T.SHORT_NOT_RUNNING if t else T.SHORT_NONE)
        label = T.BTN_DETAILS_CLOSE if self.monitor is not None else T.BTN_DETAILS_OPEN
        if self.details_btn.get_label() != label:
            trace("set_label", f"details {label}")
            self.details_btn.set_label(label)
        set_class(self.details_btn, "evox-details-open", self.monitor is not None)
        self._set_btn(self.details_btn, self.monitor is not None or name is not None,
                      T.DETAILS_TIP_CLOSE if self.monitor is not None else T.DETAILS_TIP if name else T.DETAILS_TIP_NONE)
        if self.monitor is not None:
            if name is not None:
                self._mon_target = name              # Markierungswechsel: Monitor folgt; ohne Markierung bleibt er
            mt = self._temp_rows.get(self._mon_target)
            running_mt = bool(mt and mt.get("state") == "running")
            h = ram_hint_text(self.live.summary(self._mon_target)) if running_mt else None
            self.monitor.update(self._mon_target, mt, self._live.get(self._mon_target) if mt else None,
                                self._purpose_starts(self._mon_target) if mt else 0, h[1] if h else None)
        self._retime()

    def _purpose_starts(self, name) -> int:
        """Anzahl Starts des Zwecks (Zweck-Statistik, je Zyklus einmal in refresh gelesen)."""
        return getattr(self, "_pstats", {}).get(livestats.purpose_of(name), {}).get("starts", 0)

    def _sync_stop(self):
        """Stop and erase nur mit Auswahl (und wenn kein Vorgang läuft); sonst Tooltip mit Grund."""
        has = self.selected() is not None
        self._set_btn(self.stop_btn, has and not self.busy, T.BTN_STOP_TIP if has else T.BTN_STOP_TIP_NONE)

    def safe_refresh(self):
        """refresh() im GTK-Thread; Fehler (z. B. libvirt weg) in die Statuszeile statt ins Terminal."""
        try:
            self.refresh()
        except Exception as e:  # noqa: BLE001 – GUI soll weiterlaufen
            self.show(T.MSG_REFRESH_ERROR.format(err=_err_text(e)), bad=True)
        self._sync_howto()
        self._cycle += 1
        trace_cycle(self._cycle)

    def _tick(self):
        self._full_at = time.monotonic()
        if not self.busy and not self._tick_running:
            self._tick_running = True           # Hintergrundlauf: Knöpfe bleiben unberührt (kein Aus/Ein pro Zyklus)
            self._run(self.ev.reconcile, lambda acts: self.show("; ".join(acts)) if acts else None, quiet=True)
        return True

    def selected(self):
        model, it = self.view.get_selection().get_selected()
        return model[it][0] if it else None

    def show(self, text, bad=False):
        """Statuszeile; bad=True → rote, fette Warnung (Farbe passend zum Theme)."""
        if bad:
            self.msg.set_markup(colored(text, self.colors["bad"]))
        else:
            self.msg.set_text(text)

    def show_vm(self, name, opener=None):
        """VM-Fenster öffnen; Fehler sofort oder nach VIEWER_CHECK_S Sekunden in die Statuszeile."""
        try:
            proc, err = (opener or open_console)(name)       # open_console erst hier auflösen (Tests tauschen es aus)
        except Exception as e:  # noqa: BLE001
            self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            return None

        # 0.7.0: genau EINE Prüfung je Fenster. Bis 0.6.21 konnte check_viewer zweimal laufen (direkter Aufruf +
        # Zeitgeber); der zweite Lauf las aus der schon geschlossenen stderr-Datei → "ValueError: seek of closed file".
        # Jetzt: der erste Aufruf entfernt den Zeitgeber, weitere Aufrufe tun nichts; Lesefehler stören die GUI nicht.
        state = {"src": None, "done": False}

        def check_viewer(from_timer=False):
            if state["done"]:
                return False
            state["done"] = True
            src, state["src"] = state["src"], None
            self._viewer_checks.pop(src, None)
            if src is not None and not from_timer:
                GLib.source_remove(src)                    # direkter Aufruf vor Ablauf: Zeitgeber nicht mehr nötig
            try:
                text = viewer_error(proc, err)
            except (OSError, ValueError):
                text = ""
            finally:
                err.close()
            if text and self._tick_id is not None:     # Fenster noch offen
                self.show(text)
            return False
        state["src"] = GLib.timeout_add_seconds(VIEWER_CHECK_S, check_viewer, True)
        self._viewer_checks[state["src"]] = check_viewer
        check_viewer.state = state
        return check_viewer

    # ---- Fortschritt für lange Vorgänge (Import, Prüfen): Balken pulsiert, Phase + Laufzeit
    def start_progress(self, phase, name):
        self._t0 = time.monotonic()
        self._fraction = None
        self._phase_text = T.PHASE[phase].format(name=name)
        self.progress.show()
        self._update_progress()
        if self._progress_timer is None:
            self._progress_timer = GLib.timeout_add(PULSE_MS, self._update_progress)

    def set_phase(self, phase, name, fraction=None):
        """Aus dem Arbeits-Thread nur über GLib.idle_add aufrufen. fraction 0..1 = Anteil (sonst pulsierend)."""
        if self._cancel is not None and self._cancel.is_set():
            return False                     # Text „Cancelling …“ bleibt stehen
        self._phase_text = T.PHASE[phase].format(name=name)
        self._fraction = fraction
        self._update_progress()
        return False

    def _update_progress(self):
        el = int(time.monotonic() - self._t0)
        elapsed = f"{el // 60}:{el % 60:02d}"
        if self._fraction is None:
            self.progress.set_text(T.PROGRESS.format(phase=self._phase_text, elapsed=elapsed))
            self.progress.pulse()
        else:
            self.progress.set_fraction(self._fraction)
            self.progress.set_text(T.PROGRESS_PCT.format(phase=self._phase_text, pct=int(self._fraction * 100),
                                                         elapsed=elapsed))
        return True

    def stop_progress(self):
        if self._progress_timer is not None:
            GLib.source_remove(self._progress_timer)
            self._progress_timer = None
        self.progress.hide()
        self.cancel_copy_btn.hide()
        self._cancel = None
        self._fraction = None

    # ---- Aktionen im Hintergrund (libvirt blockiert)
    # Start, Stop und Reconcile laufen in einem Arbeits-Thread; refresh() und alle
    # Widget-Zugriffe nur im GTK-Thread (über GLib.idle_add). Die Registry öffnet je
    # Thread eine eigene SQLite-Verbindung; der Arbeits-Thread schließt seine am Ende.
    def _run(self, fn, done=None, quiet=False):
        """Vorgang im Hintergrund. quiet=True (5-s-Zeitgeber): `busy` und Knopfzustände bleiben unberührt; die Sperre
        gegen gleichzeitige Vorgänge liegt unverändert in lifecycle (Lock). Ursache des Flackerns bis 0.6.13: der
        Zeitgeber schaltete alle Aktionsknöpfe samt Make template alle 5 s aus und wieder ein."""
        if not quiet:
            self.busy = True
            for b in self.action_btns:
                set_sensitive(b, False)
            set_sensitive(self.make_btn, False)

        def work():
            try:
                res, err = fn(), None
            except Exception as e:  # noqa: BLE001 – jeder Fehler muss in die Statuszeile
                res, err = None, e
            finally:
                self.ev.reg.close()
            GLib.idle_add(finish, res, err)

        def finish(res, err):
            if quiet:
                self._tick_running = False
            else:
                self.busy = False
                self.stop_progress()
                for b in self.action_btns:
                    set_sensitive(b, True)
            self._sync_stop()
            self._sync_vault()
            if isinstance(err, Cancelled):
                self.show(str(err))
            elif err:
                self.show(T.MSG_ERROR.format(err=_err_text(err)), bad=True)
            elif done:
                try:
                    done(res)
                except Exception as e:  # noqa: BLE001
                    self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            self.safe_refresh()
            return False

        t = threading.Thread(target=work, daemon=True)
        t.start()
        return t

    def on_start(self, _btn, offline=False):
        """Beide Start-Knöpfe öffnen denselben Dialog; der Knopf legt den Modus fest."""
        template = self.active_template()
        if not template:
            self.show(T.MSG_NO_TEMPLATE)
            return None
        d = StartDialog(self, self.ev, template, offline=offline)
        resp = d.run()
        purpose, mem, cpus, shown, remember = d.purpose_text, d.memory_mib, d.vcpus, d.vm_name, d.remember
        d.destroy()
        if resp != Gtk.ResponseType.OK:
            return None
        self.save_remember(purpose, mem, remember)
        return self.start_vm(template, purpose, mem, cpus, offline, expect_name=shown)

    def save_remember(self, purpose, mem, remember):
        """Haken an: RAM für den Zweck merken; Haken aus: gemerkten Wert vergessen. Fehler nur melden, Start geht weiter."""
        try:
            self.ev.s.remember_ram(purpose_name(purpose), mem if remember else None)
        except EvoxError:
            pass
        except OSError as e:
            self.show(T.MSG_REMEMBER_FAILED.format(err=_err_text(e)), bad=True)

    def start_vm(self, template, purpose, mem, cpus, offline, opener=None, expect_name=None):
        """Im Arbeits-Thread exakt Evox.start (wie `evoxd start [--no-net]`), danach VM-Fenster öffnen."""
        self.show(T.MSG_STARTING)

        def done(r):
            try:
                self.ev.s.count_purpose_start(livestats.purpose_of(r.name))   # Zweck-Statistik (nur Zähler)
            except Exception as e:  # noqa: BLE001 – Statistik ist nur Hinweis
                trace("stats_error", _err_text(e)[:60])
            net = T.MSG_STARTED_NET if r.net else T.MSG_STARTED_NONET
            self.show(" ".join([T.MSG_STARTED.format(name=r.name, net=net)] + r.warnings))
            self.show_vm(r.name, opener=opener)

        def work():
            # nie stillschweigend einen anderen Namen als den angezeigten starten
            if expect_name is not None:
                now = next_free_name(self.ev, purpose)
                if now != expect_name:
                    raise EvoxError(T.MSG_NAME_CHANGED.format(shown=expect_name, now=now))
            r = self.ev.start(template, purpose=purpose, want_net=not offline, memory_mib=mem, vcpus=cpus)
            if expect_name is not None and r.name != expect_name:
                r.warnings.append(T.MSG_NAME_DIFFERS.format(shown=expect_name, name=r.name))
            return r
        return self._run(work, done)

    def on_import(self, _btn):
        try:
            d = ImportDialog(self, self.ev)
        except Exception as e:  # noqa: BLE001 – libvirt nicht erreichbar o. ä.
            self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            return
        resp = d.run()
        c = d.selected()
        d.destroy()
        if resp == Gtk.ResponseType.OK and c and confirm_import(self, c):
            self.import_template(c["name"])

    def import_template(self, name):
        """Im Arbeits-Thread exakt Evox.import_template (wie `evoxd template-import`)."""
        self.start_progress("check", name)

        def work():
            bid = self.ev.import_template(name, progress=lambda p: GLib.idle_add(self.set_phase, p, name))
            b = self.ev.reg.base(bid)
            try:
                size = fmt_size(self.ev.hv.vol_size(b.vol_path)[1])
            except Exception:  # noqa: BLE001 – nur Anzeige
                size = "?"
            return b, size

        def done(res):
            b, size = res
            self.refresh_bases(select=b.name)
            self.show(T.MSG_IMPORTED.format(name=b.name, version=b.version, sha=b.sha256[:16], size=size))
        return self._run(work, done)

    # ---- Vaults: Make template (nur ausgeschaltete VAULT-*, Original bleibt unverändert)
    def on_make_template(self, _btn):
        v = self.selected_vault()
        if v is None or v["problem"]:
            self.show(T.BTN_MAKE_TIP_NONE if v is None else T.VAULT_PROBLEM.format(problem=v["problem"]))
            return None
        try:
            plan = self.ev.make_template_plan(v["name"])
        except Exception as e:  # noqa: BLE001 – Zustand inzwischen geändert, libvirt weg o. ä.
            self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            self.safe_refresh()
            return None
        d = MakeTemplateDialog(self, self.ev, plan)
        self.make_dialog = d                       # für Tests erreichbar
        resp = d.run()
        ok, name = d.update(), d.name_text
        d.destroy()
        if resp == Gtk.ResponseType.OK and ok:
            return self.make_template(v["name"], name)
        return None

    def make_template(self, vault, name):
        """Im Arbeits-Thread Evox.make_template; Fortschritt in Prozent (geschätzt) mit Abbrechen-Knopf."""
        self._cancel = cancel = threading.Event()
        self.start_progress("check", vault)
        self.cancel_copy_btn.show()
        self.cancel_copy_btn.set_sensitive(True)

        def work():
            bid = self.ev.make_template(vault, name, cancel=cancel,
                                        progress=lambda p, f=None: GLib.idle_add(self.set_phase, p, vault, f))
            return self.ev.reg.base(bid), self.ev.reg.origin(self.ev.reg.base(bid).vol_name)

        def done(res):
            b, o = res
            self.refresh_bases(select=b.name)
            self.show(T.MSG_MADE.format(name=b.name, version=b.version, vault=vault,
                                        size=fmt_size(o.size if o else None), sha=b.sha256[:16]))
        return self._run(work, done)

    def on_cancel_copy(self, _btn):
        if self._cancel is not None:
            self._cancel.set()
            self.cancel_copy_btn.set_sensitive(False)
            self._phase_text = T.MSG_CANCELLING
            self._fraction = None
            self._update_progress()
            self.show(T.MSG_CANCELLING)

    def on_virt_manager(self, _btn, opener=None):
        """virt-manager öffnen (open_virt_manager erst hier auflösen; Tests tauschen es aus)."""
        try:
            (opener or open_virt_manager)()
        except Exception as e:  # noqa: BLE001
            self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            return
        self.show("")
        self.hint_bar.show()

    def offer_orphan_cleanup(self, ask=None):
        """Beim Start: unfertige Kopien früherer Läufe nennen und nach Bestätigung löschen (nie automatisch)."""
        try:
            orphans = self.ev.orphan_copies()
        except Exception as e:  # noqa: BLE001
            self.show(T.MSG_ERROR.format(err=_err_text(e)), bad=True)
            return False
        if not orphans:
            return False
        text = T.ORPHAN_TEXT.format(list="\n".join(
            T.ORPHAN_LINE.format(vol=o["vol_name"], vault=o["vault"], date=fmt_datetime(o["started"]),
                                 missing="" if o["exists"] else T.ORPHAN_MISSING) for o in orphans))
        if (ask or self._ask)(T.ORPHAN_TITLE, text):
            self._run(self.ev.remove_orphans,
                      lambda removed: self.show(T.MSG_ORPHANS_REMOVED.format(list=", ".join(removed))))
        else:
            self.show(T.MSG_ORPHANS_KEPT)
        return False

    def _ask(self, title, text) -> bool:
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.YES_NO, text=title)
        d.format_secondary_text(text)
        style_responses(d, Gtk.ResponseType.YES, "evox-fn-remove", Gtk.ResponseType.NO)
        secure_dialog(d, Gtk.ResponseType.NO)
        resp = d.run()
        d.destroy()
        return resp == Gtk.ResponseType.YES

    def on_verify(self, _btn):
        row = self.selected_base()
        if not row:
            self.show(T.MSG_SELECT_TEMPLATE)
            return
        self.start_progress("checksum", row["name"])

        def done(ok):
            self.show_verify_result(row["name"], row["version"], ok)
            self.refresh_bases()
        return self._run(lambda: self.ev.verify_base(row["id"]), done)   # die gewählte Version

    def show_verify_result(self, name, version, ok):
        self.show((T.MSG_VERIFY_OK if ok else T.MSG_VERIFY_BAD).format(name=name, version=version), bad=not ok)

    # ---- Prüfung nach dem Beenden (Einstellung, Standard aus): eigener Thread, sperrt keine Knöpfe
    def on_verify_setting(self, chk):
        self.ev.s.verify_after_shutdown = chk.get_active()
        try:
            self.ev.s.save_option("verify_after_shutdown", chk.get_active())
        except OSError as e:
            self.show(T.MSG_SETTING_ERR.format(err=e), bad=True)

    def _after_destroy(self, base_id):
        """GTK-Thread (über idle_add aus Evox.on_temp_destroyed)."""
        if self.ev.s.verify_after_shutdown:
            self.auto_verify(base_id)
        return False

    def auto_verify(self, base_id):
        """template-verify der Kopie im Hintergrund; Ergebnis in der Statuszeile. Gibt den Thread zurück."""
        b = self.ev.reg.base(base_id)
        if b is None or base_id in self._verifying:
            return None
        self._verifying.add(base_id)
        self.show(T.MSG_AUTO_VERIFY.format(name=b.name, version=b.version))

        def work():
            try:
                res, err = self.ev.verify_base(base_id), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            finally:
                self.ev.reg.close()
            GLib.idle_add(finish, res, err)

        def finish(ok, err):
            self._verifying.discard(base_id)
            if err is not None:
                self.show(T.MSG_AUTO_VERIFY_ERR.format(err=_err_text(err)), bad=True)
            else:
                self.show_verify_result(b.name, b.version, ok)
            self.refresh_bases()
            self.safe_refresh()
            return False

        t = threading.Thread(target=work, daemon=True)
        t.start()
        return t

    # ---- Entfernen
    def on_remove(self, _btn):
        rows = self.selected_bases()
        if not rows:
            self.show(T.MSG_SELECT_TEMPLATE)
            return None
        d = RemoveDialog(self, rows)
        resp = d.run()
        d.destroy()
        if resp == Gtk.ResponseType.OK:
            return self.remove_templates([(r["name"], r["version"]) for r in rows])
        return None

    def remove_templates(self, copies):
        """Im Arbeits-Thread je Kopie exakt Evox.remove_template (wie `evoxd template-remove`);
        verweigerte Kopien (z. B. in Benutzung) werden benannt, die übrigen trotzdem entfernt."""
        def work():
            removed, refused = [], []
            for name, version in copies:
                try:
                    removed.extend(self.ev.remove_template(name, version=version))
                except EvoxError as e:
                    refused.append(f"{name} v{version}: {e}")
            return removed, refused

        def done(res):
            removed, refused = res
            self.refresh_bases()
            ok = T.MSG_REMOVED.format(list=", ".join(f"{b.name} v{b.version}" for b in removed)) if removed else ""
            if refused:
                self.show(" ".join(x for x in (ok, T.MSG_REFUSED.format(list=" | ".join(refused))) if x), bad=True)
            else:
                self.show(ok)
        return self._run(work, done)

    def on_console(self, _btn):
        name = self.selected()
        if not name:
            self.show(T.MSG_SELECT_FIRST)
            return
        self.show(T.MSG_OPENING.format(name=name))
        self.show_vm(name)

    def _add_ram_hint(self, d, name):
        """0.7.1: eine Zeile mit Ampel + Klartext (nur Information) und Opt-in-Knopf „Remember … for <Zweck>“.
        Ohne echte Gastwerte kein Hinweis (nichts geraten). Bestätigungsablauf und Anfangsfokus bleiben unverändert."""
        try:
            hint = ram_hint_text(self.live.summary(name))
        except Exception as e:  # noqa: BLE001 – Hinweis darf den Dialog nie stören
            trace("hint_error", _err_text(e)[:60])
            hint = None
        d.ram_hint = d.remember_btn = None                  # für Tests erreichbar
        if hint is None:
            return
        lvl, text, sug = hint
        box = Gtk.Box(spacing=SPACING)
        lbl = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        lbl.set_markup(colored(text, self.colors[RAM_LEVEL_COLOR[lvl]], bold=True))
        box.pack_start(lbl, True, True, 0)
        purpose = livestats.purpose_of(name)
        if sug and purpose:
            btn = fn_class(Gtk.Button(label=T.HINT_REMEMBER.format(sug=livestats.fmt_ram_gb(sug), purpose=purpose)),
                           "aux")
            btn.set_tooltip_text(T.HINT_REMEMBER_TIP)
            btn.connect("clicked", self._on_hint_remember, purpose, sug)
            box.pack_start(btn, False, False, 0)
            d.remember_btn = btn
        d.get_message_area().pack_start(box, False, False, 0)
        box.show_all()
        d.ram_hint = lbl

    def _on_hint_remember(self, btn, purpose, sug):
        """Setzt nur die gemerkte RAM-Größe des Zwecks (Mechanismus aus 0.7.0; Startdialog begrenzt weiter auf die
        Kapazität). Ändert weder die VM noch die Bestätigung."""
        try:
            self.ev.s.remember_ram(purpose, sug)
            btn.set_label(T.HINT_REMEMBERED.format(sug=livestats.fmt_ram_gb(sug), purpose=purpose))
            btn.set_sensitive(False)
        except OSError as e:
            btn.set_label(T.MSG_REMEMBER_FAILED.format(err=_err_text(e)))

    def on_stop(self, _btn):
        name = self.selected()
        if not name:
            self.show(T.MSG_SELECT_FIRST)
            return
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE)
        d.set_markup(T.STOP_TEXT.format(name=GLib.markup_escape_text(name)))
        d.add_button(T.STOP_CANCEL, Gtk.ResponseType.CANCEL).get_style_context().add_class("evox-cancel")
        d.add_button(T.STOP_CONFIRM, Gtk.ResponseType.OK).get_style_context().add_class("evox-danger")
        self._add_ram_hint(d, name)
        secure_dialog(d)
        self.stop_dialog = d                       # für Tests erreichbar
        resp = d.run()
        d.destroy()
        if resp == Gtk.ResponseType.OK:
            self._run(lambda: self.ev.stop(name), lambda _r: self.show(T.MSG_ERASED.format(name=name)))


RESET_COLORS_ENV = "EVOXD_RESET_COLORS"


def reset_colors(storage) -> bool:
    """Notbremse (EVOXD_RESET_COLORS=1): Konfig sichern, dann Aussehen auf Standard. True bei Erfolg/nichts zu tun."""
    path = storage.config_file or storage.config_path()
    try:
        if path.exists():
            shutil.copy2(path, path.with_name(f"{path.name}.colors-{int(time.time())}"))
        storage.save_option(theme.KEY, theme.default_appearance())
    except OSError as e:
        print(f"EVOX: could not reset colors: {e}", file=sys.stderr)
        return False
    return True


def offer_setup_without_libvirt():
    """libvirt nicht erreichbar (z. B. Pakete fehlen): den Setup check ohne Evox anbieten (0.10.0)."""
    try:
        d = SetupDialog(None, None)
    except Exception:  # noqa: BLE001 – ohne Display bleibt es bei der Meldung
        return
    d.start_check()
    d.run()
    d.destroy()


def main(argv=None):
    no_core_dumps()
    Gtk.Window.set_default_icon_name(ICON_NAME)
    try:
        ev = open_evox()
    except Exception as e:  # libvirt nicht erreichbar o. ä.
        print(f"EVOX cannot start: {e}", file=sys.stderr)
        offer_setup_without_libvirt()
        return 1
    if os.environ.get(RESET_COLORS_ENV) == "1" and not reset_colors(ev.s):
        return 1
    w = MainWindow(ev)
    w.connect("destroy", Gtk.main_quit)
    w.show_all()
    GLib.idle_add(w.offer_orphan_cleanup)
    GLib.idle_add(w.startup_setup_check)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

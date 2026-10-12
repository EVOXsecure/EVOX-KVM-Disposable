#!/usr/bin/env python3
"""Baut docs/manual/<stem>.{en,de}.html aus den .md-Quellen (A7a/A7b): quick-guide, full-manual, developer-doc (nur EN).
Nur Standardbibliothek, kein Netz. Aufruf: python3 tools/build_manual.py
Unterstützt: # ## ### Überschriften, Absätze, 1. Listen, - Listen, Tabellen, **fett**, *kursiv*, `code`, Codeblöcke, {{svg:name}}.
Lange Dokumente (alles außer quick-guide): eine Spalte, mehrseitig druckbar."""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "manual"
sys.path.insert(0, str(ROOT / "src"))
from evoxd import theme as _theme  # noqa: E402  (nur Farbtabellen, keine GTK-Abhängigkeit)

EASY = {"easy-guide"}                       # einseitig, eine Spalte, große Schrift (A7c)
SHORT = {"quick-guide"} | EASY              # einseitig; quick-guide zweispaltig; alle anderen: lang, eine Spalte
NO_SWITCH = {"developer-doc"}               # nur Englisch: kein Sprachumschalter
C = {"vault": "#D4AF37", "tpl": "#00F0FF", "net": "#39D353", "off": "#0060b3", "title": "#8c00ff",
     "bad": "#c93a3a", "bg": "#1b1b24", "fg": "#f2f2f2", "mute": "#a9acc0"}

L = {  # sichtbare Texte der Grafiken je Sprache
    "en": dict(flow_t="Flow 1–4", flow_d="Data flow", vault="1 VAULT", vault_s="your VM, set up once", tpl="2 TEMPLATE", tpl_s="protected clean copy",
               disp="3 DISPOSABLE", disp_s="start / stop tab", start="4 START", internet="INTERNET", offline="OFFLINE",
               life_t="What happens at start and end", l1="Template", l1s="read-only source", l2="Encrypted overlay", l2s="LUKS, key in memory only",
               l3="Network lock", l3s="before the VM runs", l4="You work", l4s="in the VM", l5="Stop and erase", l5s="overlay + key gone",
               vm="Disposable VM", inet="Internet", ok="reachable", host="Host", router="Router / home network", others="Other VMs",
               clip="Clipboard", blocked="blocked", note="H1, confirmed on the host: router, host, another VM, multicast, broadcast blocked.",
               note2="Internet and DNS (Quad9) work. VM has no IPv6. netcheck ok.",
               ui=dict(lang="Deutsch", other="de", toc="Contents", search="Search…", theme="Light / dark", close="Close this tab to return to EVOX.", ver="EVOX KVM DISPOSABLE {v}"),
               lv_t="Security levels (no numbers, only steps)", l_1="Normal Linux", l_1s="programs share one system",
               l_2="EVOX", l_2s="work in a throw-away VM, network lock, erased", l_3="Qubes OS", l_3s="every task in its own isolated VM",
               rm_t="Risk matrix: who covers what", rm_cols=("EVOX does", "You do", "Open limit"),
               rm_rows=("Clipboard leaks", "Data left on disk", "Dirty template", "Wrong mode", "Lost downloads / passwords", "Crash or power loss", "Limits of the host"),
               rm_leg="✔ covered   ! action needed   ✕ not covered by EVOX", sw_t="Theme colors (from theme.py)",
               sw_roles=("Title", "VAULT", "TEMPLATE", "DISPOSABLE", "OFFLINE", "Step 2", "EXIT"),
               more="stronger", lim="EVOX limits: group libvirt, X11, VAULT without network lock, host kernel"),
    "de": dict(flow_t="Ablauf 1–4", flow_d="Datenfluss", vault="1 VAULT", vault_s="deine VM, einmal eingerichtet", tpl="2 TEMPLATE", tpl_s="geschützte saubere Kopie",
               disp="3 DISPOSABLE", disp_s="Reiter Start / Ende", start="4 START", internet="INTERNET", offline="OFFLINE",
               life_t="Was beim Start und Ende passiert", l1="Template", l1s="nur lesbare Quelle", l2="Verschlüsseltes Overlay", l2s="LUKS, Schlüssel nur im RAM",
               l3="Netzsperre", l3s="bevor die VM läuft", l4="Du arbeitest", l4s="in der VM", l5="Stop and erase", l5s="Overlay + Schlüssel weg",
               vm="Wegwerf-VM", inet="Internet", ok="erreichbar", host="Host", router="Router / Heimnetz", others="Andere VMs",
               clip="Zwischenablage", blocked="gesperrt", note="H1, am Host bestätigt: Router, Host, andere VM, Multicast, Broadcast gesperrt.",
               note2="Internet und DNS (Quad9) gehen. VM ohne IPv6. netcheck ok.",
               ui=dict(lang="English", other="en", toc="Inhalt", search="Suchen…", theme="Hell / dunkel", close="Schließe diesen Tab, um zu EVOX zurückzukehren.", ver="EVOX KVM DISPOSABLE {v}"),
               lv_t="Sicherheitsstufen (keine Zahlen, nur Stufen)", l_1="Normales Linux", l_1s="Programme teilen sich ein System",
               l_2="EVOX", l_2s="Arbeit in Wegwerf-VM, Netzsperre, gelöscht", l_3="Qubes OS", l_3s="jede Aufgabe in eigener isolierter VM",
               rm_t="Risiko-Matrix: wer deckt was ab", rm_cols=("EVOX macht", "Du machst", "Offene Grenze"),
               rm_rows=("Zwischenablage", "Daten auf der Platte", "Unsauberes Template", "Falscher Modus", "Verlorene Downloads / Passwörter", "Absturz oder Stromausfall", "Grenzen des Hosts"),
               rm_leg="✔ abgedeckt   ! Handlung nötig   ✕ von EVOX nicht abgedeckt", sw_t="Theme-Farben (aus theme.py)",
               sw_roles=("Titel", "VAULT", "TEMPLATE", "DISPOSABLE", "OFFLINE", "Schritt 2", "EXIT"),
               more="stärker", lim="Grenzen von EVOX: Gruppe libvirt, X11, VAULT ohne Netzsperre, Host-Kernel"),
}


def _box(x, y, w, h, fill, txt, title, sub, tc="#111"):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}"/>'
            f'<text x="{x + w / 2}" y="{y + 17}" text-anchor="middle" font-weight="bold" font-size="12" fill="{tc}">{html.escape(title)}</text>'
            f'<text x="{x + w / 2}" y="{y + 31}" text-anchor="middle" font-size="9" fill="{tc}">{html.escape(sub)}</text>')


def _arrow(x1, y1, x2, y2, col="#fff"):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2" marker-end="url(#ah)"/>'


def _svg(body, w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}" '
            f'font-family="sans-serif"><title>{html.escape(title)}</title>'
            '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#fff"/></marker></defs>'
            f'<rect width="{w}" height="{h}" rx="6" fill="{C["bg"]}"/>{body}</svg>')


def svg_flow(t):
    b = _box(8, 8, 100, 40, C["vault"], 0, t["vault"], t["vault_s"], "#1a1400") + _arrow(110, 28, 126, 28)
    b += _box(128, 8, 100, 40, C["tpl"], 0, t["tpl"], t["tpl_s"], "#001a1c") + _arrow(230, 28, 246, 28)
    b += _box(248, 8, 100, 40, C["net"], 0, t["disp"], t["disp_s"], "#04210c") + _arrow(350, 28, 366, 28)
    b += (f'<rect x="368" y="8" width="104" height="19" rx="5" fill="{C["net"]}"/><text x="420" y="21" text-anchor="middle" font-size="10" font-weight="bold" fill="#04210c">4 START · {t["internet"]}</text>'
          f'<rect x="368" y="29" width="104" height="19" rx="5" fill="{C["off"]}"/><text x="420" y="42" text-anchor="middle" font-size="10" font-weight="bold" fill="#fff">4 START · {t["offline"]}</text>')
    return _svg(b, 480, 56, t["flow_t"])


def svg_life(t):
    xs = [6, 100, 194, 288, 382]
    cols = [C["tpl"], "#8c6bd6", "#d8a02a", C["net"], C["bad"]]
    keys = [("l1", "l1s"), ("l2", "l2s"), ("l3", "l3s"), ("l4", "l4s"), ("l5", "l5s")]
    b = ""
    for i, (x, c, (k, ks)) in enumerate(zip(xs, cols, keys)):
        tc = "#fff" if c in (C["bad"], "#8c6bd6") else "#111"
        b += f'<rect x="{x}" y="8" width="84" height="46" rx="6" fill="{c}"/>'
        b += f'<text x="{x + 42}" y="26" text-anchor="middle" font-size="10" font-weight="bold" fill="{tc}">{html.escape(t[k])}</text>'
        b += f'<text x="{x + 42}" y="42" text-anchor="middle" font-size="8" fill="{tc}">{html.escape(t[ks])}</text>'
        if i < 4:
            b += _arrow(x + 85, 31, x + 97, 31)
    return _svg(b, 480, 62, t["life_t"])


def svg_flowdata(t):
    b = (f'<rect x="150" y="38" width="100" height="40" rx="6" fill="{C["net"]}"/>'
         f'<text x="200" y="62" text-anchor="middle" font-size="12" font-weight="bold" fill="#04210c">{html.escape(t["vm"])}</text>')
    b += _arrow(252, 58, 318, 58, C["net"])
    b += (f'<rect x="320" y="38" width="100" height="40" rx="6" fill="none" stroke="{C["net"]}" stroke-width="2"/>'
          f'<text x="370" y="56" text-anchor="middle" font-size="12" font-weight="bold" fill="{C["net"]}">{html.escape(t["inet"])}</text>'
          f'<text x="370" y="70" text-anchor="middle" font-size="9" fill="{C["fg"]}">{html.escape(t["ok"])}</text>')
    items = [("host", 6), ("router", 96), ("others", 186), ("clip", 276)]
    for key, x in items:
        b += f'<line x1="200" y1="80" x2="{x + 40}" y2="102" stroke="{C["bad"]}" stroke-width="1.5" stroke-dasharray="4 3"/>'
        b += (f'<rect x="{x}" y="102" width="86" height="26" rx="5" fill="none" stroke="{C["bad"]}" stroke-width="2"/>'
              f'<text x="{x + 43}" y="113" text-anchor="middle" font-size="9" font-weight="bold" fill="{C["fg"]}">{html.escape(t[key])}</text>'
              f'<text x="{x + 43}" y="124" text-anchor="middle" font-size="8" fill="#ff8a8a">✕ {html.escape(t["blocked"])}</text>')
    b += f'<text x="8" y="143" font-size="8.5" fill="{C["mute"]}">{html.escape(t["note"])}</text>'
    b += f'<text x="8" y="154" font-size="8.5" fill="{C["mute"]}">{html.escape(t["note2"])}</text>'
    return _svg(b, 480, 160, t["flow_d"])


def svg_levels(t):
    b = ""
    for i, (k, col, tc) in enumerate((("l_1", "#7d8191", "#fff"), ("l_2", C["net"], "#04210c"), ("l_3", C["title"], "#fff"))):
        h = 30 + i * 18
        x = 8 + i * 154
        b += f'<rect x="{x}" y="{74 - h + 6}" width="146" height="{h}" rx="6" fill="{col}"/>'
        b += f'<text x="{x + 73}" y="{74 - h + 22}" text-anchor="middle" font-size="12" font-weight="bold" fill="{tc}">{i + 1}  {html.escape(t[k])}</text>'
        if i == 0:
            b += f'<text x="{x + 73}" y="{74 - h + 36}" text-anchor="middle" font-size="8" fill="{tc}">{html.escape(t["l_1s"])}</text>'
        else:
            b += f'<text x="{x + 73}" y="{74 - h + 36}" text-anchor="middle" font-size="8" fill="{tc}">{html.escape(t[k + "s"])}</text>'
    b += f'<text x="8" y="94" font-size="8.5" fill="{C["mute"]}">→ {html.escape(t["more"])}   ·   {html.escape(t["lim"])}</text>'
    return _svg(b, 480, 100, t["lv_t"])



def svg_risk(t):
    # Zeilen: (EVOX, Du, Grenze) mit "y" abgedeckt, "a" Handlung, "n" nicht abgedeckt, "" leer – belegt durch die Risikotabelle im Handbuch
    cells = (("y", "", ""), ("y", "a", ""), ("y", "a", ""), ("", "a", ""), ("", "a", ""), ("y", "a", ""), ("", "a", "n"))
    sym = {"y": ("✔", C["net"]), "a": ("!", "#d8a02a"), "n": ("✕", "#ff7b72"), "": ("·", C["mute"])}
    x0, cw, rh = 190, 94, 20
    b = ""
    for j, name in enumerate(t["rm_cols"]):
        b += f'<text x="{x0 + j * cw + cw / 2}" y="20" text-anchor="middle" font-size="10" font-weight="bold" fill="{C["fg"]}">{html.escape(name)}</text>'
    for i, (row, cs) in enumerate(zip(t["rm_rows"], cells)):
        y = 30 + i * rh
        b += f'<rect x="6" y="{y}" width="468" height="{rh - 2}" rx="4" fill="#26263a"/>'
        b += f'<text x="12" y="{y + 13}" font-size="10" fill="{C["fg"]}">{html.escape(row)}</text>'
        for j, c in enumerate(cs):
            ch, col = sym[c]
            b += f'<text x="{x0 + j * cw + cw / 2}" y="{y + 14}" text-anchor="middle" font-size="13" font-weight="bold" fill="{col}">{ch}</text>'
    b += f'<text x="8" y="{30 + 7 * rh + 12}" font-size="9" fill="{C["mute"]}">{html.escape(t["rm_leg"])}</text>'
    return _svg(b, 480, 30 + 7 * rh + 20, t["rm_t"])


def svg_themes(t):
    roles = ("title", "vault", "template", "disposable", "offline", "step2", "exit")
    x0, sw = 130, 44
    b = ""
    for j, name in enumerate(t["sw_roles"]):
        b += f'<text x="{x0 + j * (sw + 4) + sw / 2}" y="16" text-anchor="middle" font-size="7.5" fill="{C["mute"]}">{html.escape(name)}</text>'
    for i, (key, th) in enumerate(_theme.THEMES.items()):
        y = 24 + i * 20
        b += f'<text x="8" y="{y + 13}" font-size="10" fill="{C["fg"]}">{html.escape(th["label"])}</text>'
        for j, r in enumerate(roles):
            b += f'<rect x="{x0 + j * (sw + 4)}" y="{y}" width="{sw}" height="16" rx="3" fill="{th["roles"][r]}" stroke="#555" stroke-width=".5"/>'
    return _svg(b, 480, 24 + len(_theme.THEMES) * 20 + 6, t["sw_t"])

SVGS = {"flow": svg_flow, "life": svg_life, "flowdata": svg_flowdata, "levels": svg_levels, "risk": svg_risk, "themes": svg_themes}

# ---- Easy Guide (A7c): eigene Inline-SVGs in GUI-Farben (theme.SAFETY / DARK), helle Fläche, Schrift >= 16 Einheiten bei 720 Breite ----
E = {
    "en": dict(steps=("Choose", "Start", "Use", "Erase"),
               sent=(("Pick a purpose,", "e.g. EMAIL."), ("Click START.", "Wait a moment."), ("Open Thunderbird", "and read mail."), ("Click Stop and", "erase. All gone.")),
               green="Green = internet", blue="Blue = no internet", red="Red = erase all",
               before="Before", after="After", virus="attachment with virus", gone="the box is gone", mine="your own computer",
               mine_ok="untouched", box="the box",
               chk=("Before start", "After you finish"),
               chk_rows=(("Updates are installed", "Template is clean", "OFFLINE for files"),
                         ("Box is gone from the list", "Nothing I need was inside", "Crash? evoxd reconcile"))),
    "de": dict(steps=("Wählen", "Starten", "Benutzen", "Löschen"),
               sent=(("Zweck wählen,", "z. B. EMAIL."), ("START klicken.", "Kurz warten."), ("Thunderbird öffnen", "und Mail lesen."), ("Stop and erase", "klicken. Alles weg.")),
               green="Grün = Internet", blue="Blau = ohne Internet", red="Rot = alles löschen",
               before="Vorher", after="Nachher", virus="Anhang mit Virus", gone="die Kiste ist weg", mine="dein eigener Rechner",
               mine_ok="unberührt", box="die Kiste",
               chk=("Vor dem Start", "Nach dem Beenden"),
               chk_rows=(("Updates sind installiert", "Template ist sauber", "OFFLINE für Dateien"),
                         ("Kiste ist aus der Liste weg", "Nichts Wichtiges darin", "Absturz? evoxd reconcile"))),
}
EI = {"ink": "#111111", "panel": "#f7f5fc", "line": "#5a00b3", "net": _theme.SAFETY["mode_internet"], "off": _theme.SAFETY["mode_offline"],
      "red": _theme.SAFETY["danger"], "cyan": _theme.DARK["template"], "vault": _theme.DARK["vault"], "title": _theme.DARK["title"]}


def _e(t):
    return E["en" if t["ui"]["other"] == "de" else "de"]       # ui.other = die andere Sprache


def _esvg(body, w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}" font-family="sans-serif">'
            f'<title>{html.escape(title)}</title><rect width="{w}" height="{h}" rx="8" fill="{EI["panel"]}"/>{body}</svg>')


def _etx(x, y, s, size=16, w="normal", fill=None, anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{w}" fill="{fill or EI["ink"]}">{html.escape(s)}</text>'


def svg_easy_steps(t):
    e = _e(t)
    b = ""
    icons = (
        # 1 Zweckliste mit markierter Zeile
        f'<rect x="34" y="50" width="100" height="14" rx="3" fill="#ddd"/><rect x="34" y="68" width="100" height="18" rx="3" fill="{EI["net"]}"/>'
        f'<rect x="34" y="90" width="100" height="14" rx="3" fill="#ddd"/>',
        # 2 grüner Knopf mit Dreieck
        f'<rect x="30" y="52" width="108" height="48" rx="10" fill="{EI["net"]}"/><path d="M72,62 L100,76 L72,90 z" fill="#fff"/>',
        # 3 Fenster mit Umschlag
        f'<rect x="30" y="48" width="108" height="58" rx="6" fill="#fff" stroke="{EI["line"]}" stroke-width="3"/><rect x="30" y="48" width="108" height="12" rx="4" fill="{EI["line"]}"/>'
        f'<rect x="56" y="68" width="56" height="30" rx="3" fill="#fff" stroke="{EI["ink"]}" stroke-width="2.5"/><path d="M56,68 L84,86 L112,68" fill="none" stroke="{EI["ink"]}" stroke-width="2.5"/>',
        # 4 roter Knopf mit Kreuz
        f'<rect x="30" y="52" width="108" height="48" rx="10" fill="{EI["red"]}"/><path d="M68,64 L100,88 M100,64 L68,88" stroke="#fff" stroke-width="7" stroke-linecap="round"/>',
    )
    for i in range(4):
        x = i * 184
        b += f'<g transform="translate({x},0)"><rect x="2" y="4" width="168" height="170" rx="10" fill="#fff" stroke="{EI["line"]}" stroke-width="2.5"/>'
        b += f'<circle cx="26" cy="26" r="15" fill="{EI["title"]}"/>' + _etx(26, 32, str(i + 1), 18, "bold", "#fff")
        b += _etx(98, 33, e["steps"][i], 20, "bold") + icons[i]
        b += _etx(86, 128, e["sent"][i][0]) + _etx(86, 152, e["sent"][i][1]) + "</g>"
    return _esvg(b, 716, 178, " / ".join(e["steps"]))


def svg_easy_buttons(t):
    e = _e(t)
    b = ""
    for i, (txt, col, bord, cap, capcol) in enumerate((
            ("START: INTERNET", EI["net"], _theme.SAFETY["mode_border"], e["green"], "#0b5a2a"),
            ("START: OFFLINE", EI["off"], _theme.SAFETY["mode_offline_border"], e["blue"], "#00468a"),
            ("Stop and erase", EI["red"], _theme.SAFETY["danger_border"], e["red"], "#9c1212"))):
        x = i * 242
        b += f'<rect x="{x + 4}" y="8" width="226" height="56" rx="10" fill="{col}" stroke="{bord}" stroke-width="3"/>'
        b += _etx(x + 117, 44, txt, 21, "bold", "#fff") + _etx(x + 117, 92, cap, 18, "bold", capcol)
    return _esvg(b, 716, 108, "START: INTERNET / START: OFFLINE / Stop and erase")


def _pc(x, y, inner, e, label):
    return (f'<rect x="{x}" y="{y}" width="190" height="110" rx="10" fill="#fff" stroke="{EI["ink"]}" stroke-width="3"/>' + inner +
            _etx(x + 95, y + 134, label, 16, "bold"))


def svg_easy_ba(t):
    e = _e(t)
    bug = (f'<g stroke="{EI["red"]}" stroke-width="3"><path d="M86,74 L70,66 M86,84 L68,84 M86,94 L70,102 M110,74 L126,66 M110,84 L128,84 M110,94 L126,102"/></g>'
           f'<ellipse cx="98" cy="84" rx="14" ry="17" fill="{EI["red"]}"/><circle cx="98" cy="64" r="7" fill="{EI["red"]}"/>')
    left = (_etx(115, 28, e["before"], 20, "bold") + _pc(20, 40, f'<rect x="38" y="52" width="154" height="86" rx="8" fill="{EI["cyan"]}" fill-opacity=".35" stroke="{EI["cyan"]}" stroke-width="3"/>'
            + f'<g transform="translate(18,6)">{bug}</g>', e, e["mine"]))
    left += _etx(115, 214, e["virus"], 16)
    arrow = (f'<path d="M232,100 L322,100" stroke="{EI["ink"]}" stroke-width="5"/><path d="M322,88 L342,100 L322,112 z" fill="{EI["ink"]}"/>'
             f'<rect x="228" y="116" width="124" height="34" rx="8" fill="{EI["red"]}"/>' + _etx(290, 139, "Stop and erase", 15, "bold", "#fff"))
    gone = f'<rect x="38" y="52" width="154" height="86" rx="8" fill="none" stroke="#777" stroke-width="3" stroke-dasharray="8 7"/>' + _etx(115, 100, e["gone"], 16, "bold", "#555")
    ok = f'<circle cx="196" cy="40" r="17" fill="{EI["net"]}"/><path d="M187,40 L194,48 L206,32" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>'
    right = _etx(375 + 115, 28, e["after"], 20, "bold") + f'<g transform="translate(375,0)">' + _pc(20, 40, gone, e, e["mine"]) + "</g>"
    right += f'<g transform="translate(375,0)">{ok}</g>'
    right += _etx(375 + 115, 214, e["mine_ok"], 16, "bold", "#0b5a2a")
    return _esvg(left + arrow + right, 716, 230, f'{e["before"]} / {e["after"]}')


def svg_easy_check(t):
    e = _e(t)
    b = ""
    for c in range(2):
        x = c * 362
        b += f'<rect x="{x + 2}" y="4" width="350" height="146" rx="10" fill="#fff" stroke="{EI["line"]}" stroke-width="2.5"/>' + _etx(x + 20, 32, e["chk"][c], 20, "bold", anchor="start")
        for r, row in enumerate(e["chk_rows"][c]):
            y = 52 + r * 31
            b += f'<rect x="{x + 18}" y="{y}" width="22" height="22" rx="4" fill="#fff" stroke="{EI["ink"]}" stroke-width="2.5"/>' + _etx(x + 50, y + 18, row, 16, anchor="start")
    return _esvg(b, 716, 154, " / ".join(e["chk"]))

SVGS.update({"easy_steps": svg_easy_steps, "easy_buttons": svg_easy_buttons, "easy_ba": svg_easy_ba, "easy_check": svg_easy_check})

PAL = {  # Bildschirm dunkel (Standard) und hell (Druck / Umschalter); Kontrast ≥ 4,5:1 gegen bg (Test)
    "dark": dict(bg="#000000", panel="#0b0b14", fg="#e8e8f0", mute="#b4b8cc", title="#c58cff", h_a="#00e5ff", h_b="#e08ae0",
                 line="#4a2a7a", glow="#8c00ff", code="#7cffb0", link="#66e8ff"),
    "light": dict(bg="#ffffff", panel="#f4f1fa", fg="#1a1a1a", mute="#4a4a5a", title="#5a00b3", h_a="#00656e", h_b="#8a2a8a",
                  line="#b9a5d6", glow="#b9a5d6", code="#0b5a2a", link="#004f9c"),
}


def _vars(p):
    return ";".join(f"--{k}:{v}" for k, v in p.items())


CSS = ("""
*{box-sizing:border-box}html,body{margin:0}body{font:10pt/1.35 sans-serif}
.page{%(dark)s;background:var(--bg);color:var(--fg);min-height:100vh;padding:4mm 0}
#lt:checked~.page{%(light)s}
#lt{position:absolute;opacity:0}#lt:focus-visible~.page .tg{outline:3px solid #C6FF00}
main{width:210mm;min-height:297mm;margin:0 auto;padding:8mm;background:var(--bg);border:1px solid var(--line);
 box-shadow:0 0 10px var(--glow);columns:2;column-gap:7mm}main.long{padding:10mm 12mm}
header.top{column-span:all;display:flex;align-items:center;gap:3mm;margin:0 0 1.5mm}
header.top svg.logo{width:11mm;height:11mm;margin:0;flex:none}
header.top .bar{margin-left:auto;display:flex;gap:2mm;align-items:center;font-size:8pt}
h1{margin:0;font-size:17pt;color:var(--title);text-shadow:0 0 8px var(--glow)}
.sub{column-span:all;margin:0 0 1.5mm;color:var(--mute);font-size:8pt}
nav.toc{column-span:all;margin:0 0 1.5mm;font-size:8pt;color:var(--mute)}nav.toc a{margin-right:2.2mm}
a{color:var(--link)}a:focus-visible,input:focus-visible,label:focus-visible{outline:3px solid #C6FF00}
.tg,.lang{border:1px solid var(--line);border-radius:3px;padding:.3mm 1.6mm;cursor:pointer;color:var(--link);text-decoration:none}
input#q{background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:3px;padding:.3mm 1.5mm;width:30mm}
h2{margin:2mm 0 .8mm;font-size:11pt;color:var(--h_a);border-bottom:1px solid var(--line);break-after:avoid;text-shadow:0 0 5px var(--glow)}
section:nth-of-type(even) h2{color:var(--h_b)}
p{margin:.6mm 0}ol{margin:.6mm 0;padding-left:5mm}li{margin:0}
svg{display:block;width:100%%;height:auto;margin:1mm 0;break-inside:avoid;border:1px solid var(--line);border-radius:6px;box-shadow:0 0 5px var(--glow)}
section{break-inside:avoid-column}table{border-collapse:collapse;width:100%%;font-size:7.4pt;margin:.8mm 0}
th,td{border:1px solid var(--line);padding:.6mm 1mm;vertical-align:top;text-align:left}th{background:var(--panel)}
code{font-family:monospace;color:var(--code);background:var(--panel);padding:0 .6mm;border-radius:2px}
pre.cmd{margin:1mm 0;padding:1mm 2mm;border:1px solid var(--line);border-left:3px solid var(--code);background:var(--panel);
 overflow-x:auto;user-select:all;white-space:pre-wrap;break-inside:avoid}pre.cmd code{padding:0;background:none}
footer.foot{column-span:all;margin-top:2mm;padding-top:1mm;border-top:1px solid var(--line);font-size:7.5pt;color:var(--mute);display:flex;justify-content:space-between}
.long{columns:1!important}.long section{break-inside:auto}.long table{font-size:8.4pt}.long h3{font-size:10pt;margin:2mm 0 .5mm;color:var(--title)}
.long tr{break-inside:avoid}ul{margin:.6mm 0;padding-left:5mm}
.easy{columns:1!important;font-size:16px}.easy h1{font-size:24pt}.easy h2{font-size:15pt;margin:3mm 0 1mm;color:var(--h_a)}.easy p,.easy li{font-size:16px;margin:1mm 0}
.easy .sub,.easy nav.toc{font-size:16px}.easy ol{padding-left:8mm}.easy svg{margin:1.5mm 0}.easy footer.foot{font-size:12px}
@media print{.long,body .long{font-size:9pt}.long table{font-size:8pt}.long section{break-inside:auto}.long h2{break-before:page}}
@media print{@page{size:A4;margin:@@MARGIN@@}html,body{background:#fff}
 .page,#lt:checked~.page{%(light)s;padding:0;min-height:0}
 body{font-size:7.2pt}main{width:auto;max-width:100%%;min-height:0;padding:0;margin:0;border:0;box-shadow:none;column-gap:6mm;overflow:visible}
 main.long{font-size:9pt;padding:0}
 main.easy{font-size:12pt}.easy h1{font-size:20pt}.easy h2{font-size:13pt;margin:2mm 0 .6mm}.easy p,.easy li,.easy .sub{font-size:12pt;margin:.6mm 0}.easy svg{margin:.8mm 0}.easy footer.foot{font-size:9pt;margin-top:1mm}
 nav.toc,.noprint,header.top .bar,.closehint{display:none!important}svg{box-shadow:none;max-width:100%%;overflow:visible}h2,h1{text-shadow:none}
 .long h2{break-before:page}.long section:first-of-type h2{break-before:auto}h1,h2,h3{break-after:avoid}
 svg,tr,pre.cmd,ol,li{break-inside:avoid}pre.cmd{overflow:visible;white-space:pre-wrap;word-break:break-word}code{white-space:pre-wrap;overflow-wrap:anywhere}
 section[hidden]{display:block!important}}
""" % {"dark": _vars(PAL["dark"]), "light": _vars(PAL["light"])})

SCRIPT = ("(function(){var q=document.getElementById('q');if(!q)return;q.addEventListener('input',function(){"
          "var v=q.value.toLowerCase();document.querySelectorAll('main section').forEach(function(s){"
          "s.hidden=!!v&&s.textContent.toLowerCase().indexOf(v)<0;});});})();")


def icon_svg():
    t = (ROOT / "packaging" / "icons" / "evoxd.svg").read_text(encoding="utf-8")
    t = re.sub(r"<\?xml[^>]*\?>\s*", "", t)
    return t.replace("<svg ", '<svg class="logo" ', 1).replace('width="256" height="256"', 'width="40" height="40" aria-hidden="true"', 1).replace(' role="img" aria-label="EVOX KVM DISPOSABLE"', "", 1)


def version():
    m = re.search(r'__version__ = "([^"]+)"', (ROOT / "src" / "evoxd" / "__init__.py").read_text())
    return m.group(1)


def inline(s):
    """Code-Spans zuerst herausnehmen (darin darf * stehen), dann fett/kursiv auf dem Rest."""
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if len(p) > 2 and p[0] == p[-1] == "`":
            out.append("<code>" + html.escape(p[1:-1], quote=False) + "</code>")
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        out.append(re.sub(r"\*(.+?)\*", r"<i>\1</i>", p))
    return "".join(out)


def convert(md, lang, stem="quick-guide", ver=None):
    t, ver = L[lang], ver or version()
    ui = t["ui"]
    body, toc, terms, sect, i, n = [], [], {}, False, 0, 0
    lines = md.splitlines()
    cur = None
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            title = ln[2:].strip()
        elif ln.startswith("### "):
            body.append(f"<h3>{inline(ln[4:].strip())}</h3>")
        elif ln.startswith("## "):
            body.append("</section>" if sect else "")
            n += 1
            m = re.match(r"(.*?)\s*\{#([A-Za-z][\w-]*)\}\s*$", ln[3:])
            text, cur = (m.group(1), m.group(2)) if m else (ln[3:].strip(), f"s{n}")
            toc.append((cur, text))
            body.append(f'<section id="{cur}"><h2>{inline(text)}</h2>')
            sect = True
        elif m := re.fullmatch(r"\{\{svg:(\w+)\}\}", ln.strip()):
            body.append(SVGS[m.group(1)](t))
        elif ln.strip() == "{{index}}":
            body.append("@@INDEX@@")
        elif ln.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(html.escape(lines[i], quote=False))
                i += 1
            body.append('<pre class="cmd" tabindex="0"><code>' + "\n".join(code) + "</code></pre>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append("<li>" + inline(lines[i][2:]) + "</li>")
                terms_from(lines[i], cur, terms)
                i += 1
            body.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"\d+\. ", ln):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                items.append("<li>" + inline(re.sub(r"^\d+\. ", "", lines[i])) + "</li>")
                terms_from(lines[i], cur, terms)
                i += 1
            body.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                terms_from(lines[i], cur, terms)
                i += 1
            head, rest = rows[0], rows[2:]
            body.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>" +
                        "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rest) + "</table>")
            continue
        elif ln.strip():
            sub = ln.replace("{{version}}", ver)
            body.append(f'<p class="sub">{inline(sub)}</p>' if (not sect and not toc) else f"<p>{inline(sub)}</p>")
            terms_from(ln, cur, terms)
        i += 1
    if sect:
        body.append("</section>")
    index = ("<ul>" + "".join(f'<li><a href="#{a}">{html.escape(k)}</a></li>' for k, a in sorted(terms.items(), key=lambda kv: kv[0].lower())) + "</ul>")
    inner = "\n".join(x for x in body if x).replace("@@INDEX@@", index)
    nav = '<nav class="toc" aria-label="%s"><b>%s:</b> ' % (ui["toc"], ui["toc"]) + " ".join(f'<a href="#{a}">{html.escape(x)}</a>' for a, x in toc) + "</nav>"
    other = f'{stem}.{ui["other"]}.html'
    sw = "" if stem in NO_SWITCH else f'<a class="lang" href="{other}" hreflang="{ui["other"]}" lang="{ui["other"]}">{ui["lang"]}</a>'
    top = (f'<header class="top">{icon_svg()}<h1>{html.escape(title)}</h1><div class="bar">'
           f'{sw}'
           f'<label class="tg" for="lt" tabindex="0">{ui["theme"]}</label>'
           f'<input id="q" type="search" placeholder="{ui["search"]}" aria-label="{ui["search"]}"></div></header>')
    foot = (f'<footer class="foot"><span>{ui["ver"].format(v=ver)}</span><span class="closehint">{ui["close"]}</span></footer>')
    return (f'<!DOCTYPE html>\n<html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<meta name="evoxd-version" content="{ver}"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<style>{CSS.replace("@@MARGIN@@", "12mm" if stem in SHORT else "18mm")}</style></head>\n<body><input type="checkbox" id="lt" aria-label="{ui["theme"]}">'
            f'<div class="page"><main{' class="easy"' if stem in EASY else (' class="long"' if stem not in SHORT else "")}>\n{top}\n{nav}\n{inner}\n{foot}\n</main></div><script>{SCRIPT}</script></body></html>\n')


def terms_from(line, anchor, terms):
    if anchor:
        for m in re.finditer(r"\*\*(.+?)\*\*", line):
            terms.setdefault(m.group(1).strip(": "), anchor)


def main():
    for src in sorted(OUT.glob("*.??.md")):
        stem, lang = src.name[:-6], src.name[-5:-3]
        if lang not in L:
            continue
        (OUT / f"{stem}.{lang}.html").write_text(convert(src.read_text(encoding="utf-8"), lang, stem), encoding="utf-8")
        print("wrote", f"{stem}.{lang}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

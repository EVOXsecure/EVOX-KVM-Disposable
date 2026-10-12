"""Alle Texte der Oberfläche an einer Stelle (englisch). Platzhalter in {} werden mit format() gefüllt."""

APP_TITLE = "EVOX KVM DISPOSABLE"
TAGLINE = "Secure. Disposable. Isolated. Encrypted. Network-locked. Erased on exit."
SUBLINE = "Throwaway VMs for safe browsing and e-mail."

# Reiter (Disposable vorne) und Erklärsätze für leere Reiter
TAB_VAULT = "1. VAULT"
TAB_TEMPLATE = "2. TEMPLATE"
TAB_DISPOSABLE = "3. DISPOSABLE"
EMPTY_DISPOSABLE = "No disposable VMs running. Pick a template and click Start."
EMPTY_TEMPLATES = ("No templates yet. Create a VAULT-* VM, shut it down, then use Make template "
                   "in the VAULT tab, or Import template.")
EMPTY_VAULTS = ("No VAULT-* VMs found. Create one in virt-manager and name it VAULT-<purpose>, "
                "e.g. VAULT-MAIL.")

# Detailleiste (nur sichtbar, wenn eine VM markiert ist; 0.7.1: drei Blöcke RAM / CPU / Netz+Overlay)
DETAILS = "Details"
# 0.7.2: großer Detailbereich hinter dem Knopf; 0.7.3: nur Text, keine Pfeile
BTN_DETAILS_OPEN = "OPEN DETAILS"
BTN_DETAILS_CLOSE = "CLOSE DETAILS"
DE_BTN_DETAILS_OPEN = "DETAILS ÖFFNEN"
DE_BTN_DETAILS_CLOSE = "DETAILS SCHLIESSEN"
DETAILS_TIP = "Opens the Live Monitor window for the selected VM: RAM, CPU and network"
DE_DETAILS_TIP = "Öffnet das Fenster Live Monitor zur gewählten VM: RAM, CPU und Netz"
DETAILS_TIP_CLOSE = "Closes the Live Monitor window"
DE_DETAILS_TIP_CLOSE = "Schließt das Fenster Live Monitor"
DETAILS_TIP_NONE = "Select a VM first"
DE_DETAILS_TIP_NONE = "Zuerst eine VM markieren"
# 0.7.4 Kurzzeile im Hauptfenster (eine Zeile) und Fenster „Live Monitor“
SHORT_LINE = "RAM {ram}  ·  CPU {cpu}  ·  Up {up}"
DE_SHORT_LINE = "RAM {ram}  ·  CPU {cpu}  ·  Läuft {up}"
SHORT_RAM = "{sym} {word} {est}{pct} %"
SHORT_NONE = "Select a running VM to see its live values."
DE_SHORT_NONE = "Eine laufende VM markieren, um ihre Live-Werte zu sehen."
SHORT_NOT_RUNNING = "VM stopped"
DE_SHORT_NOT_RUNNING = "VM beendet"
MON_TITLE = "Live Monitor"
MON_HEAD = "Live Monitor – {name}"
MON_STOPPED = "VM stopped"
DE_MON_STOPPED = "VM beendet"
MON_STOPPED_SUB = "No values to show. Mark a running VM in the main window."
DE_MON_STOPPED_SUB = "Keine Werte vorhanden. Im Hauptfenster eine laufende VM markieren."
MON_NO_VM = "No VM marked"
DE_MON_NO_VM = "Keine VM markiert"
MON_PIN = "Always on top"
DE_MON_PIN = "Immer im Vordergrund"
MON_PIN_TIP = "Keeps this window above other windows. Remembered."
DE_MON_PIN_TIP = "Hält dieses Fenster über anderen Fenstern. Wird gemerkt."
STATUS_MON_CLOSE = "CLOSE DETAILS: closes the Live Monitor window. Enter to close (Esc also closes)."
DE_STATUS_MON_CLOSE = "DETAILS SCHLIESSEN: schließt das Fenster Live Monitor. Enter zum Schließen (Esc schließt ebenfalls)."
STATUS_MON_PIN = "Always on top: keeps the Live Monitor above other windows. Space switches it on or off."
DE_STATUS_MON_PIN = "Immer im Vordergrund: hält den Live Monitor über anderen Fenstern. Leertaste schaltet um."
STATUS_MON_DEFAULT = "Live values of the marked VM, updated every second. Esc closes this window."
DE_STATUS_MON_DEFAULT = "Live-Werte der markierten VM, jede Sekunde aktualisiert. Esc schließt dieses Fenster."
# 0.7.0 Live-Werte (nur lesend aus libvirt; fehlt ein Wert: "n/a", nie erfunden); 0.7.1 Liste schlank
LIVE_COLUMNS = ("Up", "RAM", "CPU")
DE_LIVE_COLUMNS = ("Laufzeit", "RAM", "CPU")
LIVE_NA = "n/a"
LIVE_WAIT = "…"                      # CPU: erster Messpunkt, Prozent ab dem nächsten Zyklus
LIVE_EST = "~"                       # Kennzeichnung geschätzter RAM-Werte
LIVE_EST_DETAIL = " (est.)"
DE_LIVE_EST_DETAIL = " (geschätzt)"
# Ampel: Symbol + Wort (nie nur Farbe); 0.7.1: grün bis 60 %, gelb bis 85 %, rot darüber
RAM_LEVELS = {"low": ("○", "LOW – less RAM would do"), "ok": ("●", "OK"),
              "high": ("▲", "HIGH"), "full": ("■", "FULL")}
DE_RAM_LEVELS = {"low": ("○", "NIEDRIG – weniger RAM reicht"), "ok": ("●", "OK"),
                 "high": ("▲", "HOCH"), "full": ("■", "VOLL")}
LIVE_RAM_CELL = "{sym} {est}{pct} %"
LIVE_CPU = "{pct} %"
LIVE_NET = "↓ {rx}   ↑ {tx}"
LIVE_NO_NET = "no network (offline)"
DE_LIVE_NO_NET = "kein Netz (offline)"
LIVE_TIP = ("Live values, read-only from libvirt every 5 s. RAM: ● OK (up to 60 %), ▲ HIGH (up to 85 %), "
            "■ FULL (over 85 %), ○ LOW (under 30 %). ~ / (est.) = estimate from the host process (guest reports "
            "no memory figures). Peak = highest value seen since this window opened.")
DE_LIVE_TIP = ("Live-Werte, nur lesend aus libvirt alle 5 s. RAM: ● OK (bis 60 %), ▲ HOCH (bis 85 %), "
               "■ VOLL (über 85 %), ○ NIEDRIG (unter 30 %). ~ / (geschätzt) = Schätzung aus dem Host-Prozess (Gast "
               "meldet keine Speicherwerte). Spitze = höchster Wert seit Öffnen dieses Fensters.")
# Liste: Modus-Spalte
MODE_COL_INTERNET = "INTERNET"
MODE_COL_OFFLINE = "OFFLINE"
# Block a) RAM
BLOCK_RAM = "RAM"
BLOCK_CPU = "CPU"
BLOCK_NET = "Network & overlay"
DE_BLOCK_NET = "Netz & Overlay"
RAM_LINE = "{used} / {size} ({pct} %){est}"
RAM_LEVEL_LINE = "{sym} {word}"
RAM_PEAK = "Peak {peak} ({pct} %) at {time}"
DE_RAM_PEAK = "Spitze {peak} ({pct} %) um {time}"
RAM_FULL_COUNT = "RAM full (over 95 %): {n}×"
DE_RAM_FULL_COUNT = "RAM voll (über 95 %): {n}×"
RAM_NA = "RAM use n/a – the guest reports no memory figures."
DE_RAM_NA = "RAM-Nutzung n/a – der Gast meldet keine Speicherwerte."
# Block b) CPU
CPU_LINE = "{pct} % of {n} vCPU(s)"
DE_CPU_LINE = "{pct} % von {n} vCPU(s)"
CPU_HIST = "Last {min} min"
DE_CPU_HIST = "Letzte {min} min"
# Block c) Netz / Overlay
NET_ROWS = ("Traffic:", "Overlay:", "Running for:", "Template:", "Mode:", "Network lock:", "Starts:")
DE_NET_ROWS = ("Verkehr:", "Overlay:", "Läuft seit:", "Template:", "Modus:", "Netzsperre:", "Starts:")
OVERLAY_LINE = "{used} of {disk} ({pct} %) · peak {peak}"
DE_OVERLAY_LINE = "{used} von {disk} ({pct} %) · Spitze {peak}"
OVERLAY_LINE_NODISK = "{used} · peak {peak}"
DE_OVERLAY_LINE_NODISK = "{used} · Spitze {peak}"
LOCK_STATE = {"ok": "● active", "bad": "■ INACTIVE – VMs blocked", "cut": "✂ CUT by guard", "off": "– offline (no network)"}
DE_LOCK_STATE = {"ok": "● aktiv", "bad": "■ INAKTIV – VMs gesperrt", "cut": "✂ vom Wächter GETRENNT",
                 "off": "– offline (kein Netz)"}
STARTS_LINE = "{purpose}: {n}× started"
DE_STARTS_LINE = "{purpose}: {n}× gestartet"
DETAIL_TIP_OVERLAY = "Overlay file: {file}. Started: {started}."
DE_DETAIL_TIP_OVERLAY = "Overlay-Datei: {file}. Gestartet: {started}."

# 0.7.1 Hinweis beim Stop and erase (nur Information, keine automatische Anpassung)
HINT_RAM = {"high": "RAM peak {peak} of {size} ({pct} %). Next time choose more RAM: {sug}.",
            "low": "RAM peak only {peak} of {size}. Next time {sug} is enough.",
            "full": "RAM was full {n} times. For better performance choose more RAM next time ({sug}).",
            "ok": "RAM peak {peak} of {size} ({pct} %). The size fits."}
DE_HINT_RAM = {"high": "RAM-Spitze {peak} von {size} ({pct} %). Nächstes Mal mehr RAM wählen: {sug}.",
               "low": "RAM-Spitze nur {peak} von {size}. Nächstes Mal reichen {sug}.",
               "full": "RAM war {n}-mal voll. Für bessere Leistung nächstes Mal mehr RAM wählen ({sug}).",
               "ok": "RAM-Spitze {peak} von {size} ({pct} %). Die Größe passt."}
HINT_REMEMBER = "Remember {sug} for {purpose}"
DE_HINT_REMEMBER = "{sug} für {purpose} merken"
HINT_REMEMBER_TIP = "Only stores the suggested RAM size for the next start (still limited by free memory). Nothing else changes."
DE_HINT_REMEMBER_TIP = ("Merkt nur die vorgeschlagene RAM-Größe für den nächsten Start (weiter begrenzt durch freien "
                        "Speicher). Sonst ändert sich nichts.")
HINT_REMEMBERED = "✔ Remembered {sug} for {purpose}"
DE_HINT_REMEMBERED = "✔ {sug} für {purpose} gemerkt"
STATUS_HINT_REMEMBER = "Stores the suggested RAM size for this purpose. The VM is not changed."
DE_STATUS_HINT_REMEMBER = "Merkt die vorgeschlagene RAM-Größe für diesen Zweck. Die VM wird nicht verändert."
# 0.7.1 Zweck-Statistik im Startdialog (nur Hinweis, ändert die Auswahl nicht)
DLG_PURPOSE_PEAK = "So far {purpose} needed up to {peak}."
DE_DLG_PURPOSE_PEAK = "Bisher brauchte {purpose} höchstens {peak}."
# 0.7.3 Empfehlung im Startdialog (Spitze + 25 %, 0,25-GB-Raster, mind. 1 GB); über 85 % → „mehr RAM wählen“
DLG_RECOMMEND = "Recommended: {sug}."
DE_DLG_RECOMMEND = "Empfehlung: {sug}."
DLG_RECOMMEND_MORE = "Choose more RAM: at least {sug} recommended."
DE_DLG_RECOMMEND_MORE = "Mehr RAM wählen: mindestens {sug} empfohlen."
DLG_RAM_UNIT = "GB"
DE_DLG_RAM_UNIT = "GB"
DLG_RAM_TIP = "RAM in steps of 0.25 GB (256 MiB), from 1 GB up to what the host can spare."
DE_DLG_RAM_TIP = "RAM in Schritten von 0,25 GB (256 MiB), von 1 GB bis zu dem, was der Host abgeben kann."

# Gruppen
GROUP_HOST = "Host"
GROUP_VMS = "Disposable VMs"
GROUP_TEMPLATES = "Templates"

# Hauptfenster – Templates
TPL_COLUMNS = ("TEMPLATE", "Version", "Created", "Firmware", "Size", "Age", "Running VMs", "Status")
TPL_AGE = "{days} days"
TPL_DAMAGED = "DAMAGED"
TPL_OK = "ok"
BTN_IMPORT = "Import template…"
BTN_VERIFY = "Verify"
BTN_REMOVE = "Remove template…"
CHK_VERIFY_AFTER = "Verify template after each VM shutdown"
CHK_VERIFY_AFTER_TIP = ("After a disposable VM ends, compare the SHA-256 of its template copy in the background. "
                        "Detects changes of the copy on the host (disk errors, tampering). "
                        "Does not detect malware inside the template.")
MSG_SELECT_TEMPLATE = "Select a template in the list first."
MSG_IMPORTED = "{name} version {version} imported ({size}, SHA-256 {sha}…)."
MSG_VERIFY_OK = "{name} v{version}: template copy unchanged (SHA-256 matches)."
MSG_VERIFY_BAD = ("WARNING: {name} v{version}: checksum does NOT match – copy marked DAMAGED, "
                  "no new VMs from it. Import the template again or remove this copy.")
MSG_AUTO_VERIFY = "Verifying {name} v{version} in the background (after VM shutdown) …"
MSG_AUTO_VERIFY_ERR = "Verify after shutdown failed: {err}"
MSG_REMOVED = "Removed: {list}."
MSG_REFUSED = "Not removed: {list}"
MSG_SETTING_ERR = "Could not save the setting: {err}"
FREE_LINE = "Free in /srv/evoxd: {free}"
FREE_UNKNOWN = "Free in /srv/evoxd: unknown"
TPL_DETAIL_NONE = "Select one template to see where it comes from."
TPL_ORIGIN_VAULT = ("{name} v{version}: made from {vault} on {date} · {size} · SHA-256 {sha}…")
TPL_ORIGIN_IMPORT = "{name} v{version}: imported from domain {name} on {date} · {size} · SHA-256 {sha}…"

# Reiter VAULT (nur lesen; EVOX ändert Vaults nie)
VAULT_HINT = ("EVOX only reads and copies VAULT VMs. It never starts, changes or deletes them. "
              "Only VAULT-* VMs are shown here.")
VAULT_COLUMNS = ("VAULT", "State", "RAM", "CPUs", "Disk size", "Templates made from it")
VAULT_NONE_MADE = "–"
VAULT_SELECT = "Select a shut-off VAULT VM to make a template from it."
NO_VAULT_HINT = "Before making a template, please create a new VAULT VM."
DE_NO_VAULT_HINT = "Bevor du ein Template erstellst, lege bitte eine neue VAULT-VM an."
VAULT_PROBLEM = "Make template not possible: {problem}"
VAULT_READY = "{name} is shut off – ready to make a template."
BTN_MAKE = "Make template…"
BTN_MAKE_TIP = "Copy the disk of the selected shut-off VAULT VM into a new protected template."
BTN_MAKE_TIP_NONE = "Select one shut-off VAULT VM first."
BTN_VIRT_MANAGER = "Create new VAULT VM in virt-manager…"
BTN_VIRT_MANAGER_TIP = "Opens virt-manager so you can create a new VAULT VM. EVOX does not change libvirt."
DE_BTN_VIRT_MANAGER = "Neue VAULT-VM in virt-manager anlegen…"
DE_BTN_VIRT_MANAGER_TIP = ("Öffnet virt-manager, damit du eine neue VAULT-VM anlegen kannst. "
                           "EVOX ändert libvirt nicht.")
MSG_VIRT_MANAGER = "virt-manager opened. Name new VMs VAULT-<purpose> or TEMPLATE-<system>."   # seit 0.6.11 als Balken
# Hinweisbalken nach virt-manager (Reiter VAULT; bleibt bis ✕)
HINT_ICON = "ℹ"
HINT_OPENED = "virt-manager opened."
HINT_NAME_NEW = "Name new VMs"
HINT_PATTERN_VAULT = "VAULT-<purpose>"
HINT_OR = "or"
HINT_PATTERN_TEMPLATE = "TEMPLATE-<system>"
HINT_END = "."
HINT_CLOSE = "✕"
HINT_CLOSE_TIP = "Close this hint"
DE_HINT_OPENED = "virt-manager ist geöffnet."
DE_HINT_NAME_NEW = "Benenne neue VMs"
DE_HINT_OR = "oder"
DE_HINT_CLOSE_TIP = "Hinweis schließen"

# Make-template-Dialog
MK_TITLE = "Make template from {vault}"
MK_WARN = ("The copy contains ALL data of this VM, including passwords and browser data. "
           "Only do this if the VM is clean.")
MK_CONFIRM = "I understand. This VM is clean."
MK_SOURCE = "Source: {vault} · disk {size} ({fmt}, used {alloc}). The original is not changed."
MK_NAME = "Template name:"
MK_NAME_OK = "Name is free."
MK_SPACE = "Needed: {need}, free: {free} (after reserve: {after})"
MK_SPACE_LOW = ("Not enough space in /srv/evoxd/templates. Free some space first "
                "(EVOX keeps a reserve of {reserve}).")
MK_BTN = "Make template"
MSG_MADE = "{name} v{version} made from {vault} ({size}, SHA-256 {sha}…). It is now in the TEMPLATE tab."
MSG_CANCELLING = ("Cancelling … libvirt finishes the current copy step, then the partial copy is deleted.")
BTN_CANCEL_COPY = "Cancel"
PROGRESS_PCT = "{phase}  {pct} %  {elapsed}"

# Unfertige Kopien (nach Absturz/Stromausfall)
ORPHAN_TITLE = "Unfinished template copies found"
ORPHAN_TEXT = ("EVOX found unfinished copies from an earlier run (power loss or crash):\n{list}\n\n"
               "Delete them now? Only these EVOX copies are deleted, nothing else.")
ORPHAN_LINE = "{vol} (from {vault}, started {date}){missing}"
ORPHAN_MISSING = " – file already gone"
MSG_ORPHANS_REMOVED = "Unfinished copies deleted: {list}."
MSG_ORPHANS_KEPT = "Unfinished copies kept. EVOX asks again at the next start."

# Entfernen-Dialog
RM_TITLE = "Remove template copy"
RM_TEXT = ("Remove the imported copy {name} v{version} ({size})?\n"
           "Only EVOX's copy in /srv/evoxd/templates is deleted. The original domain "
           "(virt-manager) is not changed.")
RM_TEXT_MANY = ("Remove these {n} imported copies?\n{list}\nTotal: {total}\n"
                "Only EVOX's copies in /srv/evoxd/templates are deleted. The original domains "
                "(virt-manager) are not changed.")
RM_IN_USE = "Note: {n} running disposable VM(s) use this copy – removal will be refused."
RM_BTN = "Remove"
PHASE = {"check": "Checking {name} …",
         "copy": "Copying the disk of {name} (can take several minutes) …",
         "verify": "Checking the copy of {name} …",
         "checksum": "Computing SHA-256 of {name} …"}
PROGRESS = "{phase}  {elapsed}"

# Import-Dialog
IMP_TITLE = "Import template"
IMP_HINT = ("Shut-off libvirt domains named TEMPLATE-… . EVOX makes a protected copy; "
            "the original stays unchanged.")
IMP_COLUMNS = ("Domain", "State", "Disk size", "Note")
IMP_NONE = "No domain named TEMPLATE-… found."
IMP_OK = "ready"
IMP_BTN = "Import…"
IMP_SELECT = "Click the template you want to import."
IMP_SPACE_UNKNOWN = "Disk size unknown for {names} – space not checked; the import is not blocked."
IMP_CONFIRM_TITLE = "Import {name}?"
IMP_CONFIRM_TEXT = ("Disk: {size} (used {alloc}).\nThe disk is copied and checked; this can take "
                    "several minutes. Do not start {name} until the import is finished.")
IMP_BACKUP_WARN = ("\n\nWARNING: the name ends with -BACKUP. This looks like a backup copy, "
                   "not your maintained template. Import it only if you are sure.")

# Hauptfenster – Host
LOCK_ICON_OK = "🔒"
LOCK_ICON_BAD = "🔓"
LOCK_LABEL = "Network lock:"
LOCK_WORD_OK = "active"
LOCK_TAIL_OK = "– VMs cannot reach your host or home network"
LOCK_OK = f"{LOCK_ICON_OK} {LOCK_LABEL} {LOCK_WORD_OK} {LOCK_TAIL_OK}"
LOCK_BAD = f"{LOCK_ICON_BAD} {LOCK_LABEL} INACTIVE – VMs are blocked completely"
LOCK_TIP = ("Firewall on the host blocks every disposable VM from reaching this computer, your "
            "router, your local network and other VMs. Only the internet is allowed (in INTERNET "
            "mode). If the firewall is ever missing, a guard cuts the VM off completely.")
LOCK_TIP_WHY = "\n\nReason: {why}"
# Deutsche Fassung (Speicher für spätere Sprachumschaltung; noch nicht in der Oberfläche verdrahtet)
DE_LOCK_OK = "🔒 Netzsperre: aktiv – VMs erreichen weder deinen Rechner noch dein Heimnetz"
DE_LOCK_BAD = "🔓 Netzsperre: INAKTIV – VMs sind komplett gesperrt"
DE_LOCK_TIP = ("Die Firewall des Hosts verhindert, dass eine Wegwerf-VM diesen Rechner, deinen Router, "
               "dein lokales Netz oder andere VMs erreicht. Erlaubt ist nur das Internet (im "
               "INTERNET-Modus). Fehlt die Firewall einmal, trennt ein Wächter die VM vollständig ab.")
DE_TAB_VAULT, DE_TAB_TEMPLATE, DE_TAB_DISPOSABLE = "1. VAULT", "2. TEMPLATE", "3. DISPOSABLE"
CAP_ROOM = "room for {n} VM(s) of {size}"          # Hauptfenster und Startdialog gleich
HOST_LINE = ("RAM {total}, available {avail}, reserve {reserve}, max. for VMs {maxvms}"
             " · {room} · CPUs: {cpus}")
HOST_UNKNOWN = "Memory unknown"

# Hauptfenster – Liste
COLUMNS = ("Disposable VM", "State", "Mode")     # 0.7.1 schlank; danach LIVE_COLUMNS
DE_COLUMNS = ("Wegwerf-VM", "Zustand", "Modus")
NET_NONE = "Offline"
NET_CUT = "CUT (guard)"
NET_LOCK = "Internet"

# Hauptfenster – Knöpfe und Statuszeile
LABEL_TEMPLATE = "Template:"
BTN_START = "Start Disposable VM: INTERNET"
BTN_START_SUB = "Internet only. Host, home network and other VMs blocked."
BTN_START_OFFLINE = "Start Disposable VM: OFFLINE"
BTN_START_OFFLINE_SUB = "No connection at all. For untrusted files."
BTN_SHOW = "Show selected VM"
BTN_STOP = "Stop and erase VM"
BTN_STOP_TIP_NONE = "Select a disposable VM in the list first."
BTN_STOP_TIP = "Ends the selected VM immediately and erases all its data."
MSG_NO_TEMPLATE = "No template available (evoxd template-import TEMPLATE-…)."
MSG_SELECT_FIRST = "Select a disposable VM in the list first."
MSG_STARTING = "Starting …"
MSG_STARTED = "{name} started ({net})."
MSG_STARTED_NET = "Internet"
MSG_STARTED_NONET = "Offline"
MSG_OPENING = "Opening the window of {name} …"
MSG_ERASED = "{name} stopped and erased."
MSG_ERROR = "Error: {err}"
MSG_REFRESH_ERROR = "Error while refreshing: {err}"
STOP_TEXT = "This ends <b>{name}</b> immediately and erases all its data."
STOP_CANCEL = "Cancel"
STOP_CONFIRM = "Stop and erase"

# Startdialog
DLG_TITLE = "Start disposable VM"
DLG_CANCEL = "Cancel"
DLG_START = "Start"
# Kopfleiste im Startdialog: (Symbol, Text, Erklärsatz); Symbol und Text immer zusammen, nie nur Farbe
DLG_MODE = {"net": ("🔒〰", "INTERNET MODE",
                    "Internet works. Your computer, your home network and other VMs are blocked."),
            "none": ("🚫🌐", "OFFLINE MODE", "Fully offline. Use this to open untrusted files.")}
DLG_ROWS = ("Template:", "Purpose:", "Name:", "RAM:", "CPUs:", "Host:", "Capacity:")   # 0.7.3: RAM in GB-Anzeige
DLG_HOST = ("Host: {total}, available {avail}, reserve {reserve}, max. for VMs {maxvms}"
            " · {room}\nMax. CPUs: {cpus}   (reserve: {config})")
DLG_CAP = {"green": "OK – {left} stays available for the host",
           "yellow": "Warning – only {left} left for the host (reserve {reserve})",
           "red": "Not enough memory for this RAM size – start not possible"}
DLG_MEM_UNKNOWN = "Memory unknown – start not possible"
# 0.7.0 "Remember for purpose": nur die RAM-Größe, nie Modus oder Netzsperre; Haken standardmäßig aus
DLG_REMEMBER = "Remember RAM for {purpose}"
DLG_REMEMBER_ANY = "Remember RAM for this purpose"
DLG_REMEMBER_TIP = ("Next start with this purpose suggests this RAM size (still limited by free memory). "
                    "Only the RAM size is remembered – never the mode or the network lock. Untick to forget.")
DE_DLG_REMEMBER = "RAM für {purpose} merken"
DE_DLG_REMEMBER_ANY = "RAM für diesen Zweck merken"
DE_DLG_REMEMBER_TIP = ("Beim nächsten Start mit diesem Zweck wird diese RAM-Größe vorgeschlagen (weiter begrenzt "
                       "durch freien Speicher). Gemerkt wird nur RAM – nie Modus oder Netzsperre. Haken weg = vergessen.")
MSG_REMEMBER_FAILED = "RAM size could not be remembered: {err}"
DE_MSG_REMEMBER_FAILED = "RAM-Größe konnte nicht gemerkt werden: {err}"
DLG_NAME_UNKNOWN = "Name cannot be checked – start not possible"
MSG_NAME_CHANGED = "Not started: the name {shown} was taken in the meantime (next free: {now}). Please try again."
MSG_NAME_DIFFERS = "Note: started as {name} instead of {shown}."
DE_DLG_NAME_UNKNOWN = "Name nicht prüfbar – Start nicht möglich"
DE_MSG_NAME_CHANGED = ("Nicht gestartet: Der Name {shown} wurde inzwischen belegt (nächster freier: {now}). "
                       "Bitte erneut versuchen.")
DE_MSG_NAME_DIFFERS = "Hinweis: gestartet als {name} statt {shown}."

# Quick purpose (0.6.4): Zweck-Vorauswahl im Startdialog, Liste editierbar
QP_TITLE = "Quick purpose"
# 0.6.5: Gruppen (feste Zuordnung der Standardnamen in purposes.py), Zurück-Knopf, Vollbild
QP_GROUPS = {"everyday": "EVERYDAY", "money": "MONEY", "work": "WORK & TECH", "more": "MORE", "mylist": "MY LIST"}
DE_QP_GROUPS = {"everyday": "ALLTAG", "money": "GELD", "work": "ARBEIT & TECHNIK", "more": "WEITERE",
                "mylist": "MEINE LISTE"}
BACK = "← BACK"
DE_BACK = "← ZURÜCK"
BTN_FULLSCREEN = "Fullscreen"
BTN_FULLSCREEN_EXIT = "Exit fullscreen"
DE_BTN_FULLSCREEN = "Vollbild"
DE_BTN_FULLSCREEN_EXIT = "Vollbild beenden"
QP_EDIT = "Edit list..."
QP_OTHER = "OTHER"                      # setzt keinen Namen, fokussiert nur das Feld
QP_TIP = "Fills the purpose field only. Does not start anything."
QP_EDIT_TITLE = "Edit purposes"
QP_EDIT_NEW = "New purpose:"
QP_EDIT_ADD = "Add"
QP_EDIT_REMOVE = "Remove"
QP_EDIT_UP = "Move up"
QP_EDIT_DOWN = "Move down"
QP_EDIT_RESET = "Reset to defaults"
QP_EDIT_OK = "Save"
QP_EDIT_SAVE_ERROR = "Could not save the list: {err}"
QP_ERR_EMPTY = "Enter a purpose."
QP_ERR_CHARS = "Only letters A–Z, digits 0–9 (no spaces or other characters)."
QP_ERR_LONG = "At most {n} characters."
QP_ERR_DUP = "{name} is already in the list."
QP_ERR_FULL = "At most {n} purposes."
DE_QP_TITLE = "Schnellauswahl Zweck"
DE_QP_EDIT = "Liste bearbeiten..."
DE_DE_QP_TIP = "Füllt nur das Zweckfeld. Startet nichts."
DE_QP_EDIT_TITLE = "Zwecke bearbeiten"
DE_QP_EDIT_NEW = "Neuer Zweck:"
DE_QP_EDIT_ADD = "Hinzufügen"
DE_QP_EDIT_REMOVE = "Entfernen"
DE_QP_EDIT_UP = "Nach oben"
DE_QP_EDIT_DOWN = "Nach unten"
DE_QP_EDIT_RESET = "Standardliste wiederherstellen"
DE_QP_EDIT_OK = "Speichern"
DE_QP_EDIT_SAVE_ERROR = "Liste konnte nicht gespeichert werden: {err}"
DE_QP_ERR_EMPTY = "Bitte einen Zweck eingeben."
DE_QP_ERR_CHARS = "Nur Buchstaben A–Z und Ziffern 0–9 (keine Leerzeichen oder Sonderzeichen)."
DE_QP_ERR_LONG = "Höchstens {n} Zeichen."
DE_QP_ERR_DUP = "{name} steht schon in der Liste."
DE_QP_ERR_FULL = "Höchstens {n} Zwecke."

# HOW-TO-USE-Leiste (0.6.8): vier Schritte untereinander; Schritt 4 hat zwei Knöpfe (INTERNET / OFFLINE).
# Knöpfe 1–3 führen nur zur richtigen Stelle, 4 öffnet den Startdialog. Gesperrt nur diese Knöpfe (reine Führung).
HOWTO_TITLE = "HOW TO USE"
HOWTO_STEPS = ("1. CREATE NEW VAULT VM in virt-manager", "2. MAKE TEMPLATE of the VAULT",
               "3. CHECK / IMPORT TEMPLATE", "4. START: INTERNET", "4. START: OFFLINE")
HOWTO_TIPS = ("Goes to the VAULT tab. Create your VAULT VM there with virt-manager.",
              "Goes to the VAULT tab. Copy a shut-off VAULT VM into a protected template.",
              "Goes to the TEMPLATE tab. Import a template and check it.",
              "Opens the start dialog in INTERNET mode. Nothing starts until you click Start there.",
              "Opens the start dialog in OFFLINE mode. Nothing starts until you click Start there.")
HOWTO_TIP_NO_VAULT = "First create a VAULT VM (step 1): there is nothing to make a template from yet."
HOWTO_TIP_NO_TEMPLATE = "First create or import a template"
DE_HOWTO_TITLE = "SO GEHT'S"
DE_HOWTO_STEPS = ("1. NEUE VAULT-VM in virt-manager ANLEGEN", "2. TEMPLATE aus dem VAULT ERSTELLEN",
                  "3. TEMPLATE PRÜFEN / IMPORTIEREN", "4. START: INTERNET", "4. START: OFFLINE")
DE_HOWTO_TIPS = ("Wechselt zum Reiter VAULT. Dort legst du deine VAULT-VM mit virt-manager an.",
                 "Wechselt zum Reiter VAULT. Kopiert eine ausgeschaltete VAULT-VM in ein geschütztes Template.",
                 "Wechselt zum Reiter TEMPLATE. Dort importierst und prüfst du ein Template.",
                 "Öffnet den Startdialog im Modus INTERNET. Gestartet wird erst mit Start im Dialog.",
                 "Öffnet den Startdialog im Modus OFFLINE. Gestartet wird erst mit Start im Dialog.")
DE_HOWTO_TIP_NO_VAULT = "Lege zuerst eine VAULT-VM an (Schritt 1): Es gibt noch nichts, woraus ein Template entstehen könnte."
DE_HOWTO_TIP_NO_TEMPLATE = "Zuerst ein Template erstellen oder importieren"

# Tastaturbedienung (0.6.15): Knopf, Tooltips, Hilfefenster (F1)
BTN_KEYS = "⌨ Keys"
BTN_KEYS_TIP = "Keyboard help (F1): Tab to move, arrow keys to switch tabs, Enter to select, Esc to go back."
TABS_TIP = "Tip: Tab to move, arrow keys to switch tabs, Enter to select, Esc to go back."
KEYS_TITLE = "Keyboard help"
KEYS_ROWS = (("Tab / Shift+Tab", "Move to the next / previous element"),
             ("← →", "Switch the tab while the tab row has the focus"),
             ("↑ ↓", "Move in lists and between the HOW TO USE rows"),
             ("Enter", "Press the focused button (Space works too)"),
             ("Esc", "Close a window like ← BACK; leave fullscreen in the main window"),
             ("F11", "Fullscreen on / off"),
             ("F1", "Show this help"))
KEYS_NOTE = "A green double frame shows which element has the focus. Nothing starts without its confirmation window."
DE_BTN_KEYS = "⌨ Tasten"
DE_BTN_KEYS_TIP = "Tastaturhilfe (F1): Tab zum Wechseln, Pfeiltasten für die Reiter, Enter zum Auslösen, Esc zurück."
DE_TABS_TIP = "Tipp: Mit Tab weiterspringen, mit den Pfeiltasten die Reiter wechseln, mit Enter auswählen, mit Esc zurück."
DE_KEYS_TITLE = "Tastaturhilfe"
DE_KEYS_ROWS = (("Tab / Umschalt+Tab", "Zum nächsten / vorigen Element"),
                ("← →", "Reiter wechseln, wenn die Reiterzeile den Fokus hat"),
                ("↑ ↓", "In Listen und zwischen den SO-GEHT'S-Zeilen bewegen"),
                ("Enter", "Fokussierten Knopf auslösen (Leertaste geht auch)"),
                ("Esc", "Fenster schließen wie ← ZURÜCK; im Hauptfenster Vollbild verlassen"),
                ("F11", "Vollbild an / aus"),
                ("F1", "Diese Hilfe zeigen"))
DE_KEYS_NOTE = "Ein grüner Doppelrahmen zeigt, welches Element den Fokus hat. Ohne Bestätigungsfenster startet nichts."

# Statuszeile unten (0.6.16): Kurztext zum fokussierten Element; rein informativ, löst nichts aus
STATUS_DEFAULT = "Tab to move, arrow keys to switch tabs, Enter to select, Esc to go back."
STATUS_LOCKED = "Locked: {reason}"
STATUS_TABS = {"vault": "1. VAULT tab: your VAULT VMs (read-only list) and Make template. Arrow keys switch tabs.",
               "template": "2. TEMPLATE tab: protected templates. Import, verify or remove them. Arrow keys switch tabs.",
               "disposable": "3. DISPOSABLE tab: start and stop throwaway VMs. Arrow keys switch tabs."}
STATUS_HOWTO = ("Step 1: opens the VAULT tab, where you create a VAULT VM in virt-manager. Enter to open.",
                "Step 2: opens the VAULT tab to make a template from a shut-off VAULT VM. Enter to open.",
                "Step 3: opens the TEMPLATE tab to import and check a template. Enter to open.",
                "Step 4: opens the start dialog in INTERNET mode. Nothing starts until you click Start there.",
                "Step 4: opens the start dialog in OFFLINE mode (no network at all). Nothing starts until you click Start.")
STATUS_FULLSCREEN = "Fullscreen: switches the window to fullscreen and back. Enter to toggle (F11)."
STATUS_KEYS = "Keys: shows the keyboard help. Enter to open (F1)."
STATUS_LIST_TEMP = "List of running disposable VMs. Up/Down to select; details appear below."
STATUS_LIST_TPL = "List of templates. Up/Down to select, then Verify or Remove."
STATUS_LIST_VAULT = "List of VAULT VMs (read-only). Up/Down to select, then Make template."
STATUS_COMBO = "Template to start from. Up/Down to change."
STATUS_START = "Start Disposable VM: INTERNET: opens the start dialog. Nothing starts until you click Start there. Enter to open."
STATUS_START_OFFLINE = "Start Disposable VM: OFFLINE: opens the start dialog, no network at all. Enter to open."
STATUS_SHOW = "Show selected VM: brings the window of the selected VM to the front. Enter to open."
STATUS_STOP = "Stop and erase VM: ends the selected VM and erases all its data. Asks first. Enter to open."
STATUS_DETAILS = "OPEN/CLOSE DETAILS: opens or closes the Live Monitor window (RAM, CPU, network) of the selected VM. Enter to switch."
STATUS_IMPORT = "Import template: copies a template VM into the protected store. Enter to open."
STATUS_VERIFY = "Verify: checks that the selected template copy is unchanged (SHA-256). Enter to run."
STATUS_VERIFY_CHK = "Check the template copy in the background after every VM shutdown. Space to toggle."
STATUS_REMOVE = "Remove template: deletes the selected template copies after asking. Enter to open."
STATUS_MAKE = "Make template: copies the selected VAULT into a template. Enter to open."
STATUS_VIRT_MANAGER = "Create new VAULT VM: opens virt-manager so you can create a VAULT VM. Enter to open."
STATUS_HINT_CLOSE = "Closes this hint. Enter to close."
STATUS_CANCEL_COPY = "Cancel: stops the running copy and removes the unfinished file. Enter to cancel."
DE_STATUS_DEFAULT = "Tab zum Wechseln, Pfeiltasten für die Reiter, Enter zum Auswählen, Esc zurück."
DE_STATUS_LOCKED = "Gesperrt: {reason}"
DE_STATUS_TABS = {"vault": "Reiter 1. VAULT: deine VAULT-VMs (nur lesen) und Make template. Pfeiltasten wechseln den Reiter.",
                  "template": "Reiter 2. TEMPLATE: geschützte Templates importieren, prüfen, entfernen. Pfeiltasten wechseln den Reiter.",
                  "disposable": "Reiter 3. DISPOSABLE: Wegwerf-VMs starten und beenden. Pfeiltasten wechseln den Reiter."}
DE_STATUS_HOWTO = ("Schritt 1: öffnet den Reiter VAULT, dort legst du eine VAULT-VM in virt-manager an. Enter zum Öffnen.",
                   "Schritt 2: öffnet den Reiter VAULT, um aus einer ausgeschalteten VAULT-VM ein Template zu machen.",
                   "Schritt 3: öffnet den Reiter TEMPLATE zum Importieren und Prüfen. Enter zum Öffnen.",
                   "Schritt 4: öffnet den Startdialog im Modus INTERNET. Gestartet wird erst mit Start im Dialog.",
                   "Schritt 4: öffnet den Startdialog im Modus OFFLINE (gar kein Netz). Gestartet wird erst mit Start.")
DE_STATUS_FULLSCREEN = "Vollbild: schaltet das Fenster auf Vollbild und zurück. Enter zum Umschalten (F11)."
DE_STATUS_KEYS = "Tasten: zeigt die Tastaturhilfe. Enter zum Öffnen (F1)."
DE_STATUS_LIST_TEMP = "Liste der laufenden Wegwerf-VMs. Hoch/Runter wählt aus; Details erscheinen darunter."
DE_STATUS_LIST_TPL = "Liste der Templates. Hoch/Runter wählt aus, dann Verify oder Remove."
DE_STATUS_LIST_VAULT = "Liste der VAULT-VMs (nur lesen). Hoch/Runter wählt aus, dann Make template."
DE_STATUS_COMBO = "Template, aus dem gestartet wird. Hoch/Runter ändert."
DE_STATUS_START = "Wegwerf-VM starten: INTERNET: öffnet den Startdialog. Gestartet wird erst mit Start im Dialog."
DE_STATUS_START_OFFLINE = "Wegwerf-VM starten: OFFLINE: öffnet den Startdialog, gar kein Netz. Enter zum Öffnen."
DE_STATUS_SHOW = "Gewählte VM anzeigen: holt das Fenster der gewählten VM nach vorn. Enter zum Öffnen."
DE_STATUS_STOP = "VM beenden und löschen: beendet die gewählte VM und löscht alle ihre Daten. Fragt vorher nach."
DE_STATUS_DETAILS = "DETAILS ÖFFNEN/SCHLIESSEN: öffnet oder schließt das Fenster Live Monitor (RAM, CPU, Netz) der gewählten VM. Enter schaltet um."
DE_STATUS_IMPORT = "Template importieren: kopiert eine Template-VM in den geschützten Bestand. Enter zum Öffnen."
DE_STATUS_VERIFY = "Prüfen: kontrolliert, ob die gewählte Template-Kopie unverändert ist (SHA-256). Enter zum Ausführen."
DE_STATUS_VERIFY_CHK = "Template-Kopie nach jedem VM-Ende im Hintergrund prüfen. Leertaste schaltet um."
DE_STATUS_REMOVE = "Template entfernen: löscht die gewählten Template-Kopien nach Rückfrage. Enter zum Öffnen."
DE_STATUS_MAKE = "Make template: kopiert die gewählte VAULT-VM in ein Template. Enter zum Öffnen."
DE_STATUS_VIRT_MANAGER = "Neue VAULT-VM anlegen: öffnet virt-manager, um eine VAULT-VM anzulegen. Enter zum Öffnen."
DE_STATUS_HINT_CLOSE = "Schließt diesen Hinweis. Enter zum Schließen."
DE_STATUS_CANCEL_COPY = "Abbrechen: stoppt das laufende Kopieren und löscht die unfertige Datei. Enter zum Abbrechen."

# 0.7.5 EXIT-Knopf oben rechts und Bestätigungsdialog (drei Wege mit laufenden Wegwerf-VMs, sonst kurze Rückfrage)
BTN_EXIT = "EXIT"
BTN_EXIT_TIP = "Closes EVOX. You are asked first; running disposable VMs can stay running or be erased."
EXIT_TITLE_VMS = "Exit EVOX? {n} disposable VM(s) running"
EXIT_TEXT_VMS = ("<b>{n}</b> disposable VM(s) are running:\n{names}\n\n"
                 "KEEP VMs RUNNING closes only this window; the VMs keep running.\n"
                 "SHUT DOWN &amp; ERASE VMs ends them and erases all their data, then closes this window.")
EXIT_TITLE_NONE = "Exit EVOX?"
EXIT_TEXT_NONE = "No disposable VM is running. Close EVOX?"
EXIT_KEEP = "KEEP VMs RUNNING"
EXIT_ERASE = "SHUT DOWN & ERASE VMs"
EXIT_CONFIRM = "EXIT"
MSG_EXIT_ERASING = "Shutting down and erasing {n} disposable VM(s)…"
MSG_EXIT_FAILED = "Not erased, EVOX stays open: {items}"
STATUS_EXIT = "EXIT: closes EVOX after a confirmation. Running disposable VMs can stay running or be erased. Enter to open."
DE_BTN_EXIT = "BEENDEN"
DE_BTN_EXIT_TIP = ("Schließt EVOX. Vorher wird gefragt; laufende Wegwerf-VMs können weiterlaufen oder gelöscht werden.")
DE_EXIT_TITLE_VMS = "EVOX beenden? {n} Wegwerf-VM(s) laufen"
DE_EXIT_TEXT_VMS = ("<b>{n}</b> Wegwerf-VM(s) laufen:\n{names}\n\n"
                    "VMs WEITERLAUFEN LASSEN schließt nur dieses Fenster; die VMs laufen weiter.\n"
                    "VMs BEENDEN &amp; LÖSCHEN beendet sie und löscht alle ihre Daten, danach schließt dieses Fenster.")
DE_EXIT_TITLE_NONE = "EVOX beenden?"
DE_EXIT_TEXT_NONE = "Es läuft keine Wegwerf-VM. EVOX schließen?"
DE_EXIT_KEEP = "VMs WEITERLAUFEN LASSEN"
DE_EXIT_ERASE = "VMs BEENDEN & LÖSCHEN"
DE_EXIT_CONFIRM = "BEENDEN"
DE_MSG_EXIT_ERASING = "{n} Wegwerf-VM(s) werden beendet und gelöscht…"
DE_MSG_EXIT_FAILED = "Nicht gelöscht, EVOX bleibt offen: {items}"
DE_STATUS_EXIT = "BEENDEN: schließt EVOX nach einer Rückfrage. Laufende Wegwerf-VMs können weiterlaufen oder gelöscht werden. Enter zum Öffnen."

# Color settings (0.8.0, A4a): nur Englisch (Entscheidung Benutzer); keine DE_-Varianten
BTN_COLORS = "Color settings"
BTN_COLORS_TIP = "Choose a theme, change colors and the text size. Safety colors (red) stay fixed."
STATUS_COLORS = "Color settings: theme, colors and text size. Enter to open."
# Klartext-Rollennamen (0.8.1): EINE Stelle; theme.ROLES leitet seine Bezeichnungen hieraus ab (Tooltip, Dialog, Kontrastmeldungen)
ROLE_NAMES = {
    "background": "Window background",
    "text": "Normal text",
    "title": "Title",
    "heading": "Headings and tagline",
    "vault": "VAULT tab / Create VAULT VM button / step 1",
    "vault_border": "VAULT tab border",
    "vault_text": "VAULT tab text",
    "template": "TEMPLATE tab / Import button / step 3",
    "template_border": "TEMPLATE tab border",
    "template_text": "TEMPLATE tab text",
    "disposable": "DISPOSABLE tab / Start INTERNET button / step 4",
    "disposable_border": "DISPOSABLE tab border",
    "disposable_text": "DISPOSABLE tab text",
    "offline": "Start OFFLINE button",
    "offline_border": "Start OFFLINE button border",
    "offline_text": "Start OFFLINE button text",
    "step2": "HOW TO step 2 button",
    "step2_border": "HOW TO step 2 border",
    "step2_text": "HOW TO step 2 text",
    "make": "Make template button",
    "make_border": "Make template button border",
    "make_text": "Make template button text",
    "verify": "Verify button",
    "verify_border": "Verify button border",
    "verify_text": "Verify button text",
    "remove": "Remove button",
    "remove_border": "Remove button border",
    "remove_text": "Remove button text",
    "neutral": "Show / Fullscreen / Details buttons",
    "neutral_border": "Show button border",
    "neutral_text": "Show button text",
    "aux": "Helper buttons (Keys, Color settings)",
    "aux_border": "Helper button border",
    "aux_text": "Helper button text",
    "exit": "EXIT button",
    "exit_border": "EXIT button border",
    "exit_text": "EXIT button text",
    "back": "← BACK button",
    "back_border": "← BACK button border",
    "back_text": "← BACK button text",
    "sel_amber": "VAULT selected row",
    "sel_amber_text": "VAULT selected row text",
    "sel_amber_alt": "VAULT selected red row text",
    "sel_teal": "TEMPLATE selected row",
    "sel_teal_text": "TEMPLATE selected row text",
    "sel_teal_alt": "TEMPLATE selected -BACKUP row text",
    "sel_green": "DISPOSABLE selected row",
    "sel_green_text": "DISPOSABLE selected row text",
    "sel_green_alt": "DISPOSABLE selected red row text",
    "backup_text": "-BACKUP row text (not selected)",
    "focus": "Keyboard focus frame",
    "grp_everyday": "Quick purpose EVERYDAY",
    "grp_money": "Quick purpose MONEY",
    "grp_work": "Quick purpose WORK & TECH",
    "grp_more": "Quick purpose MORE",
    "grp_mylist": "Quick purpose MY LIST",
    "hint_bg": "Hint bar",
    "hint_text": "Hint bar text",
    "hint_mark_bg": "Hint marks",
    "hint_mark_fg": "Hint marks text",
    "step4_internet_ring": "Step 4 INTERNET ring",
    "step4_internet_glow": "Step 4 INTERNET glow",
    "step4_offline_ring": "Step 4 OFFLINE ring",
    "step4_offline_glow": "Step 4 OFFLINE glow",
    "flash": "Highlight flash",
    "name": "Names in dialogs and Live Monitor",
    "vm_name": "VM name in start dialog",
    "cpu_bar": "CPU bar",
}

# Klartextnamen der Vorschau-Elemente (Tooltip, Statuszeile, Dialog); Zuordnung Element -> Rolle: theme.PREVIEW_ELEMENTS
ELEMENT_NAMES = {
    "title": "Title",
    "heading": "Heading",
    "text": "Normal text",
    "name": "VM name",
    "background": "Window background",
    "tab_vault": "VAULT tab",
    "tab_template": "TEMPLATE tab",
    "tab_disposable": "DISPOSABLE tab",
    "row_vault_sel": "VAULT selected row",
    "row_vault_normal": "VAULT normal row",
    "row_template_sel": "TEMPLATE selected row",
    "row_template_backup": "TEMPLATE -BACKUP row",
    "row_disposable_sel": "DISPOSABLE selected row",
    "row_disposable_normal": "DISPOSABLE normal row",
    "btn_virt": "Create VAULT VM button",
    "btn_make": "Make template button",
    "btn_import": "Import template button",
    "btn_verify": "Verify button",
    "btn_remove": "Remove button",
    "btn_start_internet": "Start INTERNET button",
    "btn_start_offline": "Start OFFLINE button",
    "btn_show": "Show button",
    "btn_keys": "Keys / Color settings button",
    "btn_exit": "EXIT button",
    "btn_back": "← BACK button",
    "fixed_stop": "Stop and erase (fixed)",
    "fixed_shut": "SHUT DOWN & ERASE (fixed)",
    "fixed_inactive": "INACTIVE (fixed)",
    "fixed_error": "Error message (fixed)",
}
# Teile eines Elements (0.8.2): Schrift und Fläche getrennt wählbar
PART_NAMES = {"text": "Text color", "background": "Background color", "selected_text": "Text color when selected"}
PART_TIPS = {"text": "Change the color of the writing", "background": "Change the color of the surface",
             "selected_text": "Change the writing color while the row is selected"}
CS_PARTS_TIP = "{name}: click to change its text or background color."
CS_PARTS_TIP_SEL = "{name}: click to change its text color, or its text color when selected."
CS_STATUS_PARTS = "{name}: Enter or click, then choose Text color or Background color."
CS_STATUS_PARTS_SEL = "{name}: Enter or click, then choose Text color or Text color when selected."
CS_EDITING_PART = "Editing: {name} – {part}"
CS_PICKER_TITLE_PART = "{part} for: {name}"
CS_TITLE = "Color settings"
CS_THEME = "Theme"
CS_SIZE = "Text size"
CS_SIZE_TIP = "Text size of the whole window, 80 % to 150 % in steps of 10 %. 100 % is the default."
CS_SIZE_FMT = "{v} %"
CS_ROLE = "Color"
CS_PICK_TIP = "Click to pick a new color for the chosen item"
CS_RESET_ROLE = "Reset color"
CS_RESET_ROLE_TIP = "Back to the theme color for this item"
CS_RESET_THEME = "Reset to theme"
CS_RESET_THEME_TIP = "Undo all own colors of this theme"
CS_SAVE = "Save"
CS_USE_ANYWAY = "Use anyway"
CS_USE_ANYWAY_TIP = "Keep the hard-to-read color anyway"
CS_PREVIEW = "Preview"
CS_PV_TEXT = "Normal text on the background"
CS_PV_HEADING = "Heading example"
CS_PV_SELECTED = "selected"
CS_PV_NORMAL = "normal"
CS_PV_BACKUP = "-BACKUP"
CS_PV_NAME = "DISPOSABLE-EMAIL-01"
CS_PV_FIXED = "Fixed for safety:"
CS_PV_FIXED_STOP = "Stop and erase"
CS_PV_FIXED_SHUT = "SHUT DOWN & ERASE"
CS_PV_FIXED_INACTIVE = "INACTIVE"
CS_PV_FIXED_ERROR = "Error message"
CS_PV_FIXED_TIP = "Fixed for safety. This red cannot be changed."
CS_PV_HINT = "Click any item in the preview (or press Enter on it) to change its color."
BTN_VIRT_SHORT = "Create VAULT VM"
CS_SAFETY_NOTE = ("Fixed for safety, not changeable: Stop and erase, SHUT DOWN & ERASE, danger red, "
                  "network lock INACTIVE, error messages, INTERNET/OFFLINE mode bars.")
CS_OK = "✔ Contrast {ratio}:1 – easy to read."
CS_WARN = "⚠ Contrast only {ratio}:1 ({pair}) – hard to read. Pick another color or click Use anyway."
CS_BAD = "✖ Contrast only {ratio}:1 ({pair}) – very hard to read! You can still click Use anyway."
CS_REJECT = "✖ This item cannot be changed ({pair})."
CS_ACCEPTED = "⚠ Kept anyway: contrast {ratio}:1 ({pair})."
CS_FOCUS_CLASH = "⚠ The focus frame is hard to see on: {items}. The dark inner line still shows it."
CS_COMPARE = "Compare"
CS_COMPARE_TIP = "Hold to see the color before your last change. Release to see the new color again. Changes nothing."
CS_COMPARE_NONE = "Nothing to compare yet: change a color first."
CS_COMPARE_SHOWING = "Showing the old color of: {name}. Release to see the new one."
CS_EDITING = "Editing: {name}"
CS_FIXED_INFO = "{name}: fixed for safety, cannot be changed."
CS_PICKER_TITLE = "Color for: {name}"
CS_STATUS_ELEMENT = "{name}: Enter or click to change its color."
CS_STATUS_FIXED = "{name}: fixed for safety, not changeable."
CS_STATUS_COMPARE = "Compare: hold the button (or Space) to see the old color of the last change."
CS_STATUS_DEFAULT = "Preview: click an item (or Tab to it and press Enter) to change its color."
CS_FOCUS_ENV = "Note: EVOXD_FOCUS_COLOR is set and overrides the focus color."
CS_THEME_CHANGED = "Theme changed. Own colors were cleared."
CS_EXPORT = "Export theme…"
CS_EXPORT_TIP = "Save your colors as a theme file (.json) that you can share or load again"
CS_IMPORT = "Import theme…"
CS_IMPORT_TIP = "Load a theme file. Only plain colors are read; fixed safety colors never change."
CS_EXPORT_TITLE = "Export theme"
CS_IMPORT_TITLE = "Import theme"
CS_FILE_FILTER = "Theme files (*.json)"
CS_EXPORTED = "Theme saved to {path}."
CS_EXPORT_FAILED = "Could not save the theme file: {err}"
CS_IMPORTED = "Theme loaded: {n} own colors. Check the preview, then Save."
CS_IMPORT_FAILED = "Theme file refused: {err}"
CS_RESET_DONE = "All colors are back to the theme."
MSG_COLORS_SAVED = "Colors and text size saved and applied."
MSG_COLORS_FAILED = "Could not save the color settings: {err}"
BTN_START_SHORT = "Start: INTERNET"
BTN_START_OFFLINE_SHORT = "Start: OFFLINE"
BTN_IMPORT_SHORT = "Import"
BTN_MAKE_SHORT = "Make template"
BTN_VERIFY_SHORT = "Verify"
BTN_REMOVE_SHORT = "Remove"
BTN_SHOW_SHORT = "Show"
BTN_STOP_SHORT = "Stop and erase (fixed)"

# Setup check (0.10.0, A6): nur Englisch; Befehle kommen aus dem festen Katalog in setupcheck.py
BTN_SETUP = "Setup check"
BTN_SETUP_TIP = "Checks packages, groups, services and the EVOX setup. Fixes open in a terminal after you confirm."
STATUS_SETUP = "Setup check: shows what this computer still needs. Enter to open."
BTN_DOCS = "Documentation"
BTN_DOCS_TIP = "Opens the documentation (Easy Guide, Quick Guide, Full Manual, Developer Doc) in your browser. Local files, no internet."
STATUS_DOCS = "Documentation: choose a language and a document to open in your browser. Enter to open."
DOCS_TITLE = "Documentation"
DOCS_VERSION = "Docs for version {v}"
DOCS_OLDER = "These docs are for version {d}, this program is {p}. They may be out of date."
DOCS_LANG = "Language"
DOCS_LANG_EN = "English"
DOCS_LANG_DE = "Deutsch"
DOCS_OPEN = "Open"
DOCS_SOON = "coming soon"
DOCS_MISSING = "file missing"
DOCS_CARDS = {"easy": ("Easy Guide", "Start here: one simple page with pictures. No technical words."),
              "quick": ("Quick Guide", "One page: the 4 steps, the network lock, keys and the main risks."),
              "full": ("Full Manual", "Threat model, comparison, troubleshooting, FAQ, CLI reference and more."),
              "dev": ("Developer Doc", "How EVOX is built: modules, tests, packaging.")}
DOCS_NOT_FOUND = "Not found: {name}"
CTX_HELP = "?"
CTX_HELP_TIP = "Opens the matching part of the Quick Guide in your browser."
CTX_HELP_STATUS = "Help: opens the Quick Guide in your browser. Enter to open."
SETUP_TITLE = "Setup check"
SETUP_STEP = "Step {n} of {m}: {what}"
SETUP_STEP_NAMES = ("Packages and internet", "Hardware", "Groups", "Services", "EVOX setup", "Template")
SETUP_CHECKING = "Checking…"
SETUP_READY = "Ready ✓ – everything is in place."
SETUP_PROBLEMS = "{n} item(s) need attention."
SETUP_REPORT_HEAD = "EVOX setup check"
SETUP_FIX = "Fix it"
SETUP_FIX_TIP = "Shows the exact command first. It only runs after you confirm, in a terminal where you type your password."
SETUP_RECHECK = "Check again"
SETUP_COPY = "Copy report"
SETUP_COPIED = "Report copied."
SETUP_LAUNCHER = "Create desktop launcher"
SETUP_LAUNCHER_TIP = "Puts an EVOX GUI launcher on your desktop (your home folder only)."
SETUP_PANEL_HINT = "To add EVOX to the panel: right-click the menu entry, then Add to panel."
SETUP_LAUNCHER_OK = "Launcher written: {path}"
SETUP_LAUNCHER_NOPKG = "The package menu entry was not found – launcher not created."
SETUP_LAUNCHER_NODIR = "No desktop folder inside your home folder – launcher not created."
SETUP_CONFIRM_TITLE = "Run this command?"
SETUP_CONFIRM_TEXT = "A terminal window opens and runs exactly this command. You type your password there, EVOX never sees it:"
SETUP_CONFIRM_OK = "Run in terminal"
SETUP_NO_TERMINAL = "No terminal found (gnome-terminal or x-terminal-emulator). Run the command by hand."
SETUP_TERMINAL_FAILED = "The terminal could not be started: {err}"
SETUP_TERMINAL_OPEN = "Terminal is open – close it to continue."
SETUP_NO_FIX = "No automatic fix for this item."
SETUP_BAR = "Setup check found {n} item(s) that need attention."
SETUP_BAR_OPEN = "Open Setup check"
SETUP_BAR_OPEN_TIP = "Opens the Setup check."
STATUS_SETUP_BAR_OPEN = "Opens the Setup check. Enter to open."
SETUP_NOT_INSTALLED = "not installed"
SETUP_MISSING = "missing"
SETUP_NET_OK = "Internet reachable (for apt)"
SETUP_NET_BAD = "Internet not reachable"
SETUP_WHY_NET = "apt needs the internet to install missing packages; connect first, then check again."
SETUP_KVM_OK = "/dev/kvm is available"
SETUP_KVM_MISSING = "/dev/kvm is missing"
SETUP_KVM_DENIED = "/dev/kvm cannot be read or written"
SETUP_WHY_KVM = "Without KVM virtual machines are extremely slow; enable virtualization in the BIOS/UEFI."
SETUP_WHY_KVM_ACCESS = "VMs need access to /dev/kvm; the kvm group usually grants it (see Groups)."
SETUP_RAM = "Free RAM: {gib:.1f} GiB"
SETUP_RAM_UNKNOWN = "Free RAM unknown"
SETUP_WHY_RAM = "Less than {gib} GiB free: only small VMs will start. Close other programs."
SETUP_DISK = "Free disk space: {gib:.0f} GiB"
SETUP_DISK_UNKNOWN = "Free disk space unknown"
SETUP_WHY_DISK = "Less than {gib} GiB free: templates and VM overlays need room. Free some space."
SETUP_GROUP_OK = "You are in the group {g}"
SETUP_GROUP_NOT = "You are not in the group {g}"
SETUP_GROUP_MISSING = "The group {g} does not exist"
SETUP_GROUP_RELOGIN = "Added to the group {g}, not active yet"
SETUP_RELOGIN = "log out and in again"
SETUP_WHY_GROUP = {
    "libvirt": "Members of libvirt may talk to the virtualization service without root.",
    "kvm": "Members of kvm may use hardware acceleration (/dev/kvm).",
}
SETUP_UNIT_OK = "Service {u} is active"
SETUP_UNIT_BAD = "Service {u} is not active"
SETUP_WHY_UNIT = {
    "libvirtd": "libvirt runs the virtual machines; without it EVOX cannot start anything.",
    "evoxd-netguard": "The net guard keeps OFFLINE VMs off the network; EVOX refuses to start VMs without it.",
}
SETUP_EVOX_NO_LIBVIRT = "libvirt is not reachable"
SETUP_EVOX_NET = "EVOX network"
SETUP_EVOX_FILTER = "EVOX network filter"
SETUP_EVOX_POOLS = "EVOX storage pools"
SETUP_WHY_EVOX = "EVOX needs its own network, filter and storage pools; `evoxd setup` creates them once."
SETUP_TPL_OK = "{n} template(s) available"
SETUP_TPL_NONE = "No template yet"
SETUP_TPL_UNKNOWN = "Templates could not be read"
SETUP_WHY_TPL = "Disposable VMs are started from a template."
SETUP_TPL_HINT = "Use Import from existing VM or Create new VAULT VM (HOW TO USE, steps 1 and 2)."
SETUP_WHY_PKG = {
    "python3-libvirt": "EVOX talks to libvirt through this Python module.",
    "python3-gi": "The EVOX window is built with GTK through this module.",
    "gir1.2-gtk-3.0": "Provides the GTK 3 library data for the window.",
    "libvirt-daemon-system": "The libvirt service that runs the virtual machines.",
    "libvirt-daemon-driver-qemu": "Lets libvirt run QEMU/KVM machines.",
    "nftables": "The net guard uses it to block the network for OFFLINE VMs.",
    "iproute2": "Network tools used for the isolated EVOX network.",
    "virt-viewer": "Shows the window of a running VM.",
    "qemu-utils": "Disk image tools (overlays and checks).",
    "qemu-system-x86": "The emulator that runs the VMs.",
}

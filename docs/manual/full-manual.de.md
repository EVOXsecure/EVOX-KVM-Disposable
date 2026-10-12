# EVOX KVM DISPOSABLE – Handbuch
Version {{version}} · Deutsch · für den Alltag · Unbestätigtes ist als solches gekennzeichnet

## Was EVOX ist {#intro}
EVOX startet eine Wegwerf-VM (virtuelle Maschine) aus einer sauberen, geschützten Kopie eines Systems, das du selbst vorbereitet hast. Darin öffnest du einen riskanten Link oder eine unbekannte Datei. Drückst du **Stop and erase VM**, ist alles weg, was die VM getan hat. Solange sie läuft, ist die VM von deinem Rechner (dem *Host*), deinem Heimnetz und deinen anderen VMs abgeschnitten.

Dieses Handbuch erklärt, wogegen EVOX schützt, wogegen nicht, wie du es bedienst und welche Fehler du vermeiden musst. Aussagen stützen sich auf automatische Tests, auf die Netztests am Host (unten *H1*) oder auf Bestätigungen vom Host. Was nur erwartet wird, steht auch so da.

## Bedrohungsmodell {#threat}
**EVOX soll schützen gegen:**
- Schadsoftware oder eine bösartige Webseite in der VM, die sich auf deinem System **festsetzen** will: VM und Daten werden am Ende vernichtet.
- Eine übernommene VM, die deinen Host, Router, dein Heimnetz, andere VMs oder den Multicast-/Broadcast-Verkehr deines Netzes **erreichen** will: gesperrt durch die Netzsperre (siehe Kapitel H1-Nachweis).
- Eine VM, die **unbemerkt weiterläuft** und Netz hat: der Wächter überwacht die Sperre und trennt die VM, wenn die Sperre verloren geht.
- Datenreste auf der Platte: die VM schreibt in ein **verschlüsseltes Overlay**; der Schlüssel liegt nur im Arbeitsspeicher.
- Versehentliche Schäden an deinen eigenen VMs: EVOX schreibt nie auf deine VAULT-VMs (Regel R29).

**EVOX schützt nicht gegen:**
- Was **du selbst tippst**: Passwörter, Bankdaten, Kartennummern. Fragt eine Phishing-Seite danach, bekommt der Angreifer es. Siehe *Was EVOX nicht schützt*.
- Eine Lücke im Host-Kernel, in QEMU oder KVM, mit der ein Programm aus jeder VM ausbrechen kann (offene Grenze, siehe Vergleich).
- Einen Benutzer in der Gruppe `libvirt`, der gegen EVOX arbeitet: diese Gruppe ist unter Linux sehr mächtig (offene Grenze).
- Andere Programme auf deinem X11-Desktop, die Bildschirm oder Tastatur mitlesen (offene Grenze).
- Die VAULT-VM: sie läuft **ohne** Netzsperre, weil es deine eigene VM ist (offene Grenze).

## Vergleich: normales Linux, EVOX, Qubes OS {#compare}
{{svg:levels}}
Die Stufen sind Schritte, keine gemessenen Zahlen. Sie beschreiben, wie stark eine riskante Aufgabe vom Rest deiner Daten getrennt ist.

| | 1 Normales Linux | 2 EVOX | 3 Qubes OS |
|---|---|---|---|
| Wo riskante Arbeit stattfindet | In deiner normalen Sitzung, neben deinen Dateien | In einer Wegwerf-VM aus einem geschützten Template | Jede Aufgabe in einer eigenen isolierten VM, von Anfang an so gebaut |
| Was danach bleibt | Alles, was das Programm geschrieben hat | Nichts (Overlay und Schlüssel werden gelöscht) | Hängt von der VM ab; Wegwerf-VMs hinterlassen ebenfalls nichts |
| Netz zu Host und Heimnetz | Voll offen | Durch die Netzsperre gesperrt (in H1 bestätigt) | Getrennte Netz-VMs |
| Begründung der Stufe | Keine Trennung | Echte VM plus Sperre plus Löschen, läuft aber auf einem normalen Linux-Desktop | Das ganze System ist auf Isolation ausgelegt |
| Offene Grenzen | Alles | Gruppe libvirt, X11, VAULT ohne Netzsperre, Host-Kernel | Eigene, hier nicht behandelt |

EVOX ist **stärker als normales Linux** und **schwächer als Qubes OS**, weil EVOX auf einem gewöhnlichen Desktop aufsetzt. Das ist die ehrliche Begründung für Stufe 2. Wer die stärkste Trennung braucht, sollte Qubes OS nehmen.

## Installation {#install}
{{svg:flow}}
1. Paket installieren: `sudo apt install ./evoxd_<Version>_all.deb` (mit deinem Dateinamen). Es bringt die Programme `evoxd` und `evoxd-gui`, den Wächterdienst `evoxd-netguard`, diese Dokumentation und den Menüeintrag.
2. Trage dich in die Gruppen `libvirt` und `kvm` ein und **melde dich ab und wieder an** (der Setup check zeigt einen Hinweis, solange die neue Anmeldung fehlt).
3. EVOX-Speicher einmal anlegen. Im Projektordner: `sudo tools/setup-evoxd.sh --apply` (ohne `--apply` prüft es nur und zeigt, was es täte). Es legt `/srv/evoxd` mit den Unterordnern `templates` und `overlays` an.
4. EVOX-Netz, -Filter und -Speicherpools in libvirt einmal anlegen: `evoxd setup`.
5. `evoxd-gui` starten und den **Setup check** öffnen (nächstes Kapitel). Jeden roten Punkt beheben.

Voraussetzung: ein Rechner mit Hardware-Virtualisierung (`/dev/kvm`), mindestens 4 GiB verfügbarer RAM und 20 GiB freier Plattenplatz, damit der Setup check diese Punkte als in Ordnung meldet.

## Setup check {#setupcheck}
Das Fenster **Setup check** listet in sechs Schritten, was dem Rechner noch fehlt. Es erscheint beim ersten Start auch automatisch. Ein grünes ✔ heißt in Ordnung, ein rotes ✗ heißt, es fehlt etwas; ein kurzer Grund sagt warum.

| Schritt | Was geprüft wird |
|---|---|
| 1 Pakete und Internet | Die nötigen Pakete (`python3-libvirt`, `python3-gi`, `gir1.2-gtk-3.0`, `libvirt-daemon-system`, `libvirt-daemon-driver-qemu`, `nftables`, `iproute2`, `virt-viewer`, `qemu-utils`, `qemu-system-x86`) und ein einfacher Test, ob das Internet erreichbar ist |
| 2 Hardware | `/dev/kvm` ist vorhanden und du darfst es nutzen, verfügbarer RAM, freier Plattenplatz |
| 3 Gruppen | Du bist in `libvirt` und `kvm`; Hinweis, falls du dich noch neu anmelden musst |
| 4 Dienste | `libvirtd` und `evoxd-netguard` sind aktiv |
| 5 EVOX-Einrichtung | EVOX-Netz, EVOX-Netzfilter und EVOX-Speicherpools sind vorhanden |
| 6 Template | Mindestens ein Template ist vorhanden |

Zu jedem Problem gibt es den Knopf **Fix it**. Er zeigt zuerst den genauen Befehl und führt ihn erst nach deiner Bestätigung aus, in einem Terminal, in dem **du** dein Passwort eingibst. Die Befehle stammen aus einer festen Liste (Pakete, Gruppen, Dienste, `evoxd setup`). Das Fenster selbst bekommt nie Administratorrechte.

Der Knopf **?** öffnet dieses Kapitel. Der Internettest ist der einzige Netzzugriff, den EVOX selbst macht; die Dokumentation öffnet nur lokale Dateien.

## Die drei Reiter {#tabs}
EVOX hat drei Reiter, einen je Stufe. Benutze sie von links nach rechts.

### 1. VAULT
Deine eigenen VMs (Namen mit `VAULT-` am Anfang). Du legst sie in virt-manager an und pflegst sie dort; der Knopf **Create new VAULT VM in virt-manager…** öffnet es. EVOX **schreibt nie** auf eine VAULT-VM. Wähle eine ausgeschaltete VAULT-VM und drücke **Make template…**, um ihre Platte in ein neues geschütztes Template zu kopieren. Die Kopie braucht freien Platz in `/srv/evoxd`; EVOX prüft das vorher und zeigt den Plan.

### 2. TEMPLATE
Die geschützten Kopien. Knöpfe: **Import template…** (eine ausgeschaltete `TEMPLATE-*`-VM importieren), **Verify** (prüft die gespeicherte SHA-256-Prüfsumme; eine beschädigte Kopie wird markiert und startet keine neue VM mehr) und **Remove template…** (entfernt nur die Kopie, nie die Original-VM). Halte Templates sauber: siehe *Richtig benutzen und Risiken*.

### 3. DISPOSABLE
Hier arbeitest du. Knöpfe: **Start Disposable VM: INTERNET** (nur Internet), **Start Disposable VM: OFFLINE** (gar keine Verbindung, für Dateien, denen du nicht traust), **Show selected VM** (öffnet ihr Fenster), **Stop and erase VM** (beendet die gewählte VM sofort und löscht ihre Daten) und **OPEN DETAILS** (der Live Monitor). Der Startdialog fragt Template, Zweck, RAM und CPUs ab und prüft vor dem Start, dass der Host genug RAM frei behält. Eine laufende VM heißt `DISPOSABLE-<ZWECK>-NN`.

## HOW TO USE und Quick purpose {#howto}
**HOW TO USE** ist die Schrittliste oben im Hauptfenster: 1. Create new VAULT VM in virt-manager, 2. Make template of the VAULT, 3. Check / import template, 4. Start: INTERNET oder OFFLINE. Jede Zeile springt zum passenden Reiter oder öffnet den Startdialog. **Nichts startet, bis du im Dialog auf Start klickst.**

**Quick purpose** ist eine Knopfliste im Startdialog, in Gruppen sortiert (EVERYDAY, MONEY, WORK & TECH, MORE, MY LIST). Ein Druck füllt nur das Zweckfeld. Es startet nichts. Mit **Edit list…** änderst du die Liste; Zwecke bestehen nur aus Buchstaben und Ziffern, höchstens 16 Zeichen, und werden groß geschrieben. Der Zweck wird Teil des VM-Namens, so erkennst du die VMs.

## Live Monitor {#monitor}
**OPEN DETAILS** öffnet den Live Monitor für die gewählte VM: RAM, CPU, Netzverkehr und Overlay-Größe. Die Werte werden nur lesend aus libvirt geholt, etwa einmal pro Sekunde, solange eine VM läuft. RAM und CPU haben immer Symbol und Wort (zum Beispiel ● OK, ▲ HIGH, ■ FULL), nie nur eine Farbe. Mit `~` markierte RAM-Werte sind Schätzungen, wenn die VM sie nicht meldet. Das Fenster kann im Vordergrund bleiben. Beim Beenden schlägt EVOX unter Umständen eine RAM-Größe für das nächste Mal vor, nach dem höchsten gesehenen Wert. **Remember RAM for <ZWECK>** im Startdialog merkt sich deine Wahl.

## Themes und Color settings {#colors}
In **Color settings** (oben rechts) wählst du ein Theme, änderst einzelne Farben und stellst die Textgröße von 80 % bis 150 % in 10er-Schritten ein. Klicke ein Element in der Vorschau an (oder mit Tab hin und Enter) und wähle **Text color** oder **Background color**. Knöpfe: **Compare** (gedrückt halten, um die Farbe vor deiner letzten Änderung zu sehen), **Reset color**, **Reset to theme**, **Save**.

Der Kontrast wird als Verhältnis angezeigt. Unter 3:1 gibt es eine Warnung und du kannst **Use anyway** klicken; unter 2:1 ist die Warnung stärker (schwer lesbar). EVOX verweigert nie eine Farbe. Die **Sicherheitsfarben bleiben in jedem Theme fest**: Stop and erase, SHUT DOWN & ERASE, INACTIVE, Fehlermeldungen und die Modusfarben INTERNET / OFFLINE.

**Export theme…** speichert deine Farben als `.json`-Datei, **Import theme…** lädt eine. Gelesen werden nur einfache `#RRGGBB`-Farben, es gibt ein Größenlimit, und Sicherheitsfarben lassen sich per Datei nicht ändern. Wenn die Farben das Fenster unbenutzbar machen, starte einmal mit `EVOXD_RESET_COLORS=1 evoxd-gui`; die alte Konfiguration wird vorher gesichert.

{{svg:themes}}
Themes: Dark (Standard), Light, High Contrast, Nord, Solarized Dark, Dracula, Tron Legacy, Cyberpunk, Synthwave, Matrix, Amber Terminal. Die Farbfelder oben werden aus der Farbtabelle des Programms gelesen.

## Tastatur {#keys}
| Taste | Wirkung |
|---|---|
| Tab / Umschalt+Tab | Zum nächsten / vorigen Element |
| ← → | Reiter wechseln, solange die Reiterzeile den Fokus hat |
| ↑ ↓ | In Listen und zwischen den HOW-TO-USE-Zeilen bewegen |
| Enter (oder Leertaste) | Fokussierten Knopf drücken |
| Esc | Fenster wie ← BACK schließen; im Hauptfenster Vollbild verlassen |
| F11 | Vollbild an / aus |
| F1 | Tastaturhilfe |

Ein Rahmen zeigt, welches Element den Fokus hat. Die Zeile unten erklärt das fokussierte Element.

## Documentation-Dialog {#docs}
Der Knopf **Documentation** öffnet einen Dialog mit der Sprache (Englisch oder Deutsch, nach deiner Systemsprache vorbelegt, nicht gemerkt) und drei Karten: **Quick Guide** (eine Seite), **Full Manual** (dieses Dokument) und **Developer Doc** (nur Englisch). Eine Karte ist grau, solange ihre Datei fehlt. **Open** startet deinen Browser nur mit der lokalen Datei; es gibt keinen Netzzugriff und keinen automatischen Wechsel in die andere Sprache. Sind die Dokumente älter als das Programm, erscheint eine Warnung. Die **?**-Knöpfe in Setup check und Color settings öffnen das passende Kapitel dieses Handbuchs.

## Architektur {#arch}
{{svg:life}}
- **Template:** eine geschützte Kopie einer VAULT-Platte unter `/srv/evoxd/templates`, mit SHA-256-Prüfsumme, die *Verify* vergleicht.
- **Wegwerf-VM:** für eine Sitzung aus der neuesten Template-Kopie erzeugt. Ihre Definition entsteht aus einer festen Positivliste von Geräten und wird vor jedem Start geprüft. Die Zwischenablage ist aus.
- **Verschlüsseltes Overlay:** alle Schreibzugriffe gehen in ein eigenes LUKS-verschlüsseltes Overlay unter `/srv/evoxd/overlays`. Der Schlüssel ist zufällig, wird für diese VM erzeugt und nur im Arbeitsspeicher gehalten (ein libvirt-Secret). Mit dem Ende der VM sind Overlay und Schlüssel weg.
- **Netzsperre:** eine nftables-Tabelle, Routing-Regeln und ein libvirt-Netzfilter sperren das Netz der VM ein. Die Sperre wird geprüft, *bevor* die VM läuft; ohne funktionierende Sperre startet keine VM mit Netz.
- **Wächter:** der Dienst `evoxd-netguard` läuft als root unter systemd und überwacht die Sperre. Geht die Tabelle verloren, trennt er sofort alle Ports der EVOX-Bridge (*fail-closed*: im Zweifel kein Netz). EVOX startet ohne ihn keine VMs mit Netz.
- **Registry:** eine kleine Datenbank in deinem State-Ordner, die festhält, was EVOX vorhat und was es getan hat. Nach einem Absturz vergleicht `evoxd reconcile` sie mit libvirt und vernichtet Reste.
- **R29:** EVOX schreibt nie auf VAULT-VMs oder andere Arbeits-VMs. Einzige Ausnahme ist ein Aufräumskript, das du selbst startest.

{{svg:flowdata}}

## H1-Nachweis {#h1}
Die Netztests wurden am Host gemacht (*H1*) und vom Benutzer bestätigt. Die Tabelle zeigt, was aus einer Wegwerf-VM heraus geprüft wurde.

| Ziel | Ergebnis | Bestätigt |
|---|---|---|
| Router / Heimnetz | Gesperrt | Ja, am Host |
| Host | Gesperrt | Ja, am Host |
| Andere VM | Gesperrt | Ja, am Host |
| Multicast | Gesperrt | Ja, am Host |
| Broadcast | Gesperrt | Ja, am Host |
| Internet | Geht | Ja, am Host |
| DNS (Quad9) | Geht | Ja, am Host |
| IPv6 | Die VM hat keines | Ja, am Host |
| `evoxd netcheck` | OK | Ja, am Host |
| Wächter-Test | Fail-closed (Netz getrennt, wenn die Sperre verloren geht) | Ja, am Host |

Das zeigt den Stand zum Zeitpunkt der Tests. Es ist keine Garantie gegen Lücken im Host-Kernel oder in QEMU. Führe `evoxd netcheck` nach Updates, nach einem Neustart oder bei Zweifel aus; vor jedem Start ist es nicht nötig (die GUI zeigt "Network lock: active").

## Richtig benutzen und Risiken {#risks}
{{svg:risk}}
Jedes Risiko unten sagt, wie es passiert, wie EVOX es verhindert und was du tust.

| Risiko | Wie es passiert | Wie EVOX es verhindert | Was du tust |
|---|---|---|---|
| Zwischenablage | Text zwischen Host und VM würde Daten (oder Schadinhalt) hinüberbringen | Kein Zwischenablage-Kanal zwischen Host und VM; die Definition wird vor jedem Start geprüft | Kein Kopieren und Einfügen erwarten; Nötiges abtippen |
| Overlay: Daten auf der Platte | Fenster schließen oder Ausschalten lässt VM und Daten stehen | Schreiben geht in ein verschlüsseltes Overlay; der Schlüssel liegt nur im RAM und wird mit der VM zerstört | Immer **Stop and erase VM** benutzen, nie nur das Fenster schließen |
| Template nicht sauber | Ein Login, ein Virus oder ein Rest im Template landet in jeder neuen VM | Templates sind geschützte Kopien mit Prüfsumme; *Verify* findet Änderungen | Keine Logins und keine persönlichen Daten im Template; vor *Make template* Updates einspielen; nie ein `-BACKUP` als Template nehmen; ab und zu prüfen |
| Falscher Modus | Ein Dokument im INTERNET-Modus kann nach außen rufen | Der OFFLINE-Modus hat gar kein Netz | OFFLINE für Dokumente und Dateien, denen du nicht traust |
| Downloads und Passwörter | Alles in der VM wird am Ende gelöscht, auch Dateien, die du behalten wolltest | Nicht verhinderbar: Löschen ist der Zweck | Nichts Wichtiges in der VM speichern; keinen Passwortmanager darin benutzen |
| Absturz oder Stromausfall | Nach einem Host-Absturz kann eine VM oder ein Overlay übrig bleiben | Absichten und Taten stehen in der Registry | `evoxd reconcile` ausführen; es vernichtet Reste |
| Grenzen (offen) | Gruppe libvirt, X11, VAULT ohne Sperre, Host-Kernel (siehe Bedrohungsmodell) | Nicht abgedeckt | Host aktuell halten; nur vertrauenswürdige Benutzer in der Gruppe libvirt; die VAULT-VM nicht für riskante Aufgaben starten |

## Checklisten {#checklists}
**Vor dem Start**
1. Der Host ist aktuell und der Setup check zeigt kein ✗.
2. Das Template ist geprüft und sauber (und nicht zu alt).
3. Du hast den richtigen Modus gewählt: OFFLINE für Dateien und Dokumente.
4. Du weißt, was du in der VM tust und dass nichts bleibt.

**Nach dem Beenden**
1. Du hast **Stop and erase VM** gedrückt; die VM ist aus der Liste verschwunden.
2. Nichts Nötiges blieb in der VM.
3. `evoxd reconcile` nur bei Absturz oder Stromausfall, nicht nach normalem Stop.
4. Bei Verdacht auf ein Problem: siehe *Notfallseite*.

## Szenarien {#scenarios}
**E-Mail mit Link.** Starte INTERNET mit dem Zweck EMAIL, öffne den Link im Browser der VM, schließe mit *Stop and erase VM*. Verlangt die Seite ein Login, gib keine echten Passwörter ein (siehe *Was EVOX nicht schützt*).

**Online-Banking.** EVOX macht Banking nicht von allein sicherer: eine Seite, in die du Daten tippst, kann sie trotzdem stehlen. Eine Wegwerf-VM hilft nur gegen Software, die auf deinem Rechner bleiben will. Entscheide selbst, ob das passt; benutze die offizielle App oder Seite, tippe die Adresse selbst und gib Bankdaten nie auf einer Seite ein, die du über einen E-Mail-Link erreicht hast.

**Unbekannter Anhang.** Benutze den OFFLINE-Modus. Bring die Datei mit Vorsicht in die VM (die Zwischenablage ist aus; ein Dateiweg hängt von deiner VM-Einrichtung ab und ist nicht Teil von EVOX). Öffnen, ansehen, dann *Stop and erase VM*. Nichts verlässt die VM.

## Was EVOX nicht schützt {#notprotected}
- **Phishing-Eingaben.** EVOX kann eine echte nicht von einer falschen Seite unterscheiden. Alles, was du tippst, geht an den, der die Seite betreibt.
- **Selbst getippte Passwörter.** Ein Keylogger in der VM sieht sie. Ein in einer Wegwerf-VM getipptes Passwort gilt als der Seite und allem, was dort läuft, bekannt.
- **Was du danach mit dem Host machst.** Eine Datei aus der VM in dein normales System zu holen, bringt ihr Risiko mit.
- **Die offenen Grenzen** aus dem Bedrohungsmodell.

## Bekannte Grenzen {#limits}
Diese Grenzen sind in 1.0.0 offen. Das Design verbirgt sie nicht.
- **Wayland ist unbestätigt.** Das beschriebene Design setzt eine X11-Sitzung voraus. Unter Wayland hat es niemand geprüft.
- **Die Gruppe `libvirt` ist praktisch root-nah.** Wer in ihr ist, kann libvirt und damit VMs und Netzsperre ändern. Nur vertraute Benutzer gehören hinein.
- **X11 lässt Desktop-Programme aufeinander wirken.** Ein Programm auf deinem Desktop kann Bildschirm und Tastatur mitlesen und Eingaben einschleusen, auch in das VM-Fenster.
- **Die VAULT-VM hat keine EVOX-Netzsperre.** Das ist Absicht (Regel R29: EVOX fasst deine VAULT-VMs nie an). Nicht für riskante Aufgaben nutzen.
- **Host-Kernel, QEMU und KVM.** Ein Fehler dort kann ein Programm aus jeder VM ausbrechen lassen. Host aktuell halten.
- **Kein Datenaustausch zwischen Host und VM.** Zwischenablage und Dateiübertragung sind absichtlich zu. Dateien aus einer Wegwerf-VM lassen sich nicht behalten.
- **Nicht so stark wie Qubes OS.** EVOX läuft auf einem normalen Desktop; siehe Vergleich.
- **Noch nicht gesehen ([U]):** Druck und Seitenlayout der Handbücher auf einem echten Drucker sowie die Oberfläche unter Wayland.

## Datenschutz: was EVOX speichert {#privacy}
**EVOX speichert:**
- die **Registry** (`registry.sqlite3` in `~/.local/state/evoxd`): VM-Namen, Templates, was EVOX vorhatte und tat;
- **purpose-stats.json**: je Zweck den höchsten RAM-Wert und die Zahl der Starts;
- **config.json** (`~/.config/evoxd`): deine Zweckliste, gemerkte RAM-Größen, Host-Reserve, Aussehen (Theme, Farben, Textgröße);
- **gui.json** und **last-start.json**: Fenstergröße und -position, ob der Setup check gezeigt wurde, die letzten Startwahlen;
- die **Wächter-Statusdatei** in `/run/evoxd` (beim Neustart gelöscht).

**EVOX speichert nie:** Passwörter, VM-Inhalte, Browserdaten oder den Overlay-Schlüssel auf der Platte. Es sendet keine Daten irgendwohin. Der einzige eigene Netzzugriff ist der Internettest im Setup check; die Dokumentation benutzt nur lokale Dateien. Nichts aus der VM übersteht *Stop and erase VM*.

## Notfallseite {#emergency}
Wenn du glaubst, eine Wegwerf-VM wurde übernommen:
1. Drücke jetzt **Stop and erase VM** (oder `evoxd stop --all`).
2. Führe `evoxd reconcile` aus, dann `evoxd netcheck`. Beide sollten kein Problem melden.
3. Hast du ein Passwort in die VM getippt, **ändere es** von einem sauberen Gerät aus.
4. Kopiere keine Dateien aus der VM. Sie werden mit ihr gelöscht.
5. Meldet `netcheck` NOT OK oder zeigt die Liste **CUT (guard)**: der Wächter hat das Netz getrennt. Starte keine neuen VMs mit Netz, bis der Setup check wieder grün ist.
6. Verdächtigst du den Host selbst: trenne ihn vom Netz und benutze ein anderes Gerät für Passwörter. EVOX kann einen übernommenen Host nicht beurteilen.

## Template-Pflegeplan {#upkeep}
- **Monatlich:** VAULT-VM starten, alle Updates einspielen, herunterfahren, dann erneut *Make template…*. `evoxd template-list` markiert Templates, die älter als 14 Tage sind, als OLD.
- Funktioniert das neue Template, alte Versionen entfernen: `evoxd template-remove NAME --older`.
- Ab und zu prüfen: `evoxd template-verify NAME`.
- Keine Logins, keine persönlichen Dateien in der VAULT-VM, die du zum Template kopierst.
- Nie ein `-BACKUP` als Template benutzen.

## Glossar {#glossary}
- **VM (virtuelle Maschine):** ein Rechner, der in deinem Rechner nachgebildet wird.
- **Host:** dein echter Rechner.
- **VAULT:** deine eigene VM, von EVOX nie angefasst.
- **Template:** die geschützte saubere Kopie einer VAULT-VM.
- **Wegwerf-VM (Disposable):** eine einmalige VM aus einem Template.
- **Overlay:** der getrennte Bereich, in den die VM schreibt; am Ende gelöscht.
- **LUKS:** ein Standardverfahren zum Verschlüsseln einer Platte.
- **nftables:** die Linux-Firewall, die EVOX für die Netzsperre nutzt.
- **Wächter (Guard):** der Dienst, der die Netzsperre überwacht.
- **Fail-closed:** bei einem Fehler sperren statt erlauben.
- **libvirt / KVM / QEMU:** die Linux-Werkzeuge, die virtuelle Maschinen ausführen.
- **Gruppe libvirt:** eine Linux-Gruppe, deren Mitglieder alle VMs steuern dürfen; sehr mächtig.
- **X11:** das klassische Linux-Anzeigesystem; Programme darauf können einander beobachten.
- **Registry:** EVOX' eigene Aufzeichnung dessen, was es gestartet hat.
- **reconcile:** die Registry mit libvirt abgleichen und Reste aufräumen.

## Fehlersuche {#trouble}
| Symptom | Ursache | Lösung |
|---|---|---|
| Start abgelehnt, Netzsperre-Fehler | Wächterdienst nicht aktiv oder Sperre fehlt | Setup check Schritt 4 und 5; `evoxd netcheck` |
| Start abgelehnt, zu wenig RAM | Der Host würde unter seine Reserve fallen | Weniger RAM wählen oder Programme schließen; die Reserve ist in config.json einstellbar (`host_reserve_mib`) |
| Kein Template im Startdialog | Kein Template importiert | Kapitel *Die drei Reiter*: Make template oder Import |
| Template als DAMAGED markiert | Prüfsumme stimmt nicht | Erneut importieren oder die Kopie entfernen |
| Liste zeigt CUT (guard) | Der Wächter hat das Netz der VM getrennt | VM mit Stop and erase beenden; `evoxd netcheck` ausführen |
| VM-Fenster öffnet sich nicht | `virt-viewer` fehlt oder ist fehlgeschlagen | Setup check Schritt 1; *Show selected VM* erneut |
| VM-Rest nach Absturz | Host stürzte ab, während eine VM lief | `evoxd reconcile` |
| Setup check meldet Gruppe fehlt, obwohl eingetragen | Neue Anmeldung fehlt noch | Ab- und wieder anmelden |
| Documentation-Karte ist grau | Die Datei fehlt | Paket neu installieren |
| Unleserliche Farben | Eine gewählte Farbkombination | Color settings: Reset to theme, oder `EVOXD_RESET_COLORS=1 evoxd-gui` |

## FAQ {#faq}
**Sieht die VM meine Dateien?** Nach dem Entwurf nicht: sie hat keinen Zugriff auf Host oder Heimnetz.

**Warum ist die Zwischenablage aus?** Sie ist ein Weg, auf dem Daten zwischen Host und VM wechseln, also ist sie geschlossen.

**Ist der INTERNET-Modus sicher?** Die VM erreicht nur das Internet. Was sie dort tut, hängt von der Software darin ab.

**Kann ich eine Datei aus der VM behalten?** Nicht über EVOX. Alles wird gelöscht.

**Läuft EVOX unter Wayland?** Der dokumentierte Entwurf geht von einer X11-Sitzung aus; Wayland steht auf der Roadmap. Das Verhalten unter Wayland ist nicht bestätigt.

**Ist EVOX so sicher wie Qubes OS?** Nein. Siehe den Vergleich.

## Befehlszeile (CLI-Referenz) {#cli}
Rufe `evoxd --help` oder `evoxd <Befehl> --help` auf. `evoxd --version` zeigt die Version.

Normalerweise brauchst du diese nicht. Die Oberfläche erledigt das für dich.
- `evoxd reconcile`: nur nach Absturz, Stromausfall oder bei Auffälligkeiten nötig; nicht nach einem normalen *Stop and erase*.
- `evoxd netcheck`: nicht vor jedem Start nötig; die GUI zeigt die Netzsperre ("Network lock: active"). Sinnvoll nach Updates, nach einem Neustart oder bei Zweifel; Exitcode 2 bei Fehler.

| Befehl | Bedeutung | Optionen |
|---|---|---|
| `evoxd setup` | EVOX-Netz, -Filter und -Pools in libvirt anlegen (einmalig) | – |
| `evoxd template-import DOMAIN` | Geschützte Kopie einer ausgeschalteten `TEMPLATE-*`-VM importieren | – |
| `evoxd template-list` | Templates auflisten (Alter, Größe, Nutzung, Hinweise OLD / DAMAGED) | – |
| `evoxd template-verify NAME` | Prüfsumme prüfen (Standard: neueste Version); Exitcode 3 bei Abweichung | `--version N` |
| `evoxd template-remove NAME` | Importierte Kopie entfernen, nie die Original-Domain | `--version N` oder `--older` |
| `evoxd start TEMPLATE` | Wegwerf-VM aus der neuesten Kopie starten | `--purpose`, `--memory MIB` (Vielfache von 256), `--cpus`, `--no-net`, `--console` |
| `evoxd list` | Wegwerf-VMs auflisten | – |
| `evoxd stop [NAME…]` | Stop = VM vernichten | `--all` |
| `evoxd console NAME` | VM-Fenster öffnen | – |
| `evoxd reconcile` | Mit libvirt abgleichen, Reste vernichten (nur nach Absturz oder bei Auffälligkeiten) | – |
| `evoxd netcheck` | Netzsperre und Wächter prüfen; Exitcode 2, wenn nicht OK | – |

## Update und Backup {#update}
**Update:** das neue Paket mit `sudo apt install ./evoxd_<Version>_all.deb` installieren. Die Installation startet den Wächterdienst neu. Danach den Setup check öffnen (bei Zweifel `evoxd netcheck` ausführen). Konfiguration und State-Dateien bleiben.

**Backup:** deine VAULT-VMs und Templates liegen in libvirt und `/srv/evoxd`; sichere sie mit deinem üblichen Verfahren. EVOX selbst hat wenig zu sichern: `~/.config/evoxd/config.json` (deine Listen und Farben). Wegwerf-VMs und Overlays lohnen kein Backup.

## Änderungen (kurz) {#changelog}
- **1.0.0** Release: Doku-Durchsicht, Kapitel Bekannte Grenzen, Roadmap. Funktional identisch mit 0.10.4.
- **0.10.4** Druckränder und Hinweise zu reconcile / netcheck.
- **0.10.3** Handbuch EN + DE und Developer Doc; die **?**-Knöpfe öffnen es.
- **0.10.2** Documentation-Dialog, neuer Dokumentstil.
- **0.10.1** Quick Guide.
- **0.10.0** Setup check.
- **0.9.2** Sieben neue Themes.
- **0.9.1** Neues Icon.
- **0.9.0** Kontrast warnt nur; Theme-Export und -Import; Notfall-Farbreset.

## Roadmap V2.0 {#roadmap}
Pläne, keine Versprechen:
- Ein **pkexec-Helfer** mit fester Befehlsliste, damit Korrekturen kein Terminal brauchen.
- **Härtung der Gruppe libvirt** (heute eine offene Grenze).
- **Wayland**-Unterstützung.
- **Mehrere Sprachen** im Programm (heute ist die Oberfläche nur Englisch).
- **Aktive RAM-Optimierung**, nur als Angebot, das du annehmen oder ablehnen kannst.

## Lizenz, Haftung, Meldeweg {#license}
Die Lizenz steht in `/usr/share/doc/evoxd/copyright`. EVOX wird **ohne Gewährleistung** bereitgestellt. Es verringert Risiko, es beseitigt es nicht. Du benutzt es auf eigene Verantwortung, und die offenen Grenzen dieses Handbuchs gelten.

Einen Fehler meldest du mit: Version (`evoxd --version`), was du getan hast, die angezeigte Meldung und die Ausgabe von `evoxd netcheck`. Keine Passwörter oder privaten Daten angeben. Die Meldeadresse steht im Maintainer-Feld des Pakets (`dpkg -s evoxd`).

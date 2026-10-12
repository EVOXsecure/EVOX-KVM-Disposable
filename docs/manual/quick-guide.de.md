# EVOX KVM DISPOSABLE – Kurzanleitung (Quick Guide)
Version {{version}} · eine Seite · ausführlich im Handbuch (Full Manual)

## Was ist EVOX {#what}
EVOX startet eine Wegwerf-VM (virtuelle Maschine, ein Computer im Computer) aus einer sauberen Kopie deines Systems. Du öffnest einen riskanten Link oder eine Datei und drückst danach **Stop and erase VM**: Alles, was die VM getan hat, ist weg. Die VM ist von deinem Host (dem echten Rechner), deinem Heimnetz und deinen anderen VMs abgeschottet.

## Die 4 Schritte {#steps}
{{svg:flow}}
1. **VAULT** (Tresor): deine eigene VM, einmal in virt-manager eingerichtet. EVOX schreibt nie hinein.
2. **TEMPLATE** (Vorlage): eine geschützte Kopie einer VAULT-VM (Knopf *Make template*). Sauber halten.
3. **DISPOSABLE** (Wegwerf): der Reiter, in dem du Wegwerf-VMs startest und beendest.
4. **START**: *INTERNET* (nur Internet) oder *OFFLINE* (gar keine Verbindung, für fremde Dateien).

## Start und Ende {#startstop}
{{svg:life}}

## Netzsperre {#netlock}
Im Modus INTERNET erreicht die VM nur das Internet; Host, Router, Heimnetz und andere VMs sind gesperrt. OFFLINE hat gar keine Verbindung.

{{svg:flowdata}}

## Sicherheitsstufen {#levels}
{{svg:levels}}

## Tastatur {#keys}
**Tab** nächstes Element · **Pfeile** Reiter / Listen wechseln · **Enter** Knopf drücken · **Esc** zurück · **F1** Tastaturhilfe · **F11** Vollbild.

## Richtig benutzen und Risiken (Correct use and risks) {#risks}
| Risiko | So verhindert EVOX es | Das tust du |
|---|---|---|
| Zwischenablage (Clipboard) | Keine Zwischenablage zwischen Host und VM (in der VM-Definition abgeschaltet, vor jedem Start geprüft). | Nichts aus der VM kopieren oder hineinschieben; Nötiges abtippen. |
| Daten bleiben liegen | Die VM schreibt in ein verschlüsseltes Overlay (LUKS, Schreibschicht); der Schlüssel liegt nur im Arbeitsspeicher. | Immer **Stop and erase VM** benutzen, nie nur Fenster schließen oder ausschalten. |
| Verschmutztes Template | Templates sind geschützte Kopien und prüfbar (Verify). | Keine Logins im Template, Updates vor *Make template*, ein -BACKUP nie als Vorlage. |
| Falscher Modus | OFFLINE hat kein Netz. | OFFLINE für Dokumente und unbekannte Dateien. |
| Downloads und Passwörter weg | Alles verschwindet mit der VM. | Nichts Wichtiges dort lassen; kein Passwortmanager in Wegwerf-VMs. |
| Absturz oder Stromausfall | Reste werden vermerkt. | Nur dann `evoxd reconcile` ausführen. |
| Grenzen (offen) | Nicht abgedeckt: Mitglieder der Gruppe libvirt sind mächtig, X11 lässt Programme auf deinem Desktop einander sehen, eine VAULT-VM läuft ohne Netzsperre (Absicht), Wayland ist unbestätigt, es gibt keinen Datenaustausch zwischen Host und VM, ein Fehler in Host-Kernel oder QEMU kann aus jeder VM ausbrechen. EVOX ist nicht so stark wie Qubes OS. | Host aktuell halten; nur vertraute Benutzer in libvirt; VAULT-VM nicht für riskante Aufgaben starten. |

**Vor dem Start:** 1. Host aktuell, Setup check ohne ✗. 2. Template geprüft und sauber. 3. Richtiger Modus (OFFLINE für Dateien).
**Nach dem Beenden:** 1. VM nicht mehr in der Liste (*Stop and erase*). 2. Nichts Wichtiges blieb in der VM. 3. `evoxd reconcile` nur bei Absturz.

## Selten nötige Befehle {#cli}
Normalerweise brauchst du diese nicht. Die Oberfläche erledigt das für dich.
- `evoxd reconcile`: nur nach Absturz, Stromausfall oder bei Auffälligkeiten nötig; nicht nach einem normalen *Stop and erase*.
- `evoxd netcheck`: nicht vor jedem Start nötig; die GUI zeigt die Netzsperre ("Network lock: active"). Sinnvoll nach Updates, nach einem Neustart oder bei Zweifel; Exitcode 2 bei Fehler.

## Hilfe {#help}
Der Knopf **Documentation** (Hauptfenster) öffnet eine Auswahl der Anleitungen im Browser; **?** in Setup check und Color settings öffnet das passende Kapitel des Handbuchs. **Keys** oder F1 zeigt die Tastaturhilfe; **Setup check** zeigt, was der Rechner noch braucht. Tooltip beim Daraufzeigen; die untere Zeile erklärt das Element mit Fokus.

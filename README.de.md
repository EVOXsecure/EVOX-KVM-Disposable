# EVOX KVM DISPOSABLE (evoxd)

[English](README.md) | **Deutsch**

EVOX startet **virtuelle KVM-Wegwerf-Maschinen** für riskante Aufgaben wie E-Mails lesen oder im Web surfen.
Jede VM entsteht aus einer geschützten Kopie der Vorlage und wird beim Beenden **zerstört**. Nichts bleibt erhalten.
EVOX sperrt außerdem das Netz der VM auf das Internet (kein Zugriff auf dein LAN oder den Host); das erzwingt ein kleiner Guard-Dienst mit Root-Rechten.

Repository: https://github.com/EVOXsecure/EVOX-KVM-Disposable (Besitzer: EVOXsecure)

Version: 1.0.1 · Lizenz: GPL-3.0-or-later · Getestet auf **Linux Mint 22 / Ubuntu 24.04** (X11).

## Voraussetzungen

### Nötig

1. **x86-64-PC mit Linux Mint 22 / Ubuntu 24.04 und X11-Sitzung.** *Warum:* so wurde getestet; Wayland ist unbestätigt.
2. **CPU-Virtualisierung im BIOS/UEFI eingeschaltet:** Intel „Intel Virtualization Technology“ (VT-x) oder AMD „SVM Mode“ (AMD-V) → Enabled. *Warum:* KVM braucht sie; ohne sie fehlt `/dev/kvm` und VMs starten nicht oder sind extrem langsam.
   - **Wo:** meist Advanced → CPU Configuration (manchmal Security oder Overclocking). Die Namen unterscheiden sich je Hersteller; die BIOS-Taste ist oft Entf, F2 oder F10.
   - **Prüfen:** `grep -Ec '(vmx|svm)' /proc/cpuinfo` gibt eine Zahl über 0 aus, und `ls -l /dev/kvm` muss existieren.
3. **4 GiB freier RAM oder mehr.** *Warum:* VMs nehmen RAM vom Host (die kleinste VM braucht 1024 MiB); der Setup check warnt unter 4 GiB.
4. **50 GiB freier Speicherplatz empfohlen (mindestens 20 GiB).** *Warum:* EVOX selbst ist nur wenige MB groß, aber Vorlagen und VM-Platten sind groß. Eine einzelne kleine VM oder Vorlage kann etwa 10 GiB belegen, bei mehreren Vorlagen sind 50 GiB schnell verbraucht; verschlüsselte VM-Overlays wachsen während der Arbeit. Der Setup check warnt unter 20 GiB.
5. **Internet während der Installation.** *Warum:* apt lädt die Abhängigkeiten (libvirt, QEMU, nftables und mehr).
6. **Ein Benutzer mit sudo-Passwort.** *Warum:* Installation und Einrichtung brauchen Root; danach muss der Benutzer in den Gruppen `libvirt` und `kvm` sein („Fix it“ im Setup check, dann einmal aus- und einloggen).
7. **Nested Virtualization, wenn EVOX in einer VM läuft.** *Warum:* sonst gibt es in dieser VM kein `/dev/kvm`.

### Nicht nötig

- **VT-d / IOMMU.** *Warum nicht:* nur nötig, um echte Geräte (z. B. eine Grafikkarte) an eine VM durchzureichen; das macht EVOX nicht.
- **Secure Boot ändern.** *Warum nicht:* EVOX installiert keine Kernelmodule (nur Python-Dateien und Dienste), Secure Boot kann also an bleiben.
- **Spezielle Grafikkarte oder Treiber.** *Warum nicht:* die VM nutzt virtuelle Grafik.
- **Andere Virtualisierungssoftware (VirtualBox, VMware).** *Warum nicht:* EVOX bringt alles mit KVM/QEMU/libvirt mit.

## Installation mit dem Terminal

Für Linux Mint 22 / Ubuntu 24.04. Der Download liegt unter [Releases](https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest). Öffne ein Terminal und führe diesen Terminal-Befehl aus. Er lädt das Paket, prüft die Prüfsumme und installiert es. Du musst nur dein Passwort eingeben.

Terminal-Befehl:

```
B=https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest/download; cd ~ && wget -q $B/evoxd_1.0.1_all.deb $B/SHA256SUMS && sha256sum -c SHA256SUMS && sudo apt install ./evoxd_1.0.1_all.deb
```

- **Prüfsumme:** der Befehl bricht ab, wenn die Prüfsumme nicht stimmt. Die Prüfsumme schützt vor beschädigten Downloads, nicht vor einem kompromittierten Konto.
- **Nach der Installation:** EVOX starten → Setup check → bei den EVOX-Punkten „Fix it“ → einmal aus- und einloggen → „Check again“.
- **KVM:** `/dev/kvm` muss verfügbar sein (in einer VM: Nested Virtualization).
- **Kommandozeile:** `evoxd setup` (einmalig), `evoxd netcheck`, `evoxd list`.

## Bekannte Grenzen (kurz)

- **Wayland:** unbestätigt; X11 ist die getestete Sitzung.
- **Gruppe `libvirt`:** die Mitgliedschaft ist praktisch gleichwertig mit Root.
- **X11:** erlaubt Eingabe-Einschleusung zwischen Anwendungen.
- **VAULT-VMs:** haben keine EVOX-Netzsperre (gewollt).
- **Host-Abhängigkeit:** hängt von der Sicherheit von Host-Kernel, QEMU und KVM ab.
- **Keine Zwischenablage:** kein Austausch von Zwischenablage oder Daten zwischen Host und VM.
- **Qubes OS:** nicht so stark wie Qubes OS.

Siehe das Kapitel „Known limits“ im Full Manual.

## Dokumentation

[docs/manual/](docs/manual/) – Quick Guide, Easy Guide, Full Manual, Developer Doc (EN, teilweise DE).

## Sicherheit

Siehe [SECURITY.md](SECURITY.md).

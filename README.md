# EVOX KVM DISPOSABLE (evoxd)

EVOX starts **disposable KVM virtual machines** for risky tasks such as reading e-mail or browsing the web.
Every VM is created from a protected template copy and is **destroyed** when you stop it. Nothing is kept.
EVOX also keeps the VM's network locked to the internet only (no access to your LAN or the host), enforced by a small root guard service.

Repository: https://github.com/EVOXsecure/EVOX-KVM-Disposable (owner: EVOXsecure)

Version: 1.0.1 · License: GPL-3.0-or-later · Tested on **Linux Mint 22 / Ubuntu 24.04** (X11).

## Install EVOX KVM DISPOSABLE with Terminal

**English:** For Linux Mint 22 / Ubuntu 24.04. The download is on the [Releases page](https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest).
Open a terminal and run this terminal command. It downloads the package, checks its checksum and installs it. You only have to enter your password.

**Deutsch:** Für Linux Mint 22 / Ubuntu 24.04. Der Download liegt unter [Releases](https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest).
Öffne ein Terminal und führe diesen Terminal Befehl aus. Er lädt das Paket, prüft die Prüfsumme und installiert es. Du musst nur dein Passwort eingeben.

Terminal Command / Terminal Befehl:

```
B=https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest/download; cd ~ && wget -q $B/evoxd_1.0.1_all.deb $B/SHA256SUMS && sha256sum -c SHA256SUMS && sudo apt install ./evoxd_1.0.1_all.deb
```

- EN: Aborts if the checksum does not match. The checksum protects against corrupted downloads, not against a compromised account.
- DE: Bricht ab, wenn die Prüfsumme nicht stimmt. Die Prüfsumme schützt vor beschädigten Downloads, nicht vor einem kompromittierten Konto.
- EN: After installing: start EVOX → Setup check → click "Fix it" on the EVOX items → log out and in once → "Check again".
- DE: Nach der Installation: EVOX starten → Setup check → bei den EVOX-Punkten "Fix it" → einmal aus- und einloggen → "Check again".
- EN: `/dev/kvm` must be available (inside a VM: nested virtualization).
- DE: `/dev/kvm` muss verfügbar sein (in einer VM Nested Virtualization).

On the command line: `evoxd setup` (once), `evoxd netcheck`, `evoxd list`.

## Known limits (short)

- Wayland is unconfirmed; X11 is the tested session.
- Membership in group `libvirt` is practically root-equivalent.
- X11 allows input injection between applications.
- VAULT VMs have no EVOX network lock (by design).
- Depends on host kernel, QEMU and KVM security.
- No clipboard or data exchange between host and VM.
- Not as strong as Qubes OS.

See the chapter "Known limits" in the Full Manual.

## Documentation

[docs/manual/](docs/manual/) – Quick Guide, Easy Guide, Full Manual, Developer Doc (EN, partly DE).

## Security

See [SECURITY.md](SECURITY.md).

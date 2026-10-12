# EVOX KVM DISPOSABLE (evoxd)

EVOX starts **disposable KVM virtual machines** for risky tasks such as reading e-mail or browsing the web.
Every VM is created from a protected template copy and is **destroyed** when you stop it. Nothing is kept.
EVOX also keeps the VM's network locked to the internet only (no access to your LAN or the host), enforced by a small root guard service.

Repository: https://github.com/EVOXsecure/EVOX-KVM-Disposable (owner: EVOXsecure)

Version: 1.0.1 · License: GPL-3.0-or-later · Tested on **Linux Mint 22 / Ubuntu 24.04** (X11).

## Install (.deb from a release)

Download `evoxd_<version>_all.deb` and `SHA256SUMS` from the release page, then:

```
sha256sum -c SHA256SUMS --ignore-missing
sudo apt install ./evoxd_<version>_all.deb
```

Do not install if the check does not print `OK`.
Then start **EVOX** from the menu, open **Setup check** and fix everything marked ✗ (it tells you what the computer still needs).
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

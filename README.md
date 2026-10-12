# EVOX KVM DISPOSABLE (evoxd)

**English** | [Deutsch](README.de.md)

EVOX starts **disposable KVM virtual machines** for risky tasks such as reading e-mail or browsing the web.
Every VM is created from a protected template copy and is **destroyed** when you stop it. Nothing is kept.
EVOX also keeps the VM's network locked to the internet only (no access to your LAN or the host), enforced by a small root guard service.

Repository: https://github.com/EVOXsecure/EVOX-KVM-Disposable (owner: EVOXsecure)

Version: 1.0.1 · License: GPL-3.0-or-later · Tested on **Linux Mint 22 / Ubuntu 24.04** (X11).

## Requirements

### Required

1. **x86-64 PC with Linux Mint 22 / Ubuntu 24.04 and an X11 session.** *Why:* this is what was tested; Wayland is unconfirmed.
2. **CPU virtualization enabled in BIOS/UEFI:** Intel "Intel Virtualization Technology" (VT-x) or AMD "SVM Mode" (AMD-V) → Enabled. *Why:* KVM needs it; without it `/dev/kvm` is missing and VMs do not start or are extremely slow.
   - **Where:** usually Advanced → CPU Configuration (sometimes Security or Overclocking). Names differ by vendor; the BIOS key is often Del, F2 or F10.
   - **Check:** `grep -Ec '(vmx|svm)' /proc/cpuinfo` prints a number above 0, and `ls -l /dev/kvm` must exist.
3. **4 GiB free RAM or more.** *Why:* VMs take RAM from the host (the smallest VM uses 1024 MiB); Setup check warns below 4 GiB.
4. **50 GiB free disk space recommended (at least 20 GiB).** *Why:* EVOX itself is only a few MB, but templates and VM disks are large. A single small VM or template can be about 10 GiB, so with several templates 50 GiB is used up quickly; encrypted VM overlays grow while you work. Setup check warns below 20 GiB.
5. **Internet during installation.** *Why:* apt downloads the dependencies (libvirt, QEMU, nftables and more).
6. **A user with a sudo password.** *Why:* installation and setup need root; afterwards the user must be in the groups `libvirt` and `kvm` ("Fix it" in Setup check, then log out and in once).
7. **Nested virtualization if EVOX runs inside a VM.** *Why:* otherwise there is no `/dev/kvm` in that VM.

### Not needed

- **VT-d / IOMMU.** *Why not:* only needed to pass real devices (e.g. a graphics card) to a VM; EVOX does not do that.
- **Secure Boot change.** *Why not:* EVOX installs no kernel modules (only Python files and services), so Secure Boot can stay on.
- **Special graphics card or drivers.** *Why not:* the VM uses virtual graphics.
- **Other virtualization software (VirtualBox, VMware).** *Why not:* EVOX brings everything with KVM/QEMU/libvirt.

## Install with the terminal

For Linux Mint 22 / Ubuntu 24.04. The download is on the [Releases page](https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest). Open a terminal and run this terminal command. It downloads the package, checks its checksum and installs it. You only have to enter your password.

Terminal Command:

```
B=https://github.com/EVOXsecure/EVOX-KVM-Disposable/releases/latest/download; cd ~ && wget -q $B/evoxd_1.0.1_all.deb $B/SHA256SUMS && sha256sum -c SHA256SUMS && sudo apt install ./evoxd_1.0.1_all.deb
```

- **Checksum:** the command aborts if the checksum does not match. The checksum protects against corrupted downloads, not against a compromised account.
- **After installing:** start EVOX → Setup check → click "Fix it" on the EVOX items → log out and in once → "Check again".
- **KVM:** `/dev/kvm` must be available (inside a VM: nested virtualization).
- **Command line:** `evoxd setup` (once), `evoxd netcheck`, `evoxd list`.

## Known limits (short)

- **Wayland:** unconfirmed; X11 is the tested session.
- **Group `libvirt`:** membership is practically root-equivalent.
- **X11:** allows input injection between applications.
- **VAULT VMs:** have no EVOX network lock (by design).
- **Host dependence:** depends on host kernel, QEMU and KVM security.
- **No clipboard:** no clipboard or data exchange between host and VM.
- **Qubes OS:** not as strong as Qubes OS.

See the chapter "Known limits" in the Full Manual.

## Documentation

[docs/manual/](docs/manual/) – Quick Guide, Easy Guide, Full Manual, Developer Doc (EN, partly DE).

## Security

See [SECURITY.md](SECURITY.md).

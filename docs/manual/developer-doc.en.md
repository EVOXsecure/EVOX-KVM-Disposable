# EVOX KVM DISPOSABLE – Developer Doc
version {{version}} · English only · for people who change the code

## Overview {#overview}
EVOX (working name `evoxd`) is a Python 3 program: a GTK 3 window (`evoxd-gui`) and a command line (`evoxd`) on top of libvirt/QEMU/KVM, plus a root guard service (`evoxd-netguard`). The package is a plain `.deb` (architecture `all`) built by `packaging/build-deb.sh`. The standard library and the system Python modules are used; there is no pip dependency.

## Module map {#modules}
All modules are in `src/evoxd/`.

| Module | Purpose | Security file |
|---|---|---|
| `lifecycle.py` | Start, stop (= destroy), reconcile | **yes** |
| `domxml.py` | VM XML from an allow-list of devices, and its validation | **yes** |
| `capacity.py` | Capacity check (RAM, disk) before a start | **yes** |
| `guard.py` | Network guard service (root, systemd), fail-closed | **yes** |
| `config.py` | Names, paths, limits, `Settings`, config and state files | |
| `hv.py` | libvirt, only through the Python API | |
| `storage.py` | XML for pool, volume, overlay, secret; ephemeral LUKS key | |
| `registry.py` | Intent and log (SQLite) | |
| `ownership.py` | Central ownership check (R29) | |
| `lock.py` | `flock` lock | |
| `errors.py` | User-facing errors (`EvoxError`) | |
| `livestats.py` | Live values, read-only | |
| `purposes.py` | Purpose list of the start dialog | |
| `setupcheck.py` | Setup check items, fix commands from fixed lists | |
| `manual.py` | Opens documentation (local files, `xdg-open`, no shell) | |
| `theme.py` | Color roles, themes, CSS, contrast, theme export / import | |
| `texts.py` | All GUI texts | |
| `gui.py` | GTK 3 window, tabs, dialogs, Live Monitor, Color settings | |
| `cli.py` | `evoxd <command>` | |
| `net/model.py`, `net/check.py` | Network lock model (nftables, filter) and its check | |

Other folders: `tools/` (release, backup, build_manual, launchers), `packaging/` (deb files, service, icon, man page, changelog), `tests/`, `docs/`.

## Architecture {#arch}
- **Start:** `lifecycle` checks capacity and the network lock, creates the LUKS overlay with a random key (kept in memory as a libvirt secret), builds the XML in `domxml` (allow-list, validated), defines and starts the transient domain, and records intent and result in the registry.
- **Stop:** destroy the domain, remove overlay and secret, update the registry.
- **Reconcile:** compare registry and libvirt, destroy leftovers.
- **Network:** `net/model.py` defines the EVOX network (bridge `evoxd0`), the nwfilter `evoxd-clean` and the nftables table `evoxd`. `guard.py` loads and watches the table and writes `/run/evoxd/netguard.json`; if the table is lost it cuts all ports of the bridge.
- **Storage:** pools `evoxd-templates` and `evoxd-overlays` on `/srv/evoxd/templates` and `/srv/evoxd/overlays`, created by `tools/setup-evoxd.sh` (folders) and `evoxd setup` (pools).
- **libvirt access** only in `hv.py`, through the Python API, never by calling `virsh`.

## Config and state files {#files}
| File | Content |
|---|---|
| `~/.config/evoxd/config.json` | `host_reserve_mib`, `template_reserve_mib`, `purposes`, `remember_ram_mib`, `appearance` (theme, roles, accepted, font scale) |
| `~/.local/state/evoxd/registry.sqlite3` | Intent and log |
| `~/.local/state/evoxd/purpose-stats.json` | Per purpose: `peak_mib`, `starts` |
| `~/.local/state/evoxd/gui.json` | Window size, `maximized`, `details_expanded`, `monitor`, `monitor_pin`, `setup_seen` |
| `~/.local/state/evoxd/last-start.json` | Last start choices |
| `$XDG_RUNTIME_DIR/evoxd/lock` | `flock` lock |
| `/run/evoxd/netguard.json` | Guard status (written by the guard) |

Writers are atomic with mode 0600; a broken file is kept as `.broken-<time>`; other keys of a shared file are preserved. Paths follow `XDG_*` variables (`Settings`).

## Tests {#tests}
Run with `PYTHONPATH=src python3 -m unittest …`. The unit tests use `unittest` only.
- **Fake hypervisor:** `tests/fakehv.py` replaces `LibvirtHypervisor`. No libvirt, no `virsh`, no real VMs, no `sudo`.
- **nospawn:** `tests/nospawn.py` replaces `subprocess.Popen.__init__` so that no test can start a real program (only the Python interpreter is allowed). A violation fails the test even if the application swallows the error.
- **GUI tests** use stand-ins and count GTK calls; `test_cycle.py` checks that an unchanged refresh makes **0 GTK calls**.
- **Quick run:** `tools/test-quick.sh <keyword>` runs the test files whose name or content matches (for example `gui`, `theme`, `net`).
- **Full run:** only through `tools/release.sh` (see below), which runs the whole suite under `C.UTF-8` and `de_DE.UTF-8`.
- Tests for the documents (A7b) are in `tests/test_a7b.py` (well-formed HTML, same chapters in EN and DE, no external URLs, CLI reference complete, cards and anchors).

## Release {#release}
`tools/release.sh <version>` (`--dry-run` shows the steps): the version must equal `__version__` in `src/evoxd/__init__.py`; runs the tests in both locales, builds the `.deb` (`packaging/build-deb.sh`), runs `lintian` and `desktop-file-validate`, makes the backup (`tools/backup-projekt.sh`) and sends a desktop notification. Exit code ≠ 0 means: report, do not commit. After it: one documentation section (3–5 lines) in `docs/TECHNISCHER_IST-STAND.md`, a status line in `docs/KURZ.md`, then a local `git` commit. There is no remote. Project skills describe the routine: `evox-release`, `evox-regeln`, `evox-gui`, `evox-test`, `evox-hosttest`.

Documents: edit `docs/manual/*.md`, run `python3 tools/build_manual.py`, commit the generated `.html` too. `build-deb.sh` installs every `docs/manual/*.??.html` and `*.??.md` into `/usr/share/doc/evoxd/manual/`.

## Hard rules {#rules}
- **R29:** EVOX never writes to `VAULT-*` or work VMs. The only exception is `tools/cleanup-legacy.sh`, started by the user.
- **Security files** (`lifecycle.py`, `domxml.py`, `capacity.py`, `guard.py`) are changed only with the strongest model (Opus) and an explicit task.
- **Colors only through `theme.py`.** `gui.py` contains no color values. Safety colors are fixed and not part of any theme.
- **GUI text in English only,** and all of it in `texts.py`.
- **Cycle = 0 GTK calls** when nothing changed.
- No `sudo`, no `virsh`, no real VMs and no real network access in tests.
- Passwords, keys and LAN addresses do not belong in `docs/`.

## Theme system {#theme}
`theme.THEMES` maps a key to `{label, base, roles}`. `base` is `system` (GTK colors, used by the default Dark), `light` or `dark`. A theme is a dict of color roles, derived from `DARK` for most themes. `SAFETY` (danger red, error, INTERNET / OFFLINE mode colors, inner focus line) is applied last and cannot be overridden. `build_css(theme, overrides, focus, scale)` creates the whole CSS from the roles; the text size scales all `pt` values (80–150 %, step 10). User values must be strict `#RRGGBB`. Contrast follows WCAG: below 3:1 warn (`Use anyway`), below 2:1 stronger warning; a color is never refused. Export / import use the JSON format `evoxd-theme` (size limit 16 KiB, plain colors only). Saved in `config.json` under `appearance`. `EVOXD_FOCUS_COLOR` overrides the focus color; `EVOXD_RESET_COLORS=1` resets the appearance at start.

## Setup check catalog {#catalog}
`setupcheck.py` builds items `(step, id, ok, text, why, fix, hint)` in six steps:
1. **packages** – `PACKAGES` (ten fixed names) and an internet reachability test (`archive.ubuntu.com:80`).
2. **hardware** – `/dev/kvm` exists and is usable, available RAM ≥ 4096 MiB, free disk ≥ 20 GiB.
3. **groups** – `libvirt`, `kvm` (member, member but not yet active in this login, or missing).
4. **services** – `libvirtd`, `evoxd-netguard` active.
5. **evox** – network, filter, pools via the hypervisor.
6. **template** – at least one template.

Fix commands are produced only from the fixed lists `PACKAGES`, `GROUPS`, `UNITS` plus `evoxd setup`; the GUI shows the command, runs it in a terminal after confirmation and never holds root.

## Backup tools {#backup}
- `tools/backup-projekt.sh [version]` writes the project archive to `~/EVOX-Backups` (plus a `.sha256`), then runs `backup-check.sh`. `EVOX_BACKUP_DIR` overrides the folder.
- `tools/backup-check.sh [folder]` checks the newest archive: checksum and entry count against the previous archive (`EVOX_BACKUP_MIN_PERCENT`, default 80). It only reports.
- Neither needs `sudo` or the network, neither deletes anything.

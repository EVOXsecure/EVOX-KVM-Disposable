# EVOX KVM DISPOSABLE – Full Manual
version {{version}} · English · for everyday users · what is not confirmed is marked as such

## What EVOX is {#intro}
EVOX starts a throw-away virtual machine (VM) from a clean, protected copy of a system you prepared. You open a risky link or an unknown file inside it. When you press **Stop and erase VM**, everything the VM did is gone. While it runs, the VM is cut off from your computer (the *host*), your home network and your other VMs.

This manual explains what EVOX protects against, what it does not protect against, how to use it, and which mistakes you must avoid. Statements are backed by automated tests, by the network checks done on the host (called *H1* below) or by confirmations from the host. Where something is only expected, it says so.

## Threat model {#threat}
**EVOX is built to protect against:**
- Malware or a malicious web page that runs inside the VM and tries to **stay** on your system: the VM and its data are destroyed at the end.
- A compromised VM that tries to **reach** your host, router, home network, other VMs or the multicast / broadcast traffic of your network: blocked by the network lock (see chapter H1 evidence).
- A VM that is **left running unnoticed** with network access: the guard (*Wächter*) watches the lock and cuts the VM off if the lock is lost.
- Leftover data on disk: the VM writes to an **encrypted overlay**; the key lives only in memory.
- Accidental damage to your own VMs: EVOX never writes to your VAULT VMs (rule R29).

**EVOX does not protect against:**
- What **you type** into the VM: passwords, bank data, credit-card numbers. If a phishing page asks, the attacker gets it. See *What EVOX does not protect*.
- A flaw in the host kernel, in QEMU or in KVM that lets a program escape from any VM (open limit, see comparison).
- A user who is a member of group `libvirt` and acts against EVOX: that group is very powerful on Linux (open limit).
- Other programs on your X11 desktop that watch your screen or keystrokes (open limit).
- The VAULT VM: it runs **without** the network lock, because it is your own VM (open limit).

## Comparison: normal Linux, EVOX, Qubes OS {#compare}
{{svg:levels}}
The levels are steps, not measured numbers. They describe how strongly a risky task is separated from the rest of your data.

| | 1 Normal Linux | 2 EVOX | 3 Qubes OS |
|---|---|---|---|
| Where risky work happens | In your normal session, next to your files | In a throw-away VM started from a protected template | Every task in its own isolated VM, designed for this from the start |
| What stays afterwards | Everything the program wrote | Nothing (overlay and key are erased) | Depends on the VM; disposable VMs also leave nothing |
| Network towards host and home network | Fully open | Blocked by the network lock (confirmed in H1) | Separate network VMs |
| Reason for the level | No separation | Real VM plus lock plus erase, but it runs on a normal Linux desktop | The whole system is built around isolation |
| Open limits | Everything | Group libvirt, X11, VAULT without network lock, host kernel | Its own, not covered here |

EVOX is **stronger than normal Linux** and **weaker than Qubes OS**, because EVOX sits on top of an ordinary desktop. That is the honest reason for level 2. Whoever needs the strongest separation should use Qubes OS.

## Installation {#install}
{{svg:flow}}
1. Install the package: `sudo apt install ./evoxd_<version>_all.deb` (use the file name you have). It installs the programs `evoxd` and `evoxd-gui`, the guard service `evoxd-netguard`, this documentation and the menu entry.
2. Add yourself to the groups `libvirt` and `kvm`, then **log out and in again** (Setup check shows a note when the new login is still missing).
3. Create the EVOX storage once. In the project folder: `sudo tools/setup-evoxd.sh --apply` (without `--apply` it only checks and shows what it would do). It creates `/srv/evoxd` with the sub-folders `templates` and `overlays`.
4. Create the EVOX network, filter and storage pools in libvirt, once: `evoxd setup`.
5. Start `evoxd-gui` and open **Setup check** (next chapter). Fix every red item.

Needs: a computer with hardware virtualization (`/dev/kvm`), at least 4 GiB of available RAM and 20 GiB of free disk space for the Setup check to report these as fine.

## Setup check {#setupcheck}
The **Setup check** window lists what the computer still needs, in six steps. It also appears automatically on the first start. A green ✔ means fine, a red ✗ means something is missing and a short reason tells why.

| Step | What is checked |
|---|---|
| 1 Packages and internet | The needed packages (`python3-libvirt`, `python3-gi`, `gir1.2-gtk-3.0`, `libvirt-daemon-system`, `libvirt-daemon-driver-qemu`, `nftables`, `iproute2`, `virt-viewer`, `qemu-utils`, `qemu-system-x86`) and a plain internet reachability test |
| 2 Hardware | `/dev/kvm` exists and you may use it, available RAM, free disk space |
| 3 Groups | You are in `libvirt` and `kvm`; a note if you still must log in again |
| 4 Services | `libvirtd` and `evoxd-netguard` are active |
| 5 EVOX setup | EVOX network, EVOX network filter, EVOX storage pools exist |
| 6 Template | At least one template is available |

Each problem has a button **Fix it**. It shows the exact command first and runs it only after you confirm, in a terminal where **you** type your password. The commands come from a fixed list (packages, groups, services, `evoxd setup`). The window itself never gets administrator rights.

The **?** button opens this chapter. The internet test is the only network access EVOX makes itself; the documentation opens local files only.

## The three tabs {#tabs}
EVOX has three tabs, one for each stage. Use them from left to right.

### 1. VAULT
Your own VMs (names starting with `VAULT-`). You create and maintain them in virt-manager; the button **Create new VAULT VM in virt-manager…** opens it. EVOX **never writes** to a VAULT VM. Select a shut-off VAULT VM and press **Make template…** to copy its disk into a new protected template. The copy needs free space in `/srv/evoxd`; EVOX checks first and shows the plan.

### 2. TEMPLATE
The protected copies. Buttons: **Import template…** (import a shut-off `TEMPLATE-*` VM), **Verify** (checks the stored SHA-256 checksum; a damaged copy is marked and no new VM starts from it) and **Remove template…** (removes only the copy, never the original VM). Keep templates clean: see *Correct use and risks*.

### 3. DISPOSABLE
Where you work. Buttons: **Start Disposable VM: INTERNET** (internet only), **Start Disposable VM: OFFLINE** (no connection at all, for untrusted files), **Show selected VM** (opens its window), **Stop and erase VM** (ends the selected VM at once and erases its data) and **OPEN DETAILS** (the Live Monitor). The start dialog asks for template, purpose, RAM and CPUs, and checks that the host keeps enough RAM free before it starts anything. A running VM is named `DISPOSABLE-<PURPOSE>-NN`.

## HOW TO USE and Quick purpose {#howto}
**HOW TO USE** is the list of steps at the top of the main window: 1. Create new VAULT VM in virt-manager, 2. Make template of the VAULT, 3. Check / import template, 4. Start: INTERNET or OFFLINE. Each row jumps to the matching tab or opens the start dialog. **Nothing starts until you click Start in the dialog.**

**Quick purpose** is a list of buttons in the start dialog, sorted in groups (EVERYDAY, MONEY, WORK & TECH, MORE, MY LIST). Pressing one only fills the purpose field. It does not start anything. **Edit list…** lets you change the list; purposes are capital letters and digits only, up to 16 characters. The purpose becomes part of the VM name, so you can tell VMs apart.

## Live Monitor {#monitor}
**OPEN DETAILS** opens the Live Monitor for the selected VM: RAM, CPU, network traffic and overlay size. The values are read only from libvirt, about once per second while a VM runs. RAM and CPU carry a symbol and a word (for example ● OK, ▲ HIGH, ■ FULL), never only a color. RAM values marked `~` are estimates when the VM does not report them. The window can be kept on top. When you stop a VM, EVOX may suggest a RAM size for next time, based on the highest value seen. **Remember RAM for <PURPOSE>** in the start dialog stores your choice.

## Themes and Color settings {#colors}
**Color settings** (top right) lets you choose a theme, change single colors and set the text size from 80 % to 150 % in steps of 10 %. Click an item in the preview (or Tab to it and press Enter), then pick **Text color** or **Background color**. Buttons: **Compare** (hold to see the color before your last change), **Reset color**, **Reset to theme**, **Save**.

Contrast is shown as a ratio. Below 3:1 you get a warning and may click **Use anyway**; below 2:1 the warning is stronger (hard to read). EVOX never refuses a color. The **safety colors stay fixed** in every theme: Stop and erase, SHUT DOWN & ERASE, INACTIVE, error messages and the INTERNET / OFFLINE mode colors.

**Export theme…** saves your colors as a `.json` file; **Import theme…** loads one. Only plain `#RRGGBB` colors are read, a size limit applies, and safety colors cannot be changed by a file. If the colors ever make the window unusable, start once with `EVOXD_RESET_COLORS=1 evoxd-gui`; the old config is saved first.

{{svg:themes}}
Themes: Dark (default), Light, High Contrast, Nord, Solarized Dark, Dracula, Tron Legacy, Cyberpunk, Synthwave, Matrix, Amber Terminal. The swatches above are read from the program's own color table.

## Keyboard {#keys}
| Key | Action |
|---|---|
| Tab / Shift+Tab | Move to the next / previous element |
| ← → | Switch the tab while the tab row has the focus |
| ↑ ↓ | Move in lists and between the HOW TO USE rows |
| Enter (or Space) | Press the focused button |
| Esc | Close a window like ← BACK; leave fullscreen in the main window |
| F11 | Fullscreen on / off |
| F1 | Keyboard help |

A frame shows which element has the focus. The bottom line explains the focused element.

## Documentation dialog {#docs}
The **Documentation** button opens a dialog with the language (English or German, preset from your system language, not remembered) and three cards: **Quick Guide** (one page), **Full Manual** (this document) and **Developer Doc** (English only). A card is grey while its file is missing. **Open** starts your browser with the local file only; there is no network access and no automatic fallback to the other language. A warning appears if the documents are older than the program. The **?** buttons in Setup check and Color settings open the matching chapter of this manual.

## Architecture {#arch}
{{svg:life}}
- **Template:** a protected copy of a VAULT disk, stored under `/srv/evoxd/templates`, with a SHA-256 checksum that *Verify* compares.
- **Disposable VM:** created for one session from the newest template copy. Its definition is built from a fixed allow-list of devices and checked before every start. Clipboard sharing is off.
- **Encrypted overlay:** all writes go to a separate LUKS-encrypted overlay under `/srv/evoxd/overlays`. The key is random, is created for this VM and is kept only in memory (a libvirt secret). When the VM ends, the overlay and the key are gone.
- **Network lock:** an nftables table, routing rules and a libvirt network filter confine the VM's network. The lock is checked *before* the VM runs; without a working lock a networked VM does not start.
- **Guard (Wächter):** the service `evoxd-netguard` runs as root under systemd and watches the lock. If the table is lost it cuts all ports of the EVOX bridge at once (*fail-closed*: when in doubt, no network). EVOX refuses to start networked VMs without it.
- **Registry:** a small database in your state folder that records what EVOX intends to do and what it did. After a crash, `evoxd reconcile` compares it with libvirt and destroys leftovers.
- **R29:** EVOX never writes to VAULT VMs or other work VMs. The only exception is a clean-up script that you start yourself.

{{svg:flowdata}}

## H1 evidence {#h1}
The network tests were done on the host (*H1*) and confirmed by the user. The table lists what was checked from inside a disposable VM.

| Target | Result | Confirmed |
|---|---|---|
| Router / home network | Blocked | Yes, on the host |
| Host | Blocked | Yes, on the host |
| Another VM | Blocked | Yes, on the host |
| Multicast | Blocked | Yes, on the host |
| Broadcast | Blocked | Yes, on the host |
| Internet | Works | Yes, on the host |
| DNS (Quad9) | Works | Yes, on the host |
| IPv6 | The VM has none | Yes, on the host |
| `evoxd netcheck` | OK | Yes, on the host |
| Guard test | Fail-closed (network cut when the lock is lost) | Yes, on the host |

This shows the state at the time of the tests. It is not a guarantee against flaws in the host kernel or in QEMU. Run `evoxd netcheck` after updates, after a reboot or when in doubt; it is not needed before every start (the GUI shows "Network lock: active").

## Correct use and risks {#risks}
{{svg:risk}}
Each risk below says how it happens, how EVOX prevents it and what you do.

| Risk | How it happens | How EVOX prevents it | What you do |
|---|---|---|---|
| Clipboard leaks | Copying text between host and VM would carry data (or hostile content) across | No clipboard channel between host and VM; the definition is checked before every start | Do not expect copy and paste; retype what you need |
| Overlay: data left on disk | Closing the window or powering off leaves the VM and its data in place | Writes go to an encrypted overlay; the key exists only in memory and is destroyed with the VM | Always use **Stop and erase VM**, never only close the window |
| Template not clean | A login, a virus or a leftover in the template lands in every new VM | Templates are protected copies with a checksum; *Verify* finds changes | No logins and no personal data in the template; install updates before *Make template*; never use a `-BACKUP` as template; verify now and then |
| Wrong mode | Opening a document in INTERNET mode lets it call out | OFFLINE mode has no network at all | Use OFFLINE for documents and files you do not trust |
| Downloads and passwords | Everything in the VM is erased at the end, including files you wanted | Not preventable: erasing is the purpose | Save nothing you need in the VM; do not use a password manager inside it |
| Crash or power loss | A VM or overlay may remain after the host crashes | Intentions and actions are recorded in the registry | Run `evoxd reconcile`; it destroys leftovers |
| Limits (open) | Group libvirt, X11, VAULT without lock, host kernel (see threat model) | Not covered | Keep the host updated; only trusted users in group libvirt; do not run the VAULT VM for risky tasks |

## Checklists {#checklists}
**Before you start**
1. The host is updated and Setup check shows no ✗.
2. The template was verified and is clean (and not too old).
3. You chose the right mode: OFFLINE for files and documents.
4. You know what you will do in the VM and that nothing stays.

**After you finish**
1. You pressed **Stop and erase VM**; the VM is gone from the list.
2. Nothing you need was left inside.
3. `evoxd reconcile` only after a crash or power loss, not after a normal stop.
4. If you suspect a problem: see *Emergency page*.

## Scenarios {#scenarios}
**E-mail with a link.** Start INTERNET with purpose EMAIL, open the link in the VM's browser, close with *Stop and erase VM*. If the page asks for a login, do not type real passwords (see *What EVOX does not protect*).

**Online banking.** EVOX does not make banking safer by itself: a page you type your data into can still steal it. A disposable VM only helps against software that tries to remain on your computer. Decide for yourself whether this fits; use the official app or page, type the address yourself, and never type bank data on a page you reached by an e-mail link.

**Unknown attachment.** Use OFFLINE mode. Get the file into the VM with care (the clipboard is off; a file route depends on your VM setup and is not part of EVOX). Open it, look, then *Stop and erase VM*. Nothing leaves the VM.

## What EVOX does not protect {#notprotected}
- **Phishing inputs.** EVOX cannot tell a real from a fake page. Whatever you type is sent to whoever runs the page.
- **Passwords you type yourself.** A keylogger in the VM sees them. A password typed in a disposable VM should be considered known to the site and to anything running there.
- **Anything you do to the host afterwards.** Moving a file out of the VM into your normal system brings its risk with it.
- **The open limits** listed in the threat model.

## Known limits {#limits}
These limits are open in 1.0.0. They are not hidden by the design.
- **Wayland is not confirmed.** The documented design assumes an X11 session. Nobody has checked it under Wayland.
- **Group `libvirt` is practically close to root.** Anyone in that group can change libvirt and with it the VMs and the network lock. Only trusted users belong there.
- **X11 lets desktop programs act on each other.** A program on your desktop can read the screen and keystrokes and can inject input, including into the VM window.
- **The VAULT VM has no EVOX network lock.** This is intentional (rule R29: EVOX never touches your VAULT VMs). Do not use it for risky tasks.
- **Host kernel, QEMU and KVM.** A flaw there can let a program escape from any VM. Keep the host updated.
- **No data exchange between host and VM.** Clipboard and file transfer are closed on purpose. Files cannot be kept from a disposable VM.
- **Not as strong as Qubes OS.** EVOX runs on an ordinary desktop; see the comparison.
- **Not seen yet ([U]):** printing and page layout of the manuals on a real printer, and the GUI under Wayland.

## Privacy: what EVOX stores {#privacy}
**EVOX stores:**
- the **registry** (`registry.sqlite3` in `~/.local/state/evoxd`): VM names, templates, what EVOX intended and did;
- **purpose-stats.json**: per purpose the highest RAM value and the number of starts;
- **config.json** (`~/.config/evoxd`): your purpose list, remembered RAM sizes, host reserve, appearance (theme, colors, text size);
- **gui.json** and **last-start.json**: window size and position, whether Setup check was shown, the last start choices;
- the **guard status** file in `/run/evoxd` (cleared on reboot).

**EVOX never stores:** passwords, VM contents, browsing data, or the overlay key on disk. It does not send data anywhere. The only own network access is the internet test in Setup check; the documentation uses local files only. Nothing in the VM survives *Stop and erase VM*.

## Emergency page {#emergency}
If you think a disposable VM was compromised:
1. Press **Stop and erase VM** now (or `evoxd stop --all`).
2. Run `evoxd reconcile`, then `evoxd netcheck`. Both should report no problem.
3. If you typed any password into the VM, **change it** from a clean device.
4. Do not copy files out of the VM. They are erased with it.
5. If `netcheck` reports NOT OK or the list shows **CUT (guard)**: the guard cut the network. Do not start new networked VMs until Setup check is green again.
6. If you suspect the host itself: disconnect it from the network and use another device for passwords. EVOX cannot judge a compromised host.

## Template care plan {#upkeep}
- **Monthly:** start the VAULT VM, install all updates, shut it down, then *Make template…* again. `evoxd template-list` marks templates older than 14 days as OLD.
- After a new template works, remove old versions: `evoxd template-remove NAME --older`.
- Verify now and then: `evoxd template-verify NAME`.
- No logins, no personal files in the VAULT VM that you copy to a template.
- Never use a `-BACKUP` as template.

## Glossary {#glossary}
- **VM (virtual machine):** a computer simulated inside your computer.
- **Host:** your real computer.
- **VAULT:** your own VM, never touched by EVOX.
- **Template:** the protected clean copy of a VAULT VM.
- **Disposable VM:** a one-time VM started from a template.
- **Overlay:** the separate area where the VM writes; erased at the end.
- **LUKS:** a standard way to encrypt a disk.
- **nftables:** the Linux firewall that EVOX uses for the network lock.
- **Guard (Wächter):** the service that watches the network lock.
- **Fail-closed:** when something is wrong, block instead of allow.
- **libvirt / KVM / QEMU:** the Linux tools that run virtual machines.
- **Group libvirt:** a Linux group whose members may control all VMs; very powerful.
- **X11:** the classic Linux display system; programs on it can watch each other.
- **Registry:** EVOX's own record of what it started.
- **reconcile:** compare the registry with libvirt and clean up leftovers.

## Troubleshooting {#trouble}
| Symptom | Cause | Solution |
|---|---|---|
| Start refused, network lock error | Guard service not active or lock missing | Setup check step 4 and 5; `evoxd netcheck` |
| Start refused, not enough RAM | The host would drop below its reserve | Choose less RAM or close programs; the reserve can be set in config.json (`host_reserve_mib`) |
| No template in the start dialog | No template imported | Chapter *The three tabs*: Make template or Import |
| Template marked DAMAGED | Checksum does not match | Import again or remove the copy |
| List shows CUT (guard) | The guard cut the VM's network | Stop and erase the VM; run `evoxd netcheck` |
| VM window does not open | `virt-viewer` missing or failed | Setup check step 1; use *Show selected VM* again |
| Leftover VM after a crash | Host crashed while a VM ran | `evoxd reconcile` |
| Setup check says group missing though you added it | New login still missing | Log out and in again |
| Documentation card is grey | The file is missing | Reinstall the package |
| Unreadable colors | A chosen color combination | Color settings: Reset to theme, or `EVOXD_RESET_COLORS=1 evoxd-gui` |

## FAQ {#faq}
**Can the VM see my files?** Not by design: it has no access to the host or the home network.

**Why is the clipboard off?** It is a way for data to cross between host and VM, so it is closed.

**Is INTERNET mode safe?** The VM can reach the internet only. What it does there is up to the software inside it.

**Can I keep a file from the VM?** Not through EVOX. Everything is erased.

**Does EVOX work on Wayland?** The documented design assumes an X11 session; Wayland is a roadmap item. Behavior under Wayland is not confirmed.

**Is EVOX as safe as Qubes OS?** No. See the comparison.

## Command line reference {#cli}
Run `evoxd --help` or `evoxd <command> --help`. `evoxd --version` prints the version.

Normally you do not need these. The GUI does it for you.
- `evoxd reconcile`: only needed after a crash, a power loss or when something looks odd; not after a normal *Stop and erase*.
- `evoxd netcheck`: not needed before every start; the GUI shows the lock ("Network lock: active"). Useful after updates, after a reboot or when in doubt; exit code 2 on failure.

| Command | Meaning | Options |
|---|---|---|
| `evoxd setup` | Define the EVOX network, filter and pools in libvirt (once) | – |
| `evoxd template-import DOMAIN` | Import a protected copy of a shut-off `TEMPLATE-*` VM | – |
| `evoxd template-list` | List templates (age, size, in-use count, OLD / DAMAGED notes) | – |
| `evoxd template-verify NAME` | Verify the checksum (default: newest version); exit code 3 if it does not match | `--version N` |
| `evoxd template-remove NAME` | Remove an imported copy, never the original domain | `--version N` or `--older` |
| `evoxd start TEMPLATE` | Start a disposable VM from the newest copy | `--purpose`, `--memory MIB` (multiples of 256), `--cpus`, `--no-net`, `--console` |
| `evoxd list` | List disposable VMs | – |
| `evoxd stop [NAME…]` | Stop = destroy a VM | `--all` |
| `evoxd console NAME` | Open the VM window | – |
| `evoxd reconcile` | Compare with libvirt, destroy leftovers (only after a crash or if something looks odd) | – |
| `evoxd netcheck` | Check network lock and guard; exit code 2 if not OK | – |

## Update and backup {#update}
**Update:** install the new package with `sudo apt install ./evoxd_<version>_all.deb`. The guard service is restarted by the installation. Afterwards open Setup check (and run `evoxd netcheck` if in doubt). Your config and state files stay.

**Backup:** your VAULT VMs and templates live in libvirt and `/srv/evoxd`; back them up with your usual method. EVOX itself has little to save: `~/.config/evoxd/config.json` (your lists and colors). Disposable VMs and overlays are never worth saving.

## Changelog (short) {#changelog}
- **1.0.0** Release: documentation review, known limits chapter, roadmap. Functionally identical to 0.10.4.
- **0.10.4** Print margins and hints for reconcile / netcheck.
- **0.10.3** Full Manual EN + DE and Developer Doc; the **?** buttons open it.
- **0.10.2** Documentation dialog, new document style.
- **0.10.1** Quick Guide.
- **0.10.0** Setup check.
- **0.9.2** Seven new themes.
- **0.9.1** New icon.
- **0.9.0** Contrast only warns; theme export and import; emergency color reset.

## Roadmap V2.0 {#roadmap}
Plans, not promises:
- A **pkexec helper** with a fixed command list, so fixes need no terminal.
- **Hardening of group libvirt** (today an open limit).
- **Wayland** support.
- **More languages** in the program (today the interface is English only).
- **Active RAM optimization**, only as an offer you can accept or decline.

## License, liability, reporting {#license}
The license is in `/usr/share/doc/evoxd/copyright`. EVOX is provided **without warranty**. It reduces risk; it does not remove it. You use it at your own responsibility, and the open limits of this manual apply.

To report an error: note the version (`evoxd --version`), what you did, the message shown, and the output of `evoxd netcheck`. Do not include passwords or private data. The reporting address is in the package's maintainer field (`dpkg -s evoxd`).

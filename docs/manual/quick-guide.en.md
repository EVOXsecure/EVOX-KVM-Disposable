# EVOX KVM DISPOSABLE – Quick Guide
version {{version}} · one page · details in the Full Manual

## What is EVOX {#what}
EVOX starts a throw-away virtual machine (VM) from a clean copy of your system. You open a risky link or a file, then press **Stop and erase VM**: everything the VM did is gone. The VM is blocked from your host, your home network and your other VMs.

## The 4 steps {#steps}
{{svg:flow}}
1. **VAULT**: your own VM, set up once in virt-manager. EVOX never writes to it.
2. **TEMPLATE**: a protected copy of a VAULT VM (button *Make template*). Keep it clean.
3. **DISPOSABLE**: the tab where you start and stop throw-away VMs.
4. **START**: *INTERNET* (internet only) or *OFFLINE* (no connection at all, for untrusted files).

## Start and stop {#startstop}
{{svg:life}}

## Network lock {#netlock}
In INTERNET mode the VM can reach the internet only; host, router, home network and other VMs are blocked. OFFLINE has no connection at all.

{{svg:flowdata}}

## Security levels {#levels}
{{svg:levels}}

## Keyboard {#keys}
**Tab** next element · **Arrows** switch tabs / lists · **Enter** press button · **Esc** back · **F1** keyboard help · **F11** fullscreen.

## Correct use and risks {#risks}
| Risk | How EVOX prevents it | What you do |
|---|---|---|
| Clipboard leaks | No clipboard between host and VM (switched off in the VM definition, checked before every start). | Nothing to copy out of or into the VM; retype what you need. |
| Data left on disk | The VM writes to an encrypted overlay (LUKS); the key exists only in memory. | Always use **Stop and erase VM**, never just close the window or power off. |
| Dirty template | Templates are protected copies and can be verified. | No logins in the template, run updates before *Make template*, never use a -BACKUP as template. |
| Wrong mode | OFFLINE has no network. | Use OFFLINE for documents and unknown files. |
| Lost downloads and passwords | Everything vanishes with the VM. | Save nothing you need; no password manager in disposable VMs. |
| Crash or power loss | Leftovers are tracked. | Only then run `evoxd reconcile`. |
| Limits (open) | Not covered: members of group libvirt are powerful, X11 lets programs on your desktop see each other, a VAULT VM runs without the network lock (intended), Wayland is not confirmed, there is no data exchange between host and VM, a host kernel or QEMU flaw can break out of any VM. EVOX is not as strong as Qubes OS. | Keep the host updated; only trusted users in libvirt; do not run the VAULT VM for risky tasks. |

**Before start:** 1. Host updated, Setup check has no ✗. 2. Template verified and clean. 3. Right mode chosen (OFFLINE for files).
**After end:** 1. VM gone from the list (*Stop and erase*). 2. Nothing needed was left inside. 3. `evoxd reconcile` only after a crash.

## Rarely needed commands {#cli}
Normally you do not need these. The GUI does it for you.
- `evoxd reconcile`: only needed after a crash, a power loss or when something looks odd; not after a normal *Stop and erase*.
- `evoxd netcheck`: not needed before every start; the GUI shows the lock ("Network lock: active"). Useful after updates, after a reboot or when in doubt; exit code 2 on failure.

## Help {#help}
Button **Documentation** (main window) opens a choice of guides in your browser; **?** in Setup check and Color settings opens the matching chapter of the Full Manual. **Keys** or F1 shows the keyboard help; **Setup check** tells you what the computer still needs. Hover a button for a tooltip; the bottom line explains the focused element.

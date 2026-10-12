"""Logik von tools/install-launchers.sh: Starter für EVOX GUI und Claude Code im Benutzerverzeichnis.

Kein sudo, Schreibzugriff nur unter $HOME. Keine Cinnamon-Einstellungen, keine Leiste.
Fremde Programme (dpkg-query, xdg-user-dir, gio) laufen über den Parameter `run`, damit die Tests
nichts Echtes starten (tests/nospawn.py).
"""
import os
import re
import shutil
import subprocess
import sys

MARK = "X-EVOX-Launcher"
PROJECT = "CLAUDE-Projekts/EVOX-KVM-DISPOSABLE"
SAFE = re.compile(r"^[A-Za-z0-9_./+-]+$")
USAGE = "Aufruf: install-launchers.sh [--dry-run] [--remove]"


def _out(run, cmd, env):
    try:
        r = run(cmd, capture_output=True, text=True, timeout=20, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def desktop_dir(home, env, run, say):
    env = dict(env, HOME=home)
    d = (_out(run, ["xdg-user-dir", "DESKTOP"], env) or "").strip()
    if not d:
        d = os.path.join(home, "Desktop")
        say(f"HINWEIS: xdg-user-dir DESKTOP nicht verfügbar, nehme {d}")
    d = os.path.realpath(d)
    if not (d == home or d.startswith(home.rstrip("/") + "/")):
        say(f"FEHLER: Desktop-Ordner {d} liegt nicht im Benutzerverzeichnis, nichts geschrieben")
        return None
    if not os.path.isdir(d):
        say(f"FEHLER: Desktop-Ordner {d} existiert nicht")
        return None
    return d


def package_entry(run, env):
    """(Pfad der .desktop-Datei, Name des Icons) aus der Dateiliste des Pakets evoxd, sonst (None, None)."""
    lst = _out(run, ["dpkg-query", "-L", "evoxd"], env)
    if lst is None:
        return None, None
    files = lst.split("\n")
    ds = [f for f in files if f.startswith("/usr/share/applications/") and f.endswith(".desktop")]
    ds = [f for f in ds if os.path.isfile(f)]
    if not ds:
        return None, None
    icon = "evoxd" if any(f.endswith("/apps/evoxd.svg") for f in files) else "computer"
    return ds[0], icon


def evox_content(src, icon):
    with open(src, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines()
             if not ln.startswith(("Icon=", MARK + "="))]
    lines.insert(1, f"Icon={icon}")
    lines.append(f"{MARK}=evoxd-gui")
    return "\n".join(lines) + "\n"


def pick_terminal(which):
    """(Exec-Anfang, Name) oder None. gnome-terminal zuerst: Aufrufform `--` ist eindeutig."""
    if which("gnome-terminal"):
        return "gnome-terminal --", "gnome-terminal"
    if which("x-terminal-emulator"):
        return "x-terminal-emulator -e", "x-terminal-emulator"
    return None


def code_content(project, term):
    return ("[Desktop Entry]\nType=Application\nName=CODE-EVOX-KVM-DISPOSABLE\n"
            "Comment=Claude Code im Projektordner EVOX-KVM-DISPOSABLE\n"
            f'Exec={term} bash -lc "cd {project} && claude; exec bash"\n'
            "Icon=utilities-terminal\nTerminal=false\nCategories=Development;\n"
            f"{MARK}=code\n")


def write_if_changed(path, text, dry, say):
    try:
        with open(path, encoding="utf-8") as f:
            old = f.read()
    except OSError:
        old = None
    if old == text:
        say(f"unverändert: {path}")
    elif dry:
        say(f"[dry-run] würde schreiben: {path}")
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        say(f"geschrieben: {path}")


def trust(path, dry, run, which, env, say):
    if dry:
        say(f"[dry-run] würde ausführbar machen + vertrauen: {path}")
        return
    os.chmod(path, 0o755)
    if not which("gio"):
        say(f"HINWEIS: gio fehlt. Auf dem Schreibtisch Rechtsklick → „Starten erlauben“ bei {os.path.basename(path)}")
        return
    r = None
    try:
        r = run(["gio", "set", path, "metadata::trusted", "true"], capture_output=True, text=True,
                timeout=20, env=env)
    except (OSError, subprocess.SubprocessError):
        pass
    if r is None or r.returncode != 0:
        say(f"HINWEIS: gio set metadata::trusted fehlgeschlagen; Rechtsklick → „Starten erlauben“ bei {os.path.basename(path)}")


def remove(paths, dry, say):
    for p in paths:
        if not os.path.isfile(p):
            say(f"nicht vorhanden: {p}")
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            mine = f"{MARK}=" in f.read()
        if not mine:
            say(f"HINWEIS: {p} ist nicht von diesem Skript, nicht angefasst")
        elif dry:
            say(f"[dry-run] würde löschen: {p}")
        else:
            os.remove(p)
            say(f"gelöscht: {p}")


def main(argv, env=None, run=subprocess.run, which=shutil.which, say=print):
    env = dict(os.environ if env is None else env)
    if any(a not in ("--dry-run", "--remove") for a in argv):
        say(USAGE)
        return 2
    dry, rm = "--dry-run" in argv, "--remove" in argv
    home = os.path.realpath(env.get("HOME", ""))
    if not env.get("HOME") or not os.path.isdir(home):
        say("FEHLER: HOME nicht gesetzt oder kein Ordner")
        return 1
    apps = os.path.join(home, ".local/share/applications")
    menu_code = os.path.join(apps, "code-evox-kvm-disposable.desktop")
    ddir = desktop_dir(home, env, run, say)
    if ddir is None:
        return 1
    desk_code = os.path.join(ddir, "code-evox-kvm-disposable.desktop")
    desk_evox = os.path.join(ddir, "evoxd-gui.desktop")
    if rm:
        remove([menu_code, desk_code, desk_evox], dry, say)
        return 0

    rc = 0
    # a) EVOX GUI: Menüeintrag kommt aus dem Paket; nur die Kopie auf dem Schreibtisch
    src, icon = package_entry(run, env)
    if src is None:
        say("HINWEIS: Paket evoxd nicht installiert oder ohne Menüeintrag; EVOX-Starter übersprungen")
        rc = 1
    else:
        say(f"Menüeintrag des Pakets: {src} (Icon {icon})")
        write_if_changed(desk_evox, evox_content(src, icon), dry, say)
        if not dry:
            trust(desk_evox, dry, run, which, env, say)
    # b) Claude Code
    project = os.path.join(home, PROJECT)
    claude = which("claude") or (os.path.join(home, ".local/bin/claude")
                                 if os.access(os.path.join(home, ".local/bin/claude"), os.X_OK) else None)
    term = pick_terminal(which)
    if not os.path.isdir(project):
        say(f"FEHLER: Projektordner {project} fehlt, Code-Starter nicht angelegt")
        rc = 1
    elif not claude:
        say("FEHLER: Befehl claude nicht gefunden (PATH, ~/.local/bin), Code-Starter nicht angelegt")
        rc = 1
    elif not SAFE.match(project):
        say(f"FEHLER: Projektpfad {project} enthält Sonderzeichen/Leerzeichen, nicht unterstützt")
        rc = 1
    elif term is None:
        say("FEHLER: weder gnome-terminal noch x-terminal-emulator gefunden, Code-Starter nicht angelegt")
        rc = 1
    else:
        say(f"Terminal: {term[1]}; claude: {claude}")
        text = code_content(project, term[0])
        for p in (menu_code, desk_code):
            write_if_changed(p, text, dry, say)
            if not dry and p == desk_code:
                trust(p, dry, run, which, env, say)
            elif not dry:
                os.chmod(p, 0o644)
    if dry:
        say("[dry-run] nichts geschrieben")
    else:
        say("Leiste: Menü öffnen → Rechtsklick auf den Eintrag → „Zur Leiste hinzufügen“ (siehe HOST-SCHRITTE.md)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Kapazitätsprüfung vor jedem Start (ENTSCHEIDUNGEN.md §20.17).

Rechnet mit MemAvailable (nicht MemFree: Seiten-Cache ist freigebbar).
Bedarf je VM = RAM der VM + QEMU-Overhead (§20.17: ca. 0,2 GiB).
- green:  nach dem Start bleibt mindestens die Host-Reserve verfügbar
- yellow: nach dem Start bleibt weniger als die Reserve (Warnung, Start erlaubt)
- red:    nach dem Start bliebe weniger als die halbe Reserve → Start verweigert
GUI und CLI (evoxd start) benutzen dieselbe Funktion assess().
"""
import locale
from dataclasses import dataclass

VM_OVERHEAD_MIB = 256


@dataclass
class Capacity:
    level: str          # green / yellow / red
    total_mib: int
    avail_mib: int
    reserve_mib: int
    need_mib: int       # Bedarf dieser VM inkl. Overhead
    left_after_mib: int  # nach dem Start noch verfügbar
    max_for_vms_mib: int  # verfügbar minus Reserve
    fits: int           # so viele VMs dieser Größe passen jetzt (ohne Reserve anzutasten)

    @property
    def more_vms(self) -> int:
        """Weitere VMs dieser Größe nach diesem Start."""
        return max(0, self.fits - 1)


def read_meminfo(path="/proc/meminfo") -> dict:
    out = {}
    with open(path) as f:
        for line in f:
            k, v = line.split(":", 1)
            out[k] = int(v.split()[0])  # kB
    return out


def need_mib(vm_mib: int) -> int:
    return int(vm_mib) + VM_OVERHEAD_MIB


def max_vm_mib(meminfo: dict, reserve_mib: int) -> int:
    """Größte VM, die noch ohne Warnung startet (0, wenn keine)."""
    return max(0, meminfo["MemAvailable"] // 1024 - reserve_mib - VM_OVERHEAD_MIB)


def assess(meminfo: dict, vm_mib: int, reserve_mib: int = 2048) -> Capacity:
    avail = meminfo["MemAvailable"] // 1024
    total = meminfo["MemTotal"] // 1024
    need = need_mib(vm_mib)
    left = avail - need
    max_for_vms = max(0, avail - reserve_mib)
    if left < reserve_mib // 2:
        level = "red"
    elif left < reserve_mib:
        level = "yellow"
    else:
        level = "green"
    return Capacity(level, total, avail, reserve_mib, need, left, max_for_vms, max_for_vms // need)


def fmt_dec(x: float, digits: int = 1) -> str:
    """Dezimalzahl mit dem Dezimalzeichen der Systemsprache (LC_NUMERIC; GTK und CLI setzen es)."""
    return locale.format_string(f"%.{digits}f", x)


def fmt_gib(mib: int) -> str:
    return f"{fmt_dec(mib / 1024)} GiB"


def fmt_bytes_gib(b: int) -> str:
    return fmt_gib(b // 2**20)

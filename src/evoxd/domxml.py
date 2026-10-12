"""VM-Beschreibung aus Positivliste erzeugen und Live-XML prüfen (T3, T8).

Alles, was nicht ausdrücklich erlaubt ist, gilt als Verstoß.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from . import config
from .errors import AllowlistViolation

ET.register_namespace("evoxd", config.META_URI)


@dataclass
class TempSpec:
    name: str
    uuid: str
    overlay_path: str
    base_path: str
    secret_uuid: str
    template: str = ""
    purpose: str = ""
    memory_mib: int = 2048
    vcpus: int = 2
    net: bool = True
    mac: Optional[str] = None
    firmware: str = "bios"
    transfer_channel: bool = False  # Version 2 – in Version 1 immer aus


BALLOON_STATS_S = 1   # 0.7.2: Statistik-Periode des virtio-balloon (= 1-s-Live-Takt der GUI; 0.7.1: 5)


def hard_limit_kib(memory_mib: int) -> int:
    return int(memory_mib * 1.25 + 256) * 1024


_UNIT_KIB = {"b": 1 / 1024, "bytes": 1 / 1024, "k": 1, "kib": 1, "kb": 1000 / 1024,
             "m": 1024, "mib": 1024, "mb": 1000**2 / 1024, "g": 1024**2, "gib": 1024**2, "gb": 1000**3 / 1024}


def resources(xml: Optional[str]) -> dict:
    """RAM (MiB) und CPUs aus der Domain-Beschreibung lesen; None, wenn nicht lesbar."""
    out = {"memory_mib": None, "vcpus": None}
    if not xml:
        return out
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    mem = root.find("currentMemory")
    if mem is None:
        mem = root.find("memory")
    try:
        if mem is not None:
            out["memory_mib"] = int(int(mem.text) * _UNIT_KIB[mem.get("unit", "KiB").lower()] // 1024)
        if root.find("vcpu") is not None:
            out["vcpus"] = int(root.findtext("vcpu"))
    except (TypeError, ValueError, KeyError):
        pass
    return out


def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, {k.rstrip("_"): str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def build(spec: TempSpec) -> str:
    if spec.transfer_channel:
        raise AllowlistViolation("Transfer channel is disabled in version 1.")
    if not re.fullmatch(config.TEMP_NAME_RE, spec.name):
        raise AllowlistViolation("Name does not follow the DISPOSABLE-<PURPOSE>-NN scheme.")
    if not spec.template:
        raise AllowlistViolation("Template missing in metadata.")
    if not config.ram_on_grid(spec.memory_mib):                     # 0.7.3: nur 256-MiB-Raster im erlaubten Bereich
        raise AllowlistViolation("RAM size not allowed (multiples of 256 MiB, 1024 to 32768 MiB).")
    if spec.net and not spec.mac:
        raise AllowlistViolation("Network mode without MAC address.")
    d = ET.Element("domain", type="kvm")
    _sub(d, "name", spec.name)
    _sub(d, "uuid", spec.uuid)
    md = _sub(d, "metadata")
    ET.SubElement(md, f"{{{config.META_URI}}}temp",
                  {"net": "net" if spec.net else "none", "version": "1",
                   "template": spec.template, "purpose": spec.purpose})
    _sub(d, "memory", spec.memory_mib * 1024, unit="KiB")
    _sub(d, "currentMemory", spec.memory_mib * 1024, unit="KiB")
    mt = _sub(d, "memtune")
    _sub(mt, "hard_limit", hard_limit_kib(spec.memory_mib), unit="KiB")
    _sub(d, "vcpu", spec.vcpus, placement="static")
    os_attrs = {"firmware": "efi"} if spec.firmware == "efi" else {}
    os_el = _sub(d, "os", **os_attrs)
    _sub(os_el, "type", "hvm", arch="x86_64", machine="q35")
    _sub(os_el, "boot", dev="hd")
    f = _sub(d, "features")
    _sub(f, "acpi")
    _sub(f, "apic")
    _sub(d, "cpu", mode="host-model")
    _sub(d, "clock", offset="utc")
    _sub(d, "on_poweroff", "destroy")
    _sub(d, "on_reboot", "restart")
    _sub(d, "on_crash", "destroy")
    pm = _sub(d, "pm")
    _sub(pm, "suspend-to-mem", enabled="no")
    _sub(pm, "suspend-to-disk", enabled="no")

    dev = _sub(d, "devices")
    disk = _sub(dev, "disk", type="file", device="disk")
    _sub(disk, "driver", name="qemu", type="qcow2", cache="none", discard="unmap")
    src = _sub(disk, "source", file=spec.overlay_path)
    enc = _sub(src, "encryption", format="luks")
    _sub(enc, "secret", type="passphrase", uuid=spec.secret_uuid)
    bs = _sub(disk, "backingStore", type="file")
    _sub(bs, "format", type="qcow2")
    bsrc = _sub(bs, "source", file=spec.base_path)
    _sub(bsrc, "seclabel", model="dac", relabel="no")
    _sub(bs, "backingStore")
    _sub(disk, "target", dev="vda", bus="virtio")

    _sub(dev, "controller", type="usb", model="qemu-xhci")
    if spec.net:
        iface = _sub(dev, "interface", type="network")
        _sub(iface, "mac", address=spec.mac)
        _sub(iface, "source", network=config.NETWORK)
        _sub(iface, "model", type="virtio")
        fr = _sub(iface, "filterref", filter=config.NWFILTER)
        _sub(fr, "parameter", name="CTRL_IP_LEARNING", value="dhcp")
    _sub(dev, "input", type="tablet", bus="usb")
    g = _sub(dev, "graphics", type="spice")
    _sub(g, "listen", type="none")
    _sub(g, "image", compression="off")
    _sub(g, "clipboard", copypaste="no")
    _sub(g, "filetransfer", enable="no")
    _sub(g, "gl", enable="no")
    _sub(dev, "audio", id="1", type="none")
    v = _sub(dev, "video")
    _sub(v, "model", type="virtio", heads="1", primary="yes")
    # 0.7.1: Gast-Speicherstatistik alle BALLOON_STATS_S s (nur lesend vom Host über libvirt; kein neuer Kanal)
    _sub(_sub(dev, "memballoon", model="virtio"), "stats", period=BALLOON_STATS_S)
    rng = _sub(dev, "rng", model="virtio")
    _sub(rng, "backend", "/dev/urandom", model="random")
    return ET.tostring(d, encoding="unicode")


# ---------------------------------------------------------------- Live-Prüfung

_TOP = {"name", "uuid", "metadata", "memory", "currentMemory", "maxMemory", "memtune", "vcpu", "resource",
        "os", "features", "cpu", "clock", "on_poweroff", "on_reboot", "on_crash", "pm", "devices", "seclabel",
        "genid", "title", "description"}
_DEVICES = {"emulator", "disk", "controller", "interface", "input", "graphics", "audio", "video",
            "memballoon", "rng", "watchdog"}
_CONTROLLERS = {"pci", "usb", "sata", "ide"}
_INPUTS = {("tablet", "usb"), ("mouse", "ps2"), ("keyboard", "ps2")}
_FEATURES = {"acpi", "apic", "vmport", "pae"}


def _fail(msg):
    raise AllowlistViolation(msg)


def validate_live(xml: str, expect_net: bool, require_apparmor: bool = True) -> None:
    """Prüft das Live-XML einer laufenden Temp-VM. Wirft AllowlistViolation."""
    root = ET.fromstring(xml)
    if root.tag != "domain" or root.get("type") != "kvm":
        _fail("Not a KVM domain XML.")
    for child in root:
        if child.tag not in _TOP:
            _fail(f"Element <{child.tag}> not allowed.")
    if not re.fullmatch(config.TEMP_NAME_RE, root.findtext("name", "")):
        _fail("Name does not follow the DISPOSABLE-<PURPOSE>-NN scheme.")
    md = root.find(f"metadata/{{{config.META_URI}}}temp")
    if md is None or not md.get("template"):
        _fail("EVOX metadata (template) missing.")
    if root.find("memtune/hard_limit") is None:
        _fail("Memory limit (hard_limit) missing.")
    for feat in root.find("features") if root.find("features") is not None else []:
        if feat.tag not in _FEATURES:
            _fail(f"Feature <{feat.tag}> not allowed.")

    labels = root.findall("seclabel")
    if any(s.get("type") == "none" for s in labels):
        _fail("Security label disabled (seclabel type='none').")
    if require_apparmor and not any(s.get("model") == "apparmor" and s.get("type") == "dynamic" for s in labels):
        _fail("No dynamic AppArmor profile.")

    devs = root.find("devices")
    if devs is None:
        _fail("No device list.")
    for el in devs:
        if el.tag not in _DEVICES:
            _fail(f"Device <{el.tag}> not allowed.")

    disks = devs.findall("disk")
    if len(disks) != 1 or disks[0].get("device") != "disk" or disks[0].get("type") != "file":
        _fail("Exactly one file-backed disk expected.")
    disk = disks[0]
    src = disk.find("source")
    if src is None or not src.get("file", "").startswith(config.OVERLAY_PATH + "/" + config.TEMP_PREFIX):
        _fail("Disk is not an overlay in the EVOX overlay pool.")
    enc = src.find("encryption")
    if enc is None:
        enc = disk.find("encryption")
    if enc is None or enc.get("format") != "luks":
        _fail("Overlay is not LUKS-encrypted.")
    if disk.find("readonly") is not None or disk.find("shareable") is not None:
        _fail("Unexpected disk options.")
    bs = disk.find("backingStore")
    bsrc = bs.find("source") if bs is not None else None
    if bsrc is None or not bsrc.get("file", "").startswith(config.TEMPLATE_PATH + "/" + config.TEMPLATE_PREFIX):
        _fail("Template copy is not in the EVOX template pool.")
    if bs.find("backingStore/source") is not None:
        _fail("Template copy is not flat (further backing file).")

    for c in devs.findall("controller"):
        if c.get("type") not in _CONTROLLERS:
            _fail(f"Controller '{c.get('type')}' not allowed.")
    for i in devs.findall("input"):
        if (i.get("type"), i.get("bus")) not in _INPUTS:
            _fail(f"Input device {i.get('type')}/{i.get('bus')} not allowed.")
    # q35: libvirt (ab 9.x) trägt den fest eingebauten iTCO-Watchdog ins Live-XML ein
    for w in devs.findall("watchdog"):
        if w.get("model") != "itco":
            _fail(f"Watchdog '{w.get('model')}' not allowed.")
    for a in devs.findall("audio"):
        if a.get("type") != "none":
            _fail("Audio channel not allowed.")

    gfx = devs.findall("graphics")
    if len(gfx) != 1 or gfx[0].get("type") != "spice":
        _fail("Exactly one SPICE display expected.")
    g = gfx[0]
    listens = g.findall("listen")
    if not listens or any(l.get("type") != "none" for l in listens) or g.get("port") not in (None, "-1"):
        _fail("SPICE must not be reachable over the network (listen type='none').")
    cb, ft, gl = g.find("clipboard"), g.find("filetransfer"), g.find("gl")
    if cb is None or cb.get("copypaste") != "no" or ft is None or ft.get("enable") != "no":
        _fail("Clipboard/file transfer not disabled.")
    if gl is not None and gl.get("enable") == "yes":
        _fail("3D acceleration not allowed.")

    ifaces = devs.findall("interface")
    if not expect_net:
        if ifaces:
            _fail("Mode 'No network', but a network interface is present.")
    else:
        if len(ifaces) != 1 or ifaces[0].get("type") != "network":
            _fail("Exactly one interface in the EVOX network expected.")
        it = ifaces[0]
        if it.find("source") is None or it.find("source").get("network") != config.NETWORK:
            _fail("Interface is not in the EVOX network.")
        fr = it.find("filterref")
        if fr is None or fr.get("filter") != config.NWFILTER:
            _fail("nwfilter missing on the interface.")
        m = it.find("model")
        if m is None or m.get("type") != "virtio":
            _fail("Unexpected network model.")

"""XML für Pool, Basis-Volume, Overlay und flüchtiges Secret (T4, T5)."""
import secrets
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr, escape

from . import config


def pool_xml(name: str, path: str) -> str:
    return (f"<pool type='dir'><name>{escape(name)}</name><target><path>{escape(path)}</path>"
            "<permissions><mode>0711</mode><owner>0</owner><group>0</group></permissions>"
            "</target></pool>")


def pools() -> list:
    """Beide EVOX-Pools unter /srv/evoxd: (Name, XML)."""
    return [(config.TEMPLATE_POOL, pool_xml(config.TEMPLATE_POOL, config.TEMPLATE_PATH)),
            (config.OVERLAY_POOL, pool_xml(config.OVERLAY_POOL, config.OVERLAY_PATH))]


def base_vol_xml(vol_name: str) -> str:
    """Flache, schreibgeschützte Kopie (root 0444); Ziel von createXMLFrom."""
    return (f"<volume><name>{escape(vol_name)}</name><capacity unit='bytes'>0</capacity>"
            "<target><format type='qcow2'/>"
            "<permissions><mode>0444</mode><owner>0</owner><group>0</group></permissions>"
            "</target></volume>")


def overlay_vol_xml(vol_name: str, capacity_bytes: int, base_path: str, secret_uuid: str) -> str:
    return (f"<volume><name>{escape(vol_name)}</name><capacity unit='bytes'>{int(capacity_bytes)}</capacity>"
            "<target><format type='qcow2'/>"
            "<permissions><mode>0600</mode><owner>0</owner><group>0</group></permissions>"
            f"<encryption format='luks'><secret type='passphrase' uuid={quoteattr(secret_uuid)}/></encryption>"
            "</target>"
            f"<backingStore><path>{escape(base_path)}</path><format type='qcow2'/></backingStore>"
            "</volume>")


def new_passphrase() -> bytes:
    """Flüchtiger LUKS-Schlüssel: 32 Zufallsbytes (256 Bit) als 64 Hex-Zeichen.

    QEMU/qemu-img verlangen für LUKS-Passphrasen gültiges UTF-8 (Rohbytes
    scheitern). Derselbe Wert gilt für Overlay-Erzeugung und Domain-Start,
    da beide das Secret über die UUID nachschlagen. Nie speichern oder loggen.
    """
    return secrets.token_hex(32).encode("ascii")


def secret_xml(secret_uuid: str, usage_name: str) -> str:
    """Flüchtig (nur im Speicher von libvirtd) und privat (Wert nicht auslesbar)."""
    return (f"<secret ephemeral='yes' private='yes'><uuid>{escape(secret_uuid)}</uuid>"
            f"<usage type='volume'><volume>{escape(usage_name)}</volume></usage></secret>")


def check_base_vol(vol_xml: str) -> None:
    """Template-Kopie muss root-eigen und 0444 sein."""
    root = ET.fromstring(vol_xml)
    perms = root.find("target/permissions")
    mode = perms.findtext("mode") if perms is not None else None
    owner = perms.findtext("owner") if perms is not None else None
    if mode is None or int(mode, 8) != 0o444 or owner != "0":
        raise PermissionError(f"Template copy is not protected (mode={mode}, owner={owner}).")
    if root.find("backingStore/path") is not None:
        raise PermissionError("Template copy is not flat (has a backing file).")

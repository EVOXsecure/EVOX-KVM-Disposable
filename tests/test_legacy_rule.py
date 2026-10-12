"""Regel für Altlasten im Pool default (tools/legacy_rule.py) gegen erfundene Beispieldaten."""
import importlib.util
import os
import unittest

from tests.nospawn import NoSpawnMixin

_P = os.path.join(os.path.dirname(__file__), "..", "tools", "legacy_rule.py")
_spec = importlib.util.spec_from_file_location("legacy_rule", _P)
rule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rule)

D = "/var/lib/libvirt/images"
MiB, GiB = 1024 ** 2, 1024 ** 3
PROT = {f"{D}/TEMPLATE-DEBIAN13.qcow2", f"{D}/VAULT-DEBIAN13.qcow2",
        f"{D}/TEMPLATE-DEBIAN13-BACKUP.qcow2", f"{D}/VAULT-DEBIAN13-BACKUP.qcow2",
        f"{D}/DISPOSABLE-BANK-03.qcow2"}   # von einer definierten VM benutzt


def sample():
    """Ähnlich einer vol-list des Pools default: (name, groesse, belegt)."""
    vols = [("TEMPLATE-DEBIAN13.qcow2", 64 * GiB, 9 * GiB), ("VAULT-DEBIAN13.qcow2", 64 * GiB, 14 * GiB),
            ("TEMPLATE-DEBIAN13-BACKUP.qcow2", 64 * GiB, 9 * GiB),
            ("VAULT-DEBIAN13-BACKUP.qcow2", 64 * GiB, 14 * GiB),
            ("TEMPLATE-DEBIAN13.running", 0, 0), ("VAULT-DEBIAN13.running", 0, 0),
            ("TEMPLATE-OLD.qcow2", 20 * GiB, 196 * 1024), ("debian-13.4.0-amd64-netinst.iso", 754 * MiB, 754 * MiB)]
    for i in range(1, 8):    # 7 leere Overlays
        vols.append((f"DISPOSABLE-EMAIL-{i:02d}-2026100{i}.qcow2", 64 * GiB, 196 * 1024))
    for i in range(1, 23):   # 22 Lauf-Marker
        vols.append((f"DISPOSABLE-WEB-{i:02d}.running", 0, 0))
    return vols


class LegacyRule(NoSpawnMixin, unittest.TestCase):
    def c(self, name, size, alloc, prot=PROT, d=D):
        return rule.classify(name, f"{d}/{name}", size, alloc, D, prot)[0]

    def test_sample_counts(self):
        hits = [n for n, s, a in sample() if self.c(n, s, a)]
        self.assertEqual(sum(n.endswith(".qcow2") for n in hits), 7)
        self.assertEqual(sum(n.endswith(".running") for n in hits), 22)
        self.assertTrue(all(n.startswith("DISPOSABLE-") for n in hits))

    def test_template_vault_never(self):
        for n in ("TEMPLATE-DEBIAN13.qcow2", "VAULT-DEBIAN13.qcow2", "TEMPLATE-DEBIAN13-BACKUP.qcow2",
                  "VAULT-DEBIAN13-BACKUP.qcow2", "TEMPLATE-X.running", "VAULT-X.running"):
            self.assertFalse(self.c(n, 0, 0), n)            # selbst leer und ungeschützt: nie
            self.assertFalse(self.c(n, 0, 0, prot=set()), n)

    def test_future_disposable_with_data(self):
        self.assertFalse(self.c("DISPOSABLE-EMAIL-01.qcow2", 64 * GiB, 2 * GiB, prot=set()))
        self.assertFalse(self.c("DISPOSABLE-EMAIL-01.qcow2", 64 * GiB, MiB, prot=set()))   # genau 1 MiB
        self.assertTrue(self.c("DISPOSABLE-EMAIL-01.qcow2", 64 * GiB, MiB - 1, prot=set()))

    def test_used_by_vm(self):
        self.assertFalse(self.c("DISPOSABLE-BANK-03.qcow2", 64 * GiB, 0))

    def test_running_not_empty(self):
        self.assertFalse(self.c("DISPOSABLE-WEB-01.running", 5, 4096))
        self.assertFalse(self.c("DISPOSABLE-WEB-01.running", 0, 4096))

    def test_other_names_and_places(self):
        for n in ("disposable-web-01.running", "DISPOSABLE-WEB-01.qcow2.bak", "DISPOSABLE-WEB-01.raw",
                  "DISPOSABLE-WEB-01.running.old", "XDISPOSABLE-WEB-01.running", "DISPOSABLE-WEB-01.img"):
            self.assertFalse(self.c(n, 0, 0), n)
        self.assertFalse(self.c("DISPOSABLE-WEB-01.running", 0, 0, d=D + "/sub"))
        self.assertFalse(rule.classify("DISPOSABLE-A.running", f"{D}/DISPOSABLE-B.running", 0, 0, D, set())[0])
        self.assertFalse(self.c("DISPOSABLE-WEB-01.qcow2", -1, -1))   # Größe unbekannt

    def test_vol_xml(self):
        x = ("<volume type='file'><name>DISPOSABLE-WEB-01.running</name><capacity unit='bytes'>0</capacity>"
             "<allocation unit='bytes'>0</allocation><target><path>/var/lib/libvirt/images/"
             "DISPOSABLE-WEB-01.running</path></target></volume>")
        self.assertEqual(rule.vol_from_xml(x), ("DISPOSABLE-WEB-01.running",
                                                f"{D}/DISPOSABLE-WEB-01.running", 0, 0))


if __name__ == "__main__":
    unittest.main()

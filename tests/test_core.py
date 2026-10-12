import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests.nospawn import NoSpawnMixin
from evoxd import capacity, config, domxml, storage
from evoxd.config import Settings
from evoxd.errors import AllowlistViolation, Cancelled, CapacityError, EvoxError, LockBusy, NotOwned, SpaceError
from evoxd.lifecycle import Evox, space_needed, suggest_template_name
from evoxd.lock import exclusive
from evoxd.ownership import Owner, classify
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor

MEM_OK = {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20}
MEM_LOW = {"MemTotal": 16 * 2**20, "MemAvailable": 3 * 2**20}


def spec(net=True):
    return domxml.TempSpec(name="DISPOSABLE-EMAIL-01", uuid="00000000-0000-0000-0000-000000000001",
                           overlay_path=config.OVERLAY_PATH + "/DISPOSABLE-EMAIL-01-abcd1234.qcow2",
                           base_path=config.TEMPLATE_PATH + "/TEMPLATE-MAIL-v1.qcow2",
                           secret_uuid="00000000-0000-0000-0000-000000000002",
                           template="TEMPLATE-MAIL", purpose="EMAIL",
                           net=net, mac="52:54:00:00:00:01" if net else None)


def live(net=True):
    root = ET.fromstring(domxml.build(spec(net)))
    ET.SubElement(root, "seclabel", type="dynamic", model="apparmor")
    return root


def s(root):
    return ET.tostring(root, encoding="unicode")


class AllowlistTest(NoSpawnMixin, unittest.TestCase):
    def test_built_xml_passes(self):
        domxml.validate_live(s(live(True)), expect_net=True)
        domxml.validate_live(s(live(False)), expect_net=False)

    def test_no_net_has_no_interface(self):
        self.assertIsNone(ET.fromstring(domxml.build(spec(False))).find("devices/interface"))

    def test_transfer_channel_disabled(self):
        sp = spec()
        sp.transfer_channel = True
        with self.assertRaises(AllowlistViolation):
            domxml.build(sp)

    def _reject(self, mutate, net=True):
        r = live(net)
        mutate(r)
        with self.assertRaises(AllowlistViolation):
            domxml.validate_live(s(r), expect_net=net)

    def test_rejections(self):
        dev = lambda r: r.find("devices")
        cases = {
            "hostdev": lambda r: ET.SubElement(dev(r), "hostdev"),
            "filesystem": lambda r: ET.SubElement(dev(r), "filesystem"),
            "channel": lambda r: ET.SubElement(dev(r), "channel", type="spicevmc"),
            "redirdev": lambda r: ET.SubElement(dev(r), "redirdev"),
            "qemu-cmdline": lambda r: ET.SubElement(r, "{http://libvirt.org/schemas/domain/qemu/1.0}commandline"),
            "seclabel-none": lambda r: ET.SubElement(r, "seclabel", type="none"),
            "second-disk": lambda r: dev(r).append(ET.fromstring(ET.tostring(r.find("devices/disk")))),
            "spice-listen-addr": lambda r: r.find("devices/graphics/listen").set("type", "address"),
            "clipboard": lambda r: r.find("devices/graphics/clipboard").set("copypaste", "yes"),
            "audio-spice": lambda r: r.find("devices/audio").set("type", "spice"),
            "wrong-network": lambda r: r.find("devices/interface/source").set("network", "default"),
            "no-filterref": lambda r: r.find("devices/interface").remove(r.find("devices/interface/filterref")),
            "disk-outside-pool": lambda r: r.find("devices/disk/source").set("file", "/tmp/x.qcow2"),
            "no-encryption": lambda r: r.find("devices/disk/source").remove(r.find("devices/disk/source/encryption")),
            "no-hard-limit": lambda r: r.remove(r.find("memtune")),
            "no-metadata": lambda r: r.remove(r.find("metadata")),
            "no-template-in-metadata": lambda r: r.find("metadata")[0].attrib.pop("template"),
            "name-scheme": lambda r: setattr(r.find("name"), "text", "evoxd-tmp-1"),
            "backing-outside-templates": lambda r: r.find("devices/disk/backingStore/source").set(
                "file", config.OVERLAY_PATH + "/TEMPLATE-MAIL-v1.qcow2"),
            "scsi-controller": lambda r: ET.SubElement(dev(r), "controller", type="scsi"),
            "gl": lambda r: r.find("devices/graphics/gl").set("enable", "yes"),
            "watchdog-i6300esb": lambda r: ET.SubElement(dev(r), "watchdog", model="i6300esb"),
        }
        for label, mut in cases.items():
            with self.subTest(label):
                self._reject(mut)

    def test_itco_watchdog_allowed(self):
        r = live()
        ET.SubElement(r.find("devices"), "watchdog", model="itco", action="reset")
        domxml.validate_live(s(r), expect_net=True)

    def test_interface_in_no_net_mode(self):
        r = live(False)
        r.find("devices").append(live(True).find("devices/interface"))
        with self.assertRaises(AllowlistViolation):
            domxml.validate_live(s(r), expect_net=False)

    def test_apparmor_required(self):
        r = ET.fromstring(domxml.build(spec()))
        with self.assertRaises(AllowlistViolation):
            domxml.validate_live(s(r), expect_net=True)


class OwnershipStorageTest(NoSpawnMixin, unittest.TestCase):
    def test_classify(self):
        xml = domxml.build(spec())
        self.assertIs(classify("DISPOSABLE-EMAIL-01", xml), Owner.EVOX)
        # Markierung entscheidet, nicht der Name
        self.assertIs(classify("DISPOSABLE-STEP211", "<domain><uuid>x</uuid></domain>"), Owner.FOREIGN)
        self.assertIs(classify("renamed-by-user", xml), Owner.EVOX)
        no_tpl = xml.replace('template="TEMPLATE-MAIL"', "")
        self.assertIs(classify("DISPOSABLE-EMAIL-01", no_tpl), Owner.FOREIGN)
        # VAULT-*/TEMPLATE-* nie EVOX-eigen, auch mit Markierung (R29)
        self.assertIs(classify("VAULT-DEBIAN13", xml), Owner.FOREIGN)
        self.assertIs(classify("TEMPLATE-DEBIAN13", xml), Owner.FOREIGN)
        self.assertIs(classify("VAULT-X", "<domain><uuid>u1</uuid></domain>", {"u1"}), Owner.TRANSFER)

    def test_base_perms(self):
        storage.check_base_vol(storage.base_vol_xml("TEMPLATE-X-v1.qcow2"))
        bad = storage.base_vol_xml("b").replace("0444", "0644")
        with self.assertRaises(PermissionError):
            storage.check_base_vol(bad)

    def test_secret_ephemeral_private(self):
        r = ET.fromstring(storage.secret_xml("u", "/p"))
        self.assertEqual((r.get("ephemeral"), r.get("private")), ("yes", "yes"))

    def test_passphrase_utf8_256bit(self):
        a, b = storage.new_passphrase(), storage.new_passphrase()
        self.assertEqual(len(a), 64)
        self.assertEqual(len(bytes.fromhex(a.decode("utf-8"))), 32)
        self.assertNotEqual(a, b)

    def test_overlay_encrypted_with_backing(self):
        r = ET.fromstring(storage.overlay_vol_xml("DISPOSABLE-EMAIL-01-a.qcow2", 1, "/b", "u"))
        self.assertEqual(r.find("target/encryption").get("format"), "luks")
        self.assertEqual(r.findtext("backingStore/path"), "/b")


GIB = 2**20  # kB je GiB in /proc/meminfo
# Echte Zahlen des Benutzers: 16 GiB gesamt, ca. 4 GiB belegt → MemAvailable ca. 12 GiB
MEM_USER = {"MemTotal": 16 * GIB, "MemFree": 3 * GIB, "MemAvailable": 12 * GIB}


class CapacityTest(NoSpawnMixin, unittest.TestCase):
    def test_levels(self):
        self.assertEqual(capacity.assess(MEM_OK, 2048).level, "green")
        self.assertEqual(capacity.assess(MEM_LOW, 2048).level, "red")
        c = capacity.assess({"MemTotal": 16 * GIB, "MemAvailable": 4000 * 1024}, 2048)
        self.assertEqual(c.level, "yellow")       # 4000-2304 = 1696 < 2048, ≥ 1024

    def test_user_numbers_2_5_gib_no_warning(self):
        c = capacity.assess(MEM_USER, 2560)
        self.assertEqual(c.level, "green")
        self.assertEqual(c.avail_mib, 12288)      # MemAvailable, nicht MemFree
        self.assertEqual(c.left_after_mib, 12288 - 2560 - capacity.VM_OVERHEAD_MIB)
        self.assertEqual(c.max_for_vms_mib, 10240)

    def test_user_numbers_three_vms_of_3_gib_fit(self):
        self.assertGreaterEqual(capacity.assess(MEM_USER, 3072).fits, 3)
        mem = dict(MEM_USER)
        for _ in range(3):                         # nacheinander starten: MemAvailable sinkt
            c = capacity.assess(mem, 3072)
            self.assertEqual(c.level, "green")
            mem["MemAvailable"] -= c.need_mib * 1024
        self.assertEqual(capacity.assess(mem, 3072).level, "red")   # vierte passt nicht mehr

    def test_uses_memavailable_not_memfree(self):
        self.assertEqual(capacity.assess(MEM_USER, 2560).level,
                         capacity.assess(dict(MEM_USER, MemFree=1), 2560).level)

    def test_reserve_boundaries(self):
        avail = 2048 + 2048 + capacity.VM_OVERHEAD_MIB     # genau Reserve übrig
        m = {"MemTotal": 16 * GIB, "MemAvailable": avail * 1024}
        self.assertEqual(capacity.assess(m, 2048).level, "green")
        self.assertEqual(capacity.assess(m, 2049).level, "yellow")
        self.assertEqual(capacity.assess(m, 2048 + 1024).level, "yellow")   # genau halbe Reserve
        self.assertEqual(capacity.assess(m, 2048 + 1025).level, "red")
        self.assertEqual(capacity.max_vm_mib(m, 2048), 2048)

    def test_reserve_configurable(self):
        self.assertEqual(capacity.assess(MEM_USER, 8192, reserve_mib=2048).level, "green")
        self.assertEqual(capacity.assess(MEM_USER, 8192, reserve_mib=4096).level, "yellow")
        self.assertEqual(capacity.assess(MEM_USER, 8192, reserve_mib=8192).level, "red")


class SettingsFileTest(NoSpawnMixin, unittest.TestCase):
    def test_reserve_from_config_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            self.assertEqual(Settings.load(p).host_reserve_mib, 2048)          # keine Datei
            p.write_text('{"host_reserve_mib": 3072}')
            self.assertEqual(Settings.load(p).host_reserve_mib, 3072)
            for bad in ('{"host_reserve_mib": 100}', '{"host_reserve_mib": "4096"}', "[1]", "kaputt"):
                p.write_text(bad)
                self.assertEqual(Settings.load(p).host_reserve_mib, 2048, bad)

    def test_verify_after_shutdown_setting(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "config.json"
            s = Settings.load(p)
            self.assertFalse(s.verify_after_shutdown)                         # Standard aus
            p.parent.mkdir()
            p.write_text('{"host_reserve_mib": 3072}')
            s.save_option("verify_after_shutdown", True)
            s2 = Settings.load(p)
            self.assertTrue(s2.verify_after_shutdown)
            self.assertEqual(s2.host_reserve_mib, 3072)                       # anderer Wert bleibt
            self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)
            p.write_text('{"verify_after_shutdown": "yes"}')
            self.assertFalse(Settings.load(p).verify_after_shutdown)

    def test_gui_state(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(state_dir=Path(d))
            self.assertEqual(s.load_gui_state(), {"width": 1100, "height": 820, "maximized": False,
                                                  "details_expanded": None, "monitor": None,
                                                  "monitor_pin": False, "setup_seen": False})     # 0.7.2: None = noch keine Wahl
            s.save_gui_state(1200, 900, True)
            self.assertEqual(s.load_gui_state(), {"width": 1200, "height": 900, "maximized": True,
                                                  "details_expanded": None, "monitor": None, "monitor_pin": False,
                                                  "setup_seen": False})
            s.save_gui_state(1200, 900, True, True)
            self.assertTrue(s.load_gui_state()["details_expanded"])
            s.save_gui_state(1200, 900, False, False)                 # 0.7.1: Detailbereich eingeklappt gemerkt
            self.assertFalse(s.load_gui_state()["details_expanded"])
            s.gui_state_path.write_text('{"width": 5, "height": "x"}')
            self.assertEqual(s.load_gui_state()["width"], 1100)


class ResourcesTest(NoSpawnMixin, unittest.TestCase):
    def test_read_from_domain_xml(self):
        sp = spec()
        sp.memory_mib, sp.vcpus = 3072, 3
        self.assertEqual(domxml.resources(domxml.build(sp)), {"memory_mib": 3072, "vcpus": 3})
        x = "<domain><memory unit='GiB'>4</memory><vcpu>2</vcpu></domain>"
        self.assertEqual(domxml.resources(x), {"memory_mib": 4096, "vcpus": 2})
        self.assertEqual(domxml.resources(None), {"memory_mib": None, "vcpus": None})
        self.assertEqual(domxml.resources("<domain/>"), {"memory_mib": None, "vcpus": None})


class LockTest(NoSpawnMixin, unittest.TestCase):
    def test_second_lock_times_out(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lock"
            with exclusive(p, 1):
                with self.assertRaises(LockBusy):
                    with exclusive(p, 0.3):
                        pass
            with exclusive(p, 0.3):
                pass


class LifecycleTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.settings = Settings(state_dir=d / "state", runtime_dir=d / "run")
        self.hv = FakeHypervisor()
        self.reg = Registry(self.settings.registry_path)
        self.net_ok = (True, "")
        self.mem = MEM_OK
        self.ev = Evox(self.settings, self.hv, self.reg, net_check=lambda: self.net_ok,
                       meminfo=lambda: self.mem)
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.hv.add_foreign("VAULT-WORK", state="running")
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def test_registry_mode_0600(self):
        self.assertEqual(os.stat(self.settings.registry_path).st_mode & 0o777, 0o600)

    def test_import_only_template_domains(self):
        self.hv.add_foreign("VAULT-OFF")
        for dom in ("VAULT-WORK", "VAULT-OFF", "MAIL-BASIS"):
            with self.assertRaises(EvoxError):
                self.ev.import_template(dom)
        r = self.ev.start("TEMPLATE-MAIL")
        with self.assertRaises(EvoxError):
            self.ev.import_template(r.name)
        self.hv.add_foreign("TEMPLATE-ON", state="running")
        with self.assertRaises(EvoxError):
            self.ev.import_template("TEMPLATE-ON")

    def test_template_candidates(self):
        self.hv.add_foreign("TEMPLATE-ON", state="running")
        self.hv.add_foreign("TEMPLATE-X-BACKUP")
        self.hv.add_foreign("VAULT-OFF")
        self.ev.start("TEMPLATE-MAIL")
        c = {x["name"]: x for x in self.ev.template_candidates()}
        self.assertEqual(sorted(c), ["TEMPLATE-MAIL", "TEMPLATE-ON", "TEMPLATE-X-BACKUP"])   # nie VAULT-*, nie DISPOSABLE-*
        self.assertEqual(c["TEMPLATE-MAIL"]["problem"], "")
        self.assertEqual(c["TEMPLATE-MAIL"]["size"], 10 * 2**30)
        self.assertIn("shut it down first", c["TEMPLATE-ON"]["problem"])
        self.assertTrue(c["TEMPLATE-X-BACKUP"]["backup"])
        self.assertFalse(c["TEMPLATE-MAIL"]["backup"])

    def test_import_progress_phases_and_cleanup(self):
        phases = []
        self.ev.import_template("TEMPLATE-MAIL", progress=phases.append)
        self.assertEqual(phases, ["copy", "checksum"])
        self.hv.vol_sha256 = lambda _n: (_ for _ in ()).throw(RuntimeError("read error"))
        with self.assertRaises(RuntimeError):
            self.ev.import_template("TEMPLATE-MAIL")
        self.assertNotIn("TEMPLATE-MAIL-v3.qcow2", self.hv.vols)              # halbe Kopie entfernt

    def test_locale_decimal_mark(self):
        import locale
        old = locale.setlocale(locale.LC_NUMERIC)
        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
            self.assertEqual(capacity.fmt_gib(2560), "2.5 GiB")
            try:
                locale.setlocale(locale.LC_NUMERIC, "de_DE.UTF-8")
            except locale.Error:
                self.skipTest("de_DE.UTF-8 nicht installiert")
            self.assertEqual(capacity.fmt_gib(2560), "2,5 GiB")
        finally:
            locale.setlocale(locale.LC_NUMERIC, old)

    def test_import_versions(self):
        self.ev.import_template("TEMPLATE-MAIL")
        self.assertEqual(self.reg.latest_base("TEMPLATE-MAIL").version, 2)
        self.assertEqual(self.hv.vols["TEMPLATE-MAIL-v2.qcow2"]["path"],
                         config.TEMPLATE_PATH + "/TEMPLATE-MAIL-v2.qcow2")

    def test_names_and_metadata(self):
        a = self.ev.start("TEMPLATE-MAIL")
        b = self.ev.start("TEMPLATE-MAIL", purpose="web")
        c = self.ev.start("TEMPLATE-MAIL")
        self.assertEqual((a.name, b.name, c.name), ("DISPOSABLE-EMAIL-01", "DISPOSABLE-WEB-01", "DISPOSABLE-EMAIL-02"))
        md = ET.fromstring(self.hv.domain_xml(a.name)).find(f"metadata/{{{config.META_URI}}}temp")
        self.assertEqual((md.get("template"), md.get("purpose")), ("TEMPLATE-MAIL", "EMAIL"))
        self.assertTrue(self.reg.temp(a.name).overlay_name.startswith("DISPOSABLE-EMAIL-01-"))
        self.ev.stop(a.name)
        self.assertEqual(self.ev.start("TEMPLATE-MAIL").name, "DISPOSABLE-EMAIL-01")   # Name wiederverwendet
        self.assertEqual(self.ev.list_temps()[0]["template"], "TEMPLATE-MAIL v1")

    def test_name_skips_foreign_domains(self):
        self.hv.add_foreign("DISPOSABLE-EMAIL-01")      # Altbestand mit gleichem Namen
        r = self.ev.start("TEMPLATE-MAIL")
        self.assertEqual(r.name, "DISPOSABLE-EMAIL-02")
        with self.assertRaises(NotOwned):
            self.ev.stop("DISPOSABLE-EMAIL-01")

    def test_bad_purpose(self):
        for p in ("", "E-MAIL", "X" * 17, "../a"):
            with self.assertRaises(EvoxError):
                self.ev.start("TEMPLATE-MAIL", purpose=p)

    def test_memory_cpus_and_last_values(self):
        self.assertEqual(self.settings.load_last_start(), {"memory_mib": 2048, "vcpus": 2, "purpose": "EMAIL"})
        r = self.ev.start("TEMPLATE-MAIL", purpose="WEB", memory_mib=3072, vcpus=1)
        root = ET.fromstring(self.hv.domain_xml(r.name))
        self.assertEqual((root.findtext("memory"), root.findtext("vcpu")), (str(3072 * 1024), "1"))
        self.assertEqual(self.settings.load_last_start(), {"memory_mib": 3072, "vcpus": 1, "purpose": "WEB"})
        self.assertEqual(os.stat(self.settings.last_start_path).st_mode & 0o777, 0o600)
        for mem, cpu in ((512, 1), (2048, 0), (2048, 999)):
            with self.assertRaises(EvoxError):
                self.ev.start("TEMPLATE-MAIL", memory_mib=mem, vcpus=cpu)
        with self.assertRaises(CapacityError):
            self.ev.start("TEMPLATE-MAIL", memory_mib=12288)   # 12 GiB > 12 GiB verfügbar − Overhead

    def test_start_with_net(self):
        r = self.ev.start("TEMPLATE-MAIL")
        self.assertTrue(r.net)
        self.assertEqual(self.hv.domain_state(r.name), "running")
        self.assertEqual(self.hv.secrets, {}, "Secret muss nach dem Start entfernt sein")
        self.assertEqual(self.reg.temp(r.name).state, "running")

    def test_start_net_check_fails_starts_without_net(self):
        self.net_ok = (False, "guard missing")
        r = self.ev.start("TEMPLATE-MAIL")
        self.assertFalse(r.net)
        self.assertIsNone(ET.fromstring(self.hv.domain_xml(r.name)).find("devices/interface"))
        self.assertTrue(any("WITHOUT network" in w for w in r.warnings))

    def test_capacity_red_refuses(self):
        self.mem = MEM_LOW
        with self.assertRaises(CapacityError):
            self.ev.start("TEMPLATE-MAIL")
        self.assertEqual(self.reg.active_temps(), [])

    def test_start_user_numbers_no_warning_and_three_vms(self):
        """CLI/GUI-Rechnung über Evox.start: 2,5 GiB ohne Warnung, 3 × 3 GiB nacheinander, 4. verweigert."""
        self.mem = dict(MEM_USER)
        r = self.ev.start("TEMPLATE-MAIL", memory_mib=2560, want_net=False)
        self.assertEqual(r.warnings, [])
        self.ev.stop(r.name)
        for _ in range(3):
            r = self.ev.start("TEMPLATE-MAIL", memory_mib=3072, want_net=False)
            self.assertEqual(r.warnings, [])
            self.mem["MemAvailable"] -= capacity.need_mib(3072) * 1024
        with self.assertRaises(CapacityError):
            self.ev.start("TEMPLATE-MAIL", memory_mib=3072, want_net=False)
        self.assertEqual(len(self.reg.active_temps()), 3)
        self.assertEqual({(t["memory_mib"], t["vcpus"]) for t in self.ev.list_temps()}, {(3072, 2)})

    def test_start_yellow_warns(self):
        self.mem = {"MemTotal": 16 * GIB, "MemAvailable": 4000 * 1024}
        r = self.ev.start("TEMPLATE-MAIL", memory_mib=2048, want_net=False)
        self.assertTrue(any("Memory tight" in w for w in r.warnings))

    def test_unprotected_base_refuses(self):
        b = self.reg.latest_base("TEMPLATE-MAIL")
        self.hv.vols[b.vol_name]["xml"] = self.hv.vols[b.vol_name]["xml"].replace("0444", "0666")
        with self.assertRaises(PermissionError):
            self.ev.start("TEMPLATE-MAIL")

    def test_live_violation_destroys_everything(self):
        self.hv.live_hook = lambda x: x.replace("<devices>", "<devices><hostdev/>")
        with self.assertRaises(AllowlistViolation):
            self.ev.start("TEMPLATE-MAIL")
        self.assertEqual([n for n in self.hv.domains if n.startswith("DISPOSABLE-")], [])
        self.assertEqual([v for v in self.hv.vols if v.startswith("DISPOSABLE-")], [])
        self.assertEqual(self.hv.secrets, {})
        self.assertEqual(self.reg.active_temps(), [])

    def test_start_failure_cleans_up(self):
        self.hv.fail_create = True
        with self.assertRaises(RuntimeError):
            self.ev.start("TEMPLATE-MAIL")
        self.assertEqual([v for v in self.hv.vols if v.startswith("DISPOSABLE-")], [])
        self.assertEqual(self.hv.secrets, {})

    def test_stop_destroys(self):
        r = self.ev.start("TEMPLATE-MAIL")
        ov = self.reg.temp(r.name).overlay_name
        self.ev.stop(r.name)
        self.assertIsNone(self.hv.domain_xml(r.name))
        self.assertNotIn(ov, self.hv.vols)
        self.assertEqual(self.reg.temp(r.name).state, "gone")

    def test_stop_foreign_refused(self):
        with self.assertRaises(NotOwned):
            self.ev.stop("VAULT-WORK")
        self.assertEqual(self.hv.domain_state("VAULT-WORK"), "running")

    def test_reconcile_guest_poweroff(self):
        r = self.ev.start("TEMPLATE-MAIL")
        ov = self.reg.temp(r.name).overlay_name
        del self.hv.domains[r.name]          # Gast hat sich selbst ausgeschaltet
        acts = self.ev.reconcile()
        self.assertTrue(acts)
        self.assertNotIn(ov, self.hv.vols)
        self.assertEqual(self.reg.temp(r.name).state, "gone")

    def test_reconcile_crash_during_start(self):
        r = self.ev.start("TEMPLATE-MAIL")
        self.reg.set_state(r.name, "creating")   # Absturz vor 'running'
        self.ev.reconcile()
        self.assertIsNone(self.hv.domain_xml(r.name))

    def test_reconcile_orphans_and_foreign_untouched(self):
        r = self.ev.start("TEMPLATE-MAIL")
        self.reg.db.execute("DELETE FROM temps")         # Registry verloren
        dead = "DISPOSABLE-EMAIL-07-dead.qcow2"
        self.hv.vols[dead] = {"path": config.OVERLAY_PATH + "/" + dead, "xml": "", "cap": 1,
                              "pool": config.OVERLAY_POOL}
        self.hv.secrets["s-orphan"] = config.OVERLAY_PATH + "/" + dead
        self.hv.secrets["s-foreign"] = "/var/lib/libvirt/images/other.qcow2"
        self.ev.reconcile()
        self.assertIsNone(self.hv.domain_xml(r.name))
        self.assertNotIn(dead, self.hv.vols)
        self.assertNotIn("s-orphan", self.hv.secrets)
        self.assertIn("s-foreign", self.hv.secrets)
        self.assertEqual(self.hv.domain_state("VAULT-WORK"), "running")
        self.assertEqual(self.hv.domain_state("TEMPLATE-MAIL"), "shutoff")
        self.assertIn(self.reg.latest_base("TEMPLATE-MAIL").vol_name, self.hv.vols)

    def test_running_temp_kept_by_reconcile(self):
        r = self.ev.start("TEMPLATE-MAIL")
        self.ev.reconcile()
        self.assertEqual(self.hv.domain_state(r.name), "running")
        self.assertIn(self.reg.temp(r.name).overlay_name, self.hv.vols)


    # ---- Template entfernen / prüfen / damaged (0.4.0)
    def test_remove_single_copy_and_registry(self):
        b = self.reg.latest_base("TEMPLATE-MAIL")
        r = self.ev.start("TEMPLATE-MAIL")
        self.ev.stop(r.name)                                      # Protokollzeile 'gone' verweist auf die Kopie
        removed = self.ev.remove_template("TEMPLATE-MAIL")
        self.assertEqual([x.version for x in removed], [1])
        self.assertNotIn(b.vol_name, self.hv.vols)
        self.assertIn(f"delvol:{b.vol_name}", self.hv.calls)
        self.assertEqual(self.reg.bases(), [])
        self.assertEqual(self.hv.domain_state("TEMPLATE-MAIL"), "shutoff")      # Original unberührt
        self.assertEqual(self.hv.domain_state("VAULT-WORK"), "running")
        self.assertEqual(self.ev.import_template("TEMPLATE-MAIL") and self.reg.latest_base("TEMPLATE-MAIL").version,
                         2)                                       # Versionsnummer nie wiederverwendet

    def test_remove_versions_and_older(self):
        self.ev.import_template("TEMPLATE-MAIL")
        self.ev.import_template("TEMPLATE-MAIL")
        with self.assertRaisesRegex(EvoxError, "3 versions .*--version N or --older"):
            self.ev.remove_template("TEMPLATE-MAIL")
        with self.assertRaisesRegex(EvoxError, "version 9"):
            self.ev.remove_template("TEMPLATE-MAIL", version=9)
        self.assertEqual([b.version for b in self.ev.remove_plan("TEMPLATE-MAIL", older=True)], [1, 2])
        self.ev.remove_template("TEMPLATE-MAIL", version=2)
        self.assertEqual([b.version for b in self.reg.bases()], [1, 3])
        self.ev.remove_template("TEMPLATE-MAIL", older=True)
        self.assertEqual([b.version for b in self.reg.bases()], [3])
        self.assertIn("TEMPLATE-MAIL-v3.qcow2", self.hv.vols)
        with self.assertRaisesRegex(EvoxError, "no older versions"):
            self.ev.remove_template("TEMPLATE-MAIL", older=True)
        for bad in ("VAULT-WORK", "MAIL", "TEMPLATE-NONE"):
            with self.assertRaises(EvoxError):
                self.ev.remove_template(bad)

    def test_remove_refused_while_used_registry(self):
        r = self.ev.start("TEMPLATE-MAIL")
        del self.hv.domains[r.name]                               # nur noch in der Registry aktiv
        with self.assertRaisesRegex(EvoxError, f"in use by .*{r.name}"):
            self.ev.remove_template("TEMPLATE-MAIL")
        self.assertEqual(len(self.reg.bases()), 1)

    def test_remove_refused_while_used_libvirt(self):
        b = self.reg.latest_base("TEMPLATE-MAIL")
        r = self.ev.start("TEMPLATE-MAIL")
        self.reg.set_state(r.name, "gone")                        # Registry sagt frei, libvirt nicht
        with self.assertRaisesRegex(EvoxError, f"in use by {r.name}"):
            self.ev.remove_template("TEMPLATE-MAIL")
        del self.hv.domains[r.name]
        self.hv.add_foreign("OTHER-VM", state="running", disk=b.vol_path)   # fremde VM nutzt die Kopie
        with self.assertRaisesRegex(EvoxError, "in use by .*OTHER-VM"):
            self.ev.remove_template("TEMPLATE-MAIL")
        del self.hv.domains["OTHER-VM"]                           # verwaistes Overlay mit dieser Kopie als Backing
        with self.assertRaisesRegex(EvoxError, "in use by DISPOSABLE-EMAIL-01-"):
            self.ev.remove_template("TEMPLATE-MAIL")
        self.assertIn(b.vol_name, self.hv.vols)
        self.hv.pool = False
        with self.assertRaisesRegex(EvoxError, "pools are not active"):
            self.ev.remove_template("TEMPLATE-MAIL")

    def test_remove_ownership_and_path_checks(self):
        b = self.reg.latest_base("TEMPLATE-MAIL")
        for col, val in (("vol_path", "/var/lib/libvirt/images/mail.qcow2"),
                         ("vol_name", "../mail.qcow2"), ("vol_name", "VAULT-WORK-v1.qcow2")):
            self.reg.db.execute(f"UPDATE bases SET {col}=? WHERE id=?", (val, b.id))
            with self.assertRaises(NotOwned, msg=val):
                self.ev.remove_template("TEMPLATE-MAIL")
            self.reg.db.execute(f"UPDATE bases SET {col}=? WHERE id=?", (getattr(b, col), b.id))
        self.hv.vols[b.vol_name]["path"] = "/var/lib/libvirt/images/" + b.vol_name   # Volume liegt woanders
        with self.assertRaises(NotOwned):
            self.ev.remove_template("TEMPLATE-MAIL")
        self.assertIn(b.vol_name, self.hv.vols)
        del self.hv.vols[b.vol_name]                              # Datei fehlt schon → nur Eintrag entfernen
        self.ev.remove_template("TEMPLATE-MAIL")
        self.assertEqual(self.reg.bases(), [])
        self.assertNotIn(f"delvol:{b.vol_name}", self.hv.calls)

    def test_damaged_blocks_start_until_reimport(self):
        self.assertTrue(self.ev.verify_template("TEMPLATE-MAIL"))
        self.hv.vol_sha256 = lambda _n: "0" * 64
        self.assertFalse(self.ev.verify_template("TEMPLATE-MAIL", version=1))
        self.assertTrue(self.reg.latest_base("TEMPLATE-MAIL").damaged)
        self.assertTrue(self.ev.template_overview()[0]["damaged"])
        with self.assertRaisesRegex(EvoxError, "DAMAGED"):
            self.ev.start("TEMPLATE-MAIL")
        del self.hv.vol_sha256
        self.ev.import_template("TEMPLATE-MAIL")                  # neu importiert → v2 unbeschädigt
        self.assertTrue(self.ev.start("TEMPLATE-MAIL").name)
        self.ev.stop("DISPOSABLE-EMAIL-01")
        self.ev.remove_template("TEMPLATE-MAIL", version=1)       # beschädigte Kopie entfernen

    def test_on_temp_destroyed_hook(self):
        seen = []
        self.ev.on_temp_destroyed = seen.append
        bid = self.reg.latest_base("TEMPLATE-MAIL").id
        r = self.ev.start("TEMPLATE-MAIL")
        self.ev.stop(r.name)                                      # Stop
        r = self.ev.start("TEMPLATE-MAIL")
        del self.hv.domains[r.name]                               # Gast aus → Reconcile
        self.ev.reconcile()
        self.assertEqual(seen, [bid, bid])
        self.ev.on_temp_destroyed = lambda _b: 1 / 0              # Fehler im Hook stört das Vernichten nicht
        r = self.ev.start("TEMPLATE-MAIL")
        self.ev.stop(r.name)
        self.assertEqual(self.reg.temp(r.name).state, "gone")

    def test_registry_migration_v1(self):
        import sqlite3
        p = Path(self.tmp.name) / "old.sqlite3"
        db = sqlite3.connect(str(p))
        db.executescript("""CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO meta VALUES ('schema_version', '1');
            CREATE TABLE bases (id INTEGER PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL,
              vol_name TEXT NOT NULL UNIQUE, vol_path TEXT NOT NULL, sha256 TEXT NOT NULL, src_uuid TEXT NOT NULL,
              firmware TEXT NOT NULL DEFAULT 'bios', created REAL NOT NULL, retired INTEGER NOT NULL DEFAULT 0,
              UNIQUE (name, version));
            INSERT INTO bases VALUES (1, 'TEMPLATE-X', 1, 'TEMPLATE-X-v1.qcow2', '/p', 'aa', 'u', 'bios', 0, 0);""")
        db.commit()
        db.close()
        reg = Registry(p)
        self.assertEqual(reg.base(1).damaged, 0)
        self.assertEqual(reg.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "2")
        reg.close()

# Schreibende Attrappen-Methoden: dürfen nie eine Vault (Name oder Plattenpfad) betreffen (R29)
WRITE_OPS = ("create_domain", "destroy_domain", "define_secret", "undefine_secret", "create_vol", "delete_vol",
             "setup")
READ_PATH_OPS = ("vol_info", "vol_size", "vol_capacity", "clone_vol")   # Plattenpfad nur lesend


class VaultTest(NoSpawnMixin, unittest.TestCase):
    """A2: Reiter VAULT (nur lesen) und Make template (Kopie einer ausgeschalteten Vault)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.settings = Settings(state_dir=d / "state", runtime_dir=d / "run")
        self.hv = FakeHypervisor()
        self.reg = Registry(self.settings.registry_path)
        self.ev = Evox(self.settings, self.hv, self.reg, net_check=lambda: (True, ""), meminfo=lambda: MEM_OK)
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.ev.import_template("TEMPLATE-MAIL")
        self.disk = self.hv.add_vault("VAULT-MAIL")
        self.touched = []
        self._guard_vaults()

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def _guard_vaults(self):
        """Jeder Schreibzugriff auf VAULT-Namen oder -Plattenpfade gilt als Fehler."""
        hv = self

        def wrap(name, fn):
            def guarded(*a, **k):
                vaults = {n for n in hv.hv.domains if n.startswith("VAULT-")}
                paths = {p for p in hv.hv.disk_info}
                args = [str(x) for x in list(a) + list(k.values())]
                hit = [x for x in args if any(v in x for v in vaults) or any(p in x for p in paths)]
                if hit and (name in WRITE_OPS or name not in READ_PATH_OPS + ("domain_xml", "vault_state",
                                                                              "domain_state")):
                    hv.touched.append((name, hit))
                if name == "clone_vol" and any(v in str(a[0]) for v in vaults):
                    hv.touched.append((name, "target names a vault"))
                return fn(*a, **k)
            return guarded
        for name in dir(self.hv):
            fn = getattr(self.hv, name)
            if callable(fn) and not name.startswith("_") and name not in ("add_vault", "add_foreign"):
                setattr(self.hv, name, wrap(name, fn))

    def assertVaultUntouched(self, name="VAULT-MAIL", state="shutoff"):
        self.assertEqual(self.touched, [])
        self.assertEqual(self.hv.domains[name][1], state)
        self.assertIn(self.disk, self.hv.domains["VAULT-MAIL"][0])

    def test_vault_list_states_and_checks(self):
        self.hv.add_vault("VAULT-RUN", state="running")
        self.hv.add_vault("VAULT-PAUSE")
        self.hv.vault_states["VAULT-PAUSE"] = "paused"
        self.hv.add_vault("VAULT-SAVED")
        self.hv.vault_states["VAULT-SAVED"] = "saved"
        self.hv.add_vault("VAULT-TWO", extra_disk=True)
        self.hv.add_vault("VAULT-CHAIN", backing="/var/lib/libvirt/images/base.qcow2")
        self.hv.add_vault("VAULT-VMDK", fmt="vmdk")
        self.hv.add_vault("VAULT-RAW", fmt="raw")
        self.hv.add_vault("VAULT-NOPOOL", disk="/nopool/x.qcow2")
        v = {x["name"]: x for x in self.ev.vault_list()}
        self.assertNotIn("TEMPLATE-MAIL", v)                       # nur VAULT-*
        self.assertEqual(v["VAULT-MAIL"]["problem"], "")
        self.assertEqual((v["VAULT-MAIL"]["memory_mib"], v["VAULT-MAIL"]["vcpus"], v["VAULT-MAIL"]["size"]),
                         (4096, 2, 20 * 2**30))
        self.assertEqual(v["VAULT-MAIL"]["state_text"], "shut off")
        self.assertEqual(v["VAULT-RAW"]["problem"], "")
        self.assertIn("running – shut it down first", v["VAULT-RUN"]["problem"])
        self.assertIn("paused", v["VAULT-PAUSE"]["problem"])
        self.assertIn("saved", v["VAULT-SAVED"]["problem"])
        self.assertIn("exactly one disk", v["VAULT-TWO"]["problem"])
        self.assertIn("snapshot chain", v["VAULT-CHAIN"]["problem"])
        self.assertIn("only qcow2 or raw", v["VAULT-VMDK"]["problem"])
        self.assertIn("not readable", v["VAULT-NOPOOL"]["problem"])
        for n in ("VAULT-RUN", "VAULT-PAUSE", "VAULT-SAVED", "VAULT-TWO", "VAULT-CHAIN"):
            with self.assertRaises(EvoxError):
                self.ev.make_template(n, "TEMPLATE-X")
        with self.assertRaises(NotOwned):
            self.ev.make_template("TEMPLATE-MAIL", "TEMPLATE-X")
        self.assertEqual(self.reg.pending(), [])
        self.assertEqual(self.touched, [])

    def test_name_suggestion_and_collisions(self):
        self.assertEqual(suggest_template_name("VAULT-WEB", set()), "TEMPLATE-WEB")
        self.assertEqual(suggest_template_name("VAULT-a b/ü", set()), "TEMPLATE-a-b--")
        self.assertEqual(self.ev.suggest_name("VAULT-MAIL"), "TEMPLATE-MAIL-2")    # Domain + Kopie belegt
        self.hv.add_foreign("TEMPLATE-MAIL-2")                                      # Domain
        self.assertEqual(self.ev.suggest_name("VAULT-MAIL"), "TEMPLATE-MAIL-3")
        self.hv._add_vol("<volume><name>TEMPLATE-MAIL-3-v1.qcow2</name></volume>", config.TEMPLATE_POOL,
                         config.TEMPLATE_PATH)                                      # Datei im Pool
        self.assertEqual(self.ev.suggest_name("VAULT-MAIL"), "TEMPLATE-MAIL-4")
        for bad, why in (("VAULT-X", "must start with TEMPLATE-"), ("TEMPLATE-a/b", "Allowed after"),
                         ("TEMPLATE-", "Allowed after"), ("TEMPLATE-" + "x" * 41, "Allowed after"),
                         ("TEMPLATE-MAIL", "already used"), ("template-mail-2", "must start"),
                         ("TEMPLATE-mail-3", "already used")):
            with self.assertRaises(EvoxError) as cm:
                self.ev.check_new_name(bad)
            self.assertIn(why, str(cm.exception), bad)
        self.assertEqual(self.ev.check_new_name(" TEMPLATE-NEW_1.0 "), "TEMPLATE-NEW_1.0")
        with self.assertRaises(EvoxError):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-MAIL")
        self.assertEqual(self.reg.pending(), [])

    def test_space_check_boundaries(self):
        need = space_needed(20 * 2**30, 8 * 2**30)
        self.assertEqual(need, 20 * 2**30 + 20 * 2**30 // 100)
        self.assertEqual(space_needed(2**30, 2**29), 2**30 + 64 * 2**20)          # Mindestrand 64 MiB
        self.assertEqual(space_needed(2**30, 3 * 2**30), 3 * 2**30 + 64 * 2**20)  # belegt > virtuell
        reserve = self.settings.template_reserve_mib * 2**20
        self.hv.free = need + reserve                                               # genau passend → erlaubt
        p = self.ev.make_template_plan("VAULT-MAIL")
        self.assertTrue(p["space"]["ok"])
        self.assertEqual((p["space"]["need"], p["space"]["after"]), (need, need))
        self.hv.free = need + reserve - 1                                           # 1 Byte zu wenig
        self.assertFalse(self.ev.make_template_plan("VAULT-MAIL")["space"]["ok"])
        with self.assertRaises(SpaceError) as cm:
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-MAILX")
        self.assertIn("Not enough space in /srv/evoxd/templates", str(cm.exception))
        self.assertNotIn("clone:" + self.disk, self.hv.calls)                       # nichts kopiert
        self.assertEqual(self.reg.pending(), [])
        self.hv.free = reserve // 2                                                 # weniger als Reserve
        self.assertLess(self.ev.make_template_plan("VAULT-MAIL")["space"]["after"], 0)
        self.assertVaultUntouched()

    def test_make_template_success_registry_and_origin(self):
        phases = []
        self.hv.clone_delay = 1.2
        bid = self.ev.make_template("VAULT-MAIL", "TEMPLATE-MAIL-2", progress=lambda p, f=None: phases.append((p, f)))
        b = self.reg.base(bid)
        self.assertEqual((b.name, b.version, b.vol_name), ("TEMPLATE-MAIL-2", 1, "TEMPLATE-MAIL-2-v1.qcow2"))
        self.assertEqual(b.vol_path, config.TEMPLATE_PATH + "/TEMPLATE-MAIL-2-v1.qcow2")
        storage.check_base_vol(self.hv.vol_xml(b.vol_name))                        # root 0444, flach
        o = self.reg.origin(b.vol_name)
        self.assertEqual((o.vault, o.size), ("VAULT-MAIL", 8 * 2**30))
        self.assertEqual(b.sha256, self.hv.vol_sha256(b.vol_name))
        self.assertEqual(self.reg.pending(), [])
        names = [p for p, _ in phases]
        self.assertEqual([n for i, n in enumerate(names) if i == 0 or names[i - 1] != n],
                         ["check", "copy", "verify", "checksum"])
        fr = [f for p, f in phases if p == "copy" and f is not None]
        self.assertTrue(fr and fr == sorted(fr) and max(fr) <= 0.99, fr)           # Fortschritt steigt
        ov = {t["name"]: t for t in self.ev.template_overview()}
        self.assertEqual(ov["TEMPLATE-MAIL-2"]["origin"], "VAULT-MAIL")
        self.assertIsNone(ov["TEMPLATE-MAIL"]["origin"])                            # Import: keine Vault
        self.assertEqual({x["name"]: x for x in self.ev.vault_list()}["VAULT-MAIL"]["templates"],
                         ["TEMPLATE-MAIL-2 v1"])
        r = self.ev.start("TEMPLATE-MAIL-2")                                        # nutzbar wie ein Import
        self.ev.stop(r.name)
        self.ev.remove_template("TEMPLATE-MAIL-2")
        self.assertEqual(self.reg.origins(), [])
        self.assertVaultUntouched()

    def test_cancel_deletes_partial_copy(self):
        cancel = __import__("threading").Event()
        self.hv.clone_hook = lambda _v: cancel.set()                                # Abbruch während der Kopie
        with self.assertRaises(Cancelled):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB", cancel=cancel)
        self.assertNotIn("TEMPLATE-WEB-v1.qcow2", self.hv.vols)
        self.assertIn("delvol:TEMPLATE-WEB-v1.qcow2", self.hv.calls)
        self.assertEqual((self.reg.pending(), [b.name for b in self.reg.bases()]), ([], ["TEMPLATE-MAIL"]))
        cancel = __import__("threading").Event()
        cancel.set()                                                                # schon vor der Kopie
        self.hv.clone_hook = None
        with self.assertRaises(Cancelled):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB", cancel=cancel)
        self.assertEqual(self.reg.pending(), [])
        self.assertEqual(self.reg.next_base_version("TEMPLATE-WEB"), 3)            # Nummern nie wiederverwendet
        self.assertVaultUntouched()

    def test_vault_started_before_or_during_copy(self):
        orig = self.hv.vault_state
        seq = iter(["shutoff", "running"])                                          # Plan ok, kurz vor Kopie läuft sie
        self.hv.vault_state = lambda n: next(seq, "running") if n == "VAULT-MAIL" else orig(n)
        with self.assertRaises(EvoxError) as cm:
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB")
        self.assertIn("was started – nothing copied", str(cm.exception))
        self.assertNotIn("clone:" + self.disk, self.hv.calls)
        self.hv.vault_state = orig

        def start_vault(_v):                                                        # Benutzer startet sie in virt-manager
            self.hv.domains["VAULT-MAIL"][1] = "running"
        self.hv.clone_hook = start_vault
        with self.assertRaises(EvoxError) as cm:
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB")
        self.assertIn("started during the copy", str(cm.exception))
        self.assertEqual([v for v in self.hv.vols if v.startswith("TEMPLATE-WEB")], [])
        self.assertEqual(self.reg.pending(), [])
        self.assertVaultUntouched(state="running")

    def test_copy_error_and_unreadable_source(self):
        def boom(_v):
            raise RuntimeError("qemu-img: Could not open (simulated)")
        self.hv.clone_hook = boom
        with self.assertRaises(RuntimeError):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB")
        self.assertEqual(([v for v in self.hv.vols if v.startswith("TEMPLATE-WEB")], self.reg.pending()), ([], []))
        self.hv.clone_hook = None
        self.hv.vol_sha256 = lambda _n: 1 / 0                                       # Fehler bei der Prüfsumme
        with self.assertRaises(ZeroDivisionError):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB")
        self.assertEqual([v for v in self.hv.vols if v.startswith("TEMPLATE-WEB")], [])
        self.hv.add_vault("VAULT-NOPOOL", disk="/nopool/v.qcow2")
        with self.assertRaises(EvoxError) as cm:
            self.ev.make_template("VAULT-NOPOOL", "TEMPLATE-WEB")
        self.assertIn("not readable", str(cm.exception))
        self.assertVaultUntouched()

    def test_orphans_after_crash_offered_never_foreign(self):
        # Absturz mitten in der Kopie: pending + halbe Datei bleiben liegen
        self.reg.add_pending("TEMPLATE-WEB-v1.qcow2", "TEMPLATE-WEB", 1, "VAULT-MAIL")
        self.hv._add_vol("<volume><name>TEMPLATE-WEB-v1.qcow2</name></volume>", config.TEMPLATE_POOL,
                         config.TEMPLATE_PATH)
        self.reg.add_pending("TEMPLATE-GONE-v1.qcow2", "TEMPLATE-GONE", 1, "VAULT-MAIL")   # Datei nie entstanden
        self.hv._add_vol("<volume><name>TEMPLATE-FOREIGN-v1.qcow2</name></volume>", config.TEMPLATE_POOL,
                         config.TEMPLATE_PATH)                                      # fremd: nicht in pending
        self.assertIn("TEMPLATE-WEB", self.ev.taken_template_names())
        o = {x["vol_name"]: x for x in self.ev.orphan_copies()}
        self.assertEqual(sorted(o), ["TEMPLATE-GONE-v1.qcow2", "TEMPLATE-WEB-v1.qcow2"])
        self.assertTrue(o["TEMPLATE-WEB-v1.qcow2"]["exists"])
        self.assertFalse(o["TEMPLATE-GONE-v1.qcow2"]["exists"])
        with exclusive(self.settings.lock_path):                                    # anderer Vorgang läuft
            self.assertEqual(self.ev.orphan_copies(), [])
        self.assertEqual(sorted(self.ev.remove_orphans()), ["TEMPLATE-GONE-v1.qcow2", "TEMPLATE-WEB-v1.qcow2"])
        self.assertIn("TEMPLATE-FOREIGN-v1.qcow2", self.hv.vols)                    # nie Fremdes löschen
        self.assertIn("TEMPLATE-MAIL-v1.qcow2", self.hv.vols)
        self.assertEqual(self.reg.pending(), [])
        self.assertEqual(self.reg.next_base_version("TEMPLATE-WEB"), 2)
        self.assertVaultUntouched()

    def test_original_never_written(self):
        """Ganzer Ablauf inkl. Fehlerfällen: kein Schreibzugriff auf VAULT-Namen/-Pfade, nur lesend kopiert."""
        before = list(self.hv.domains["VAULT-MAIL"])
        self.ev.vault_list()
        self.ev.make_template_plan("VAULT-MAIL")
        self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB")
        self.hv.clone_hook = lambda _v: 1 / 0
        with self.assertRaises(ZeroDivisionError):
            self.ev.make_template("VAULT-MAIL", "TEMPLATE-WEB2")
        self.ev.reconcile()
        self.assertEqual(self.hv.domains["VAULT-MAIL"], before)
        self.assertIn("clone:" + self.disk, self.hv.calls)                         # nur als Kopierquelle gelesen
        self.assertFalse([c for c in self.hv.calls if self.disk in c and not c.startswith(("clone:", "volinfo:"))])
        self.assertVaultUntouched()
        # Gegenprobe: der Wächter erkennt einen Schreibzugriff
        self.hv.destroy_domain("VAULT-MAIL")
        self.assertEqual(self.touched[0][0], "destroy_domain")

    def test_registry_additive_and_old_reader(self):
        import sqlite3
        p = Path(self.tmp.name) / "v2.sqlite3"
        db = sqlite3.connect(str(p))
        db.executescript("""CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO meta VALUES ('schema_version', '2');
            CREATE TABLE bases (id INTEGER PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL,
              vol_name TEXT NOT NULL UNIQUE, vol_path TEXT NOT NULL, sha256 TEXT NOT NULL, src_uuid TEXT NOT NULL,
              firmware TEXT NOT NULL DEFAULT 'bios', created REAL NOT NULL, retired INTEGER NOT NULL DEFAULT 0,
              damaged INTEGER NOT NULL DEFAULT 0, UNIQUE (name, version));
            INSERT INTO bases VALUES (1, 'TEMPLATE-X', 3, 'TEMPLATE-X-v3.qcow2', '/p', 'aa', 'u', 'bios', 5, 0, 0);""")
        db.commit()
        db.close()
        reg = Registry(p)                                                           # 0.6.0 öffnet 0.5.x-Registry
        self.assertEqual(reg.base(1).version, 3)
        self.assertIsNone(reg.origin("TEMPLATE-X-v3.qcow2"))
        reg.commit_template("TEMPLATE-Y", 1, "TEMPLATE-Y-v1.qcow2", "/q", "bb", "u2", "efi", "VAULT-Y", 42)
        self.assertEqual(reg.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "2")
        reg.close()
        old = sqlite3.connect(str(p))                                               # wie 0.5.4: SELECT * → 11 Spalten
        rows = old.execute("SELECT * FROM bases ORDER BY id").fetchall()
        self.assertEqual([len(r) for r in rows], [11, 11])
        old.execute("DELETE FROM bases WHERE id=2")                                 # 0.5.4 entfernt die Kopie
        old.commit()
        old.close()
        reg = Registry(p)
        self.assertEqual(reg.origins(), [])                                         # verwaiste Herkunft zählt nicht
        reg.close()

    def test_template_reserve_from_config(self):
        cfg = Path(self.tmp.name) / "c.json"
        cfg.write_text('{"template_reserve_mib": 2048}')
        self.assertEqual(Settings.load(cfg).template_reserve_mib, 2048)
        cfg.write_text('{"template_reserve_mib": 5}')
        self.assertEqual(Settings.load(cfg).template_reserve_mib, config.DEFAULT_TEMPLATE_RESERVE_MIB)


if __name__ == "__main__":
    unittest.main()

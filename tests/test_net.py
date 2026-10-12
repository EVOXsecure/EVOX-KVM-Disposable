import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tests.nospawn import NoSpawnMixin
from evoxd import config
from evoxd.guard import Guard
from evoxd.net import check, model


class FakeNet:
    """Simuliert nft/ip für den Wächter."""

    def __init__(self):
        self.table = None
        self.rules = set()
        self.ports = [{"ifindex": 21, "ifname": "vnet0", "address": "fe:54:00:aa:bb:cc", "flags": ["UP"], "state": "forwarding"}]
        self.bridge_up = True
        self.log = []

    def __call__(self, cmd, input_=None, check=True):
        self.log.append(cmd)
        if cmd[:2] == ["nft", "-f"]:
            self.table = "loaded"
            return ""
        if cmd[:3] == ["nft", "-j", "list"]:
            if self.table is None:
                if check:
                    raise RuntimeError("no table")
                return ""
            return json.dumps({"nftables": [{"metainfo": {}}, {"table": {"name": "evoxd", "handle": 5}},
                                            {"rule": {"expr": self.table, "handle": 9, "packets": 3}}]})
        if cmd[:4] == ["ip", "-j", "-4", "rule"]:
            return json.dumps([{"priority": p, "iif": config.BRIDGE, "dst": d, "dstlen": l, "action": "prohibit"}
                               for p, d, l in self.rules])
        if cmd[:4] == ["ip", "-4", "rule", "add"]:
            net, plen = cmd[cmd.index("to") + 1].split("/")
            self.rules.add((int(cmd[cmd.index("pref") + 1]), net, int(plen)))
            return ""
        if cmd[:3] == ["ip", "-j", "link"]:
            return json.dumps([{k: v for k, v in p.items() if k != "state"} for p in self.ports])
        if cmd[:4] == ["bridge", "-j", "link", "show"]:
            return json.dumps([{"ifindex": p["ifindex"], "ifname": p["ifname"], "master": config.BRIDGE,
                                "state": p["state"]} for p in self.ports])
        if cmd[:3] == ["bridge", "link", "set"]:
            assert cmd[5:] == ["state", "0"], cmd
            for p in self.ports:
                if p["ifname"] == cmd[4]:
                    p["state"] = "disabled"
            return ""
        if cmd[:3] == ["ip", "link", "set"]:
            dev, state = cmd[4], cmd[5]
            if dev == config.BRIDGE:
                self.bridge_up = state == "up"
            for p in self.ports:
                if p["ifname"] == dev:
                    p["flags"] = ["UP"] if state == "up" else []
            return ""
        raise AssertionError(cmd)


class GuardTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.net = FakeNet()
        self.g = Guard(runner=self.net, status_path=os.path.join(self.tmp.name, "s.json"), log=lambda m: None)
        self.g.load_table()

    def tearDown(self):
        self.tmp.cleanup()

    def test_healthy(self):
        st = self.g.check_once()
        self.assertTrue(st["table_ok"])
        self.assertEqual(st["trips"], 0)
        self.assertEqual(len(self.net.rules), len(model.BLOCKED_V4))
        self.assertEqual(oct(os.stat(self.g.status_path).st_mode & 0o777), "0o644")

    def test_flush_cuts_ports_and_reloads(self):
        self.g.check_once()
        self.net.table = None        # nft flush ruleset
        st = self.g.check_once()
        self.assertEqual(st["trips"], 1)
        self.assertEqual(self.net.ports[0]["state"], "disabled", "Port muss gesperrt sein")
        self.assertEqual(self.net.ports[0]["flags"], ["UP"], "Link bleibt oben (kein libvirtd-Hänger)")
        self.assertTrue(st["table_ok"], "Tabelle neu geladen")
        self.assertTrue(self.net.bridge_up, "Bridge bleibt für neue VMs aktiv")
        self.assertEqual(st["tripped_macs"], ["52:54:00:aa:bb:cc"])
        cut = self.net.log.index(["bridge", "link", "set", "dev", "vnet0", "state", "0"])
        reload = max(i for i, c in enumerate(self.net.log) if c[:2] == ["nft", "-f"])
        self.assertLess(cut, reload, "erst trennen, dann neu laden")

    def test_modified_table_cuts(self):
        self.g.check_once()
        self.net.table = "manipuliert"
        self.assertEqual(self.g.check_once()["trips"], 1)

    def test_tripped_port_stays_down(self):
        self.net.table = None
        self.g.check_once()
        self.net.ports[0]["state"] = "forwarding"   # Kernel/libvirt gibt den Port wieder frei
        self.g.check_once()
        self.assertEqual(self.net.ports[0]["state"], "disabled")

    def test_new_vm_after_trip_not_cut(self):
        self.net.table = None
        self.g.check_once()
        self.net.ports = [{"ifindex": 30, "ifname": "vnet0", "address": "fe:54:00:11:22:33", "flags": ["UP"],
                           "state": "forwarding"}]
        st = self.g.check_once()
        self.assertEqual(self.net.ports[0]["state"], "forwarding")
        self.assertEqual(st["tripped_macs"], [])

    def test_route_rules_restored(self):
        self.g.check_once()
        self.net.rules.clear()
        self.g.check_once()
        self.assertEqual(len(self.net.rules), len(model.BLOCKED_V4))

    def test_reload_failure_reports_error(self):
        self.g.check_once()
        self.net.table = None
        orig = self.net.__call__

        def broken(cmd, input_=None, check=True):
            if cmd[:2] == ["nft", "-f"]:
                raise RuntimeError("nft kaputt")
            return orig(cmd, input_, check)
        self.g.run = broken
        st = self.g.check_once()
        self.assertFalse(st["table_ok"])
        self.net.ports.append({"ifindex": 40, "ifname": "vnet1", "address": "fe:54:00:44:55:66", "flags": ["UP"],
                               "state": "forwarding"})
        st = self.g.check_once()
        self.assertTrue(all(p["state"] == "disabled" for p in self.net.ports), "ohne Tabelle: alle Ports gesperrt")
        self.assertFalse(check.check_guard(st, 3, st["ts"])[0])


class ModelCheckTest(NoSpawnMixin, unittest.TestCase):
    def test_ruleset_contents(self):
        rs = model.nft_ruleset()
        for cidr in ("192.168.0.0/16", "10.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4"):
            self.assertIn(cidr, rs)
        self.assertIn('iifname "evoxd0" meta nfproto ipv6', rs)
        self.assertIn("ip saddr != " + config.NET_CIDR, rs)
        self.assertNotIn("203.0.113", rs)

    def test_network_xml_passes_check(self):
        self.assertEqual(check.check_network(model.network_xml()), (True, ""))

    def test_network_deviations(self):
        for old, new in (("isolated='yes'", "isolated='no'"), ("stp='off'", "stp='on'"), ("<dns enable='no'/>", ""),
                         ("mode='nat'", "mode='bridge'")):
            self.assertFalse(check.check_network(model.network_xml().replace(old, new))[0], old)
        v6 = model.network_xml().replace("</network>", "<ip family='ipv6' address='fd00::1' prefix='64'/></network>")
        self.assertFalse(check.check_network(v6)[0])
        self.assertFalse(check.check_network(None)[0])

    def test_nwfilter_check(self):
        self.assertTrue(check.check_nwfilter(model.nwfilter_xml())[0])
        self.assertFalse(check.check_nwfilter(model.nwfilter_xml().replace("clean-traffic", "allow-all"))[0])
        self.assertFalse(check.check_nwfilter(None)[0])

    def test_guard_status(self):
        ok = {"ts": 100.0, "table_ok": True, "rules_ok": True, "ipv6_off": True}
        self.assertTrue(check.check_guard(ok, 3, 101)[0])
        self.assertFalse(check.check_guard(ok, 3, 110)[0], "veraltet")
        self.assertFalse(check.check_guard({}, 3, 101)[0])
        self.assertFalse(check.check_guard(dict(ok, rules_ok=False), 3, 101)[0])

    def test_route_rules(self):
        rr = model.route_rules()
        self.assertEqual(len({r["pref"] for r in rr}), len(rr))
        self.assertTrue(all(r["iif"] == config.BRIDGE and r["action"] == "prohibit" for r in rr))


if __name__ == "__main__":
    unittest.main()

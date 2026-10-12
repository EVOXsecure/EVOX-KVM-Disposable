"""Startprüfung fail-closed (ENTSCHEIDUNGEN.md §20.4): Netz, nwfilter, Wächter."""
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import config
from . import model


def guard_status(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def check_guard(st: dict, max_age: float, now: float = None) -> tuple:
    now = time.time() if now is None else now
    if not st:
        return False, "guard not running"
    if now - st.get("ts", 0) > max_age:
        return False, "guard not responding"
    if not (st.get("table_ok") and st.get("rules_ok") and st.get("ipv6_off")):
        return False, "guard reports incomplete lock"
    return True, ""


def check_network(xml) -> tuple:
    if xml is None:
        return False, f"network {config.NETWORK} not active"
    r = ET.fromstring(xml)
    fwd = r.find("forward")
    checks = [
        (fwd is not None and fwd.get("mode") == "nat" and fwd.get("dev") is None, "forward"),
        (r.find("bridge") is not None and r.find("bridge").get("name") == config.BRIDGE, "bridge"),
        (r.find("bridge") is not None and r.find("bridge").get("stp") == "off", "stp (port blocking needs stp=off)"),
        (r.find("port") is not None and r.find("port").get("isolated") == "yes", "port isolated"),
        (r.find("dns") is not None and r.find("dns").get("enable") == "no", "dns"),
        (not any(i.get("family") == "ipv6" for i in r.findall("ip")), "ipv6"),
        ([i.get("address") for i in r.findall("ip")] == [config.NET_GW], "ip"),
    ]
    bad = [n for ok, n in checks if not ok]
    return (False, f"network differs: {', '.join(bad)}") if bad else (True, "")


def _filter_key(xml: str):
    r = ET.fromstring(xml)
    return (r.get("name"), r.get("chain"),
            tuple(sorted(f.get("filter") for f in r.findall("filterref"))),
            tuple(sorted(ET.tostring(x, encoding="unicode").strip() for x in r.findall("rule"))))


def check_nwfilter(xml) -> tuple:
    if xml is None:
        return False, f"nwfilter {config.NWFILTER} missing"
    want = _filter_key(model.nwfilter_xml())
    have = _filter_key(xml)
    if want[:3] != have[:3] or len(want[3]) != len(have[3]):
        return False, "nwfilter differs"
    return True, ""


def make_net_check(hv, settings):
    def net_check():
        for ok, why in (check_guard(guard_status(settings.guard_status), settings.guard_max_age_s),
                        check_network(hv.network_xml(config.NETWORK)),
                        check_nwfilter(hv.nwfilter_xml(config.NWFILTER))):
            if not ok:
                return False, why
        return True, ""
    return net_check

"""Attrappe für LibvirtHypervisor (kein libvirt in Unit-Tests, CLAUDE.md)."""
import hashlib
import os
import time
import xml.etree.ElementTree as ET

from evoxd import config


class FakeHypervisor:
    def __init__(self):
        self.domains = {}   # name -> [xml, state]
        self.vols = {}      # name -> {"path", "xml", "cap"}
        self.secrets = {}   # uuid -> usage
        self.secret_values = {}
        self.live_hook = None   # fn(xml)->xml, simuliert Abweichungen im Live-XML
        self.fail_create = False
        self.calls = []
        self.pool = True
        self.clone_delay = 0.0  # simuliert lange Kopie (Sekunden)
        self.clone_hook = None  # fn(vol_name) während der Kopie (z. B. Vault starten, Fehler werfen)
        self.vault_states = {}  # name -> paused/saved/… (sonst Zustand aus domains)
        self.disk_info = {}     # Pfad -> {"capacity", "allocation", "format", "backing"}
        self.free = 100 * 2**30  # freier Platz im Template-Pool
        self.stats = {}         # 0.7.0: name -> Roh-Statistik wie libvirt domainListGetStats
        self.stats_error = None  # Ausnahme, die domain_stats wirft (Fehlerfall)
        self.stats_calls = 0

    def add_foreign(self, name, state="shutoff", disk="/var/lib/libvirt/images/mail.qcow2", extra=""):
        u = "11111111-2222-3333-4444-%012d" % len(self.domains)
        self.domains[name] = [f"<domain type='kvm'><name>{name}</name><uuid>{u}</uuid>{extra}<os><type>hvm</type></os>"
                              f"<devices><disk type='file' device='disk'><source file='{disk}'/></disk></devices></domain>",
                              state]

    def list_domains(self):
        return [(n, ET.fromstring(d[0]).findtext("uuid")) for n, d in self.domains.items()]

    def domain_xml(self, name):
        d = self.domains.get(name)
        return d[0] if d else None

    def domain_state(self, name):
        d = self.domains.get(name)
        return d[1] if d else None

    def vault_state(self, name):
        d = self.domains.get(name)
        if d is None:
            return None
        return self.vault_states.get(name, d[1])

    def add_vault(self, name, state="shutoff", disk=None, fmt="qcow2", extra_disk=False, backing=None,
                  capacity=20 * 2**30, allocation=8 * 2**30, mem_kib=4194304, vcpus=2):
        """VAULT-* mit einer Platte (optional zweite Platte, Backing-Kette, Format)."""
        disk = disk or f"/var/lib/libvirt/images/{name}.qcow2"
        u = "99999999-2222-3333-4444-%012d" % len(self.domains)
        dsk = (f"<disk type='file' device='disk'><driver name='qemu' type='{fmt}'/><source file='{disk}'/>"
               "<target dev='vda'/></disk>")
        if extra_disk:
            dsk += "<disk type='file' device='disk'><source file='/var/lib/libvirt/images/data.qcow2'/></disk>"
        dsk += "<disk type='file' device='cdrom'><target dev='sda'/></disk>"
        self.domains[name] = [f"<domain type='kvm'><name>{name}</name><uuid>{u}</uuid>"
                              f"<memory unit='KiB'>{mem_kib}</memory><currentMemory unit='KiB'>{mem_kib}"
                              f"</currentMemory><vcpu>{vcpus}</vcpu><os><type>hvm</type></os>"
                              f"<devices>{dsk}</devices></domain>", state]
        self.disk_info[disk] = {"capacity": capacity, "allocation": allocation, "format": fmt, "backing": backing}
        return disk

    def domain_stats(self, names):
        """Nur lesend wie LibvirtHypervisor.domain_stats; nur übergebene, vorhandene Namen."""
        self.stats_calls += 1
        if self.stats_error:
            raise self.stats_error
        return {n: dict(self.stats[n]) for n in names if n in self.domains and n in self.stats}

    def create_domain(self, xml):
        self.calls.append("create_domain")
        if self.fail_create:
            raise RuntimeError("start failed (simulated)")
        root = ET.fromstring(xml)
        ET.SubElement(root, "seclabel", type="dynamic", model="apparmor", relabel="yes")
        live = ET.tostring(root, encoding="unicode")
        if self.live_hook:
            live = self.live_hook(live)
        self.domains[root.findtext("name")] = [live, "running"]

    def destroy_domain(self, name):
        self.calls.append(f"destroy:{name}")
        self.domains.pop(name, None)

    def define_secret(self, xml, value):
        root = ET.fromstring(xml)
        assert root.get("ephemeral") == "yes" and root.get("private") == "yes"
        value.decode("utf-8")   # wie QEMU: LUKS-Passphrase muss UTF-8 sein
        u = root.findtext("uuid")
        self.secrets[u] = root.findtext("usage/volume")
        self.secret_values[u] = value

    def undefine_secret(self, uuid):
        self.secrets.pop(uuid, None)
        self.secret_values.pop(uuid, None)

    def list_secrets(self):
        return list(self.secrets.items())

    def pool_ok(self):
        return self.pool

    def _add_vol(self, xml, pool, path_dir):
        root = ET.fromstring(xml)
        name = root.findtext("name")
        path = f"{path_dir}/{name}"
        self.vols[name] = {"path": path, "xml": xml, "cap": 10 * 2**30, "pool": pool}
        return path

    def create_vol(self, xml):
        return self._add_vol(xml, config.OVERLAY_POOL, config.OVERLAY_PATH)

    def clone_vol(self, xml, src_path):
        self.calls.append(f"clone:{src_path}")
        name = ET.fromstring(xml).findtext("name")
        info = self.disk_info.get(src_path, {"capacity": 10 * 2**30, "allocation": 6 * 2**30})
        xml = xml.replace("<capacity unit='bytes'>0</capacity>", f"<capacity unit='bytes'>{info['capacity']}</capacity>")
        path = self._add_vol(xml, config.TEMPLATE_POOL, config.TEMPLATE_PATH)   # entsteht schon während der Kopie
        self.vols[name]["alloc"] = 0
        try:
            if self.clone_delay:
                steps = 5
                for i in range(steps):
                    time.sleep(self.clone_delay / steps)
                    self.vols[name]["alloc"] = info["allocation"] * (i + 1) // steps
            if self.clone_hook:
                self.clone_hook(name)
        except BaseException:
            raise
        self.vols[name]["alloc"] = info["allocation"]
        return path

    def delete_vol(self, name, pool=config.OVERLAY_POOL):
        self.calls.append(f"delvol:{name}")
        if name in self.vols and self.vols[name]["pool"] == pool:
            del self.vols[name]

    def list_vols(self, pool=config.OVERLAY_POOL):
        return [(n, v["path"]) for n, v in self.vols.items() if v["pool"] == pool]

    def vol_xml(self, name, pool=config.TEMPLATE_POOL):
        v = self.vols[name]
        assert v["pool"] == pool
        return v["xml"]

    def find_vol(self, name, pool=config.TEMPLATE_POOL):
        v = self.vols.get(name)
        return v["xml"].replace("<target>", f"<target><path>{v['path']}</path>", 1) if v and v["pool"] == pool else None

    def vol_size(self, path):
        if "nopool" in path:
            raise RuntimeError("Storage volume not found")
        if path in self.disk_info:
            return self.disk_info[path]["capacity"], self.disk_info[path]["allocation"]
        return 10 * 2**30, 6 * 2**30

    def vol_info(self, path):
        self.calls.append(f"volinfo:{path}")
        if "nopool" in path:
            raise RuntimeError("Storage volume not found")
        return dict(self.disk_info.get(path, {"capacity": 10 * 2**30, "allocation": 6 * 2**30,
                                              "format": "qcow2", "backing": None}))

    def vol_alloc(self, name, pool=config.TEMPLATE_POOL):
        v = self.vols.get(name)
        return v.get("alloc", 6 * 2**30) if v and v["pool"] == pool else None

    def pool_free(self, pool=config.TEMPLATE_POOL):
        return self.free

    def vol_capacity(self, path):
        return 10 * 2**30

    def vol_sha256(self, name):
        return hashlib.sha256(name.encode()).hexdigest()

    def network_xml(self, name):
        return None

    def nwfilter_xml(self, name):
        return None

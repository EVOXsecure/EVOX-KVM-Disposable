"""Zugriff auf libvirt ausschließlich über die Python-API (T2).

Die Klasse kapselt alle Aufrufe, damit Lifecycle und Tests gegen eine
Attrappe laufen können. Alles Verändernde an Domains geht vorher durch
ownership.require_owned() im Lifecycle.
"""
import hashlib
from typing import Optional

from . import config


class LibvirtHypervisor:
    def __init__(self, uri: str = config.URI):
        import libvirt  # erst hier, damit Unit-Tests ohne libvirt laufen
        self._lv = libvirt
        libvirt.registerErrorHandler(lambda *_: None, None)
        self.conn = libvirt.open(uri)

    def _nf(self, exc) -> bool:
        lv = self._lv
        return exc.get_error_code() in (lv.VIR_ERR_NO_DOMAIN, lv.VIR_ERR_NO_STORAGE_VOL,
                                        lv.VIR_ERR_NO_SECRET, lv.VIR_ERR_NO_NETWORK,
                                        lv.VIR_ERR_NO_NWFILTER, lv.VIR_ERR_NO_STORAGE_POOL)

    # Domains
    def list_domains(self) -> list:
        return [(d.name(), d.UUIDString()) for d in self.conn.listAllDomains()]

    def domain_xml(self, name: str) -> Optional[str]:
        try:
            return self.conn.lookupByName(name).XMLDesc(0)
        except self._lv.libvirtError as e:
            if self._nf(e):
                return None
            raise

    def domain_state(self, name: str) -> Optional[str]:
        try:
            st = self.conn.lookupByName(name).state()[0]
        except self._lv.libvirtError as e:
            if self._nf(e):
                return None
            raise
        return "running" if st == self._lv.VIR_DOMAIN_RUNNING else (
            "shutoff" if st == self._lv.VIR_DOMAIN_SHUTOFF else "other")

    def vault_state(self, name: str) -> Optional[str]:
        """Feiner Zustand (nur lesend): running, paused, saved (ausgeschaltet mit Sicherungsabbild), shutoff, other."""
        lv = self._lv
        try:
            dom = self.conn.lookupByName(name)
            st = dom.state()[0]
            saved = st == lv.VIR_DOMAIN_SHUTOFF and dom.hasManagedSaveImage(0)
        except lv.libvirtError as e:
            if self._nf(e):
                return None
            raise
        if saved:
            return "saved"
        return {lv.VIR_DOMAIN_RUNNING: "running", lv.VIR_DOMAIN_PAUSED: "paused", lv.VIR_DOMAIN_PMSUSPENDED: "paused",
                lv.VIR_DOMAIN_SHUTOFF: "shutoff"}.get(st, "other")

    def domain_stats(self, names) -> dict:
        """Nur lesend (A3): libvirt-Statistiken (CPU, Balloon, Netz, Platten) je laufender Domain, {name: dict}.
        Nicht gefundene Domains fehlen im Ergebnis; nur die übergebenen Namen werden gelesen."""
        lv = self._lv
        doms = []
        for n in names:
            try:
                doms.append(self.conn.lookupByName(n))
            except lv.libvirtError as e:
                if not self._nf(e):
                    raise
        if not doms:
            return {}
        kinds = (lv.VIR_DOMAIN_STATS_CPU_TOTAL | lv.VIR_DOMAIN_STATS_BALLOON
                 | lv.VIR_DOMAIN_STATS_INTERFACE | lv.VIR_DOMAIN_STATS_BLOCK)
        return {d.name(): dict(st) for d, st in self.conn.domainListGetStats(doms, kinds, 0)}

    def create_domain(self, xml: str) -> None:
        # transient; Start ohne Pausieren
        self.conn.createXML(xml, 0)

    def destroy_domain(self, name: str) -> None:
        try:
            self.conn.lookupByName(name).destroy()
        except self._lv.libvirtError as e:
            if not self._nf(e):
                raise

    # Secrets
    def define_secret(self, xml: str, value: bytes) -> None:
        s = self.conn.secretDefineXML(xml, 0)
        s.setValue(value, 0)

    def undefine_secret(self, uuid: str) -> None:
        try:
            self.conn.secretLookupByUUIDString(uuid).undefine()
        except self._lv.libvirtError as e:
            if not self._nf(e):
                raise

    def list_secrets(self) -> list:
        return [(s.UUIDString(), s.usageID() or "") for s in self.conn.listAllSecrets()]

    # Storage: Templates in evoxd-templates, Overlays in evoxd-overlays (/srv/evoxd)
    def _pool(self, name: str = config.OVERLAY_POOL):
        return self.conn.storagePoolLookupByName(name)

    def pool_ok(self) -> bool:
        for name in (config.TEMPLATE_POOL, config.OVERLAY_POOL):
            try:
                if not self._pool(name).isActive():
                    return False
            except self._lv.libvirtError as e:
                if self._nf(e):
                    return False
                raise
        return True

    def create_vol(self, xml: str) -> str:
        """Overlay im Overlay-Pool."""
        return self._pool(config.OVERLAY_POOL).createXML(xml, 0).path()

    def clone_vol(self, xml: str, src_path: str) -> str:
        """Template-Kopie im Template-Pool."""
        src = self.conn.storageVolLookupByPath(src_path)
        return self._pool(config.TEMPLATE_POOL).createXMLFrom(xml, src, 0).path()

    def delete_vol(self, vol_name: str, pool: str = config.OVERLAY_POOL) -> None:
        try:
            self._pool(pool).storageVolLookupByName(vol_name).delete(0)
        except self._lv.libvirtError as e:
            if not self._nf(e):
                raise

    def list_vols(self, pool: str = config.OVERLAY_POOL) -> list:
        p = self._pool(pool)
        p.refresh(0)
        return [(v.name(), v.path()) for v in p.listAllVolumes()]

    def vol_xml(self, vol_name: str, pool: str = config.TEMPLATE_POOL) -> str:
        return self._pool(pool).storageVolLookupByName(vol_name).XMLDesc(0)

    def find_vol(self, vol_name: str, pool: str = config.TEMPLATE_POOL) -> Optional[str]:
        """XML eines Volumes im Pool oder None, wenn es dort nicht existiert; nur lesend."""
        try:
            return self._pool(pool).storageVolLookupByName(vol_name).XMLDesc(0)
        except self._lv.libvirtError as e:
            if e.get_error_code() == self._lv.VIR_ERR_NO_STORAGE_VOL:
                return None
            raise

    def vol_size(self, path: str) -> tuple:
        """(virtuelle Größe, belegter Platz) in Bytes; nur lesend."""
        info = self.conn.storageVolLookupByPath(path).info()
        return info[1], info[2]

    def vol_info(self, path: str) -> dict:
        """Nur lesend: virtuelle Größe, belegter Platz, Format und Backing-Datei eines Volumes (per Pfad)."""
        import xml.etree.ElementTree as ET
        vol = self.conn.storageVolLookupByPath(path)
        info = vol.info()
        root = ET.fromstring(vol.XMLDesc(0))
        fmt = root.find("target/format")
        return {"capacity": info[1], "allocation": info[2], "format": fmt.get("type") if fmt is not None else None,
                "backing": root.findtext("backingStore/path")}

    def vol_alloc(self, vol_name: str, pool: str = config.TEMPLATE_POOL) -> Optional[int]:
        """Belegter Platz eines Volumes (Fortschritt einer laufenden Kopie); None, wenn (noch) nicht vorhanden."""
        try:
            return self._pool(pool).storageVolLookupByName(vol_name).info()[2]
        except self._lv.libvirtError:
            return None

    def pool_free(self, pool: str = config.TEMPLATE_POOL) -> int:
        """Freier Platz im Dateisystem des Pools (Bytes); nur lesend."""
        p = self._pool(pool)
        try:
            p.refresh(0)        # schlägt fehl, solange libvirt in den Pool kopiert → letzter Stand
        except self._lv.libvirtError:
            pass
        return p.info()[3]

    def vol_capacity(self, path: str) -> int:
        return self.conn.storageVolLookupByPath(path).info()[1]

    def vol_sha256(self, vol_name: str) -> str:
        vol = self._pool(config.TEMPLATE_POOL).storageVolLookupByName(vol_name)
        st = self.conn.newStream(0)
        h = hashlib.sha256()
        vol.download(st, 0, 0, 0)
        st.recvAll(lambda _s, data, hh: hh.update(data), h)
        st.finish()
        return h.hexdigest()

    # Netz (nur lesen)
    def network_xml(self, name: str) -> Optional[str]:
        try:
            n = self.conn.networkLookupByName(name)
        except self._lv.libvirtError as e:
            if self._nf(e):
                return None
            raise
        return n.XMLDesc(0) if n.isActive() else None

    def nwfilter_xml(self, name: str) -> Optional[str]:
        try:
            return self.conn.nwfilterLookupByName(name).XMLDesc(0)
        except self._lv.libvirtError as e:
            if self._nf(e):
                return None
            raise

    # Einrichtung (nur eigene Namen; vom Benutzer per `evoxd setup` ausgelöst, HOST-SCHRITTE)
    def setup(self, network_xml: str, nwfilter_xml: str, pools: list) -> list:
        done = []
        if self.nwfilter_xml(config.NWFILTER) is None:
            self.conn.nwfilterDefineXML(nwfilter_xml)
            done.append(f"nwfilter {config.NWFILTER} defined")
        try:
            net = self.conn.networkLookupByName(config.NETWORK)
        except self._lv.libvirtError as e:
            if not self._nf(e):
                raise
            net = self.conn.networkDefineXML(network_xml)
            done.append(f"network {config.NETWORK} defined")
        net.setAutostart(1)
        if not net.isActive():
            net.create()
            done.append(f"network {config.NETWORK} started")
        for name, xml in pools:
            try:
                pool = self._pool(name)
            except self._lv.libvirtError as e:
                if not self._nf(e):
                    raise
                pool = self.conn.storagePoolDefineXML(xml, 0)
                pool.build(0)
                done.append(f"pool {name} defined")
            pool.setAutostart(1)
            if not pool.isActive():
                pool.create(0)
                done.append(f"pool {name} started")
        return done

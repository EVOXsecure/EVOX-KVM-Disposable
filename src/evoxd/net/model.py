"""Soll-Konfiguration des Gastnetzes. Eine Quelle für EVOX, Wächter und Tests."""
import ipaddress

from .. import config

# ENTSCHEIDUNGEN.md §20.4: Heimnetz, Host, Sonderbereiche, Multicast/Broadcast
BLOCKED_V4 = (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
)
RULE_PREF = 3100  # ip rule Priorität (nach local=0, vor main=32766)


def network_xml() -> str:
    net = ipaddress.ip_network(config.NET_CIDR)
    dns = ",".join(config.PUBLIC_RESOLVERS)
    return (
        "<network xmlns:dnsmasq='http://libvirt.org/schemas/network/dnsmasq/1.0'>"
        f"<name>{config.NETWORK}</name>"
        "<forward mode='nat'><nat><port start='1024' end='65535'/></nat></forward>"
        f"<bridge name='{config.BRIDGE}' stp='off' delay='0'/>"
        "<port isolated='yes'/>"
        "<dns enable='no'/>"
        f"<ip address='{config.NET_GW}' netmask='{net.netmask}'>"
        f"<dhcp><range start='{config.NET_DHCP[0]}' end='{config.NET_DHCP[1]}'/></dhcp></ip>"
        f"<dnsmasq:options><dnsmasq:option value='dhcp-option=option:dns-server,{dns}'/></dnsmasq:options>"
        "</network>")


def nwfilter_xml() -> str:
    return (
        f"<filter name='{config.NWFILTER}' chain='root'>"
        "<filterref filter='clean-traffic'/>"
        "<rule action='drop' direction='inout' priority='-600'><mac protocolid='ipv6'/></rule>"
        "</filter>")


def nft_ruleset() -> str:
    br, t = config.BRIDGE, config.NFT_TABLE
    blocked = ", ".join(BLOCKED_V4)
    return f"""table inet {t} {{
	set blocked4 {{
		type ipv4_addr
		flags interval
		elements = {{ {blocked} }}
	}}

	chain input {{
		type filter hook input priority -300; policy accept;
		iifname "{br}" meta nfproto ipv6 counter drop
		iifname "{br}" udp sport 68 udp dport 67 accept
		iifname "{br}" counter drop
	}}

	chain forward {{
		type filter hook forward priority -300; policy accept;
		iifname "{br}" meta nfproto ipv6 counter drop
		oifname "{br}" meta nfproto ipv6 counter drop
		iifname "{br}" oifname "{br}" counter drop
		iifname "{br}" ip saddr != {config.NET_CIDR} counter drop
		iifname "{br}" ip daddr @blocked4 counter drop
	}}
}}
"""


def nft_load_script() -> str:
    """Atomar: Tabelle anlegen (falls fehlt), leeren und neu befüllen."""
    t = config.NFT_TABLE
    return f"table inet {t}\ndelete table inet {t}\n" + nft_ruleset()


def route_rules() -> list:
    """Routing-Sperre R: unabhängig von nftables; wirkt auf weitergeleitete Pakete."""
    return [{"pref": RULE_PREF + i, "iif": config.BRIDGE, "to": cidr, "action": "prohibit"}
            for i, cidr in enumerate(BLOCKED_V4)]

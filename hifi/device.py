"""Device detection — form-factor + brand + bluetooth fallback."""
import hashlib, re
from typing import Optional, List, Dict
from .util import _run


def wpctl_inspect(node_id: str) -> Dict[str, str]:
    r = _run(["wpctl", "inspect", node_id])
    if r.returncode != 0:
        return {}
    info = {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s+\*?\s*(\S+)\s*=\s*(.+)", line)
        if m:
            info[m.group(1)] = m.group(2).strip().strip('"')
    return info


def _strip(line: str) -> str:
    return re.sub(r"[\s│├└─]+", " ", line).strip()


def _device_props(sink_id: str) -> Dict[str, str]:
    info = wpctl_inspect(sink_id)
    dev_id = info.get("device.id", "")
    return wpctl_inspect(dev_id) if dev_id else {}


def list_sinks() -> List[Dict]:
    sinks = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return sinks
    section = None
    for line in r.stdout.splitlines():
        s = _strip(line)
        if "Sinks:" in s:
            section = "sink"
        elif "Sources:" in s or "Streams:" in s or s == "":
            section = None
        elif section == "sink":
            m = re.match(r"\*?\s*(\d+)\.\s+(.+?)(\s+\[vol:.*)?$", s)
            if m:
                sinks.append({"id": m.group(1), "name": m.group(2).strip(),
                              "is_default": s.startswith("*")})
    return sinks


def list_all_devices() -> List[Dict]:
    devices = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return devices
    section = None
    for line in r.stdout.splitlines():
        s = _strip(line)
        if "Devices:" in s:
            section = "device"
        elif "Sinks:" in s:
            section = "sink"
        elif "Sources:" in s:
            section = "source"
        elif "Streams:" in s or s == "":
            section = None
        elif section:
            m = re.match(r"\*?\s*(\d+)\.\s+(.+)$", s)
            if m:
                name = re.sub(r"\s*\[vol:\s*[\d.]+\]\s*$", "", m.group(2).strip())
                dev = {"id": m.group(1), "name": name, "type": section,
                       "is_default": s.startswith("*")}
                if section in ("sink", "source"):
                    info = wpctl_inspect(dev["id"])
                    props = _device_props(dev["id"])
                    dev["node_name"] = info.get("node.name", "")
                    dev["device_name"] = props.get("device.product.name", dev["name"])
                    dev["form_factor"] = props.get("device.form-factor", "")
                    dev["bus"] = props.get("device.bus", "")
                devices.append(dev)
    return devices


def detect_headset() -> Optional[Dict]:
    """3-tier detection: form-factor → brand → bluetooth."""
    BRANDS = re.compile(
        r"hyperx|razer|logitech|sennheiser|sony|jbl|steelseries|"
        r"corsair|redragon|aula|h\d{3}",
        re.IGNORECASE,
    )
    for dev in list_sinks():
        info = wpctl_inspect(dev["id"])
        props = _device_props(dev["id"])
        ff = props.get("device.form-factor", "")
        bus = props.get("device.bus", info.get("device.bus", ""))

        dev["node_name"] = info.get("node.name", "")
        dev["device_name"] = props.get("device.product.name", dev["name"])
        dev["device_id"] = info.get("device.id", "")
        dev["form_factor"] = ff
        dev["bus"] = bus
        dev["icon"] = props.get("device.icon-name", "")

        # Tier 1: form-factor
        if ff == "headset":
            dev["detect_method"] = "form-factor"
            return dev

        # Tier 2: brand name
        name = dev.get("device_name", "")
        if BRANDS.search(name):
            dev["detect_method"] = "brand"
            dev["form_factor"] = "headset"
            return dev

        # Tier 3: bluetooth audio
        if bus == "bluetooth" and any(c in name.lower() for c in ("headset", "headphone", "a2dp")):
            dev["detect_method"] = "bluetooth"
            dev["form_factor"] = "headset"
            return dev

    return None


def compute_fingerprint(dev: Dict) -> str:
    key = f"{dev.get('device_name', '')}|{dev.get('bus', '')}|{dev.get('form_factor', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

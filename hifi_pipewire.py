#!/usr/bin/env python3
"""PipeWire integration: zero-config virtual profiles for mic/speaker effects.

Each effect creates a virtual PipeWire node. User just selects it — done.
No manual config. No terminal. Just pick the profile.
"""

import os, re, subprocess, json
from pathlib import Path
from typing import Optional, Dict, List

PW_CONF = Path.home() / ".config" / "pipewire"
WP_CONF = Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
FILTER_DIR = PW_CONF / "filter-chain.conf.d"
TEMPLATE_DIR = Path("/usr/share/hifi-suite/configs")
STATE_DIR = Path.home() / ".local" / "share" / "hifi-suite"
EE_PRESETS = Path.home() / ".config" / "easyeffects"
CUSTOM_PROFILES = Path.home() / ".config" / "pipewire" / "hifi-suite"


def _env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env(), check=check)


# ── wpctl Device Management ──────────────────────────────────────────────

def wpctl_status() -> str:
    r = _run(["wpctl", "status"])
    return r.stdout if r.returncode == 0 else ""


def wpctl_inspect(node_id: str) -> Dict[str, str]:
    r = _run(["wpctl", "inspect", node_id])
    if r.returncode != 0:
        return {}
    info = {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s+(node\.\S+|device\.\S+)\s*=\s*(.+)", line)
        if m:
            info[m.group(1)] = m.group(2).strip().strip('"')
    return info


def wpctl_inspect_all(node_id: str) -> Dict[str, str]:
    """Extract ALL properties from wpctl inspect (not just node/device prefixed).

    Handles the `*` prefix that PipeWire uses for active/default properties.
    """
    r = _run(["wpctl", "inspect", node_id])
    if r.returncode != 0:
        return {}
    info = {}
    for line in r.stdout.splitlines():
        m = re.match(r"\s+\*?\s*(\S+)\s*=\s*(.+)", line)
        if m:
            info[m.group(1)] = m.group(2).strip().strip('"')
    return info


def wpctl_get_volume(node_id: str) -> Optional[float]:
    r = _run(["wpctl", "get-volume", node_id])
    if r.returncode != 0:
        return None
    m = re.search(r"Volume:\s*([\d.]+)", r.stdout)
    return float(m.group(1)) if m else None


def wpctl_set_volume(node_id: str, vol: float) -> bool:
    vol = max(0.0, min(1.5, vol))
    r = _run(["wpctl", "set-volume", node_id, str(vol)])
    return r.returncode == 0


def wpctl_set_mute(node_id: str, toggle=True) -> bool:
    r = _run(["wpctl", "set-mute", node_id, "toggle" if toggle else "0"])
    return r.returncode == 0


def wpctl_set_default(node_id: str) -> bool:
    r = _run(["wpctl", "set-default", node_id])
    return r.returncode == 0


def _strip_wpctl_line(line: str) -> str:
    """Strip Unicode box-drawing characters and whitespace from wpctl output."""
    return re.sub(r"[\s│├└─]+", " ", line).strip()


def list_audio_devices() -> List[Dict]:
    devices = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return devices
    section = None
    for line in r.stdout.splitlines():
        s = _strip_wpctl_line(line)
        if "Sinks:" in s:
            section = "sink"
        elif "Sources:" in s:
            section = "source"
        elif "Streams:" in s or s == "":
            section = None
        elif section:
            # Handle "* 56. Name" (default) and "56. Name" (non-default)
            m = re.match(r"\*?\s*(\d+)\.\s+(.+)$", s)
            if m:
                is_default = s.startswith("*")
                name = m.group(2).strip()
                # Strip trailing [vol: X.XX] for clean name
                name = re.sub(r"\s*\[vol:\s*[\d.]+\]\s*$", "", name)
                devices.append({
                    "id": m.group(1), "name": name,
                    "type": section, "is_default": is_default,
                })
    return devices


# ── Headset Detection ─────────────────────────────────────────────────────

_BRANDS = [
    "Redragon", "Logitech", "HyperX", "Razer", "SteelSeries",
    "Corsair", "Sennheiser", "Sony", "JBL", "Audio-Technica",
    "Aula", "Bang", "Marshall", "Beats", "Anker", "Edifier",
    "XiiSound", "Weltrend", r"[Hh]\d{3}",
]

_VIRTUAL_PREFIXES = ("filter", "rnnoise", "easyeffects", "combine", "hifi_")


def _is_virtual(node_name: str) -> bool:
    """Check if a node name belongs to a virtual/filter device."""
    nn = node_name.lower()
    return any(p in nn for p in _VIRTUAL_PREFIXES)


def get_connection_type(node_id: str) -> str:
    """Return human-readable connection type from PipeWire device.bus property.

    Returns: 'bluetooth', 'usb', 'pci' (3.5mm jack / built-in), or 'unknown'.
    """
    info = wpctl_inspect(node_id)
    bus = info.get("device.bus", "")
    return bus if bus else "unknown"


def list_all_devices() -> List[Dict]:
    """List all audio devices with full properties (bus, form-factor, icon)."""
    devices = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return devices
    section = None
    for line in r.stdout.splitlines():
        s = _strip_wpctl_line(line)
        if "Devices:" in s:
            section = "device"
        elif "Sinks:" in s:
            section = "sink"
        elif "Sources:" in s:
            section = "source"
        elif "Streams:" in s or s == "":
            section = None
        elif section:
            is_default = s.startswith("*")
            m = re.match(r"\*?\s*(\d+)\.\s+(.+)$", s)
            if m:
                name = m.group(2).strip()
                name = re.sub(r"\s*\[vol:\s*[\d.]+\]\s*$", "", name)
                name = re.sub(r"\s*\[alsa\]\s*$", "", name)
                dev = {
                    "id": m.group(1), "name": name,
                    "type": section, "is_default": is_default,
                }
                if section in ("sink", "source"):
                    info = wpctl_inspect(dev["id"])
                    device_info = _get_device_props(dev["id"])
                    dev["node_name"] = info.get("node.name", "")
                    dev["device_name"] = device_info.get("device.product.name", dev["name"])
                    dev["device_id"] = info.get("device.id", "")
                    dev["form_factor"] = device_info.get("device.form-factor", "")
                    dev["bus"] = device_info.get("device.bus", "")
                    dev["icon"] = device_info.get("device.icon-name", "")
                devices.append(dev)
    return devices


def _get_device_props(sink_node_id: str) -> Dict[str, str]:
    """From a sink node ID, fetch the parent Device node's full properties.

    The Sink node has device.id pointing to the Device node, where
    device.form-factor and device.icon-name live.
    Uses wpctl_inspect_all (not the filtered version) to capture device.id.
    """
    sink_all = wpctl_inspect_all(sink_node_id)
    device_id = sink_all.get("device.id", "")
    if not device_id:
        return {}
    return wpctl_inspect_all(device_id)


def detect_headset() -> Optional[Dict]:
    """Detect any headset using PipeWire device properties.

    Detection priority:
    1. device.form-factor = "headset" on parent Device node
    2. Brand name match (legacy fallback)
    3. Bluetooth device with Audio/Sink (likely BT headset)

    Works for: USB, Bluetooth, 2.4GHz dongle, 3.5mm jack headsets.
    """
    candidates = []

    for dev in list_audio_devices():
        if dev["type"] != "sink":
            continue
        sink_info = wpctl_inspect(dev["id"])
        device_info = _get_device_props(dev["id"])
        form_factor = device_info.get("device.form-factor", "")
        bus = device_info.get("device.bus", sink_info.get("device.bus", ""))
        icon = device_info.get("device.icon-name", "")

        dev["node_name"] = sink_info.get("node.name", "")
        dev["device_name"] = device_info.get("device.product.name", dev["name"])
        dev["device_id"] = sink_info.get("device.id", "")
        dev["form_factor"] = form_factor
        dev["bus"] = bus
        dev["icon"] = icon

        # Strategy 1: form-factor = "headset" (most reliable)
        if form_factor == "headset":
            dev["detect_method"] = "form-factor"
            return dev

        # Collect for fallback scoring
        candidates.append(dev)

    # Strategy 2 & 3: brand match + bluetooth fallback
    for dev in candidates:
        score = 0
        for brand in _BRANDS:
            if re.search(brand, dev["name"], re.I):
                score += 3
        if dev.get("bus") == "bluetooth":
            score += 5
        if score >= 3:
            dev["detect_method"] = "brand" if score == 3 else "bluetooth"
            return dev

    return None


def find_wireless_headset() -> Optional[Dict]:
    """Detect headset — uses PipeWire properties (form-factor, bus, brand)."""
    return detect_headset()


def find_physical_mic() -> Optional[Dict]:
    """Find the first physical microphone (not virtual)."""
    for dev in list_audio_devices():
        if dev["type"] == "source" and not dev["name"].startswith("Noise Cancelling"):
            info = wpctl_inspect(dev["id"])
            nn = info.get("node.name", "")
            # Skip virtual sources created by hifi-suite or EasyEffects
            if "rnnoise" in nn.lower() or "easyeffects" in nn.lower() or "capture." in nn:
                continue
            dev["node_name"] = nn
            return dev
    return None


# ── Battery Detection ─────────────────────────────────────────────────────

def get_battery_level() -> Optional[Dict]:
    """Get battery level of detected headset.

    Methods tried in order:
    1. UPower D-Bus (most reliable for Bluetooth headsets)
    2. PipeWire Battery property (if exposed)
    3. bluetoothctl BatteryPercentage (for paired BT devices)

    Returns: {"level": int (0-100), "charging": bool, "method": str} or None.
    """
    # Method 1: UPower D-Bus
    result = _battery_upower()
    if result:
        return result

    # Method 2: PipeWire battery property
    headset = detect_headset()
    if headset:
        result = _battery_pipewire(headset.get("id", ""))
        if result:
            return result

        # Method 3: bluetoothctl (only for Bluetooth devices)
        if headset.get("bus") == "bluetooth":
            result = _battery_bluetoothctl(headset.get("device_name", ""))
            if result:
                return result

    return None


def _battery_upower() -> Optional[Dict]:
    """Get battery via UPower D-Bus (best for Bluetooth headsets)."""
    r = _run(["gdbus", "call", "--system",
              "--dest", "org.freedesktop.UPower",
              "--object-path", "/org/freedesktop/UPower",
              "--method", "org.freedesktop.UPower.EnumerateDevices"])
    if r.returncode != 0:
        return None

    # Extract device paths
    paths = re.findall(r"(/org/freedesktop/UPower/devices/[^\s']+)", r.stdout)
    for path in paths:
        # Get display name
        name_r = _run(["gdbus", "call", "--system",
                       "--dest", "org.freedesktop.UPower",
                       "--object-path", path,
                       "--method", "org.freedesktop.DBus.Properties.Get",
                       "org.freedesktop.UPower.Device", "NativePath"])
        if name_r.returncode != 0:
            continue
        native = name_r.stdout.lower()

        # Check if it's an audio device (headset)
        # Bluetooth audio devices often show as /org/bluez/... or contain "headset"
        is_audio = any(kw in native for kw in ("headset", "headphone", "audio", "bluez"))
        if not is_audio:
            continue

        # Get percentage
        pct_r = _run(["gdbus", "call", "--system",
                       "--dest", "org.freedesktop.UPower",
                       "--object-path", path,
                       "--method", "org.freedesktop.DBus.Properties.Get",
                       "org.freedesktop.UPower.Device", "Percentage"])
        if pct_r.returncode != 0:
            continue
        pct_m = re.search(r"double\s+([\d.]+)", pct_r.stdout)
        if not pct_m:
            continue

        # Get charging state
        state_r = _run(["gdbus", "call", "--system",
                         "--dest", "org.freedesktop.UPower",
                         "--object-path", path,
                         "--method", "org.freedesktop.DBus.Properties.Get",
                         "org.freedesktop.UPower.Device", "State"])
        charging = False
        if state_r.returncode == 0:
            # State 1 = charging, 2 = discharging, 4 = fully charged
            state_m = re.search(r"uint32\s+(\d+)", state_r.stdout)
            if state_m:
                charging = int(state_m.group(1)) in (1, 4)

        return {"level": int(float(pct_m.group(1))),
                "charging": charging, "method": "upower"}

    return None


def _battery_pipewire(node_id: str) -> Optional[Dict]:
    """Get battery from PipeWire device properties."""
    if not node_id:
        return None
    info = wpctl_inspect_all(node_id)
    # PipeWire may expose battery as device.battery.charge-level or similar
    for key in info:
        if "battery" in key.lower() or "charge" in key.lower():
            m = re.search(r"(\d+)", info[key])
            if m:
                return {"level": int(m.group(1)), "charging": None,
                        "method": "pipewire"}
    return None


def _battery_bluetoothctl(device_name: str) -> Optional[Dict]:
    """Get battery from bluetoothctl (for paired BT devices)."""
    # List paired devices
    r = _run(["bluetoothctl", "devices", "Paired"])
    if r.returncode != 0:
        return None

    mac = None
    for line in r.stdout.splitlines():
        if device_name.lower() in line.lower():
            m = re.match(r"Device\s+([0-9A-F:]{17})", line, re.I)
            if m:
                mac = m.group(1)
                break

    if not mac:
        return None

    # Get battery info
    info_r = _run(["bluetoothctl", "info", mac])
    if info_r.returncode != 0:
        return None

    pct_m = re.search(r"BatteryPercentage:\s*(\d+)", info_r.stdout)
    if pct_m:
        return {"level": int(pct_m.group(1)), "charging": None,
                "method": "bluetoothctl"}

    return None


# ── Zero-Config Virtual Profiles ──────────────────────────────────────────
#
# Each effect creates a virtual PipeWire node:
#   NC    → Virtual microphone source with noise cancellation
#   EQ    → Virtual sink with convolution EQ
#   EC    → Virtual source with echo cancellation
#   Surround → Virtual sink with spatializer
#
# User just selects the virtual node in their audio settings. Done.

def _find_rnnoise_plugin() -> Optional[str]:
    for p in [
        "/usr/lib/ladspa/librnnoise_ladspa.so",
        "/usr/lib64/ladspa/librnnoise_ladspa.so",
        "/usr/lib/x86_64-linux-gnu/ladspa/librnnoise_ladspa.so",
        "/usr/lib/i386-linux-gnu/ladspa/librnnoise_ladspa.so",
    ]:
        if Path(p).exists():
            return p
    return None


def _find_sofa_file() -> Optional[str]:
    """Find a SOFA HRIR file for spatializer."""
    candidates = [
        Path.home() / "Resources" / "hrir.sofa",
        Path("/usr/share/hifi-suite/hrir.sofa"),
        Path.home() / ".config" / "hifi-suite" / "hrir.sofa",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def virtual_surround_manager_installed() -> bool:
    """Check if virtual-surround-manager is installed."""
    r = _run(["which", "virtual-surround-manager"])
    if r.returncode == 0:
        return True
    # Check Flatpak
    r = _run(["flatpak", "list", "--app"])
    return "virtual_surround_manager" in r.stdout.lower() if r.returncode == 0 else False


def virtual_surround_manager_running() -> bool:
    r = _run(["pgrep", "-x", "virtual-surround-manager"])
    return r.returncode == 0


def enable_vsm_surround() -> bool:
    """Launch virtual-surround-manager for GUI-based surround setup.

    VSM uses PipeWire C API directly — no config files needed.
    User selects a HeSuVi WAV preset in the GUI. Done.
    """
    if not virtual_surround_manager_installed():
        print("virtual-surround-manager not found.")
        print("Install: paru -S virtual-surround-manager")
        print("Or: flatpak install flathub de.berny23.virtual_surround_manager")
        return False

    # Launch in background
    _run(["virtual-surround-manager", "&"])
    return True


def _restart_pw():
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])


# ── Custom Headset Profiles (JSON) ───────────────────────────────────────
#
# Users can create custom profiles at:
#   ~/.config/pipewire/hifi-suite/<headset-name>.json
#
# Example profile for AULA G7 Pro 2026:
# {
#   "name": "AULA G7 Pro 2026",
#   "brand": "Aula",
#   "eq_wav": "~/Downloads/aula-g7-pro-eq.wav",
#   "sofa_file": "~/Resources/hrir-generic.sofa",
#   "nc_threshold": 50,
#   "recommended_volume": 75,
#   "notes": "Budget gaming headset with surprisingly good soundstage"
# }

def list_custom_profiles() -> List[Dict]:
    """List all custom headset profiles."""
    profiles = []
    if CUSTOM_PROFILES.exists():
        for f in sorted(CUSTOM_PROFILES.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                data["_file"] = str(f)
                profiles.append(data)
            except Exception:
                pass
    return profiles


def load_custom_profile(headset_name: str) -> Optional[Dict]:
    """Load a custom profile by headset name."""
    # Try exact match
    profile_file = CUSTOM_PROFILES / f"{headset_name}.json"
    if profile_file.exists():
        try:
            return json.loads(profile_file.read_text())
        except Exception:
            pass

    # Try fuzzy match (case-insensitive, partial)
    if CUSTOM_PROFILES.exists():
        name_lower = headset_name.lower()
        for f in CUSTOM_PROFILES.glob("*.json"):
            if name_lower in f.stem.lower():
                try:
                    return json.loads(f.read_text())
                except Exception:
                    pass
    return None


def save_custom_profile(headset_name: str, profile: Dict) -> bool:
    """Save a custom headset profile."""
    CUSTOM_PROFILES.mkdir(parents=True, exist_ok=True)
    profile_file = CUSTOM_PROFILES / f"{headset_name}.json"
    profile["_name"] = headset_name
    try:
        profile_file.write_text(json.dumps(profile, indent=2))
        return True
    except Exception:
        return False


def delete_custom_profile(headset_name: str) -> bool:
    """Delete a custom headset profile."""
    profile_file = CUSTOM_PROFILES / f"{headset_name}.json"
    if profile_file.exists():
        profile_file.unlink()
        return True
    return False


def get_profile_for_headset(headset_name: str) -> Optional[Dict]:
    """Get profile for a headset: custom JSON first, then brand defaults."""
    # Try custom profile first
    custom = load_custom_profile(headset_name)
    if custom:
        return custom

    # Fall back to brand defaults
    name_lower = headset_name.lower()
    for brand, sources in HEADSET_SOURCES.items():
        if brand in name_lower:
            return {
                "name": headset_name,
                "brand": brand,
                "eq_url": sources["eq_url"],
                "eq_note": sources["eq_note"],
                "sofa_url": sources["sofa_url"],
                "sofa_note": sources["sofa_note"],
                "_source": "brand_default",
            }

    # Generic fallback
    return {
        "name": headset_name,
        "brand": "unknown",
        "eq_url": "https://autoeq.app",
        "eq_note": "Search your headset model, select 'Convolution' format",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "Download from ARI database (220+ listeners)",
        "_source": "generic",
    }


def print_headset_profile(headset_name: str):
    """Print profile for a headset (custom or brand default)."""
    profile = get_profile_for_headset(headset_name)
    if not profile:
        print(f"No profile found for: {headset_name}")
        return

    source = profile.get("_source", "custom")
    print(f"\nProfile for: {headset_name}")
    print(f"Source: {'Custom JSON' if source == 'custom' else 'Brand database' if source == 'brand_default' else 'Generic'}")
    print("=" * 60)

    if profile.get("eq_wav"):
        print(f"\nEQ (pre-configured):")
        print(f"  File: {profile['eq_wav']}")
    else:
        print(f"\nEQ (Convolution):")
        print(f"  Site: {profile.get('eq_url', 'https://autoeq.app')}")
        print(f"  How: {profile.get('eq_note', 'Search your headset')}")
        print(f"  Place: ~/.config/hifi-suite/eq.wav")

    if profile.get("sofa_file"):
        print(f"\nSurround (pre-configured):")
        print(f"  File: {profile['sofa_file']}")
    else:
        print(f"\nSurround (HRIR/SOFA):")
        print(f"  Site: {profile.get('sofa_url', 'http://sofacoustics.org/data')}")
        print(f"  How: {profile.get('sofa_note', 'Download from ARI database')}")
        print(f"  Place: ~/Resources/hrir.sofa")

    if profile.get("nc_threshold"):
        print(f"\nNC threshold: {profile['nc_threshold']}%")
    if profile.get("recommended_volume"):
        print(f"Recommended volume: {profile['recommended_volume']}%")
    if profile.get("notes"):
        print(f"Notes: {profile['notes']}")

    print(f"\nCustom profile: ~/.config/pipewire/hifi-suite/{headset_name}.json")


# ── Headset-Specific File Recommendations ─────────────────────────────────

# Database: headset → best sources for EQ/SOFA files
HEADSET_SOURCES = {
    # Format: brand_pattern: { eq_url, eq_search, sofa_url, sofa_note }
    "redragon": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Redragon H{model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav. New models (H888 Luce etc.) may not be listed yet — create a custom profile.",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI (220+ listeners) or CIPIC (45 listeners) — generic HRTF works well",
    },
    "aula": {
        "eq_url": "https://autoeq.app",
        "eq_search": "AULA {model}",
        "eq_note": "New brand — may not be in AutoEq yet. Create custom profile at ~/.config/pipewire/hifi-suite/",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "AULA headsets have good soundstage. ARI or MIT-KEMAR recommended.",
    },
    "logitech": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Logitech {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "G Pro X has good built-in spatial. For custom: ARI database",
    },
    "hyperx": {
        "eq_url": "https://autoeq.app",
        "eq_search": "HyperX {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI or MIT-KEMAR database",
    },
    "razer": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Razer {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI or CIPIC database",
    },
    "steelseries": {
        "eq_url": "https://autoeq.app",
        "eq_search": "SteelSeries {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI database (220+ listeners, best coverage)",
    },
    "corsair": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Corsair {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI or CIPIC database",
    },
    "sennheiser": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Sennheiser {model}",
        "eq_note": "HD 650, HD 800, etc. well supported. Search your model.",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "Sennheiser has great HRTF data. ARI database recommended.",
    },
    "sony": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Sony {model}",
        "eq_note": "WH-1000XM4/XM5 well supported. Search your model.",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI or HUTUBS database (96 listeners with 3D head models)",
    },
    "jbl": {
        "eq_url": "https://autoeq.app",
        "eq_search": "JBL {model}",
        "eq_note": "Search your model, select 'Convolution' format, download .wav",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI or CIPIC database",
    },
    "audio-technica": {
        "eq_url": "https://autoeq.app",
        "eq_search": "Audio-Technica {model}",
        "eq_note": "ATH-M50x, ATH-G1 well supported. Search your model.",
        "sofa_url": "http://sofacoustics.org/data",
        "sofa_note": "ARI database recommended",
    },
}

# HRTF databases from sofacoustics.org
HRTF_DATABASES = [
    ("SOFA Main Repository", "http://sofacoustics.org/data", "Official: worldwide HRTFs, BRIRs, HpIRs"),
    ("ARI Database", "http://sofacoustics.org/data/database/ari", "220+ human listeners, in-the-ear HRTFs"),
    ("CIPIC", "http://sofacoustics.org/data/database/cipic", "45 listeners, anthropometric data"),
    ("MIT-KEMAR", "http://sofacoustics.org/data/database/mit", "Classic dummy head, reference HRTFs"),
    ("HUTUBS", "http://sofacoustics.org/data/database/hutubs/", "96 listeners, 3D head models, HpIRs"),
    ("Aachen", "http://sofacoustics.org/data/database/aachen", "48 listeners, 3D ear models"),
    ("3D3A Princeton", "https://sofacoustics.org/data/database/3d3a/", "38 subjects, 3D head/torso scans"),
    ("SS2 (Meta)", "https://sofacoustics.org/data/database/ss2/", "78 listeners, newest database"),
]


def get_headset_sources(headset_name: str) -> Dict:
    """Get recommended download sources for a specific headset."""
    name_lower = headset_name.lower()
    result = {"eq": None, "sofa": None, "hrtf": HRTF_DATABASES}

    # Match brand
    for brand, sources in HEADSET_SOURCES.items():
        if brand in name_lower:
            result["eq"] = sources["eq_url"]
            result["eq_note"] = sources["eq_note"]
            result["sofa"] = sources["sofa_url"]
            result["sofa_note"] = sources["sofa_note"]
            break

    # Default if no match
    if not result["eq"]:
        result["eq"] = "https://autoeq.app"
        result["eq_note"] = "Search your headset model, select 'Convolution' format"
        result["sofa"] = "https://www.audioease.com/sofa/"
        result["sofa_note"] = "Download any HRIR .sofa file (generic HRTF)"

    return result


def print_headset_sources(headset_name: str):
    """Print download recommendations for a headset."""
    src = get_headset_sources(headset_name)
    print(f"\nRecommended files for: {headset_name}")
    print("=" * 60)
    print(f"\nEQ (Convolution):")
    print(f"  Site: {src['eq']}")
    print(f"  How: {src['eq_note']}")
    print(f"  Place: ~/.config/hifi-suite/eq.wav")
    print(f"\nSurround (HRIR/SOFA):")
    print(f"  Site: {src['sofa']}")
    print(f"  How: {src['sofa_note']}")
    print(f"  Place: ~/Resources/hrir.sofa")
    print(f"\nHRTF Databases (sofacoustics.org):")
    for name, url, desc in src["hrtf"]:
        print(f"  {name}")
        print(f"    {url}")
        print(f"    {desc}")


# ── NC: Noise Cancelling Virtual Microphone ───────────────────────────────

def enable_nc(threshold: float = 50.0) -> bool:
    """Create a virtual microphone with noise cancellation.

    After enabling, a new source "Noise Cancelling Mic" appears in PipeWire.
    User selects it as their input — all noise is removed automatically.
    """
    plugin = _find_rnnoise_plugin()
    if not plugin:
        print("RNNoise not found. Install: noise-suppression-for-voice")
        return False

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / "nc.conf"
    conf.write_text(f"""// HiFi Suite — Noise Cancelling Virtual Microphone
// Select "Noise Cancelling Mic" as your input source. Done.
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "Noise Cancelling Mic"
            media.name       = "Noise Cancelling Mic"
            filter.graph = {{
                nodes = [
                    {{ type = ladspa
                      name = rnnoise
                      plugin = "{plugin}"
                      label  = noise_suppressor_mono
                      control = {{
                          "VAD Threshold (%)"          = {threshold}
                          "VAD Grace Period (ms)"      = 200
                          "Retroactive VAD Grace (ms)" = 0
                      }}
                    }}
                ]
            }}
            audio.rate = 48000
            capture.props = {{
                node.name    = "capture.hifi_rnnoise"
                node.passive = true
                audio.rate   = 48000
            }}
            playback.props = {{
                node.name    = "hifi_rnnoise_source"
                media.class  = Audio/Source
                audio.rate   = 48000
                node.description = "Noise Cancelling Mic"
            }}
        }}
    }}
]
""")
    _restart_pw()
    return True


def disable_nc() -> bool:
    return disable_filter("nc")


# ── Surround: Virtual Surround Sink ──────────────────────────────────────

def enable_surround(channels: int = 8) -> bool:
    """Enable virtual surround.

    Strategy:
    1. If virtual-surround-manager is installed → launch it (best UX)
    2. If SOFA file available → create PipeWire filter chain
    3. Otherwise → tell user what to do
    """
    # Strategy 1: virtual-surround-manager (best UX, uses PipeWire C API directly)
    if virtual_surround_manager_installed():
        return enable_vsm_surround()

    # Strategy 2: SOFA file → PipeWire filter chain
    sofa = _find_sofa_file()
    if not sofa:
        print("No surround method available.")
        print("Option A (recommended): paru -S virtual-surround-manager")
        print("Option B: Download HRIR .sofa to ~/Resources/hrir.sofa")
        # Show headset-specific recommendation
        headset = find_wireless_headset()
        if headset:
            print_headset_sources(headset.get("name", ""))
        else:
            print(f"\nSOFA downloads: http://sofacoustics.org/data")
            print(f"Best: ARI database (220+ listeners)")
            print(f"  http://sofacoustics.org/data/database/ari")
        return False

    FILTER_DIR.mkdir(parents=True, exist_ok=True)

    if channels == 12:
        name, desc = "surround714", "HiFi 7.1.4 Surround"
        ch_positions = "[ FL FR FC LFE RL RR SL SR TFL TFR TRL TRR ]"
        n_channels = 12
    else:
        name, desc = "surround", "HiFi 7.1 Surround"
        ch_positions = "[ FL FR FC LFE RL RR SL SR ]"
        n_channels = 8

    # Build spatializer nodes
    if channels == 8:
        speaker_defs = [
            ("spFL", 30, 0, 3.0), ("spFR", 330, 0, 3.0),
            ("spFC", 0, 0, 3.0), ("spLFE", 180, 0, 3.0),
            ("spRL", 150, 0, 3.0), ("spRR", 210, 0, 3.0),
            ("spSL", 90, 0, 3.0), ("spSR", 270, 0, 3.0),
        ]
    else:
        speaker_defs = [
            ("spFL", 30, 0, 75.0), ("spFR", 330, 0, 75.0),
            ("spFC", 0, 0, 75.0), ("spLFE", 180, 0, 75.0),
            ("spRL", 150, 0, 75.0), ("spRR", 210, 0, 75.0),
            ("spSL", 90, 0, 75.0), ("spSR", 270, 0, 75.0),
            ("spTFL", 30, 75, 75.0), ("spTFR", 330, 75, 75.0),
            ("spTRL", 150, 75, 75.0), ("spTRR", 210, 75, 75.0),
        ]

    nodes = []
    links = []
    inputs = []
    for i, (sname, az, el, rad) in enumerate(speaker_defs):
        nodes.append(f"""                    {{ type = sofa label = spatializer name = {sname}
                      config = {{ filename = "{sofa}" }}
                      control = {{ "Azimuth" = {az:.1f} "Elevation" = {el:.1f} "Radius" = {rad:.1f} }} }}""")
        links.append(f'                    {{ output = "{sname}:Out L"  input = "mixL:In {i+1}" }}')
        links.append(f'                    {{ output = "{sname}:Out R"  input = "mixR:In {i+1}" }}')
        inputs.append(f'"{sname}:In"')

    nodes_str = "\n".join(nodes)
    links_str = "\n".join(links)
    inputs_str = " ".join(inputs)

    conf = FILTER_DIR / f"{name}.conf"
    conf.write_text(f"""// HiFi Suite — Virtual Surround Sink
// Select "{desc}" as your output. Spatial audio is automatic.
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "{desc}"
            media.name       = "{desc}"
            filter.graph = {{
                nodes = [
{nodes_str}
                    {{ type = builtin label = mixer name = mixL }}
                    {{ type = builtin label = mixer name = mixR }}
                ]
                links = [
{links_str}
                ]
                inputs  = [ {inputs_str} ]
                outputs = [ "mixL:Out" "mixR:Out" ]
            }}
            capture.props = {{
                node.name      = "input.hifi_spatializer"
                media.class    = Audio/Sink
                audio.rate     = 48000
                audio.channels = {n_channels}
                audio.position = {ch_positions}
            }}
            playback.props = {{
                node.name      = "output.hifi_spatializer"
                node.passive   = true
                audio.rate     = 48000
                audio.channels = 2
                audio.position = [ FL FR ]
            }}
        }}
    }}
]
""")
    _restart_pw()
    return True


# ── EQ: Convolution Equalizer Sink ───────────────────────────────────────

def enable_eq(wav_path: str = None) -> bool:
    """Create a virtual sink with convolution EQ.

    After enabling, select "HiFi EQ" as your output.
    Audio is equalized automatically using the .wav file.
    """
    if not wav_path:
        candidates = [
            Path.home() / ".config" / "hifi-suite" / "eq.wav",
            Path.home() / "Resources" / "eq.wav",
        ]
        for c in candidates:
            if c.exists():
                wav_path = str(c)
                break

    if not wav_path or not Path(wav_path).exists():
        print("EQ .wav not found.")
        headset = find_wireless_headset()
        if headset:
            print_headset_sources(headset.get("name", ""))
        else:
            print("Download: https://autoeq.app")
            print("  Search your headset model")
            print("  Select 'Convolution' format, download .wav")
            print("  Place at: ~/.config/hifi-suite/eq.wav")
            print("\nSource: https://github.com/jaakkopasanen/AutoEq")
            print("  16k+ stars, measurements from oratory1990, crinacle, Rtings")
        return False

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / "eq.conf"
    conf.write_text(f"""// HiFi Suite — Convolution EQ
// Select "HiFi EQ" as your output. Equalization is automatic.
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "HiFi EQ"
            media.name       = "HiFi EQ"
            filter.graph = {{
                nodes = [
                    {{ type = builtin
                      label = convolver
                      name  = convolver
                      config = {{ filename = "{wav_path}" }}
                    }}
                ]
                inputs  = [ "convolver:In" ]
                outputs = [ "convolver:Out" ]
            }}
            audio.channels = 2
            capture.props = {{
                node.name   = "input.hifi_eq"
                media.class = Audio/Sink
            }}
            playback.props = {{
                node.name   = "output.hifi_eq"
                node.passive = true
            }}
        }}
    }}
]
""")
    _restart_pw()
    return True


# ── EC: Echo Cancellation Source ─────────────────────────────────────────

def enable_ec(mic_node: str = None, output_node: str = None) -> bool:
    """Create a virtual source with echo cancellation.

    After enabling, select "HiFi Echo Cancelled Mic" as your input.
    Echo from speakers is removed automatically.
    """
    if not mic_node or not output_node:
        # Auto-detect: find physical mic and default output
        mic = find_physical_mic()
        sinks = [d for d in list_audio_devices() if d["type"] == "sink"]
        if not mic or not sinks:
            print("Could not auto-detect mic and output. Specify manually.")
            return False
        mic_node = mic.get("node_name", "")
        output_node = sinks[0].get("node_name", "")
        if not mic_node or not output_node:
            print("Could not resolve device node names.")
            return False

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / "ec.conf"
    conf.write_text(f"""// HiFi Suite — Echo Cancellation
// Select "HiFi Echo Cancelled Mic" as your input. Echo is removed automatically.
context.modules = [
    {{ name = libpipewire-module-echo-cancel
        flags = [ nofail ]
        args = {{
            monitor.mode = true
            capture.props = {{
                node.target = "{mic_node}"
                node.passive = true
            }}
            sink.props = {{
                node.target = "{output_node}"
            }}
            source.props = {{
                node.name   = "hifi_ec_source"
                node.description = "HiFi Echo Cancelled Mic"
            }}
        }}
    }}
]
""")
    _restart_pw()
    return True


# ── Filter Management ────────────────────────────────────────────────────

AVAILABLE_FILTERS = {
    "nc": ("Noise Cancelling Mic", enable_nc),
    "surround": ("HiFi Surround (7.1)", lambda: enable_surround(8)),
    "surround714": ("HiFi 7.1.4 Surround", lambda: enable_surround(12)),
    "eq": ("HiFi EQ", enable_eq),
    "ec": ("HiFi Echo Cancelled Mic", enable_ec),
}


def list_filters() -> Dict[str, Dict]:
    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, (desc, _) in AVAILABLE_FILTERS.items():
        conf = FILTER_DIR / f"{name}.conf"
        result[name] = {"description": desc, "enabled": conf.exists(), "path": str(conf)}
    return result


def enable_filter(name: str, params: Optional[Dict] = None) -> bool:
    if name not in AVAILABLE_FILTERS:
        return False
    if easyeffects_running() and name in ("nc", "eq", "ec"):
        print(f"Warning: EasyEffects running — {name} may conflict.")
    _, func = AVAILABLE_FILTERS[name]
    if params:
        return func(**params)
    return func()


def disable_filter(name: str) -> bool:
    conf = FILTER_DIR / f"{name}.conf"
    if conf.exists():
        conf.unlink()
        _restart_pw()
        return True
    return False


# ── WirePlumber Mic Preference Rules ─────────────────────────────────────

def write_mic_priority_rule(node_name: str, priority: int = 2000) -> bool:
    WP_CONF.mkdir(parents=True, exist_ok=True)
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"
    rule_file.write_text(f"""monitor.alsa.rules = [
  {{
    matches = [ {{ node.name = "{node_name}" }} ]
    actions = {{
      update-props = {{
        priority.session = {priority}
        priority.driver  = {priority}
      }}
    }}
  }}
]
""")
    _run(["systemctl", "--user", "restart", "wireplumber"])
    return True


def write_mic_priority_rule_regex(pattern: str, priority: int = 2000) -> bool:
    WP_CONF.mkdir(parents=True, exist_ok=True)
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"
    rule_file.write_text(f"""monitor.alsa.rules = [
  {{
    matches = [ {{ node.name = "~{pattern}" }} ]
    actions = {{
      update-props = {{
        priority.session = {priority}
        priority.driver  = {priority}
      }}
    }}
  }}
]
""")
    _run(["systemctl", "--user", "restart", "wireplumber"])
    return True


def delete_mic_priority_rule() -> bool:
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"
    if rule_file.exists():
        rule_file.unlink()
        _run(["systemctl", "--user", "restart", "wireplumber"])
        return True
    return False


def list_mic_priority_rules() -> List[str]:
    rules = []
    if WP_CONF.exists():
        for f in sorted(WP_CONF.glob("*.conf")):
            content = f.read_text()
            if "priority.session" in content:
                rules.append(f"{f.name}")
    return rules


# ── Combined Sink ─────────────────────────────────────────────────────────

def create_combined_sink(name: str, sink_patterns: List[str]) -> bool:
    PW_CONF.mkdir(parents=True, exist_ok=True)
    conf = PW_CONF / f"51-combine-{name}.conf"
    matches = "\n".join(f'                        {{ node.name = "{p}" }}' for p in sink_patterns)
    conf.write_text(f"""context.modules = [
  {{   name = libpipewire-module-combine-stream
      args = {{
          combine.mode = sink
          node.name    = "combined_{name}"
          node.description = "{name}"
          combine.props = {{ audio.position = [ FL FR ] }}
          stream.props = {{}}
          stream.rules = [
              {{ matches = [
{matches}
              ] actions = {{ create-stream = {{}} }} }}
          ]
      }}
  }}
]
""")
    _restart_pw()
    return True


def delete_combined_sink(name: str) -> bool:
    conf = PW_CONF / f"51-combine-{name}.conf"
    if conf.exists():
        conf.unlink()
        _restart_pw()
        return True
    return False


# ── EasyEffects Integration ───────────────────────────────────────────────

def easyeffects_running() -> bool:
    return _run(["pgrep", "-x", "easyeffects"]).returncode == 0


def easyeffects_list_presets(preset_type: str = "input") -> List[str]:
    preset_dir = EE_PRESETS / preset_type
    if not preset_dir.exists():
        return []
    return [f.stem for f in preset_dir.glob("*.json")]


def easyeffects_load_preset(name: str) -> bool:
    return _run(["easyeffects", "--load-preset", name]).returncode == 0


def easyeffects_stop():
    _run(["systemctl", "--user", "stop", "easyeffects.service"])


def easyeffects_start():
    _run(["systemctl", "--user", "start", "easyeffects.service"])


# ── Auto-Configuration ───────────────────────────────────────────────────

def auto_configure() -> Dict[str, str]:
    """Detect hardware, create all virtual profiles. Zero-config.

    What gets enabled automatically:
    - NC: Always (if RNNoise plugin available) → creates virtual mic
    - Surround: If virtual-surround-manager installed → launch GUI
    - Default input: Set to NC mic if created
    """
    applied = {}

    headset = find_wireless_headset()
    if headset:
        applied["headset"] = headset.get("name", "unknown")

    # Auto-enable NC (virtual mic with noise cancellation)
    if _find_rnnoise_plugin():
        if enable_nc():
            applied["nc"] = "Noise Cancelling Mic created"
            applied["nc_usage"] = "Select 'Noise Cancelling Mic' as input in your app"

    # Auto-restart PipeWire to pick up virtual sources
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])

    # Auto-set NC mic as default input
    sources = [d for d in list_audio_devices() if d["type"] == "source"]
    for src in sources:
        if "hifi_rnnoise" in src["name"].lower() or "noise cancelling" in src["name"].lower():
            wpctl_set_default(src["id"])
            applied["default_input"] = src["name"]
            break

    # Check surround availability
    if virtual_surround_manager_installed():
        applied["surround"] = "virtual-surround-manager available (run: hifi-suite enable surround)"
    else:
        applied["surround"] = "install virtual-surround-manager for 7.1/5.1 surround"

    if easyeffects_running():
        applied["easyeffects"] = "running"

    return applied


# ── State ────────────────────────────────────────────────────────────────

def save_state(key: str, value):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / "pipewire_state.json"
    try:
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
    except Exception:
        state = {}
    state[key] = value
    state_file.write_text(json.dumps(state, indent=2))


def load_state(key: str, default=None):
    state_file = STATE_DIR / "pipewire_state.json"
    try:
        if state_file.exists():
            return json.loads(state_file.read_text()).get(key, default)
    except Exception:
        pass
    return default

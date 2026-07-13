"""Audio utilities — volume, filters, battery, profiles, display. All in one file."""
import sys, json, re, time, subprocess
from pathlib import Path
from typing import Optional, Dict, List
from .util import _run, PW_CONF, STATE_DIR, LEARNING_DIR, CUSTOM_PROFILES

# ── Paths ──────────────────────────────────────────────────────────────────

PW_DROPIN = PW_CONF / "pipewire.conf.d"
EE_PRESETS = Path.home() / ".config" / "easyeffects"

# ── Volume ─────────────────────────────────────────────────────────────────

def wpctl_get_volume(node_id: str) -> Optional[float]:
    r = _run(["wpctl", "get-volume", node_id])
    if r.returncode != 0:
        return None
    m = re.search(r"Volume:\s*([\d.]+)", r.stdout)
    return float(m.group(1)) if m else None


def wpctl_set_volume(node_id: str, vol: float) -> bool:
    return _run(["wpctl", "set-volume", node_id, str(max(0.0, min(1.5, vol)))]).returncode == 0


def wpctl_set_mute(node_id: str) -> bool:
    return _run(["wpctl", "set-mute", node_id, "toggle"]).returncode == 0


def wpctl_set_default(node_id: str) -> bool:
    return _run(["wpctl", "set-default", node_id]).returncode == 0


# ── Low Latency Mode ─────────────────────────────────────────────────────

PW_CONF_DIR = Path.home() / ".config" / "pipewire"
LOW_LATENCY_CONF = PW_CONF_DIR / "hifi-low-latency.conf"


def low_latency_enabled() -> bool:
    """Check if low-latency mode is active."""
    return LOW_LATENCY_CONF.exists()


def low_latency_enable() -> bool:
    """Enable low-latency mode: quantum=64, rate=48000, realtime."""
    PW_CONF_DIR.mkdir(parents=True, exist_ok=True)
    LOW_LATENCY_CONF.write_text("""# HiFi Suite — Low Latency Mode
# Reduces audio buffer size for lower latency (gaming, live monitoring)
# May increase CPU usage and cause glitches on slow systems

context.properties = {
    default.clock.quantum = 64
    default.clock.min-quantum = 32
    default.clock.max-quantum = 256
    default.clock.rate = 48000
}

context.modules = [
    { name = libpipewire-module-rt
        args = {
            nice.level = -11
            rt.prio = 88
            rt.time.soft = -1
            rt.time.hard = -1
        }
        flags = [ ifexists nofail ]
    }
]
""")
    _restart_pw()
    return True


def low_latency_disable() -> bool:
    """Disable low-latency mode (restore defaults)."""
    if LOW_LATENCY_CONF.exists():
        LOW_LATENCY_CONF.unlink()
    _restart_pw()
    return True


# ── PipeWire Node Management ──────────────────────────────────────────────

def pw_list_nodes() -> list:
    """List all PipeWire nodes with type, name, description, and whether they're virtual."""
    import json as _json
    r = _run(["pw-dump"])
    if r.returncode != 0:
        return []
    try:
        data = _json.loads(r.stdout)
    except Exception:
        return []

    nodes = []
    for node in data:
        info = node.get("info", {})
        props = info.get("props", {})
        name = props.get("node.name", "")
        desc = props.get("node.description", "")
        mc = props.get("media.class", "")
        node_id = node.get("id", "")

        if not name or not node_id:
            continue

        # Skip internal PipeWire nodes
        skip_names = ("Dummy-Driver", "Freewheel-Driver", "Midi-Bridge", "bluez_midi")
        if any(s in name for s in skip_names) or any(s in desc for s in skip_names):
            continue

        # Determine category and human-readable label
        category = "device"
        label = ""
        can_delete = False

        if "Stream/" in mc:
            category = "stream"
            label = "Stream"
        elif "rnnoise" in name.lower() or "noise cancelling" in desc.lower():
            category = "filter"
            label = "NC Filter (noise cancellation — input)"
            can_delete = True
        elif "hifi_rnnoise" in name.lower():
            category = "filter"
            label = "NC Source (virtual mic output)"
            can_delete = True
        elif "filtered_output" in name.lower() or "noise filtered" in desc.lower():
            category = "filter"
            label = "NC Filter (noise cancellation — output)"
            can_delete = True
        elif "hifi_eq" in name.lower() or "HiFi EQ" in desc:
            category = "filter"
            label = "EQ Filter (convolution equalizer)"
            can_delete = True
        elif "hifi_spatializer" in name.lower() or "Surround" in desc:
            category = "filter"
            label = "Surround Filter (virtual spatial audio)"
            can_delete = True
        elif "hifi_ec" in name.lower() or "Echo Cancelled" in desc:
            category = "filter"
            label = "EC Filter (echo cancellation)"
            can_delete = True
        elif name.startswith("alsa_") or name.startswith("bluez_"):
            category = "device"
            label = "Hardware Device"
        else:
            # No alsa/bluez prefix = virtual
            category = "virtual"
            label = "Virtual Device"
            can_delete = True

        nodes.append({
            "id": str(node_id),
            "name": name,
            "description": desc,
            "media_class": mc,
            "category": category,
            "label": label,
            "can_delete": can_delete,
        })

    return nodes


def pw_destroy_node(node_id: str) -> bool:
    """Destroy a PipeWire node by ID (only works for virtual/filter nodes)."""
    r = _run(["pw-cli", "destroy", str(node_id)])
    return r.returncode == 0


def reset_all_filters() -> dict:
    """Remove ALL hifi-suite filters, low-latency mode, and restore defaults.

    Returns: {"removed": [...], "errors": [...]}
    """
    removed = []
    errors = []

    # 1. Remove all filter configs from pipewire.conf.d
    if PW_DROPIN.exists():
        for f in PW_DROPIN.glob("hifi-*.conf"):
            try:
                f.unlink()
                removed.append(f.name)
            except Exception as e:
                errors.append(f"{f.name}: {e}")

    # 2. Remove low-latency config
    if LOW_LATENCY_CONF.exists():
        try:
            LOW_LATENCY_CONF.unlink()
            removed.append("hifi-low-latency.conf")
        except Exception as e:
            errors.append(f"hifi-low-latency.conf: {e}")

    # 3. Remove legacy filter configs
    legacy_dir = PW_CONF / "filter-chain.conf.d"
    if legacy_dir.exists():
        for f in legacy_dir.glob("hifi-*.conf"):
            try:
                f.unlink()
                removed.append(f"legacy/{f.name}")
            except Exception as e:
                errors.append(f"legacy/{f.name}: {e}")

    # 4. Restart PipeWire to apply changes
    if removed:
        _restart_pw()

    return {"removed": removed, "errors": errors}


def find_physical_mic() -> Optional[Dict]:
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return None
    section = None
    for line in r.stdout.splitlines():
        s = re.sub(r"[\s│├└─]+", " ", line).strip()
        if "Sources:" in s:
            section = "source"
        elif "Sinks:" in s or "Streams:" in s or s == "":
            section = None
        elif section == "source":
            m = re.match(r"\*?\s*(\d+)\.\s+(.+?)(\s+\[vol:.*)?$", s)
            if m:
                info = _run(["wpctl", "inspect", m.group(1)])
                if info.returncode == 0:
                    nn = re.search(r'node\.name\s*=\s*"([^"]+)"', info.stdout)
                    nn = nn.group(1) if nn else ""
                    skip = ("rnnoise", "easyeffects", "capture.", "virtual")
                    if any(x in nn.lower() for x in skip):
                        continue
                    return {"id": m.group(1), "name": m.group(2).strip(), "node_name": nn}
    return None


# ── Filters ────────────────────────────────────────────────────────────────

class FilterManager:
    def load(self, name: str, config: str) -> bool:
        PW_DROPIN.mkdir(parents=True, exist_ok=True)
        (PW_DROPIN / f"hifi-{name}.conf").write_text(config)
        _restart_pw()
        if self._verify(name):
            return True
        (PW_DROPIN / f"hifi-{name}.conf").unlink(missing_ok=True)
        return False

    def unload(self, name: str):
        (PW_DROPIN / f"hifi-{name}.conf").unlink(missing_ok=True)
        _restart_pw()

    def list_active(self) -> list:
        r = _run(["wpctl", "status"])
        text = r.stdout.lower()
        active = []
        patterns = {"rnnoise": "NC", "noise cancelling": "NC", "hifi eq": "EQ",
                    "convolver": "EQ", "hifi surround": "SURROUND",
                    "spatializer": "SURROUND", "echo cancelled": "EC"}
        found = set()
        for pat, label in patterns.items():
            if pat in text and label not in found:
                active.append(label)
                found.add(label)
        return active

    def _verify(self, name: str, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = _run(["wpctl", "status"]).stdout.lower()
            for p in (f"hifi_{name}", "hifi_rnnoise", "noise cancelling",
                      "hifi eq", "hifi surround", "hifi_spatializer"):
                if p in text:
                    return True
            time.sleep(0.3)
        return False


def _restart_pw():
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])


def find_rnnoise() -> Optional[str]:
    for p in ("/usr/lib/ladspa/librnnoise_ladspa.so",
              "/usr/lib64/ladspa/librnnoise_ladspa.so",
              "/usr/lib/x86_64-linux-gnu/ladspa/librnnoise_ladspa.so"):
        if Path(p).exists():
            return p
    return None


def find_eq_wav() -> Optional[str]:
    for p in (Path.home() / ".config/hifi-suite/eq.wav",
              Path.home() / "Resources/eq.wav"):
        if p.exists():
            return str(p)
    return None


def find_sofa() -> Optional[str]:
    for p in (Path.home() / "Resources/hrir.sofa",
              Path("/usr/share/hifi-suite/hrir.sofa"),
              Path.home() / ".config/hifi-suite/hrir.sofa"):
        if p.exists():
            return str(p)
    return None


def vsm_installed() -> bool:
    return _run(["which", "virtual-surround-manager"]).returncode == 0


def launch_vsm():
    subprocess.Popen(["virtual-surround-manager"], start_new_session=True)


def render_nc(plugin: str, threshold: float = 50.0, mic_node: str = "") -> str:
    """Render NC filter chain config. If mic_node is provided, routes explicitly."""
    cap = (f'node.name = "capture.hifi_rnnoise" node.target = "{mic_node}" audio.rate = 48000'
           if mic_node else
           'node.name = "capture.hifi_rnnoise" node.passive = true audio.rate = 48000')
    return f'''# HiFi Suite — Noise Cancelling (Input)
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ ifexists nofail ]
        args = {{
            node.description = "Noise Cancelling Mic"
            media.name = "Noise Cancelling Mic"
            filter.graph = {{
                nodes = [
                    {{ type = ladspa name = rnnoise plugin = "{plugin}"
                      label = noise_suppressor_mono
                      control = {{ "VAD Threshold (%)" = {threshold}
                                  "VAD Grace Period (ms)" = 200
                                  "Retroactive VAD Grace (ms)" = 0 }} }}
                ]
            }}
            audio.rate = 48000
            capture.props = {{ {cap} }}
            playback.props = {{ node.name = "hifi_rnnoise_source"
                media.class = Audio/Source audio.rate = 48000
                node.description = "Noise Cancelling Mic" }}
        }}
    }}
]'''


def render_noise_output(plugin: str, out_node: str, threshold: float = 50.0) -> str:
    """Render noise filter for OUTPUT — cleans incoming audio from the other side."""
    return f'''# HiFi Suite — Noise Cancelling (Output)
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ ifexists nofail ]
        args = {{
            node.description = "Noise Filtered Output"
            media.name = "Noise Filtered Output"
            filter.graph = {{
                nodes = [
                    {{ type = ladspa name = rnnoise plugin = "{plugin}"
                      label = noise_suppressor_mono
                      control = {{ "VAD Threshold (%)" = {threshold}
                                  "VAD Grace Period (ms)" = 200
                                  "Retroactive VAD Grace (ms)" = 0 }} }}
                ]
            }}
            audio.rate = 48000
            capture.props = {{ node.target = "{out_node}" node.passive = true audio.rate = 48000 }}
            playback.props = {{ node.name = "hifi_filtered_output"
                media.class = Audio/Sink audio.rate = 48000
                node.description = "Noise Filtered Output" }}
        }}
    }}
]'''


def render_eq(wav: str) -> str:
    return f'''# HiFi Suite — EQ
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ ifexists nofail ]
        args = {{
            node.description = "HiFi EQ"
            media.name = "HiFi EQ"
            filter.graph = {{
                nodes = [
                    {{ type = builtin label = convolver name = convolver
                      config = {{ filename = "{wav}" }} }}
                ]
                inputs = [ "convolver:In" ]
                outputs = [ "convolver:Out" ]
            }}
            audio.channels = 2
            capture.props = {{ node.name = "input.hifi_eq" media.class = Audio/Sink }}
            playback.props = {{ node.name = "output.hifi_eq" node.passive = true }}
        }}
    }}
]'''


def render_surround(sofa: str, channels: int = 8) -> str:
    if channels == 8:
        name, desc = "surround", "HiFi 7.1 Surround"
        n_ch, ch_pos = 8, "[ FL FR FC LFE RL RR SL SR ]"
        speakers = [("spFL",30,0,3),("spFR",330,0,3),("spFC",0,0,3),("spLFE",180,0,3),
                    ("spRL",150,0,3),("spRR",210,0,3),("spSL",90,0,3),("spSR",270,0,3)]
    else:
        name, desc = "surround714", "HiFi 7.1.4 Surround"
        n_ch, ch_pos = 12, "[ FL FR FC LFE RL RR SL SR TFL TFR TRL TRR ]"
        speakers = [("spFL",30,0,75),("spFR",330,0,75),("spFC",0,0,75),("spLFE",180,0,75),
                    ("spRL",150,0,75),("spRR",210,0,75),("spSL",90,0,75),("spSR",270,0,75),
                    ("spTFL",30,75,75),("spTFR",330,75,75),("spTRL",150,75,75),("spTRR",210,75,75)]
    nodes, links, inputs = [], [], []
    for i, (sn, az, el, rad) in enumerate(speakers):
        nodes.append(f'{{ type = sofa label = spatializer name = {sn} '
                     f'config = {{ filename = "{sofa}" }} '
                     f'control = {{ "Azimuth" = {az:.1f} "Elevation" = {el:.1f} "Radius" = {rad:.1f} }} }}')
        links.append(f'{{ output = "{sn}:Out L" input = "mixL:In {i+1}" }}')
        links.append(f'{{ output = "{sn}:Out R" input = "mixR:In {i+1}" }}')
        inputs.append(f'"{sn}:In"')
    return f'''# HiFi Suite — Surround
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ ifexists nofail ]
        args = {{
            node.description = "{desc}"
            media.name = "{desc}"
            filter.graph = {{
                nodes = [
                    {", ".join(nodes)},
                    {{ type = builtin label = mixer name = mixL }},
                    {{ type = builtin label = mixer name = mixR }}
                ]
                links = [ {", ".join(links)} ]
                inputs = [ {", ".join(inputs)} ]
                outputs = [ "mixL:Out" "mixR:Out" ]
            }}
            capture.props = {{ node.name = "input.hifi_spatializer" media.class = Audio/Sink
                audio.rate = 48000 audio.channels = {n_ch} audio.position = {ch_pos} }}
            playback.props = {{ node.name = "output.hifi_spatializer" node.passive = true
                audio.rate = 48000 audio.channels = 2 audio.position = [ FL FR ] }}
        }}
    }}
]'''


def render_ec(mic_node: str, out_node: str) -> str:
    return f'''# HiFi Suite — Echo Cancellation
context.modules = [
    {{ name = libpipewire-module-echo-cancel
        flags = [ ifexists nofail ]
        args = {{
            monitor.mode = true
            capture.props = {{ node.target = "{mic_node}" node.passive = true }}
            sink.props = {{ node.target = "{out_node}" }}
            source.props = {{ node.name = "hifi_ec_source"
                node.description = "HiFi Echo Cancelled Mic" }}
        }}
    }}
]'''


# ── Battery ────────────────────────────────────────────────────────────────

def get_battery(device: Dict = None) -> Optional[Dict]:
    for method in (_battery_upower, _battery_pipewire):
        result = method()
        if result:
            return result
    if device and device.get("bus") == "bluetooth":
        result = _battery_btctl(device.get("device_name", ""))
        if result:
            return result
    return None


def _battery_upower() -> Optional[Dict]:
    r = _run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UPower",
              "--object-path", "/org/freedesktop/UPower",
              "--method", "org.freedesktop.UPower.EnumerateDevices"])
    if r.returncode != 0:
        return None
    for path in re.findall(r"(/org/freedesktop/UPower/devices/[^\s']+)", r.stdout):
        name_r = _run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UPower",
                        "--object-path", path, "--method",
                        "org.freedesktop.DBus.Properties.Get",
                        "org.freedesktop.UPower.Device", "NativePath"])
        if name_r.returncode != 0:
            continue
        native = name_r.stdout.lower()
        if not any(kw in native for kw in ("headset", "headphone", "audio", "bluez")):
            continue
        pct_r = _run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UPower",
                       "--object-path", path, "--method",
                       "org.freedesktop.DBus.Properties.Get",
                       "org.freedesktop.UPower.Device", "Percentage"])
        if pct_r.returncode != 0:
            continue
        pct = re.search(r"double\s+([\d.]+)", pct_r.stdout)
        if not pct:
            continue
        state_r = _run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UPower",
                         "--object-path", path, "--method",
                         "org.freedesktop.DBus.Properties.Get",
                         "org.freedesktop.UPower.Device", "State"])
        charging = False
        if state_r.returncode == 0:
            st = re.search(r"uint32\s+(\d+)", state_r.stdout)
            if st:
                charging = int(st.group(1)) in (1, 4)
        return {"level": int(float(pct.group(1))), "charging": charging, "method": "upower"}
    return None


def _battery_pipewire() -> Optional[Dict]:
    from .device import detect_headset, wpctl_inspect
    dev = detect_headset()
    if not dev:
        return None
    info = wpctl_inspect(dev.get("id", ""))
    bat = info.get("device.battery.percentage", "")
    if not bat:
        return None
    try:
        level = int(float(bat))
    except (ValueError, TypeError):
        return None
    chg = info.get("device.battery.charging", "").lower() in ("true", "yes", "1")
    return {"level": level, "charging": chg, "method": "pipewire"}


def _battery_btctl(name: str) -> Optional[Dict]:
    r = _run(["bluetoothctl", "devices", "Paired"])
    if r.returncode != 0:
        return None
    mac = None
    for line in r.stdout.splitlines():
        if name.lower() in line.lower():
            m = re.match(r"Device\s+([0-9A-F:]{17})", line, re.I)
            if m:
                mac = m.group(1)
                break
    if not mac:
        return None
    info = _run(["bluetoothctl", "info", mac])
    if info.returncode != 0:
        return None
    pct = re.search(r"BatteryPercentage:\s*(\d+)", info.stdout)
    return {"level": int(pct.group(1)), "charging": None, "method": "bluetoothctl"} if pct else None


# ── Learning DB ────────────────────────────────────────────────────────────

class LearningDB:
    def __init__(self):
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, fp: str) -> Optional[Dict]:
        p = LEARNING_DIR / f"{fp}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def record_success(self, fp: str, name: str, device: Dict = None):
        lesson = self._get_or_create(fp)
        if device:
            lesson.setdefault("device_name", device.get("device_name", ""))
            lesson.setdefault("bus", device.get("bus", ""))
            lesson.setdefault("form_factor", device.get("form_factor", ""))
        sf = lesson.setdefault("successful_filters", {})
        entry = sf.setdefault(name, {"count": 0})
        entry["count"] += 1
        entry["last_used"] = time.time()
        self._save(fp, lesson)

    def record_failure(self, fp: str, name: str, error: str, device: Dict = None):
        lesson = self._get_or_create(fp)
        if device:
            lesson.setdefault("device_name", device.get("device_name", ""))
            lesson.setdefault("bus", device.get("bus", ""))
            lesson.setdefault("form_factor", device.get("form_factor", ""))
        ff = lesson.setdefault("failed_filters", {})
        entry = ff.setdefault(name, {"count": 0})
        entry["count"] += 1
        entry["error"] = error
        self._save(fp, lesson)

    def find_similar(self, dev: Dict) -> Optional[Dict]:
        bus, ff = dev.get("bus", ""), dev.get("form_factor", "")
        best, best_score = None, 0
        for f in LEARNING_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            score = (data.get("bus") == bus) + 2 * (data.get("form_factor") == ff)
            if score > best_score and data.get("successful_filters"):
                best_score, best = score, data
        return best

    def _get_or_create(self, fp: str) -> Dict:
        return self.get(fp) or {"fingerprint": fp, "device_name": "", "bus": "",
                                "form_factor": "", "successful_filters": {},
                                "failed_filters": {}, "first_seen": time.time()}

    def _save(self, fp: str, data: Dict):
        data["last_seen"] = time.time()
        (LEARNING_DIR / f"{fp}.json").write_text(json.dumps(data, indent=2))


# ── Profiles ───────────────────────────────────────────────────────────────

HEADSET_SOURCES = {
    "redragon": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "aula": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "logitech": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "hyperx": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "razer": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "sennheiser": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "sony": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
    "jbl": {"eq_url": "https://autoeq.app", "sofa_url": "http://sofacoustics.org/data"},
}


def list_profiles() -> List[Dict]:
    if not CUSTOM_PROFILES.exists():
        return []
    return [json.loads(f.read_text()) for f in CUSTOM_PROFILES.glob("*.json")
            if f.suffix == ".json"]


def get_profile(name: str) -> Dict:
    p = CUSTOM_PROFILES / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    for brand, src in HEADSET_SOURCES.items():
        if brand in name.lower():
            return {"name": name, "brand": brand, **src}
    return {"name": name, "brand": "unknown", "eq_url": "https://autoeq.app"}


def save_profile(name: str, profile: Dict) -> bool:
    CUSTOM_PROFILES.mkdir(parents=True, exist_ok=True)
    profile["_name"] = name
    (CUSTOM_PROFILES / f"{name}.json").write_text(json.dumps(profile, indent=2))
    return True


def delete_profile(name: str) -> bool:
    p = CUSTOM_PROFILES / f"{name}.json"
    if p.exists():
        p.unlink()
        return True
    return False


# ── Display Helpers ────────────────────────────────────────────────────────

class Color:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; CYAN = "\033[36m"


USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text, color):
    return f"{color}{text}{Color.RESET}" if USE_COLOR else str(text)


def bold(t): return c(t, Color.BOLD)
def dim(t): return c(t, Color.DIM)
def success(t): return c(t, Color.GREEN)
def error(t): return c(t, Color.RED)
def warning(t): return c(t, Color.YELLOW)


def device_icon(bus):
    return {"usb": "[USB]", "bluetooth": "[BT]", "pci": "[3.5mm]"}.get(bus, "[???]")


def print_banner():
    import sys as _sys
    print()
    print(c("  ┌─────────────────────────────────────────┐", Color.CYAN))
    print(c("  │", Color.CYAN) + c("  HiFi Suite v3.0", Color.BOLD) + c("                              │", Color.CYAN))
    print(c("  │", Color.CYAN) + dim("  Zero-config audio for wireless headsets") + c("  │", Color.CYAN))
    print(c("  └─────────────────────────────────────────┘", Color.CYAN))
    print()


def print_device_table(devices):
    if not devices:
        print(warning("  No audio devices found."))
        return
    print(f"\n  {bold('Audio Devices')}")
    print(dim("  " + "─" * 60))
    for i, dev in enumerate(devices):
        ff = dev.get("form_factor", "")
        label = c("Headset", Color.GREEN) if ff == "headset" else c(dev.get("type", "?"), Color.DIM)
        default = c(" *", Color.GREEN) if dev.get("is_default") else ""
        name = dev.get("name", "?")[:35]
        print(f"  {c(str(i+1), Color.CYAN):>4}  {name:<35} {label}{default}")
    print(dim("  " + "─" * 60))


def print_effects(active=None):
    from .audio import FilterManager, low_latency_enabled
    if active is None:
        active = FilterManager().list_active()
    active_text = " ".join(active).lower()
    effects = [
        ("nc", "Noise Filter — Input (your mic, outgoing)"),
        ("nc_out", "Noise Filter — Output (other person, incoming)"),
        ("ec", "Echo Cancellation — Input (your mic, reduces echo)"),
        ("surround", "7.1 Surround"),
        ("eq", "Equalizer"),
    ]
    print(f"\n  {bold('Effects')}")
    print(dim("  " + "─" * 55))
    for key, label in effects:
        on = key in active_text
        icon = c("[ON] ", Color.GREEN) if on else c("[off]", Color.DIM)
        print(f"  {icon} {c(label, Color.BOLD if on else Color.DIM)}")
    # Low latency
    ll = low_latency_enabled()
    icon = c("[ON] ", Color.GREEN) if ll else c("[off]", Color.DIM)
    label = "Low Latency Mode"
    extra = dim(" (quantum=64, rt priority)") if ll else ""
    print(f"  {icon} {c(label, Color.BOLD if ll else Color.DIM)}{extra}")
    print(dim("  " + "─" * 55))
    if not ll:
        print(dim("  Tip: hifi-suite effect latency on  — for gaming/live monitoring"))
    print()


def print_status(dev, volume, battery):
    print(f"\n  {bold('Device Status')}")
    print(dim("  " + "─" * 45))
    print(f"  {c('Device:', Color.CYAN)}    {bold(dev.get('device_name', 'Unknown'))}")
    print(f"  {c('Bus:', Color.CYAN)}       {device_icon(dev.get('bus', '?'))} {dev.get('bus', '?')}")
    if volume is not None:
        pct = int(volume * 100)
        color = Color.GREEN if pct > 70 else Color.YELLOW if pct > 30 else Color.RED
        bar_len = 20
        filled = int(bar_len * volume)
        bar = c("=" * filled, color) + c("-" * (bar_len - filled), Color.DIM)
        print(f"  {c('Volume:', Color.CYAN)}    [{bar}] {pct}%")
    if battery:
        level = battery["level"]
        color = Color.GREEN if level > 50 else Color.YELLOW if level > 20 else Color.RED
        chg = " [CHG]" if battery.get("charging") else ""
        print(f"  {c('Battery:', Color.CYAN)}   {c(f'{level}%', color)}{chg}")
    print(dim("  " + "─" * 45))


def print_node_table(nodes):
    """Print all PipeWire nodes in a categorized table with clear labels."""
    if not nodes:
        print(warning("  No nodes found."))
        return

    categories = [
        ("device", "Physical Devices (hardware)", Color.GREEN),
        ("virtual", "Virtual Devices (software-created)", Color.YELLOW),
        ("filter", "Active Filters (hifi-suite)", Color.CYAN),
        ("stream", "Active Streams (apps using audio)", Color.DIM),
    ]

    print(f"\n  {bold('PipeWire Nodes')}")
    print(dim("  " + "─" * 65))

    for cat_key, cat_label, cat_color in categories:
        cat_nodes = [n for n in nodes if n["category"] == cat_key]
        if not cat_nodes:
            continue
        print(f"\n  {c(cat_label, cat_color)}")
        print(dim("  " + "·" * 60))
        for n in cat_nodes:
            nid = c(n["id"], Color.CYAN)
            name = n["description"] or n["name"]
            if len(name) > 35:
                name = name[:32] + "..."
            label = n.get("label", "")
            if n["can_delete"]:
                badge = c("[removable]", Color.RED)
            else:
                badge = c("[permanent]", Color.DIM)
            print(f"  {nid:>5}  {name:<35} {badge} {dim(label)}")

    print(dim("\n  " + "─" * 65))
    print(dim("  hifi-suite device remove <id>  — remove a [removable] node"))

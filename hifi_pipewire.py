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


def list_audio_devices() -> List[Dict]:
    devices = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return devices
    section = None
    for line in r.stdout.splitlines():
        s = line.strip()
        if "Sinks:" in s:
            section = "sink"
        elif "Sources:" in s:
            section = "source"
        elif "Streams:" in s or s == "":
            section = None
        elif section and re.match(r"\d+\.", s):
            m = re.match(r"(\d+)\.\s+(.+?)(\s+\*)?$", s)
            if m:
                devices.append({
                    "id": m.group(1), "name": m.group(2).strip(),
                    "type": section, "is_default": m.group(3) is not None,
                })
    return devices


def find_wireless_headset() -> Optional[Dict]:
    brands = [
        "Redragon", "Logitech", "HyperX", "Razer", "SteelSeries",
        "Corsair", "Sennheiser", "Sony", "JBL", "Audio-Technica",
        "Bang", "Marshall", "Beats", "Anker", "Edifier", "XiiSound",
        "Weltrend", r"[Hh]\d{3}",
    ]
    for dev in list_audio_devices():
        for brand in brands:
            if re.search(brand, dev["name"], re.I):
                info = wpctl_inspect(dev["id"])
                dev["node_name"] = info.get("node.name", "")
                dev["device_name"] = info.get("device.product.name", dev["name"])
                return dev
    return None


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
        print("Install: yay -S virtual-surround-manager")
        print("Or: flatpak install flathub de.berny23.virtual_surround_manager")
        return False

    # Launch in background
    _run(["virtual-surround-manager", "&"])
    return True


def _restart_pw():
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])


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
        print("Option A (recommended): yay -S virtual-surround-manager")
        print("Option B: Download HRIR .sofa to ~/Resources/hrir.sofa")
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
        print("EQ .wav not found. Download from https://autoeq.app")
        print("Place at ~/.config/hifi-suite/eq.wav")
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

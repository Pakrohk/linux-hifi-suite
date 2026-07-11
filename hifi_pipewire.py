#!/usr/bin/env python3
"""PipeWire integration: wpctl-based device mgmt, filter chains, WirePlumber rules, zero-config.

Patterns inspired by danielrosehill/Claude-Pipewire-Skills-plugin.
"""

import os, re, subprocess, json
from pathlib import Path
from typing import Optional, Dict, List, Tuple

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


# ── wpctl Device Management (modern WirePlumber CLI) ──────────────────────

def wpctl_status() -> str:
    """Get wpctl status output."""
    r = _run(["wpctl", "status"])
    return r.stdout if r.returncode == 0 else ""


def wpctl_inspect(node_id: str) -> Dict[str, str]:
    """Inspect a PipeWire node for its properties."""
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
    """Get volume for a node (0.0 - 1.5)."""
    r = _run(["wpctl", "get-volume", node_id])
    if r.returncode != 0:
        return None
    m = re.search(r"Volume:\s*([\d.]+)", r.stdout)
    return float(m.group(1)) if m else None


def wpctl_set_volume(node_id: str, vol: float) -> bool:
    """Set volume (0.0 - 1.5, where 1.0 = 100%)."""
    vol = max(0.0, min(1.5, vol))
    r = _run(["wpctl", "set-volume", node_id, str(vol)])
    return r.returncode == 0


def wpctl_set_mute(node_id: str, toggle=True) -> bool:
    """Mute toggle or explicit set."""
    arg = "toggle" if toggle else "0"
    r = _run(["wpctl", "set-mute", node_id, arg])
    return r.returncode == 0


def wpctl_set_default(node_type: str, node_id: str) -> bool:
    """Set default sink or source. node_type: 'sink' or 'source'."""
    r = _run(["wpctl", "set-default", node_id])
    return r.returncode == 0


def list_audio_devices() -> List[Dict]:
    """Enumerate all sinks and sources with wpctl."""
    devices = []
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return devices

    section = None
    for line in r.stdout.splitlines():
        line_stripped = line.strip()
        if "Sinks:" in line_stripped:
            section = "sink"
            continue
        elif "Sources:" in line_stripped:
            section = "source"
            continue
        elif "Streams:" in line_stripped or line_stripped == "":
            section = None
            continue

        if section and re.match(r"\s*\d+\.", line_stripped):
            m = re.match(r"\s*(\d+)\.\s+(.+?)(\s+\*)?$", line_stripped)
            if m:
                devices.append({
                    "id": m.group(1),
                    "name": m.group(2).strip(),
                    "type": section,
                    "is_default": m.group(3) is not None,
                })
    return devices


def find_wireless_headset() -> Optional[Dict]:
    """Find wireless headset via wpctl, matching common brand patterns."""
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


# ── WirePlumber Preference Rules ──────────────────────────────────────────

def write_mic_priority_rule(node_name: str, priority: int = 2000, fallback_name: str = None, fallback_priority: int = 100) -> bool:
    """Write a WirePlumber rule to auto-prefer a microphone."""
    WP_CONF.mkdir(parents=True, exist_ok=True)
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"

    matches = f'{{ node.name = "{node_name}" }}'
    lines = [
        'monitor.alsa.rules = [',
        '  {',
        f'    matches = [ {matches} ]',
        '    actions = {',
        '      update-props = {',
        f'        priority.session = {priority}',
        f'        priority.driver  = {priority}',
        '      }',
        '    }',
        '  }',
    ]

    if fallback_name:
        fb_matches = f'{{ node.name = "{fallback_name}" }}'
        lines += [
            '  {',
            f'    matches = [ {fb_matches} ]',
            '    actions = {',
            '      update-props = {',
            f'        priority.session = {fallback_priority}',
            '      }',
            '    }',
            '  }',
        ]

    lines.append(']')
    rule_file.write_text("\n".join(lines) + "\n")
    _restart_wireplumber()
    return True


def write_mic_priority_rule_regex(pattern: str, priority: int = 2000) -> bool:
    """Write a WirePlumber rule using regex match (e.g. '~alsa_input.usb-Jabra.*')."""
    WP_CONF.mkdir(parents=True, exist_ok=True)
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"

    rule = f"""monitor.alsa.rules = [
  {{
    matches = [
      {{ node.name = "~{pattern}" }}
    ]
    actions = {{
      update-props = {{
        priority.session = {priority}
        priority.driver  = {priority}
      }}
    }}
  }}
]
"""
    rule_file.write_text(rule)
    _restart_wireplumber()
    return True


def delete_mic_priority_rule() -> bool:
    """Remove the mic priority rule."""
    rule_file = WP_CONF / "51-hifi-mic-priority.conf"
    if rule_file.exists():
        rule_file.unlink()
        _restart_wireplumber()
        return True
    return False


def list_mic_priority_rules() -> List[str]:
    """List active WirePlumber mic priority rules."""
    rules = []
    if WP_CONF.exists():
        for f in sorted(WP_CONF.glob("*.conf")):
            content = f.read_text()
            if "priority.session" in content:
                rules.append(f"{f.name}: {content[:200]}")
    return rules


def _restart_wireplumber():
    """Restart WirePlumber to apply rule changes."""
    _run(["systemctl", "--user", "restart", "wireplumber"])


# ── Combined Sink (simultaneous output) ───────────────────────────────────

def create_combined_sink(name: str, description: str, sink_patterns: List[str]) -> bool:
    """Create a PipeWire combined sink for simultaneous output to multiple devices."""
    PW_CONF.mkdir(parents=True, exist_ok=True)
    conf = PW_CONF / f"51-combine-{name}.conf"

    matches = "\n".join(f'                        {{ node.name = "{p}" }}' for p in sink_patterns)

    conf.write_text(f"""context.modules = [
  {{   name = libpipewire-module-combine-stream
      args = {{
          combine.mode = sink
          node.name    = "combined_{name}"
          node.description = "{description}"
          combine.props = {{
              audio.position = [ FL FR ]
          }}
          stream.props = {{}}
          stream.rules = [
              {{
                  matches = [
{matches}
                  ]
                  actions = {{ create-stream = {{}} }}
              }}
          ]
      }}
  }}
]
""")
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])
    return True


def delete_combined_sink(name: str) -> bool:
    """Remove a combined sink config."""
    conf = PW_CONF / f"51-combine-{name}.conf"
    if conf.exists():
        conf.unlink()
        _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])
        return True
    return False


# ── RNNoise (noise cancellation) ──────────────────────────────────────────

def _find_rnnoise_plugin() -> Optional[str]:
    """Find the RNNoise LADSPA plugin."""
    candidates = [
        "/usr/lib/ladspa/librnnoise_ladspa.so",
        "/usr/lib64/ladspa/librnnoise_ladspa.so",
        "/usr/lib/x86_64-linux-gnu/ladspa/librnnoise_ladspa.so",
        "/usr/lib/i386-linux-gnu/ladspa/librnnoise_ladspa.so",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def enable_rnnoise(threshold: float = 50.0) -> bool:
    """Enable RNNoise noise cancellation filter chain."""
    plugin = _find_rnnoise_plugin()
    if not plugin:
        print("RNNoise LADSPA plugin not found. Install: noise-suppression-for-voice")
        return False

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / "nc.conf"
    conf.write_text(f"""context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "Noise Cancelling source (RNNoise)"
            media.name       = "Noise Cancelling source"
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
                node.name    = "capture.rnnoise_source"
                node.passive = true
                audio.rate   = 48000
            }}
            playback.props = {{
                node.name    = "rnnoise_source"
                media.class  = Audio/Source
                audio.rate   = 48000
            }}
        }}
    }}
]
""")
    _run(["systemctl", "--user", "restart", "pipewire", "wireplumber"])
    return True


# ── EasyEffects Integration ───────────────────────────────────────────────

def easyeffects_running() -> bool:
    r = _run(["pgrep", "-x", "easyeffects"])
    return r.returncode == 0


def easyeffects_list_presets(preset_type: str = "input") -> List[str]:
    """List EasyEffects presets (input or output)."""
    preset_dir = EE_PRESETS / preset_type
    if not preset_dir.exists():
        return []
    return [f.stem for f in preset_dir.glob("*.json")]


def easyeffects_load_preset(name: str) -> bool:
    """Load an EasyEffects preset via CLI."""
    r = _run(["easyeffects", "--load-preset", name])
    return r.returncode == 0


def easyeffects_stop():
    _run(["systemctl", "--user", "stop", "easyeffects.service"])


def easyeffects_start():
    _run(["systemctl", "--user", "start", "easyeffects.service"])


# ── Filter Chain Management ───────────────────────────────────────────────

AVAILABLE_FILTERS = {
    "surround": "7.1 Surround Sound",
    "surround714": "7.1.4 Surround Sound",
    "nc": "RNNoise Noise Cancellation",
    "eq": "Convolution EQ",
    "ec": "Echo Cancellation",
}


def list_filters() -> Dict[str, bool]:
    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, desc in AVAILABLE_FILTERS.items():
        conf = FILTER_DIR / f"{name}.conf"
        result[name] = {"description": desc, "enabled": conf.exists(), "path": str(conf)}
    return result


def enable_filter(name: str, params: Optional[Dict] = None) -> bool:
    if name == "nc":
        return enable_rnnoise(params.get("threshold", 50.0) if params else 50.0)

    if name not in AVAILABLE_FILTERS:
        return False

    if easyeffects_running() and name in ("nc", "eq", "ec"):
        print(f"Warning: EasyEffects running — {name} may conflict.")

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / f"{name}.conf"
    template = TEMPLATE_DIR / f"{name}.conf"

    if template.exists():
        content = template.read_text()
        if params:
            for k, v in params.items():
                content = content.replace(f"<{k}>", str(v))
        conf.write_text(content)
        _run(["systemctl", "--user", "restart", "pipewire"])
        return True
    return False


def disable_filter(name: str) -> bool:
    conf = FILTER_DIR / f"{name}.conf"
    if conf.exists():
        conf.unlink()
        _run(["systemctl", "--user", "restart", "pipewire"])
        return True
    return False


# ── Auto-Configuration (zero-config) ──────────────────────────────────────

def auto_configure() -> Dict[str, str]:
    """Detect hardware and apply optimal settings. Zero-config."""
    applied = {}

    headset = find_wireless_headset()
    if headset:
        applied["headset"] = headset.get("name", "unknown")

        # Auto-enable NC if plugin available
        if _find_rnnoise_plugin():
            if enable_rnnoise():
                applied["nc"] = "enabled"

    # Check EasyEffects
    if easyeffects_running():
        applied["easyeffects"] = "running"

    return applied


# ── State Persistence ─────────────────────────────────────────────────────

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

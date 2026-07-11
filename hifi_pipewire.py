#!/usr/bin/env python3
"""PipeWire integration: dynamic filter chain management, auto-detection, zero-config."""

import os, re, subprocess, json, shutil
from pathlib import Path
from typing import Optional, Dict, List

CONF_DIR = Path.home() / ".config" / "pipewire"
FILTER_DIR = CONF_DIR / "filter-chain.conf.d"
TEMPLATE_DIR = Path("/usr/share/hifi-suite/configs")
STATE_DIR = Path.home() / ".local" / "share" / "hifi-suite"


def _env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env(), check=check)


def _run_pw(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env())


# ── Device Detection ──────────────────────────────────────────────────────

WIRELESS_PATTERNS = [
    r"[Hh]\d{3}", r"Wireless\s+headset", r"XiiSound", r"Weltrend",
    r"Redragon", r"Logitech", r"HyperX", r"Razer", r"SteelSeries",
    r"Corsair", r"Sennheiser", r"Sony", r"JBL", r"Audio-Technica",
    r"Bang", r"Marshall", r"Beats", r"Anker", r"Edifier",
]


def detect_headset() -> Optional[Dict]:
    """Detect wireless headset via aplay -l. Returns dict with card_id, name, etc."""
    try:
        r = _run(["aplay", "-l"])
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            if "card" not in line.lower():
                continue
            for pat in WIRELESS_PATTERNS:
                if re.search(pat, line, re.I):
                    m = re.search(r"card (\d+):", line, re.I)
                    if m:
                        nm = re.search(r"\[([^\]]+)\]", line)
                        return {
                            "card_id": m.group(1),
                            "name": nm.group(1) if nm else "Wireless Headset",
                            "analog": _detect_profile(m.group(1)),
                        }
        return None
    except Exception:
        return None


def _detect_profile(card_id: str) -> bool:
    try:
        r = _run(["pactl", "list", "cards"])
        inside = False
        for line in r.stdout.splitlines():
            if f"card {card_id}" in line.lower():
                inside = True
            if inside and "Active Profile:" in line:
                return "analog" in line
    except Exception:
        pass
    return False


def get_default_sink() -> Optional[str]:
    """Get the default PipeWire/Pulse sink name."""
    try:
        r = _run(["pactl", "get-default-sink"])
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


def get_sink_info(sink_name: str) -> Optional[Dict]:
    """Get sink details."""
    try:
        r = _run(["pactl", "list", "sinks"])
        if r.returncode != 0:
            return None
        inside = False
        info = {}
        for line in r.stdout.splitlines():
            if f"Name: {sink_name}" in line:
                inside = True
                continue
            if inside:
                if line.startswith("    ") or line.startswith("\t"):
                    k, _, v = line.partition(":")
                    info[k.strip()] = v.strip()
                elif line.strip() and not line.startswith(" "):
                    break
        return info if info else None
    except Exception:
        return None


# ── EasyEffects Detection ─────────────────────────────────────────────────

def easyeffects_running() -> bool:
    """Check if EasyEffects is running (it manages its own filter chains)."""
    try:
        r = _run(["pgrep", "-x", "easyeffects"])
        return r.returncode == 0
    except Exception:
        return False


def easyeffects_nodes() -> List[str]:
    """Get PipeWire nodes created by EasyEffects."""
    try:
        r = _run(["pactl", "list", "nodes", "short"])
        if r.returncode != 0:
            return []
        nodes = []
        for line in r.stdout.splitlines():
            if "easyeffects" in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    nodes.append(parts[1])
        return nodes
    except Exception:
        return []
    except Exception:
        return []


# ── Filter Chain Management ───────────────────────────────────────────────

AVAILABLE_FILTERS = {
    "surround": "7.1 Surround Sound",
    "surround714": "7.1.4 Surround Sound",
    "nc": "RNNoise Noise Cancellation",
    "eq": "Convolution EQ",
    "ec": "Echo Cancellation",
}


def list_filters() -> Dict[str, bool]:
    """List all filters and their enabled state."""
    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, desc in AVAILABLE_FILTERS.items():
        conf = FILTER_DIR / f"{name}.conf"
        result[name] = {
            "description": desc,
            "enabled": conf.exists() and conf.is_symlink(),
            "path": str(conf),
        }
    return result


def enable_filter(name: str, params: Optional[Dict] = None) -> bool:
    """Enable a PipeWire filter by installing its config."""
    if name not in AVAILABLE_FILTERS:
        return False

    # Check EasyEffects conflict
    if easyeffects_running() and name in ("nc", "eq", "ec"):
        print(f"Warning: EasyEffects is running. {name} may conflict.")
        print("Consider disabling EasyEffects or its matching feature.")

    FILTER_DIR.mkdir(parents=True, exist_ok=True)
    conf = FILTER_DIR / f"{name}.conf"

    # Try template from installed configs
    template = TEMPLATE_DIR / f"{name}.conf"
    if template.exists():
        content = template.read_text()
        if params:
            for k, v in params.items():
                content = content.replace(f"<{k}>", str(v))
        conf.write_text(content)
        return True

    # Fallback: generate minimal config
    return _generate_filter(name, conf, params)


def disable_filter(name: str) -> bool:
    """Disable a PipeWire filter by removing its config."""
    conf = FILTER_DIR / f"{name}.conf"
    if conf.exists():
        conf.unlink()
        return True
    return False


def _generate_filter(name: str, conf: Path, params: Optional[Dict] = None) -> bool:
    """Generate a minimal filter config."""
    if name == "nc":
        plugin = "/usr/lib/ladspa/librnnoise_ladspa.so"
        if not Path(plugin).exists():
            plugin = "/usr/lib64/ladspa/librnnoise_ladspa.so"
        conf.write_text(f"""context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "RNNoise"
            media.name       = "RNNoise"
            filter.graph = {{
                nodes = [
                    {{ type = ladspa
                      name = rnnoise
                      plugin = "{plugin}"
                      label  = noise_suppressor_mono
                      control = {{
                          "VAD Threshold (%)"          = 75.0
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
            }}
            playback.props = {{
                node.name    = "output.rnnoise_source"
                media.class  = Audio/Source
            }}
        }}
    }}
]
""")
        return True
    return False


# ── Auto-Configuration ────────────────────────────────────────────────────

def auto_configure(headset: Optional[Dict] = None) -> Dict[str, str]:
    """Auto-configure filters based on detected hardware. Returns applied config."""
    applied = {}

    if headset is None:
        headset = detect_headset()
    if headset is None:
        return applied

    # Always enable NC if plugin available
    nc_plugin = Path("/usr/lib/ladspa/librnnoise_ladspa.so")
    nc_plugin64 = Path("/usr/lib64/ladspa/librnnoise_ladspa.so")
    if nc_plugin.exists() or nc_plugin64.exists():
        if enable_filter("nc"):
            applied["nc"] = "enabled"

    return applied


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

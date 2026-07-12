"""State + Pure Processors — Level 2 IOP.

State = TypedDict (no classes, no inheritance)
Processors = pure functions (state → state)
Intent = implicit in function name (no Purpose enum needed)
"""
from typing import TypedDict, Optional


class State(TypedDict, total=False):
    """Single source of truth. Every processor reads/writes this."""
    device: dict
    volume: int
    error: str
    nc_enabled: bool
    eq_enabled: bool
    surround_enabled: bool
    ec_enabled: bool
    battery: dict
    devices: list
    active_filters: list
    learned_config: dict
    fingerprint: str


# ── Pure Processors ────────────────────────────────────────────────────────
# Each: State → State. No side effects. No classes. Just data in, data out.

def detect_device(s: State) -> State:
    from .device import detect_headset, compute_fingerprint
    dev = detect_headset()
    if not dev:
        return {**s, "error": "No headset detected. Connect a headset."}
    return {**s, "device": dev, "fingerprint": compute_fingerprint(dev)}


def identify_device(s: State) -> State:
    dev = s.get("device")
    if not dev:
        return s
    return {
        **s,
        "device_name": dev.get("device_name", "Unknown"),
        "bus": dev.get("bus", "unknown"),
        "form_factor": dev.get("form_factor", "unknown"),
    }


def check_battery(s: State) -> State:
    if s.get("error") or not s.get("device"):
        return s
    from .audio import get_battery
    bat = get_battery(s["device"])
    return {**s, "battery": bat} if bat else s


def list_devices(s: State) -> State:
    from .device import list_all_devices
    return {**s, "devices": list_all_devices()}


def learn_device(s: State) -> State:
    fp = s.get("fingerprint", "")
    if not fp:
        return s
    from .audio import LearningDB
    db = LearningDB()
    lesson = db.get(fp)
    dev = s.get("device", {})
    if lesson:
        return {**s, "learned_config": lesson}
    similar = db.find_similar(dev)
    if similar:
        return {**s, "learned_config": similar}
    return {**s, "learned_config": _smart_defaults(dev)}


def apply_learned(s: State) -> State:
    cfg = s.get("learned_config", {})
    if not cfg:
        return s
    out = dict(s)
    for name in cfg.get("successful_filters", []):
        key = f"{name.lower()}_enabled"
        out[key] = True
    return out


def smart_defaults(s: State) -> State:
    if s.get("error"):
        return s
    out = dict(s)
    has_caps = any(k.endswith("_enabled") for k in out if k != "error")
    if not has_caps:
        out["nc_enabled"] = True
        from .audio import vsm_installed, find_eq_wav
        if vsm_installed():
            out["surround_enabled"] = True
        if find_eq_wav():
            out["eq_enabled"] = True
    return out


def enable_nc(s: State) -> State:
    if s.get("error") or not s.get("nc_enabled"):
        return s
    from .audio import find_rnnoise, render_nc, FilterManager
    plugin = find_rnnoise()
    if not plugin:
        return {**s, "error": "RNNoise not found. Install: noise-suppression-for-voice"}
    from .audio import find_physical_mic
    mic = find_physical_mic()
    mic_node = mic["node_name"] if mic else ""
    config = render_nc(plugin, mic_node=mic_node)
    ok = FilterManager().load("nc", config)
    return s if ok else {**s, "error": "Failed to load NC filter"}


def enable_eq(s: State) -> State:
    if s.get("error") or not s.get("eq_enabled"):
        return s
    from .audio import find_eq_wav, render_eq, FilterManager
    wav = find_eq_wav()
    if not wav:
        return {**s, "error": "EQ WAV not found. Download from https://autoeq.app"}
    ok = FilterManager().load("eq", render_eq(wav))
    return s if ok else {**s, "error": "Failed to load EQ filter"}


def enable_surround(s: State) -> State:
    if s.get("error") or not s.get("surround_enabled"):
        return s
    from .audio import vsm_installed, launch_vsm, find_sofa, render_surround, FilterManager
    if vsm_installed():
        launch_vsm()
        return s
    sofa = find_sofa()
    if not sofa:
        return {**s, "error": "No surround: install virtual-surround-manager or download HRIR .sofa"}
    ok = FilterManager().load("surround", render_surround(sofa))
    return s if ok else {**s, "error": "Failed to load surround filter"}


def enable_ec(s: State) -> State:
    if s.get("error") or not s.get("ec_enabled"):
        return s
    from .audio import find_physical_mic, render_ec, FilterManager
    mic = find_physical_mic()
    if not mic:
        return {**s, "error": "No physical microphone found"}
    dev = s.get("device", {})
    out_node = dev.get("node_name", "")
    if not out_node:
        return {**s, "error": "No output node for echo cancellation"}
    ok = FilterManager().load("ec", render_ec(mic["node_name"], out_node))
    return s if ok else {**s, "error": "Failed to load EC filter"}


def disable_filter(s: State) -> State:
    effect = s.get("effect_to_disable", "")
    if not effect:
        return s
    from .audio import FilterManager
    FilterManager().unload(effect)
    return {**s, f"{effect}_enabled": False}


def set_volume(s: State) -> State:
    vol = s.get("volume")
    dev = s.get("device")
    if vol is None or not dev:
        return s
    from .audio import wpctl_set_volume
    ok = wpctl_set_volume(dev["id"], vol / 100.0)
    return s if ok else {**s, "error": "Failed to set volume"}


def get_volume(s: State) -> State:
    dev = s.get("device")
    if not dev:
        return s
    from .audio import wpctl_get_volume
    vol = wpctl_get_volume(dev["id"])
    return {**s, "volume": int(vol * 100)} if vol else s


def set_default(s: State) -> State:
    dev = s.get("device")
    if not dev:
        return s
    from .audio import wpctl_set_default
    wpctl_set_default(dev["id"])
    return s


def get_effects(s: State) -> State:
    from .audio import FilterManager
    fm = FilterManager()
    return {**s, "active_filters": fm.list_active()}


def record_outcome(s: State) -> State:
    """After-hook: record success/failure for learning."""
    fp = s.get("fingerprint", "")
    if not fp:
        return s
    from .audio import LearningDB
    db = LearningDB()
    dev = s.get("device")
    if s.get("error"):
        for key in ("nc_enabled", "eq_enabled", "surround_enabled", "ec_enabled"):
            if key in s:
                db.record_failure(fp, key.replace("_enabled", ""), s["error"], device=dev)
    else:
        for key in ("nc_enabled", "eq_enabled", "surround_enabled", "ec_enabled"):
            if s.get(key):
                db.record_success(fp, key.replace("_enabled", ""), device=dev)
    return s


def _smart_defaults(dev: dict) -> dict:
    from .audio import vsm_installed, find_eq_wav
    defaults = ["NC"]
    if vsm_installed():
        defaults.append("SURROUND")
    if find_eq_wav():
        defaults.append("EQ")
    return {"successful_filters": {f: {} for f in defaults}, "from_defaults": True}

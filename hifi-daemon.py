#!/usr/bin/env python3
"""Unified audio daemon: wpctl-based volume control + PCM sync for wireless headsets."""

import socket, os, sys, signal, time, json, re, subprocess, logging
from pathlib import Path
from typing import Optional, Set

LOG_DIR = Path.home() / ".local" / "share" / "hifi-suite"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = LOG_DIR / "volume_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "daemon.log"), logging.StreamHandler()],
)
log = logging.getLogger("hifi-daemon")


def _env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env())


# ── Headset Detection (uses hifi_pipewire module) ─────────────────────────

def _detect_headset():
    """Detect headset using PipeWire device properties (form-factor, bus, brand)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from hifi_pipewire import detect_headset
        return detect_headset()
    except ImportError:
        return _detect_headset_fallback()


def _detect_headset_fallback():
    """Fallback detection if hifi_pipewire is not importable."""
    import re as _re
    r = _run(["wpctl", "status"])
    if r.returncode != 0:
        return None

    section = None
    for line in r.stdout.splitlines():
        stripped = line.strip()
        if "Sinks:" in stripped:
            section = "sink"
            continue
        elif "Sources:" in stripped or "Streams:" in stripped or stripped == "":
            section = None
            continue

        if section == "sink" and _re.match(r"\d+\.", stripped):
            m = _re.match(r"(\d+)\.\s+(.+?)(\s+\*)?$", stripped)
            if m:
                # Check form-factor via wpctl inspect
                info = _run(["wpctl", "inspect", m.group(1)])
                if info.returncode == 0:
                    if 'device.form-factor = "headset"' in info.stdout:
                        nm = _re.search(r'node\.name\s*=\s*"([^"]+)"', info.stdout)
                        return {
                            "id": m.group(1),
                            "name": m.group(2).strip(),
                            "node_name": nm.group(1) if nm else "",
                            "device_name": m.group(2).strip(),
                            "form_factor": "headset",
                        }
    return None


def _get_battery():
    """Get battery level of detected headset."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from hifi_pipewire import get_battery_level
        return get_battery_level()
    except ImportError:
        return None


# ── AudioDevice ───────────────────────────────────────────────────────────

class AudioDevice:
    """Wraps wpctl for modern PipeWire volume/device management."""

    def __init__(self):
        self.sink_id: Optional[str] = None
        self.device_name: str = "Headset"
        self.node_name: str = ""
        self.bus: str = ""
        self.form_factor: str = ""
        self.last_set = 0.0
        self.debounce = 0.5
        self.battery: Optional[dict] = None

    def detect(self) -> bool:
        """Find headset using PipeWire properties (form-factor, bus, brand)."""
        headset = _detect_headset()
        if headset:
            self.sink_id = headset.get("id", "")
            self.device_name = headset.get("device_name", headset.get("name", "Headset"))
            self.node_name = headset.get("node_name", "")
            self.bus = headset.get("bus", "")
            self.form_factor = headset.get("form_factor", "")
            log.info("Detected: %s (id %s, bus=%s, form=%s)",
                     self.device_name, self.sink_id, self.bus, self.form_factor)
            # Check battery
            self.battery = _get_battery()
            if self.battery:
                log.info("Battery: %d%% (%s)", self.battery["level"], self.battery["method"])
            return True
        return False

    def get_volume(self) -> Optional[float]:
        if not self.sink_id:
            return None
        r = _run(["wpctl", "get-volume", self.sink_id])
        if r.returncode != 0:
            return None
        m = re.search(r"Volume:\s*([\d.]+)", r.stdout)
        return float(m.group(1)) if m else None

    def set_volume(self, vol: int, silent=False) -> bool:
        if not self.sink_id or not 0 <= vol <= 100:
            return False
        wp_vol = vol / 100.0
        r = _run(["wpctl", "set-volume", self.sink_id, str(wp_vol)])
        if r.returncode == 0:
            self.last_set = time.time()
            self._save_state(vol)
            return True
        return False

    def toggle_mute(self) -> bool:
        if not self.sink_id:
            return False
        r = _run(["wpctl", "set-mute", self.sink_id, "toggle"])
        return r.returncode == 0

    def set_default(self) -> bool:
        if not self.sink_id:
            return False
        r = _run(["wpctl", "set-default", self.sink_id])
        return r.returncode == 0

    def should_debounce(self):
        return (time.time() - self.last_set) < self.debounce

    def _save_state(self, vol):
        try:
            STATE_FILE.write_text(json.dumps({
                "volume": vol, "device": self.device_name,
                "sink_id": self.sink_id, "node_name": self.node_name,
                "bus": self.bus, "form_factor": self.form_factor,
                "battery": self.battery, "ts": time.time(),
            }))
        except Exception:
            pass

    def load_state(self) -> Optional[int]:
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text()).get("volume")
        except Exception:
            pass
        return None


# ── Daemon ────────────────────────────────────────────────────────────────

class Daemon:
    def __init__(self):
        self.running = True
        self.dev = AudioDevice()
        self.vol_before_mute = None
        self.sock_path = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/hifi-suite.sock"
        self.err_count = 0
        self.last_device_ids: Set[str] = set()
        self.poll_counter = 0
        self.poll_interval = 3  # check every 3 seconds

    def _handle(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERR: empty"
        c = parts[0]

        if c == "scan":
            # Force re-detection
            self.dev.sink_id = None
            if self.dev.detect():
                return (f"OK: device={self.dev.device_name} id={self.dev.sink_id} "
                        f"bus={self.dev.bus} form={self.dev.form_factor}")
            return "ERR: no headset found"

        if c == "battery":
            bat = _get_battery()
            if bat:
                return f"OK: level={bat['level']} charging={bat['charging']} method={bat['method']}"
            return "ERR: no battery info available"

        if c == "devices":
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from hifi_pipewire import list_all_devices
                devs = list_all_devices()
                lines = []
                for d in devs:
                    bus = d.get("bus", "?")
                    ff = d.get("form_factor", "")
                    extra = f" [{bus}]" if bus and bus != "?" else ""
                    if ff:
                        extra += f" ({ff})"
                    default = " *" if d.get("is_default") else ""
                    lines.append(f"{d['id']}. {d['name']}{extra}{default}")
                return "OK: " + "; ".join(lines) if lines else "ERR: no devices"
            except ImportError:
                return "ERR: module not found"

        if not self.dev.sink_id:
            if not self.dev.detect():
                return "ERR: no headset"

        if c == "set" and len(parts) == 2:
            try:
                vol = int(parts[1])
            except ValueError:
                return "ERR: bad volume"
            if self.dev.set_volume(vol, silent=True):
                return f"OK: {vol}"
            self.dev.sink_id = None
            if self.dev.detect() and self.dev.set_volume(vol, silent=True):
                return f"OK: {vol}"
            return "ERR: set failed"

        if c == "get":
            vol = self.dev.get_volume()
            if vol is None:
                return "ERR: read failed"
            pct = int(vol * 100)
            return f"OK: {pct}"

        if c == "status":
            vol = self.dev.get_volume()
            pct = int(vol * 100) if vol else "?"
            bat = ""
            if self.dev.battery:
                bat = f" battery={self.dev.battery['level']}%"
            return (f"OK: device={self.dev.device_name} id={self.dev.sink_id} "
                    f"node={self.dev.node_name} bus={self.dev.bus} "
                    f"volume={pct}%{bat}")

        if c == "mute":
            vol = self.dev.get_volume()
            if vol is None:
                return "ERR: read failed"
            if vol == 0:
                restore = self.vol_before_mute or 0.5
                self.dev.set_volume(int(restore * 100), silent=True)
                self.vol_before_mute = None
                return f"OK: unmuted {int(restore * 100)}"
            self.vol_before_mute = vol
            self.dev.set_volume(0, silent=True)
            return "OK: muted"

        if c == "default":
            if self.dev.set_default():
                return f"OK: default={self.dev.device_name}"
            return "ERR: set default failed"

        if c == "ping":
            return "OK: pong"

        return f"ERR: unknown '{c}'"

    def _poll_devices(self):
        """Check for device connect/disconnect events."""
        try:
            r = _run(["wpctl", "status"])
            if r.returncode != 0:
                return

            current_ids: Set[str] = set()
            for line in r.stdout.splitlines():
                # Strip box-drawing chars and optional * prefix
                stripped = re.sub(r"[\s│├└─]+", " ", line).strip()
                m = re.match(r"\*?\s*(\d+)\.\s+", stripped)
                if m:
                    current_ids.add(m.group(1))

            added = current_ids - self.last_device_ids
            removed = self.last_device_ids - current_ids

            if added or removed:
                for dev_id in added:
                    log.info("Device connected: id=%s", dev_id)
                for dev_id in removed:
                    log.info("Device disconnected: id=%s", dev_id)

                # Re-detect headset if current one was removed or new one added
                if not self.dev.sink_id or self.dev.sink_id in removed or added:
                    old_name = self.dev.device_name
                    self.dev.sink_id = None
                    if self.dev.detect():
                        log.info("Headset changed: %s -> %s",
                                 old_name, self.dev.device_name)
                        restored = self.dev.load_state()
                        if restored is not None:
                            self.dev.set_volume(restored, silent=True)
                            log.info("Restored volume: %d%%", restored)
                    elif self.dev.sink_id in removed:
                        log.info("Headset disconnected")

            self.last_device_ids = current_ids
        except Exception as e:
            log.error("Poll error: %s", e)

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))

        if os.path.exists(self.sock_path):
            os.unlink(self.sock_path)

        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self.sock_path)
        srv.listen(5)
        srv.settimeout(1.0)
        os.chmod(self.sock_path, 0o600)

        if not self.dev.detect():
            log.warning("No headset on startup, will auto-detect")
        else:
            restored = self.dev.load_state()
            if restored is not None:
                self.dev.set_volume(restored, silent=True)
                log.info("Restored volume: %d%%", restored)

        # Initialize device ID tracking
        try:
            r = _run(["wpctl", "status"])
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    stripped = re.sub(r"[\s│├└─]+", " ", line).strip()
                    m = re.match(r"\*?\s*(\d+)\.\s+", stripped)
                    if m:
                        self.last_device_ids.add(m.group(1))
        except Exception:
            pass

        log.info("Daemon started, socket: %s", self.sock_path)
        while self.running:
            try:
                try:
                    cli, _ = srv.accept()
                    data = cli.recv(1024).decode().strip()
                    if data:
                        cli.sendall(self._handle(data).encode())
                    cli.close()
                except socket.timeout:
                    pass

                # Poll for device changes
                self.poll_counter += 1
                if self.poll_counter >= self.poll_interval:
                    self.poll_counter = 0
                    self._poll_devices()

            except Exception as e:
                log.error("Socket error: %s", e)

        srv.close()
        if os.path.exists(self.sock_path):
            os.unlink(self.sock_path)
        log.info("Daemon stopped")


if __name__ == "__main__":
    d = Daemon()
    try:
        d.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error("Fatal: %s", e, exc_info=True)
        sys.exit(1)

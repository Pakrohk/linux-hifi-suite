#!/usr/bin/env python3
"""Unified audio daemon: wpctl-based volume control + PCM sync for wireless headsets."""

import socket, os, sys, signal, time, json, re, subprocess, logging
from pathlib import Path
from typing import Tuple, Optional

LOG_DIR = Path.home() / ".local" / "share" / "hifi-suite"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = LOG_DIR / "volume_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "daemon.log"), logging.StreamHandler()],
)
log = logging.getLogger("hifi-daemon")

BRANDS = [
    r"Redragon", r"Logitech", r"HyperX", r"Razer", r"SteelSeries",
    r"Corsair", r"Sennheiser", r"Sony", r"JBL", r"Audio-Technica",
    r"Bang", r"Marshall", r"Beats", r"Anker", r"Edifier",
    r"XiiSound", r"Weltrend", r"[Hh]\d{3}",
]


def _env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env())


class AudioDevice:
    """Wraps wpctl for modern PipeWire volume/device management."""

    def __init__(self):
        self.sink_id: Optional[str] = None
        self.device_name: str = "Headset"
        self.node_name: str = ""
        self.last_set = 0.0
        self.debounce = 0.5

    def detect(self) -> bool:
        """Find wireless headset via wpctl."""
        r = _run(["wpctl", "status"])
        if r.returncode != 0:
            return False

        section = None
        for line in r.stdout.splitlines():
            stripped = line.strip()
            if "Sinks:" in stripped:
                section = "sink"
                continue
            elif "Sources:" in stripped or "Streams:" in stripped or stripped == "":
                section = None
                continue

            if section == "sink" and re.match(r"\d+\.", stripped):
                m = re.match(r"(\d+)\.\s+(.+?)(\s+\*)?$", stripped)
                if m:
                    for brand in BRANDS:
                        if re.search(brand, m.group(2), re.I):
                            self.sink_id = m.group(1)
                            self.device_name = m.group(2).strip()
                            # Get stable node.name
                            inspect = _run(["wpctl", "inspect", self.sink_id])
                            if inspect.returncode == 0:
                                nm = re.search(r'node\.name\s*=\s*"([^"]+)"', inspect.stdout)
                                if nm:
                                    self.node_name = nm.group(1)
                            log.info("Detected: %s (id %s)", self.device_name, self.sink_id)
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
        # wpctl uses 0.0-1.5 scale
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
                "sink_id": self.sink_id, "ts": time.time(),
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


class Daemon:
    def __init__(self):
        self.running = True
        self.dev = AudioDevice()
        self.vol_before_mute = None
        self.sock_path = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/hifi-suite.sock"
        self.err_count = 0

    def _handle(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERR: empty"
        c = parts[0]

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
            return (f"OK: device={self.dev.device_name} id={self.dev.sink_id} "
                    f"node={self.dev.node_name} volume={pct}%")

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

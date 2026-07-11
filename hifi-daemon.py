#!/usr/bin/env python3
"""Unified audio daemon: volume sync + socket control for wireless headsets."""

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

DEVICE_PATTERNS = [
    r"[Hh]\d{3}", r"Wireless\s+headset", r"XiiSound", r"Weltrend",
    r"Redragon", r"Logitech", r"HyperX", r"Razer", r"SteelSeries",
    r"Corsair", r"Sennheiser", r"Sony", r"JBL", r"Audio-Technica",
]


def _lc_env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, env=_lc_env())


class Headset:
    def __init__(self):
        self.card_id: Optional[str] = None
        self.device_name: str = "Headset"
        self.analog: bool = False
        self.last_set = 0.0
        self.debounce = 0.5

    def detect(self) -> bool:
        try:
            r = _run(["aplay", "-l"])
            if r.returncode != 0:
                return False
            for line in r.stdout.splitlines():
                if "card" not in line.lower():
                    continue
                for pat in DEVICE_PATTERNS:
                    if re.search(pat, line, re.I):
                        m = re.search(r"card (\d+):", line, re.I)
                        if m:
                            self.card_id = m.group(1)
                            nm = re.search(r"\[([^\]]+)\]", line)
                            self.device_name = nm.group(1) if nm else "Headset"
                            self._detect_profile()
                            log.info("Detected: %s (card %s)", self.device_name, self.card_id)
                            return True
            return False
        except Exception:
            return False

    def _detect_profile(self):
        try:
            r = _run(["pactl", "list", "cards"])
            inside = False
            for line in r.stdout.splitlines():
                if any(p in line for p in ["XiiSound", "Weltrend", "Redragon", self.device_name]):
                    inside = True
                if inside and "Active Profile:" in line:
                    self.analog = "analog" in line
                    return
        except Exception:
            pass

    def get_volumes(self) -> Tuple[Optional[int], Optional[int]]:
        if not self.card_id:
            return None, None
        try:
            r = _run(["amixer", "-c", self.card_id, "contents"])
            if r.returncode != 0:
                return None, None
            v1 = v2 = None
            lines = r.stdout.splitlines()
            for i, line in enumerate(lines):
                if "name='PCM Playback Volume'" not in line:
                    continue
                if i + 2 < len(lines) and "values=" in lines[i + 2]:
                    m = re.search(r"values=(.+)", lines[i + 2])
                    if m:
                        val = int(m.group(1).strip().split(",")[0])
                        if "index=1" in line:
                            v2 = val
                        else:
                            v1 = val
            return v1, v2
        except Exception:
            return None, None

    def set_volume(self, vol: int, silent=False) -> bool:
        if not self.card_id or not 0 <= vol <= 100:
            return False
        try:
            if self.analog:
                _run(["amixer", "-c", self.card_id, "set", "PCM", "100%"])
                _run(["amixer", "-c", self.card_id, "cset", "numid=10", str(vol)])
            else:
                _run(["amixer", "-c", self.card_id, "set", "PCM", f"{vol}%"])
                _run(["amixer", "-c", self.card_id, "cset", "numid=10", str(vol)])
            self.last_set = time.time()
            self._save_state(vol)
            return True
        except Exception:
            return False

    def sync_from_master(self) -> bool:
        v1, v2 = self.get_volumes()
        if v1 is None or v1 == v2:
            return False
        try:
            _run(["amixer", "-c", self.card_id, "cset", "numid=10", str(v1)])
            self.last_set = time.time()
            return True
        except Exception:
            return False

    def should_debounce(self):
        return (time.time() - self.last_set) < self.debounce

    def _save_state(self, vol):
        try:
            STATE_FILE.write_text(json.dumps({
                "volume": vol, "device": self.device_name,
                "card": self.card_id, "ts": time.time(),
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
        self.hs = Headset()
        self.vol_before_mute = None
        self.sock_path = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/hifi-suite.sock"
        self.err_count = 0

    def _handle(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERR: empty"
        c = parts[0]

        if not self.hs.card_id:
            if not self.hs.detect():
                return "ERR: no headset"

        if c == "set" and len(parts) == 2:
            try:
                vol = int(parts[1])
            except ValueError:
                return "ERR: bad volume"
            if self.hs.set_volume(vol, silent=True):
                return f"OK: {vol}"
            self.hs.card_id = None
            if self.hs.detect() and self.hs.set_volume(vol, silent=True):
                return f"OK: {vol}"
            return "ERR: set failed"

        if c == "get":
            v1, v2 = self.hs.get_volumes()
            if v1 is None:
                return "ERR: read failed"
            eff = v2 if self.hs.analog else v1
            return f"OK: {eff}"

        if c == "status":
            v1, v2 = self.hs.get_volumes()
            return f"OK: device={self.hs.device_name} card={self.hs.card_id} v1={v1} v2={v2} analog={self.hs.analog}"

        if c == "mute":
            v1, v2 = self.hs.get_volumes()
            if v1 is None:
                return "ERR: read failed"
            cur = v2 if self.hs.analog else v1
            if cur == 0:
                vol = self.vol_before_mute or 50
                self.hs.set_volume(vol, silent=True)
                self.vol_before_mute = None
                return f"OK: unmuted {vol}"
            self.vol_before_mute = cur
            self.hs.set_volume(0, silent=True)
            return "OK: muted"

        if c == "ping":
            return "OK: pong"

        return f"ERR: unknown '{c}'"

    def _sync_loop(self):
        if self.hs.should_debounce():
            return
        if not self.hs.card_id:
            if not self.hs.detect():
                self.err_count += 1
                return
            self.err_count = 0
        v1, v2 = self.hs.get_volumes()
        if v1 is None:
            self.err_count += 1
            if self.err_count >= 3:
                self.hs.card_id = None
                self.err_count = 0
            return
        self.err_count = 0
        if not self.hs.analog and v1 != v2:
            self.hs.sync_from_master()

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

        if not self.hs.detect():
            log.warning("No headset on startup, will auto-detect")
        else:
            restored = self.hs.load_state()
            if restored is not None:
                self.hs.set_volume(restored, silent=True)
                log.info("Restored volume: %d%%", restored)

        log.info("Daemon started, socket: %s", self.sock_path)
        tick = 0
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
            tick += 1
            if tick % 2 == 0:
                self._sync_loop()

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

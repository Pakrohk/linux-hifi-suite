#!/usr/bin/env python3
"""HiFi Suite Daemon — uses state processors, not pipeline class."""
import socket, os, signal, time, json, logging, sys

from .state import State
from .pipeline import run
from . import state as s

LOG_DIR = os.path.expanduser("~/.local/share/hifi-suite")
os.makedirs(LOG_DIR, exist_ok=True)
STATE_FILE = os.path.join(LOG_DIR, "volume_state.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(os.path.join(LOG_DIR, "daemon.log")),
                              logging.StreamHandler()])
log = logging.getLogger("hifi-daemon")


class Daemon:
    def __init__(self):
        self.running = True
        self.state: State = {}
        self.sock_path = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/hifi-suite.sock"
        self.poll_counter = 0
        self.poll_interval = 3

    def _detect(self) -> bool:
        st = run({}, s.detect_device, s.identify_device)
        if st.get("error"):
            return False
        self.state = st
        return True

    def _handle(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERR: empty"
        c = parts[0]

        if c == "scan":
            self.state = {}
            if self._detect():
                dev = self.state["device"]
                return f"OK: device={dev.get('device_name')} id={dev['id']} bus={dev.get('bus')}"
            return "ERR: no headset found"

        if c == "battery":
            st = run(self.state, s.check_battery)
            bat = st.get("battery")
            return f"OK: level={bat['level']} charging={bat['charging']}" if bat else "ERR: no battery"

        if c == "devices":
            st = run({}, s.list_devices)
            devs = st.get("devices", [])
            lines = [f"{d['id']}. {d['name']} [{d.get('bus', '?')}]" for d in devs]
            return "OK: " + "; ".join(lines) if lines else "ERR: no devices"

        if not self.state.get("device"):
            if not self._detect():
                return "ERR: no headset"

        if c == "set" and len(parts) == 2:
            try:
                vol = int(parts[1])
            except ValueError:
                return "ERR: bad volume"
            st = run({**self.state, "volume": vol}, s.set_volume)
            return f"OK: {vol}" if not st.get("error") else "ERR: set failed"

        if c == "get":
            st = run(self.state, s.get_volume)
            return f"OK: {st.get('volume', '?')}"

        if c == "status":
            st = run(self.state, s.get_volume, s.check_battery)
            bat = st.get("battery")
            bat_str = f" battery={bat['level']}%" if bat else ""
            return (f"OK: device={self.state['device'].get('device_name', '?')} "
                    f"id={self.state['device']['id']} "
                    f"volume={st.get('volume', '?')}%{bat_str}")

        if c == "mute":
            from .audio import wpctl_get_volume, wpctl_set_volume
            vol = wpctl_get_volume(self.state["device"]["id"])
            if vol is None:
                return "ERR: read failed"
            if vol == 0:
                saved = self._load_vol()
                wpctl_set_volume(self.state["device"]["id"], (saved or 50) / 100.0)
                return f"OK: unmuted {saved or 50}"
            self._save_vol(int(vol * 100))
            wpctl_set_volume(self.state["device"]["id"], 0)
            return "OK: muted"

        if c == "default":
            run(self.state, s.set_default)
            return f"OK: default={self.state['device'].get('device_name', '?')}"

        if c == "ping":
            return "OK: pong"

        return f"ERR: unknown '{c}'"

    def _poll(self):
        from .device import list_sinks, wpctl_inspect
        devices = list_sinks()
        has_headset = any(
            wpctl_inspect(d["id"]).get("device.form-factor", "") == "headset"
            for d in devices
        ) if devices else False

        if has_headset and not self.state.get("device"):
            if self._detect():
                saved = self._load_vol()
                if saved is not None:
                    from .audio import wpctl_set_volume
                    wpctl_set_volume(self.state["device"]["id"], saved / 100.0)
                    log.info("Restored volume: %d%%", saved)
        elif not has_headset and self.state.get("device"):
            log.info("Headset disconnected")
            self.state = {}

    def _save_vol(self, vol: int):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"volume": vol, "ts": time.time()}, f)
        except Exception:
            pass

    def _load_vol(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    return json.load(f).get("volume")
        except Exception:
            pass
        return None

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

        if self._detect():
            saved = self._load_vol()
            if saved is not None:
                from .audio import wpctl_set_volume
                wpctl_set_volume(self.state["device"]["id"], saved / 100.0)

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
                self.poll_counter += 1
                if self.poll_counter >= self.poll_interval:
                    self.poll_counter = 0
                    self._poll()
            except Exception as e:
                log.error("Socket error: %s", e)
        srv.close()
        if os.path.exists(self.sock_path):
            os.unlink(self.sock_path)
        log.info("Daemon stopped")


def main():
    d = Daemon()
    try:
        d.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error("Fatal: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Shared utilities — minimal."""
import os, subprocess
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "share" / "hifi-suite"
LEARNING_DIR = STATE_DIR / "learning"
PW_CONF = Path.home() / ".config" / "pipewire"
CUSTOM_PROFILES = PW_CONF / "hifi-suite"


def _env():
    e = os.environ.copy()
    e["LC_ALL"] = "C"
    e["LANG"] = "C"
    return e


def _run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env(), check=check)

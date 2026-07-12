#!/usr/bin/env python3
"""HiFi Suite CLI — thin Typer interface. All logic in state.py processors."""
import sys
from typing import Optional
from enum import Enum

import typer

from .state import State
from .pipeline import run
from . import state as s

app = typer.Typer(name="hifi-suite", help="Zero-config audio suite for Linux headsets",
                  no_args_is_help=True, add_completion=False)
vol_app = typer.Typer(help="Volume control", no_args_is_help=True)
dev_app = typer.Typer(help="Device management", no_args_is_help=True)
eff_app = typer.Typer(help="Audio effects", no_args_is_help=True)
prof_app = typer.Typer(help="Headset profiles", no_args_is_help=True)
daemon_app = typer.Typer(help="Daemon management", no_args_is_help=True)
app.add_typer(vol_app, name="vol")
app.add_typer(dev_app, name="device")
app.add_typer(eff_app, name="effect")
app.add_typer(prof_app, name="profile")
app.add_typer(daemon_app, name="daemon")


# ── Helpers ────────────────────────────────────────────────────────────────

def _detect() -> State:
    return run({}, s.detect_device, s.identify_device, s.check_battery)


def _ok(st: State) -> bool:
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        return False
    return True


# ── Top-level Commands ─────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        from .audio import print_banner
        print_banner()
        typer.echo(ctx.parent.get_help() if ctx.parent else ctx.get_help())


@app.command()
def status():
    """Show device and effects status."""
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    from .audio import print_status, print_effects, wpctl_get_volume
    vol = wpctl_get_volume(st["device"]["id"])
    print_status(st["device"], vol, st.get("battery"))
    print_effects()


@app.command()
def scan():
    """Force re-detection of headset."""
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    dev = st["device"]
    typer.echo(f"Detected: {dev.get('device_name', 'Unknown')} (id={dev['id']}, bus={dev.get('bus')})")


@app.command()
def auto():
    """Auto-detect and configure everything."""
    from .audio import print_banner, bold, c, Color, device_icon
    print_banner()
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    dev = st["device"]
    typer.echo(f"  {c('Headset:', Color.CYAN)}     {bold(dev.get('device_name', 'Unknown'))}")
    typer.echo(f"  {c('Connection:', Color.CYAN)} {device_icon(dev.get('bus', '?'))} {dev.get('bus', '?')}")
    if st.get("battery"):
        bat = st["battery"]
        color = Color.GREEN if bat["level"] > 50 else Color.YELLOW if bat["level"] > 20 else Color.RED
        typer.echo(f"  {c('Battery:', Color.CYAN)}    {c(str(bat['level']) + '%', color)}")
    typer.echo()
    # Full auto pipeline
    st = run(st, s.learn_device, s.apply_learned, s.smart_defaults,
             s.enable_nc, s.enable_eq, s.enable_surround, s.enable_ec,
             after=s.record_outcome)
    if st.get("error"):
        typer.echo(f"  Error: {st['error']}")
        raise typer.Exit(1)
    typer.echo(bold("  Configured:"))
    for key in ("nc_enabled", "eq_enabled", "surround_enabled", "ec_enabled"):
        if st.get(key):
            typer.echo(f"  {success('[ON]')} {bold(key.replace('_enabled', '').upper())}")
    typer.echo()
    _daemon_action("start")
    typer.echo(dim("  Tip: Use 'hifi-suite device select' to manage devices interactively"))


@app.command(name="setup")
def setup_cmd():
    """Same as auto."""
    auto()


@app.command()
def effects():
    """List effects and status."""
    from .audio import print_effects as pe
    pe()


@app.command(name="select")
def select_device():
    """Interactive device selector."""
    from .audio import print_device_table, c, Color, bold
    st = run({}, s.list_devices)
    devs = st.get("devices", [])
    if not devs:
        typer.echo(c("  No audio devices found.", Color.YELLOW))
        raise typer.Exit(1)
    print_device_table(devs)
    try:
        choice = typer.prompt("  Select device number (q to quit)")
    except (EOFError, KeyboardInterrupt):
        return
    if choice.strip().lower() == "q":
        return
    try:
        idx = int(choice.strip()) - 1
        dev = devs[idx]
    except (ValueError, IndexError):
        typer.echo(c("  Invalid selection.", Color.RED))
        return
    typer.echo(f"  Selected: {bold(dev.get('name', '?'))}")


@app.command()
def default():
    """Set headset as default output."""
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    run(st, s.set_default)
    typer.echo(f"Default: {st['device'].get('device_name', 'Unknown')}")


@app.command()
def recommend(name: Optional[str] = typer.Argument(None)):
    """Show download recommendations."""
    from .audio import get_profile
    if not name:
        st = _detect()
        if st.get("error"):
            typer.echo("No headset detected. Usage: hifi-suite recommend <name>")
            raise typer.Exit(1)
        name = st["device"].get("device_name", "Unknown")
        typer.echo(f"Detected: {name}")
    p = get_profile(name)
    typer.echo(f"\nRecommended files for: {name}")
    typer.echo(f"  EQ: {p.get('eq_url', 'https://autoeq.app')}")
    typer.echo(f"  SOFA: {p.get('sofa_url', 'http://sofacoustics.org/data')}")


# ── Volume Subcommands ─────────────────────────────────────────────────────

@vol_app.callback(invoke_without_command=True)
def vol_cb(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@vol_app.command(name="get")
def vol_get():
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    st = run(st, s.get_volume)
    typer.echo(f"{st.get('volume', '?')}%")


@vol_app.command(name="set")
def vol_set(value: int = typer.Argument(..., help="Volume 0-100")):
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    st = run({**st, "volume": value}, s.set_volume)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)


@vol_app.command(name="mute")
def vol_mute():
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    from .audio import wpctl_set_mute
    wpctl_set_mute(st["device"]["id"])


@vol_app.command(name="up")
def vol_up(amount: int = typer.Argument(5)):
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    from .audio import wpctl_get_volume, wpctl_set_volume
    cur = wpctl_get_volume(st["device"]["id"])
    if cur is not None:
        wpctl_set_volume(st["device"]["id"], min(1.0, cur + amount / 100.0))


@vol_app.command(name="down")
def vol_down(amount: int = typer.Argument(5)):
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    from .audio import wpctl_get_volume, wpctl_set_volume
    cur = wpctl_get_volume(st["device"]["id"])
    if cur is not None:
        wpctl_set_volume(st["device"]["id"], max(0.0, cur - amount / 100.0))


# ── Device Subcommands ─────────────────────────────────────────────────────

@dev_app.command(name="list")
def dev_list(detail: bool = typer.Option(False, "--detail", "-d")):
    from .audio import print_device_table
    st = run({}, s.list_devices)
    print_device_table(st.get("devices", []))


@dev_app.command(name="scan")
def dev_scan():
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    dev = st["device"]
    typer.echo(f"Detected: {dev.get('device_name', 'Unknown')} (id={dev['id']})")


@dev_app.command(name="battery")
def dev_battery():
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    if st.get("battery"):
        b = st["battery"]
        typer.echo(f"Battery: {b['level']}% ({'charging' if b['charging'] else 'discharging'})")
    else:
        typer.echo("No battery info available")


@dev_app.command(name="default")
def dev_default():
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    run(st, s.set_default)
    typer.echo(f"Default: {st['device'].get('device_name', 'Unknown')}")


# ── Effect Subcommands ─────────────────────────────────────────────────────

class EffectName(str, Enum):
    NC = "nc"; SURROUND = "surround"; EQ = "eq"; EC = "ec"


@eff_app.command(name="list")
def eff_list():
    from .audio import print_effects
    print_effects()


@eff_app.command(name="enable")
def eff_enable(name: EffectName = typer.Argument(...)):
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    proc = {"nc": s.enable_nc, "surround": s.enable_surround,
            "eq": s.enable_eq, "ec": s.enable_ec}[name.value]
    st = run({**st, f"{name.value}_enabled": True}, proc, after=s.record_outcome)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Enabled: {name.value}")


@eff_app.command(name="disable")
def eff_disable(name: EffectName = typer.Argument(...)):
    st = _detect()
    if not _ok(st):
        raise typer.Exit(1)
    run({**st, "effect_to_disable": name.value}, s.disable_filter)
    typer.echo(f"Disabled: {name.value}")


# ── Profile Subcommands ────────────────────────────────────────────────────

@prof_app.command(name="list")
def prof_list():
    from .audio import list_profiles
    for p in list_profiles():
        typer.echo(f"  {p.get('_name', p.get('name', '?'))} ({p.get('brand', '?')})")


@prof_app.command(name="show")
def prof_show(name: str = typer.Argument(...)):
    from .audio import get_profile
    p = get_profile(name)
    typer.echo(f"Profile: {name} | Brand: {p.get('brand', '?')}")


@prof_app.command(name="create")
def prof_create():
    from .audio import save_profile
    name = typer.prompt("Headset name")
    brand = typer.prompt("Brand")
    save_profile(name, {"name": name, "brand": brand})
    typer.echo(f"Profile saved: {name}")


@prof_app.command(name="delete")
def prof_delete(name: str = typer.Argument(...)):
    from .audio import delete_profile
    if delete_profile(name):
        typer.echo(f"Deleted: {name}")
    else:
        typer.echo(f"Not found: {name}")
        raise typer.Exit(1)


# ── Daemon Subcommands ─────────────────────────────────────────────────────

def _daemon_action(action: str):
    import subprocess
    r = subprocess.run(["systemctl", "--user", action, "hifi-daemon"], capture_output=True)
    typer.echo(f"Daemon {action}" + (" OK" if r.returncode == 0 else " (systemd unavailable)"))


@daemon_app.command(name="start")
def daemon_start(): _daemon_action("start")

@daemon_app.command(name="stop")
def daemon_stop(): _daemon_action("stop")

@daemon_app.command(name="restart")
def daemon_restart(): _daemon_action("restart")

@daemon_app.command(name="status")
def daemon_status(): _daemon_action("status")


def main_entry():
    app()

if __name__ == "__main__":
    sys.exit(main_entry() or 0)

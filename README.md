<p align="center">
  <img src="https://img.shields.io/badge/Audio-Wireless%20Headsets-232323?style=for-the-badge&labelColor=232323&color=00d4aa" alt="Audio"/>
  <img src="https://img.shields.io/badge/Linux-Arch%20%7C%20Fedora%20%7C%20Ubuntu-232323?style=for-the-badge&labelColor=232323&color=fcc624" alt="Linux"/>
  <img src="https://img.shields.io/badge/PipeWire-Native-232323?style=for-the-badge&labelColor=232323&color=ff6b6b" alt="PipeWire"/>
  <img src="https://img.shields.io/badge/Status-Stable-232323?style=for-the-badge&labelColor=232323&color=2ecc71" alt="Status"/>
</p>

<h1 align="center">HiFi Suite v3</h1>

<p align="center">
  <b>Zero-config audio suite for wireless headsets on Linux</b><br/>
  <sub>Volume control · Virtual surround · Noise cancellation · EQ · All DEs</sub>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#effects">Effects</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## What is HiFi Suite?

HiFi Suite is a **unified audio management tool** for wireless headsets on Linux. It combines volume control, virtual surround sound, noise cancellation, and equalization into a single tool that **works out of the box** — no configuration needed.

### The Problem

Wireless headsets on Linux have fragmented audio control:
- Volume sync between ALSA channels is broken on many USB dongles
- Virtual surround requires manual PipeWire filter chain setup
- Noise cancellation needs LADSPA plugins + config files
- Each desktop environment has its own widget — none work cross-DE
- EasyEffects exists but doesn't auto-configure
- No way to save per-headset settings

### The Solution

HiFi Suite wraps PipeWire's native `wpctl` CLI with a simple interface:

```bash
hifi-suite auto          # Detect headset, enable NC, start daemon — done
hifi-suite vol set 75    # Set volume
hifi-suite effect list   # See what's active
```

**One command. Zero config. Every headset.**

---

## Features

| Feature | Description |
|---------|-------------|
| **Universal detection** | Detects ANY headset via PipeWire `device.form-factor` + brand + bluetooth fallback |
| **Zero-config** | `hifi-suite auto` configures everything on first run |
| **Battery monitoring** | Shows battery level (UPower / PipeWire / bluetoothctl) |
| **Volume control** | Set, mute, relative (+/-), software gain up to 150% |
| **Virtual surround** | 7.1 and 7.1.4 via PipeWire SOFA spatializer |
| **Noise cancellation** | RNNoise virtual mic — select as input, noise gone |
| **Convolution EQ** | Apply AutoEq `.wav` files as PipeWire filter chains |
| **Echo cancellation** | PipeWire `module-echo-cancel` for speaker leakage |
| **Custom profiles** | Per-headset JSON settings (EQ, SOFA, NC, volume) |
| **Learning system** | Remembers successful configs per device, auto-applies next time |
| **3 DE widgets** | KDE Plasma 6, GNOME Shell 46+, Cinnamon |
| **Systemd daemon** | Auto-start, persistent volume, socket-based control |

---

## Install

### Arch Linux (AUR)

```bash
paru -S hifi-suite-git
```

> **Upgrading from `redragon-audio-suite-git`?** Just install `hifi-suite-git` — pacman auto-replaces the old package.

### Manual

```bash
git clone https://github.com/Pakrohk/linux-hifi-suite.git
cd linux-hifi-suite
makepkg -si
```

### Dependencies

| Required | Purpose |
|----------|---------|
| `python` | Daemon and CLI |
| `typer` | CLI framework (auto-completion, colored help) |
| `alsa-utils` | ALSA hardware control |
| `pipewire` | Audio server |
| `pipewire-alsa` | ALSA bridge |
| `pipewire-pulse` | PulseAudio compatibility |

| Optional | Purpose |
|----------|---------|
| `noise-suppression-for-voice` | RNNoise LADSPA plugin (recommended) |
| `virtual-surround-manager` | Virtual 7.1/5.1 surround with HeSuVi WAV (recommended) |
| `easyeffects` | GUI audio effects |
| `realtime-privileges` | Low-latency audio |
| `plasma-desktop` | KDE Plasma widget |
| `gnome-shell` | GNOME Shell extension |
| `cinnamon` | Cinnamon applet |

---

## Quick Start

```bash
# 1. Install
paru -S hifi-suite-git

# 2. Auto-configure (detects headset, enables NC, starts daemon)
hifi-suite auto

# 3. Control volume
hifi-suite vol set 75     # Set to 75%
hifi-suite vol mute       # Toggle mute
hifi-suite vol get        # Show current volume

# 4. Check status
hifi-suite effect list    # See active effects
hifi-suite device list    # List all PipeWire devices
hifi-suite device battery # Show headset battery level
```

That's it. The daemon runs in the background, detects connect/disconnect events, and keeps everything in sync.

---

## Commands

### Top-level

```bash
hifi-suite auto           # Auto-detect + configure everything
hifi-suite status         # Show device and effects status
hifi-suite scan           # Force re-detection of headset
hifi-suite effects        # List all effects and status
hifi-suite default        # Set headset as default output
hifi-suite select         # Interactive device selector
hifi-suite recommend      # Show download recommendations
```

### Volume (`hifi-suite vol`)

```bash
hifi-suite vol get        # Get current volume
hifi-suite vol set 75     # Set absolute volume
hifi-suite vol up 10      # Increase by 10%
hifi-suite vol down 10    # Decrease by 10%
hifi-suite vol mute       # Toggle mute
```

### Devices (`hifi-suite device`)

```bash
hifi-suite device list           # List all PipeWire devices
hifi-suite device list --detail  # Devices with connection type
hifi-suite device scan           # Force re-detection
hifi-suite device battery        # Show headset battery level
hifi-suite device default        # Set headset as default output
```

### Effects (`hifi-suite effect`)

```bash
hifi-suite effect list           # List effects and status
hifi-suite effect enable nc      # Enable noise cancellation
hifi-suite effect disable nc     # Disable noise cancellation
hifi-suite effect enable surround # Enable 7.1 surround
hifi-suite effect enable eq      # Enable convolution EQ
hifi-suite effect enable ec      # Enable echo cancellation
```

### Profiles (`hifi-suite profile`)

```bash
hifi-suite profile list                    # List custom profiles
hifi-suite profile show "Redragon H888"    # Show profile
hifi-suite profile create                  # Create new profile (interactive)
hifi-suite profile delete "Redragon H888"  # Delete profile
```

### Daemon (`hifi-suite daemon`)

```bash
hifi-suite daemon start     # Start the daemon
hifi-suite daemon stop      # Stop the daemon
hifi-suite daemon restart   # Restart
hifi-suite daemon status    # Check if running
```

---

## Effects

### Noise Cancellation (RNNoise)

Automatic noise suppression using the RNNoise LADSPA plugin.

```bash
hifi-suite effect enable nc
```

**How it works:** Creates a virtual microphone source called "Noise Cancelling Mic". Select it as your input in any app — all noise is automatically removed.

### Virtual Surround

7.1 and 7.1.4 virtual surround using PipeWire SOFA spatializer.

```bash
hifi-suite effect enable surround    # 7.1
```

**Requirements:**
- A `.sofa` HRIR file (download from [SOFA Conventions](http://sofacoustics.org/data))
- Or: [virtual-surround-manager](https://github.com/Berny23/virtual-surround-manager) (recommended)

### Convolution EQ

Apply EQ curves from [AutoEq](https://autoeq.app) as PipeWire filter chains.

```bash
hifi-suite effect enable eq
```

Place your `.wav` EQ file at `~/.config/hifi-suite/eq.wav`.

### Echo Cancellation

For speakers or open-back headphones that leak audio.

```bash
hifi-suite effect enable ec
```

---

## Architecture

HiFi Suite v3 uses **Functional IOP (Intent-Oriented Programming)** — a hybrid approach combining functional programming with intent-based data flow.

### Core Principles

1. **State = TypedDict** — simple dict, no class overhead
2. **Processors = pure functions** — `State → State`, no side effects
3. **Pipeline = function composition** — `run(state, *steps)` instead of Pipeline class
4. **CLI = thin Typer layer** — only I/O, all logic in processors

### Project Structure

```
hifi/
├── __init__.py    — version
├── state.py       — State TypedDict + all pure processors
├── pipeline.py    — compose() + run() — 35 lines
├── cli.py         — Typer CLI (thin, delegates to pipeline)
├── daemon.py      — daemon with device monitoring
├── device.py      — detection (form-factor + brand + bluetooth)
├── audio.py       — volume, filters, battery, profiles, display
└── util.py        — shared utilities
```

### How Data Flows

```python
from .state import State
from .pipeline import run
from . import state as s

# Each step reads state, returns new state
result = run(
    {"volume": 75},
    s.detect_device,     # State → State (adds device info)
    s.enable_nc,         # State → State (enables NC filter)
    s.set_volume,        # State → State (sets volume)
    after=s.record_outcome,  # Learning hook
)

if result.get("error"):
    print(f"Error: {result['error']}")
```

### Adding a New Feature

1. Add a processor in `state.py`:
```python
def my_new_feature(s: State) -> State:
    if s.get("error"):
        return s
    # ... do something ...
    return {**s, "my_feature_enabled": True}
```

2. Add a Typer command in `cli.py`:
```python
@app.command()
def my_command():
    st = _detect()
    st = run(st, s.my_new_feature)
    typer.echo(f"Done: {st.get('my_feature_enabled')}")
```

That's it. No classes to inherit, no interfaces to implement, no decorators to register.

### Why This Design?

| Old (OOP) | New (Functional IOP) |
|---|---|
| 16 files, 2695 lines | **8 files, 1496 lines** |
| Intent dataclass + Pipeline class | State dict + run() function |
| `pipe.process(Intent(...))` | `run(state, step1, step2)` |
| Processor class methods | Pure functions `State → State` |
| 50-line `_build_pipeline()` | 35-line `pipeline.py` total |

---

## Contributing

### Development Setup

```bash
git clone https://github.com/Pakrohk/linux-hifi-suite.git
cd linux-hifi-suite

# Run directly from source (no install needed)
python3 hifi-suite --help
python3 hifi-suite auto
```

### Code Style

- **Pure processors** — each function in `state.py` takes `State`, returns `State`. No side effects.
- **Thin CLI** — `cli.py` only handles I/O (typer prompts, printing). All logic in processors.
- **No classes** — unless you need methods on data (e.g., `FilterManager` for filter lifecycle).
- **English only** — all code comments and docstrings in English.

### Project Layout

| File | Lines | Purpose |
|------|-------|---------|
| `state.py` | ~230 | State TypedDict + all processors |
| `pipeline.py` | ~35 | `run()` and `compose()` |
| `cli.py` | ~360 | Typer CLI commands |
| `daemon.py` | ~190 | Unix socket daemon |
| `device.py` | ~125 | Device detection |
| `audio.py` | ~530 | Volume, filters, battery, profiles, display |
| `util.py` | ~20 | Shared subprocess runner |

### Testing

```bash
# Syntax check
for f in hifi/*.py; do python3 -c "import ast; ast.parse(open('$f').read())"; done

# Run from source
python3 hifi-suite --help
python3 hifi-suite device list
python3 hifi-suite vol get
```

---

## Compatible Headsets

HiFi Suite detects **any headset** via PipeWire's `device.form-factor` property — no brand list needed. Works with:

- **USB headsets** — detected via `device.bus = "usb"`
- **Bluetooth headsets** — detected via `device.bus = "bluetooth"`
- **2.4GHz dongle headsets** — detected via `device.bus = "usb"`
- **3.5mm jack headsets** — detected via `device.bus = "pci"`

Tested with: Redragon H888/H878/H848, Aula G7 Pro, Logitech G Pro X/G733, HyperX Cloud II/Alpha, Razer BlackShark/Kraken, SteelSeries Arctis 7, Sony WH-1000XM4, JBL Quantum 800.

---

## Upgrading from Redragon Audio Suite

```bash
paru -S hifi-suite-git    # Old package auto-removed
hifi-suite auto            # Re-run setup
```

---

## License

[MIT](LICENSE) — The shortest license that works.

---

<p align="center">
  <sub>Built with PipeWire + Python + Typer · Works on every Linux desktop · Zero config</sub>
</p>

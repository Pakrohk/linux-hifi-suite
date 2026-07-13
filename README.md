<p align="center">
  <img src="https://img.shields.io/badge/Audio-Wireless%20Headsets-232323?style=for-the-badge&labelColor=232323&color=00d4aa" alt="Audio"/>
  <img src="https://img.shields.io/badge/Linux-Arch%20%7C%20Fedora%20%7C%20Ubuntu-232323?style=for-the-badge&labelColor=232323&color=fcc624" alt="Linux"/>
  <img src="https://img.shields.io/badge/PipeWire-Native-232323?style=for-the-badge&labelColor=232323&color=ff6b6b" alt="PipeWire"/>
  <img src="https://img.shields.io/badge/Status-Stable-232323?style=for-the-badge&labelColor=232323&color=2ecc71" alt="Status"/>
  <img src="https://img.shields.io/badge/Python-3.10+-232323?style=for-the-badge&labelColor=232323&color=3776ab" alt="Python"/>
  <img src="https://img.shields.io/badge/Typer-CLI-232323?style=for-the-badge&labelColor=232323&color=009688" alt="Typer"/>
</p>

<h1 align="center">HiFi Suite v3</h1>

<p align="center">
  <b>Zero-config audio suite for wireless headsets on Linux</b><br/>
  <sub>Volume · Surround · Noise Filter · Echo Cancel · EQ · Low Latency · Device Management</sub>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#effects">Effects</a> ·
  <a href="#noise-filter">Noise Filter</a> ·
  <a href="#echo-cancellation">Echo Cancellation</a> ·
  <a href="#low-latency">Low Latency</a> ·
  <a href="#device-management">Device Management</a> ·
  <a href="#desktop-widgets">Widgets</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## What is HiFi Suite?

HiFi Suite is a **unified audio management tool** for wireless headsets on Linux. It combines volume control, virtual surround sound, noise filtering, echo cancellation, equalization, and low-latency mode into a single tool that **works out of the box**.

### The Problem

Wireless headsets on Linux have fragmented audio control:
- Volume sync between ALSA channels is broken on many USB dongles
- Virtual surround requires manual PipeWire filter chain setup
- Noise cancellation needs LADSPA plugins + config files
- Echo cancellation is separate from noise filtering — no way to use both
- No way to filter noise on incoming audio (other person's side)
- Low-latency mode requires manual PipeWire quantum configuration
- Each desktop environment has its own widget — none work cross-DE

### The Solution

```bash
hifi-suite auto              # Detect headset, enable filters, start daemon — done
hifi-suite noise input       # Filter noise from your mic (outgoing)
hifi-suite noise output      # Filter noise from other side (incoming)
hifi-suite effect enable ec  # Echo cancellation on your mic (works with NC)
hifi-suite effect latency on # Low-latency for gaming (~3ms)
hifi-suite reset             # Remove all filters, restore defaults
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
| **Noise filter (input)** | RNNoise on your mic — outgoing audio cleaned |
| **Noise filter (output)** | RNNoise on incoming audio — other person's noise removed |
| **Noise filter (both)** | Both directions simultaneously |
| **Echo cancellation** | Independent EC toggle — works alongside noise filter |
| **Convolution EQ** | Apply AutoEq `.wav` files as PipeWire filter chains |
| **Low-latency mode** | quantum=64 + RT priority — ~3ms latency for gaming |
| **Device management** | List all PipeWire nodes, remove virtual devices |
| **Reset** | Remove all filters and restore PipeWire defaults |
| **Custom profiles** | Per-headset JSON settings (EQ, SOFA, volume) |
| **Learning system** | Remembers successful configs per device, auto-applies next time |
| **3 DE widgets** | KDE Plasma 6, GNOME Shell 46+, Cinnamon — with noise/latency/reset controls |
| **Systemd daemon** | Auto-start, persistent volume, socket-based control |
| **Tab completion** | Full shell completion for all commands and subcommands |

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
| `python-typer` | CLI framework (auto-completion, colored help) |
| `alsa-utils` | ALSA hardware control |
| `pipewire` | Audio server |
| `pipewire-alsa` | ALSA bridge |
| `pipewire-pulse` | PulseAudio compatibility |

| Optional | Purpose |
|----------|---------|
| `noise-suppression-for-voice` | RNNoise LADSPA plugin (recommended for noise filter + EC) |
| `virtual-surround-manager` | Virtual 7.1/5.1 surround with HeSuVi WAV |
| `realtime-privileges` | Low-latency audio (RT priority) |
| `plasma-desktop` | KDE Plasma widget |
| `gnome-shell` | GNOME Shell extension |
| `cinnamon` | Cinnamon applet |

---

## Quick Start

```bash
# 1. Install
paru -S hifi-suite-git

# 2. Auto-configure everything
hifi-suite auto

# 3. Control volume
hifi-suite vol set 75     # Set to 75%
hifi-suite vol mute       # Toggle mute

# 4. Enable noise filter
hifi-suite noise input    # Clean your mic (outgoing)

# 5. Enable echo cancellation (works alongside noise filter)
hifi-suite effect enable ec

# 6. Enable low-latency for gaming
hifi-suite effect latency on

# 7. Check status
hifi-suite effect list    # See active effects + latency
hifi-suite battery        # Show headset battery

# 8. Reset everything when needed
hifi-suite reset          # Remove all filters, restore defaults
```

---

## Commands

### Top-level

```bash
hifi-suite auto           # Auto-detect + configure everything
hifi-suite status         # Show device and effects status
hifi-suite scan           # Force re-detection of headset
hifi-suite battery        # Show headset battery level
hifi-suite devices        # List all PipeWire devices
hifi-suite effects        # List all effects and status
hifi-suite default        # Set headset as default output
hifi-suite select         # Interactive device selector
hifi-suite recommend      # Show download recommendations
hifi-suite reset          # Remove all filters, restore PipeWire defaults
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
hifi-suite device manage         # List ALL nodes (real + virtual + filters + streams)
hifi-suite device remove <id>    # Remove a virtual PipeWire node
hifi-suite device scan           # Force re-detection
hifi-suite device battery        # Show headset battery level
hifi-suite device default        # Set headset as default output
```

### Effects (`hifi-suite effect`)

```bash
hifi-suite effect list              # List effects and status
hifi-suite effect enable nc         # Enable noise filter (input)
hifi-suite effect enable ec         # Enable echo cancellation (works with NC)
hifi-suite effect enable surround   # Enable 7.1 surround
hifi-suite effect enable eq         # Enable convolution EQ
hifi-suite effect disable ec        # Disable echo cancellation
hifi-suite effect latency on        # Enable low-latency mode
hifi-suite effect latency off       # Disable low-latency mode
```

### Noise Filter (`hifi-suite noise`)

```bash
hifi-suite noise input    # Filter noise on YOUR mic (outgoing audio)
hifi-suite noise output   # Filter noise on incoming audio (other person)
hifi-suite noise both     # Filter both directions simultaneously
hifi-suite noise off      # Disable all noise filters
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

### Reset

```bash
hifi-suite reset            # Remove ALL filters and restore defaults
```

Removes: noise filters (NC/NC_out), echo cancellation (EC), surround, EQ, low-latency config. PipeWire restarts automatically.

---

## Effects

### Noise Filter

Noise filtering that works in **3 modes**:

```bash
hifi-suite noise input     # Clean YOUR mic (outgoing)
hifi-suite noise output    # Clean incoming audio (other person's side)
hifi-suite noise both      # Both directions
hifi-suite noise off       # Disable all
```

**How it works:**
- **Input mode**: Creates a virtual microphone "Noise Cancelling Mic" using RNNoise. Select it as your input in any app — your outgoing audio is cleaned.
- **Output mode**: Creates a virtual output "Noise Filtered Output" using RNNoise. Select it as your output — incoming audio from the other side is cleaned.
- **Both mode**: Both filters active simultaneously.

**Requirements:**
```bash
sudo pacman -S noise-suppression-for-voice  # RNNoise LADSPA plugin
```

### Echo Cancellation

Independent echo cancellation that **works alongside the noise filter**. Both can be active at the same time on the same microphone.

```bash
hifi-suite effect enable ec     # Enable echo cancellation
hifi-suite effect disable ec    # Disable echo cancellation
```

**How it works:**
- Uses PipeWire's `module-echo-cancel` on your physical microphone
- Cancels echo/feedback from the speaker into the mic
- **Independent of NC** — you can have NC (noise filter) + EC (echo cancel) simultaneously
- EC handles echo, NC handles background noise — different problems, same mic

**When to use EC:**
- Speaker audio leaks into your mic (open-back headphones, speakers)
- Other person hears their own voice echoed back
- Video call echo issues

### Virtual Surround

7.1 and 7.1.4 virtual surround using PipeWire SOFA spatializer.

```bash
hifi-suite effect enable surround
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

### Low-Latency Mode

Reduces audio buffer size for lower latency — essential for gaming, live monitoring, and real-time applications.

```bash
hifi-suite effect latency on    # Enable (~3ms latency)
hifi-suite effect latency off   # Disable (default ~20ms)
```

**What it does:**
- Sets PipeWire quantum to 64 samples (~3ms at 48kHz)
- Enables real-time thread priority (nice=-11, rt.prio=88)
- Reduces max-quantum to 256 for safety

**Latency comparison:**

| Mode | Quantum | Latency | Best for |
|------|---------|---------|----------|
| Default | 1024 | ~21ms | Music, video, calls |
| Low Latency | 64 | **~3ms** | Gaming, live monitoring |

**Works on:** USB headsets (best), PCI/internal audio, HDMI. Bluetooth has inherent ~40-80ms latency that can't be fully overcome.

**Warning:** May cause audio glitches on slow systems. Disable if you hear crackling.

### Effects Display

```bash
$ hifi-suite effects

  Effects
  ────────────────────────────────────────────────────
  [ON]  Noise Filter — Input (your mic, outgoing)
  [off] Noise Filter — Output (other person, incoming)
  [ON]  Echo Cancellation — Input (your mic, reduces echo)
  [off] 7.1 Surround
  [off] Equalizer
  [ON]  Low Latency Mode (quantum=64, rt priority)
  ────────────────────────────────────────────────────
  Tip: hifi-suite effect latency on  — for gaming/live monitoring
```

---

## Device Management

View and manage all PipeWire audio nodes — real devices, virtual devices, filters, and active streams.

```bash
hifi-suite device manage
```

**Example output:**

```
  PipeWire Nodes
  ─────────────────────────────────────────────────────────────

  Physical Devices (hardware)
  ······························································
    46  H888 Wireless headset     [permanent]  Hardware Device
    71  USB Audio Device          [permanent]  Hardware Device
    73  Built-in Audio            [permanent]  Hardware Device

  Active Filters (hifi-suite)
  ······························································
    34  capture.hifi_rnnoise      [removable]  NC Filter (noise cancellation — input)
    45  hifi_rnnoise_source       [removable]  NC Source (virtual mic output)

  Active Streams
  ······························································
    47  Firefox
   101  Firefox

  ─────────────────────────────────────────────────────────────
  hifi-suite device remove <id>  — remove a [removable] node
```

**Remove virtual devices:**
```bash
hifi-suite device remove 34    # Remove a filter node
hifi-suite device remove 45    # Remove a virtual source
```

---

## Desktop Widgets

All three widgets support the full feature set:

| Feature | KDE Plasma 6 | GNOME Shell 46+ | Cinnamon |
|---------|:---:|:---:|:---:|
| Volume control (slider + scroll) | Yes | Yes | Yes |
| Mute toggle | Yes | Yes | Yes |
| Battery display | Yes | Yes | Yes |
| Noise Filter (Input/Output/Both) | Yes | Yes | Yes |
| Echo Cancellation toggle | Yes | Yes | Yes |
| 7.1 Surround toggle | Yes | Yes | Yes |
| EQ toggle | Yes | Yes | Yes |
| Low Latency toggle | Yes | Yes | Yes |
| Reset All button | Yes | Yes | Yes |

### KDE Plasma 6

Auto-installed with the package. Add to panel:
1. Right-click panel → **Add Widgets**
2. Search **"HiFi Suite"**
3. Add to panel

### GNOME Shell 46+

Auto-installed. Enable:
```bash
gnome-extensions enable hifi-suite@hifi-suite
```

### Cinnamon

Auto-installed. Add to panel:
1. Right-click panel → **Applets**
2. Find **"HiFi Suite"**
3. Add to panel

---

## Architecture

HiFi Suite v3 uses **Functional IOP (Intent-Oriented Programming)** — a hybrid approach combining functional programming with intent-based data flow.

### Core Principles

```
┌─────────────────────────────────────────────────────┐
│                    State (dict)                     │
│         "What do I know about the system?"          │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │   Processor     │
              │  (State → State)│
              │  Pure function  │
              │  No side effects│
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   Pipeline      │
              │ run(state, *steps)│
              │   Composition   │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   CLI (Typer)   │
              │  Just I/O       │
              └─────────────────┘
```

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
    s.enable_nc,         # State → State (enables noise filter)
    s.enable_ec,         # State → State (enables echo cancellation)
    s.set_volume,        # State → State (sets volume)
    after=s.record_outcome,  # Learning hook
)

if result.get("error"):
    print(f"Error: {result['error']}")
```

---

## Adding a New Feature

Adding a new feature to HiFi Suite is simple — just 2 steps. No classes to inherit, no interfaces to implement, no decorators to register.

### Step 1: Add a Processor

Open `hifi/state.py` and add a pure function:

```python
def my_new_feature(s: State) -> State:
    """My awesome new feature."""
    # Check for errors from previous steps
    if s.get("error"):
        return s

    # Check if already enabled (for toggle commands)
    if not s.get("my_feature_enabled"):
        return s

    # Do the actual work
    from .audio import some_helper_function
    result = some_helper_function()

    if result:
        return {**s, "my_feature_enabled": True}
    else:
        return {**s, "error": "Failed to enable my feature"}
```

### Step 2: Add a CLI Command

Open `hifi/cli.py` and add a Typer command:

```python
@eff_app.command(name="my-feature")
def my_feature():
    """Enable my awesome new feature."""
    st = run({}, s.detect_device)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)
    st = run({**st, "my_feature_enabled": True}, s.my_new_feature)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)
    typer.echo("Enabled: my-feature")
```

### That's it!

```bash
hifi-suite effect my-feature    # Your new command works!
```

### Real Example: How Echo Cancellation Was Added

**Step 1** — `state.py`:
```python
def enable_ec(s: State) -> State:
    """Enable echo cancellation on the physical mic (independent of NC)."""
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
    config = render_ec(mic["node_name"], out_node)
    ok = FilterManager().load("ec", config)
    return s if ok else {**s, "error": "Failed to load echo cancellation"}
```

**Step 2** — `cli.py`:
```python
@eff_app.command(name="enable")
def eff_enable(name: EffectName = typer.Argument(...)):
    """Enable an audio effect. EC works alongside NC noise filter."""
    st = run({}, s.detect_device)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)
    proc = {"nc": s.enable_nc, "surround": s.enable_surround,
            "eq": s.enable_eq, "ec": s.enable_ec}[name.value]
    st = run({**st, f"{name.value}_enabled": True}, proc, after=s.record_outcome)
    if st.get("error"):
        typer.echo(f"Error: {st['error']}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Enabled: {name.value}")
```

### Code Style Rules

- **Pure processors** — each function in `state.py` takes `State`, returns `State`. No side effects.
- **Thin CLI** — `cli.py` only handles I/O (typer prompts, printing). All logic in processors.
- **No classes** — unless you need methods on data (e.g., `FilterManager`).
- **English only** — all code comments and docstrings in English.
- **Error propagation** — check `s.get("error")` at the start, return early if set.

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

### Project Layout

| File | Lines | Purpose |
|------|-------|---------|
| `state.py` | ~280 | State TypedDict + all processors |
| `pipeline.py` | ~35 | `run()` and `compose()` |
| `cli.py` | ~480 | Typer CLI commands |
| `daemon.py` | ~190 | Unix socket daemon |
| `device.py` | ~125 | Device detection |
| `audio.py` | ~700 | Volume, filters, battery, profiles, display |
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

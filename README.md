<p align="center">
  <img src="https://img.shields.io/badge/Audio-Wireless%20Headsets-232323?style=for-the-badge&labelColor=232323&color=00d4aa" alt="Audio"/>
  <img src="https://img.shields.io/badge/Linux-Arch%20%7C%20Fedora%20%7C%20Ubuntu-232323?style=for-the-badge&labelColor=232323&color=fcc624" alt="Linux"/>
  <img src="https://img.shields.io/badge/PipeWire-Native-232323?style=for-the-badge&labelColor=232323&color=ff6b6b" alt="PipeWire"/>
  <img src="https://img.shields.io/badge/Status-Alpha-232323?style=for-the-badge&labelColor=232323&color=9b59b6" alt="Status"/>
</p>

<h1 align="center">HiFi Suite</h1>

<p align="center">
  <b>Zero-config audio suite for wireless headsets on Linux</b><br/>
  <sub>Volume control · Virtual surround · Noise cancellation · EQ · All DEs</sub>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#effects">Effects</a> ·
  <a href="#custom-profiles">Profiles</a> ·
  <a href="#desktop-widgets">Widgets</a> ·
  <a href="#compatible-headsets">Headsets</a>
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
hifi-suite vol 75        # Set volume
hifi-suite effects       # See what's active
```

**One command. Zero config. Every headset.**

---

## Features

| Feature | Description |
|---------|-------------|
| **Auto-detection** | Detects any wireless headset via `wpctl` |
| **Zero-config** | `hifi-suite auto` configures everything on first run |
| **Volume control** | Set, mute, relative (+/-), software gain up to 150% |
| **Virtual surround** | 7.1 and 7.1.4 via PipeWire SOFA spatializer |
| **Noise cancellation** | RNNoise virtual mic — select as input, noise gone |
| **Convolution EQ** | Apply AutoEq `.wav` files as PipeWire filter chains |
| **Echo cancellation** | PipeWire `module-echo-cancel` for speaker leakage |
| **Combined sinks** | Play to speakers + headset simultaneously |
| **Mic preference rules** | WirePlumber auto-select preferred mic on connect |
| **Custom profiles** | Per-headset JSON settings (EQ, SOFA, NC, volume) |
| **File recommendations** | Best download sites for your specific headset model |
| **EasyEffects compat** | Detects conflicts, manages presets via CLI |
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
| `alsa-utils` | ALSA hardware control |
| `pipewire` | Audio server |
| `pipewire-alsa` | ALSA bridge |
| `pipewire-pulse` | PulseAudio compatibility |
| `socat` | Socket communication |

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
hifi-suite vol 75        # Set to 75%
hifi-suite vol mute      # Toggle mute
hifi-suite vol get       # Show current volume

# 4. Check status
hifi-suite effects       # See active effects
hifi-suite devices       # List all PipeWire devices
```

That's it. The daemon runs in the background and keeps everything in sync.

---

## Commands

### Volume

```bash
hifi-suite vol 75          # Set absolute volume
hifi-suite vol 50+         # Increase by 50%
hifi-suite vol 10-         # Decrease by 10%
hifi-suite vol mute        # Toggle mute
hifi-suite vol get         # Get current volume
```

### Effects

```bash
hifi-suite enable nc       # Enable noise cancellation
hifi-suite disable nc      # Disable noise cancellation
hifi-suite enable surround # Enable 7.1 surround
hifi-suite effects         # List all effects and status
```

### Devices

```bash
hifi-suite devices         # List all PipeWire sinks/sources
hifi-suite default         # Set headset as default output
```

### Mic Preference (WirePlumber)

```bash
# Auto-select a mic when connected
hifi-suite mic-prefer "alsa_input.usb-Jabra_Evolve2_85.mono-fallback"

# Regex match (e.g. any USB mic)
hifi-suite mic-prefer-regex "alsa_input.usb-*"

# List active rules
hifi-suite mic-rules

# Remove preference
hifi-suite mic-unprefer
```

### Combined Output

```bash
# Play to speakers AND headset simultaneously
hifi-suite combine "Speakers+Headset" \
  "alsa_output.pci-0000_00_1f.3.analog-stereo" \
  "alsa_output.usb-Headset-00.analog-stereo"

# Remove combined sink
hifi-suite combine-remove "Speakers+Headset"
```

### EasyEffects

```bash
hifi-suite ee-list         # List installed presets
hifi-suite ee-load "MyEQ"  # Load a preset
hifi-suite ee-start        # Start EasyEffects
hifi-suite ee-stop         # Stop EasyEffects
```

### Custom Profiles

```bash
hifi-suite profile list        # List custom headset profiles
hifi-suite profile show        # Show profile for detected headset
hifi-suite profile show "AULA G7 Pro 2026"  # Show specific profile
hifi-suite profile create      # Create new profile (interactive)
hifi-suite profile delete "AULA G7 Pro 2026" # Delete profile
```

### File Recommendations

```bash
hifi-suite recommend        # Auto-detect headset and recommend files
hifi-suite recommend "AULA G7 Pro 2026"  # Recommend for specific model
```

### Daemon

```bash
hifi-suite daemon start    # Start the daemon
hifi-suite daemon stop     # Stop the daemon
hifi-suite daemon restart  # Restart
hifi-suite daemon status   # Check if running
```

---

## Effects

### Noise Cancellation (RNNoise)

Automatic noise suppression using the RNNoise LADSPA plugin.

```bash
hifi-suite enable nc       # Enable
hifi-suite disable nc      # Disable
```

**How it works:** Creates a virtual microphone source called "Noise Cancelling Mic". Select it as your input in any app — all noise is automatically removed.

The plugin path is auto-detected across distributions:
- `/usr/lib/ladspa/librnnoise_ladspa.so` (Arch, Fedora)
- `/usr/lib64/ladspa/librnnoise_ladspa.so` (64-bit)
- `/usr/lib/x86_64-linux-gnu/ladspa/` (Debian, Ubuntu)

### Virtual Surround

7.1 and 7.1.4 virtual surround using PipeWire SOFA spatializer.

```bash
hifi-suite enable surround    # 7.1
hifi-suite enable surround714 # 7.1.4
```

**Requirements:**
- A `.sofa` HRIR file (download from [SOFA Conventions](http://sofacoustics.org/data) — ARI database recommended)
- PipeWire built with `libmysofa` support
- Or: [virtual-surround-manager](https://github.com/Berny23/virtual-surround-manager) (recommended — uses HeSuVi WAV, no config needed)

> **Note:** Fedora needs `pipewire-module-filter-chain-sofa`. Ubuntu does not build PipeWire with libmysofa.

### Convolution EQ

Apply EQ curves from [AutoEq](https://autoeq.app) as PipeWire filter chains.

```bash
hifi-suite enable eq
```

Place your `.wav` EQ file at `~/.config/hifi-suite/eq.wav`. AutoEq produces settings for all types of equalizer apps — select "Convolution" format for PipeWire.

### Echo Cancellation

For speakers or open-back headphones that leak audio. Uses PipeWire's `module-echo-cancel`.

```bash
hifi-suite enable ec
```

Edit the config to set your actual microphone and output device node names.

---

## Custom Profiles

Save per-headset settings as JSON files at `~/.config/pipewire/hifi-suite/`.

### Profile Format

```json
{
  "name": "AULA G7 Pro 2026",
  "brand": "Aula",
  "eq_wav": "~/Downloads/aula-g7-pro-eq.wav",
  "sofa_file": "~/Resources/hrir-generic.sofa",
  "nc_threshold": 50,
  "recommended_volume": 75,
  "notes": "Budget gaming headset with surprisingly good soundstage"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Headset name (used as filename) |
| `brand` | string | Brand name |
| `eq_wav` | string | Path to EQ `.wav` file |
| `sofa_file` | string | Path to HRIR `.sofa` file |
| `nc_threshold` | number | RNNoise VAD threshold (0-100) |
| `recommended_volume` | number | Optimal volume level (0-100) |
| `notes` | string | User notes |

### How It Works

1. `hifi-suite profile create` — interactive profile creation
2. `hifi-suite recommend` — shows download sites + uses your profile
3. `hifi-suite enable eq` — auto-uses `eq_wav` from profile if set
4. `hifi-suite enable surround` — auto-uses `sofa_file` from profile if set

**Priority:** Custom JSON > Brand defaults > Generic fallback

### Download Sources

| Type | Site | Notes |
|------|------|-------|
| **EQ WAV** | [autoeq.app](https://autoeq.app) | 6033+ headphones, select "Convolution" format |
| **EQ Source** | [github.com/jaakkopasanen/AutoEq](https://github.com/jaakkopasanen/AutoEq) | 16k+ stars, measurements from oratory1990, crinacle, Rtings |
| **SOFA HRIR** | [sofacoustics.org/data](http://sofacoustics.org/data) | Official: worldwide HRTFs, BRIRs |
| **ARI Database** | [sofacoustics.org/data/database/ari](http://sofacoustics.org/data/database/ari) | 220+ listeners, best coverage |
| **CIPIC** | [sofacoustics.org/data/database/cipic](http://sofacoustics.org/data/database/cipic) | 45 listeners, anthropometric data |
| **MIT-KEMAR** | [sofacoustics.org/data/database/mit](http://sofacoustics.org/data/database/mit) | Classic dummy head, reference HRTFs |
| **HUTUBS** | [sofacoustics.org/data/database/hutubs/](http://sofacoustics.org/data/database/hutubs/) | 96 listeners, 3D head models |

---

## Desktop Widgets

### KDE Plasma 6

Auto-installed with the package. Add to panel:
1. Right-click panel → **Add Widgets**
2. Search **"HiFi Suite"**
3. Add to panel

Features: volume slider, mute, effects toggle (NC/surround/eq/ec), scroll to adjust.

### GNOME Shell 46+

Auto-installed. Enable:
```bash
gnome-extensions enable hifi-suite@hifi-suite
```

Features: panel icon, volume slider, mute, effects submenu, scroll to adjust.

### Cinnamon

Auto-installed. Add to panel:
1. Right-click panel → **Applets**
2. Find **"HiFi Suite"**
3. Add to panel

---

## Compatible Headsets

HiFi Suite auto-detects any wireless headset. Tested with:

| Brand | Models |
|-------|--------|
| Aula | G7 Pro 2026, F2026 |
| Redragon | H878, H848, H510 |
| Logitech | G Pro X, G733, G935 |
| HyperX | Cloud II, Cloud Alpha, Cloud Orbit |
| Razer | BlackShark, Kraken, Nari |
| SteelSeries | Arctis 7, Arctis Pro |
| Corsair | Void, HS70, Virtuoso |
| Sennheiser | GSP 670, GSP 370 |
| Sony | WH-1000XM4, WF-1000XM4 |
| JBL | Quantum 800, Quantum 910 |
| Audio-Technica | ATH-G1, ATH-M50xBT |

> If your headset isn't detected, open an issue with the output of `wpctl status` and `aplay -l`.

---

## How It Works

```
┌─────────────────────────────────────────────────┐
│                   hifi-suite                    │
│         (CLI / Widget / Extension / Profile)    │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Volume   │  │ Effects  │  │ Device Mgmt  │   │
│  │ Control  │  │ Manager  │  │ (wpctl)      │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │               │          │
│  ┌────┴──────────────┴───────────────┴───────┐  │
│  │              hifi-daemon.py               │  │
│  │     (Socket server + PCM sync daemon)     │  │
│  └──────────────────┬───────────────────────┘   │
│                     │                           │
├─────────────────────┼───────────────────────────┤
│                     │ Unix Socket               │
├─────────────────────┼───────────────────────────┤
│                     ▼                           │
│  ┌──────────────────────────────────────────┐   │
│  │              PipeWire                    │   │
│  │  ┌──────┐ ┌──────┐ ┌────┐ ┌──────────┐   │   │
│  │  │ wpctl│ │filter│ │ NC │ │combine   │   │   │
│  │  │      │ │chain │ │ RN │ │sink      │   │   │
│  │  └──────┘ └──────┘ └────┘ └──────────┘   │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ~/.config/pipewire/hifi-suite/                 │
│  ├── AULA G7 Pro 2026.json  (custom profile)   │
│  └── Redragon H888.json     (custom profile)   │
└─────────────────────────────────────────────────┘
```

---

## Project Structure

```
linux-hifi-suite/
├── hifi-daemon.py          # Unified daemon (volume sync + socket control)
├── hifi_pipewire.py        # PipeWire integration (wpctl, filters, rules, profiles)
├── hifi-suite              # CLI entry point
├── hifi-daemon.service     # Systemd user service
├── hifi-suite.install      # Pacman install hooks
├── PKGBUILD                # Arch Linux package
├── configs/                # PipeWire filter chain templates
│   ├── surround-7.1.conf
│   ├── surround-7.1.4.conf
│   ├── nc.conf             # RNNoise
│   ├── eq.conf             # Convolution EQ
│   ├── ec.conf             # Echo cancellation
│   └── 99-realtime.conf
├── plasma-widget/          # KDE Plasma 6 widget
├── gnome-extension/        # GNOME Shell 46+ extension
└── cinnamon-applet/        # Cinnamon applet
```

---

## Upgrading from Redragon Audio Suite

If you have `redragon-audio-suite-git` installed:

```bash
# Just install the new package — pacman handles the transition
paru -S hifi-suite-git

# Old package is automatically removed
# Your PipeWire configs are preserved
# Run setup again:
hifi-suite auto
```

---

## License

[MIT](LICENSE) — The shortest license that works.

---

<p align="center">
  <sub>Built with PipeWire · Works on every Linux desktop · Zero config</sub>
</p>

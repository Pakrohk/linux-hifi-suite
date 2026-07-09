
# Maintainer: Pakrohk <pakrohk@gmail.com>
pkgname=redragon-audio-suite-git
pkgver=0.0.0
pkgrel=1
pkgdesc="Complete audio suite for Redragon headsets on Arch Linux: PCM sync fix + 7.1.4 virtual surround + EQ + noise cancellation"
arch=('any')
url="https://github.com/cristianocps/redragon-hs-companion"
license=('MIT')
depends=('python' 'alsa-utils' 'pipewire' 'pipewire-alsa' 'pipewire-pulse')
makedepends=('git')
optdepends=(
    'gnome-shell: GNOME Shell extension for volume control'
    'cinnamon: Cinnamon applet for volume control'
    'plasma-desktop: KDE Plasma widget for volume control'
    'noise-suppression-for-voice: System-wide noise cancellation'
    'easyeffects: GUI for advanced audio effects'
    'virtual-surround-manager: GUI to manage HeSuVi .wav files for EasyEffects'
)
provides=('redragon-hs-companion')
conflicts=('redragon-hs-companion' 'redragon-hs-companion-git')
source=(
    "redragon-hs-companion::git+https://github.com/cristianocps/redragon-hs-companion.git"
    "pipewire-dx-utils::git+https://github.com/DekoDX/Pipewire-DX-Utils.git"
)
md5sums=('SKIP' 'SKIP')

pkgver() {
  cd "$srcdir/redragon-hs-companion" || return 1
  local ver
  ver=$(git describe --long --tags 2>/dev/null | sed 's/^v//; s/\([^-]*\)-g.*/\1/')
  if [ -z "$ver" ]; then
    ver="0.0.0"
  fi
  echo "$ver"
}

ask_user() {
    local question="$1"
    local default="${2:-n}"
    local answer
    while true; do
        read -p "$question [Y/n]: " answer
        answer=${answer:-$default}
        case $answer in
            [Yy]* ) return 0 ;;
            [Nn]* ) return 1 ;;
            * ) echo "Please answer yes or no." ;;
        esac
    done
}

package() {
    echo ""
    echo "=========================================="
    echo "  Redragon Audio Suite Installation"
    echo "=========================================="
    echo ""
    echo "This suite includes:"
    echo "  1. redragon-hs-companion - PCM channel sync fix for wireless headsets"
    echo "  2. Pipewire-DX-Utils - Advanced filter-chain configs (7.1.4 surround, EQ, noise cancellation)"
    echo "  3. Setup script to auto-configure your devices"
    echo ""

    # ============================================
    # PART 1: redragon-hs-companion (core)
    # ============================================
    echo "--- Installing redragon-hs-companion ---"
    cd "$srcdir/redragon-hs-companion" || exit 1

    install -Dm755 redragon-volume "$pkgdir/usr/bin/redragon-volume"
    install -Dm755 redragon_control_daemon.py "$pkgdir/usr/bin/redragon_control_daemon.py"
    install -Dm755 redragon_daemon.py "$pkgdir/usr/bin/redragon_daemon.py"

    # Check if systemd service files exist before installing
    if [ -f "systemd/redragon-control-daemon.service" ]; then
        install -Dm644 systemd/redragon-control-daemon.service "$pkgdir/usr/lib/systemd/user/redragon-control-daemon.service"
    else
        echo "  Warning: redragon-control-daemon.service not found, skipping."
    fi

    if [ -f "systemd/redragon-volume-sync.service" ]; then
        install -Dm644 systemd/redragon-volume-sync.service "$pkgdir/usr/lib/systemd/user/redragon-volume-sync.service"
    else
        echo "  Warning: redragon-volume-sync.service not found, skipping."
    fi

    echo ""
    echo "--- Desktop Widgets (redragon-hs-companion) ---"
    if [ -d "gnome-extension" ] && ask_user "Install GNOME Shell extension?" "n"; then
        install -d "$pkgdir/usr/share/gnome-shell/extensions/redragon-hs-companion@cristianocps.github.com"
        cp -r gnome-extension/* "$pkgdir/usr/share/gnome-shell/extensions/redragon-hs-companion@cristianocps.github.com/"
        echo "  -> GNOME extension installed"
    fi
    if [ -d "cinnamon-applet" ] && ask_user "Install Cinnamon applet?" "n"; then
        install -d "$pkgdir/usr/share/cinnamon/applets/redragon-hs-companion@cristianocps.github.com"
        cp -r cinnamon-applet/* "$pkgdir/usr/share/cinnamon/applets/redragon-hs-companion@cristianocps.github.com/"
        echo "  -> Cinnamon applet installed"
    fi
    if [ -d "plasma-widget" ] && ask_user "Install KDE Plasma widget?" "n"; then
        install -d "$pkgdir/usr/share/plasma/plasmoids/redragon-hs-companion"
        cp -r plasma-widget/* "$pkgdir/usr/share/plasma/plasmoids/redragon-hs-companion/"
        echo "  -> KDE Plasma widget installed"
    fi

    # ============================================
    # PART 2: Pipewire-DX-Utils (optional)
    # ============================================
    echo ""
    echo "--- Pipewire-DX-Utils Configuration ---"
    echo "This includes:"
    echo "  - Virtual Surround 7.1.4 (requires .sofa file)"
    echo "  - Convolution EQ (requires .wav file from AutoEq)"
    echo "  - Noise Cancellation (requires noise-suppression-for-voice)"
    echo "  - Echo Cancellation (for speakers/open-back headphones)"
    echo ""

    if ask_user "Install Pipewire-DX-Utils configuration files?" "n"; then
        cd "$srcdir/pipewire-dx-utils" || exit 1

        install -d "$pkgdir/etc/pipewire/filter-chain.conf.d/"
        install -d "$pkgdir/etc/pipewire/pipewire.conf.d/"
        install -d "$pkgdir/usr/share/doc/redragon-audio-suite/"

        if [ -d "filter-chain.conf.d" ]; then
            cp -r filter-chain.conf.d/* "$pkgdir/etc/pipewire/filter-chain.conf.d/"
        fi
        if [ -d "pipewire.conf.d" ]; then
            cp -r pipewire.conf.d/* "$pkgdir/etc/pipewire/pipewire.conf.d/"
        fi
        if [ -f "README.md" ]; then
            install -Dm644 README.md "$pkgdir/usr/share/doc/redragon-audio-suite/Pipewire-DX-Utils-README.md"
        fi

        # ============================================
        # PART 3: Setup Script
        # ============================================
        cat > "$pkgdir/usr/bin/redragon-audio-setup" << 'EOF'
#!/bin/bash
# Redragon Audio Suite - Interactive Setup Wizard (Arch Linux only)

set -e

echo "=========================================="
echo "  Redragon Audio Suite - Setup Wizard"
echo "=========================================="
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo) to modify system config files."
    exit 1
fi

CONFIG_DIR="/etc/pipewire/filter-chain.conf.d"
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Error: Pipewire-DX-Utils configs not found at $CONFIG_DIR"
    echo "Please install redragon-audio-suite with Pipewire-DX-Utils first."
    exit 1
fi

ask_user() {
    local question="$1"
    local default="${2:-n}"
    local answer
    while true; do
        read -p "$question [Y/n]: " answer
        answer=${answer:-$default}
        case $answer in
            [Yy]* ) return 0 ;;
            [Nn]* ) return 1 ;;
            * ) echo "Please answer yes or no." ;;
        esac
    done
}

get_node_id() {
    local device_name="$1"
    wpctl status 2>/dev/null | grep -E "│.*$device_name" | head -1 | awk '{print $2}' | tr -d '[]' || echo ""
}

show_resources() {
    echo ""
    echo "=========================================="
    echo "  Recommended Resources for Audio Files"
    echo "=========================================="
    echo ""
    echo "1. SOFA files (Virtual Surround 7.1.4):"
    echo "   - Official SofaConventions database:"
    echo "     https://www.sofaconventions.org/mediawiki/index.php/Downloads"
    echo "   - Direct sample:"
    echo "     https://sofacoustics.org/data/database_sofa_0.6/ari/dtf%20b_nh724.sofa"
    echo ""
    echo "2. HRIR WAV files (Convolution EQ / HeSuVi):"
    echo "   - Airtable HRTF Database:"
    echo "     https://airtable.com/appayGNkn3nSuXkaz/shruimhjdSakUPg2m"
    echo "   - Direct downloads:"
    echo "     * Atmos: https://mega.nz/folder/eS5yXKLJ#4DGd1mPK1uWrZVh_pCmLAg"
    echo "     * CMSS-3D: https://mega.nz/folder/fWokGQKD#EMxOQx6McwxiotxTyXJQSg"
    echo "     * Generic KEMAR: https://stuff.salscheider-online.de/hrir_kemar.tar.gz"
    echo ""
    echo "3. Convolution EQ WAV files:"
    echo "   - AutoEq (generate for your headphone model):"
    echo "     https://autoeq.app"
    echo ""
}

echo "--- Step 1: Detecting Audio Devices ---"
echo "Available audio devices:"
wpctl status | grep -E "(Audio|Sink|Source)" | head -20
echo ""
echo "Please identify your headphone/speaker device name (e.g., 'alsa_output.pci-0000_00_1f.3.analog-stereo'):"
read -p "Device name: " HEADPHONE_DEV
HEADPHONE_NODE=$(get_node_id "$HEADPHONE_DEV")
if [ -z "$HEADPHONE_NODE" ]; then
    echo "Warning: Could not find node ID for '$HEADPHONE_DEV'."
    echo "You can list all devices with: wpctl status"
    read -p "Enter node ID manually (e.g., '42'): " HEADPHONE_NODE
fi
echo "  -> Headphone node ID: $HEADPHONE_NODE"

echo ""
echo "--- Step 2: Virtual Surround 7.1.4 (SOFA) ---"
if ask_user "Enable virtual surround?" "n"; then
    show_resources
    echo "Please provide the path to your .sofa file:"
    read -p "Path (e.g., /path/to/file.sofa): " SOFA_PATH
    if [ -n "$SOFA_PATH" ] && [ -f "$SOFA_PATH" ]; then
        echo "  -> Found: $SOFA_PATH"
    else
        echo "  -> File not found. Skipping."
        SOFA_PATH=""
    fi
else
    SOFA_PATH=""
fi

echo ""
echo "--- Step 3: Convolution EQ (AutoEq WAV) ---"
if ask_user "Enable convolution EQ?" "n"; then
    echo "Generate a .wav file for your headphone model at:"
    echo "  https://autoeq.app"
    read -p "Path to .wav EQ file: " EQ_PATH
    if [ -n "$EQ_PATH" ] && [ -f "$EQ_PATH" ]; then
        echo "  -> Found: $EQ_PATH"
    else
        echo "  -> File not found. Skipping."
        EQ_PATH=""
    fi
else
    EQ_PATH=""
fi

echo ""
echo "--- Step 4: Noise Cancellation (Microphone) ---"
echo "Requires noise-suppression-for-voice (pacman -S noise-suppression-for-voice)"
if ask_user "Enable noise cancellation?" "n"; then
    if command -v noise-suppression-for-voice &>/dev/null || [ -f "/usr/lib/ladspa/noise-suppression-voice.so" ]; then
        NC_ENABLED=true
        echo "  -> noise-suppression found."
    else
        echo "Warning: noise-suppression-for-voice not found."
        echo "Install it with: pacman -S noise-suppression-for-voice"
        if ask_user "Continue without noise cancellation?" "y"; then
            NC_ENABLED=false
        else
            exit 0
        fi
    fi
else
    NC_ENABLED=false
fi

echo ""
echo "--- Step 5: Echo Cancellation (for speakers/open-back headphones) ---"
if ask_user "Enable echo cancellation?" "n"; then
    EC_ENABLED=true
    echo "Please provide your microphone device:"
    read -p "Microphone device name: " MIC_DEV
    MIC_NODE=$(get_node_id "$MIC_DEV")
    if [ -z "$MIC_NODE" ]; then
        read -p "Enter node ID manually: " MIC_NODE
    fi
    echo "  -> Microphone node ID: $MIC_NODE"
else
    EC_ENABLED=false
fi

echo ""
echo "--- Applying Configurations ---"

update_node_target() {
    local file="$1"
    local node_id="$2"
    if [ -f "$file" ]; then
        sed -i "s/node.target = .*/node.target = $node_id/" "$file"
        echo "  Updated $file with node.target = $node_id"
    fi
}

update_file_path() {
    local file="$1"
    local old_path="$2"
    local new_path="$3"
    if [ -f "$file" ]; then
        sed -i "s|$old_path|$new_path|g" "$file"
        echo "  Updated $file: $old_path -> $new_path"
    fi
}

if [ -n "$SOFA_PATH" ]; then
    for conf in "$CONFIG_DIR"/surround-*.conf; do
        if [ -f "$conf" ]; then
            update_file_path "$conf" "/path/to/your/file.sofa" "$SOFA_PATH"
            update_node_target "$conf" "$HEADPHONE_NODE"
        fi
    done
fi

if [ -n "$EQ_PATH" ] && [ -f "$CONFIG_DIR/eq.conf" ]; then
    update_file_path "$CONFIG_DIR/eq.conf" "/path/to/your/eq.wav" "$EQ_PATH"
    update_node_target "$CONFIG_DIR/eq.conf" "$HEADPHONE_NODE"
fi

if [ "$NC_ENABLED" = true ] && [ -f "$CONFIG_DIR/nc.conf" ]; then
    sed -i '/node.target/d' "$CONFIG_DIR/nc.conf"
    LADSPA_PATH=$(find /usr/lib/ladspa /usr/lib64/ladspa -name "noise-suppression*.so" 2>/dev/null | head -1)
    if [ -n "$LADSPA_PATH" ] && [ -f "$LADSPA_PATH" ]; then
        sed -i "s|/path/to/noise-suppression-voice.so|$LADSPA_PATH|g" "$CONFIG_DIR/nc.conf"
        echo "  Updated LADSPA path to $LADSPA_PATH"
    else
        echo "  Warning: LADSPA plugin not found. Update manually in $CONFIG_DIR/nc.conf"
    fi
fi

if [ "$EC_ENABLED" = true ] && [ -f "$CONFIG_DIR/ec.conf" ]; then
    sed -i "0,/node.target = .*/s//node.target = $MIC_NODE/" "$CONFIG_DIR/ec.conf"
    sed -i "0,/node.target = .*/s//node.target = $HEADPHONE_NODE/" "$CONFIG_DIR/ec.conf"
    echo "  Updated ec.conf with mic node $MIC_NODE and headphone node $HEADPHONE_NODE"
fi

echo ""
echo "--- Configuration applied successfully! ---"
echo ""
echo "To activate, enable the filter-chain service:"
echo "  systemctl --user enable --now filter-chain.service"
echo ""
echo "Then set 'Virtual Surround Sink' as default in pavucontrol."
echo ""
echo "Resources:"
echo "  - SOFA: https://www.sofaconventions.org/mediawiki/index.php/Downloads"
echo "  - HRTF DB: https://airtable.com/appayGNkn3nSuXkaz/shruimhjdSakUPg2m"
echo "  - AutoEq: https://autoeq.app"
EOF

        chmod +x "$pkgdir/usr/bin/redragon-audio-setup"
        echo "  -> Setup script installed to /usr/bin/redragon-audio-setup"

        # ============================================
        # PART 4: Documentation
        # ============================================
        cat > "$pkgdir/usr/share/doc/redragon-audio-suite/QUICKSTART.md" << 'EOF'
# Quick Start Guide for Redragon Audio Suite

## After Installation

1. **Run the setup wizard** (as root):
   ```
   sudo redragon-audio-setup
   ```

2. **Enable the filter-chain service**:
   ```
   systemctl --user enable --now filter-chain.service
   ```

3. **Set Virtual Surround Sink as default** in pavucontrol.

## Required Files

- **Virtual Surround (.sofa)**: Download from SofaConventions or Airtable.
- **EQ (.wav)**: Generate from AutoEq for your headphone model.

Rerun `sudo redragon-audio-setup` after downloading.

## GUI Options

- `easyeffects` – graphical audio effects
- `virtual-surround-manager` – manage HeSuVi .wav files

## Resources

- SofaConventions: https://www.sofaconventions.org/mediawiki/index.php/Downloads
- Airtable HRTF DB: https://airtable.com/appayGNkn3nSuXkaz/shruimhjdSakUPg2m
- AutoEq: https://autoeq.app
EOF

        echo "  -> Documentation installed to /usr/share/doc/redragon-audio-suite/"
    fi

    echo ""
    echo "=========================================="
    echo "  Installation complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Enable redragon-hs-companion services:"
    echo "     systemctl --user enable --now redragon-control-daemon.service"
    echo "     systemctl --user enable --now redragon-volume-sync.service"
    echo ""
    echo "  2. Run the setup wizard:"
    echo "     sudo redragon-audio-setup"
    echo ""
    echo "  3. Enable filter-chain service:"
    echo "     systemctl --user enable --now filter-chain.service"
    echo ""
}

# Maintainer: Pakrohk <pakrohk@gmail.com>
pkgname=redragon-audio-suite-git
pkgver=0.3.2
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
    'virtual-surround-manager: GUI to manage HeSuVi .wav files for EasyEffects (RECOMMENDED)'
    'zenity: Graphical file picker for GNOME'
    'kdialog: Graphical file picker for KDE'
)
provides=('redragon-hs-companion')
conflicts=('redragon-hs-companion' 'redragon-hs-companion-git')
source=(
    "redragon-hs-companion::git+https://github.com/cristianocps/redragon-hs-companion.git"
    "pipewire-dx-utils::git+https://github.com/DekoDX/Pipewire-DX-Utils.git"
)
install="${pkgname}.install"
md5sums=('SKIP' 'SKIP')

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
    echo "  2. Pipewire-DX-Utils - Advanced filter-chain configs (optional)"
    echo "  3. Setup script to guide you through configuration"
    echo ""

    # ============================================
    # PART 1: redragon-hs-companion (core)
    # ============================================
    echo "--- Installing redragon-hs-companion ---"
    cd "$srcdir/redragon-hs-companion" || exit 1

    install -d "$pkgdir/usr/bin"

    install -Dm755 redragon-volume "$pkgdir/usr/bin/redragon-volume"
    install -Dm755 redragon_control_daemon.py "$pkgdir/usr/bin/redragon_control_daemon.py"
    install -Dm755 redragon_daemon.py "$pkgdir/usr/bin/redragon_daemon.py"
    install -Dm755 redragon_volume_sync.py "$pkgdir/usr/bin/redragon_volume_sync.py"

    install -d "$pkgdir/usr/lib/systemd/user"
    if [ -f "systemd/redragon-control-daemon.service" ]; then
        install -Dm644 systemd/redragon-control-daemon.service "$pkgdir/usr/lib/systemd/user/redragon-control-daemon.service"
    fi

    echo ""
    echo "--- Desktop Widgets (redragon-hs-companion) ---"
    if [ -d "gnome-extension" ] && ask_user "Install GNOME Shell extension?" "n"; then
        install -d "$pkgdir/usr/share/gnome-shell/extensions/redragon-volume-sync@cristiano"
        cp -r gnome-extension/* "$pkgdir/usr/share/gnome-shell/extensions/redragon-volume-sync@cristiano/"
        echo "  -> GNOME extension installed"
    fi
    if [ -d "cinnamon-applet" ] && ask_user "Install Cinnamon applet?" "n"; then
        install -d "$pkgdir/usr/share/cinnamon/applets/redragon-volume-sync@cristiano"
        cp -r cinnamon-applet/* "$pkgdir/usr/share/cinnamon/applets/redragon-volume-sync@cristiano/"
        echo "  -> Cinnamon applet installed"
    fi
    if [ -d "plasma-widget" ] && ask_user "Install KDE Plasma widget?" "n"; then
        install -d "$pkgdir/usr/share/plasma/plasmoids/redragon-volume-sync@cristiano"
        cp -r plasma-widget/* "$pkgdir/usr/share/plasma/plasmoids/redragon-volume-sync@cristiano/"
        echo "  -> KDE Plasma widget installed"
    fi

    # ============================================
    # PART 2: Pipewire-DX-Utils (optional)
    # ============================================
    echo ""
    echo "--- Pipewire-DX-Utils Configuration ---"
    echo "NOTE: It is recommended to use 'virtual-surround-manager' instead of manual configs."
    echo "If you install Pipewire-DX-Utils, it may conflict with virtual-surround-manager."
    echo ""

    if ask_user "Install Pipewire-DX-Utils configuration files (not recommended)?" "n"; then
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
    fi

    # ============================================
    # PART 3: Setup Script (with GUI file picker)
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
    echo "Some operations may require root privileges."
    echo "Please run with sudo if you need to modify system files."
    echo ""
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

pick_file() {
    local title="$1"
    local filetypes="$2"
    local selected=""
    if command -v zenity &>/dev/null; then
        selected=$(zenity --file-selection --title="$title" --file-filter="$filetypes" 2>/dev/null)
    elif command -v kdialog &>/dev/null; then
        selected=$(kdialog --getopenfilename "$HOME" "$filetypes" --title "$title" 2>/dev/null)
    else
        echo "Graphical file picker not found. Please enter path manually."
        read -p "Path: " selected
    fi
    echo "$selected"
}

echo "--- Step 1: Enable redragon-hs-companion service ---"
if ask_user "Enable redragon-control-daemon service now?" "y"; then
    systemctl --user enable --now redragon-control-daemon.service 2>/dev/null || echo "  -> Failed to enable service (maybe already running)"
    echo "  -> Service enabled"
fi
echo ""

echo "--- Step 2: Virtual Surround (7.1.4) ---"
echo "For virtual surround, you have two options:"
echo "  1. Use virtual-surround-manager (RECOMMENDED) - GUI tool that handles everything"
echo "  2. Manual configuration with Pipewire-DX-Utils (advanced)"
echo ""
if ask_user "Do you have virtual-surround-manager installed?" "n"; then
    echo "Great! Launch it with: virtual-surround-manager"
    echo "Select your headphone as output and choose a preset."
    echo ""
else
    echo "Please install virtual-surround-manager:"
    echo "  yay -S virtual-surround-manager"
    echo ""
    if ask_user "Install virtual-surround-manager now?" "n"; then
        yay -S virtual-surround-manager --noconfirm || echo "Failed to install. Please install manually."
    fi
fi
echo ""

echo "--- Step 3: Convolution EQ (optional) ---"
echo "If you want to use EQ, you need a .wav file from AutoEq."
echo "Go to https://autoeq.app, select your headphone, choose 'Convolution' as app."
echo ""
if ask_user "Do you have a .wav EQ file?" "n"; then
    echo "Please select your .wav file:"
    EQ_FILE=$(pick_file "Select EQ WAV file" "*.wav")
    if [ -n "$EQ_FILE" ] && [ -f "$EQ_FILE" ]; then
        echo "  -> Selected: $EQ_FILE"
        mkdir -p "$HOME/.config/redragon-audio-suite"
        cp "$EQ_FILE" "$HOME/.config/redragon-audio-suite/eq.wav" 2>/dev/null || true
        echo "  -> Copied to ~/.config/redragon-audio-suite/eq.wav"
    else
        echo "  -> No file selected or invalid."
    fi
fi
echo ""

echo "--- Step 4: Noise Cancellation (optional) ---"
if ask_user "Install noise-suppression-for-voice?" "n"; then
    pacman -S noise-suppression-for-voice --noconfirm 2>/dev/null || echo "Failed to install. Please install manually."
fi
echo ""

echo "--- Step 5: Echo Cancellation (optional) ---"
if ask_user "Enable echo cancellation?" "n"; then
    echo "To enable echo cancellation, you need to configure ec.conf manually."
fi
echo ""

echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Launch virtual-surround-manager and configure it."
echo "  2. For EasyEffects integration, install easyeffects and use virtual-surround-manager."
echo "  3. Set 'Virtual Surround Sink' as default in pavucontrol (if using manual config)."
echo ""
echo "Resources:"
echo "  - virtual-surround-manager: https://github.com/Berny23/virtual-surround-manager"
echo "  - AutoEq (WAV for EQ): https://autoeq.app"
EOF

    chmod +x "$pkgdir/usr/bin/redragon-audio-setup"
    echo "  -> Setup script installed to /usr/bin/redragon-audio-setup"

    # ============================================
    # PART 4: Documentation
    # ============================================
    cat > "$pkgdir/usr/share/doc/redragon-audio-suite/QUICKSTART.md" << 'EOF'
# Quick Start Guide for Redragon Audio Suite

## After Installation

1. **Enable the control daemon**:
   ```
   systemctl --user enable --now redragon-control-daemon.service
   ```

2. **Run the setup wizard**:
   ```
   sudo redragon-audio-setup
   ```

## Recommended Setup (with virtual-surround-manager)

1. Install virtual-surround-manager: `yay -S virtual-surround-manager`
2. Launch it and select your headphone as output.
3. Choose a preset (e.g., Atmos, CMSS-3D).
4. If you use EasyEffects, enable integration in virtual-surround-manager.

## Manual Configuration (Pipewire-DX-Utils)

If you prefer manual config, the files are installed at:
- `/etc/pipewire/filter-chain.conf.d/`
- `/etc/pipewire/pipewire.conf.d/`

## Resources

- virtual-surround-manager: https://github.com/Berny23/virtual-surround-manager
- AutoEq (WAV for EQ): https://autoeq.app
- EasyEffects: https://github.com/wwmm/easyeffects
EOF

    echo "  -> Documentation installed to /usr/share/doc/redragon-audio-suite/"

    echo ""
    echo "=========================================="
    echo "  Installation complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Enable redragon-hs-companion service:"
    echo "     systemctl --user enable --now redragon-control-daemon.service"
    echo ""
    echo "  2. Run the setup wizard:"
    echo "     sudo redragon-audio-setup"
    echo ""
}

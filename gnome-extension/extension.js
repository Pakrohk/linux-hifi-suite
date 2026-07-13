import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';

const HiFiIndicator = GObject.registerClass(
class HiFiIndicator extends PanelMenu.Button {
    _init(ext) {
        super._init(0.0, 'HiFi Suite');
        this._ext = ext;
        this._connected = false;
        this._volume = 0;
        this._muted = false;
        this._device = 'Headset';
        this._bus = '';
        this._battery = -1;
        this._batteryCharging = false;
        this._effects = {};
        this._lowLatency = false;
        this._updating = false;

        this._icon = new St.Icon({ icon_name: 'audio-volume-muted-symbolic', style_class: 'system-status-icon' });
        this.add_child(this._icon);

        // Device info
        this._statusLabel = new St.Label({ text: 'Detecting...', style: 'font-size: 9pt; padding: 4px 8px;' });
        let statusItem = new PopupMenu.PopupMenuItem('', { reactive: false, can_focus: false });
        statusItem.add_child(this._statusLabel);
        this.menu.addMenuItem(statusItem);

        // Connection type
        this._connLabel = new St.Label({ text: '', style: 'font-size: 8pt; color: #999; padding: 0 8px 4px 8px;' });
        let connItem = new PopupMenu.PopupMenuItem('', { reactive: false, can_focus: false });
        connItem.add_child(this._connLabel);
        this.menu.addMenuItem(connItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Battery badge
        this._batLabel = new St.Label({ text: '', style: 'font-size: 9pt; padding: 2px 8px;' });
        let batItem = new PopupMenu.PopupMenuItem('', { reactive: false, can_focus: false });
        batItem.add_child(this._batLabel);
        this.menu.addMenuItem(batItem);

        // Volume display
        this._volLabel = new St.Label({ text: '-- %', style: 'font-size: 18pt; font-weight: bold; padding: 6px 0;' });
        let volItem = new PopupMenu.PopupMenuItem('', { reactive: false, can_focus: false });
        volItem.add_child(this._volLabel);
        this.menu.addMenuItem(volItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Slider
        let sliderItem = new PopupMenu.PopupBaseMenuItem({ activate: false });
        this._slider = new Slider.Slider(0);
        this._slider.connect('notify::value', () => this._onSlider());
        sliderItem.add_child(this._slider);
        this.menu.addMenuItem(sliderItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Mute
        this._muteBtn = new PopupMenu.PopupMenuItem('Mute');
        this._muteBtn.connect('activate', () => this._mute());
        this.menu.addMenuItem(this._muteBtn);

        // ── Noise Filter submenu ──
        let noiseSub = new PopupMenu.PopupSubMenuMenuItem('Noise Filter');
        this.menu.addMenuItem(noiseSub);

        this._noiseInputItem = new PopupMenu.PopupSwitchMenuItem('Input (your mic)', false);
        this._noiseInputItem.connect('toggled', (_, on) => {
            this._cmd(on ? 'noise input' : 'noise off');
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => { this._refresh(); return false; });
        });
        noiseSub.menu.addMenuItem(this._noiseInputItem);

        this._noiseOutputItem = new PopupMenu.PopupSwitchMenuItem('Output (other person)', false);
        this._noiseOutputItem.connect('toggled', (_, on) => {
            this._cmd(on ? 'noise output' : 'noise off');
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => { this._refresh(); return false; });
        });
        noiseSub.menu.addMenuItem(this._noiseOutputItem);

        this._noiseBothItem = new PopupMenu.PopupSwitchMenuItem('Both directions', false);
        this._noiseBothItem.connect('toggled', (_, on) => {
            this._cmd(on ? 'noise both' : 'noise off');
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => { this._refresh(); return false; });
        });
        noiseSub.menu.addMenuItem(this._noiseBothItem);

        // ── Effects submenu ──
        let effectsSub = new PopupMenu.PopupSubMenuMenuItem('Effects');
        this.menu.addMenuItem(effectsSub);

        this._effectItems = {};
        ['surround', 'eq'].forEach(f => {
            let item = new PopupMenu.PopupSwitchMenuItem(f.toUpperCase(), false);
            item.connect('toggled', (_, on) => this._toggleEffect(f, on));
            effectsSub.menu.addMenuItem(item);
            this._effectItems[f] = item;
        });

        // ── Low Latency toggle ──
        this._latencyItem = new PopupMenu.PopupSwitchMenuItem('Low Latency Mode', false);
        this._latencyItem.connect('toggled', (_, on) => {
            this._cmd('effect latency ' + (on ? 'on' : 'off'));
            this._lowLatency = on;
        });
        this.menu.addMenuItem(this._latencyItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // ── Reset button ──
        this._resetItem = new PopupMenu.PopupMenuItem('Reset All Filters');
        this._resetItem.connect('activate', () => {
            this._cmd('reset');
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => { this._refresh(); return false; });
        });
        this.menu.addMenuItem(this._resetItem);

        // Scroll to adjust
        this.connect('scroll-event', (_, event) => {
            let dir = event.get_scroll_direction();
            if (dir === Clutter.ScrollDirection.UP) this._changeVol(5);
            else if (dir === Clutter.ScrollDirection.DOWN) this._changeVol(-5);
            return Clutter.EVENT_STOP;
        });

        this._startMonitor();
    }

    _cmd(cmd) {
        try {
            let proc = Gio.Subprocess.new(
                ['hifi-suite', ...cmd.split(' ')],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
            let [, out] = proc.communicate_utf8_sync(null, null);
            return out.trim();
        } catch (e) {
            return '';
        }
    }

    _connLabel(bus) {
        switch (bus) {
            case 'usb': return 'USB / 2.4GHz';
            case 'bluetooth': return 'Bluetooth';
            case 'pci': return '3.5mm / Built-in';
            default: return bus || '';
        }
    }

    _updateIcon() {
        this._icon.icon_name = this._volume === 0 || this._muted
            ? 'audio-volume-muted-symbolic'
            : this._volume < 33 ? 'audio-volume-low-symbolic'
            : this._volume < 66 ? 'audio-volume-medium-symbolic'
            : 'audio-volume-high-symbolic';
    }

    _changeVol(delta) {
        if (!this._connected) return;
        let n = Math.max(0, Math.min(100, this._volume + delta));
        if (n !== this._volume) {
            this._volume = n;
            this._muted = n === 0;
            this._updating = true;
            this._slider.value = n / 100;
            this._updating = false;
            this._volLabel.text = n + ' %';
            this._updateIcon();
            this._cmd('vol ' + n);
        }
    }

    _onSlider() {
        if (this._updating || !this._connected) return;
        let v = Math.round(this._slider.value * 100);
        this._volume = v;
        this._muted = v === 0;
        this._volLabel.text = v + ' %';
        this._updateIcon();
        this._cmd('vol ' + v);
    }

    _mute() {
        if (!this._connected) return;
        this._cmd('vol mute');
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => { this._refresh(); return false; });
    }

    _toggleEffect(name, on) {
        this._cmd(on ? 'effect enable ' + name : 'effect disable ' + name);
    }

    _refresh() {
        let out = this._cmd('status');
        if (!out.includes('device=')) {
            this._connected = false;
            this._statusLabel.text = 'No headset';
            this._connLabel.text = '';
            this._batLabel.text = '';
            return;
        }

        let devMatch = out.match(/device=([^\s]+(?:\s+[^\s]+)*?)\s+(?:id|node)=/);
        let busMatch = out.match(/bus=(\S+)/);
        let volMatch = out.match(/volume=(\d+)%/);
        let batMatch = out.match(/battery=(\d+)/);

        if (devMatch) {
            this._device = devMatch[1];
            this._connected = true;
            this._statusLabel.text = this._device;
        }

        if (busMatch) {
            this._bus = busMatch[1];
            this._connLabel.text = this._connLabel(this._bus);
        }

        if (volMatch) {
            this._volume = parseInt(volMatch[1]);
            this._muted = this._volume === 0;
            this._volLabel.text = this._volume + ' %';
            this._updating = true;
            this._slider.value = this._volume / 100;
            this._updating = false;
            this._updateIcon();
        }

        if (batMatch) {
            this._battery = parseInt(batMatch[1]);
            this._batteryCharging = out.includes('charging=true');
            let icon = this._batteryCharging ? '⚡' : (this._battery < 20 ? '🔴' : this._battery < 50 ? '🟡' : '🟢');
            this._batLabel.text = icon + ' Battery: ' + this._battery + '%';
        } else {
            this._battery = -1;
            this._batLabel.text = '';
        }

        // Refresh effects
        let effOut = this._cmd('effects');
        let lines = effOut.split('\n');
        let ncIn = false, ncOut = false;
        for (let line of lines) {
            if (line.includes('Noise Filter') && line.includes('Input')) ncIn = line.includes('[ON]');
            if (line.includes('Noise Filter') && line.includes('Output')) ncOut = line.includes('[ON]');
            if (line.includes('Low Latency')) this._lowLatency = line.includes('[ON]');
            ['surround', 'eq'].forEach(f => {
                let re = new RegExp('\\b' + f + '\\b.*\\[ON\\]', 'i');
                if (re.test(line) && this._effectItems[f]) this._effectItems[f].setToggleState(true);
                let reOff = new RegExp('\\b' + f + '\\b.*\\[off\\]', 'i');
                if (reOff.test(line) && this._effectItems[f]) this._effectItems[f].setToggleState(false);
            });
        }
        this._noiseInputItem.setToggleState(ncIn);
        this._noiseOutputItem.setToggleState(ncOut);
        this._noiseBothItem.setToggleState(ncIn && ncOut);
        this._latencyItem.setToggleState(this._lowLatency);
    }

    _startMonitor() {
        GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        super.destroy();
    }
});

export default class HiFiSuiteExtension extends Extension {
    enable() {
        this._indicator = new HiFiIndicator(this);
        Main.panel.addToStatusArea('hifi-suite', this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

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
        this._updating = false;

        this._icon = new St.Icon({ icon_name: 'audio-volume-muted-symbolic', style_class: 'system-status-icon' });
        this.add_child(this._icon);

        // Status
        this._statusLabel = new St.Label({ text: 'Detecting...', style: 'font-size: 9pt; padding: 4px 8px;' });
        let statusItem = new PopupMenu.PopupMenuItem('', { reactive: false, can_focus: false });
        statusItem.add_child(this._statusLabel);
        this.menu.addMenuItem(statusItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

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

        // Set default
        let defaultBtn = new PopupMenu.PopupMenuItem('Use as Output');
        defaultBtn.connect('activate', () => this._setDefault());
        this.menu.addMenuItem(defaultBtn);

        // Effects submenu
        let effectsItem = new PopupMenu.PopupMenuItem('Effects');
        this.menu.addMenuItem(effectsItem);
        let effectsSub = new PopupMenu.PopupSubMenuMenuItem('Effects');
        this.menu.addMenuItem(effectsSub);

        ['surround', 'nc', 'eq', 'ec'].forEach(f => {
            let item = new PopupMenu.PopupSwitchMenuItem(f.toUpperCase(), false);
            item.connect('toggled', (_, on) => this._toggleFilter(f, on));
            effectsSub.menu.addMenuItem(item);
        });

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

    _setDefault() {
        if (!this._connected) return;
        this._cmd('status');
    }

    _toggleFilter(name, on) {
        this._cmd(on ? 'enable ' + name : 'disable ' + name);
    }

    _refresh() {
        let out = this._cmd('vol get');
        let m = out.match(/(\d+)%/);
        if (m) {
            this._volume = parseInt(m[1]);
            this._muted = this._volume === 0;
            this._volLabel.text = this._volume + ' %';
            this._updating = true;
            this._slider.value = this._volume / 100;
            this._updating = false;
            this._updateIcon();
        }
    }

    _startMonitor() {
        GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            if (this._connected) {
                this._refresh();
            } else {
                let out = this._cmd('status');
                if (out.includes('device=')) {
                    let m = out.match(/device=([^\s]+)/);
                    if (m) {
                        this._device = m[1];
                        this._connected = true;
                        this._statusLabel.text = this._device;
                        this._refresh();
                    }
                } else {
                    this._statusLabel.text = 'No headset';
                }
            }
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

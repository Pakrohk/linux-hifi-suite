const Applet = imports.ui.applet;
const Main = imports.ui.main;
const GLib = imports.gi.GLib;
const Gio = imports.gi.Gio;
const Lang = imports.lang;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;

const UUID = "hifi-suite@cinnamon";

function MyApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

MyApplet.prototype = {
    __proto__: Applet.IconApplet.prototype,

    _init: function(metadata, orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);

        this.set_applet_icon_symbolic_name("audio-headphones");
        this.set_applet_tooltip("HiFi Suite");

        this._connected = false;
        this._volume = 0;
        this._muted = false;
        this._bus = "";
        this._battery = -1;
        this._lowLatency = false;

        // Menu
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this._menu = new PopupMenu.PopupMenu(this, orientation);
        this.menuManager.addMenu(this._menu);

        // Device name
        this._statusItem = new PopupMenu.PopupMenuItem("Detecting...", { reactive: false });
        this._menu.addMenuItem(this._statusItem);

        // Connection type
        this._connItem = new PopupMenu.PopupMenuItem("", { reactive: false });
        this._connItem.label.set_style("font-size: 9pt; color: #999;");
        this._menu.addMenuItem(this._connItem);
        this._menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Battery
        this._batItem = new PopupMenu.PopupMenuItem("", { reactive: false });
        this._menu.addMenuItem(this._batItem);

        // Volume label
        this._volItem = new PopupMenu.PopupMenuItem("-- %", { reactive: false });
        this._menu.addMenuItem(this._volItem);
        this._menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Mute
        this._muteItem = new PopupMenu.PopupMenuItem("Mute");
        this._menu.addMenuItem(this._muteItem);
        this._muteItem.connect("activate", Lang.bind(this, this._toggleMute));

        // ── Noise Filter submenu ──
        this._noiseItem = new PopupMenu.PopupSubMenuMenuItem("Noise Filter");
        this._menu.addMenuItem(this._noiseItem);

        this._noiseInputItem = new PopupMenu.PopupSwitchMenuItem("Input (your mic)", false);
        this._noiseInputItem.connect("toggled", Lang.bind(this, function(_, on) {
            this._cmd(on ? "noise input" : "noise off");
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, Lang.bind(this, function() { this._refresh(); }));
        }));
        this._noiseItem.menu.addMenuItem(this._noiseInputItem);

        this._noiseOutputItem = new PopupMenu.PopupSwitchMenuItem("Output (other person)", false);
        this._noiseOutputItem.connect("toggled", Lang.bind(this, function(_, on) {
            this._cmd(on ? "noise output" : "noise off");
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, Lang.bind(this, function() { this._refresh(); }));
        }));
        this._noiseItem.menu.addMenuItem(this._noiseOutputItem);

        this._noiseBothItem = new PopupMenu.PopupSwitchMenuItem("Both directions", false);
        this._noiseBothItem.connect("toggled", Lang.bind(this, function(_, on) {
            this._cmd(on ? "noise both" : "noise off");
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, Lang.bind(this, function() { this._refresh(); }));
        }));
        this._noiseItem.menu.addMenuItem(this._noiseBothItem);

        // ── Effects submenu ──
        this._effectsItem = new PopupMenu.PopupSubMenuMenuItem("Effects");
        this._menu.addMenuItem(this._effectsItem);

        this._effectItems = {};
        ["surround", "eq"].forEach(Lang.bind(this, function(f) {
            let item = new PopupMenu.PopupSwitchMenuItem(f.toUpperCase(), false);
            item.connect("toggled", Lang.bind(this, function(_, on) {
                this._cmd(on ? "effect enable " + f : "effect disable " + f);
            }));
            this._effectsItem.menu.addMenuItem(item);
            this._effectItems[f] = item;
        }));

        // ── Low Latency toggle ──
        this._latencyItem = new PopupMenu.PopupSwitchMenuItem("Low Latency Mode", false);
        this._latencyItem.connect("toggled", Lang.bind(this, function(_, on) {
            this._cmd("effect latency " + (on ? "on" : "off"));
            this._lowLatency = on;
        }));
        this._menu.addMenuItem(this._latencyItem);

        this._menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // ── Reset button ──
        this._resetItem = new PopupMenu.PopupMenuItem("Reset All Filters");
        this._resetItem.connect("activate", Lang.bind(this, function() {
            this._cmd("reset");
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, Lang.bind(this, function() { this._refresh(); }));
        }));
        this._menu.addMenuItem(this._resetItem);

        // Scroll to change volume
        this.actor.connect("scroll-event", Lang.bind(this, this._onScroll));

        // Start monitoring
        this._startMonitor();
    },

    _cmd: function(cmd) {
        try {
            let proc = Gio.Subprocess.new(
                ["hifi-suite"].concat(cmd.split(" ")),
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
            let [, out] = proc.communicate_utf8_sync(null, null);
            return out.trim();
        } catch (e) {
            return "";
        }
    },

    _connLabel: function(bus) {
        switch (bus) {
            case "usb": return "USB / 2.4GHz";
            case "bluetooth": return "Bluetooth";
            case "pci": return "3.5mm / Built-in";
            default: return bus || "";
        }
    },

    _toggleMute: function() {
        if (!this._connected) return;
        this._cmd("vol mute");
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, Lang.bind(this, function() {
            this._refresh();
        }));
    },

    _onScroll: function(actor, event) {
        if (!this._connected) return;
        let direction = event.get_scroll_direction();
        let delta = direction === 1 ? 5 : -5;
        let newVol = Math.max(0, Math.min(100, this._volume + delta));
        if (newVol !== this._volume) {
            this._volume = newVol;
            this._muted = newVol === 0;
            this._volItem.label.set_text(newVol + " %");
            this._cmd("vol " + newVol);
        }
    },

    _refresh: function() {
        let out = this._cmd("status");
        if (out.indexOf("device=") < 0) {
            this._connected = false;
            this._statusItem.label.set_text("No headset");
            this._connItem.label.set_text("");
            this._batItem.label.set_text("");
            return;
        }

        let devMatch = out.match(/device=([^\s]+(?:\s+[^\s]+)*?)\s+(?:id|node)=/);
        let busMatch = out.match(/bus=(\S+)/);
        let volMatch = out.match(/volume=(\d+)%/);
        let batMatch = out.match(/battery=(\d+)/);

        if (devMatch) {
            this._connected = true;
            this._statusItem.label.set_text(devMatch[1]);
        }

        if (busMatch) {
            this._bus = busMatch[1];
            this._connItem.label.set_text(this._connLabel(this._bus));
        }

        if (volMatch) {
            this._volume = parseInt(volMatch[1]);
            this._muted = this._volume === 0;
            this._volItem.label.set_text(this._volume + " %");
        }

        if (batMatch) {
            this._battery = parseInt(batMatch[1]);
            let charging = out.indexOf("charging=true") >= 0;
            let icon = charging ? "\u26A1" : (this._battery < 20 ? "\uD83D\uDD34" : this._battery < 50 ? "\uD83D\uDFE1" : "\uD83D\uDFE2");
            this._batItem.label.set_text(icon + " Battery: " + this._battery + "%");
        } else {
            this._battery = -1;
            this._batItem.label.set_text("");
        }

        // Refresh effects
        let effOut = this._cmd("effects");
        let lines = effOut.split("\n");
        let ncIn = false, ncOut = false;
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].indexOf("Noise Filter") >= 0 && lines[i].indexOf("Input") >= 0) ncIn = lines[i].indexOf("[ON]") >= 0;
            if (lines[i].indexOf("Noise Filter") >= 0 && lines[i].indexOf("Output") >= 0) ncOut = lines[i].indexOf("[ON]") >= 0;
            if (lines[i].indexOf("Low Latency") >= 0) this._lowLatency = lines[i].indexOf("[ON]") >= 0;
            let self = this;
            ["surround", "eq"].forEach(function(f) {
                let re = new RegExp("\\b" + f + "\\b.*(\\[ON\\]|\\[off\\])", "i");
                let m = lines[i].match(re);
                if (m && self._effectItems[f]) {
                    self._effectItems[f].setToggleState(m[1] === "[ON]");
                }
            });
        }
        this._noiseInputItem.setToggleState(ncIn);
        this._noiseOutputItem.setToggleState(ncOut);
        this._noiseBothItem.setToggleState(ncIn && ncOut);
        this._latencyItem.setToggleState(this._lowLatency);
    },

    _startMonitor: function() {
        GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, Lang.bind(this, function() {
            this._refresh();
            return true;
        }));
    },

    on_applet_clicked: function() {
        this._menu.toggle();
    },

    on_applet_removed_from_panel: function() {
        // Cleanup
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new MyApplet(metadata, orientation, panel_height, instance_id);
}

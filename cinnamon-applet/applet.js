const Applet = imports.ui.applet;
const Main = imports.ui.main;
const GLib = imports.gi.GLib;
const Gio = imports.gi.Gio;
const Lang = imports.lang;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;
const Settings = imports.ui.settings;

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

        // Menu
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this._menu = new PopupMenu.PopupMenu(this, orientation);
        this.menuManager.addMenu(this._menu);

        // Status
        this._statusItem = new PopupMenu.PopupMenuItem("Detecting...", { reactive: false });
        this._menu.addMenuItem(this._statusItem);
        this._menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Volume label
        this._volItem = new PopupMenu.PopupMenuItem("-- %", { reactive: false });
        this._menu.addMenuItem(this._volItem);
        this._menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Mute
        this._muteItem = new PopupMenu.PopupMenuItem("Mute");
        this._menu.addMenuItem(this._muteItem);
        this._muteItem.connect("activate", Lang.bind(this, this._toggleMute));

        // Effects submenu
        this._effectsItem = new PopupMenu.PopupSubMenuMenuItem("Effects");
        this._menu.addMenuItem(this._effectsItem);

        ["surround", "nc", "eq", "ec"].forEach(Lang.bind(this, function(f) {
            let item = new PopupMenu.PopupSwitchMenuItem(f.toUpperCase(), false);
            item.connect("toggled", Lang.bind(this, function(_, on) {
                this._cmd(on ? "enable " + f : "disable " + f);
            }));
            this._effectsItem.menu.addMenuItem(item);
        }));

        // Default output
        let defaultItem = new PopupMenu.PopupMenuItem("Use as Output");
        this._menu.addMenuItem(defaultItem);
        defaultItem.connect("activate", Lang.bind(this, function() {
            this._cmd("status");
        }));

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
        let delta = direction === 1 ? 5 : -5; // UP=1, DOWN=-1 in some Cinnamon versions
        let newVol = Math.max(0, Math.min(100, this._volume + delta));
        if (newVol !== this._volume) {
            this._volume = newVol;
            this._muted = newVol === 0;
            this._volItem.label.set_text(newVol + " %");
            this._cmd("vol " + newVol);
        }
    },

    _refresh: function() {
        let out = this._cmd("vol get");
        let m = out.match(/(\d+)%/);
        if (m) {
            this._volume = parseInt(m[1]);
            this._muted = this._volume === 0;
            this._volItem.label.set_text(this._volume + " %");
        }
    },

    _startMonitor: function() {
        GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, Lang.bind(this, function() {
            if (this._connected) {
                this._refresh();
            } else {
                let out = this._cmd("status");
                if (out.indexOf("device=") >= 0) {
                    let m = out.match(/device=(\S+)/);
                    if (m) {
                        this._connected = true;
                        this._statusItem.label.set_text(m[1]);
                        this._refresh();
                    }
                } else {
                    this._statusItem.label.set_text("No headset");
                }
            }
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

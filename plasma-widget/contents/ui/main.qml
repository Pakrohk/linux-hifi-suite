import QtQuick
import QtQuick.Layouts
import QtCore
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property bool isConnected: false
    property string deviceName: "Headset"
    property string connectionType: ""
    property int currentVolume: 0
    property bool isMuted: false
    property int batteryLevel: -1
    property bool batteryCharging: false
    property var effectStates: ({})
    property bool updatingSlider: false

    preferredRepresentation: compactRepresentation

    // ── Command Execution ───────────────────────────────────────────────
    Process {
        id: process
        property string pendingCmd: ""
        onFinished: function(exitCode, exitStatus) {
            if (exitCode === 0 && stdout !== "")
                handleOutput(pendingCmd, stdout.toString())
        }
    }

    function run(cmd) {
        process.pendingCmd = cmd
        process.start("sh", ["-c", cmd])
    }

    function handleOutput(cmd, out) {
        if (cmd.includes("status")) {
            // Parse: device=H888 id=56 node=... bus=usb volume=80%
            var devMatch = out.match(/device=([^\s]+(?:\s+[^\s]+)*?)\s+(?:id|node)=/)
            var busMatch = out.match(/bus=(\S+)/)
            var volMatch = out.match(/volume=(\d+)%/)
            var batMatch = out.match(/battery=(\d+)/)

            if (devMatch) {
                deviceName = devMatch[1]
                isConnected = true
                connectionType = busMatch ? busMatch[1] : ""
            } else {
                isConnected = false
                deviceName = "Headset"
                connectionType = ""
            }

            if (volMatch) {
                currentVolume = parseInt(volMatch[1])
                isMuted = currentVolume === 0
                updatingSlider = true
                slider.value = currentVolume
                updatingSlider = false
            }

            if (batMatch) {
                batteryLevel = parseInt(batMatch[1])
                batteryCharging = out.includes("charging=true")
            } else {
                batteryLevel = -1
            }
        } else if (cmd.includes("vol get")) {
            var v = out.match(/(\d+)/)
            if (v) {
                currentVolume = parseInt(v[1])
                isMuted = currentVolume === 0
                updatingSlider = true
                slider.value = currentVolume
                updatingSlider = false
            }
        } else if (cmd.includes("effects")) {
            // Parse effect states from hifi-suite effects output
            var lines = out.split("\n")
            for (var i = 0; i < lines.length; i++) {
                var effMatch = lines[i].match(/^\s*(nc|surround|surround714|eq|ec)\s+(ON|off)/)
                if (effMatch) {
                    effectStates[effMatch[1]] = effMatch[2] === "ON"
                }
            }
            effectStatesChanged()
        }
    }

    // ── Actions ─────────────────────────────────────────────────────────
    function updateVol() {
        if (isConnected) run("hifi-suite vol get")
    }

    function detect() {
        run("hifi-suite status")
        run("hifi-suite effects")
    }

    function setVol(v) {
        if (isConnected) run("hifi-suite vol " + Math.round(v))
    }

    function toggleMute() {
        if (isConnected) {
            run("hifi-suite vol mute")
            muteTimer.restart()
        }
    }

    function toggleEffect(name) {
        var on = !effectStates[name]
        run("hifi-suite " + (on ? "enable " : "disable ") + name)
        effectStates[name] = on
        effectStatesChanged()
    }

    function connectionLabel() {
        switch (connectionType) {
            case "usb": return "USB / 2.4GHz"
            case "bluetooth": return "Bluetooth"
            case "pci": return "3.5mm / Built-in"
            default: return connectionType || ""
        }
    }

    // ── Timers ──────────────────────────────────────────────────────────
    Timer {
        id: pollTimer
        interval: 3000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: isConnected ? updateVol() : detect()
    }
    Timer { id: muteTimer; interval: 100; onTriggered: updateVol() }
    Timer { id: debounceTimer; interval: 20; onTriggered: setVol(slider.value) }

    // ── Compact Representation (Panel Icon) ─────────────────────────────
    compactRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.iconSizes.small
        Layout.minimumHeight: Kirigami.Units.iconSizes.small

        Kirigami.Icon {
            anchors.fill: parent
            source: currentVolume === 0 || isMuted ? "audio-volume-muted-symbolic"
                : currentVolume < 33 ? "audio-volume-low-symbolic"
                : currentVolume < 66 ? "audio-volume-medium-symbolic"
                : "audio-volume-high-symbolic"
        }

        // Battery indicator dot
        Rectangle {
            visible: batteryLevel >= 0
            width: 6; height: 6; radius: 3
            anchors { top: parent.top; right: parent.right }
            color: batteryLevel < 20 ? Kirigami.Theme.negativeTextColor
                : batteryLevel < 50 ? Kirigami.Theme.neutralTextColor
                : Kirigami.Theme.positiveTextColor
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
            onClicked: function(mouse) {
                if (mouse.button === Qt.LeftButton) root.expanded = !root.expanded
                else toggleMute()
            }
            onWheel: function(w) {
                if (!isConnected) return
                var d = w.angleDelta.y > 0 ? 5 : -5
                var n = Math.max(0, Math.min(100, currentVolume + d))
                if (n !== currentVolume) {
                    currentVolume = n
                    isMuted = n === 0
                    updatingSlider = true
                    slider.value = n
                    updatingSlider = false
                    setVol(n)
                }
            }
        }
    }

    // ── Full Representation (Popup) ─────────────────────────────────────
    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: 300
        Layout.preferredHeight: 360
        spacing: 0

        // Header: Device name + connection type
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            Kirigami.Icon {
                source: "audio-headphones"
                implicitWidth: 20; implicitHeight: 20
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                PlasmaComponents3.Label {
                    text: isConnected ? deviceName : "No headset"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                PlasmaComponents3.Label {
                    visible: isConnected && connectionLabel() !== ""
                    text: connectionLabel()
                    font.pointSize: Kirigami.Theme.smallFont.pointSize * 0.85
                    color: Kirigami.Theme.disabledTextColor
                    Layout.fillWidth: true
                }
            }

            // Battery badge
            Rectangle {
                visible: batteryLevel >= 0
                width: batteryLabel.width + 12
                height: 20
                radius: 10
                color: batteryLevel < 20 ? Kirigami.Theme.negativeTextColor
                    : batteryLevel < 50 ? Kirigami.Theme.neutralTextColor
                    : Kirigami.Theme.positiveTextColor

                RowLayout {
                    anchors.centerIn: parent
                    spacing: 2

                    Kirigami.Icon {
                        source: batteryCharging ? "battery-flash-symbolic" : "battery-symbolic"
                        implicitWidth: 12; implicitHeight: 12
                    }

                    PlasmaComponents3.Label {
                        id: batteryLabel
                        text: batteryLevel + "%"
                        font.pointSize: Kirigami.Theme.smallFont.pointSize * 0.8
                        color: "white"
                    }
                }
            }
        }

        PlasmaComponents3.Separator { Layout.fillWidth: true }

        // Volume display
        PlasmaComponents3.Label {
            text: currentVolume + " %"
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.5
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
        }

        PlasmaComponents3.Separator { Layout.fillWidth: true }

        // Volume slider
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            Kirigami.Icon { source: "audio-volume-low"; implicitWidth: 16; implicitHeight: 16 }

            PlasmaComponents3.Slider {
                id: slider
                Layout.fillWidth: true
                from: 0; to: 100; value: currentVolume; stepSize: 1
                onMoved: {
                    if (updatingSlider) return
                    currentVolume = Math.round(value)
                    isMuted = currentVolume === 0
                    debounceTimer.restart()
                }
            }

            Kirigami.Icon { source: "audio-volume-high"; implicitWidth: 16; implicitHeight: 16 }
        }

        PlasmaComponents3.Separator { Layout.fillWidth: true }

        // Mute button
        PlasmaComponents3.Button {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            icon.name: isMuted ? "audio-volume-muted" : "audio-volume-high"
            text: isMuted ? "Unmute" : "Mute"
            onClicked: toggleMute()
        }

        PlasmaComponents3.Separator { Layout.fillWidth: true }

        // Effects section
        PlasmaComponents3.Label {
            text: "Effects"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            font.bold: true
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing
        }

        Grid {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            columns: 2
            rowSpacing: 4
            columnSpacing: 4

            Repeater {
                model: ListModel {
                    ListElement { key: "nc"; label: "NC"; icon: "noise-canceling" }
                    ListElement { key: "surround"; label: "7.1"; icon: "speaker" }
                    ListElement { key: "eq"; label: "EQ"; icon: "view-statistics" }
                    ListElement { key: "ec"; label: "EC"; icon: "microphone" }
                }

                PlasmaComponents3.ToolButton {
                    required property var model
                    Layout.fillWidth: true
                    text: model.label
                    icon.name: model.icon
                    checkable: true
                    checked: effectStates[model.key] || false
                    onClicked: toggleEffect(model.key)
                }
            }
        }

        Item { Layout.fillHeight: true }
    }

    Component.onCompleted: detect()
}

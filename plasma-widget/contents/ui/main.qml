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
    property bool lowLatency: false
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
        } else if (cmd.includes("effects")) {
            var lines = out.split("\n")
            for (var i = 0; i < lines.length; i++) {
                // Match: [ON]  Noise Filter — Input (your mic, outgoing)
                //        [off] 7.1 Surround
                //        [ON]  Low Latency Mode (quantum=64, rt priority)
                if (lines[i].includes("Low Latency")) {
                    lowLatency = lines[i].includes("[ON]")
                }
                var ncIn = lines[i].includes("Noise Filter") && lines[i].includes("Input")
                var ncOut = lines[i].includes("Noise Filter") && lines[i].includes("Output")
                var surr = lines[i].includes("7.1 Surround")
                var eq = lines[i].includes("Equalizer")
                var ec = lines[i].includes("Echo Cancellation")
                if (ncIn) effectStates["nc_in"] = lines[i].includes("[ON]")
                if (ncOut) effectStates["nc_out"] = lines[i].includes("[ON]")
                if (ec) effectStates["ec"] = lines[i].includes("[ON]")
                if (surr) effectStates["surround"] = lines[i].includes("[ON]")
                if (eq) effectStates["eq"] = lines[i].includes("[ON]")
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

    function toggleNoise(mode) {
        if (effectStates["nc_" + mode]) {
            run("hifi-suite noise off")
            effectStates["nc_in"] = false
            effectStates["nc_out"] = false
        } else {
            run("hifi-suite noise " + mode)
            if (mode === "both") {
                effectStates["nc_in"] = true
                effectStates["nc_out"] = true
            } else if (mode === "input") {
                effectStates["nc_in"] = true
                effectStates["nc_out"] = false
            } else if (mode === "output") {
                effectStates["nc_in"] = false
                effectStates["nc_out"] = true
            }
        }
        effectStatesChanged()
        // Refresh actual state
        refreshTimer.restart()
    }

    function toggleEffect(name) {
        var on = !effectStates[name]
        run("hifi-suite " + (on ? "effect enable " : "effect disable ") + name)
        effectStates[name] = on
        effectStatesChanged()
    }

    function toggleLatency() {
        run("hifi-suite effect latency " + (lowLatency ? "off" : "on"))
        lowLatency = !lowLatency
    }

    function resetAll() {
        run("hifi-suite reset")
        effectStates = {}
        lowLatency = false
        effectStatesChanged()
        refreshTimer.restart()
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
    Timer { id: refreshTimer; interval: 500; onTriggered: detect() }

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
        Layout.preferredWidth: 320
        Layout.preferredHeight: 520
        spacing: 0

        // Header
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
                width: batteryLabel.width + 12; height: 20; radius: 10
                color: batteryLevel < 20 ? Kirigami.Theme.negativeTextColor
                    : batteryLevel < 50 ? Kirigami.Theme.neutralTextColor
                    : Kirigami.Theme.positiveTextColor
                RowLayout {
                    anchors.centerIn: parent; spacing: 2
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

        // Volume
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

        // Noise Filter section
        PlasmaComponents3.Label {
            text: "Noise Filter"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            font.bold: true
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            spacing: 4

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "Input"
                icon.name: "microphone"
                checkable: true
                checked: effectStates["nc_in"] || false
                onClicked: toggleNoise("input")
                PlasmaComponents3.ToolTip {
                    text: "Filter noise from YOUR mic"
                }
            }

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "Output"
                icon.name: "speaker"
                checkable: true
                checked: effectStates["nc_out"] || false
                onClicked: toggleNoise("output")
                PlasmaComponents3.ToolTip {
                    text: "Filter noise from other person"
                }
            }

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "Both"
                icon.name: "audio-headphones"
                checkable: true
                checked: (effectStates["nc_in"] || false) && (effectStates["nc_out"] || false)
                onClicked: toggleNoise("both")
                PlasmaComponents3.ToolTip {
                    text: "Filter both directions"
                }
            }
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

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "7.1 Surround"
                icon.name: "speaker"
                checkable: true
                checked: effectStates["surround"] || false
                onClicked: toggleEffect("surround")
            }

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "EQ"
                icon.name: "view-statistics"
                checkable: true
                checked: effectStates["eq"] || false
                onClicked: toggleEffect("eq")
            }

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: "Echo Cancel"
                icon.name: "microphone"
                checkable: true
                checked: effectStates["ec"] || false
                onClicked: toggleEffect("ec")
                PlasmaComponents3.ToolTip {
                    text: "Cancel echo on your mic (works with noise filter)"
                }
            }
        }

        PlasmaComponents3.Separator { Layout.fillWidth: true }

        // Low Latency + Reset row
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            spacing: 4

            PlasmaComponents3.ToolButton {
                Layout.fillWidth: true
                text: lowLatency ? "Latency: ON" : "Latency: OFF"
                icon.name: "speedometer"
                checkable: true
                checked: lowLatency
                onClicked: toggleLatency()
                PlasmaComponents3.ToolTip {
                    text: lowLatency ? "Disable low-latency mode" : "Enable low-latency (~3ms)"
                }
            }

            PlasmaComponents3.Button {
                Layout.fillWidth: true
                text: "Reset All"
                icon.name: "edit-clear"
                onClicked: resetAll()
                PlasmaComponents3.ToolTip {
                    text: "Remove all filters, restore defaults"
                }
            }
        }

        Item { Layout.fillHeight: true }
    }

    Component.onCompleted: detect()
}

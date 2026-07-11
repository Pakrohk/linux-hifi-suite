import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property bool isConnected: false
    property string deviceName: "Headset"
    property int currentVolume: 0
    property bool isMuted: false
    property bool updatingSlider: false

    preferredRepresentation: compactRepresentation

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(src, data) {
            if (data["exit code"] === 0 && data["stdout"])
                handleOutput(src, data["stdout"])
            disconnectSource(src)
        }
        function run(cmd) { connectSource(cmd) }
    }

    function handleOutput(cmd, out) {
        if (cmd.includes("status")) {
            var m = out.match(/device=([^\s]+(?:\s+[^\s]+)*?)\s+card=/)
            if (m) { deviceName = m[1]; isConnected = true }
            else isConnected = false
        } else if (cmd.includes("get")) {
            var v = out.match(/Volume:\s*(\d+)%/)
            if (v) {
                currentVolume = parseInt(v[1])
                isMuted = currentVolume === 0
                updatingSlider = true; slider.value = currentVolume; updatingSlider = false
            }
        }
    }

    function updateVol() { if (isConnected) exec.run("hifi-suite vol get") }
    function detect() { exec.run("hifi-suite status") }
    function setVol(v) { if (isConnected) exec.run("hifi-suite vol " + Math.round(v)) }
    function toggleMute() { if (isConnected) { exec.run("hifi-suite vol mute"); muteTimer.restart() } }
    function toggleEffect(name, on) { exec.run("hifi-suite " + (on ? "enable " : "disable ") + name) }

    Timer { id: pollTimer; interval: 3000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: isConnected ? updateVol() : detect() }
    Timer { id: muteTimer; interval: 100; onTriggered: updateVol() }
    Timer { id: debounceTimer; interval: 20; onTriggered: setVol(slider.value) }

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
                    currentVolume = n; isMuted = n === 0
                    updatingSlider = true; slider.value = n; updatingSlider = false
                    setVol(n)
                }
            }
        }
    }

    fullRepresentation: Item {
        Layout.preferredWidth: 280
        Layout.preferredHeight: 320

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing

            PlasmaComponents3.Label {
                text: isConnected ? deviceName : "No headset"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                Layout.fillWidth: true
            }

            PlasmaComponents3.Separator { Layout.fillWidth: true }

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

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
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

            PlasmaComponents3.Button {
                Layout.fillWidth: true
                text: isMuted ? "Unmute" : "Mute"
                onClicked: toggleMute()
            }

            // Effects section
            PlasmaComponents3.Separator { Layout.fillWidth: true }

            PlasmaComponents3.Label {
                text: "Effects"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                font.bold: true
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                Repeater {
                    model: ["surround", "nc", "eq", "ec"]
                    PlasmaComponents3.Button {
                        text: modelData.toUpperCase()
                        checkable: true
                        onClicked: toggleEffect(modelData, checked)
                        Layout.fillWidth: true
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    Component.onCompleted: detect()
}

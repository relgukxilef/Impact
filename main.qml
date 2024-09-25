import QtQuick
import QtQuick.Window
import QtMultimedia

Window {
    property var model
    property color accentColor: "#ef2d56"

    width: 720
    height: 1280
    visible: true
    title: qsTr("Impact")
    color: dropArea.containsDrag ? accentColor : "black"

    DropArea {
        id: dropArea
        anchors.fill: parent

        onDropped: (drop) => {
            var file = drop.urls[0]
            model.drop(file, videoOutput)
        }
    }

    VideoOutput {
        id: videoOutput
        anchors.fill: parent
    }
}

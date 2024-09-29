import QtQuick
import QtQuick.Window
import QtMultimedia
import QtQuick.Controls

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
            textLabel.visible = false;
        }

        Text {
            id: textLabel
            text: qsTr("Drop a video file here.")
            color: "white"
            anchors.centerIn: parent
        }
    }

    VideoOutput {
        id: videoOutput
        anchors.fill: parent
    }

    Column {
        anchors.fill: parent

        Row {
            height: 32

            Button {
                text: qsTr("Save")
            }
        }
    }
}

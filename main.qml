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
        }

        Text {
            id: textLabel
            text: qsTr(model.label)
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

            // TODO: add buttons
        }
    }

    Rectangle {
        width: 20
        height: 20
        color: accentColor

        anchors.centerIn: parent

        RotationAnimation on rotation {
            loops: Animation.Infinite
            easing.type: Easing.InOutQuad
            from: 0
            to: 360
            duration: 1000
        }

        visible: model.progress == 0
    }

    Rectangle {
        width: parent.width * model.progress
        height: 10
        color: accentColor

        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left

        visible: model.progress != 1
    }
}

import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property var modelData: ({})
  property real cardWidth: 120
  property real cardHeight: 82

  signal applied(string path)
  signal favoriteToggled(string id)
  signal deleted(string id)
  signal revealed(string path)

  width: cardWidth
  height: cardHeight

  readonly property bool isCurrent: modelData && modelData.isCurrent === true
  readonly property bool isFavorite: modelData && modelData.favorite === true
  readonly property bool canDelete: modelData && modelData.canDelete === true && !isCurrent
  readonly property string thumbSource: {
    if (!modelData) return ""
    if (modelData.thumbnail && modelData.thumbnail.length > 0) {
      return "file://" + modelData.thumbnail
    }
    return modelData.path ? "file://" + modelData.path : ""
  }

  Rectangle {
    id: cardBackground
    anchors.fill: parent
    radius: Style.cornerRadius
    color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.05)
    clip: true

    border.color: root.isCurrent
      ? Commons.Color.accent
      : (cardMouse.containsMouse ? Commons.Color.popups.border : Qt.rgba(Commons.Color.popups.border.r, Commons.Color.popups.border.g, Commons.Color.popups.border.b, 0.4))
    border.width: root.isCurrent ? Math.max(2, Style.space(2)) : 1

    Behavior on border.color { ColorAnimation { duration: 120 } }

    // Wallpaper Thumbnail
    Image {
      id: thumbImage
      anchors.fill: parent
      anchors.margins: root.isCurrent ? 2 : 1
      source: root.thumbSource
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: true
      opacity: cardMouse.containsMouse ? 1.0 : 0.92

      Behavior on opacity { NumberAnimation { duration: 100 } }
    }

    // Gradient overlay for bottom title legibility
    Rectangle {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: Style.space(24)
      gradient: Gradient {
        GradientStop { position: 0.0; color: "transparent" }
        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.75) }
      }
    }

    // Name label
    Text {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: Style.space(4)
      text: modelData ? (modelData.name || modelData.filename || "") : ""
      color: "#ffffff"
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      elide: Text.ElideRight
      horizontalAlignment: Text.AlignLeft
    }

    // Active Checkmark Badge (Top Left)
    Rectangle {
      visible: root.isCurrent
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.margins: Style.space(4)
      width: Style.space(18)
      height: Style.space(18)
      radius: Style.space(9)
      color: Commons.Color.accent

      Text {
        anchors.centerIn: parent
        text: "󰄬"
        color: Commons.Color.accentForeground || "#ffffff"
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        font.bold: true
      }
    }

    // Card Action Buttons (Top Right, visible on hover or if favorite)
    Row {
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Style.space(4)
      spacing: Style.space(3)
      opacity: (cardMouse.containsMouse || root.isFavorite) ? 1.0 : 0.0

      Behavior on opacity { NumberAnimation { duration: 120 } }

      // Favorite Button
      Rectangle {
        width: Style.space(20)
        height: Style.space(20)
        radius: Style.space(10)
        color: favMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.8) : Qt.rgba(0, 0, 0, 0.5)

        Text {
          anchors.centerIn: parent
          text: root.isFavorite ? "󰋑" : "󰋔"
          color: root.isFavorite ? "#ff5c7c" : "#ffffff"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        MouseArea {
          id: favMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: function(mouse) {
            mouse.accepted = true
            if (modelData && modelData.id) {
              root.favoriteToggled(modelData.id)
            }
          }
        }
      }

      // Locate in file manager button (hover only)
      Rectangle {
        visible: cardMouse.containsMouse
        width: Style.space(20)
        height: Style.space(20)
        radius: Style.space(10)
        color: locateMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.8) : Qt.rgba(0, 0, 0, 0.5)

        Text {
          anchors.centerIn: parent
          text: "󰉋"
          color: locateMouse.containsMouse ? Commons.Color.accent : "#ffffff"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        MouseArea {
          id: locateMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: function(mouse) {
            mouse.accepted = true
            if (modelData && modelData.path) {
              root.revealed(modelData.path)
            }
          }
        }
      }

      // Delete Button (only for global items, not active)
      Rectangle {
        visible: cardMouse.containsMouse && root.canDelete
        width: Style.space(20)
        height: Style.space(20)
        radius: Style.space(10)
        color: deleteMouse.containsMouse ? Qt.rgba(180, 20, 40, 0.9) : Qt.rgba(0, 0, 0, 0.5)

        Text {
          anchors.centerIn: parent
          text: "󰩹"
          color: "#ffffff"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        MouseArea {
          id: deleteMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: function(mouse) {
            mouse.accepted = true
            if (modelData && modelData.id) {
              root.deleted(modelData.id)
            }
          }
        }
      }
    }

    // Main Click Area to Apply Wallpaper
    MouseArea {
      id: cardMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      acceptedButtons: Qt.LeftButton
      onClicked: {
        if (modelData && modelData.path) {
          root.applied(modelData.path)
        }
      }
    }
  }
}

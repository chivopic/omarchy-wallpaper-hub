import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property var wallpaperItem: ({})
  property real cardWidth: 120
  property real cardHeight: 82

  signal applied(string path)
  signal favoriteToggled(string id)
  signal deleted(string id)
  signal revealed(string path)

  width: cardWidth
  height: cardHeight

  readonly property bool isCurrent: wallpaperItem && wallpaperItem.isCurrent === true
  readonly property bool isFavorite: wallpaperItem && wallpaperItem.favorite === true
  readonly property bool canDelete: wallpaperItem && wallpaperItem.canDelete === true && !isCurrent
  readonly property string thumbSource: {
    if (!wallpaperItem) return ""
    if (wallpaperItem.thumbnail && wallpaperItem.thumbnail.length > 0) {
      return "file://" + wallpaperItem.thumbnail
    }
    return wallpaperItem.path ? "file://" + wallpaperItem.path : ""
  }

  // Stable card-level hover tracker (never drops when entering child buttons)
  HoverHandler {
    id: cardHover
  }

  Rectangle {
    id: cardBackground
    anchors.fill: parent
    radius: Style.cornerRadius
    color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.08)
    clip: true

    border.color: root.isCurrent
      ? Commons.Color.accent
      : (cardHover.hovered ? Commons.Color.accent : Qt.rgba(Commons.Color.popups.border.r, Commons.Color.popups.border.g, Commons.Color.popups.border.b, 0.4))
    border.width: root.isCurrent ? Math.max(2, Style.space(2)) : 1

    Behavior on border.color { ColorAnimation { duration: 120 } }

    // 1. Wallpaper Thumbnail Image
    Image {
      id: thumbImage
      anchors.fill: parent
      anchors.margins: root.isCurrent ? 2 : 1
      source: root.thumbSource
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: true
      opacity: cardHover.hovered ? 1.0 : 0.92

      Behavior on opacity { NumberAnimation { duration: 100 } }
    }

    // 2. Base MouseArea for Whole Card (z: 1)
    MouseArea {
      id: cardMouse
      z: 1
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      onWheel: function(wheel) {
        wheel.accepted = false // Pass wheel to parent Flickable for smooth scrolling
      }
      onClicked: function(mouse) {
        if (mouse.button === Qt.RightButton) {
          // Right-click shortcut: reveal in file manager
          if (wallpaperItem && wallpaperItem.path) {
            root.revealed(wallpaperItem.path)
          }
        } else if (mouse.button === Qt.LeftButton) {
          if (wallpaperItem && wallpaperItem.path) {
            root.applied(wallpaperItem.path)
          }
        }
      }
    }

    // 3. Gradient overlay for title legibility (z: 2)
    Rectangle {
      z: 2
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: Style.space(26)
      gradient: Gradient {
        GradientStop { position: 0.0; color: "transparent" }
        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.8) }
      }
    }

    // 4. Name label (z: 3)
    Text {
      z: 3
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: Style.space(5)
      text: wallpaperItem ? (wallpaperItem.name || wallpaperItem.filename || "") : ""
      color: "#ffffff"
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      font.bold: root.isCurrent
      elide: Text.ElideRight
      horizontalAlignment: Text.AlignLeft
    }

    // 5. Active Checkmark Badge Top Left (z: 4)
    Rectangle {
      z: 4
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

    // 6. Action Buttons Top Right (z: 10 - stable hover & comfortable touch target)
    Row {
      z: 10
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Style.space(4)
      spacing: Style.space(4)
      opacity: (cardHover.hovered || root.isFavorite) ? 1.0 : 0.0

      Behavior on opacity { NumberAnimation { duration: 120 } }

      // Favorite Button (24x24)
      Rectangle {
        width: Style.space(24)
        height: Style.space(24)
        radius: Style.space(12)
        color: favMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.85) : (root.isFavorite ? Qt.rgba(0, 0, 0, 0.65) : Qt.rgba(0, 0, 0, 0.5))
        border.color: favMouse.containsMouse ? (root.isFavorite ? "#ff5c7c" : Commons.Color.accent) : (root.isFavorite ? "#ff5c7c" : "transparent")
        border.width: 1

        Behavior on color { ColorAnimation { duration: 100 } }

        Text {
          anchors.centerIn: parent
          text: root.isFavorite ? "󰋑" : "󰋔"
          color: root.isFavorite ? "#ff5c7c" : (favMouse.containsMouse ? Commons.Color.accent : "#ffffff")
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        MouseArea {
          id: favMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          preventStealing: true
          onWheel: function(wheel) { wheel.accepted = false }
          onClicked: function(mouse) {
            mouse.accepted = true
            if (wallpaperItem && wallpaperItem.id) {
              root.favoriteToggled(wallpaperItem.id)
            }
          }
        }
      }

      // Locate in file manager button (24x24)
      Rectangle {
        visible: cardHover.hovered
        width: Style.space(24)
        height: Style.space(24)
        radius: Style.space(12)
        color: locateMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.85) : Qt.rgba(0, 0, 0, 0.5)
        border.color: locateMouse.containsMouse ? Commons.Color.accent : "transparent"
        border.width: 1

        Behavior on color { ColorAnimation { duration: 100 } }

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
          preventStealing: true
          onWheel: function(wheel) { wheel.accepted = false }
          onClicked: function(mouse) {
            mouse.accepted = true
            if (wallpaperItem && wallpaperItem.path) {
              root.revealed(wallpaperItem.path)
            }
          }
        }
      }

      // Delete Button (24x24, only if canDelete)
      Rectangle {
        visible: cardHover.hovered && root.canDelete
        width: Style.space(24)
        height: Style.space(24)
        radius: Style.space(12)
        color: deleteMouse.containsMouse ? Qt.rgba(210, 30, 45, 0.95) : Qt.rgba(0, 0, 0, 0.5)
        border.color: deleteMouse.containsMouse ? "#ff4d6a" : "transparent"
        border.width: 1

        Behavior on color { ColorAnimation { duration: 100 } }

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
          preventStealing: true
          onWheel: function(wheel) { wheel.accepted = false }
          onClicked: function(mouse) {
            mouse.accepted = true
            if (wallpaperItem && wallpaperItem.id) {
              root.deleted(wallpaperItem.id)
            }
          }
        }
      }
    }
  }
}

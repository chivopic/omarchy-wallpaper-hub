import QtQuick
import QtQuick.Effects
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property var targetItem: null
  property int saturation: 0
  property int brightness: 100
  property bool open: false

  signal applyAdjusted(string targetId, int sat, int bri, bool autoApply)
  signal cancel()

  visible: open || modalAnim.running
  opacity: open ? 1.0 : 0.0

  Behavior on opacity {
    NumberAnimation { id: modalAnim; duration: 150; easing.type: Easing.OutCubic }
  }

  // Backdrop prevent clicks passing through
  MouseArea {
    anchors.fill: parent
    preventStealing: true
    onClicked: function(mouse) { mouse.accepted = true }
  }

  Rectangle {
    anchors.fill: parent
    radius: Style.cornerRadius
    color: Commons.Color.popups.background
    border.color: Commons.Color.popups.border
    border.width: 1

    Column {
      anchors.fill: parent
      anchors.margins: Style.space(10)
      spacing: Style.space(6)

      // 1. Header Row
      Item {
        width: parent.width
        height: Style.space(24)

        Row {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "󰹤"
            font.family: Style.font.family
            font.pixelSize: Style.font.icon
            color: Commons.Color.accent
          }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "调节壁纸灰度与暗度"
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.bold: true
            color: Commons.Color.foreground
          }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "· " + (root.targetItem ? (root.targetItem.name || root.targetItem.filename || "") : "当前壁纸")
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            color: Commons.Color.muted
            elide: Text.ElideRight
            width: Style.space(160)
          }
        }

        PanelActionButton {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          iconText: "✕"
          tooltipText: "关闭 (Esc)"
          size: Style.space(22)
          onClicked: root.cancel()
        }
      }

      PanelSeparator {
        width: parent.width
      }

      // 2. Real-Time GPU Preview Box
      Rectangle {
        width: parent.width
        height: Style.space(130)
        radius: Style.cornerRadius
        color: Qt.rgba(0, 0, 0, 0.45)
        border.color: Commons.Color.popups.border
        border.width: 1
        clip: true

        Image {
          id: previewImg
          anchors.centerIn: parent
          width: parent.width - Style.space(6)
          height: parent.height - Style.space(6)
          fillMode: Image.PreserveAspectFit
          asynchronous: true
          cache: true
          source: {
            if (!root.targetItem) return ""
            if (root.targetItem.thumbnail) return "file://" + root.targetItem.thumbnail
            return root.targetItem.path ? "file://" + root.targetItem.path : ""
          }

          layer.enabled: true
          layer.effect: MultiEffect {
            saturation: (root.saturation / 100.0) - 1.0
            brightness: (root.brightness / 100.0) - 1.0
          }
        }

        // Preview status pill badge
        Rectangle {
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.margins: Style.space(6)
          height: Style.space(18)
          width: previewPillText.implicitWidth + Style.space(10)
          radius: Style.space(9)
          color: Qt.rgba(0, 0, 0, 0.75)
          border.color: root.saturation === 0 ? Commons.Color.accent : Commons.Color.popups.border
          border.width: 1

          Text {
            id: previewPillText
            anchors.centerIn: parent
            text: {
              var sText = (root.saturation === 0) ? "纯黑白" : (root.saturation < 100 ? "低彩 " + root.saturation + "%" : "原彩色")
              var bText = (root.brightness < 100) ? " · 调光 " + root.brightness + "%" : ""
              return sText + bText
            }
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            color: root.saturation === 0 ? Commons.Color.accent : "#ffffff"
          }
        }
      }

      // 3. Grayscale / Saturation Controls
      Column {
        width: parent.width
        spacing: Style.space(3)

        Item {
          width: parent.width
          height: Style.space(16)
          Text {
            text: "灰度饱和度 (0% 为纯黑白)"
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            color: Commons.Color.foreground
          }
          Text {
            anchors.right: parent.right
            text: root.saturation + "%"
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            color: Commons.Color.accent
          }
        }

        ButtonGroup {
          width: parent.width
          height: Style.space(24)
          value: String(root.saturation)
          options: [
            { value: "0", label: "纯黑白 0%" },
            { value: "25", label: "微冷 25%" },
            { value: "50", label: "低彩 50%" },
            { value: "75", label: "微彩 75%" },
            { value: "100", label: "原彩 100%" }
          ]
          onChanged: function(val) {
            root.saturation = Number(val)
          }
        }
      }

      // 4. Brightness / Dark Mode Dimming Controls
      Column {
        width: parent.width
        spacing: Style.space(3)

        Item {
          width: parent.width
          height: Style.space(16)
          Text {
            text: "暗夜调光 (护眼降亮度)"
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            color: Commons.Color.foreground
          }
          Text {
            anchors.right: parent.right
            text: root.brightness + "%"
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            color: Commons.Color.accent
          }
        }

        ButtonGroup {
          width: parent.width
          height: Style.space(24)
          value: String(root.brightness)
          options: [
            { value: "65", label: "深度暗夜 65%" },
            { value: "80", label: "柔和暗光 80%" },
            { value: "90", label: "微调 90%" },
            { value: "100", label: "原光 100%" }
          ]
          onChanged: function(val) {
            root.brightness = Number(val)
          }
        }
      }

      PanelSeparator {
        width: parent.width
      }

      // 5. Action Buttons (Footer)
      Item {
        width: parent.width
        height: Style.space(32)

        Button {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          text: "取消"
          bordered: true
          onClicked: root.cancel()
        }

        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          Button {
            text: "仅保存新图"
            iconText: "󰆓"
            tooltipText: "生成暗色黑白壁纸保存入库，但不立即切换"
            bordered: true
            onClicked: {
              var targetId = root.targetItem ? (root.targetItem.id || root.targetItem.path) : "current"
              root.applyAdjusted(targetId, root.saturation, root.brightness, false)
            }
          }

          Button {
            text: "保存并设为壁纸"
            iconText: "󰄄"
            tooltipText: "生成暗色黑白壁纸并立即设为当前桌面背景"
            bordered: true
            color: Commons.Color.accent
            onClicked: {
              var targetId = root.targetItem ? (root.targetItem.id || root.targetItem.path) : "current"
              root.applyAdjusted(targetId, root.saturation, root.brightness, true)
            }
          }
        }
      }
    }
  }
}

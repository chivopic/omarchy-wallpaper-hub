import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "components"

PopupCard {
  id: root

  property var widget: null
  property var wallpaperItems: []
  property string currentScope: "current-theme"
  property string currentTheme: ""
  property string currentName: ""
  property int themeCount: 0
  property int globalCount: 0
  property int favCount: 0
  property string statusMessage: ""
  property bool isBusy: false
  property bool autoMono: false
  property int filterSaturation: 0
  property int filterBrightness: 100
  property bool filterToolOpen: false


  signal scopeSelected(string scope)
  signal applyWallpaper(string path)
  signal toggleFavorite(string id)
  signal deleteWallpaper(string id)
  signal revealPath(string path)
  signal importClipboard()
  signal importFile()
  signal randomWallpaper()
  signal refreshCatalog()
  signal convertCurrentToMono()
  signal convertToMono(string id)

  contentWidth: fittedContentWidth(Style.space(430))
  contentHeight: fittedContentHeight(panelCol.implicitHeight)

  Item {
    id: panelLayout
    anchors.fill: parent
    focus: true

    Keys.onEscapePressed: root.close()

    Column {
      id: panelCol
      anchors.fill: parent
      spacing: Style.space(8)

      // 1. Top Header Row: Title, Theme Tag, Random & Close
      Item {
        width: parent.width
        height: Style.space(26)
        implicitHeight: Style.space(26)

        Row {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(8)

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "󰸉"
            font.family: Style.font.family
            font.pixelSize: Style.font.icon
            color: Commons.Color.accent
          }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Wallpaper Hub"
            font.family: Style.font.family
            font.pixelSize: Style.font.title
            font.bold: true
            color: Commons.Color.foreground
          }

          // Theme pill badge
          Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            height: Style.space(18)
            width: themeLabel.implicitWidth + Style.space(12)
            radius: Style.space(9)
            color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.08)
            border.color: Commons.Color.popups.border
            border.width: 1

            Text {
              id: themeLabel
              anchors.centerIn: parent
              text: root.currentTheme || "default"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.8)
            }
          }
        }

        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          PanelActionButton {
            iconText: "󰹤"
            tooltipText: "暗夜黑白与滤镜调节"
            size: Style.space(24)
            hasCursor: root.filterToolOpen
            onClicked: root.filterToolOpen = !root.filterToolOpen
          }

          PanelActionButton {
            iconText: "󰒝"
            tooltipText: "随机换壁纸 (当前分类)"
            size: Style.space(24)
            onClicked: root.randomWallpaper()
          }

          PanelActionButton {
            iconText: "✕"
            tooltipText: "关闭 (Esc)"
            size: Style.space(24)
            onClicked: root.close()
          }
        }
      }

      // 2. Scope Tabs (Current Theme / Global / Favorites)
      ButtonGroup {
        id: scopeButtonGroup
        width: parent.width
        value: root.currentScope
        options: [
          { value: "current-theme", label: "主题壁纸" + (root.themeCount > 0 ? " · " + root.themeCount : "") },
          { value: "global", label: "全局库" + (root.globalCount > 0 ? " · " + root.globalCount : "") },
          { value: "favorites", label: "收藏夹" + (root.favCount > 0 ? " · " + root.favCount : "") }
        ]
        onChanged: function(val) {
          root.scopeSelected(val)
        }
      }

      PanelSeparator {
        width: parent.width
      }
      // Expandable Grayscale / Mono Adjustment Tool Drawer
      Item {
        visible: root.filterToolOpen
        width: parent.width
        height: root.filterToolOpen ? Style.space(68) : 0
        implicitHeight: root.filterToolOpen ? Style.space(68) : 0
        clip: true

        Behavior on height { NumberAnimation { duration: 150 } }

        Rectangle {
          anchors.fill: parent
          radius: Style.cornerRadius
          color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.05)
          border.color: Commons.Color.popups.border
          border.width: 1

          Column {
            anchors.fill: parent
            anchors.margins: Style.space(6)
            spacing: Style.space(4)

            // Row 1: Saturation / Grayscale
            Row {
              spacing: Style.space(6)
              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "灰度饱和度:"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.7)
              }

              ButtonGroup {
                height: Style.space(22)
                value: String(root.filterSaturation)
                options: [
                  { value: "0", label: "纯黑白 0%" },
                  { value: "30", label: "微冷 30%" },
                  { value: "60", label: "低彩 60%" },
                  { value: "100", label: "原彩 100%" }
                ]
                onChanged: function(val) {
                  root.filterSaturation = Number(val)
                }
              }
            }

            // Row 2: Dark Dimming & Quick Action
            Row {
              width: parent.width
              spacing: Style.space(6)

              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "暗夜调光:"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.7)
              }

              ButtonGroup {
                height: Style.space(22)
                value: String(root.filterBrightness)
                options: [
                  { value: "100", label: "正常 100%" },
                  { value: "85", label: "柔和 85%" },
                  { value: "70", label: "暗夜 70%" }
                ]
                onChanged: function(val) {
                  root.filterBrightness = Number(val)
                }
              }

              Button {
                text: "应用到当前壁纸"
                iconText: "󰄄"
                bordered: true
                height: Style.space(22)
                onClicked: root.convertCurrentToMono()
              }
            }
          }
        }
      }


      // 3. Main Grid Area
      Item {
        width: parent.width
        height: Style.space(320)
        implicitHeight: Style.space(320)
        clip: true

        WallpaperGrid {
          anchors.fill: parent
          items: root.wallpaperItems
          currentScope: root.currentScope

          onApplied: function(path) { root.applyWallpaper(path) }
          onFavoriteToggled: function(id) { root.toggleFavorite(id) }
          onDeleted: function(id) { root.deleteWallpaper(id) }
          onRevealed: function(path) { root.revealPath(path) }
          onImportClipboardRequested: root.importClipboard()
          onImportFileRequested: root.importFile()
          onMonoRequested: function(id) { root.convertToMono(id) }
        }

        // Loading/Busy overlay indicator
        Rectangle {
          visible: root.isBusy
          anchors.fill: parent
          color: Qt.rgba(0, 0, 0, 0.3)
          radius: Style.cornerRadius

          Row {
            anchors.centerIn: parent
            spacing: Style.space(8)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "󰑐"
              font.family: Style.font.family
              font.pixelSize: Style.font.icon
              color: Commons.Color.accent

              RotationAnimation on rotation {
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
              }
            }

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "处理中..."
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: "#ffffff"
            }
          }
        }
      }

      PanelSeparator {
        width: parent.width
      }

      // 4. Bottom Footer Toolbar
      Item {
        width: parent.width
        height: Style.space(34)
        implicitHeight: Style.space(34)

        Row {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          Button {
            text: "剪贴板导入"
            iconText: "󰅍"
            tooltipText: "导入剪贴板中的图片并设为壁纸"
            bordered: true
            onClicked: root.importClipboard()
          }

          Button {
            text: "本地图片"
            iconText: "󰐕"
            tooltipText: "选择本地图片导入全局库"
            bordered: true
            onClicked: root.importFile()
          }
          Button {
            text: root.autoMono ? "暗夜黑白模式: 开" : "暗夜黑白: 关"
            iconText: "󰹤"
            tooltipText: root.autoMono ? "暗夜黑白模式已开启：导入时自动转为黑白壁纸" : "点击开启：导入时自动转为暗色黑白壁纸"
            bordered: true
            onClicked: root.autoMono = !root.autoMono
          }
        }

        // Status or Toast message
        Text {
          anchors.centerIn: parent
          visible: root.statusMessage !== ""
          text: root.statusMessage
          color: Commons.Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
          elide: Text.ElideRight
          maximumLineCount: 1
        }

        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          PanelActionButton {
            iconText: "󰉋"
            tooltipText: "打开壁纸文件夹"
            size: Style.space(26)
            onClicked: {
              if (root.currentScope === "global") {
                Quickshell.execDetached(["xdg-open", Quickshell.env("HOME") + "/.local/share/omarchy-wallpaper-hub/wallpapers"])
              } else {
                Quickshell.execDetached(["xdg-open", Quickshell.env("HOME") + "/.config/omarchy/backgrounds/" + root.currentTheme])
              }
            }
          }

          PanelActionButton {
            iconText: "󰑐"
            tooltipText: "刷新壁纸库"
            size: Style.space(26)
            onClicked: root.refreshCatalog()
          }
        }
      }
    }
  }
}

import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property var items: []
  property string currentScope: "current-theme"
  property int columns: 3
  property real gridSpacing: Style.space(8)
  onCurrentScopeChanged: {
    flickable.contentY = 0
  }

  signal applied(string path)
  signal favoriteToggled(string id)
  signal deleted(string id)
  signal revealed(string path)
  signal importClipboardRequested()
  signal importFileRequested()

  readonly property real itemWidth: Math.floor((width - (columns - 1) * gridSpacing) / columns)
  readonly property real itemHeight: Math.round(itemWidth * 0.64)

  // Empty State View
  Item {
    id: emptyState
    anchors.fill: parent
    visible: !root.items || root.items.length === 0

    Column {
      anchors.centerIn: parent
      spacing: Style.space(10)
      width: parent.width * 0.85

      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.currentScope === "favorites" ? "󰋔" : "󰸉"
        font.family: Style.font.family
        font.pixelSize: Style.space(36)
        color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.35)
      }

      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: {
          if (root.currentScope === "favorites") return "暂无收藏壁纸\n点击卡片右上角心形图标即可收藏"
          if (root.currentScope === "global") return "全局壁纸库为空\n支持从剪贴板快速粘贴或选择本地图片"
          return "当前主题暂无壁纸"
        }
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.6)
        horizontalAlignment: Text.AlignHCenter
        lineHeight: 1.3
      }

      Row {
        visible: root.currentScope !== "favorites"
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Style.space(8)
        topPadding: Style.space(6)

        Button {
          text: "剪贴板导入"
          iconText: "󰅍"
          bordered: true
          onClicked: root.importClipboardRequested()
        }

        Button {
          text: "本地图片"
          iconText: "󰐕"
          bordered: true
          onClicked: root.importFileRequested()
        }
      }
    }
  }

  // Scrollable Grid View
  Flickable {
    id: flickable
    anchors.fill: parent
    visible: root.items && root.items.length > 0
    contentWidth: width
    contentHeight: grid.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    interactive: contentHeight > height
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    Grid {
      id: grid
      width: parent.width
      columns: root.columns
      spacing: root.gridSpacing

      Repeater {
        model: root.items

        delegate: WallpaperCard {
          required property var modelData
          cardWidth: root.itemWidth
          cardHeight: root.itemHeight
          wallpaperItem: modelData
          onApplied: function(path) { root.applied(path) }
          onFavoriteToggled: function(id) { root.favoriteToggled(id) }
          onDeleted: function(id) { root.deleted(id) }
          onRevealed: function(path) { root.revealed(path) }
        }
      }
    }
  }
}

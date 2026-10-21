import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.chivopic.wallpaper-hub"

  readonly property string scriptPath: String(Qt.resolvedUrl("backend.py")).replace(/^file:\/\//, "")
  readonly property string defaultScopeSetting: setting("defaultScope", "current-theme")

  // State
  property string currentScope: defaultScopeSetting
  property string currentTheme: ""
  property string currentBackground: ""
  property string currentName: ""
  property int themeCount: 0
  property int globalCount: 0
  property int favCount: 0
  property var wallpaperItems: []
  property string statusMessage: ""
  property bool isBusy: false

  property bool autoMono: false
  property int filterSaturation: 0
  property int filterBrightness: 100

  // UI state
  property bool popupOpen: false
  property bool contextMenuOpen: false
  property int pendingWheelDirection: 0

  function scopeLabel(s) {
    if (s === "global") return "全局库"
    if (s === "favorites") return "收藏夹"
    return "当前主题"
  }

  readonly property string tooltipText: "Wallpaper Hub\n" +
    "当前壁纸: " + (currentName || "默认") + "\n" +
    "切换范围: " + scopeLabel(currentScope) + " (" +
    (currentScope === "global" ? globalCount : (currentScope === "favorites" ? favCount : themeCount)) + " 张)\n" +
    "左键: 壁纸画廊 · 滚轮: 上/下张 · 中键: 随机 · 右键: 菜单"

  function close() {
    popupOpen = false
    contextMenuOpen = false
  }

  function toggle() {
    contextMenuOpen = false
    popupOpen = !popupOpen
    if (popupOpen) {
      refreshAll()
    }
  }

  function toggleContextMenu() {
    popupOpen = false
    contextMenuOpen = !contextMenuOpen
  }

  function showToast(msg, notifyDesktop) {
    statusMessage = msg
    toastTimer.restart()
    // Only send desktop notification when panel is NOT open (e.g. wheel / hotkey blind switching)
    if (notifyDesktop === true || (!root.popupOpen && notifyDesktop !== false)) {
      Quickshell.execDetached([
        "omarchy", "notification", "send",
        "-g", "󰸉", "-u", "low", "-t", "2000",
        "Wallpaper Hub", msg
      ])
    }
  }

  Timer {
    id: toastTimer
    interval: 3500
    repeat: false
    onTriggered: root.statusMessage = ""
  }

  // Wheel debounce (250ms)
  Timer {
    id: wheelDebounceTimer
    interval: 250
    repeat: false
    onTriggered: {
      if (root.pendingWheelDirection !== 0) {
        root.cycleWallpaper(root.pendingWheelDirection)
        root.pendingWheelDirection = 0
      }
    }
  }

  function handleWheel(delta) {
    if (delta === 0) return
    pendingWheelDirection = (delta < 0) ? 1 : -1
    wheelDebounceTimer.restart()
  }

  // Periodic poll for external changes (every 5s)
  Timer {
    id: pollTimer
    interval: 5000
    running: true
    repeat: true
    onTriggered: {
      if (!statusProc.running) {
        statusProc.running = true
      }
    }
  }

  Component.onCompleted: {
    refreshAll()
  }

  function refreshAll() {
    if (!statusProc.running) statusProc.running = true
    loadList(currentScope)
  }

  function loadList(scope) {
    currentScope = scope
    listProc.command = ["/usr/bin/python3", "-I", root.scriptPath, "list", "--scope", scope]
    listProc.running = true
  }

  function applyWallpaper(path) {
    if (!path) return
    root.currentBackground = path
    var filename = path.substring(path.lastIndexOf("/") + 1)
    root.currentName = filename.substring(0, filename.lastIndexOf(".")) || filename
    applyProc.command = ["/usr/bin/python3", "-I", root.scriptPath, "apply", path]
    applyProc.running = true
  }

  function cycleWallpaper(direction) {
    var subcmd = (direction > 0) ? "next" : "previous"
    cycleProc.command = ["/usr/bin/python3", "-I", root.scriptPath, subcmd, "--scope", currentScope]
    cycleProc.running = true
  }

  function randomWallpaper() {
    randomProc.command = ["/usr/bin/python3", "-I", root.scriptPath, "random", "--scope", currentScope]
    randomProc.running = true
  }

  function toggleFavorite(id) {
    var items = []
    for (var i = 0; i < root.wallpaperItems.length; i++) {
      var it = root.wallpaperItems[i]
      if (it.id === id) {
        it.favorite = !it.favorite
      }
      items.push(it)
    }
    root.wallpaperItems = items
    favProc.command = ["/usr/bin/python3", "-I", root.scriptPath, "favorite", id, "--toggle"]
    favProc.running = true
  }

  function deleteWallpaper(id) {
    var items = []
    for (var i = 0; i < root.wallpaperItems.length; i++) {
      if (root.wallpaperItems[i].id !== id) {
        items.push(root.wallpaperItems[i])
      }
    }
    root.wallpaperItems = items
    delProc.command = ["/usr/bin/python3", "-I", root.scriptPath, "delete", id]
    delProc.running = true
  }
  function convertToMono(targetId, sat, bri, autoApply) {
    var s = (sat !== undefined) ? sat : root.filterSaturation
    var b = (bri !== undefined) ? bri : root.filterBrightness
    var applyFlag = (autoApply !== false)
    isBusy = true
    var cmd = [
      "/usr/bin/python3", "-I", root.scriptPath,
      "convert-mono", targetId || "current",
      "--saturation", String(s),
      "--brightness", String(b),
      "--target-scope", (root.currentScope === "global" ? "global" : "theme")
    ]
    if (!applyFlag) {
      cmd.push("--no-apply")
    }
    monoProc.command = cmd
    monoProc.running = true
  }

  function importClipboard() {
    isBusy = true
    var cmd = ["/usr/bin/python3", "-I", root.scriptPath, "import-clipboard", "--target", "global"]
    if (root.autoMono) {
      cmd.push("--mono")
      cmd.push("--saturation", String(root.filterSaturation))
      cmd.push("--brightness", String(root.filterBrightness))
    }
    clipProc.command = cmd
    clipProc.running = true
  }
  function pickAndImportFile() {
    pickFileProc.running = true
  }

  function revealPath(path) {
    if (!path) return
    Quickshell.execDetached(["xdg-open", path.substring(0, path.lastIndexOf("/"))])
  }

  // ---------------- Backend Processes ----------------

  // 1. Status Process
  Process {
    id: statusProc
    command: ["/usr/bin/python3", "-I", root.scriptPath, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success && res.data) {
            var d = res.data
            var oldTheme = root.currentTheme
            root.currentTheme = d.theme || ""
            root.currentBackground = d.currentBackground || ""
            root.currentName = d.currentName || ""

            if (d.counts) {
              root.themeCount = Number(d.counts.currentTheme || 0)
              root.globalCount = Number(d.counts.global || 0)
              root.favCount = Number(d.counts.favorites || 0)
            }

            // AC-06 & Section 3.2: If theme changed externally, reset scope to current-theme
            if (oldTheme && oldTheme !== root.currentTheme) {
              root.currentScope = "current-theme"
              root.loadList("current-theme")
            }
          }
        } catch (e) {}
      }
    }
  }

  // 2. List Process
  Process {
    id: listProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        root.isBusy = false
        try {
          var res = JSON.parse(text)
          if (res && res.success && Array.isArray(res.data)) {
            root.wallpaperItems = res.data
          }
        } catch (e) {}
      }
    }
  }

  // 3. Apply Process
  Process {
    id: applyProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.refreshAll()
            root.showToast("已应用壁纸", false)
          } else if (res && res.error) {
            root.showToast("切换失败: " + res.error.message, true)
          }
        } catch (e) {}
      }
    }
  }

  // 4. Cycle Process (Wheel next/prev)
  Process {
    id: cycleProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success && res.data) {
            var item = res.data.item
            if (item) {
              root.currentBackground = item.path
              root.currentName = item.name
              root.showToast("壁纸: " + item.name + " (" + (res.data.index + 1) + "/" + res.data.total + ")")
            }
            root.refreshAll()
          } else if (res && res.error) {
            root.showToast(res.error.message)
          }
        } catch (e) {}
      }
    }
  }

  // 5. Random Process
  Process {
    id: randomProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success && res.data && res.data.item) {
            root.currentBackground = res.data.item.path
            root.currentName = res.data.item.name
            root.showToast("随机壁纸: " + res.data.item.name)
            root.refreshAll()
          }
        } catch (e) {}
      }
    }
  }

  // 6. Favorite Process
  Process {
    id: favProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.refreshAll()
          }
        } catch (e) {}
      }
    }
  }

  // 7. Delete Process
  Process {
    id: delProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.showToast("壁纸已移入回收站", false)
            root.refreshAll()
          } else if (res && res.error) {
            root.showToast("删除失败: " + res.error.message, true)
            root.refreshAll()
          }
        } catch (e) {}
      }
    }
  }

  // 8. Clipboard Import Process
  Process {
    id: clipProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        root.isBusy = false
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.showToast("已导入剪贴板图片并应用")
            root.refreshAll()
          } else if (res && res.error) {
            root.showToast("导入失败: " + res.error.message)
          }
        } catch (e) {
          root.showToast("导入失败: 无法解析返回数据")
        }
      }
    }
  }

  // 9. File Pick & Import Process
  Process {
    id: pickFileProc
    command: ["/usr/bin/python3", "-I", root.scriptPath, "pick-file"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        try {
          var res = JSON.parse(text)
          if (res && res.success && res.data && res.data.selected) {
            var cmd = [
              "/usr/bin/python3", "-I", root.scriptPath,
              "import-file", res.data.selected,
              "--target", "global"
            ]
            if (root.autoMono) {
              cmd.push("--mono")
              cmd.push("--saturation", String(root.filterSaturation))
              cmd.push("--brightness", String(root.filterBrightness))
            }
            importFileProc.command = cmd
            importFileProc.running = true
          }
        } catch (e) {}
      }
    }
  }

  // 10. File Import Worker Process
  Process {
    id: importFileProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        root.isBusy = false
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.showToast("图片导入成功并已应用")
            root.refreshAll()
          } else if (res && res.error) {
            root.showToast("导入失败: " + res.error.message)
          }
        } catch (e) {}
      }
    }
  }

  // 11. Mono / Grayscale Conversion Process
  Process {
    id: monoProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: function() {
        root.isBusy = false
        try {
          var res = JSON.parse(text)
          if (res && res.success) {
            root.refreshAll()
            root.showToast("已转换为暗夜黑白壁纸并应用", false)
          } else if (res && res.error) {
            root.showToast("转换失败: " + res.error.message, true)
          }
        } catch (e) {}
      }
    }
  }

  // ---------------- Visual Items ----------------

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // The Top Bar Button
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰸉"
    tooltipText: root.tooltipText
    horizontalMargin: 8.5

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) {
        root.toggle()
      } else if (mouseButton === Qt.RightButton) {
        root.toggleContextMenu()
      } else if (mouseButton === Qt.MiddleButton) {
        root.randomWallpaper()
      }
    }

    onWheelMoved: function(delta) {
      root.handleWheel(delta)
    }
  }

  // Main Gallery Popup Panel
  WallpaperPanel {
    id: galleryPanel
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.popupOpen
    widget: root
    wallpaperItems: root.wallpaperItems
    currentScope: root.currentScope
    currentTheme: root.currentTheme
    currentName: root.currentName
    themeCount: root.themeCount
    globalCount: root.globalCount
    favCount: root.favCount
    statusMessage: root.statusMessage
    isBusy: root.isBusy
    autoMono: root.autoMono
    filterSaturation: root.filterSaturation
    filterBrightness: root.filterBrightness
    onConvertCurrentToMono: root.convertToMono("current")
    onConvertToMono: function(id) { root.convertToMono(id) }
    onConvertAndApplyAdjusted: function(targetId, sat, bri, autoApply) {
      root.convertToMono(targetId, sat, bri, autoApply)
    }

    onScopeSelected: function(scope) {
      root.loadList(scope)
    }
    onApplyWallpaper: function(path) {
      root.applyWallpaper(path)
    }
    onToggleFavorite: function(id) {
      root.toggleFavorite(id)
    }
    onDeleteWallpaper: function(id) {
      root.deleteWallpaper(id)
    }
    onRevealPath: function(path) {
      root.revealPath(path)
    }
    onImportClipboard: root.importClipboard()
    onImportFile: root.pickAndImportFile()
    onRandomWallpaper: root.randomWallpaper()
    onRefreshCatalog: root.refreshAll()
  }

  // Right-Click Context Menu Popup
  PopupCard {
    id: contextMenu
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.contextMenuOpen
    contentWidth: fittedContentWidth(Style.space(210))
    contentHeight: fittedContentHeight(contextCol.implicitHeight)

    Column {
      id: contextCol
      anchors.fill: parent
      spacing: Style.space(4)

      Text {
        text: "Wallpaper Hub"
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        font.bold: true
        color: Commons.Color.accent
        bottomPadding: Style.space(2)
      }

      PanelSeparator {
        width: parent.width
      }

      Button {
        width: parent.width
        text: "从剪贴板导入 (暗夜黑白)"
        iconText: "󰹤"
        onClicked: {
          root.contextMenuOpen = false
          var old = root.autoMono
          root.autoMono = true
          root.importClipboard()
          root.autoMono = old
        }
      }

      Button {
        width: parent.width
        text: "将当前壁纸转为黑白"
        iconText: "󰄄"
        onClicked: {
          root.contextMenuOpen = false
          root.convertToMono("current")
        }
      }

      Button {
        width: parent.width
        text: "从剪贴板导入壁纸"
        iconText: "󰅍"
        onClicked: {
          root.contextMenuOpen = false
          root.importClipboard()
        }
      }

      Button {
        width: parent.width
        text: "添加本地图片..."
        iconText: "󰐕"
        onClicked: {
          root.contextMenuOpen = false
          root.pickAndImportFile()
        }
      }

      Button {
        width: parent.width
        text: "随机切换一张壁纸"
        iconText: "󰒝"
        onClicked: {
          root.contextMenuOpen = false
          root.randomWallpaper()
        }
      }

      Button {
        width: parent.width
        text: "打开全局壁纸文件夹"
        iconText: "󰉋"
        onClicked: {
          root.contextMenuOpen = false
          Quickshell.execDetached(["xdg-open", Quickshell.env("HOME") + "/.local/share/omarchy-wallpaper-hub/wallpapers"])
        }
      }

      Button {
        width: parent.width
        text: "刷新壁纸列表"
        iconText: "󰑐"
        onClicked: {
          root.contextMenuOpen = false
          root.refreshAll()
        }
      }
    }
  }
}

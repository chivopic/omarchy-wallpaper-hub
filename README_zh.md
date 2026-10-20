# Omarchy Wallpaper Hub · 桌面壁纸管理微件

<p align="center">
  <b>面向 Omarchy Linux 的轻量级原生桌面壁纸管理插件</b><br>
  顶栏极速盲切 · 画廊网格预览 · 剪贴板/文件一键导入 · 主题与全局双库分离 · 收藏夹 · 安全回收
</p>

<p align="center">
  <a href="https://plugins.omarchy.org"><img src="https://img.shields.io/badge/Omarchy-plugin-orange?style=flat-square" alt="Omarchy plugin" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/Version-1.0.0-green?style=flat-square" alt="Version 1.0.0" />
  <img src="https://img.shields.io/badge/Python-3.10+-yellow?style=flat-square" alt="Python 3.10+" />
</p>

---

## 🌟 核心特性

- **Native First 原生兼容**：复用 Omarchy 官方 CLI 底层壁纸管道（`omarchy theme bg set`），保持原生平滑过渡动效，不强行覆盖或破坏系统软链接。
- **多库协同与历史壁纸无缝识别**：
  - **当前主题库**：跟随 Omarchy 当前主题（如 `vantablack`、`tokyo-night`、`catppuccin` 等），支持主题预设背景与用户自定义主题背景。
  - **全局壁纸库**：独立于主题，跨主题永久保留。
  - **本地用户壁纸自动索引**：自动扫描并无缝索引 `~/Pictures/wallpapers/` 中的现有壁纸，无需重新迁移。
- **顶栏极速盲切手势**：
  - 🖱️ **滚轮向上 / 向下**：250ms 防抖极速切换上一张 / 下一张壁纸（受当前分类约束）。
  - 🎲 **鼠标中键**：在当前分类内随机挑选一张壁纸并应用。
  - 🖼️ **鼠标左键**：展开 / 收起 3 列缩略图画廊卡片面板。
  - ⚙️ **鼠标右键**：唤出快捷功能菜单（剪贴板导入、添加本地图片、打开壁纸文件夹、刷新列表）。
- **极速导入引擎**：
  - **Wayland 剪贴板一键导入**：网页或截图工具中“复制图片”后，一键写入全局库并设为壁纸。
  - **本地图形文件选择器**：内置 Zenity 图形文件拾取器，轻松添加本地图片。
  - **安全去重与格式校验**：基于 SHA-256 自动去重，严格校验静态 PNG、JPEG、WebP，拦截损坏文件与异常大图（>25MB 或 >50MP）。
- **轻量与安全（Safe by Default）**：
  - 零后台守护进程，纯按需唤起。
  - 仅允许将插件管理的全局壁纸移入回收站（`gio trash`），原生壁纸与用户主题壁纸受写保护。
  - 禁止删除当前正在使用的活动壁纸，防止桌面背景异常。

---

## 🕹️ 交互指南

| 操作 | 区域 | 行为 |
| :--- | :--- | :--- |
| **滚轮向下** | 顶栏图标 | 切换到**下一张**壁纸（受当前分类约束，防抖 250ms） |
| **滚轮向上** | 顶栏图标 | 切换到**上一张**壁纸（受当前分类约束，防抖 250ms） |
| **鼠标中键** | 顶栏图标 | 在当前分类中**随机挑选**一张壁纸并应用 |
| **鼠标左键** | 顶栏图标 | 打开或关闭壁纸画廊下拉面板 |
| **鼠标右键** | 顶栏图标 | 打开快捷菜单（剪贴板导入、打开目录、刷新） |
| **鼠标悬停** | 顶栏图标 | Tooltip 提示当前壁纸名称、当前切换分类与壁纸总数 |
| **单击卡片** | 画廊面板 | 立即应用该壁纸并高亮选中（带勾选标记） |
| **心形图标** | 卡片右上角 | 收藏 / 取消收藏壁纸（加入“收藏夹”分类） |
| **文件夹图标** | 卡片右上角 | 在文件管理器（Nautilus / xdg-open）中定位该文件 |
| **垃圾桶图标** | 卡片右上角 | 将全局壁纸移入系统回收站（当前正在使用的壁纸受保护禁止删除） |
| **Esc / 外部点击** | 任意位置 | 关闭画廊面板 |

---

## 📂 壁纸库与数据路径 (遵循 XDG 规范)

| 数据类别 | 路径 | 说明 |
| :--- | :--- | :--- |
| **插件全局壁纸** | `~/.local/share/omarchy-wallpaper-hub/wallpapers/` | 所有导入的全局静态壁纸 |
| **用户壁纸目录** | `~/Pictures/wallpapers/` | 用户本地已有的壁纸集合（自动索引） |
| **元数据与收藏** | `~/.local/share/omarchy-wallpaper-hub/metadata.json` | 收藏状态、导入时间、来源信息 |
| **缩略图缓存** | `~/.cache/omarchy-wallpaper-hub/thumbnails/` | 由 `vipsthumbnail` 异步生成的快速预览缓存 |
| **当前主题壁纸** | `~/.local/state/omarchy/current/theme/backgrounds/` | Omarchy 当前主题预设壁纸 (只读) |
| **用户主题壁纸** | `~/.config/omarchy/backgrounds/<theme_name>/` | 用户为特定主题存放的专属壁纸 |

> **卸载安全性**：卸载插件**绝不会**删除 `~/.local/share/omarchy-wallpaper-hub/` 中的壁纸文件或收藏记录。

---

## 💻 命令行 CLI 接口 (`backend.py`)

所有操作均可通过 `backend.py` 脚本以标准 JSON 格式调用，方便绑定 Hyprland 全局快捷键或外部自动化脚本：

```bash
# 查看当前壁纸、主题及统计
python3 backend.py status

# 列出指定分类的壁纸 (current-theme / global / favorites)
python3 backend.py list --scope current-theme
python3 backend.py list --scope global
python3 backend.py list --scope favorites

# 切换壁纸 (next / previous / random)
python3 backend.py next --scope current-theme
python3 backend.py previous --scope global
python3 backend.py random --scope favorites

# 从剪贴板导入图片并立即设为壁纸
python3 backend.py import-clipboard --target global

# 从本地文件导入
python3 backend.py import-file /path/to/image.png --target global

# 收藏或取消收藏
python3 backend.py favorite "global:wp_xxx.png" --toggle

# 安全删除 (仅限全局库未使用的壁纸)
python3 backend.py delete "global:wp_xxx.png"
```

---

## ⌨️ 推荐的 Hyprland 快捷键绑定

你可以将以下绑定添加到自己的 Hyprland 配置文件中，实现全键盘盲切与剪贴板一键壁纸：

### `~/.config/hypr/bindings.conf`
```ini
# Super + Alt + W: 切换下一张壁纸
bind = SUPER ALT, W, exec, python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py next

# Super + Alt + R: 随机换一张壁纸
bind = SUPER ALT, R, exec, python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py random

# Super + Alt + V: 剪贴板图片设为壁纸
bind = SUPER ALT, V, exec, python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py import-clipboard
```

### `~/.config/hypr/bindings.lua` (Omarchy Lua 配置)
```lua
-- Super + Alt + W: 切换下一张壁纸
hl.bind({"SUPER", "ALT"}, "W", "exec", "python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py next")

-- Super + Alt + R: 随机换一张壁纸
hl.bind({"SUPER", "ALT"}, "R", "exec", "python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py random")

-- Super + Alt + V: 剪贴板图片设为壁纸
hl.bind({"SUPER", "ALT"}, "V", "exec", "python3 ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub/backend.py import-clipboard")
```

---

## 🚀 安装与启用

### 方式 1：通过 Omarchy CLI 一键安装（推荐）

```bash
omarchy plugin add https://github.com/chivopic/omarchy-wallpaper-hub.git --enable
```

### 方式 2：手动克隆并启用

```bash
mkdir -p ~/.config/omarchy/plugins
git clone https://github.com/chivopic/omarchy-wallpaper-hub.git ~/.config/omarchy/plugins/io.github.chivopic.wallpaper-hub
omarchy plugin enable io.github.chivopic.wallpaper-hub right
```

---

## 🛡️ 许可证

[MIT License](LICENSE) © 2026 [chivopic](https://github.com/chivopic)

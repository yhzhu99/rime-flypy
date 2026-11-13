# 外观与共享输入状态

## 统一的设计

- 候选横向排列，文字横排，5 个候选项。
- 使用平台自带的无衬线字体：Windows 中文微软雅黑、英文 Segoe UI；macOS 中文苹方、英文 Helvetica Neue；Linux 使用 `Sans` 和系统中文字体回退。
- 主文字 **16 pt**；Windows/macOS 的候选序号 12 pt、注释 13 pt。
- Windows/macOS 使用同一套清浅（paper_light）浅色配色，不随系统深色模式自动换成另一套主题。
- 字体只用于输入法能控制的候选界面；上屏后的文本和应用内行内编码仍由应用决定字体。相同逻辑字号在不同 DPI/缩放比例下的物理尺寸可能不同。

字体随平台，字号、颜色和布局统一。安装入口不下载字体、不注册用户字体，也不改变整个桌面的字体设置。

| 平台 | 字体配置 | 行为 |
| --- | --- | --- |
| Windows | `Segoe UI, Microsoft YaHei` | 拉丁字母与数字优先使用 Segoe UI，中文由微软雅黑显示 |
| macOS | `Helvetica Neue-Regular, PingFang SC-Regular` | 拉丁字母与数字优先使用 Helvetica Neue，中文由苹方显示；按鼠须管的 family-style 语法配置 |
| Linux | `Sans 16` | 使用桌面的无衬线字体及 fontconfig 中文回退，不绑定某一种发行版字体 |

Linux 没有所有发行版共同预装的中文字体。系统缺少中文字形时，安装发行版提供的中文字体包，例如 Debian/Ubuntu 的 `fonts-noto-cjk`、Fedora 的 `google-noto-sans-cjk-fonts`、Arch 的 `noto-fonts-cjk`。这是系统字体依赖，由包管理器维护；仓库不自行下载字体文件。

### 清浅配色

背景接近白色，略带暖调；所有候选文字统一使用深灰，序号和注释使用较深的灰蓝色。首选项用边界清晰的浅蓝色圆角底块区分，文字保持深灰；Windows 移除候选窗阴影，避免边缘显得模糊。保留序号区分候选。

选中色块作为独立圆角矩形，与外框分开。Windows/macOS 均使用外框圆角半径 6、内部色块圆角半径 4；内部色块尺寸较小，圆角也略小，保持接近的圆润程度。Windows 使用 4 px 的逻辑间距：色块内边距 4，色块之间的预留间隙 4，色块到外框的留白 4（不含边框），序号与文字之间 4。因此 `margin_x`/`margin_y` 均为 8，`hilite_padding` 为 4，`candidate_spacing` 为 12，`hilite_spacing` 为 4。`candidate_spacing` 是两个候选内容之间的距离，减去两侧各 4 的色块内边距，实际剩余间隙为 4。普通候选保留相同的虚拟色块空间，切换选中项时布局不跳动。

测试覆盖常用 DPI 比例下的间距平衡，以及色块与外框圆角不相交，避免小狼毫自动把选中色块裁成不对称圆角。实现依据见 [横排候选布局](https://github.com/rime/weasel/blob/0.17.4/WeaselUI/HorizontalLayout.cpp#L87)、[圆角判定](https://github.com/rime/weasel/blob/0.17.4/WeaselUI/StandardLayout.cpp#L132) 和 [自动替换色块圆角](https://github.com/rime/weasel/blob/0.17.4/WeaselUI/WeaselPanel.cpp#L494)。这些是小狼毫的逻辑布局单位，屏幕实际像素随缩放改变；macOS 使用鼠须管原生布局。

| 用途 | RGB 色值 |
| --- | --- |
| 背景 | `#FAFAF7` |
| 正文/候选文字 | `#252A31` |
| 序号/注释 | `#535D69` |
| 首选项底块 | `#CCDFF5` |
| 边框 | `#DEE2E6` |

Windows/macOS 配置使用 BGR 编码，表格使用常见的 RGB 编码。自动化检查两平台配色一致，所有正文、序号、注释与各自背景的对比度至少为 4.5:1；选中色块与普通背景的亮度对比至少为 1.25:1，避免两者太接近。

## 安装和更新

Windows 修改配色后先重新部署；若外观未刷新，使用安装目录中的 `WeaselServer.exe /quit` 正常退出服务，再启动 `WeaselServer.exe`。仅检查 `build/weasel.yaml` 不能确认运行中的服务已加载新外观。

完整的 `uv run setup.py --apply` 部署 Rime 的系统字体配置，并在 Linux 上设置标准 IBus 面板。`--config-only` 只复制 Rime 文件，跳过桌面设置和系统改键；Windows/macOS 的字体配置仍随 Rime 文件部署。

只配置 Linux IBus 面板，不改键、不部署其他 Rime 文件：

```sh
uv run appearance.py          # 无写入预览
uv run appearance.py --apply
```

在 Windows/macOS 上，`appearance.py` 只提示字体由前端配置选择，不写文件、不改注册表、不安装字体。修改字体后重新部署前端；Windows 若未刷新，应正常退出并重启小狼毫服务。

### Linux 的桌面边界

IBus-Rime 原生读取 `style/horizontal`，因此候选方向直接设为横排。它**不读取**小狼毫/鼠须管的 `font_face`、`font_point` 和配色字段；不要把这些字段复制到 `ibus_rime.custom.yaml` 后声称已生效。

本仓库为标准 IBus GTK 面板设置：

```sh
gsettings set org.freedesktop.ibus.general use-global-engine true
gsettings set org.freedesktop.ibus.panel lookup-table-orientation 0
gsettings set org.freedesktop.ibus.panel use-custom-font true
gsettings set org.freedesktop.ibus.panel custom-font 'Sans 16'
```

需要在已登录的普通桌面用户会话运行，且安装提供 `gsettings` 的 GLib 工具及 IBus schema。脚本会预检，不可写时停止。

**GNOME Shell、KDE 等桌面自带的候选面板可能接管字体和主题**，不遵循标准 IBus 面板的字体偏好。此时横排仍由 Rime 请求，但字体/颜色须通过该桌面面板支持的设置或扩展配置；本仓库不修改整个桌面的系统字体，也不自动安装桌面扩展。因此不能承诺 Linux 任意桌面与 Windows/macOS 像素一致。原生 IBus 面板的配色沿用 GTK 主题，也不支持本仓库的自定义配色字段。

## 中英文状态：各应用共享

`lua/language_keys.lua` 同步同一 Rime 服务内的所有方案会话：左 Shift 选择英文、右 Alt 选择中文后，新旧应用会话都沿用最新状态。新会话/方案重载的默认值不能重置共享状态。输入法服务重启后从中文开始。

同步只改变 `ascii_mode`，不在应用间复制编码或上屏文本。左 Shift 的原始编码只在收到该按键的应用中上屏。大写、全半角、简繁和标点模式不在这项同步范围。

小狼毫继续保留 `global_ascii: true`，并整体替换默认 `app_options`，清除 `cmd.exe`/`conhost.exe` 的强制英文，仅保留 Firefox 显示兼容项；鼠须管没有同名原生开关，因此由共用 Lua 实现。macOS 的 `app_options` 整体替换上游默认项，移除所有应用专用的 `ascii_mode`/`vim_mode`，仅保留显示兼容设置。IBus 的 `use-global-engine` 保证各应用共用同一个输入法框架，框架内的中英文模式仍由 Lua 同步。

## 回退和验证

配置文件按主 setup 的 `manifest.json` 恢复，再重新部署。此前安装的用户字体不会被自动删除；当前配置已不再引用它们，后续安装也不再依赖这些字体。

Linux 的旧 IBus 有效设置保存在 `appearance.json`（完整 setup 的配置备份目录，或独立入口打印的 `${XDG_STATE_HOME:-~/.local/state}/rime-flypy/appearance-backup-*` 目录）。恢复命令：

```sh
uv run appearance.py --restore-linux-settings '/实际备份路径/appearance.json'
```

恢复前核对所有当前值；发现后续编辑就整体停止。只恢复 IBus 设置。

实机检查：在一个应用按左 Shift，再切到另一应用直接输入 `abc`；按右 Alt 切中文，再切回第一应用输入中文。检查中文候选使用平台中文字体，英文/序号为系统无衬线字体，横排、16 pt 主文字清晰。自动化的真实多会话引擎测试不替代 macOS/Linux 桌面和字体渲染验收。

实现依据：[IBus-Rime 读取的界面字段](https://github.com/rime/ibus-rime/blob/57fba74724611b3c21e36656123fb62cf10b759c/rime_settings.c)、[鼠须管字体回退列表](https://github.com/rime/squirrel/blob/b7970a93b05ae1ca1bcd97888fd6aa3cd0458d3e/sources/SquirrelTheme.swift)、[鼠须管全局状态讨论](https://github.com/rime/squirrel/issues/145)。

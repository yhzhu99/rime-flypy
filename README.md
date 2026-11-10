# rime-flypy

个人小鹤音形配置：共用词库、Lua 扩展和确定性的中英文选择键，分别配置 Windows、Linux、macOS 的系统改键。

## 新电脑入口

按 **[新电脑配置指南](docs/new-computer.md)** 安装依赖，然后在仓库目录运行：

```sh
uv run setup.py          # 三平台一致：预览，不修改系统
uv run setup.py --apply  # 备份、部署 Rime 和对应平台的改键配置
```

Linux 统一使用 **IBus-Rime + keyd**。Windows 提供已验证版小狼毫/内核安装脚本；macOS 使用鼠须管 + Karabiner。首次输入源选择、macOS 权限与规则启用、Windows 重启仍须手动完成，详见指南中的自动化范围表。统一用 uv 管理运行环境，`.python-version` 固定 Python 3.14 系列。Python 只用于安装配置，不常驻运行。

## 最终键位约定

下表的“物理键”指键帽上原来的名字。只交换左 Ctrl/Alt，不交换右 Ctrl。

| 物理键 | 作用 |
| --- | --- |
| 左 Shift 单按并快速松开 | **固定英文**，重复按仍是英文 |
| 右 Alt（macOS 右 Option） | **固定中文**，重复按仍是中文 |
| 右 Shift | 普通 Shift，不切换语言 |
| 左 Ctrl | 左 Alt（macOS 左 Option） |
| 左 Alt（macOS 左 Option） | 左 Ctrl |
| Caps Lock | Escape |
| Escape | Caps Lock |

右 Alt 完全作为中文专用键，放弃其 Alt/AltGr/Option 组合键用途。macOS 的 Command 保持原样；Mac 键盘紧邻空格的通常是 Command，本配置仍以 **Option 键**为右 Alt。

## 两层配置

1. **系统层**：交换修饰键，把物理右 Alt 映射成 **F13**。
2. **Rime 层**：左 Shift 使用 `set_ascii_mode` 固定英文；`lua/right_alt_f13.lua` 在英文直通处理之前消费 F13 的按下和松开，将 `ascii_mode` 设为 `false`。

系统改键在其他输入法下也生效，但 F13 只有在 **Rime 已选中且输入框接受输入法事件**时才会固定中文。它不是“从任意输入法唤回 Rime”的全局命令。只有一套 Rime 输入源时，英文直接使用 Rime 的英文模式即可。

左 Shift 单按识别由 Rime 内核处理，约需在 500 ms 内松开；正常 Shift 大写组合不切换语言。固定英文会清除尚未确认的中文编码，已上屏文本不受影响。已在中文状态再次按 F13 会保留未完成编码。

## 前提和平台入口

需要含 [librime #1015](https://github.com/rime/librime/pull/1015) 固定语言功能的内核，以及 **librime-lua**。本仓库用 **librime 1.17.0** 做真实引擎测试；前端版本号不等于内核版本号。老发行版只改 YAML 不会补上内核功能。

| 平台 | Rime 用户目录 | 系统改键方案 | 操作说明 |
| --- | --- | --- | --- |
| Windows / 小狼毫 | `%APPDATA%\Rime` | Scancode Map，无额外常驻软件，需重启 | [Windows](docs/windows.md) |
| Linux / IBus-Rime | `~/.config/ibus/rime` | keyd，覆盖 X11、Wayland 和控制台 | [Linux](docs/linux.md) |
| macOS / 鼠须管 | `~/Library/Rime` | Karabiner-Elements | [macOS](docs/macos.md) |

Linux 的 keyd 和 macOS 的 Karabiner 需要在对应平台另外安装，不能只复制 Windows 注册表配置。

先部署 Rime 配置、验证 F13 能进入中文，再启用系统改键。若更新过程中需要应急中文入口，可暂时把 `default.custom.yaml` 的 `Shift_R` 改为 `unset_ascii_mode` 并重新部署；系统改键完成后改回 `noop`。

## 仓库内容

- `default.custom.yaml`、`flypy*.yaml`、`flypy/`、`lua/`：共用方案、词库、固定语言键，以及既有日期、时间、快捷词和计算器扩展。
- `weasel.custom.yaml`：Windows 的 Catppuccin 配色、字体、横排候选和 `global_ascii: true`。
- `ibus_rime.custom.yaml`：IBus 光标处原始编码和横排候选。
- `squirrel.custom.yaml`：macOS 的横排候选、Catppuccin 配色和应用选项。各前端读取自己的文件，不能假定外观和跨应用状态行为完全相同。
- `platforms/`：系统改键配置及 Windows 的预览、应用、回退脚本。
- `setup.py`：跨平台配置入口，默认预览，支持备份、只部署配置和受保护的文件回退。
- `tests/`：平台配置检查、Windows 映射行为检查、真实 librime 输入行为测试。

只同步这些配置文件。`build/`、`installation.yaml`、`user.yaml`、日志、同步缓存和学习用户词库不纳入版本控制。本次保留已有静态词库，没有新增本机学习记录。

## 更新和验证

若仓库直接位于 Rime 用户目录，执行 `git pull --ff-only` 后重新部署。若仓库与用户目录分开，更新后再次执行 `setup.py --apply`，或按平台文档执行单项操作。

```sh
uv run --with-requirements tests/requirements.txt python -m unittest discover -s tests -p 'test_*.py' -v
```

真实引擎测试（在临时目录部署，不修改正在使用的 Rime）：

```text
uv run tests/librime_behavior.py <librime动态库路径> <Rime共享数据目录>
```

GitHub Actions 在 Windows、Linux、macOS 检查配置；用实际 keyd 解析 Linux 映射，并在 Windows 上运行映射合并测试和 27 项 librime 行为检查。具体范围见 [验证记录](docs/validation.md)。

**系统层实机验收仍然必需**：检查 Ctrl/Alt、Caps/Esc 互换；按左 Shift 后输入英文；重复按左 Shift 仍为英文；按右 Alt 输入小鹤编码并上屏；重复按右 Alt 仍为中文；右 Alt 单按不激活菜单；右 Shift 大写组合正常。

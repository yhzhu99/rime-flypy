# 新电脑：从这个仓库恢复整套输入习惯

本仓库保存 Rime 配置、静态词库、扩展、外观和五条系统键盘映射。**依赖安装后，用同一个 `setup.py --apply` 配置当前平台**。Python 只在配置时运行，不是新增的常驻改键程序。

这不是零依赖、零交互安装：首次选择输入源、macOS 权限及 Karabiner 规则启用、Windows 重启仍由系统和用户完成。脚本会明确输出剩余步骤，不会把“已复制文件”当成“已完成桌面验收”。

## 1. 获取仓库和 uv

推荐三平台统一使用 **uv + Python 3.14**。仓库的 `.python-version` 固定 3.14 系列，uv 会在需要时下载解释器，无需另装全局 Python。可用 Git 克隆，也可以从 GitHub 下载 ZIP 并解压，不强制安装 Git。

```sh
git clone https://github.com/yhzhu99/rime-flypy.git
cd rime-flypy
```

安装 uv：

- Windows：`winget install -e --id astral-sh.uv`，安装后重新打开终端。
- macOS：已有 Homebrew 时用 `brew install uv`。
- Linux：按 [uv 官方安装指南](https://docs.astral.sh/uv/getting-started/installation/) 安装。

在仓库目录执行 `uv python install 3.14` 可提前准备解释器；后续统一使用 `uv run`。使用常规 CPython 构建，不额外启用 free-threaded 变体。Windows x64 的内核检查需要 x64 Python。

整机约定：个人项目和 Python 工具优先由 uv 管理；每个项目独立环境并按依赖选择 Python 版本。不要替换 Linux/macOS 系统 Python，也不要卸载其他应用自带的解释器。这个仓库的安装脚本只使用标准库，无需创建 Python 包项目或维护应用依赖锁文件；测试依赖由 `tests/requirements.txt` 固定并通过 uv 隔离运行。

## 2. 按平台安装依赖

### Windows x64

使用**当前桌面用户**的管理员 PowerShell，在仓库目录执行：

```powershell
# 可先不带 -Apply 预览；以下命令才执行安装。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\platforms\windows\install-rime.ps1 -Apply
```

脚本从官方 GitHub Release 下载经过 SHA-256 校验的小狼毫 0.17.4 和带 Lua 的 librime 1.17.0。它会安装小狼毫、备份被替换的内核、更新内核并启动服务。已是这套版本时跳过；遇到其他位置/版本的安装则停止，让你按实际环境更新，不强行覆盖。

这是固定的已验证版本，不是“自动追最新”。Windows ARM64 或其他架构请使用[官方小狼毫发布](https://github.com/rime/weasel/releases)，并确保内核支持 Lua 和固定语言选择。`setup.py` 的 Windows/Linux 版本预检要求 librime ≥ 1.17。

### Linux：统一使用 IBus-Rime + keyd

使用发行版的软件包管理器安装 IBus-Rime、librime 的 Lua 插件、keyd。常见包名如下，执行前以所用发行版的软件包索引为准：

| 发行版 | 安装示例 |
| --- | --- |
| Debian / Ubuntu | `sudo apt install ibus-rime librime-plugin-lua keyd` |
| Fedora | `sudo dnf install ibus-rime librime-lua keyd` |
| Arch Linux | `sudo pacman -S ibus-rime librime-lua keyd` |

**版本是前提**：旧系统仓库可能没有 keyd，或者 librime 太旧。必须先升级软件包来源/发行版，或按 [librime](https://github.com/rime/librime)、[IBus-Rime](https://github.com/rime/ibus-rime)、[keyd](https://github.com/rvaiya/keyd) 的官方安装说明安装支持的版本。本仓库不会自动添加第三方软件源，也不会在旧版本上假装配置成功。

自动系统改键入口适用于使用 systemd 的桌面 Linux，并要求 keyd 支持 `check` 命令。非 systemd 环境使用 `--config-only`，再按 keyd 官方文档设置服务。若 `/etc/keyd/` 已有其他 `.conf`，入口会停止，要求先按 [Linux 文档](linux.md) 合并，避免两套规则争抢同一键盘。

### macOS：鼠须管 + Karabiner-Elements

已安装 [Homebrew](https://brew.sh/) 时，可执行：

```sh
brew install uv
brew install --cask squirrel karabiner-elements
```

也可以分别使用[鼠须管](https://github.com/rime/squirrel/releases)和 [Karabiner 官方安装器](https://karabiner-elements.pqrs.org/)。选择支持固定语言选择、Lua 和左右 Shift 区分的当前版本。首次安装后可能需要注销再登录。

## 3. 预览并应用

三平台使用相同命令。以下示例必须在仓库目录运行，以读取 `.python-version`：

```sh
# 只显示目标目录和将写入的文件，不写配置、不改键。
uv run setup.py

# 应用 Rime 配置与对应平台的系统改键配置。
uv run setup.py --apply
```

Windows 的 `--apply` 在同一用户的管理员终端中运行；Linux/macOS 用普通桌面用户运行，**不要使用 `sudo uv run setup.py`**。Linux 入口仅在安装 keyd 系统配置、管理服务时调用 sudo。

| 平台 | `--apply` 自动完成 | 你最后完成的步骤 |
| --- | --- | --- |
| Windows | 检查小狼毫及内核版本；备份并复制 Rime 配置；重新部署；合并五条注册表改键 | 选中小狼毫输入源，重启 Windows |
| Linux | 检查 IBus/keyd/内核；备份并复制 Rime 配置；验证、安装 keyd 配置；启用并重载服务 | 在桌面添加 IBus 的 Rime 输入源；设置 IBus 为输入法框架；重新部署/重启 IBus |
| macOS | 检查鼠须管和 Karabiner 安装；备份并复制 Rime 配置和 Karabiner 规则模板 | 授予 Karabiner 所需权限、启用三条规则、添加鼠须管输入源并重新部署 |

只复制输入法配置、不操作系统改键时：

```sh
uv run setup.py --apply --config-only
```

非默认用户目录可加 `--rime-dir "实际用户目录"`。预览和 `--config-only` 可用于排查，不需要安装全部前端依赖。目录中不属于仓库管理范围的文件保持原样；本机 `user.yaml`、`installation.yaml`、学习词库和构建缓存不复制。

### 输入源只使用 Rime

这是个人使用目标，不由脚本强制删除其他语言：Windows 在键盘列表中移除不需要的独立英文键盘；Linux 在桌面输入源中选择 Rime；macOS 在系统设置的“键盘 → 文本输入”添加鼠须管，并按系统允许的范围调整其他输入源。macOS 的安全输入框可能强制使用系统布局。不要为此卸载语言包或改变系统显示语言。

**固定中文键只在当前选中 Rime 时生效。** 如果仍保留其他输入源，要先选择 Rime；本仓库没有把 F13 做成强制唤回 Rime 的系统全局快捷键。

## 4. 验收

按 [README](../README.md#最终键位约定) 检查所有键位：左 Shift 固定英文；右 Alt 固定中文且不弹菜单；重复按不反转状态；右 Shift 输入大写；左 Ctrl/Alt 和 Caps/Esc 互换。具体平台排查见 [Windows](windows.md)、[Linux](linux.md)、[macOS](macos.md)。

Linux 和 macOS 的桌面端到端行为尚未实机验证。自动化测试验证文件部署、规则解析与 Rime 内核，不替代新电脑上的这一步。

## 备份、更新和回退

每次写配置前，会备份所有将被替换的文件，并打印 `manifest.json` 路径；未改变的文件不复制。默认备份位置：

- Windows：`%LOCALAPPDATA%\rime-flypy\backups`
- Linux：`${XDG_STATE_HOME:-~/.local/state}/rime-flypy/backups`
- macOS：`~/Library/Application Support/rime-flypy/backups`

更新仓库后再次执行 `setup.py --apply`。Karabiner 已启用的规则是配置副本；如果仓库规则有变化，需要在 Karabiner 中禁用旧规则再导入新版。

恢复某一次配置文件修改：

```sh
uv run setup.py --restore-config "那次备份目录/manifest.json"
```

恢复会先核对所有相关文件；存在后续编辑就停止，避免覆盖。它只恢复文件，不重启前端、不撤销系统改键，也不关闭 Karabiner 已启用的规则。新安装的软件也不会被卸载。

- Windows 的系统改键备份在同一目录的 `keyboard-windows.json`，用 `platforms/windows/keyboard.ps1 -Action Undo -BackupPath ...` 回退，再重启。若映射原本已完全一致，脚本没有改注册表，也不会产生该文件。
- Linux 的旧 keyd 配置保存为 `keyd-before.conf`，`keyd-backup.json` 记录之前是否存在。恢复旧文件；之前不存在则只删除 `/etc/keyd/rime-flypy.conf`，然后 `sudo keyd reload`。
- macOS 在 Karabiner 中禁用这三条规则。恢复资产 JSON 文件本身不会停用已启用的规则。

撤掉右 Alt 中文入口之前，应确保左 Shift 已恢复为 `commit_code` 或另有可用的中文入口。

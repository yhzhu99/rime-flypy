# Windows / 小狼毫

新电脑优先按 [完整配置指南](new-computer.md) 操作：安装依赖后，`uv run setup.py --apply` 会完成本页的配置复制、重新部署和注册表改键。下面保留各部分说明，便于单独预览、修改或回退。

## 部署输入法配置

安装小狼毫和支持固定语言功能、Lua 扩展的内核。本次参考环境：小狼毫 0.17.4 + librime 1.17.0。小狼毫 0.17.4 安装包自带的旧内核需要单独更新，官方维护者的说明见 [#1692](https://github.com/rime/weasel/issues/1692)。更新前备份安装目录；不要使用不含 Lua 插件的内核替换，否则既有扩展和 F13 处理器都会失效。

仅复制 Rime 配置及静态词库时，在仓库目录执行以下命令。入口会自动备份被替换的文件：

```powershell
uv run setup.py --apply --config-only
```

通过小狼毫托盘菜单执行“重新部署”。英文状态按 F13 也必须能回到中文；日志不应出现 `right_alt_f13` 加载失败。

## 系统按键映射

预览不需要管理员权限：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\platforms\windows\keyboard.ps1 -Action Plan
```

在管理员 PowerShell 中，进入仓库目录后应用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\platforms\windows\keyboard.ps1 -Action Apply
```

脚本合并五条物理键映射：Caps Lock/Escape 互换、左 Ctrl/Alt 互换、右 Alt `E038` → F13 `0064`。只替换这五个源键的配置，保留其他源键的映射。写入前保存完整旧值，默认备份目录为 `%LOCALAPPDATA%\rime-flypy\backups`，执行结果会打印具体文件名。

**保存工作后重启 Windows。** 注册表写入成功不代表当前会话已经改键。`Plan` 的 `changed: false` 只说明存储的配置一致，也不能证明已重启。

2026-11-11 的当前电脑已经写入这五条映射；再次执行会提示无需改动，不创建新备份。此前聊天中生成的备份是那次修改的回退依据，仓库不会公开上传本机备份。

## 输入源与外观

个人目标是只保留小狼毫输入源，中英文都在 Rime 内选择。Windows 设置中的键盘列表可移除不需要的独立美式键盘；不需要为此卸载语言包或改变 Windows 显示语言。仓库脚本不自动改语言列表，避免覆盖另一台电脑的语言需求。

`weasel.custom.yaml` 使用 `global_ascii: true` 共享中英文状态，保留原有配色及候选布局。系统改键是全局的；没有选中 Rime 时，右 Alt 只会产生 F13。

## 回退

先给 Rime 恢复一个中文入口：将 `Shift_L: set_ascii_mode` 改为 `Shift_L: commit_code`，重新部署。然后在管理员 PowerShell 中使用那次 Apply 打印的备份路径：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\platforms\windows\keyboard.ps1 -Action Undo -BackupPath '实际备份文件.json'
```

回退脚本要求当前完整映射仍与备份记录的应用结果一致；后续若有其他改键，它会停止，避免覆盖。完成后重启。F13 处理器可以留在 Rime 中，不会影响其他按键。

参考：[Windows 键码映射](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/keyboard-and-mouse-class-drivers)、[小狼毫](https://github.com/rime/weasel)、[librime](https://github.com/rime/librime) 。

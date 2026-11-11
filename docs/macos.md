# macOS / 鼠须管

新电脑优先按 [完整配置指南](new-computer.md) 安装依赖，再执行 `uv run setup.py --apply`。它会备份并部署 Rime 配置、复制 Karabiner 规则模板；首次权限确认和规则启用仍按本页说明完成。

## 部署 Rime

安装当前 [Squirrel / 鼠须管](https://github.com/rime/squirrel)，确认内核支持 `set_ascii_mode` 并带有 Lua 插件。旧版前端可能不能正确区分左右 Shift；遇到右 Shift 也改变语言时，应先升级并检查前端事件，不要把两侧都设成切换键。

仅部署 Rime 配置时，在仓库目录执行，原有文件会自动备份：

```sh
uv run setup.py --apply --config-only
```

在鼠须管菜单选择“重新部署”。`squirrel.custom.yaml` 提供横排候选、原始编码和 Catppuccin 配色；中英文由共用 `language_keys.lua` 在应用会话间同步。`app_options` 整体替换鼠须管的上游默认项，移除 VS Code、终端等应用的中英文/Vim 模式特例，只保留行内显示等兼容设置。不要添加 Windows 专属的 `global_ascii` 冒充鼠须管开关。

## 系统改键：Karabiner-Elements

安装 [Karabiner-Elements](https://karabiner-elements.pqrs.org/)，按官方引导授予必要的输入权限。它是 macOS 上的独立改键组件，需要运行；本仓库 JSON 不会自行安装软件或修改系统权限。

在仓库目录复制规则文件：

```sh
mkdir -p "$HOME/.config/karabiner/assets/complex_modifications"
cp platforms/macos/rime-flypy.json "$HOME/.config/karabiner/assets/complex_modifications/"
```

在 Karabiner 的 **Complex Modifications → Add rule** 中启用这三条 `rime-flypy` 规则：

1. Caps Lock 与 Escape 互换。
2. 左 Control 与左 Option 互换。
3. 右 Option 输出 F13，作为中文专用键。

先停用系统“修饰键”设置或 Karabiner Simple Modifications 中对相同键的重复映射。规则里的 `optional: any` 保留其他修饰键，所有映射针对原来的物理键；Command 和右 Control 没有改动。

**Option 对应 Windows/Linux 的 Alt，Command 不对应 Alt。** 本方案使用右 Option；不会把紧邻空格的右 Command 也改成中文键。

在 Karabiner-EventViewer 中确认右 Option 变成 F13。如果 macOS 的键盘快捷键设置把 F13 用于截图、Mission Control 或其他动作，先移除该冲突。选中鼠须管并聚焦输入框后再测试中文；右 Option 不负责从 ABC 输入源切换到鼠须管。

## 回退

先把 Rime 的左 Shift 改回 `commit_code` 并重新部署，恢复中文入口。然后在 Karabiner 中禁用这三条 `rime-flypy` 规则即可。复制到 assets 的 JSON 只是规则模板，删除它并不会自动关闭已经启用的规则。

macOS 方案目前提供了配置与静态检查，还未在真实 Mac 上验收。按仓库 README 的实机清单检查，尤其要确认左右 Shift 的区分和 F13 没有被系统截获。

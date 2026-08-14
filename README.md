# rime-flypy

小鹤音形输入法 Rime 挂接

## 使用方法

将本仓库中的内容放置在 Rime 的用户资料夹，重新部署即可。

- Windows（小狼毫 Weasel）：`%APPDATA%\Rime`
- Linux（IBus-Rime）：`~/.config/ibus/rime`

公共的方案和词库文件会在两个平台上共用。不同平台的前端设置分别位于：

- `weasel.custom.yaml`：Windows 小狼毫配置，包含 Catppuccin 配色、字体、圆角和横排候选等外观设置。
- `ibus_rime.custom.yaml`：Linux IBus-Rime 配置。应用光标处显示原始编码，光标位于编码末尾，候选窗口使用横排布局。

Rime 会根据当前前端自动读取对应的配置文件，因此两个文件可以同时保存在用户资料夹中，互不冲突。

## 更新配置

在 Rime 用户资料夹中执行：

```bash
git pull --ff-only
```

随后重新部署 Rime。Linux IBus-Rime 可以通过重启 IBus 并重新选择 Rime 来完成部署：

```bash
ibus restart
ibus engine rime
```

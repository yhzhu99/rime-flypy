# Linux / IBus-Rime

## 部署 Rime

本仓库统一使用 IBus-Rime。安装发行版提供的 IBus-Rime，同时确认实际 librime 包含固定语言功能和 Lua 插件。仓库测试使用 librime 1.17.0；老发行版可能需要更新相关包。无需维护第二套 Linux 输入法框架。

备份已有 Rime 用户目录。在仓库目录复制配置：

```sh
RIME_USER_DIR="$HOME/.config/ibus/rime"
mkdir -p "$RIME_USER_DIR"
cp ./*.yaml "$RIME_USER_DIR/"
cp -R lua flypy "$RIME_USER_DIR/"
```

IBus 可通过以下命令重启并选择 Rime，然后检查部署结果：

```sh
ibus restart
ibus engine rime
```

`ibus_rime.custom.yaml` 负责光标处原始编码与横排候选。

## 系统改键：keyd

安装 [keyd](https://github.com/rvaiya/keyd)，具体包名和安装方式以发行版为准。本配置使用 keyd 现有的修饰层处理 Ctrl/Alt，适用于 X11、Wayland 和控制台；keyd 本身需要作为系统服务运行。

检查 `/etc/keyd/` 是否已有配置。同一键盘若已经被其他 keyd 配置匹配，应把本仓库 `[main]` 中的五条映射合并到已有文件，不要并列放两个互相竞争的配置。也应取消桌面设置、XKB 或其他工具中重复的 Ctrl/Alt、Caps/Esc 改键。

没有已有 keyd 配置时，在仓库目录执行：

```sh
# 本仓库 CI 使用支持 check 命令的 keyd；旧版可先更新 keyd。
keyd check platforms/linux/rime-flypy.conf
sudo install -m 644 platforms/linux/rime-flypy.conf /etc/keyd/rime-flypy.conf
sudo systemctl enable --now keyd
sudo keyd reload
```

默认 `[ids] *` 作用于所有匹配的键盘。若只想改某一把键盘，先用 `sudo keyd monitor` 查看设备 ID，再用具体 ID 替换 `*`。

此时物理右 Alt 输出 F13，原来的 AltGr 字符输入功能不再可用。Rime 必须是当前输入法，桌面也不能把 F13 注册成其他全局快捷键。跨应用的输入模式共享由 IBus 的设置决定；不要照抄 Windows 的 `global_ascii` 当作通用开关。

## 回退

先将 Rime 的左 Shift 改回 `commit_code` 并重新部署，恢复中英文切换入口。若创建了独立的 `/etc/keyd/rime-flypy.conf`，删除这一个文件后执行 `sudo keyd reload`；若合并到了已有配置，则恢复备份中的这五条映射。其他 keyd 配置继续保留。

keyd 出现按键异常时，其官方应急组合是 Backspace + Escape + Enter，可终止 keyd。修改后按仓库 README 的实机清单验证。

# 验证范围与已知边界

配置整理日期：2026-11-11。

## 已执行的本地验证

- Windows 已安装的小狼毫 0.17.4 / librime 1.17.0 加载仓库配置副本，27 项真实引擎检查通过：中英文起始状态下固定选择、重复按键、F13 按下和释放消费、普通右 Shift/Alt 不改模式、Shift+A 不误切换、未完成编码保留/清除、中文上屏、英文直通、Lua 日期翻译器。
- Windows 映射合并函数在 PowerShell 7 和 Windows PowerShell 5.1 通过：无旧值、重复应用、保留无关映射、替换指定源键、拒绝畸形数据及重复源键。测试不写注册表。
- Windows API 确认扫描码 `0064` 对应 `VK_F13`，小狼毫源码有对应 F13 翻译；当前电脑注册表包含目标五条映射。
- 公共 YAML、词库/方案/Lua 引用以及 Linux/macOS 的键位一致性检查通过。

## 持续集成

`.github/workflows/validate.yml` 执行三类检查：

1. Windows、Ubuntu、macOS 的 Python 配置检查；Windows 另运行映射行为测试。
2. 下载固定版本、校验 SHA-256 的官方 librime 和小狼毫包，仅解压到工作目录，不安装输入法，在临时 Rime 用户目录测试 27 项真实引擎行为。
3. 构建固定提交的 keyd，用 `keyd check` 验证配置语法。不启动 keyd 服务，也不接管 CI 键盘。

## 尚未验证的部分

- Windows 系统映射需要重启；本次没有自动重启，因此未完成物理右 Alt 到实际应用中文上屏的端到端验收。
- Linux 未在桌面会话中验证 keyd → IBus/Fcitx5 → 应用的完整链路。
- macOS 未在真实 Mac 上启用 Karabiner/鼠须管进行验收。CI 的 macOS 配置检查不等于桌面实测。
- F13 只对当前已选中的 Rime 生效。其他输入源、系统快捷键冲突、不接受输入法事件的窗口及远程桌面可能改变结果，需要按实际环境检查。
- 跨应用中英文状态的共享不是跨平台统一的 Rime 配置：Windows 配置 `global_ascii`，Linux 由输入法框架管理，macOS 还受鼠须管应用选项影响。

## 实现依据

- [librime 固定语言选择 PR #1015](https://github.com/rime/librime/pull/1015)
- [小狼毫更新内核的讨论 #1692](https://github.com/rime/weasel/issues/1692)
- [小狼毫 F13 键码翻译](https://github.com/rime/weasel/blob/0.17.4/WeaselTSF/KeyEvent.cpp)
- [鼠须管键码翻译](https://github.com/rime/squirrel/blob/master/sources/MacOSKeyCodes.swift)
- [keyd 配置与命令说明](https://github.com/rvaiya/keyd/blob/master/docs/keyd.scdoc)
- [Karabiner Complex Modifications](https://karabiner-elements.pqrs.org/docs/manual/configuration/configure-complex-modifications/)

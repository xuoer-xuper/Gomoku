# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

暂无。

## [0.3.0] - 2026-09-15

### 新增

- 大厅 / 战绩 / 对局三页布局，本地保存并查询对战记录
- 首次打开需设置昵称；创建房间可设置是否悔棋、每手思考时间
- 随机房间号，局域网 UDP 发现
- 立体棋子、落子缩放与连五金圈动画
- 投降；离开进行中的房间判负
- 终局棋盘中央显示胜负图标，提供离开与再战

### 修复

- 悔棋同意按钮被挤出侧栏点不到
- 悔棋改为撤回自己上一手（必要时连同对方应手一起撤）

### 变更

- 对局中不能再战，再战需终局且对方同意
- 大厅创建 / 加入卡片等宽，思考时间改为宽下拉

## [0.2.1] - 2026-09-15

### 修复

- 房间号不再使用 Clash/VPN 的 `198.18.x` 等虚地址，避免另一台电脑 `WinError 10061` 拒绝连接
- 创建房间时尝试放行 Windows 防火墙；加入失败时改为后台连接并 UDP 再发现房主
- 大厅不再每帧重绘棋盘，减轻机房电脑卡顿

### 变更

- 恢复 `docs/` 产品说明、功能模块图、系统架构图与通讯协议

## [0.2.0] - 2026-09-15

### 新增

- 单窗口桌面界面：大厅与棋盘一体，侧栏聊天
- 文字对话、悔棋（需对方同意）、再战（需对方同意）
- `build_exe.bat` 打包无需安装的 `Gomoku.exe`

### 变更

- 展现层改为 Tkinter，默认不再依赖 Pygame
- 创建房间者即房主的流程保持不变，界面重做

## [0.1.1] - 2026-09-15

### 新增

- 开始界面：填写昵称后「创建房间」或「加入房间」
- 创建房间的玩家即为房主，本进程内嵌对局服务，不再单独开 server 窗口
- 房间号由局域网 IP 与端口编码而成，客人输入房间号即可加入
- 创建房间后自动复制房间号，棋盘标题栏展示房间号

### 变更

- `python -m gomoku` 默认打开开始界面
- `gomoku server` / `gomoku client` 保留为高级用法

## [0.1.0] - 2026-09-15

### 新增

- 15 路自由五子棋规则：落子合法性、连五胜负、棋盘下满和棋
- 房主模式 TCP 对局服务，JSON 行协议完成加入、落子、广播与结算
- Pygame 棋盘绘制、回合提示、最新一手高亮、胜负结果展示
- 局域网双人联机：一台电脑启动 `gomoku server`，两名玩家启动客户端
- 产品说明、功能模块图、系统架构图与通讯协议文档

[Unreleased]: https://github.com/xuoer-xuper/Gomoku/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/xuoer-xuper/Gomoku/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/xuoer-xuper/Gomoku/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/xuoer-xuper/Gomoku/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/xuoer-xuper/Gomoku/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/xuoer-xuper/Gomoku/releases/tag/v0.1.0

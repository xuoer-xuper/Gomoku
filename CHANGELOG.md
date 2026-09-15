# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

暂无。

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

[Unreleased]: https://github.com/xuoer-xuper/Gomoku/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/xuoer-xuper/Gomoku/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/xuoer-xuper/Gomoku/releases/tag/v0.1.0

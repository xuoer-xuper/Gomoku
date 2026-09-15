# 联机五子棋 Gomoku

Python 双人局域网联机五子棋。不依赖云主机：其中一名玩家在本机启动对局服务（房主），另一名玩家通过局域网 IP 连接即可对战。

当前版本：**0.1.0**

## 联机方式

```text
房主电脑                         客人电脑
gomoku server  ◄──── TCP ────►  gomoku client
gomoku client
         局域网 IP:8765
```

- 两台电脑需在同一局域网（同一 Wi-Fi / 路由器）
- 房主先启动服务进程，再打开自己的棋盘客户端
- 客人使用房主的 IPv4 地址连接
- 同一台电脑可开一个服务 + 两个客户端，连接 `127.0.0.1` 做本地自测

## 技术栈

| 分层 | 选型 |
| --- | --- |
| 展现层 | Pygame（pygame-ce）绘制 15 路棋盘 |
| 通讯层 | asyncio TCP + JSON 行协议 |
| 服务层 | 自研规则引擎（落子合法性、连五判定、回合） |
| 数据层 | 内存棋盘与对局快照，无数据库 |
| 规则 | 15 路自由五子棋，连五即胜，黑先 |

## 安装与运行

需要 Python 3.11+。展现层依赖 **pygame-ce**（与 `import pygame` 兼容；官方 pygame 暂无 3.14 轮子）。

```bash
pip install -e ".[dev]"
```

房主（对局域网监听）：

```bash
python -m gomoku server --host 0.0.0.0 --port 8765
```

客户端：

```bash
python -m gomoku client --host 127.0.0.1 --port 8765 --name 玩家1
python -m gomoku client --host 192.168.x.x --port 8765 --name 玩家2
```

操作：鼠标点击交叉点落子，ESC 退出。

## 文档

- [产品功能说明](docs/product.md)
- [系统架构](docs/architecture.md)
- [功能模块图](docs/modules.md)
- [通讯协议](docs/protocol.md)
- [更新日志](CHANGELOG.md)

## Git 工作流

- 主分支 `main`，开发分支 `dev`
- 版本号从 `0.1.0` 递增；发布时在 `main` 打附注标签 `v0.1.0`
- 提交信息遵循 Angular 规范，说明使用中文

```bash
pytest
```

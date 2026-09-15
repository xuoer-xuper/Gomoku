# 系统架构

## 1. 总体结构

系统采用四层架构，依赖方向单向向下：

**展现层 → 通讯层 → 服务层 → 数据层**

创建房间的进程同时承载通讯层服务端、服务层与数据层，以及房主自己的展现层。客人进程只承载展现层与通讯层客户端。规则只在房主进程计算一份，避免两台机器各判各的。

```mermaid
flowchart TB
    subgraph guest [客人进程]
        UI2[展现层 GomokuDesktop]
        C2[通讯层 GameClient]
        UI2 --> C2
    end

    subgraph host [房主进程]
        UI1[展现层 GomokuDesktop]
        C1[通讯层 GameClient]
        UI1 --> C1
        SRV[通讯层 GameServer 0.0.0.0]
        ANN[通讯层 UDP 房间宣告]
        SM[通讯层 SessionManager / Room]
        GS[服务层 GameService]
        REF[服务层 Referee]
        ST[数据层 InMemoryGameStore]
        BD[数据层 Board / GameState]
        SRV --> SM
        ANN --> SRV
        SM --> GS
        GS --> REF
        SM --> ST
        GS --> BD
        ST --> BD
    end

    C1 -->|本机 TCP 127.0.0.1| SRV
    C2 -->|局域网 TCP JSON 行协议| SRV
    C2 -.->|房间号连不上时 UDP 发现| ANN
```

## 2. 分层职责

### 2.1 展现层（presentation）

- 技术：Tkinter 单窗口
- 模块：`GomokuDesktop`、`BoardCanvas`、`theme`
- 职责：大厅、棋盘、聊天侧栏、悔棋/再战确认
- 约束：不实现胜负规则，只消费 `GameClient.poll()` 的消息

### 2.2 通讯层（communication）

- 技术：asyncio TCP（服务端）+ 阻塞 socket 后台线程（客户端）；UDP 宣告为跨机兜底
- 模块：`Message`、`GameServer`、`SessionManager`、`Room`、`GameClient`、`room_code`、`lan`、`discover`、`firewall`
- 职责：
  - 把局域网地址编进房间号（跳过 `127.0.0.1`、`198.18.0.0/15` 等代理虚地址）
  - 监听 `0.0.0.0`，尝试写入 Windows 防火墙规则
  - 连接建立、两人匹配、消息编解码
  - 把合法落子转给服务层并广播结果
- 约束：不判断连五，只转发服务层给出的结果

### 2.3 服务层（service）

- 模块：`GameService`、`Referee`
- 职责：回合校验、落子合法性、连五检测、和棋结算、悔棋恢复、再战重置
- 约束：无 IO、无 Tkinter、可单测

### 2.4 数据层（data）

- 模块：`Board`、`Position`、`Stone`、`GameState`、`InMemoryGameStore`
- 职责：保存交叉点占用和对局快照
- 约束：棋盘只存子，不判断输赢（单一职责）

## 3. 运行时过程

```mermaid
sequenceDiagram
    participant H as 房主窗口
    participant S as 内嵌服务
    participant G as 客人窗口
    H->>S: 创建房间，监听 0.0.0.0
    H->>H: 房间号编码真实局域网 IP
    H->>S: 本机 TCP 加入（黑方）
    G->>G: 解码房间号
    G->>S: TCP connect 局域网 IP
    alt 连接被拒绝
        G->>S: UDP 发现房间号
        S-->>G: 房主真实 IP
        G->>S: 再次 TCP connect
    end
    G->>S: join
    S-->>H: game_start black
    S-->>G: game_start white
    H->>S: place
    S-->>H: move
    S-->>G: move
    Note over S: 连五后双方收到 game_over
```

## 4. 跨机连接（10061）

同一台电脑两窗口正常、另一台电脑 `WinError 10061`（目标计算机积极拒绝）时，通常是：

1. 房间号里的 IP 不是机房网卡地址，而是代理 TUN（例如 Clash `198.18.0.1`）。客人去连这个地址，本机或对端没有人在听，立即 RST。
2. 房主进程听在 `0.0.0.0`，但 Windows 防火墙丢掉或拒绝入站 SYN。本机回环不受影响，所以本机自测仍成功。

对应设计：

- `lan.local_ipv4()` 读取 `GetIpAddrTable`，丢掉环回、APIPA、`198.18/15`、CGNAT，优先 RFC1918
- 创建房间时尽量添加防火墙允许规则
- 客人 TCP 失败后用 UDP 按房间号再找一次房主

## 5. SOLID 对应关系

| 原则 | 体现 |
| --- | --- |
| S 单一职责 | `Board` 只存子，`Referee` 只判规则，`BoardCanvas` 只绘制 |
| O 开闭 | `IGameStore` 可替换为其他存储而无需改 `Room` |
| L 里氏替换 | `InMemoryGameStore` 满足 `IGameStore` 协议 |
| I 接口隔离 | 客户端只暴露 `connect/join/place/chat/poll/close` 等 |
| D 依赖倒置 | 展现层依赖 `GameClient`，服务层依赖 `Referee` 与数据对象，不反向依赖 UI |

## 6. 目录结构

```text
src/gomoku/
  presentation/    展现层（Tkinter 桌面）
  communication/   通讯层（协议、房主、房间号、局域网）
  service/         服务层（规则、悔棋、再战）
  data/            数据层（棋盘与快照）
  config.py
  exceptions.py
  __main__.py
docs/              产品、模块、架构、协议
tests/             规则、房间号、局域网地址、联机测试
```

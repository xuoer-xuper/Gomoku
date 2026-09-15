# 通讯协议

传输：TCP。编码：UTF-8。帧格式：一条 JSON 对象 + `\n`。

统一信封：

```json
{"type": "place", "payload": {"row": 7, "col": 7}}
```

## 客户端 → 服务端

| type | payload | 说明 |
| --- | --- | --- |
| `join` | `{ "name": "Alice" }` | 登记昵称，须第一条发送 |
| `place` | `{ "row": 0, "col": 0 }` | 请求在交叉点落子，0-based |
| `chat` | `{ "text": "你好" }` | 对局聊天，服务端补上发送者昵称后广播 |
| `undo_request` | `{}` | 向对方请求悔棋 |
| `undo_reply` | `{ "accepted": true }` | 同意或拒绝悔棋 |
| `rematch_request` | `{}` | 向对方请求再战 |
| `rematch_reply` | `{ "accepted": true }` | 同意或拒绝再战 |
| `ping` | `{}` | 心跳，回复 `pong` |

## 服务端 → 客户端

| type | payload | 说明 |
| --- | --- | --- |
| `joined` | `{ "player_id", "name" }` | 加入成功 |
| `waiting` | `{ "message" }` | 人数不足，等待对手 |
| `game_start` | `{ "your_color", "opponent_name", "board_size" }` | 开局，`black` / `white` |
| `move` | `{ "row", "col", "color", "next_turn" }` | 合法落子广播 |
| `invalid` | `{ "reason" }` | 仅发送给违规方 |
| `game_over` | `{ "winner", "reason", "row", "col" }` | `five_in_a_row` 或 `draw` |
| `chat` | `{ "name", "text", "system" }` | 聊天或系统提示 |
| `undo_request` | `{ "name" }` | 对方请求悔棋 |
| `undo` | `{ "row", "col", "color", "next_turn" }` | 悔棋成功，撤销该点 |
| `undo_rejected` | `{}` | 对方拒绝悔棋 |
| `rematch_request` | `{ "name" }` | 对方请求再战 |
| `opponent_left` | `{}` | 对手断开 |
| `error` | `{ "message" }` | 协议或状态错误 |
| `pong` | `{}` | 心跳应答 |

`your_color`、`color`、`winner` 取值：`black`、`white`；和棋时 `winner` 为 `null`。

## 房间号

房间号把 IPv4（32 位）和端口（16 位）编成 10 个字符（字母表去掉 `0O1I`），显示为 `XXXXX-XXXXX`。

客人解码后对 `ip:port` 发起 TCP。本机创建者始终连 `127.0.0.1`，避免走网卡。

## UDP 发现（跨机兜底）

当解码出的 IP 无法 TCP 连通时，客人向提示地址与局域网广播发送：

```text
GOMOKU_DISCOVER <房间号>
```

房主若房间号匹配，单播回复：

```text
GOMOKU_HOST <房间号> <端口>
```

客人改用回复来源 IP 再连 TCP。UDP 与 TCP 使用同一端口号，互不占用。

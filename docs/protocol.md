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
| `opponent_left` | `{}` | 对手断开 |
| `error` | `{ "message" }` | 协议或状态错误 |
| `pong` | `{}` | 心跳应答 |

`your_color`、`color`、`winner` 取值：`black`、`white`；和棋时 `winner` 为 `null`。

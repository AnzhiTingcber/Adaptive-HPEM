# 类微信 App（前后端分离）项目蓝图

## 1. 目标与范围（MVP）

优先做一个可上线的最小版本（MVP），覆盖以下核心能力：

- 账号体系：手机号/验证码登录、JWT 鉴权、刷新令牌。
- 通讯录：搜索用户、加好友、好友列表。
- 单聊：文本消息实时收发、消息落库、离线拉取。
- 会话列表：最近会话、未读计数、最后一条消息预览。
- 基础设置：头像、昵称、签名。

> 先做“能稳定聊天”的主链路，再做群聊、朋友圈、音视频等复杂功能。

## 2. 技术栈建议（前后端分离）

### 前端（Web + H5 优先）

- 框架：Vue 3 + TypeScript + Vite
- 状态管理：Pinia
- 路由：Vue Router
- UI：Naive UI / Element Plus（任选）
- 网络层：Axios（REST） + 原生 WebSocket（实时消息）
- 工程化：ESLint + Prettier + Vitest

### 后端（Java）

- 框架：Spring Boot 3 + Spring Web
- 实时通信：Spring WebSocket（STOMP）或 Netty（高并发场景）
- 鉴权：Spring Security + JWT + Refresh Token
- 数据访问：Spring Data JPA / MyBatis-Plus（按团队习惯二选一）
- 数据库：PostgreSQL（关系型数据）
- 缓存：Redis（在线状态、会话未读计数、限流）
- 对象存储：MinIO / OSS（头像、图片）
- 消息队列（可选第二阶段）：RabbitMQ / Kafka（消息投递解耦）

### 基础设施

- 部署：Docker + Docker Compose（开发/测试）
- 网关：Nginx
- 观测：Prometheus + Grafana（可选）
- 日志：Loki / ELK（可选）

## 3. 推荐目录结构（Monorepo）

```text
wechat-like-app/
├─ apps/
│  ├─ web/                  # Vue 前端
│  └─ server/               # Spring Boot 后端
├─ packages/
│  ├─ shared-types/         # 前后端共享类型（DTO/枚举）
│  └─ eslint-config/
├─ infra/
│  ├─ docker-compose.yml
│  └─ nginx/
├─ docs/
│  ├─ api/
│  ├─ db/
│  └─ architecture/
└─ README.md
```

## 4. 核心模块拆解

### 4.1 用户与认证模块

- 注册/登录（验证码）
- JWT + Refresh Token
- 设备登录态管理（可踢设备）
- 风控：验证码频控、IP 限流

### 4.2 好友关系模块

- 用户搜索（手机号/ID）
- 发起好友申请 / 同意 / 拒绝
- 黑名单与删除好友

### 4.3 消息模块（核心）

- 客户端连接 WebSocket（登录后建立）
- 消息上行：发送消息时生成 clientMsgId（幂等）
- 服务端回执：ack + serverMsgId + 发送时间
- 消息持久化：按会话存储
- 消息下行：在线推送，离线拉取补偿

### 4.4 会话模块

- 会话列表（最后消息、未读数、置顶）
- 已读回执（进入会话后上报）
- 未读计数的 Redis 缓存与数据库对账

## 5. 数据模型（MVP）

建议先定义以下核心表：

- `users`：用户基本信息
- `auth_identities`：登录凭证（手机号等）
- `friendships`：好友关系
- `friend_requests`：好友申请
- `conversations`：会话
- `conversation_members`：会话成员
- `messages`：消息主体
- `message_receipts`：送达/已读回执

示例（messages）：

- `id`（雪花/UUID）
- `conversation_id`
- `sender_id`
- `type`（text/image/file）
- `content`（JSON）
- `client_msg_id`（幂等）
- `created_at`
- 索引：`(conversation_id, created_at desc)`

## 6. API 与实时协议建议

### REST API（示例）

- `POST /auth/login`
- `POST /auth/refresh`
- `GET /users/profile`
- `PUT /users/profile`
- `GET /friends`
- `POST /friend-requests`
- `POST /friend-requests/:id/accept`
- `GET /conversations`
- `GET /conversations/:id/messages?cursor=...`

### WebSocket 事件（示例）

- `msg.send`：客户端发送消息
- `msg.ack`：服务端确认接收
- `msg.push`：服务端推送新消息
- `msg.read`：客户端上报已读
- `presence.update`：在线状态变更

## 7. 安全与一致性关键点

- 所有写操作带 `requestId/clientMsgId`，防重复提交。
- 登录与敏感接口做限流（IP + userId 双维度）。
- WebSocket 鉴权需绑定 token + deviceId。
- 头像等资源使用签名 URL，避免公开桶。
- 聊天消息采用“先入库后回执”保证可靠性。

## 8. 开发节奏（8 周参考）

- 第 1-2 周：项目初始化、认证、用户资料
- 第 3-4 周：好友体系、单聊消息链路
- 第 5-6 周：会话列表、未读与已读回执
- 第 7 周：压测、异常恢复、监控
- 第 8 周：灰度发布与问题修复

## 9. 下一步可执行清单

1. 初始化 Monorepo（`apps/web` + `apps/server` + `packages/shared-types`）。
2. 完成数据库 ER 图与第一版迁移脚本。
3. 打通“登录 -> 加好友 -> 单聊发消息 -> 会话列表更新”闭环。
4. 增加单元测试和接口契约测试（OpenAPI + mock）。
5. 部署开发环境（Docker Compose：Postgres + Redis + MinIO）。

---

如果你愿意，我下一步可以直接给你生成：

- 前端（Vue3）基础脚手架目录；
- 后端（Spring Boot）模块化代码骨架；
- 一套可跑通的登录 + 单聊最小示例接口与 WebSocket 事件。

# Adaptive-HPEM / WeChat-like App Scaffold

这是基于 `PROJECT_BLUEPRINT_CN.md` 的下一步落地版本：

- `apps/web`：Vue 3 + Vite + TypeScript 前端骨架
- `apps/server`：Spring Boot 3（Java 17）后端骨架
- `infra/docker-compose.yml`：本地依赖（PostgreSQL / Redis / MinIO）
- `packages/shared-types`：前后端共享类型占位目录

## 快速开始

### 1) 启动基础依赖

```bash
docker compose -f infra/docker-compose.yml up -d
```

### 2) 启动后端

```bash
cd apps/server
mvn spring-boot:run
```

健康检查：`GET http://localhost:8080/api/health`

WebSocket 握手地址：`ws://localhost:8080/ws`

### 3) 启动前端

```bash
cd apps/web
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 下一步建议

1. 后端：补齐认证模块（Spring Security + JWT）与用户模块。
2. 前端：补齐登录页、会话列表页、聊天页。
3. 联调：接入 WebSocket 消息发送与 ack。

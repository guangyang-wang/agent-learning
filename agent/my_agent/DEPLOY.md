# 部署说明（Docker + nginx）

## 部署信息

| 项 | 值 |
| --- | --- |
| 服务器 | `49.232.47.65`（Ubuntu，x86_64） |
| 登录用户 | `wangguangyang`（已配置 SSH 密钥） |
| 项目目录 | `/home/wangguangyang/my_agent` |
| 对外端口 | `80`（需在腾讯云安全组放行） |

## 架构

```
浏览器 ──> nginx:80 ──┬─ /           静态文件（web/dist，Vue SPA）
                      └─ /api/*      反向代理到 backend:8000（去掉 /api 前缀）
                                      backend 容器：uvicorn + FastAPI
```

后端以单个 uvicorn 进程运行：SQLite 计数和「同一时间只允许一个任务」的锁都依赖单进程，
不要改成 `--workers N`。

## 数据持久化

宿主机目录挂载进容器，容器重建不会丢数据：

| 宿主机 | 容器 | 内容 |
| --- | --- | --- |
| `./data/memory` | `/app/memory` | 短期记忆、使用次数计数 `usage.db` |
| `./data/chroma_db` | `/app/chroma_db` | RAG 向量库 |
| `./data/uploads` | `/app/data/uploads` | 上传的课件原件 |

**清零使用次数**（发布前想重置 50 次额度）：

```bash
cd /home/wangguangyang/my_agent
docker compose stop backend
rm -f data/memory/usage.db
docker compose start backend
```

## 首次部署步骤

### 1. 本地构建前端并上传

```bash
# 本地项目根目录
cd web && npm run build && cd ..

# 打包上传（排除依赖、虚拟环境和本地运行数据）
cd /d/agent/agent/my_agent
tar czf - \
  --exclude=.git --exclude=.venv --exclude=web/node_modules \
  --exclude=.pytest_cache --exclude=.idea --exclude=.claude \
  --exclude=memory --exclude=chroma_db --exclude=data \
  --exclude=.env \
  . | ssh wangguangyang@49.232.47.65 \
  'mkdir -p /home/wangguangyang/my_agent && tar xzf - -C /home/wangguangyang/my_agent'

# 单独上传密钥配置（只在服务器上存在，不进 tar、不进 git）
scp .env wangguangyang@49.232.47.65:/home/wangguangyang/my_agent/.env
```

### 2. 服务器上创建数据目录并启动

```bash
ssh wangguangyang@49.232.47.65
cd /home/wangguangyang/my_agent

mkdir -p data/memory data/chroma_db data/uploads

# 首次会安装 Python 依赖，约 5-10 分钟
docker compose up -d --build
```

### 3. 检查

```bash
docker compose ps
docker compose logs -f backend    # Ctrl+C 退出日志
curl http://127.0.0.1/api/health  # 期望 {"status":"ok"}
curl http://127.0.0.1/api/usage   # 期望 {"used":0,"limit":50,"remaining":50}
```

浏览器打开 `http://49.232.47.65/`。若无法访问，到腾讯云控制台
「安全组」放行 TCP 80 端口（后端 8000 不对外暴露，不必放行）。

## 日常更新

代码改动后，在**本地**重新构建前端再上传，然后在服务器上重建后端镜像：

```bash
# 本地：web 有改动就重新 build；后端源码有改动不用 build
cd web && npm run build && cd ..

tar czf - \
  --exclude='./.git' --exclude='./.venv' --exclude='./web/node_modules' \
  --exclude='./.pytest_cache' --exclude='./.idea' --exclude='./.claude' \
  --exclude='./memory' --exclude='./chroma_db' --exclude='./data' \
  --exclude='./src/chroma_db' --exclude='./src/agent/chroma_db' \
  --exclude='./.env' \
  . | ssh wangguangyang@49.232.47.65 \
  'tar xzf - -C /home/wangguangyang/my_agent'

# 服务器：后端是 Docker 镜像，源码变了必须重建；纯前端改动可跳过 --build
cd /home/wangguangyang/my_agent
docker compose up -d --build
```

只改了前端（`web/`）时，`web/dist` 是 bind mount 进 nginx 的，上传后无需重建容器，
刷新浏览器即可；浏览器缓存可用 `Ctrl+F5` 清掉。

## 常用运维命令

```bash
cd /home/wangguangyang/my_agent

docker compose ps                 # 状态
docker compose logs -f backend    # 后端日志
docker compose logs -f web        # nginx 日志
docker compose restart backend    # 重启后端
docker compose down               # 停止并删除容器（数据目录保留）
docker compose up -d --build      # 重新构建并启动
```

## 注意事项

- `.env` 含 DeepSeek / 硅基流动密钥，只放在服务器项目目录，权限建议 `chmod 600`。
- 入口问答在前端实现，只能挡住正常访问，不能替代鉴权；API 仍可被直接调用，
  使用次数限制（`USAGE_LIMIT`）是后端兜底。
- 并发锁是进程内锁，当前单容器单进程部署有效；未来扩成多实例需要改用 Redis 等分布式锁。

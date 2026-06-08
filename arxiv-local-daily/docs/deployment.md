# Cloudflare Tunnel 部署指南

这套部署方式适合把本地 arXiv Daily app 放到自己的服务器上，同时避免直接把 `8765` 暴露到公网。

## 文件结构

- `Dockerfile`: 构建 FastAPI/Uvicorn app 镜像。
- `docker-compose.yml`: 同时启动 app 和 `cloudflared`。
- `.env.example`: Cloudflare Tunnel token 模板，复制成 `.env` 后填写真实 token。
- `deploy/cloudflared/config.example.yml`: 可选的 named tunnel 配置模板；默认 Compose 使用 token mode。
- `scripts/backup_sqlite.sh`: 用 SQLite `.backup` 生成一致性数据库快照，并把 `config/` 一起打包。
- `config/llm.example.json`: LLM API 配置模板，复制成 `config/llm.local.json`。
- `config/summary_template.example.json`: Summary 模板配置，复制成 `config/summary_template.local.json`。

## 服务器准备

先在服务器安装 Docker 和 Docker Compose plugin。Ubuntu 上常见流程是：

```bash
sudo apt update
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

重新登录服务器后，把项目代码放到服务器，例如：

```bash
git clone <your-repo-url> arxiv-local-daily
cd arxiv-local-daily/arxiv-local-daily
```

准备本地配置：

```bash
cp .env.example .env
cp config/llm.example.json config/llm.local.json
cp config/summary_template.example.json config/summary_template.local.json
mkdir -p data backups
```

编辑 `config/llm.local.json`，填入 OpenAI-compatible API 的 `base_url`、`api_key` 和 `model`。编辑 `config/summary_template.local.json` 可以修改唯一的总结模板。

## Cloudflare 设置

前提：域名已经托管到 Cloudflare。

1. 进入 Cloudflare Zero Trust。
2. 创建一个 Cloudflare Tunnel，选择 Docker/token 部署方式。
3. 给 tunnel 添加 Public Hostname，例如 `papers.example.com`。
4. Service 填 `http://app:8765`。这里的 `app` 是 `docker-compose.yml` 里的服务名，不是服务器公网 IP。
5. 复制 Cloudflare 给出的 token，填入 `.env`：

```bash
CLOUDFLARE_TUNNEL_TOKEN=你的-token
```

## 不要暴露 8765

`docker-compose.yml` 故意没有给 `app` 写 `ports:`。这表示服务器公网不会打开 `8765`，只有同一个 Docker 网络里的 `cloudflared` 能访问 `http://app:8765`。

不要改成下面这种形式：

```yaml
ports:
  - "8765:8765"
```

如果你只是临时在服务器本机调试，可以用 SSH tunnel，而不是长期开放公网端口。

## 启动

```bash
docker compose up -d --build
```

检查状态：

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f cloudflared
```

浏览器打开你的域名，例如 `https://papers.example.com`。

## 构建镜像下载慢

Docker daemon 的 `registry-mirrors` 只影响 `docker pull python:3.12-slim`、`docker pull cloudflare/cloudflared:latest` 这一类镜像下载。构建 app 镜像时，如果卡在 `RUN apt-get update`，慢的是容器内部 Debian apt 源，不是 Docker Hub 源。

`Dockerfile` 默认会把 Debian 源切到 TUNA：

```env
DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
```

如果你的服务器在阿里云 ECS，可以在 `.env` 里改成阿里云内网源：

```env
DEBIAN_MIRROR=http://mirrors.cloud.aliyuncs.com/debian
DEBIAN_SECURITY_MIRROR=http://mirrors.cloud.aliyuncs.com/debian-security
```

然后重新构建：

```bash
docker compose build --no-cache app
docker compose up -d
```

如果卡在 `RUN python -m pip install ...`，慢的是 pip 从 PyPI 下载依赖。`.env` 里可以设置：

```env
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

阿里云可试：

```env
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

腾讯云可试：

```env
PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
```

修改后重新构建：

```bash
docker compose build --no-cache app
docker compose up -d
```

## 开启 Cloudflare Access

建议一定开启 Cloudflare Access，让这个 app 只允许你自己的邮箱或团队账号访问：

1. Cloudflare Zero Trust -> Access -> Applications。
2. Add an application -> Self-hosted。
3. Application domain 填 `papers.example.com`。
4. Policy 里只允许你的邮箱、指定邮箱域名或指定团队成员。

这一步比普通 WAF 更关键，因为 app 里会有论文数据、AI 配置状态和本地操作入口。

## 备份

手动备份：

```bash
./scripts/backup_sqlite.sh
```

备份文件会写到 `backups/arxiv-local-daily-<timestamp>.tar.gz`，里面包含 SQLite 快照和 `config/`。

可以用 cron 每天执行一次，例如：

```cron
30 3 * * * cd /path/to/arxiv-local-daily/arxiv-local-daily && ./scripts/backup_sqlite.sh >> backups/backup.log 2>&1
```

## 更新

```bash
git pull
docker compose up -d --build
docker compose logs -f app
```

## 常见问题

- 访问域名 502：先看 `docker compose logs -f cloudflared`，再确认 Public Hostname 的 service 是 `http://app:8765`。
- AI 不能运行：确认 `config/llm.local.json` 存在，并且 API key、base URL、model 都正确。
- 数据丢失：确认 `docker-compose.yml` 里保留了 `./data:/data`，SQLite 文件应在宿主机 `data/arxiv-local-daily.sqlite3`。
- 想确认没有暴露端口：`docker compose ps` 里 app 不应该出现 `0.0.0.0:8765->8765/tcp`。

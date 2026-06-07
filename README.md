# mihomo-ui-ubuntu-amd64-v0.1

一键部署 mihomo（Clash Meta）代理 + yacd Web 管理面板，支持订阅自动更新。

## 功能

- 🚀 一键部署 mihomo 代理服务
- 🖥 内置 yacd Web 管理面板（浏览器远程管理）
- 🔄 订阅自动更新（cron 每天凌晨 4 点）
- 🎯 自动选择最快节点（url-test）
- 🔁 节点故障自动转移（fallback）
- 🛡 支持 VLESS + Trojan 协议
- 🌏 中国 IP 直连，海外 IP 走代理

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/lingting0/mihomo-ui-ubuntu-amd64-v0.1.git
cd mihomo-ui-ubuntu-amd64-v0.1

# 2. 编辑配置，填入你的订阅地址
cp config.example.yaml config.yaml
nano config.yaml
# 修改 subscriptions: 下的订阅链接

# 3. 运行部署脚本
sudo bash setup.sh
```

部署完成后，浏览器打开 `http://服务器IP:9090/ui/` 即可进入管理面板。

## 文件说明

| 文件 | 说明 |
|------|------|
| `setup.sh` | 一键部署脚本 |
| `config.example.yaml` | 配置文件模板 |
| `update-sub.sh` | 订阅自动更新脚本 |
| `dashboard/` | yacd Web 管理面板 |

## 手动更新订阅

```bash
sudo bash /etc/mihomo/update-sub.sh
```

## 管理面板功能

- 🎛 切换代理节点
- 📊 查看节点延迟
- 📋 查看代理规则
- 🔗 查看活跃连接
- ⚙️ 修改配置（规则/策略组）

## Docker 部署（群晖 / 极空间 / 其他 NAS）

```bash
# 1. 克隆仓库
git clone https://github.com/lingting0/mihomo-ui-ubuntu-amd64-v0.1.git
cd mihomo-ui-ubuntu-amd64-v0.1

# 2. 创建配置目录
mkdir -p config

# 3. 复制并编辑配置模板
cp config.example.yaml config/config.yaml
# 编辑 config.yaml，修改 proxies: 下的节点，或写入订阅地址到 sub_url.txt

# 4. 启动
SUB_URL="你的订阅地址" docker compose up -d
```

面板地址：`http://NAS_IP:9090/ui/`

## 系统要求

- Ubuntu / Debian amd64（裸机部署）
- Docker / Docker Compose（NAS 部署，支持 ARM64/AMD64）
- Python 3.6+

## 协议支持

- VLESS（xhttp, ws, tcp, xtls-rprx-vision）
- Trojan（ws, tcp）

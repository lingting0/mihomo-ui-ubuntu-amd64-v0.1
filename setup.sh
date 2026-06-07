#!/bin/bash
# ============================================================
# mihomo + yacd 面板 一键部署脚本
# 适用于 Ubuntu/Debian amd64
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  mihomo + yacd 面板 一键部署${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}请用 sudo 运行此脚本${NC}"
   exit 1
fi

# 检查架构
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" ]]; then
    echo -e "${RED}仅支持 amd64 架构，当前: $ARCH${NC}"
    exit 1
fi

# ===== 1. 安装 mihomo =====
echo "[1/5] 安装 mihomo..."
if ! command -v mihomo &>/dev/null; then
    MIHOMO_VER="v1.19.27"
    MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VER}/mihomo-linux-amd64-${MIHOMO_VER}.gz"
    curl -L --max-time 120 -o /tmp/mihomo.gz "$MIHOMO_URL"
    gunzip /tmp/mihomo.gz
    install -m 755 /tmp/mihomo /usr/local/bin/mihomo
    rm -f /tmp/mihomo
    echo "mihomo 已安装"
else
    echo "mihomo 已存在: $(mihomo -v 2>&1 | head -1)"
fi

# ===== 2. 创建目录并复制文件 =====
echo "[2/5] 部署配置..."
MIHOMO_DIR="/etc/mihomo"
mkdir -p "$MIHOMO_DIR/dashboard"

# 复制配置模板（如果还没配置的话）
if [[ ! -f "$MIHOMO_DIR/config.yaml" ]]; then
    cp config.example.yaml "$MIHOMO_DIR/config.yaml"
    echo "已创建 config.yaml，请编辑填入你的订阅信息"
else
    echo "config.yaml 已存在，跳过"
fi

# 复制面板
cp -r dashboard/* "$MIHOMO_DIR/dashboard/"
echo "面板文件已部署"

# 复制更新脚本
cp update-sub.sh "$MIHOMO_DIR/"
chmod +x "$MIHOMO_DIR/update-sub.sh"

# ===== 3. 创建 systemd 服务 =====
echo "[3/5] 配置 systemd 服务..."
cat > /etc/systemd/system/mihomo.service <<'SERVICE'
[Unit]
Description=Mihomo Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable mihomo

# ===== 4. 设置 cron 自动更新 =====
echo "[4/5] 设置每日自动更新..."
(crontab -l 2>/dev/null | grep -v update-sub.sh; echo "0 4 * * * /etc/mihomo/update-sub.sh >> /etc/mihomo/mihomo-sub.log 2>&1") | crontab -
echo "cron 已设置: 每天凌晨 4 点自动更新订阅"

# ===== 5. 启动 =====
echo "[5/5] 启动 mihomo..."
systemctl restart mihomo
sleep 2

if systemctl is-active --quiet mihomo; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  部署成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "  管理面板: http://$(hostname -I | awk '{print $1}'):9090/ui/"
    echo "  配置文件: /etc/mihomo/config.yaml"
    echo "  更新脚本: /etc/mihomo/update-sub.sh"
    echo ""
    echo "  下一步: 编辑 config.yaml，填入你的订阅地址"
else
    echo -e "${RED}启动失败，请检查: journalctl -u mihomo -n 50${NC}"
    exit 1
fi

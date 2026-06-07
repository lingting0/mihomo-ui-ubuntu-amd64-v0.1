#!/bin/bash
set -e

MIHOMO_DIR="/etc/mihomo"
CONF="$MIHOMO_DIR/config.yaml"
TEMPLATE="$MIHOMO_DIR/config.yaml.template"

echo "========================================"
echo "  mihomo + yacd Docker"
echo "  架构: $(uname -m)"
echo "========================================"

# 检查是否有挂载的 config.yaml
if [[ -f "$CONF" ]]; then
    echo "[OK] 使用已存在的 config.yaml"
else
    echo "[INFO] 首次运行，从模板创建 config.yaml"
    cp "$TEMPLATE" "$CONF"
    echo "[WARN] 请编辑 config.yaml 填入你的订阅信息后重启容器"
fi

# 创建 sub_url.txt（如果用户提供了订阅地址环境变量）
if [[ -n "${SUB_URL:-}" ]] && [[ ! -f "$MIHOMO_DIR/sub_url.txt" ]]; then
    echo "$SUB_URL" > "$MIHOMO_DIR/sub_url.txt"
    echo "[OK] 已写入订阅地址"
fi

# 设置 cron 自动更新（默认每天凌晨4点）
CRON_HOUR="${UPDATE_HOUR:-4}"
echo "0 ${CRON_HOUR} * * * cd $MIHOMO_DIR && bash update-sub.sh >> $MIHOMO_DIR/mihomo-sub.log 2>&1" | crontab -
crond -b
echo "[OK] 自动更新: 每天 ${CRON_HOUR}:00"

echo "[OK] 启动 mihomo..."
exec /usr/local/bin/mihomo -d "$MIHOMO_DIR"

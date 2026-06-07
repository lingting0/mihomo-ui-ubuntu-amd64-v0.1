#!/bin/bash
set -euo pipefail

CONF=/etc/mihomo/config.yaml
DIR=/etc/mihomo
URL_FILE="$DIR/sub_url.txt"
LOG="$DIR/mihomo-sub.log"
TMP_NODES=$(mktemp)

finish() { rm -f "$TMP_NODES"; }
trap finish EXIT

ts() { date '+%F %T'; }

echo "[$(ts)] === START ===" | tee -a "$LOG"

SUB_URL=$(tr -d '\n\r' < "$URL_FILE")

echo "[$(ts)] fetching subscription..." | tee -a "$LOG"

# 下载并解码 base64，解析为代理节点列表
curl -sL --max-time 40 "$SUB_URL" | base64 -d > "$TMP_NODES" 2>/dev/null

if [[ ! -s "$TMP_NODES" ]]; then
  echo "[$(ts)] ERROR: empty or invalid subscription" | tee -a "$LOG"
  exit 1
fi

NODE_COUNT=$(wc -l < "$TMP_NODES")
echo "[$(ts)] got $NODE_COUNT proxy URLs" | tee -a "$LOG"

# 用 Python 解析节点并合并到 config.yaml
python3 - "$TMP_NODES" "$CONF" <<'PYEOF' 2>&1 | tee -a "$LOG"
import sys, re, yaml
from urllib.parse import urlparse, parse_qs, unquote

def parse_proxy(url):
    """解析 trojan:// 或 vless:// URL 为 mihomo 代理配置"""
    u = urlparse(url)
    scheme = u.scheme

    name = unquote(u.fragment) if u.fragment else (u.hostname or 'unknown')

    if scheme == 'trojan':
        return {
            'name': name,
            'server': u.hostname,
            'port': u.port or 443,
            'type': 'trojan',
            'password': u.username or '',
            'sni': u.hostname,
            'skip-cert-verify': True,
            'udp': True
        }

    elif scheme == 'vless':
        params = parse_qs(u.query)
        node = {
            'name': name,
            'type': 'vless',
            'server': u.hostname,
            'port': str(u.port or 443),
            'uuid': u.username or '',
            'alterId': 0,
            'cipher': 'auto',
            'udp': True,
            'tls': True,
            'skip-cert-verify': True
        }

        # flow
        if 'flow' in params:
            node['flow'] = params['flow'][0]

        # servername / sni
        if 'sni' in params:
            node['servername'] = params['sni'][0]
        elif 'peer' in params:
            node['servername'] = params['peer'][0]

        # network / type
        if 'type' in params:
            network = params['type'][0]
            if network in ('ws', 'tcp', 'grpc', 'xhttp'):
                node['network'] = network

        # ws-opts
        if 'path' in params:
            path = params['path'][0]
            if 'host' in params:
                node['ws-opts'] = {
                    'path': path,
                    'headers': {'Host': params['host'][0]}
                }
            else:
                node['ws-opts'] = {'path': path}

        # xhttp-opts (for newer protocols)
        if 'mode' in params:
            node['xhttp-opts'] = {
                'path': params.get('path', ['/'])[0],
                'mode': params['mode'][0]
            }

        return node

    return None

# 读取并解析订阅
with open(sys.argv[1], 'r') as f:
    urls = [line.strip() for line in f if line.strip()]

new_proxies = []
for url in urls:
    proxy = parse_proxy(url)
    if proxy:
        new_proxies.append(proxy)

# 读取当前配置
with open(sys.argv[2], 'r') as f:
    config = yaml.safe_load(f)

old_proxies = config.get('proxies', [])
old_names = {p['name'] for p in old_proxies}
new_names = {p['name'] for p in new_proxies}

added = new_names - old_names
removed = old_names - new_names
kept = old_names & new_names

print(f"[MERGE] 旧节点: {len(old_names)}, 新节点: {len(new_names)}")
if added:
    print(f"[MERGE] 新增: {', '.join(sorted(added))}")
if removed:
    print(f"[MERGE] 移除: {', '.join(sorted(removed))}")
if kept:
    print(f"[MERGE] 保留: {len(kept)} 个")

# 只替换 proxies 列表
config['proxies'] = new_proxies

with open(sys.argv[2], 'w') as f:
    yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print("[MERGE] config.yaml 已更新")
PYEOF

# 备份
cp "$CONF" "$DIR/config.yaml.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true

# 重载
RELOAD=$(curl -s -X PUT http://127.0.0.1:9090/configs \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"$CONF\"}" 2>&1) || true
echo "[$(ts)] reload: ${RELOAD:-204}" | tee -a "$LOG"
echo "[$(ts)] OK: updated" | tee -a "$LOG"

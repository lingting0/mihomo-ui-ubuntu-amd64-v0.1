#!/usr/bin/env python3
"""
mihomo 订阅管理 API 服务
监听 127.0.0.1:9091，提供订阅 URL 管理、手动更新触发、日志查看功能
仅监听本地回环地址，不对外暴露
"""
import http.server
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

MIHOMO_DIR = "/etc/mihomo"
URL_FILE = os.path.join(MIHOMO_DIR, "sub_url.txt")
LOG_FILE = os.path.join(MIHOMO_DIR, "mihomo-sub.log")
UPDATE_SCRIPT = os.path.join(MIHOMO_DIR, "update-sub.sh")
CONFIG_FILE = os.path.join(MIHOMO_DIR, "config.yaml")


def read_url():
    """读取当前订阅 URL"""
    if os.path.exists(URL_FILE):
        with open(URL_FILE) as f:
            return f.read().strip()
    return ""


def write_url(url):
    """写入新的订阅 URL"""
    url = url.strip()
    if not url:
        return False, "URL 不能为空"
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "URL 必须以 http:// 或 https:// 开头"
    with open(URL_FILE, "w") as f:
        f.write(url + "\n")
    return True, "订阅 URL 已更新"


def get_status():
    """获取订阅状态"""
    url = read_url()
    last_update = "未知"
    node_count = 0
    log_entries = []

    # 读取日志获取最后更新时间和状态
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                lines = f.readlines()
            # 取最近 50 行
            recent = lines[-50:] if len(lines) > 50 else lines
            log_entries = [line.strip() for line in recent]

            # 查找最后更新时间
            for line in reversed(lines):
                if "START" in line:
                    try:
                        last_update = line.split("===")[0].strip().strip("[]")
                    except Exception:
                        pass
                    break
        except Exception:
            pass

    # 统计节点数
    if os.path.exists(CONFIG_FILE):
        try:
            import yaml
            with open(CONFIG_FILE) as f:
                config = yaml.safe_load(f)
            node_count = len(config.get("proxies", []))
        except Exception:
            try:
                with open(CONFIG_FILE) as f:
                    content = f.read()
                node_count = content.count("\n- name:")
            except Exception:
                pass

    return {
        "url": url,
        "last_update": last_update,
        "node_count": node_count,
        "log_entries": log_entries[-20:],  # 最近 20 条日志
    }


def trigger_update():
    """手动触发订阅更新"""
    if not os.path.exists(UPDATE_SCRIPT):
        return False, f"更新脚本不存在: {UPDATE_SCRIPT}"

    try:
        result = subprocess.run(
            ["bash", UPDATE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=MIHOMO_DIR,
        )
        output = result.stdout + result.stderr
        success = "OK" in output or "updated" in output.lower()
        return success, output[-2000:]  # 返回最后 2000 字符
    except subprocess.TimeoutExpired:
        return False, "更新超时（超过 120 秒）"
    except Exception as e:
        return False, f"更新出错: {str(e)}"


def get_rules():
    """从 config.yaml 读取规则列表"""
    try:
        import yaml
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
        rules = config.get("rules", [])
        result = []
        for i, rule in enumerate(rules):
            if isinstance(rule, str):
                # 格式: "TYPE,payload,proxy" 或 "TYPE,payload,proxy,extra"
                result.append({"index": i, "raw": rule})
            else:
                result.append({"index": i, "raw": str(rule)})
        return result
    except Exception as e:
        return []


def reload_config():
    """通知 mihomo 重新加载配置"""
    try:
        import urllib.request
        body = json.dumps({"path": CONFIG_FILE}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:9090/configs",
            data=body,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[sub-api] reload config error: {e}")
        return False


def add_rule(rule_type, payload, proxy, extra=""):
    """添加一条新规则到 config.yaml"""
    try:
        import yaml
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return False, f"读取配置失败: {e}"

    if "rules" not in config:
        config["rules"] = []

    rule_str = f"{rule_type},{payload},{proxy}"
    if extra:
        rule_str += f",{extra}"

    config["rules"].append(rule_str)

    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        reload_config()
        return True, f"规则已添加: {rule_str[:60]}..."
    except Exception as e:
        return False, f"写入配置失败: {e}"


def delete_rule(index):
    """从 config.yaml 删除指定索引的规则"""
    try:
        import yaml
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return False, f"读取配置失败: {e}"

    rules = config.get("rules", [])
    if index < 0 or index >= len(rules):
        return False, f"规则索引无效: {index} (共 {len(rules)} 条)"

    deleted = rules.pop(index)

    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        reload_config()
        return True, f"规则已删除: {str(deleted)[:60]}"
    except Exception as e:
        return False, f"写入配置失败: {e}"


def update_rule(index, rule_type, payload, proxy, extra=""):
    """更新 config.yaml 中指定索引的规则"""
    try:
        import yaml
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return False, f"读取配置失败: {e}"

    rules = config.get("rules", [])
    if index < 0 or index >= len(rules):
        return False, f"规则索引无效: {index} (共 {len(rules)} 条)"

    old_rule = rules[index]
    rule_str = f"{rule_type},{payload},{proxy}"
    if extra:
        rule_str += f",{extra}"

    rules[index] = rule_str

    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        reload_config()
        return True, f"规则已更新: {str(old_rule)[:40]} → {rule_str[:40]}"
    except Exception as e:
        return False, f"写入配置失败: {e}"


class SubAPIHandler(http.server.BaseHTTPRequestHandler):
    """订阅管理 + 规则管理 API 请求处理器"""

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/status":
            self._send_json(get_status())

        elif path == "/api/log":
            status = get_status()
            self._send_json({"log": status["log_entries"]})

        elif path == "/api/rules":
            rules = get_rules()
            self._send_json({"rules": rules, "total": len(rules)})

        elif path == "/" or path == "":
            self._send_html(SUB_HTML)

        else:
            self._send_json({"error": "Not Found", "path": path}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == "/api/url":
            url = data.get("url", "")
            ok, msg = write_url(url)
            self._send_json({"success": ok, "message": msg}, 200 if ok else 400)

        elif path == "/api/update":
            ok, msg = trigger_update()
            status = get_status()
            self._send_json({
                "success": ok,
                "message": msg,
                "node_count": status["node_count"],
                "last_update": status["last_update"],
            })

        elif path == "/api/rules":
            rule_type = data.get("type", "")
            payload = data.get("payload", "")
            proxy = data.get("proxy", "")
            extra = data.get("extra", "")
            if not rule_type or not payload or not proxy:
                self._send_json({"success": False, "message": "type, payload, proxy 为必填项"}, 400)
                return
            ok, msg = add_rule(rule_type, payload, proxy, extra)
            self._send_json({"success": ok, "message": msg}, 200 if ok else 400)

        elif path.startswith("/api/rules/"):
            # DELETE /api/rules/{index}
            try:
                index = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"success": False, "message": "无效的规则索引"}, 400)
                return
            ok, msg = delete_rule(index)
            self._send_json({"success": ok, "message": msg}, 200 if ok else 400)

        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_DELETE(self):
        """处理 DELETE 请求"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/rules/"):
            try:
                index = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"success": False, "message": "无效的规则索引"}, 400)
                return
            ok, msg = delete_rule(index)
            self._send_json({"success": ok, "message": msg}, 200 if ok else 400)
        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_PUT(self):
        """处理 PUT 请求 — 更新规则"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path.startswith("/api/rules/"):
            try:
                index = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"success": False, "message": "无效的规则索引"}, 400)
                return

            rule_type = data.get("type", "")
            payload = data.get("payload", "")
            proxy = data.get("proxy", "")
            extra = data.get("extra", "")

            if not rule_type or not proxy:
                self._send_json({"success": False, "message": "type 和 proxy 为必填项"}, 400)
                return

            ok, msg = update_rule(index, rule_type, payload, proxy, extra)
            self._send_json({"success": ok, "message": msg}, 200 if ok else 400)
        else:
            self._send_json({"error": "Not Found"}, 404)

    def log_message(self, format, *args):
        """Suppress default logging to stderr"""
        pass


# 订阅管理前端页面（自包含 HTML）
SUB_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>订阅管理 - mihomo</title>
<style>
  :root {
    --bg: #1a1a2e;
    --card: #16213e;
    --accent: #0f3460;
    --text: #e0e0e0;
    --green: #4caf84;
    --red: #e0556a;
    --yellow: #d4a843;
    --blue: #5b9bd5;
    --border: #2a2a4a;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 24px;
  }
  .container { max-width: 720px; margin: 0 auto; }
  h1 {
    font-size: 1.5rem;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  h1 .icon { font-size: 1.8rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .card h2 {
    font-size: 1rem;
    margin-bottom: 16px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .input-group {
    display: flex;
    gap: 8px;
  }
  input[type="url"] {
    flex: 1;
    padding: 10px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="url"]:focus { border-color: var(--blue); }
  button {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
    white-space: nowrap;
  }
  button:hover { opacity: 0.85; transform: translateY(-1px); }
  button:active { transform: translateY(0); }
  button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .btn-primary { background: var(--blue); color: #fff; }
  .btn-success { background: var(--green); color: #fff; }
  .btn-danger { background: var(--red); color: #fff; }
  .status-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
  }
  .status-label { color: #888; font-size: 0.85rem; }
  .status-value { font-weight: 600; font-size: 0.95rem; }
  .log-area {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    max-height: 320px;
    overflow-y: auto;
    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.9rem;
    animation: slideIn 0.3s ease;
    z-index: 1000;
  }
  .toast-success { background: var(--green); color: #fff; }
  .toast-error { background: var(--red); color: #fff; }
  @keyframes slideIn {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }
  .back-link {
    display: inline-block;
    margin-bottom: 20px;
    color: var(--blue);
    text-decoration: none;
    font-size: 0.9rem;
  }
  .back-link:hover { text-decoration: underline; }
  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <a href="./" class="back-link">← 返回面板</a>
  <h1><span class="icon">📡</span> 订阅管理</h1>

  <!-- 订阅 URL 设置 -->
  <div class="card">
    <h2>🔗 订阅地址</h2>
    <div class="input-group">
      <input type="url" id="subUrl" placeholder="输入订阅 URL (https://...)" />
      <button class="btn-primary" onclick="saveUrl()">💾 保存</button>
    </div>
  </div>

  <!-- 状态信息 -->
  <div class="card">
    <h2>📊 状态概览</h2>
    <div class="status-row">
      <span class="status-label">代理节点数</span>
      <span class="status-value" id="nodeCount">--</span>
    </div>
    <div class="status-row">
      <span class="status-label">最后更新时间</span>
      <span class="status-value" id="lastUpdate">--</span>
    </div>
  </div>

  <!-- 操作按钮 -->
  <div class="card">
    <h2>⚡ 操作</h2>
    <div style="display:flex; gap:8px;">
      <button class="btn-success" id="updateBtn" onclick="triggerUpdate()">
        🔄 立即更新订阅
      </button>
      <button class="btn-danger" onclick="location.reload()">
        🔃 刷新状态
      </button>
    </div>
  </div>

  <!-- 更新日志 -->
  <div class="card">
    <h2>📋 更新日志</h2>
    <div class="log-area" id="logArea">加载中...</div>
  </div>
</div>

<script>
const API = 'http://127.0.0.1:9091';

async function loadStatus() {
  try {
    const r = await fetch(API + '/api/status');
    const data = await r.json();
    document.getElementById('subUrl').value = data.url || '';
    document.getElementById('nodeCount').textContent = data.node_count + ' 个';
    document.getElementById('lastUpdate').textContent = data.last_update || '暂无';
    document.getElementById('logArea').textContent =
      (data.log_entries && data.log_entries.length > 0)
        ? data.log_entries.join('\n')
        : '暂无日志';
  } catch (e) {
    document.getElementById('logArea').textContent =
      '⚠️ 无法连接到订阅 API 服务 (127.0.0.1:9091)\n请确认 sub-api.py 服务已启动。';
  }
}

async function saveUrl() {
  const url = document.getElementById('subUrl').value.trim();
  if (!url) { showToast('请输入订阅 URL', 'error'); return; }
  try {
    const r = await fetch(API + '/api/url', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url})
    });
    const data = await r.json();
    showToast(data.message, data.success ? 'success' : 'error');
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function triggerUpdate() {
  const btn = document.getElementById('updateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 更新中...';
  try {
    const r = await fetch(API + '/api/update', {method: 'POST'});
    const data = await r.json();
    showToast(
      data.success
        ? `更新完成！节点数: ${data.node_count}`
        : '更新失败，请查看日志',
      data.success ? 'success' : 'error'
    );
    await loadStatus();
  } catch (e) {
    showToast('更新请求失败: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔄 立即更新订阅';
  }
}

function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

loadStatus();
</script>
</body>
</html>"""


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9091
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"

    server = http.server.HTTPServer((host, port), SubAPIHandler)
    print(f"[sub-api] 订阅管理 API 已启动: http://{host}:{port}/")
    print(f"[sub-api] 配置目录: {MIHOMO_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[sub-api] 已停止")
        server.shutdown()


if __name__ == "__main__":
    main()

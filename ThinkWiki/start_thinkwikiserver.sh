#!/bin/bash
#
# 1. 找到并优雅停止
pkill -INT -f 'serve_outputs.py'
sleep 1
# 兜底
pkill -f 'thinkwiki serve' 2>/dev/null

# 2. 起一个新的（路径与参数跟原来一致）
cd /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
. ./.env                                                   # 嵌入模型配置
nohup setsid python3 scripts/thinkwiki serve \
  --root /home/tangzhiang/.copaw/workspaces/fqd_pro/wiki-fqd2.0 \
  --host 0.0.0.0 --port 8765 --allow-lan --verbose \
  >> /tmp/thinkwiki-serve.log 2>&1 < /dev/null &

# 3. 验
sleep 2
ss -tln | grep ':8765 '
curl -sS -o /dev/null -w "rc=%{http_code}\n" http://127.0.0.1:8765/index.html
tail -20 /tmp/thinkwiki-serve.log

TW=/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
WIKI=/home/tangzhiang/.copaw/workspaces/fqd_pro/wiki-fqd2.0

sudo tee /etc/systemd/system/thinkwiki-serve.service >/dev/null <<EOF
[Unit]
Description=ThinkWiki HTTP serve
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=exec
User=tang_zhiang
Group=tang_zhiang
EnvironmentFile=$TW/.env
WorkingDirectory=$TW
ExecStart=$TW/.venv/bin/python3 $TW/scripts/thinkwiki serve \
  --root $WIKI --host 0.0.0.0 --port 8765 --allow-lan
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now thinkwiki-serve
sudo systemctl status thinkwiki-serve --no-pager
# 访问控制
sudo journalctl -u thinkwiki-serve -f

之后任何时候都直接：

# sudo systemctl restart thinkwiki-serve
sudo systemctl stop thinkwiki-serve
sudo systemctl status thinkwiki-serve
# 访问方式
# ssh -N -L 8765:127.0.0.1:8765 tang_zhiang@192.168.3.50 

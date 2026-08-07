#!/usr/bin/env bash
# install-wol.sh — 在目标机器上一键配置 WOL + 持久化
# 用法:  install-wol.sh <nic>
# 必须在目标机器上以 root 运行

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <nic>" >&2
    echo "       e.g. $0 enp7s0" >&2
    echo "       e.g. $0 eth0" >&2
    exit 2
fi

NIC="$1"

if [[ $EUID -ne 0 ]]; then
    echo "must run as root (use sudo)" >&2
    exit 3
fi

echo "==> 检查 NIC $NIC"
if ! ip link show "$NIC" >/dev/null 2>&1; then
    echo "    NIC $NIC 不存在" >&2
    echo "    可用 NIC:" >&2
    ip -br link show | awk '{print "      " $1}' >&2
    exit 4
fi

echo "==> 1) 立即开 WOL"
/usr/sbin/ethtool -s "$NIC" wol g

echo "==> 2) 验证"
/usr/sbin/ethtool "$NIC" | grep -E "Wake-on|Link detected"

echo "==> 3) 检测系统类型"
SYSTEM_TYPE="unknown"
if [[ -f /etc/network/interfaces ]] && ! systemctl is-active systemd-networkd >/dev/null 2>&1; then
    SYSTEM_TYPE="ifupdown"
elif systemctl is-active NetworkManager >/dev/null 2>&1; then
    SYSTEM_TYPE="networkmanager"
elif systemctl is-active systemd-networkd >/dev/null 2>&1; then
    SYSTEM_TYPE="systemd-networkd"
fi
echo "    system type: $SYSTEM_TYPE"

case "$SYSTEM_TYPE" in
    ifupdown|*)
        echo "==> 4) 持久化（ifupdown post-up + rc.local 兜底）"
        IFACES="/etc/network/interfaces"
        if [[ ! -f "$IFACES" ]]; then
            echo "    $IFACES 不存在，PVE/Debian 通常应该存在" >&2
            echo "    跳过 ifupdown 配置，仅走 rc.local" >&2
        else
            cp "$IFACES" "${IFACES}.bak.$(date +%Y%m%d_%H%M%S)_pre-wol"
            if grep -q "ethtool -s $NIC wol g" "$IFACES"; then
                echo "    $IFACES 已有 ethtool 行，跳过"
            else
                # 在 iface <nic> ... 段下插入 post-up / pre-down
                # 简化处理：直接在文件末尾追加（用户可手动调整到正确段）
                cat >> "$IFACES" <<EOF

# WOL (added by install-wol.sh on $(date +%Y-%m-%d))
iface $NIC inet manual
    post-up /usr/sbin/ethtool -s $NIC wol g
    pre-down /usr/sbin/ethtool -s $NIC wol g
EOF
                echo "    已追加到 $IFACES"
            fi
        fi

        # rc.local 兜底
        if [[ ! -f /etc/rc.local ]]; then
            cat > /etc/rc.local <<'EOF'
#!/bin/bash
exit 0
EOF
            chmod +x /etc/rc.local
        fi
        cp /etc/rc.local "/etc/rc.local.bak.$(date +%Y%m%d_%H%M%S)_pre-wol"
        if ! grep -q "ethtool -s $NIC wol g" /etc/rc.local; then
            sed -i "/^exit 0/i /usr/sbin/ethtool -s $NIC wol g >/dev/null 2>&1 || true" /etc/rc.local
            echo "    已更新 /etc/rc.local"
        fi
        ;;

    networkmanager)
        echo "==> 4) 持久化（NetworkManager dispatcher）"
        cat > /etc/NetworkManager/dispatcher.d/99-wol-$NIC <<EOF
#!/bin/bash
if [ "\\$1" = "$NIC" ] && [ "\\$2" = "up" ]; then
    /usr/sbin/ethtool -s "\\$1" wol g
fi
EOF
        chmod +x /etc/NetworkManager/dispatcher.d/99-wol-$NIC
        echo "    已创建 dispatcher 脚本"
        ;;

    systemd-networkd)
        echo "==> 4) 持久化（systemd-networkd .link）"
        NIC_MAC=$(cat /sys/class/net/$NIC/address)
        cat > /etc/systemd/network/10-$NIC.link <<EOF
[Match]
MACAddress=$NIC_MAC

[Link]
WakeOnLan=magic
EOF
        echo "    ⚠️ 注意：systemd-networkd 在 PVE 上默认不读 link 文件"
        echo "    建议同时配 ifupdown 兜底"
        ;;
esac

echo
echo "==> ✅ 完成"
echo "    NIC: $NIC"
echo "    WOL: 已开 + 已持久化（$SYSTEM_TYPE 模式）"
echo
echo "    验证（重启后跑）:"
echo "      /usr/sbin/ethtool $NIC | grep Wake-on"
echo "    应该是: Wake-on: g"
echo
echo "    ⚠️ 提醒：别忘了 BIOS 里也要开 Wake on LAN / Power on by PCIe"

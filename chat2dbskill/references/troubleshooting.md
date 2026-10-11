# Chat2DB Local 排障手册

> 本机平台：Linux x86_64（RHEL/Rocky 系）
> JDK：OpenJDK 21（`/usr/lib/jvm/java-21-openjdk`）
> GUI rpm：`chat2db-local-5.3.899-1.x86_64`

## 问题一：JVM 找不到

**报错**
```
Failed to find JVM in "/opt/chat2db-local/chat2db-local/lib/app/runtime" directory.
```

**原因**：RPM 未内嵌 JRE，脚本硬编码去 `lib/app/runtime` 找 JVM，系统 Java 21 装在 `/usr/lib/jvm/java-21-openjdk/`。

**排查**
```bash
ls /opt/chat2db-local/chat2db-local/lib/app/runtime/
# 有 jar/dist/lib，但无 bin/java —— 确认 RPM 没带 JRE

java -version
# openjdk version "21.0.12.1"  # 系统 Java 21 是好的
```

**解决**：改启动脚本，把 JVM 路径指向系统 Java。

```bash
cd /opt/chat2db-local/chat2db-local/bin
# 备份
cp "Chat2DB Local" "Chat2DB Local.bak"
# 替换（用 | 作 sed 分隔符，避免路径里 / 冲突）
sudo sed -i 's|$APP_HOME/lib/app/runtime|/usr/lib/jvm/java-21-openjdk|g' "Chat2DB Local"
# 改名（见"问题三"）
mv "Chat2DB Local" chat2db
```

验证：
```bash
grep "java-21-openjdk" chat2db
```

---

## 问题二：Chromium SingletonLock（最常见）

**报错**
```
其他计算机 (openNebula) 的另一个 Chromium 进程 ... 好像正在使用此个人资料
CefApp: N_Initialize failed.
```

**原因**：
1. 上次异常退出残留 `SingletonLock` 锁文件
2. VNC/云桌面环境，Chromium 把主机名 `openNebula` 记作"另一台机器"，拒绝共用 Profile

**锁目录**（不要动错！）：

| 版本 | 锁目录 |
|---|---|
| **Chat2DB Local** | `~/.chat2db_local_edition/chat2db_cache_local/` |
| Chat2DB Community | `~/.chat2db-community/chat2db_cache_community/` |

**⚠️ 不要删这些**（会崩别的程序）：
- `~/.local/share/browseract/` 下的 `Singleton*`
- `~/.copaw/workspaces/*/browser/user_data/` 下的 `Singleton*`

**解决**

```bash
# 1. 杀残留进程
pkill -9 -f Chat2DB || true
pkill -9 -f jcef || true
pkill -9 -f cef_helper || true
sleep 1

# 2. 只清 Chat2DB 的锁
rm -f ~/.chat2db_local_edition/chat2db_cache_local/Singleton*
rm -f ~/.chat2db-community/chat2db_cache_community/Singleton* 2>/dev/null

# 3. 用独立 HOME 启动（推荐，永久解决）
mkdir -p /home/tangzhiang/chat2db-home
HOME=/home/tangzhiang/chat2db-home /opt/chat2db-local/chat2db-local/bin/chat2db
```

**alias 已配置为独立 HOME 启动，无需每次手敲**：
```bash
chat2db-local   # 等价于上面的完整命令
```

---

## 问题三：chat2db.cfg 找不到

**报错**
```
Error opening "/opt/chat2db-local/.../lib/app/chat2db.cfg" file: No such file or directory
```

**原因**：原二进制名 `Chat2DB Local` 含空格，脚本按空格截断拼配置文件名 `chat2db.cfg`，但实际文件叫 `Chat2DB Local.cfg`（含空格）。

**解决（二选一）**

方案 A（推荐）：补一份 cfg
```bash
cd /opt/chat2db-local/chat2db-local/lib/app
cp "Chat2DB Local.cfg" chat2db.cfg
```

方案 B：改名后拼对
```bash
cd /opt/chat2db-local/chat2db-local/bin
mv "Chat2DB Local" chat2db
```

本机已采用方案 B（二进制改为 `chat2db`，对应 alias 也已更新）。

---

## 问题四：debug.log 怎么看

```bash
# 实时跟踪
tail -f /opt/chat2db-local/chat2db-local/bin/debug.log

# 查关键状态
grep -E "instance lock|Singleton|N_Initialize|JCEF|ERROR" /opt/chat2db-local/chat2db-local/bin/debug.log
```

成功标志（grep 应有匹配）：
```
Successfully acquired the instance lock.
JCEF_I: CefApp: set state INITIALIZING
```

失败标志（grep 应无匹配）：
```
SingletonLock
其他计算机
N_Initialize failed
```

---

## 一键验证脚本

```bash
#!/usr/bin/env bash
BIN="/opt/chat2db-local/chat2db-local/bin/chat2db"
LOG="/tmp/chat2db-verify.log"

pkill -9 -f Chat2DB 2>/dev/null || true
pkill -9 -f jcef 2>/dev/null || true
rm -f ~/.chat2db_local_edition/chat2db_cache_local/Singleton* 2>/dev/null

mkdir -p /home/tangzhiang/chat2db-home
HOME=/home/tangzhiang/chat2db-home timeout 30 "$BIN" >"$LOG" 2>&1 || true

echo "=== 判定 ==="
grep -q "Successfully acquired the instance lock" "$LOG" && echo "PASS: 实例锁" || echo "FAIL: 实例锁"
grep -q "N_Initialize failed" "$LOG"              && echo "FAIL: JCEF"       || echo "PASS: JCEF"
grep -qE "SingletonLock|openNebula" "$LOG"        && echo "FAIL: 锁冲突"   || echo "PASS: 锁"
```

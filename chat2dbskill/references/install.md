# Chat2DB Local RPM 安装与启动

> 本机已装：`chat2db-local-5.3.899-1.x86_64`（rpm）
> 安装路径：`/opt/chat2db-local/chat2db-local/`
> 启动二进制：`/opt/chat2db-local/chat2db-local/bin/chat2db`（改名后，原名含空格）
> 依赖：Java 21（`/usr/lib/jvm/java-21-openjdk`）

## 启动方式

```bash
# 独立 HOME 启动（规避 Chromium SingletonLock 问题，VNC/云桌面必用）
alias chat2db-local='mkdir -p /home/tangzhiang/chat2db-home && HOME=/home/tangzhiang/chat2db-home /opt/chat2db-local/chat2db-local/bin/chat2db'

# 或者直接：
chat2db-local
```

**当前已配置的 alias**（来自 `~/.bashrc`）：
```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export PATH=$JAVA_HOME/bin:$PATH
alias chat2db-local="HOME=/home/tangzhiang/chat2db-home /opt/chat2db-local/chat2db-local/bin/chat2db-local"
```

## 启动后验证

成功日志（`debug.log`）：
```
Successfully acquired the instance lock.
Starting Studio Application, args: []
JCEF_I: CefApp: set state INITIALIZING
```

## 关键路径

| 用途 | 路径 |
|---|---|
| RPM 安装根目录 | `/opt/chat2db-local/chat2db-local/` |
| 启动二进制（改名后） | `/opt/chat2db-local/chat2db-local/bin/chat2db` |
| 原始二进制（含空格） | `/opt/chat2db-local/chat2db-local/bin/Chat2DB Local` |
| 应用资源（jar/dist） | `/opt/chat2db-local/chat2db-local/lib/app/` |
| 运行日志 | `/opt/chat2db-local/chat2db-local/bin/debug.log` |
| 系统 Java | `/usr/lib/jvm/java-21-openjdk/bin/java` |
| JCEF 用户数据（Local） | `~/.chat2db_local_edition/chat2db_cache_local/` |
| JCEF 用户数据（Community） | `~/.chat2db-community/chat2db_cache_community/` |
| 独立 HOME（推荐） | `/home/tangzhiang/chat2db-home/` |
| MCP token 存放 | GUI：设置 → CLI Integration |

## 运维命令

```bash
# 查版本
rpm -qa | grep chat2db

# 查装到哪
rpm -ql chat2db-local

# 查 JVM
java -version
readlink -f /usr/bin/java

# 杀残留进程
pkill -9 -f Chat2DB
pkill -9 -f jcef
pkill -9 -f cef_helper

# 清 JCEF 锁（只删 Chat2DB 的，不要动 browseract/copaw 的）
rm -f ~/.chat2db_local_edition/chat2db_cache_local/Singleton*
rm -f ~/.chat2db-community/chat2db_cache_community/Singleton* 2>/dev/null

# 确认锁已清
find ~/.chat2db_local_edition ~/.chat2db-community -maxdepth 3 \
  \( -name SingletonLock -o -name SingletonSocket -o -name SingletonCookie \) 2>/dev/null
# 应无输出
```

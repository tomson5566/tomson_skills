# 已注册的数据源（Registry）

> **这是用户为本 skill维护的数据源清单**。每次提到「用那个 xxx 数据源」「从 xxx搬数据」「搬到 xxx」时，先来这里查。
>
> 每个数据源一个 H2 section。**YAML frontmatter** 是机器可读的元数据（将来脚本扫），正文是人类可读的连接信息和坑。

---

## ⚠️ 安全 /维护约定

|规则 | 说明 |
|------|------|
| **URI 不写明文密码** | 用 `${ENV_VAR}` 占位，让 ingestr 在运行时展开；或写到 `~/.netrc`、Vault |
| **含敏感信息的 source 不要提交到 git** | `data_sources.md` 加 `.gitignore`，或把 secrets放另一份 `data_sources.local.md` |
| **每个源必须有 `status`** | `ok` / `degraded` / `unreachable`，便于排查 |
| **`added_at` 用 ISO8601 日期** |方便时间排序 |

---

##索引（快速跳转）

| ID | 显示名 | 类型 |状态 | 添加日期 |
|----|--------|------|------|---------|
| [`local-mysql`](#local-mysql) | 本地的mysql 数据源 | mysql | 🟡 degraded（TCP 未启用） |2026-06-07 |
| [`tmsj-remote-mysql`](#tmsj-remote-mysql) | tmsj 远程 MySQL（192.168.0.188:3308） | mysql | 🟢 ok | 2026-06-07 |
| [`mssql-133-14`](#mssql-133-14) | 内网 MSSQL（192.168.133.14, sa 账号）| mssql | 🟠 pending_verify | 2026-06-07 |
| [`datahub-registry`](#datahub-registry) | 本机 datahub 数据源清单（v3.1+ 新增）| mysql (registry) | 🟢 ok | 2026-06-08 |

> 🟢 ok = 直接可用 · 🟡 degraded =有限制（注释里写清） · 🔴 unreachable = 当前连不上 · 🟠 pending_verify = 刚登记，未实测验证

---

## local-mysql

---
id: local-mysql
display_name: 本地的mysql 数据源
type: mysql
version:8.4.3
host:127.0.0.1
port:3306
socket: /var/lib/mysql/mysql.sock
uri_template: mysql://root@127.0.0.1:3306/{database}
transport: tcp_unavailable_use_socket
auth: auth_socket
status: degraded
databases:
 - cloud
 - cloud_usage
 - information_schema
 - mysql
 - performance_schema
 - sys
 - tangzhiang
tags: [local, dev, mysql, unix-socket]
added_at:2026-06-07
---

### 连接信息（mysql客户端直连）

```bash
mysql -uroot # 默认走 /var/lib/mysql/mysql.sock 直接通
mysql -uroot --socket=/var/lib/mysql/mysql.sock -e "SHOW DATABASES;"
```

- **进程**：`mysqld` PID6752（用户 `mysql`），从08:05启动至今
- **socket**：`/var/lib/mysql/mysql.sock`（注意：`/var/run/mysqld/` 下只有 `mysqlx.sock`，那是 X Protocol，连不上经典协议）
- **`@@port =0`**：配置禁用了 TCP监听
- **`@@bind_address =0.0.0.0`**：虽然禁了 TCP，但配置层面没限制 host
- **无密码 root**：`root@localhost`走 `auth_socket` plugin，OS 用户名等于 mysql user 即通（当前 OS 用户 `tangzhiang` 也可 `mysql -uroot` 直连，机制略反常，待查）

### ⚠️ ingestr限制

**ingestr 不支持 unix socket**。
看 `pkg/source/mysql/mysql.go::uriToDSN`（行 ~60）：
```go
dsn += fmt.Sprintf("tcp(%s:%s)/%s", host, port, database) //强制 TCP
```
完全没处理 `unix(/path)`情况。

### 三种解锁方式

|方案 | 命令 /改动 | 是否需 sudo |
|------|------------|------------|
| **A（推荐）**：启用 MySQL TCP | `/etc/mysql/mysql.conf.d/mysqld.cnf` → `port =3306`，`systemctl restart mysql` | ✅ 是 |
| **B**：socat端口转发 | `socat TCP-LISTEN:3306,fork UNIX-CONNECT:/var/lib/mysql/mysql.sock` | ❌ 否（但要装 socat） |
| **C**：改 ingestr源码 | 在 `uriToDSN` 加 `unix(...)` 分支，重新编译 | ❌ 否（但维护成本高） |

### 用法示例（启用 TCP 后）

**首次全量（默认策略 replace）**：
```bash
ingestr ingest \
 --source-uri "mysql://root@127.0.0.1:3306/tangzhiang" \
 --source-table "users" \
 --dest-uri "duckdb:///tmp/out.db" \
 --dest-table "users" --yes
```

**增量 merge**：
```bash
ingestr ingest \
 --source-uri "mysql://root@127.0.0.1:3306/tangzhiang" \
 --source-table "users" \
 --dest-uri "duckdb:///tmp/out.db" \
 --dest-table "users" \
 --incremental-strategy merge --primary-key id --incremental-key updated_at \
 --interval-start "2026-01-01T00:00:00Z" --interval-end "2026-02-01T00:00:00Z" \
 --yes
```

###探查清单（添加/复用前先查）

- [] TCP 是否启用（`SELECT @@port`）
- [] 有哪些数据库（`SHOW DATABASES`）
- [] 目标表是否大（`SELECT COUNT(*)` + 表大小）
- [] 有没有时间戳列可做 incremental_key（`SHOW CREATE TABLE`）
- [] 是否需要脱敏列（哪些列含 PII）

###已知坑（已记入 `MEMORY.md`）

- `mysql -h127.0.0.1 -P3306`报 `ERROR2003 (111)` —— 不是没启动，是 TCP禁用
- `--socket=/var/run/mysqld/mysqlx.sock`报 `Protocol mismatch` —— mysqlx 是 X Protocol 不是经典协议
- 当前用户无 `sudo`，要启用 TCP 必须先用 `sudo -i` 或找有 sudo 的 shell

---

## tmsj-remote-mysql

---
id: tmsj-remote-mysql
display_name: tmsj 远程 MySQL（192.168.0.188:3308）
type: mysql
version: "8.4.8-8.1"   # 从握手 banner 探测
host: 192.168.0.188
port: 3308
user: tmsj
uri_template: mysql://tmsj:${TMSJ_MYSQL_PASSWORD}@192.168.0.188:3308/{database}
auth: env_var
auth_env: TMSJ_MYSQL_PASSWORD
status: ok
auth_plugin: caching_sha2_password   # 从握手 banner 探测
tcp_reachable: true
databases: []                        # 待用 mysql 客户端连上后 SHOW DATABASES 补
tags: [remote, lan, mysql, tmsj]
added_at: 2026-06-07
last_verified: 2026-06-07
---

### 连接信息（密码走环境变量，**不落文件明文**）

```bash
# 临时一次性使用
export TMSJ_MYSQL_PASSWORD='你的密码'   # 建议写到 ~/.bashrc 或密钥管理
mysql -h192.168.0.188 -P3308 -utmsj -p"$TMSJ_MYSQL_PASSWORD"
```

### ⚠️ 安全约定

- **密码不入 git**：本条目用 `${TMSJ_MYSQL_PASSWORD}` 占位，不要把真实值贴进本文件
- **设置环境变量**（建议）：
  ```bash
  # 加到 ~/.bashrc（仅当前用户可见，chmod 600）
  echo 'export TMSJ_MYSQL_PASSWORD="<真实值>"' >> ~/.bashrc
  chmod 600 ~/.bashrc
  source ~/.bashrc
  ```
- **mysql 客户端更优解**：用 `~/.my.cnf`（必须 `chmod 600`）
  ```ini
  [clienttmsj]
  host=192.168.0.188
  port=3308
  user=tmsj
  password=<真实值>
  ```
  用法：`mysql --defaults-group-suffix=tmsj`（注意 suffix 拼到 group 后，没有连字符）

### ingestr 用法

```bash
ingestr ingest \
  --source-uri "mysql://tmsj:${TMSJ_MYSQL_PASSWORD}@192.168.0.188:3308/<database>" \
  --source-table "your_table" \
  --dest-uri "duckdb:///tmp/out.db" \
  --dest-table "your_table" \
  --yes
```

### 网络/版本探测记录

- **TCP 探活**（无认证）：`bash -c 'cat < /dev/tcp/192.168.0.188/3308'` 成功，返回 MySQL handshake banner
- **服务端版本**：`8.4.8-8.1`（server 8.4.8，client lib 8.1）
- **auth plugin**：`caching_sha2_password`（MySQL 8 默认，老版 mysql client 可能需要升级或显式 `default-auth=mysql_native_password`）
- **LAN 地址**：`192.168.0.0/24` 网段，假设在用户家/办公内网，不暴露公网

### 探查清单（**待补**）

- [ ] `SHOW DATABASES` —— 有哪些库
- [ ] 每个目标表 `SELECT COUNT(*)` + `SHOW TABLE STATUS` 看大小
- [ ] `SHOW CREATE TABLE <tbl>` —— 主键、字段类型、有没有时间戳列做 `incremental_key`
- [ ] 哪些列含 PII 需要脱敏
- [ ] 用户/库的权限范围（`SHOW GRANTS FOR tmsj`）

### 已知坑 / 注意

- 密码含 `@` 字符，shell 直接 `mysql -pTmsj@8888` **会报错** —— shell 解析 `@8888` 当主机段；必须 `-p"$TMSJ_MYSQL_PASSWORD"` 或交互式输入
- ingestr 也可能踩到 `@` 解析，URI 里出现 `@`/`/`/`?`/`#` 需要 percent-encode（`%40` / `%2F` 等），保险起见密码走 env 变量
- 远程库 8.4 用 `caching_sha2_password`，本地 `mysql` 客户端若是 5.x/老 8.0 可能连不上 —— `mysql --version` 确认
- LAN 地址可能 DHCP 后变 IP，先 `ping` 或加到本地 hosts 注释里

---

## mssql-133-14

---
id: mssql-133-14
display_name: 内网 MSSQL（192.168.133.14, sa 账号）
type: mssql
version: "未探测"        # 待 sqlcmd / mssql-cli 握手后回填
host: 192.168.133.14
port: 1433               # SQL Server 默认端口，未验证可达
user: sa
uri_template: mssql://sa:${MSSQL_SA_PASSWORD}@192.168.133.14:1433/{database}
auth: env_var
auth_env: MSSQL_SA_PASSWORD
status: pending_verify
tcp_reachable: 未验证     # 受 sandbox 限制未做 TCP 探活，需用户在 shell 自验
databases: []            # 待连上后 SELECT name FROM sys.databases 补
tags: [remote, lan, mssql, sqlserver, sa]
added_at: 2026-06-07
---

### 连接信息（密码走环境变量，**绝不写明文到本文件**）

```bash
# 一次性导出（密码含下划线无特殊字符，shell 直接展开即可）
export MSSQL_SA_PASSWORD='你的密码'

# 用 sqlcmd / mssql-cli 验证
sqlcmd -S 192.168.133.14,1433 -U sa -P "$MSSQL_SA_PASSWORD" -Q "SELECT @@VERSION"
# 或
mssql-cli -S 192.168.133.14 -U sa -P "$MSSQL_SA_PASSWORD" -q "SELECT name FROM sys.databases"
```

> ⚠️ **本条目不是把密码存进 skill 目录**，只是把"这个数据源存在、连接模板长这样"登记下来。密码得你自己落到安全的地方。

### 🚨 安全警告（sa 账号 + 内网 192.168 段，三条都看）

1. **`sa` 是 sysadmin，权限等同 root** —— 能 `SHUTDOWN`、能改任何库、能看到所有数据。
   - 长期跑 ETL 建议建一个**专用低权限账号**（只 `SELECT` 需要的库），完成后把 `sa` 条目降级或删掉。
   - 临时跑可以接受，但别让任何脚本/管道把 `${MSSQL_SA_PASSWORD}` 打到日志里。

2. **`192.168.133.14` 是 RFC1918 私网地址** —— 不出 NAT 没问题，但请确认：
   - 你的本机在**同一个 LAN**（不是 VPN、不是公网走跳板）
   - 目标机器的防火墙（Windows 防火墙 / 第三方）**对 1433 端口放行**
   - 路由器/交换机 ACL 没有拦截

3. **明文密码如何落地**（按敏感度从高到低，三选一）：

   | 方案 | 命令 | 安全度 | 适用 |
   |------|------|--------|------|
   | **A（最推荐）** | 写到 `~/.bashrc`，`chmod 600 ~/.bashrc` | 🟢 高 | 个人开发机，临时用 |
   | **B** | 写到 `~/.mssqlcli/credentials` 或 `~/.sqlcmd/config` 类的工具配置文件，`chmod 600` | 🟢 高 | 长期用，多工具共享 |
   | **C** | 系统 keyring / HashiCorp Vault / 1Password CLI | 🟢🟢 最高 | 多人协作、生产环境 |
   | ❌ 明文到 `data_sources.md` | — | 🔴 危险 | **禁止**（违反本 skill 约定，且 `data_sources.md` 可能在 git 里）|

   一行命令把密码落到 `~/.bashrc`（**记得把 `<真实值>` 替换成真密码**）：
   ```bash
   echo 'export MSSQL_SA_PASSWORD="<真实值>"' >> ~/.bashrc
   chmod 600 ~/.bashrc
   source ~/.bashrc
   ```

### ingestr 用法

```bash
ingestr ingest \
  --source-uri "mssql://sa:${MSSQL_SA_PASSWORD}@192.168.133.14:1433/<database>" \
  --source-table "your_table" \
  --dest-uri "duckdb:///tmp/out.db" \
  --dest-table "your_table" \
  --yes
```

增量示例（merge + `updated_at`）：
```bash
ingestr ingest \
  --source-uri "mssql://sa:${MSSQL_SA_PASSWORD}@192.168.133.14:1433/<database>" \
  --source-table "orders" \
  --dest-uri "duckdb:///tmp/out.db" \
  --dest-table "orders" \
  --incremental-strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "2026-01-01T00:00:00Z" --interval-end "2026-02-01T00:00:00Z" \
  --yes
```

### 探查清单（**待补**）

- [ ] **TCP 1433 可达**：`bash -c 'cat < /dev/tcp/192.168.133.14/1433'` 应返回 SQL Server handshake banner
- [ ] **服务版本**：`SELECT @@VERSION` —— 决定要不要走 `TrustServerCertificate=true`（自签证书 2017+ 默认开）
- [ ] **数据库清单**：`SELECT name FROM sys.databases` —— 填到 `databases:` 字段
- [ ] **sa 登录方式**：`SELECT SERVERPROPERTY('IsIntegratedSecurityOnly')` —— 0=混合认证（可密码登录），1=只 Windows 认证（密码登不上）
- [ ] **目标表大小**：`sp_spaceused '<tbl>'` 或 `SELECT ... FROM sys.dm_db_partition_stats`
- [ ] **主键 / 增量列**：`SELECT ... FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='...'`
- [ ] **哪些列含 PII 需要 `--mask`**

### 已知坑 / 注意

- **密码含特殊字符需 percent-encode**：MSSQL 密码如果含 `@` / `:` / `/` / `?` / `#`，URI 里要转义成 `%40` / `%3A` / `%2F` / `%3F` / `%23`。本条目的密码由用户在环境变量 `MSSQL_SA_PASSWORD` 里维护，**本文件不存明文**；用前先在 shell 检查 `echo "${MSSQL_SA_PASSWORD}" | grep -E '[@:/?.#]'` 决定要不要 percent-encode。
- **TLS 默认行为**：SQL Server 2016+ 自签证书，`ingestr` 走 `mssql` source 时若证书校验失败需要在 URI 加 `?encrypt=true&TrustServerCertificate=true`（看具体 driver 实现）。先用明文 `encrypt=false` 跑通，再按需升级到 TLS。
- **Windows 防火墙**：默认 MSSQL 装完**不**对 1433 放行，要去「高级安全 Windows 防火墙」入站规则里开（或 `netsh advfirewall firewall add rule ...`）。
- **命名实例**：如果目标不是默认实例，端口会是动态的（SQL Browser 在 1434），URI 要写成 `192.168.133.14\instance_name,port` 形式。先 `SELECT @@SERVICENAME` 确认。
- **数据库名带空格/中文**：URI 里 percent-encode，否则 `?` `#` 等会被解析成 query 段。
- **sa 密码复杂度策略**：SQL Server 安装时强制过复杂度（大小写+数字+符号）。本条目密码由用户设置到 `MSSQL_SA_PASSWORD`，**不存明文到本文件**；如果连不上时怀疑是密码被策略拒绝，去目标机 `SELECT LOGINPROPERTY('sa', 'PasswordLastSetTime')` 看上次改密时间，并用 `ALTER LOGIN sa WITH PASSWORD = '...'` 重设。
- **跨网段 / VPN**：192.168.133.x 段和你本机是不是同段？不在同段需要路由（VPN、wireguard、ssh tunnel 等）。本 skill 假设是同 LAN。
- **本机没装 sqlcmd/mssql-cli**：ingestr 内部会自带 `mssql-go` 之类的 driver，不需要 sqlcmd；sqlcmd 只为手动验证。Debian/Ubuntu 装：`apt install mssql-tools`（微软源）或 `pip install mssql-cli`。
- **状态从 `pending_verify` 升级**：连通后改成 `ok`；不通就 `unreachable` 并在「已知坑」补原因。
## datahub-registry

---
id: datahub-registry
display_name: 本机 datahub 数据源清单（v3.1+ 新增）
type: mysql
subtype: registry
version: 8.4.3
host: 127.0.0.1
port: 3306                # 实际禁用 TCP，走 socket
socket: /var/lib/mysql/mysql.sock
uri_template: registry://datahub.db_source
transport: unix_socket_only
auth: auth_socket
status: ok
added_at: 2026-06-08
owner: dataops
tags: [local, registry, datahub, datasource-management]
---

### 用途

本机 MySQL `datahub` 库的 `db_source` 表 = **数据源清单的 source of truth**。
所有 ingestr ETL 任务在拼 URI 前，应该从这张表读连接信息。

### 连接方式

```bash
# Unix socket（默认，因为本机 MySQL 禁 TCP）
mysql -uroot --socket=/var/lib/mysql/mysql.sock datahub \
  -e "SELECT source_code, db_type, host, port, username, status FROM db_source;"
```

### 管理 CLI（v3.1+）

```bash
# 装好后，PATH 里直接能调用 datasource
datasource list                            # 全部源
datasource show MSSQL_HR_133_14            # 看详情（密码隐藏）
datasource show MSSQL_HR_133_14 --show-password  # 显示明文
datasource add --code X --name ...         # 新增
datasource update X --password newpwd      # 改密/状态
datasource delete X                        # 软删除
datasource delete X --force                # 硬删除
datasource search hr                       # 搜索
datasource count --type sqlserver          # 统计
datasource status X active                 # 改 status
```

### 已知坑 / 注意

- **密码明文保存**：用户授权。当前是本地开发 + 内部 LAN，明文风险可控。生产建议转 Vault / keyring。
- **本机 MySQL 8.4.3 走 socket**：datasource 工具默认走 `/var/lib/mysql/mysql.sock`（pymysql 支持 `unix_socket` 参数）。
- **ingestr 不支持 socket**：datasource CLI 走 socket，但 ingestr 的 MySQL driver（`pkg/source/mysql/mysql.go::uriToDSN`）强制 TCP，跨工具时仍要启用 MySQL TCP 或 `socat` 转发。
- **CLI 命名空间**：datasource 的 `--db-host/--db-port/--db-user/--db-socket` 是连本机 datahub 用的；`add --host/--port/--user` 是业务字段。命名分开，避免歧义。
- **排错 / 实战经验**：见 `troubleshooting.md` → "datasource CLI 排错" 章节（`add` 静默输出排查、shell `---` 误解析、密码从 .env 传参模板）。

---
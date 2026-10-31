# 数据模型：config/servers.json

整个 skill 的唯一数据源。所有脚本读写此文件；agent 也可直接 `jq` 查询。
手工修改后务必 `jq . config/servers.json > /dev/null` 校验。

## 顶层结构

```json
{
  "schema_version": 2,
  "updated_at": "全局最后更新时间",
  "settings": {
    "report_keep_days": 30
  },
  "servers": [ "<服务器档案>" ]
}
```

服务器档案唯一键 = `host + port + auth.username`（同一台机器可登记多个账号）。

### settings 全局设置

| 字段 | 类型 | 说明 |
|---|---|---|
| `settings.report_keep_days` | number | 巡检报告保留天数，默认 30。`server-check.sh` / `daily-disk-check.sh` 运行后自动删除超过保留期的 `reports/*.log`；手动清理用 `scripts/report-clean.sh [--days N] [--dry-run]`；单次执行可用环境变量 `RSC_REPORT_KEEP_DAYS` 临时覆盖 |

## 密钥池登记：keys/index.json

集中登记密钥池中每个密钥的来源与用途，由 `key-manage.sh generate/import/import-all` 自动维护：

```json
{
  "schema_version": 1,
  "keys": [
    {
      "name": "agentA_id_ed25519",
      "type": "(ED25519)",
      "fingerprint": "SHA256:xxxx",
      "source_device": "agentA主机",
      "comment": "import-all from /root/.ssh",
      "created_at": "..."
    }
  ]
}
```

- `source_device`：密钥来源设备名，多设备统一管理的核心字段，import-all 时强制要求
- 无 ssh-keygen 的环境 fingerprint 退化为文件 sha256 摘要
- 服务器侧绑定关系存在各档案的 `auth.key_names`，此处不重复存

## 服务器档案字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `host` | string | IP 或域名 |
| `port` | number | SSH 端口 |
| `category` | string | 分类，自由命名：生产/测试/数据库/NAS/云服务器… |
| `tags` | string[] | 标签，如 `["内网","rhel","postgresql"]` |
| `auth.type` | string | `key`（免密）或 `password`（密码） |
| `auth.username` | string | SSH 登录用户 |
| `auth.key_name` | string | type=key 时的默认私钥（引用 `keys/<key_name>`，向后兼容字段） |
| `auth.key_names` | string[] | type=key 时的**可登录密钥列表**（多设备多密钥绑定）；连接时与 key_name 合并去重后按序自动尝试 |
| `auth.password` | string | type=password 时的 SSH 登录密码（明文，按用户要求保存） |
| `auth.root_password` | string | 可选，`su - root` 提权密码 |
| `auth.become_root` | bool | 巡检时是否自动 su - root |
| `watch_services` | array | 巡检重点关注服务（见下） |
| `inspection` | object | 巡检档案（见下） |
| `created_at` / `updated_at` | string | ISO8601 时间戳，脚本自动维护 |

## watch_services 元素

```json
{
  "name": "openclaw",
  "match": "openclaw gateway",
  "start_cmd": "setsid nohup env NO_SYSTEMD_USER=1 openclaw gateway > /var/log/openclaw.log 2>&1 & disown",
  "auto_restart": false
}
```

- `match`：用 `ps aux | grep -F <match>` 判断存活，要足够精确
- `auto_restart: true` 且配有 `start_cmd` 时，巡检发现宕机会自动拉起

## inspection 巡检档案

| 字段 | 类型 | 维护方式 |
|------|------|----------|
| `last_check` | string | server-check.sh 自动回写 |
| `hostname` / `os` / `kernel` | string | server-check.sh 自动回写 |
| `listening_ports` | `[{proto,port,process}]` | server-check.sh 自动回写 |
| `services` | array | server-update.sh service 迭代回写 |
| `databases` | array | server-update.sh database / cred 迭代回写 |
| `middleware` | array | server-update.sh middleware / cred 迭代回写 |
| `dev_ports` | `[{port,service,notes,updated_at}]` | server-update.sh devport 迭代回写 |
| `accounts` | array | server-update.sh cred os 迭代回写 |
| `notes` | `[{time,text}]` | server-update.sh note 追加 |

### services 元素

```json
{
  "name": "postgresql-15",
  "path": "/usr/pgsql-15",
  "config": "/data/pg15_data/postgresql.conf",
  "port": 5433,
  "start_cmd": "sudo -u postgres /usr/pgsql-15/bin/pg_ctl -D /data/pg15_data start",
  "status": "running",
  "notes": "",
  "updated_at": "..."
}
```

### databases / middleware 元素

```json
{
  "name": "mysql-main",
  "type": "mysql",
  "version": "8.0",
  "port": 3306,
  "data_dir": "/var/lib/mysql",
  "config": "/etc/my.cnf",
  "credentials": [
    {"username": "root", "password": "S3cret!", "notes": "用途说明", "updated_at": "..."}
  ],
  "notes": "",
  "updated_at": "..."
}
```

- `credentials` 数组按 `username` upsert：改密码 = 重跑 cred 命令，时间戳刷新
- `accounts` 元素同 credentials 结构，另可加 `purpose` 字段

## 查询示例（agent 直接用 jq）

```bash
# 所有密码认证的服务器
jq '.servers[] | select(.auth.type=="password") | {host, user: .auth.username}' config/servers.json

# 某台机器的所有凭证
jq '.servers[] | select(.host=="10.0.0.5") | .inspection.databases[].credentials' config/servers.json

# 超过 30 天未巡检的机器（结合 last_check 字符串比较）
jq -r '.servers[] | select(.inspection.last_check < "2026-09-25") | .host' config/servers.json
```

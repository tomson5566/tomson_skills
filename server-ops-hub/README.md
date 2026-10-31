# server-ops-hub

> 面向 AI Agent 与运维人员的 Linux 服务器「资产档案库 + 密钥管理中枢」——一个自包含、可整体迁移的 Skill。

![Language](https://img.shields.io/badge/language-Bash-4EAA25?logo=gnubash&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey?logo=linux)
![Dependencies](https://img.shields.io/badge/deps-jq%20%7C%20openssh%20%7C%20sshpass-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

![cover](public/wechat-key-cover.jpg)

## 这是什么

每个运维/开发都有这些烦恼：

- 服务器密码记在聊天记录、便签、脑子里，找一次密码像考古
- SSH 密钥散落在每台设备的 `~/.ssh`，换电脑、换 Agent 主机就得重来一遍 `ssh-copy-id`
- `authorized_keys` 里躺着一堆「匿名公钥」，没人知道哪条属于谁，没人敢删
- 这台服务器跑了哪些服务、配置文件在哪、数据库密码多少——全靠记忆
- 换一台 AI Agent 主机，之前积累的服务器知识全部归零

**server-ops-hub 把这些全部收进一个自包含的目录**：服务器档案、免密密钥、登录密码、巡检记录、服务/数据库/中间件配置——数据与工具同目录，打包即迁移，换机器、换 Agent 后原样复活。

它既可以直接 `git clone` 当命令行工具用，也可以作为 Skill 导入 AI Agent（OpenClaw、Coze 等），让 Agent 自动巡检并把结果回写档案。

## 核心特性

- **密钥池**：多台设备的 SSH 私钥统一托管，每把密钥登记来源设备/指纹/备注（台账）
- **一机多钥**：服务器绑定密钥列表，连接时按序自动尝试，任何设备都能登录
- **密码 ↔ 免密双模式**：密码登录的服务器存用户名+密码；一条命令推公钥后自动切换免密
- **结构化档案**：分类、标签、服务（路径/配置/端口/启动命令）、数据库、中间件、开发端口、账号凭证
- **可迭代回写**：凭证按用户名 upsert，自动打时间戳，改密码重跑一条命令即可
- **巡检闭环**：安全巡检 → 报告落盘 → 关键信息自动回写档案，下次巡检/换 Agent 都有据可查
- **整体迁移**：整个目录就是迁移单元，导出/导入自动校验完整性、修复密钥权限
- **Agent 友好**：SKILL.md 内置标准工作流，新 Agent 读档即上手
- **零硬编码**：全部路径动态解析，目录放哪都能跑

## 目录结构

```
server-ops-hub/
├── SKILL.md                    # AI Agent 使用指南（触发场景 + 标准工作流）
├── config/
│   ├── servers.json            # 服务器档案库（唯一数据源，gitignore 保护）
│   └── servers.example.json    # 脱敏示例（上手参考，复制为 servers.json 使用）
├── keys/                       # 密钥池（700 权限）
│   ├── index.json              # 密钥台账（来源设备/指纹/备注）
│   └── README.md               # 密钥管理说明
├── scripts/
│   ├── lib-common.sh           # 公共库：路径解析/档案读写/SSH 执行器
│   ├── server-add.sh           # 添加/更新服务器（分类、认证方式）
│   ├── server-list.sh          # 服务器总览（支持分类过滤/JSON 输出）
│   ├── server-show.sh          # 查看单台完整档案
│   ├── server-remove.sh        # 删除服务器（需 --yes 确认）
│   ├── key-manage.sh           # 密钥池管理（导入/绑定/部署/台账）
│   ├── ssh-run.sh              # 在任意服务器执行命令（自动选认证）
│   ├── server-check.sh         # 安全巡检 + 结果回写
│   ├── server-update.sh        # 档案迭代回写（服务/库/中间件/凭证/端口）
│   ├── daily-disk-check.sh     # 批量磁盘/内存/负载巡检
│   ├── report-clean.sh         # 过期巡检报告清理（默认保留30天）
│   └── export-import.sh        # 整体导出/导入（迁移/备份/分发）
├── references/                 # 数据模型、迁移指南、排障知识库
├── assets/                     # 巡检报告模板
└── reports/                    # 巡检报告输出（迁移时可排除）
```

## 环境要求

| 依赖 | 必需性 | 用途 |
| --- | --- | --- |
| `bash` ≥ 4 | 必需 | 脚本运行环境 |
| `jq` | 必需 | 档案库 JSON 读写 |
| `openssh-client`（ssh/scp/ssh-keygen） | 必需 | 远程连接与密钥操作 |
| `sshpass` | 密码认证时必需 | 非交互密码登录（`apt/yum install sshpass`） |
| `tar` | 迁移时必需 | 导出/导入打包 |

所有依赖缺失时脚本会给出明确的安装提示，不会报天书。

## 安装

### 方式一：git clone 直接使用

```bash
git clone <你的仓库地址>.git
cd server-ops-hub
chmod 700 keys && chmod +x scripts/*.sh
scripts/server-list.sh        # 查看自带示例档案
```

### 方式二：作为 Skill 导入 AI Agent

将 `server-ops-hub.skill`（zip 格式）导入支持 Skill 的 Agent 平台（OpenClaw、Coze 等）。Agent 会按 `SKILL.md` 的指引自动使用全部能力。

## 快速开始

五分钟完成「接入一台新服务器 → 免密 → 巡检 → 回写」全流程：

```bash
cd server-ops-hub

# 1. 收编本机密钥（自动登记来源设备）
scripts/key-manage.sh import-all ~/.ssh --device 我的笔记本

# 2. 接入一台服务器（初始用密码）
scripts/server-add.sh --host 192.168.1.10 --user root \
  --password '初始密码' --category 生产 --tags 内网,web

# 3. 推公钥，切换为免密（之后不再需要密码）
scripts/key-manage.sh deploy 192.168.1.10

# 4. 验证连通性
scripts/ssh-run.sh 192.168.1.10 "hostname && df -h /"

# 5. 安全巡检（报告写入 reports/，自动回写系统信息/端口）
scripts/server-check.sh 192.168.1.10

# 6. 把解读结果迭代写入档案（AI Agent 巡检后自动做这步）
scripts/server-update.sh service 192.168.1.10 --name nginx \
  --path /usr/sbin/nginx --config /etc/nginx/nginx.conf --port 80 --status running
scripts/server-update.sh cred 192.168.1.10 os ops 'Ops@2024' --purpose "运维账号"

# 7. 换机器/备份：整体导出
scripts/export-import.sh export --out my-hub.tar.gz
```

## 命令参考

### 服务器档案

| 命令 | 说明 |
| --- | --- |
| `server-add.sh --host H --user U (--key K \| --password P) [--port 22] [--category C] [--tags a,b] [--root-password P] [--note T]` | 添加/更新服务器（按 host+port+user upsert） |
| `server-list.sh [--category C] [--json]` | 总览：IP/端口/账号/认证/分类/最近巡检 |
| `server-show.sh <host> [--user U]` | 查看单台完整档案（JSON） |
| `server-remove.sh <host> [--user U] --yes` | 删除（必须显式 `--yes`） |

### 密钥池（核心）

| 命令 | 说明 |
| --- | --- |
| `key-manage.sh list` | 密钥池总览：指纹/来源设备/绑定的服务器 |
| `key-manage.sh import-all <目录> --device D` | 批量收编某设备全部私钥（跳过 .pub/known_hosts） |
| `key-manage.sh import <name> <文件> [--device D]` | 导入单个私钥 |
| `key-manage.sh generate <name> [--type ed25519\|rsa]` | 生成新密钥对 |
| `key-manage.sh pub <name>` | 打印公钥 |
| `key-manage.sh bind <host> --key NAME` | 把密钥绑定到服务器（可绑多个，连接时按序尝试） |
| `key-manage.sh unbind <host> --key NAME` | 解绑 |
| `key-manage.sh deploy <host> [--key NAME]` | 推单个公钥到服务器并切换免密 |
| `key-manage.sh deploy-all <host>` | 把密钥池全部公钥推到服务器（新服务器一键全设备免密） |

### 巡检与回写

| 命令 | 说明 |
| --- | --- |
| `server-check.sh <host> [--user U] [--timeout N] [--no-update]` | 安全巡检：系统信息/登录用户/端口/可疑进程/authorized_keys 审计/关注服务状态，报告落盘并自动回写基础信息 |
| `server-update.sh service <host> --name N [--path --config --port --start-cmd --status]` | 回写服务（upsert） |
| `server-update.sh database <host> --name N [--type --version --port --data-dir]` | 回写数据库 |
| `server-update.sh middleware <host> --name N [--port --config]` | 回写中间件 |
| `server-update.sh cred <host> (os\|service\|database\|middleware) [目标名] <账号> <密码> [--purpose T]` | 记录/更新凭证，自动打时间戳，可无限迭代 |
| `server-update.sh devport <host> --port N [--service S]` | 记录开发端口 |
| `server-update.sh note <host> <文本>` / `category <host> <分类>` / `watch <host> --name N --match M [--start-cmd C] [--auto-restart]` | 备注 / 分类 / 关注服务（掉线可自动拉起） |
| `ssh-run.sh <host> [--user U] [--root] <命令>` | 在任意服务器执行命令（`--root` 用 root 密码 su 提权） |
| `daily-disk-check.sh [--threshold 80] [--category 生产]` | 批量磁盘/内存/负载巡检，超阈值告警，适合 crontab |
| `report-clean.sh [--days N] [--dry-run]` | 清理过期巡检报告（默认保留 30 天，巡检脚本每次运行后也会自动清理） |
| `export-import.sh export [--out FILE] [--with-reports]` / `import <FILE> [--dest DIR]` | 整体迁移：打包/解包，自动校验 + 修复权限 |

## 密钥池：设计决策

![key pool](public/wechat-key-pool.jpg)

多设备免密统一管理的核心思路是**密钥跟着档案库走，而不是跟着某台设备走**：

1. **池化收编**：所有设备的私钥导入 `keys/`，命名 `设备名_原文件名`，同名不冲突
2. **台账登记**：`keys/index.json` 记录每把密钥的来源设备、指纹、时间——看到钥匙就知道主人
3. **一机多钥**：服务器档案 `auth.key_names` 是可登录密钥列表，连接时自动逐把尝试（缺失文件自动跳过，全部失败时报错列出已试清单）
4. **整体迁移**：密钥 + 台账 + 档案同目录，`export` 一个压缩包就是「全设备通用钥匙串」

典型收益：

- 新设备/新 Agent 主机上线：`import` 解包，**解开即登录**，零 ssh-copy-id
- 新服务器上线：`deploy-all` 一键推全池公钥，**天生全设备免密**
- 淘汰旧设备：查台账 → `unbind` 精准吊销，**敢删钥匙了**

## 数据模型

档案库 `config/servers.json` 示例（节选）：

```json
{
  "schema_version": 2,
  "servers": [
    {
      "host": "192.168.1.10",
      "port": 22,
      "category": "数据库",
      "tags": ["内网"],
      "auth": {
        "type": "key",
        "username": "root",
        "key_name": "default",
        "key_names": ["笔记本_id_ed25519", "云主机_id_ed25519"],
        "password": "",
        "root_password": "",
        "become_root": false
      },
      "watch_services": [
        {"name": "openclaw", "match": "openclaw gateway", "start_cmd": "...", "auto_restart": true}
      ],
      "inspection": {
        "last_check": "2026-10-25T21:10:00+08:00",
        "hostname": "db-node-1",
        "os": "Rocky Linux 9",
        "services": [{"name": "postgresql-15", "path": "/usr/pgsql-15", "config": "/data/pg15_data/postgresql.conf", "port": 5433, "status": "running"}],
        "databases": [{"name": "pg15", "type": "postgresql", "port": 5433, "credentials": [{"username": "postgres", "password": "***", "updated_at": "..."}]}],
        "middleware": [],
        "dev_ports": [{"port": 3000, "service": "前端dev"}],
        "accounts": [],
        "notes": [{"time": "...", "text": "rhel-root 曾 99% 满，已扩容"}]
      }
    }
  ]
}
```

完整字段定义见 [references/data-schema.md](server-ops-hub/references/data-schema.md)。

## 迁移与同步

整个 Skill 目录就是可迁移单元，三种同步方式任选：

| 方式 | 命令/操作 | 适用 |
| --- | --- | --- |
| 压缩包 | `export-import.sh export --out hub.tar.gz` → 拷贝 → `import hub.tar.gz` | 换机、备份、分发（推荐） |
| 私有 Git | 把整个目录纳入**私有**仓库管理 | 持续同步、版本历史 |
| 加密网盘 | 同步目录 | 个人多设备 |

导入时自动：校验 MANIFEST 完整性 → 修复权限（keys/ 700、私钥 600、脚本 +x）→ 输出可用性提示。

边界说明：本模型是「单主写入友好」，适合个人或小团队串行维护，不适合多人并发改档案。

## 安全说明

- 密钥池内含**私钥与明文密码**——这是工具的定位，也是风险点，请像对待密码本一样对待它
- 权限基线：`keys/` 700、私钥 600（脚本每次执行自动修复）；请勿把本目录提交到公开仓库
- 导出包与私钥等价：传输用加密通道，存储用加密盘
- 设备丢失：查台账 `key-manage.sh list` → `unbind` + 清理目标机 `authorized_keys`，精准吊销即可
- 自动化场景建议密钥不设 passphrase（非交互无法输口令）；人机混用可配合 ssh-agent

## 从旧版 remote-server-check 迁移

旧版 servers.conf 数据可一键迁入 `config/servers.json`。原始密钥在旧主机 `~/.ssh` 中，三选一收编：

```bash
# ① 在旧主机上批量导入后同步（推荐）
scripts/key-manage.sh import-all ~/.ssh --device 旧主机名
# ② 生成新密钥对并重新部署
scripts/key-manage.sh generate hub && scripts/key-manage.sh deploy-all <IP>
# ③ 逐台部署
scripts/key-manage.sh deploy <IP>
```

详见 [references/migration-guide.md](server-ops-hub/references/migration-guide.md)。

## FAQ

**Q：密码认证提示缺 sshpass？**
A：`apt install sshpass`（Debian/Ubuntu）或 `yum install sshpass`（RHEL/CentOS）。建议尽快 `deploy` 切免密。

**Q：带 passphrase 的私钥能用吗？**
A：脚本用 BatchMode 非交互连接，无法输口令。自动化场景建议无口令密钥 + 严格权限保管，或使用 ssh-agent。

**Q：同 IP 多账号（root/oracle）？**
A：档案按 host+port+user 三元组唯一标识，多账号命令加 `--user` 区分。

**Q：Windows 能用吗？**
A：脚本为 Bash 编写，Windows 请使用 WSL。

**Q：巡检会改服务器上的东西吗？**
A：巡检只读（收集信息），唯一例外是 `watch_services` 配置 `auto_restart` 后掉线会自动拉起——默认关闭。

## 文档索引

- [SKILL.md](server-ops-hub/SKILL.md) — AI Agent 触发场景与标准工作流
- [references/data-schema.md](server-ops-hub/references/data-schema.md) — servers.json / index.json 完整字段定义
- [references/migration-guide.md](server-ops-hub/references/migration-guide.md) — 迁移指南（含多设备密钥归集）
- [references/zfs-usb-disk-troubleshooting.md](server-ops-hub/references/zfs-usb-disk-troubleshooting.md) — 磁盘排障知识库
- [references/vastbase-g100-install-notes.md](server-ops-hub/references/vastbase-g100-install-notes.md) — Vastbase G100 安装踩坑记录

## License

MIT

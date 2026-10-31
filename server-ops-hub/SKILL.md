---
name: server-ops-hub
description: Linux 服务器资产档案与安全巡检。当用户说"登录/检查/巡检 XXX 服务器"、"记录 XXX 服务器的数据库密码"、"这台服务器跑了哪些服务"、"加一台服务器"、"把服务器信息迁移到新机器"、"统一管理多台设备的免密登录"时触发。具备密钥池管理（多台设备的公钥/私钥集中托管、按来源设备登记、一机多密钥绑定）、免密与密码双认证、服务器分类、巡检信息（服务/路径/配置/数据库/中间件/账号密码/开发端口）迭代回写、整体打包迁移能力。
---

# 远程服务器资产档案与安全巡检

## 核心设计（先理解再使用）

- **servers.json 是唯一数据源**：`config/servers.json` 保存所有服务器的连接方式、分类、凭证、巡检档案。agent 的任何"记住这台服务器 XX 信息"都通过脚本回写到它。
- **密钥池集中托管（多设备统一）**：SSH 密钥对存于 `keys/`（目录 700、私钥 600），每台设备导入的密钥在 `keys/index.json` 登记来源设备/指纹/备注。服务器档案的 `auth.key_names` 是**可登录密钥列表**（多台设备各自的密钥可绑同一台服务器），连接时按序自动尝试。**不使用 agent 主机 `~/.ssh` 下的私钥**——那是不可迁移的。
- **整个目录即可迁移单元**：档案 + 密钥池 + 绑定关系 + 报告 + 脚本全部自包含，路径相对解析。拷目录 = 完整迁移，换新 agent 主机后可直接用原密钥/密码登录所有服务器。
- **禁止硬编码路径**：所有脚本通过 `lib-common.sh` 自定位 skill 根目录，不要写死 `/root/...` 之类的绝对路径。

## 何时使用

- 登录/检查/巡检某台 Linux 服务器（"看看 10.0.0.5 的状态"）
- 登记新服务器、修改分类/认证方式/密码
- 记录或查询服务器的：服务、服务路径、配置文件、数据库、中间件、账号密码、开发端口
- 生成/导入/部署 SSH 密钥，配置免密登录
- 统一管理多台设备（多台 agent 主机/笔记本）的免密密钥：批量导入、按设备登记、一机绑定多密钥
- 打包迁移到新的 agent 主机

## 环境自检（每次会话首次使用时）

```bash
command -v jq ssh        # 必需；密码认证还需 sshpass
```

缺则安装：`apt install -y jq openssh-client sshpass`（或 yum 等价物）。

## 命令速查

所有脚本位于 `scripts/`，均支持 `-h` 查看用法。

| 任务 | 命令 |
|------|------|
| 列出服务器（可按分类） | `server-list.sh [--category 生产]` |
| 查看单台完整档案 | `server-show.sh <host> [--user U]` |
| 登记/更新服务器 | `server-add.sh --host H --user U (--key K \| --password P) [--category C] [--root-password P] [--become-root]` |
| 删除服务器 | `server-remove.sh <host> --user U --yes` |
| 生成/导入/部署密钥 | `key-manage.sh generate/import/deploy` |
| 批量导入某设备全部密钥 | `key-manage.sh import-all ~/.ssh --device <设备名>` |
| 一机绑定/解绑多密钥 | `key-manage.sh bind/unbind <host> --key NAME` |
| 密钥池全部公钥部署到一台服务器 | `key-manage.sh deploy-all <host>` |
| 密钥池总览（来源设备/绑定关系） | `key-manage.sh list` |
| 执行任意远程命令 | `ssh-run.sh <host> [--user U] [--root] "命令"` |
| 安全巡检并回写档案 | `server-check.sh <host> [--user U]` |
| 迭代回写巡检档案 | `server-update.sh <子命令>`（见下） |
| 批量每日磁盘巡检 | `daily-disk-check.sh [--threshold 80]` |
| 打包迁移/导入 | `export-import.sh export / import` |

## server-update.sh 子命令（迭代回写，同名自动合并）

```bash
server-update.sh service    <host> --name nginx --path /usr/sbin/nginx --config /etc/nginx/nginx.conf --port 80 --status running
server-update.sh database   <host> --name mysql-main --type mysql --version 8.0 --port 3306 --data-dir /var/lib/mysql
server-update.sh middleware <host> --name redis --port 6379 --config /etc/redis.conf
server-update.sh cred       <host> database mysql-main root 'S3cret!' --purpose "mysql root"   # 改密就重跑，自动打时间戳
server-update.sh cred       <host> os oracle 'xxx'                                            # 记录系统账号
server-update.sh devport    <host> --port 3000 --service "前端dev"
server-update.sh note       <host> "根分区曾 99% 满，磁盘满时 SSH 超时要给 60-90s"
server-update.sh category   <host> "生产"
server-update.sh watch      <host> --name openclaw --match "openclaw gateway" --start-cmd "..." --auto-restart
```

## Agent 标准工作流

### 流程 A：巡检一台服务器（"检查 10.0.0.5"）

1. `server-show.sh 10.0.0.5` 读档案（多账号时按提示加 `--user`）
2. `server-check.sh 10.0.0.5` 执行巡检 → 报告存 `reports/`，基础信息（主机名/OS/内核/监听端口）**自动回写**；过期报告自动清理（默认保留 30 天，见下）
3. **解读报告**（结构见 `assets/inspection-report-template.md`），把识别出的服务/数据库/中间件/端口用 `server-update.sh` 回写
4. 向用户汇报：异常项（磁盘告警/可疑进程/未授权用户/关注服务宕掉）优先说

### 流程 B：接管一台新服务器

1. `server-add.sh --host H --user U --password 'xxx' --category ...`（密码先行）
2. `key-manage.sh generate default`（若尚无密钥）
3. `key-manage.sh deploy H --key default` → 自动切免密并验证
4. 走流程 A 完成首次巡检建档

### 流程 C：换机迁移 / 新 agent 接管

按 `references/migration-guide.md` 执行：`export-import.sh export --with-reports` → 传输 → `import` → `server-list.sh` + 抽查连通性。

### 流程 E：多设备免密登录统一管理（"把各台设备上的密钥都收进来"）

场景：设备 A（如原 agent 主机）、设备 B（如笔记本）各自持有不同私钥，都能免密登录某些服务器。统一管理办法：

1. 在每台设备上批量导入其私钥到密钥池（标注来源设备）：
   - 设备 A 上：`key-manage.sh import-all ~/.ssh --device agentA`，然后把整个 skill 目录同步到统一存放处
   - 设备 B 上同理，或把 B 的 `~/.ssh` 拷过来后 `import-all <目录> --device 笔记本B`
2. `key-manage.sh list` 核对密钥池：来源设备、指纹、当前绑定关系一目了然
3. 对每台服务器绑定它能用的所有密钥：`key-manage.sh bind <host> --key agentA_id_ed25519`、`bind <host> --key 笔记本B_id_rsa`
   - 若某密钥的公钥还没部署到该服务器：先 `deploy <host> --key <name>`（用现有认证推公钥）
   - 想让一台服务器接受密钥池全部密钥：`deploy-all <host>`
4. 之后从任意设备发起连接，`key_names` 列表按序自动尝试，任一密钥命中即登录成功
5. 设备淘汰时：`unbind <host> --key <name>` 解绑（仅改档案）；要撤远端授权需登录该服务器删 authorized_keys 对应行

### 流程 D：用户问"某台服务器的数据库密码是多少"

直接 `server-show.sh <host>` 或 jq 查 `config/servers.json` 的 `inspection.databases[].credentials`，不要重新巡检。

## 检查内容（server-check.sh 远程执行）

1. 系统信息：主机名/内核/内存/磁盘（>80% 告警）
2. 登录用户：未授权用户告警
3. 网络：出口流量、连接数
4. 监听端口全量列表（自动回写档案）
5. 可疑进程：minerd/xmrig/木马后门等特征
6. authorized_keys 风险：各用户授权密钥数量
7. 关注服务（watch_services）：存活检查，`auto_restart=true` 时自动拉起

磁盘 >90% 时的清理顺序：先 `du -h --max-depth=1 /`（/root/logs 下的 Sentinel/RocketMQ 旧日志最常见）→ `journalctl --vacuum-size=100M` → `yum clean all`；保留 30~60 天，`/data` **绝对不删**。

## 注意事项

- **明文密码是用户明确需求**：servers.json 权限保持 600；导出包含私钥与密码，提醒用户加密传输、用完即删；不要把 skill 目录提交 git
- **SSH 参数**：默认 `-o ConnectTimeout=10`；磁盘满/高负载机器用 `--timeout 60~90`
- **su 提权**：档案 `become_root=true` 且有 root_password 时，巡检自动 `su - root` 执行（沿用旧版验证过的 `echo pw | su - root -c` 机制）
- **多账号机器**：host+port+username 为唯一键，操作时按提示加 `--user`
- **巡检回写分工**：基础事实自动回写；结构化知识（服务/库/中间件/凭证）由 agent 解读后迭代回写——这是档案持续保鲜的关键，巡检完不要跳过第 3 步

## 资源索引

- `references/data-schema.md` — servers.json 完整字段定义与 jq 查询示例；需要理解/手工修档案结构时读取
- `references/migration-guide.md` — 四种迁移/接管场景的分步指南；换机、密钥丢失、旧版迁移时读取
- `references/vastbase-g100-install-notes.md` — 某 RHEL 服务器上 Vastbase G100（缺 license）与 PG15 实例安装记录；涉及该机器数据库操作时读取
- `references/zfs-usb-disk-troubleshooting.md` — USB 磁盘 ZFS 池开机不导入的排障记录；遇到 ZFS 挂载丢失时读取
- `assets/inspection-report-template.md` — 巡检报告结构与回写示例；解读巡检报告时读取
- `config/servers.example.json` — 脱敏示例档案，展示完整字段用法；初始化或理解结构时参考

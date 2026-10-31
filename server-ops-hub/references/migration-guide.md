# 迁移指南：换 Linux 机器 / 换 agent 主机

## 核心原则

**整个 skill 目录就是可迁移单元。** 档案（servers.json）、密钥（keys/）、巡检报告（reports/）、脚本全部自包含，路径相对解析，拷走即用。

## 场景一：整体迁移（推荐）

```bash
# 旧机器打包
scripts/export-import.sh export --with-reports
# 产出 server-ops-hub-export-YYYYMMDD-HHMMSS.tar.gz（含 MANIFEST 校验信息）

# 传输到新机器（任选 scp/oss/网盘；文件含私钥与明文密码，建议 gpg -c 加密）
gpg -c server-ops-hub-export-*.tar.gz   # 可选加密
scp server-ops-hub-export-*.tar.gz* new-host:/tmp/

# 新机器导入
scripts/export-import.sh import /tmp/server-ops-hub-export-*.tar.gz --dest ~/skills/
# 自动修复权限：keys/ 700、私钥 600、脚本 +x
```

导入后验证：

```bash
cd ~/skills/server-ops-hub
command -v ssh jq          # 依赖自检；密码认证还需 sshpass
scripts/server-list.sh     # 档案应完整呈现
scripts/ssh-run.sh <host> "echo ok && hostname"   # 挑一台验证连通
```

## 场景二：新 agent 主机快速接管（无旧包）

如果只有本 skill 目录的拷贝（如从 git/网盘恢复），直接：

1. 装依赖：`apt install -y openssh-client jq sshpass`（或 yum 等价物）
2. `scripts/server-list.sh` 看全部档案
3. `scripts/ssh-run.sh <host> "echo ok"` 逐台验证
4. key 认证失败的机器：确认 `keys/` 里的私钥齐全；缺失时走场景三

## 场景三：密钥丢失/重建

```bash
# 生成新密钥对
scripts/key-manage.sh generate default

# 用密码认证部署公钥到各服务器（需要档案里存了密码，或临时 server-add --password 补登）
scripts/key-manage.sh deploy <host> --key default

# 验证
scripts/ssh-run.sh <host> "echo ok"
```

## 场景四：从旧版 skill（servers.conf 纯文本）迁移

旧 `servers.conf` 每行格式为 `IP 端口 用户名 root密码`（空密码为 `''`），转换规则：

- 登录方式默认密钥认证（`auth.type=key`），第四列 root 密码 → `auth.root_password`，登录用户非 root 时 `become_root=true`
- 逐条用 `server-add.sh` 录入即可，例如：
  `server-add.sh --host 192.168.1.20 --user root --key default --root-password 'xxx'`
- 旧配置第四列非空且用户名即 root 的条目，可能是密码认证，首次连接验证后用
  `server-add.sh --host 192.168.1.20 --user root --password 'xxx'` 调整

## 场景五：多台设备的免密密钥归集到密钥池

多台设备（多台 agent 主机、笔记本）各自持有不同私钥、各自能免密登录部分服务器。归集步骤：

```bash
# 在每台设备上各执行一次（或把各设备的 ~/.ssh 拷到一处分别导入）
scripts/key-manage.sh import-all ~/.ssh --device openclaw主机
scripts/key-manage.sh import-all /tmp/laptop-ssh --device 笔记本

# 核对密钥池与绑定关系
scripts/key-manage.sh list

# 给每台服务器绑定它能用的全部密钥（公钥未部署的先部署）
scripts/key-manage.sh bind <host> --key openclaw主机_id_ed25519
scripts/key-manage.sh deploy <host> --key 笔记本_id_rsa
# 或一步到位：把密钥池全部公钥推给某台服务器
scripts/key-manage.sh deploy-all <host>
```

要点：

- `import-all` 只认含 `PRIVATE KEY` 头的文件，自动跳过 .pub/known_hosts/config
- 命名规则 `<设备名>_<原文件名>`，避免不同设备的同名密钥互相覆盖
- 绑定后连接按 `auth.key_names` 顺序尝试，任何一台设备的密钥命中即登录成功
- 归集完成后做一次 `export` 打包，这份包就是"全设备通用钥匙串"，拷到哪台机器都能工作

## 依赖清单（新机器）

| 依赖 | 用途 | 安装 |
|------|------|------|
| `ssh`/`ssh-keygen` | 连接与密钥管理 | `apt install -y openssh-client` / `yum install -y openssh-clients` |
| `jq` | 档案库读写（必需） | `apt install -y jq` / `yum install -y jq` |
| `sshpass` | 密码认证非交互登录 | `apt install -y sshpass` / `yum install -y sshpass` |
| `bash` ≥ 4 | 脚本运行 | 一般自带 |

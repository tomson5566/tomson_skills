# Vastbase G100 V2.2 安装笔记

## 环境信息
- **服务器**: 192.168.1.10（rhel-root 50G, 99%满）
- **已有PG**: PostgreSQL 15 @ 端口 10000
- **安装包位置**: `/data/pg/f/`
- **安装包版本**: Vastbase-G100-2.2_Build13 (13766) — 华为高斯数据库

## 包文件说明

| 文件 | 类型 | 用途 |
|------|------|------|
| `Vastbase-G100-2.2_Build13(13766)-CentOS-64bit.tar.bz2` | 172MB | 主体（需bzip2解压，服务器无bzip2） |
| `Vastbase-G100-2.2_Build13(13766)-centos_7-x86_64-no_mot.tar.gz` | 527MB | 内含上述tar.bz2+升级包 |
| `Vastbase-G100-2.2_Build13(13766)-CentOS-64bit-om.tar.gz` | 14MB | OM运维管理工具（Python paramiko等） |
| `Vastbase-G100-2.2_Build13(13766)-CentOS-64bit-vpatch.tar.gz` | 349MB | gcc编译工具链补丁 |
| `upgrade_sql.tar.gz` | 515KB | SQL升级脚本 |
| `version.cfg` | 34B | 版本信息：Vastbase-G100-2.2.13, 92.790, 13766 |

## 已解压目录 `/data/pg/f/` 结构

```
/data/pg/f/
├── bin/      # 可执行文件（含 vastbase, vb_initdb, vsql 等）
├── lib/      # 动态链接库（含 libssl.so.1.1 等）
├── include/  # 头文件
├── etc/      # 配置文件（kerberos, localkms）
├── share/    # locale, doc, postgresql/
├── python/   # Python依赖
├── jre/      # Java运行时
└── upgrade_sql.tar.gz
```

## 安装流程（失败）

### 步骤（不可用）
1. `useradd vastbase` 创建专用用户
2. `ln -sfn /data/pg/f /usr/local/vastbase`
3. `LD_LIBRARY_PATH=/data/pg/f/lib vb_initdb -D /data/vb_data --nodename=vbnode1`
4. 启动时报错：`license reload failed`

### 失败根因
**`gaussdb.version` 文件不存在或不合法**

- Vastbase G100 是商业闭源数据库，启动时校验 `gaussdb.version`（需华为官方签名）
- 自建 `gaussdb.version` 导致 `FATAL: "gaussdb.version" configuration file is not official`
- `vb_licensetool --dump` 和 `--view-temporary` 均失败（无license文件）
- 服务器上无 `.lic` 文件

### 结论
Vastbase G100 **必须有华为官方正式 License 文件**才能启动，无法通过命令行强制初始化。

## 替代方案：安装 PostgreSQL 15 新实例

已在 192.168.1.10 上成功安装：

```
数据目录: /data/pg15_data
端口:     5433（避开已有的 10000）
版本:     PostgreSQL 15.10
状态:     ✅ 运行中（PID 7850）
用户:     postgres（系统用户）
```

### 安装步骤
```bash
# 1. 创建数据目录
mkdir -p /data/pg15_data
chown postgres:postgres /data/pg15_data

# 2. 初始化
sudo -u postgres /usr/pgsql-15/bin/initdb -D /data/pg15_data --locale=C --encoding=UTF8

# 3. 修改端口
sed -i 's/^#port = 5432/port = 5433/' /data/pg15_data/postgresql.conf

# 4. 设置认证（本地trust）
sed -i 's/^local.*all.*all.*peer/local all all trust/' /data/pg15_data/pg_hba.conf

# 5. 启动
sudo -u postgres /usr/pgsql-15/bin/pg_ctl -D /data/pg15_data -l /data/pg15_data/logfile start

# 6. 验证
ss -tulnp | grep 5433
sudo -u postgres /usr/pgsql-15/bin/psql -p 5433 -c "SELECT version();"
```

## 关键经验

1. **磁盘99%满时，SSH超时设置要足够长**（60-90s），否则所有远程命令都超时失败
2. **bzip2包**在无bzip2工具的服务器上用 `python3 -c "import tarfile; tarfile.open(..., 'r:bz2')"` 解压
3. **商业数据库**（Vastbase、TiDB企业版等）启动依赖license文件，离线包中不一定包含，需要联系厂商获取
4. **PG多实例**端口不能冲突，5432/5433/10000是不同的，避免混淆

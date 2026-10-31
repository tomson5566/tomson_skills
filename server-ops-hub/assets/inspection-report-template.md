# 巡检报告结构模板

`server-check.sh` 生成的报告（`reports/<host>_<时间戳>.log`）遵循以下结构，
agent 解读报告时按此分段提取信息，并用 `server-update.sh` 回写档案。

## 报告分段

| 段落 | 内容 | agent 回写建议 |
|------|------|----------------|
| `[1/7] 系统信息` | 主机名/OS/内核/内存/磁盘 | 磁盘告警写入 `note`；OS 信息已自动回写 |
| `[2/7] 登录用户` | 在线用户 + 可登录账号列表 | 新发现的系统账号用 `cred os` 或 `note` 记录 |
| `[3/7] 网络流量` | 接口累计流量、连接数 | 异常突增写 `note` |
| `[4/7] 监听端口` | ss/netstat 全量输出 | 识别出的服务逐个 `service`/`devport` 回写 |
| `[5/7] 可疑进程` | 恶意进程特征扫描 | 发现即告警用户，并 `note` |
| `[6/7] authorized_keys` | 各用户授权密钥数量 | 数量异常告警用户 |
| `[7/7] 关注服务` | watch_services 状态 | 状态变化用 `service --status` 回写 |
| `###RSC_*###` 标记块 | 机器可读元数据 | 已自动回写，无需处理 |

## 回写示例（agent 解读后执行）

```bash
# 从监听端口识别出 nginx 和 mysql
server-update.sh service 10.0.0.5 --name nginx --port 80 --config /etc/nginx/nginx.conf --status running
server-update.sh database 10.0.0.5 --name mysql-main --type mysql --version 8.0 --port 3306 --data-dir /var/lib/mysql
server-update.sh cred 10.0.0.5 database mysql-main root 'S3cret!' --purpose "mysql root"
server-update.sh devport 10.0.0.5 --port 3000 --service "前端 dev server"
server-update.sh note 10.0.0.5 "根分区 85%，/var/log 占大头，已清理 journal"
```

## 原则

- **先 check 后 update**：巡检拿事实，解读后回写结构化档案
- **迭代不覆盖**：密码变更、服务增减，直接重跑对应子命令，自动按名字合并、打时间戳
- **报告是流水，档案是资产**：报告可清理，servers.json 是长期资产

# PowerMem 故障排查参考

## 2025-05-31 排查记录

### 问题：pmem memory list 报错 502

**现象**：
```
pmem memory list
Error: Failed to initialize PowerMem:  (status code: 502)
```

**诊断步骤**：

**1. 检查配置连通性**
```bash
pmem config show        # 查看完整配置
pmem config test        # 测试数据库/LLM/Embedding 连通性
```
期望输出：`Results: 3 passed, 0 failed, 0 skipped`

**2. 如 config test 报错 "Failed to connect to Ollama"**
```bash
pgrep -a ollama
systemctl status ollama
```
无进程 → Ollama 未运行

**3. 启动 Ollama（若未运行）**
```bash
nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 3
pgrep -a ollama
```

**4. 重新验证**
```bash
pmem config test
pmem memory list
```

**config test 成功输出样例**：
```
[INFO] Testing configuration connectivity...
[INFO] Testing database connection...
Invalid timezone config: {'timezone': ''}
[SUCCESS] Database: Connected
[INFO] Testing LLM connection...
[SUCCESS] LLM: Connected
[INFO] Testing embedder connection...
[SUCCESS] Embedder: Connected (dims=768)

Results: 3 passed, 0 failed, 0 skipped
```

---

### ⚠️ embedding base URL 变量名陷阱（重要）

**现象**：配置了 `OPEN_EMBEDDING_BASE_URL`，但 PowerMem 实际连接本机 127.0.0.1 而非远程地址

**根因**：PowerMem Ollama Embedding provider **只识别以下两个变量名**：
- `ollama_base_url`
- `OLLAMA_EMBEDDING_BASE_URL`

`OPEN_EMBEDDING_BASE_URL`（火山引擎等国产平台常用写法）PowerMem **完全不识别**，会被静默忽略。结果 `ollama_base_url` 保持为空，Ollama SDK 默认连接 `http://127.0.0.1:11434`（即本机 ollama）。

**验证**：
```bash
pmem config show --section embedder --show-secrets
```
若 `ollama_base_url` 行为空 → 变量名写错了

**正确写法**（在 `/root/.env` 中）：
```bash
OLLAMA_EMBEDDING_BASE_URL=http://10.229.190.87:11434
```

> ⚠️ **关键：pmem 读取的是 `/root/.env`，不是 `~/.hermes/.env`**。PowerMem 默认使用 pydantic-settings 的 `env_file = "/root/.env"`（写死在源码里），两个文件可能同时存在但只有 `/root/.env` 生效。

---

### 注意事项

- "Invalid timezone config: {'timezone': ''}" 不影响正常使用，可忽略
- 树莓派等设备重启后 Ollama 不会自动启动，需确保 systemd 服务配置正确
- `embeddinggemma:latest` 实际输出 dims=768，与配置声明的 1024 不一致，不影响功能
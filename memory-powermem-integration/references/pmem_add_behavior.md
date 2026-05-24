# PowerMem pmem add 行为记录

## 2026-05-24 实测发现

### `pmem memory add` 内部语义拆分

pmem 的 `--no-infer` 禁用后，默认会做语义推理和拆分。

**实测示例**：传入单条摘要 `192.168.3.230 服务器配置: qwenpaw用户...`，返回了 4 条 ADD 事件。

这意味着：
- 单次 `add` 调用可能写入多条记忆
- 每条记忆都会携带完整的 metadata（10 个标签）
- `{"results": [...], "event": "ADD"}` 中有多条 entry 是正常现象

### 响应时间

| 场景 | 耗时 |
|------|------|
| 带推理（默认） | 35~90s（波动大，受 API 延迟影响） |
| `--no-infer` 跳过推理 | **3~6s** |

> ⚠️ 优先使用 `--no-infer`，推理模式仅在需要 AI 自动打标签时启用。

### `--json` 解析卡住问题

使用 `--json` 时偶发解析卡住（JSON 输出模式在某些环境下挂起）。**不要使用 `--json`**，直接解析纯文本响应即可。

### 正确调用格式

```bash
# 推荐：跳过推理，快速写入
pmem memory add "[内容摘要]" --metadata '{"tag1_time":"...","tag2_topicA":"..."}' --no-infer

# 备用：启用推理模式（慢，用于 AI 自动打标签场景）
pmem memory add "[内容摘要]" --metadata '{"tag1_time":"...","tag2_topicA":"..."}'
```

### 不支持的参数

经实测，以下参数在 `memory add` 子命令中**不存在**：
- `--scope` → `Error: No such option: --scope`
- `--memory-type` → 同上

### 幂等检查结论

手动 SHA256 hash 幂等检查**被放弃**，因为：
1. pmem 内部已有智能去重机制
2. pmem 会对内容做语义拆分，hash 无法匹配
3. 实测短文本和长文本混合写入同一内容不会重复

**更新策略**：按需搜索已有记忆，若搜索结果 score > 0.8 且内容高度相似则跳过写入。
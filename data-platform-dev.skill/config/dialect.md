# 平台方言差异对照（可扩展）

本技能正文统一采用 **Hive / Spark SQL** 风格，多数数仓与湖仓平台均可接受。各平台差异收敛在本文件，**正文不重复展开**。

## 差异对照表

| 差异点 | 常见写法 A（推荐/统一） | 常见写法 B | 建议 |
|---|---|---|---|
| 建表语句 | `CREATE TABLE IF NOT EXISTS` | `CREATE OR REPLACE TABLE` | 统一用 `IF NOT EXISTS`，重建表走单独变更流程 |
| 字符串类型 | `STRING` | `VARCHAR(n)` | 统一用 `STRING`，长度约束由平台侧管理 |
| 时间类型 | `DATETIME` | `TIMESTAMP` | 统一用 `STRING` 存 `yyyyMMdd` / `yyyy-MM-dd`，另留时间戳字段 |
| 分区声明 | `PARTITIONED BY (ds STRING)` | 平台分区语法 | 置于建表语句末尾 |
| 写入语法 | `INSERT OVERWRITE TABLE ... PARTITION` | `INSERT OVERWRITE` | 统一 OVERWRITE + 分区条件，保证幂等 |
| 开窗函数 | `OVER (PARTITION BY ...)` | 标准 SQL | 优先标准 SQL，避免平台特有语法 |
| 日期函数 | `DATE_SUB / DATE_ADD / ADD_MONTHS` | 平台特有函数 | 统一封装在调度参数与公共 UDF，不散落业务 SQL |

## 新增平台步骤
1. 在下表新增一行（或新增一张方言映射），列出与本技能默认写法的差异。
2. 全文检索正文与 `templates/*.sql`，把平台特有语法替换或标注。
3. 用目标平台跑通 `ods→dwd→ads` 端到端链路验证。

## 两条工程约束（防方言扩散）
- **约束一**：业务 SQL 禁止出现平台特有的日期计算函数，业务日期一律通过调度参数注入。
- **约束二**：平台特有语法（特殊表类型、向量索引、机器学习算子等）必须收敛在指定少数任务中，并在任务注释显式标注依赖平台特性，便于未来迁移。

## 扩展区域：企业实际平台登记
| 平台 | 建表语法差异 | 字号/分区差异 | 写入/幂等差异 | 日期函数差异 | 负责人 |
|---|---|---|---|---|---|
| Hive / Spark SQL（本技能默认） | `IF NOT EXISTS` | `PARTITIONED BY (ds STRING)` | `INSERT OVERWRITE ... PARTITION` | 调度参数注入 | 数据平台组 |
| MaxCompute | (按需填写) | (按需填写) | (按需填写) | (按需填写) | |
| (其他平台) | | | | | |
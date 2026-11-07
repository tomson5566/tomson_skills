# 2 命名规范

## 命名总则
- 统一使用**大写英文字母、数字、下划线**；禁止中文、空格、特殊符号。
- 表名长度建议 ≤ 128 字符，预计超限优先缩减源端实例名/用户名等次要要素。
- 同一业务含义的对象在各层间保持**词根一致**，便于检索与血缘识别。
- 各层前缀与编码取值必须来自 `config/` 编码表，**不得自行造词**。
- 新建对象一次符合规范，禁止 `test / tmp / 待定` 占位命名上线。

## 命名模式占位符（语法）
| 占位符 | 含义 | 取值来源 |
|---|---|---|
| {系统简称} | 源业务系统英文简称 | `config/source_systems.md` |
| {源端实例名} | 源端数据库实例名(可选) | 按源系统实际填写 |
| {源端用户名} | 源端数据库用户名 | 按源系统实际填写 |
| {源表名} | 源系统中的原始表名 | 与源系统保持一致 |
| {数据域} | 业务主题域英文缩写 | `config/business_domains.md` |
| {刷新周期} | 数据刷新周期编码 | `config/refresh_periods.md` |
| {增量标识} | 分区为增量或全量 | `config/refresh_periods.md` |
| {场景简称} | 业务场景/项目英文缩写 | 企业自定义（须登记） |
| {批次} | 并行/运行批次号(可选) | 企业自定义 |

## 数据表命名

### 贴源层
| 表类型 | 命名模式 | 示例 |
|---|---|---|
| 贴源层全量表 | `ods_{系统简称}_{实例}_{用户}_{源表名}` | `ods_erp_ecs_prod_customer` |
| 贴源层增量表 | `ods_{增量方式}_{系统简称}_{实例}_{用户}_{源表名}` | `ods_inc_erp_ecs_prod_customer` |

### 共享层与应用层
| 表类型 | 命名模式 | 示例 |
|---|---|---|
| 共享层明细表 | `dwd_{数据域}_{业务对象}` | `dwd_cust_customer_info` |
| 共享层汇总表 | `dwd_{数据域}_{业务对象}_agg` | `dwd_cust_customer_info_agg` |
| 维度表 | `dim_{数据域}_{维度名}` | `dim_cust_customer` |
| 事实明细表 | `fct_{数据域}_{事实主题}` | `fct_cst_daily_consume` |
| 汇总宽表 | `dws_{数据域}_{汇总主题}` | `dws_cst_cust_day_stat` |
| 应用结果表 | `ads_{数据域}_{场景简称}_{结果名}` | `ads_cst_sales_cust_rank` |
| 临时/中间表 | `tmp_{分层}_{表名}` | `tmp_dwd_customer_flat` |
| 废弃归档表 | `bak_{原表名}_{归档批次}` | `bak_dwd_customer_info_20261001` |

> 维度/事实/宽表可追刷周期与增量标识，如 `dws_cst_cust_day_stat_d` / `_df`；**同一对象的不同刷新语义不得使用同一表名**。

### 结果发布表与外部数据表
| 表类型 | 命名模式 | 示例 |
|---|---|---|
| 结果发布表 | `srv_{数据域}_{结果名}` | `srv_cust_customer_profile` |
| 外部数据接入表 | `ods_ext_{外部来源}_{行业/类别}_{源表名}` | `ods_ext_gov_enterprise_base` |
| 外部数据共享层表 | `dwd_{数据域}_{源表名}` | `dwd_mkt_enterprise_base` |

## 任务与作业命名
任务名 = **操作前缀 + 对象**，便于监控与批量识别。

| 前缀 | 含义 | 命名模式 | 示例 |
|---|---|---|---|
| ext | 抽取 | `ext_{目标表名}` | `ext_ods_erp_ecs_prod_customer` |
| sy | 同步/集成 | `sy_{源库}_to_{目标库}_{表名}` | `sy_mysql_to_hive_dwd_cust_customer` |
| mrg | 增量合并 | `mrg_{目标表名}` | `mrg_ods_erp_ecs_prod_customer` |
| cln | 清洗 | `cln_{目标表名}` | `cln_dwd_cust_customer_info` |
| mod | 建模/覆模 | `mod_{目标表名}` | `mod_dwd_cust_customer_info` |
| agg | 汇总 | `agg_{目标表名}` | `agg_dws_cst_cust_day_stat` |
| pub | 发布 | `pub_{目标表名}` | `pub_srv_cust_customer_profile` |
| chk | 核查 | `chk_{数据域}_{对象}_{规则号}` | `chk_cust_customer_001` |
| sql | 自定义 SQL 加工 | `sql_{目标表名}` | `sql_dws_cst_cust_day_stat` |
| tmp | 临时/排障 | `tmp_{空间}_{用途}_{序号}` | `tmp_dev_debug_001` |

作业目录建议按 **空间 / 分层 / 目标表** 三级组织，与任务名对应。

## 数据服务接口命名
| 要素 | 规则 | 示例 |
|---|---|---|
| 服务分组 | 以业务应用/消费方中文命名 | 销售管理 |
| 接口名称 | `{方法}_{业务对象}_{动作}_{口径}` | `get_customer_profile_by_org` |
| 请求路径 | `/{业务域}/{资源}/{方法}_{动作}` | `/customer/profile/get_by_org` |
| 数据集名称 | `{业务域}_{数据集名}_ds` | `ds_cust_customer_profile` |
| 文件交付物 | `{日期}_{数据域}_{对象}_v{版本}` | `20261101_cust_customer_v1` |

> 接口一经发布，名称与路径不得变更；变更发新版本并公告下线时间，旧版本保留过渡期。

## 命名审核与整改
| 情形 | 处理方式 |
|---|---|
| 上线前命名不合规 | 退回整改，整改后方可发布 |
| 存量对象不合规 | 登记问题清单，限期整改并复核 |
| 同一对象多套命名并存 | 以共享层标准命名为唯一权威，其余下线或改为引用 |
| 因命名导致口径歧义 | 由数据 owner 裁定唯一口径，并回溯修正历史引用 |
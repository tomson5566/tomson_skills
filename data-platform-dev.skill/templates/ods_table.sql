-- 贴源层建表模板：保持源结构，仅做类型对齐与接入必需的技术性处理
-- 命名：ods_{系统简称}_{源端实例名}_{源端用户名}_{源表名}
-- 全量：ods_erp_ecs_prod_customer ; 增量：ods_{inc/idc/cdc/full}_{...}
CREATE TABLE IF NOT EXISTS ods_erp_ecs_prod_customer (
  id           STRING        COMMENT '客户主键',
  cust_name    STRING        COMMENT '客户名称',
  id_no        STRING        COMMENT '证件号码（敏感，已加密存储）',
  reg_capital  DECIMAL(18,4) COMMENT '注册资本',
  created_time STRING        COMMENT '创建时间 yyyy-MM-dd HH:mm:ss',
  updated_time STRING        COMMENT '更新时间 yyyy-MM-dd HH:mm:ss',
  etl_time     STRING        COMMENT 'ETL 写入时间 yyyy-MM-dd HH:mm:ss'
)
COMMENT '贴源层-ERP生产库-客户表；一行 = 源系统客户记录'
PARTITIONED BY (ds STRING);
-- 说明：
-- * etl_time 为必留字段，用于判定同步水位与排查延迟；源端有同名字段不得覆盖，应另命名。
-- * 分区字段固定 ds（yyyyMMdd）；多租户场景另加 tenant_id。
-- * 金额一律 DECIMAL(18,4)，禁止 FLOAT/DOUBLE。
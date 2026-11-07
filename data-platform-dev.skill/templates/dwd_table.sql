-- 共享层建表模板：业务主题模型，字段口径统一
-- 命名：dwd_{数据域}_{业务对象}（汇总加 _agg）
CREATE TABLE IF NOT EXISTS dwd_cust_customer_info (
  cust_id       STRING        COMMENT '客户唯一标识（客户域标准ID）',
  cust_name     STRING        COMMENT '客户名称（去除首尾空格）',
  id_no_cipher  STRING        COMMENT '证件号码密文',
  cert_type     STRING        COMMENT '证件类型，统一字典编码',
  reg_capital   DECIMAL(18,4) COMMENT '注册资本（元）',
  cust_level    STRING        COMMENT '客户等级，统一字典编码',
  cust_status   STRING        COMMENT '客户状态：NORMAL/FROZEN/CLOSED',
  src_system    STRING        COMMENT '来源系统简称',
  src_pk        STRING        COMMENT '来源系统主键',
  is_valid      STRING        COMMENT '是否有效：1有效 0无效',
  etl_time      STRING        COMMENT 'ETL 写入时间'
)
COMMENT '共享层-客户域-客户主数据；一行 = 一个客户当前有效记录'
PARTITIONED BY (ds STRING);
-- 共享层建表三硬要求：
-- 1. 字段名体现统一后口径，而非照搬源系统命名（例：源端 id_no 在共享层按敏感级别命名为 id_no_cipher）。
-- 2. 枚举值统一映射企业字典表，禁止各系统各自取值。
-- 3. 必须保留 src_system 与 src_pk，以支持多源合并与问题追溯。
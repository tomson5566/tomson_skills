-- 维度表建表模板：一致性维度，全公司唯一一份定义，所有事实表引用同一张
-- 命名：dim_{数据域}_{维度名}
CREATE TABLE IF NOT EXISTS dim_cust_customer (
  cust_id     STRING  COMMENT '客户唯一标识',
  cust_name   STRING  COMMENT '客户名称',
  cust_level  STRING  COMMENT '客户等级',
  cust_status STRING  COMMENT '客户状态',
  reg_date    STRING  COMMENT '注册日期',
  ch_id       STRING  COMMENT '渠道',
  region_id   STRING  COMMENT '地区',
  is_current  STRING  COMMENT '拉链标识，1 表示当前有效',
  valid_from  STRING  COMMENT '有效开始日期',
  valid_to    STRING  COMMENT '有效结束日期'
)
COMMENT '共享层-客户域-客户维度（一致性维度/拉链）'
PARTITIONED BY (ds STRING);

-- 一致性维度取用示例：所有事实表统一引用
SELECT d.cust_id,
       d.cust_name,
       d.cust_level,
       d.cust_status,
       d.reg_date,
       d.ch_id,
       d.region_id,
       d.is_current,
       d.valid_from,
       d.valid_to
FROM   dim_cust_customer d
WHERE  d.ds = '${bizdate}'
AND    d.is_current = '1';
-- 注意：高变更属性（客户等级、渠道归属）不得代入事实表做退化维度，否则事实/维表不一致。
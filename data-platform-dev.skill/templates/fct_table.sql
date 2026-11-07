-- 事实表建表模板：事务型事实（每行一次业务事件）
-- 命名：fct_{数据域}_{事实主题}
CREATE TABLE IF NOT EXISTS fct_cst_daily_consume (
  order_id    STRING        COMMENT '订单号',
  cust_id     STRING        COMMENT '客户唯一标识',
  pay_time    STRING        COMMENT '支付时间',
  amount      DECIMAL(18,4) COMMENT '消费金额（元）',
  order_cnt   BIGINT        COMMENT '订单数',
  region_id   STRING        COMMENT '地区（低基数稳定属性可退化）',
  ch_id       STRING        COMMENT '渠道（低基数稳定属性可退化）',
  src_system  STRING        COMMENT '来源系统简称',
  etl_time    STRING        COMMENT 'ETL 写入时间'
)
COMMENT '事实表-客户域-日消费事实；一行 = 一次消费事件'
PARTITIONED BY (ds STRING);
-- 三种事实表：
-- * 事务型事实(本模板)：每行一次事件，数据量最大，注意分区与压缩。
-- * 周期快照：每行一个周期末状态(账户余额、库存)，周期粒度与业务口径一致。
-- * 累积快照：每行一个周期累计状态(累计收入)，与事务型易混淆，须在命名与注释中区分。
-- 退化维度仅限低基数、极少变更属性(城市、行业大类)；高变更属性不得退化。
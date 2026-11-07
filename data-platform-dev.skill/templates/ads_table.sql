-- 应用层建表模板：面向场景的结果表
-- 命名：ads_{数据域}_{场景简称}_{结果名}
CREATE TABLE IF NOT EXISTS ads_cst_sales_cust_rank (
  rank_no      INT           COMMENT '排名',
  cust_id      STRING        COMMENT '客户唯一标识',
  cust_name    STRING        COMMENT '客户名称',
  sales_amt    DECIMAL(18,4) COMMENT '销售额（元）',
  order_cnt    BIGINT        COMMENT '订单数',
  stat_date    STRING        COMMENT '统计日期 yyyy-MM-dd'
)
COMMENT '应用层-客户域-销售场景-客户销售排行；一行 = 一个客户在统计日内的销售排名'
PARTITIONED BY (ds STRING);
-- 应用层表满足"可直接消费"：
-- * 字段语义自解释；指标口径与指标平台登记一致；附统计日期与数据更新时间。
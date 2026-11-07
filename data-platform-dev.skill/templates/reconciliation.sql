-- 数据对账模板：上线/补数后必做，与方法见 docs/07-quality.md

-- 1) 源端与目标端行数比对
SELECT 'source' AS side, COUNT(1) AS cnt
FROM   ods_crm_customer
WHERE  ds = '${bizdate}'
UNION ALL
SELECT 'target' AS side, COUNT(1) AS cnt
FROM   dwd_cst_customer_info
WHERE  ds = '${bizdate}';

-- 2) 主键唯一性检查（应返回 0 行）
SELECT cust_id, COUNT(1) AS cnt
FROM   dwd_cst_customer_info
WHERE  ds = '${bizdate}'
GROUP BY cust_id
HAVING COUNT(1) > 1;

-- 3) 关键金额汇总比对（与上下游/源端汇总值对比）
SELECT SUM(sales_amt) AS amt_sum
FROM   ads_cst_sales_cust_rank
WHERE  ds = '${bizdate}';

-- 通过标准：
-- * 记录数：差异在允许范围内
-- * 主键去重数：与源端唯一键数完全一致
-- * 汇总值：差异为零或在小数精度范围内
-- * 空值率：与历史对比无异常上升
-- * 抽样核对：按主键抽样字段值一致
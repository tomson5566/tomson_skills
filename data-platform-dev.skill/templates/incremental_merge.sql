-- 增量合并模板：以业务主键 + 更新时间判定最新，保证重跑幂等
-- 前置：确认增量水位 last_sync_time 已持久化（调度参数/元数据表），禁止硬编码日期。
INSERT OVERWRITE TABLE dwd_cust_customer_info PARTITION (ds = '${bizdate}')
SELECT t.cust_id,
       t.cust_name,
       t.id_no_cipher,
       t.cert_type,
       t.reg_capital,
       t.cust_level,
       t.cust_status,
       t.src_system,
       t.src_pk,
       t.is_valid,
       t.etl_time
FROM (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY s.cust_id
               ORDER BY s.updated_time DESC, s.etl_time DESC
           ) AS rn
    FROM   ods_crm_customer s
    WHERE  s.ds = '${bizdate}'
    AND    s.updated_time >= '${last_sync_time}'
) t
WHERE t.rn = 1;

-- 说明：
-- * 覆盖写入(OVERWRITE)保证幂等，任务可任意重跑且结果一致。
-- * 增量起始水位必须持久化，不得用固定日期替代；否则断点续传与补数会出错。
-- * 后置语句如需对同批次去重，可对目标分区按 etl_time 倒序保留最新一条。
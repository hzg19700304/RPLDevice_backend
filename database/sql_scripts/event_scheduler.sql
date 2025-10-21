-- RPLDevice数据库事件调度器配置
-- 用于自动执行分区管理、数据清理等维护任务

-- 启用事件调度器（如果未启用）
SET GLOBAL event_scheduler = ON;

-- 创建每日分区管理事件
CREATE EVENT IF NOT EXISTS daily_partition_management
ON SCHEDULE EVERY 1 DAY
STARTS CURRENT_TIMESTAMP + INTERVAL 1 DAY + INTERVAL 2 HOUR  -- 明天凌晨2点执行
DO
    -- 调用分区管理存储过程
    CALL manage_all_partitions();

-- 创建每周数据统计事件（简化版本）
CREATE EVENT IF NOT EXISTS weekly_data_statistics
ON SCHEDULE EVERY 1 WEEK
STARTS CURRENT_TIMESTAMP + INTERVAL 1 WEEK + INTERVAL 3 HOUR  -- 下周凌晨3点执行
DO
    -- 仅创建事件定义，不立即执行操作
    BEGIN
        -- 事件执行时进行统计操作
        -- 这里不包含立即执行的SQL语句
    END;

-- 创建每月数据清理事件（简化版本）
CREATE EVENT IF NOT EXISTS monthly_data_cleanup
ON SCHEDULE EVERY 1 MONTH
STARTS CURRENT_TIMESTAMP + INTERVAL 1 MONTH + INTERVAL 4 HOUR  -- 下月凌晨4点执行
DO
    -- 仅创建事件定义，不立即执行操作
    BEGIN
        -- 事件执行时进行数据清理操作
        -- 这里不包含立即执行的SQL语句
    END;

-- 创建数据库性能优化事件（简化版本）
CREATE EVENT IF NOT EXISTS database_optimization
ON SCHEDULE EVERY 1 WEEK
STARTS CURRENT_TIMESTAMP + INTERVAL 1 WEEK + INTERVAL 5 HOUR  -- 下周凌晨5点执行
DO
    -- 仅创建事件定义，不立即执行操作
    BEGIN
        -- 事件执行时进行数据库优化操作
        -- 这里不包含立即执行的SQL语句
    END;
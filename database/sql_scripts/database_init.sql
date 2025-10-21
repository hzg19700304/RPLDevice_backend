-- RPLDevice数据库初始化脚本
-- 创建数据库、用户权限和基础表结构

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS rpldevice 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE rpldevice;

-- 创建专用用户（生产环境建议使用）
-- CREATE USER IF NOT EXISTS 'rpl_device_user'@'localhost' IDENTIFIED BY 'secure_password_123';
-- GRANT ALL PRIVILEGES ON rpl_device.* TO 'rpl_device_user'@'localhost';
-- FLUSH PRIVILEGES;

-- 创建状态历史表（按月分区）
CREATE TABLE IF NOT EXISTS status_history (
    id BIGINT AUTO_INCREMENT,
    record_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录插入时间',
    timestamp DATETIME(3) NOT NULL COMMENT '状态变化时间戳（毫秒精度）',
    status_type VARCHAR(50) NOT NULL COMMENT '状态类型：WorkStatus/OutputStatus/FaultStatus/InputStatus',
    bit_position INT NOT NULL COMMENT '位位置（0-15）',
    old_value TINYINT NOT NULL COMMENT '变化前的状态值（0或1）',
    new_value TINYINT NOT NULL COMMENT '变化后的状态值（0或1）',
    status_name VARCHAR(100) NOT NULL COMMENT '状态名称描述',
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    upload_status TINYINT DEFAULT 0 COMMENT '上传状态：0-待上传，1-已上传，2-上传失败',
    upload_time DATETIME COMMENT '实际上传时间',
    retry_count TINYINT DEFAULT 0 COMMENT '重试次数',
    last_error VARCHAR(255) COMMENT '最后错误信息',
    PRIMARY KEY (id, timestamp),
    INDEX idx_device_id (device_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_device_timestamp (device_id, timestamp),
    INDEX idx_status_type_timestamp (status_type, timestamp),
    INDEX idx_status_bit_position (bit_position)
) 
PARTITION BY RANGE (TO_DAYS(timestamp)) (
    PARTITION p2024_01 VALUES LESS THAN (TO_DAYS('2024-02-01')),
    PARTITION p2024_02 VALUES LESS THAN (TO_DAYS('2024-03-01')),
    PARTITION p2024_03 VALUES LESS THAN (TO_DAYS('2024-04-01')),
    PARTITION p2024_04 VALUES LESS THAN (TO_DAYS('2024-05-01')),
    PARTITION p2024_05 VALUES LESS THAN (TO_DAYS('2024-06-01')),
    PARTITION p2024_06 VALUES LESS THAN (TO_DAYS('2024-07-01')),
    PARTITION p2024_07 VALUES LESS THAN (TO_DAYS('2024-08-01')),
    PARTITION p2024_08 VALUES LESS THAN (TO_DAYS('2024-09-01')),
    PARTITION p2024_09 VALUES LESS THAN (TO_DAYS('2024-10-01')),
    PARTITION p2024_10 VALUES LESS THAN (TO_DAYS('2024-11-01')),
    PARTITION p2024_11 VALUES LESS THAN (TO_DAYS('2024-12-01')),
    PARTITION p2024_12 VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_max VALUES LESS THAN MAXVALUE
);

-- 创建实时数据表（按月分区）
CREATE TABLE IF NOT EXISTS real_time_data (
    id BIGINT AUTO_INCREMENT,
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    timestamp DATETIME(3) NOT NULL COMMENT '数据采集时间戳（毫秒精度）',
    parameter_name VARCHAR(50) NOT NULL COMMENT '模拟量名称（如SV1/SA1）',
    value DECIMAL(10, 3) NOT NULL COMMENT '模拟量值',
    unit VARCHAR(10) NOT NULL COMMENT '单位（如V/A/℃）',
    upload_status TINYINT DEFAULT 0 COMMENT '上传状态：0-待上传，1-已上传，2-上传失败',
    upload_time DATETIME COMMENT '实际上传时间',
    retry_count TINYINT DEFAULT 0 COMMENT '重试次数',
    last_error VARCHAR(255) COMMENT '最后错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id, timestamp),
    INDEX idx_device_id (device_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_device_timestamp (device_id, timestamp),
    INDEX idx_parameter_name (parameter_name)
)
PARTITION BY RANGE (TO_DAYS(timestamp)) (
    PARTITION p2024_01 VALUES LESS THAN (TO_DAYS('2024-02-01')),
    PARTITION p2024_02 VALUES LESS THAN (TO_DAYS('2024-03-01')),
    PARTITION p2024_03 VALUES LESS THAN (TO_DAYS('2024-04-01')),
    PARTITION p2024_04 VALUES LESS THAN (TO_DAYS('2024-05-01')),
    PARTITION p2024_05 VALUES LESS THAN (TO_DAYS('2024-06-01')),
    PARTITION p2024_06 VALUES LESS THAN (TO_DAYS('2024-07-01')),
    PARTITION p2024_07 VALUES LESS THAN (TO_DAYS('2024-08-01')),
    PARTITION p2024_08 VALUES LESS THAN (TO_DAYS('2024-09-01')),
    PARTITION p2024_09 VALUES LESS THAN (TO_DAYS('2024-10-01')),
    PARTITION p2024_10 VALUES LESS THAN (TO_DAYS('2024-11-01')),
    PARTITION p2024_11 VALUES LESS THAN (TO_DAYS('2024-12-01')),
    PARTITION p2024_12 VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_max VALUES LESS THAN MAXVALUE
);

-- 创建事件记录表（按月分区）
CREATE TABLE IF NOT EXISTS event_records (
    id BIGINT AUTO_INCREMENT,
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    event_type VARCHAR(100) NOT NULL COMMENT '事件类型',
    event_time DATETIME(3) NOT NULL COMMENT '事件发生时间戳（毫秒精度）',
    description TEXT COMMENT '事件描述',
    upload_status TINYINT DEFAULT 0 COMMENT '上传状态：0-待上传，1-已上传，2-上传失败',
    upload_time DATETIME COMMENT '实际上传时间',
    retry_count TINYINT DEFAULT 0 COMMENT '重试次数',
    last_error VARCHAR(255) COMMENT '最后错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id, event_time),
    INDEX idx_device_id (device_id),
    INDEX idx_event_type (event_type),
    INDEX idx_event_time (event_time),
    INDEX idx_upload_status (upload_status),
    INDEX idx_device_event (device_id, event_type),
    INDEX idx_event_time_status (event_time, upload_status)
)
PARTITION BY RANGE (TO_DAYS(event_time)) (
    PARTITION p2024_01 VALUES LESS THAN (TO_DAYS('2024-02-01')),
    PARTITION p2024_02 VALUES LESS THAN (TO_DAYS('2024-03-01')),
    PARTITION p2024_03 VALUES LESS THAN (TO_DAYS('2024-04-01')),
    PARTITION p2024_04 VALUES LESS THAN (TO_DAYS('2024-05-01')),
    PARTITION p2024_05 VALUES LESS THAN (TO_DAYS('2024-06-01')),
    PARTITION p2024_06 VALUES LESS THAN (TO_DAYS('2024-07-01')),
    PARTITION p2024_07 VALUES LESS THAN (TO_DAYS('2024-08-01')),
    PARTITION p2024_08 VALUES LESS THAN (TO_DAYS('2024-09-01')),
    PARTITION p2024_09 VALUES LESS THAN (TO_DAYS('2024-10-01')),
    PARTITION p2024_10 VALUES LESS THAN (TO_DAYS('2024-11-01')),
    PARTITION p2024_11 VALUES LESS THAN (TO_DAYS('2024-12-01')),
    PARTITION p2024_12 VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_max VALUES LESS THAN MAXVALUE
);

-- 创建用户权限表
CREATE TABLE IF NOT EXISTS user_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role ENUM('admin', 'operator', 'viewer') DEFAULT 'viewer' COMMENT '用户角色',
    permissions JSON COMMENT '权限配置',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    last_login DATETIME COMMENT '最后登录时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_role (role),
    INDEX idx_is_active (is_active)
) COMMENT='用户权限表';

-- 插入默认管理员用户（密码：admin123，生产环境需要修改）
INSERT IGNORE INTO user_permissions (username, password_hash, role, permissions) 
VALUES (
    'admin', 
    '$2b$12$cfEy/P050DcXUl6dPtykIOV2uyqLR.ZvaVC1tquIjV6DH11Kr76WK',  -- bcrypt hash of 'admin123'
    'admin', 
    '{"devices": ["read", "write", "delete"], "users": ["read", "write", "delete"], "system": ["read", "write", "delete"]}'
);

-- 插入默认操作员用户（密码：operator123）
INSERT IGNORE INTO user_permissions (username, password_hash, role, permissions) 
VALUES (
    'operator', 
    '$2b$12$qno8YvtQWXxlWnSAXl2lzOLC9udw8U3oZkB8rLYmLbgCeXtl7UvPm',  -- bcrypt hash of 'operator123'
    'operator', 
    '{"devices": ["read", "write"], "users": ["read"], "system": ["read"]}'
);

-- 插入默认查看用户（密码：viewer123）
INSERT IGNORE INTO user_permissions (username, password_hash, role, permissions) 
VALUES (
    'viewer', 
    '$2b$12$12NUybgTl8icG66qH3.84.jQAXy53GUXIWlkbFhkHQj6DLas4i3oq',  -- bcrypt hash of 'viewer123'
    'viewer', 
    '{"devices": ["read"], "users": [], "system": []}'
);

-- 创建系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value JSON COMMENT '配置值',
    description TEXT COMMENT '配置描述',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_config_key (config_key),
    INDEX idx_is_active (is_active)
) COMMENT='系统配置表';

-- 插入默认系统配置
INSERT IGNORE INTO system_config (config_key, config_value, description) VALUES
('database.retention.status_history', '{"months": 12}', '状态历史数据保留月数'),
('database.retention.real_time_data', '{"months": 6}', '实时数据保留月数'),
('database.retention.event_records', '{"months": 24}', '事件记录保留月数'),
('system.max_concurrent_connections', '{"value": 100}', '最大并发连接数'),
('system.data_batch_size', '{"value": 100}', '数据批量处理大小'),
('system.flush_interval', '{"seconds": 5}', '数据刷新间隔（秒）');

-- 记录数据库初始化完成事件
INSERT INTO event_records (device_id, event_type, description, event_time)
VALUES ('system', 'DATABASE_INIT', 'Database initialization completed successfully', NOW());

-- 显示表创建结果
SHOW TABLES;

-- 显示表结构
DESCRIBE status_history;
DESCRIBE real_time_data;
DESCRIBE event_records;
DESCRIBE user_permissions;
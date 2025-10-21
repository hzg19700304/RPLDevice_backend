# flake8: noqa
"""
数据库配置管理器
负责数据库配置的加载、验证和管理
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置数据类"""
    host: str = "localhost"
    port: int = 3306
    database: str = "rpl_device"
    username: str = "root"
    password: str = ""
    charset: str = "utf8mb4"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    echo: bool = False
    
    # 数据保留策略
    retention_status_history: int = 12  # 状态历史数据保留月数
    retention_real_time_data: int = 6   # 实时数据保留月数
    retention_event_records: int = 24   # 事件记录保留月数
    
    # 异步处理配置
    batch_size: int = 100               # 批量处理大小
    flush_interval: float = 5.0        # 刷新间隔（秒）
    
    # 分区管理
    enable_partitioning: bool = True    # 启用分区管理
    auto_create_partitions: bool = True # 自动创建分区
    auto_drop_old_partitions: bool = True # 自动删除旧分区
    
    # 事件调度器
    enable_event_scheduler: bool = True # 启用事件调度器
    
    # 备份配置
    enable_auto_backup: bool = False    # 启用自动备份
    backup_interval: int = 24          # 备份间隔（小时）
    backup_retention: int = 7          # 备份保留天数
    backup_path: str = "./backups"     # 备份文件路径
    
    # 性能优化配置
    enable_query_cache: bool = True    # 启用查询缓存
    query_cache_size: int = 100        # 查询缓存大小（MB）
    max_connections: int = 200         # 最大连接数
    connection_timeout: int = 30       # 连接超时时间（秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password,
            "charset": self.charset,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle,
            "echo": self.echo,
            "retention_status_history": self.retention_status_history,
            "retention_real_time_data": self.retention_real_time_data,
            "retention_event_records": self.retention_event_records,
            "batch_size": self.batch_size,
            "flush_interval": self.flush_interval,
            "enable_partitioning": self.enable_partitioning,
            "auto_create_partitions": self.auto_create_partitions,
            "auto_drop_old_partitions": self.auto_drop_old_partitions,
            "enable_event_scheduler": self.enable_event_scheduler,
            "enable_auto_backup": self.enable_auto_backup,
            "backup_interval": self.backup_interval,
            "backup_retention": self.backup_retention,
            "backup_path": self.backup_path,
            "enable_query_cache": self.enable_query_cache,
            "query_cache_size": self.query_cache_size,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout
        }


class DatabaseConfigManager:
    """数据库配置管理器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self._config = DatabaseConfig()
        self._is_loaded = False
    
    def load_config(self, config_data: Optional[Dict[str, Any]] = None) -> bool:
        """加载数据库配置"""
        try:
            if config_data:
                # 从传入的配置数据加载
                self._load_from_dict(config_data)
            elif self.config_manager:
                # 从主配置管理器加载
                db_config = self.config_manager.get_database_config()
                if db_config:
                    self._load_from_dict(db_config)
            else:
                # 从环境变量加载
                self._load_from_env()
            
            # 验证配置
            if self._validate_config():
                self._is_loaded = True
                # logger.info("数据库配置加载成功")  # 调试信息已注释
                return True
            else:
                logger.error("数据库配置验证失败")
                return False
                
        except Exception as e:
            logger.error(f"加载数据库配置失败: {e}")
            return False
    
    def _load_from_dict(self, config_data: Dict[str, Any]):
        """从字典加载配置"""
        # 映射配置键名，支持新旧键名格式
        self._config.host = config_data.get("host", config_data.get("数据库地址", "localhost"))
        self._config.port = int(config_data.get("port", config_data.get("数据库端口", 3306)))
        self._config.database = config_data.get("database", config_data.get("数据库名称", "rpl_device"))
        self._config.username = config_data.get("username", config_data.get("数据库用户名", "root"))
        self._config.password = config_data.get("password", config_data.get("数据库密码", ""))
        self._config.charset = config_data.get("charset", "utf8mb4")
        self._config.pool_size = int(config_data.get("pool_size", config_data.get("连接池大小", 10)))
        self._config.max_overflow = int(config_data.get("max_overflow", config_data.get("最大溢出连接数", 20)))
        self._config.pool_recycle = int(config_data.get("pool_recycle", config_data.get("连接池回收时间", 3600)))
        self._config.echo = bool(config_data.get("echo", config_data.get("SQL调试模式", False)))
        
        # 数据保留策略
        self._config.retention_status_history = int(config_data.get("retention_status_history", config_data.get("状态历史数据保留月数", 12)))
        self._config.retention_real_time_data = int(config_data.get("retention_real_time_data", config_data.get("实时数据保留月数", 6)))
        self._config.retention_event_records = int(config_data.get("retention_event_records", config_data.get("事件记录保留月数", 24)))
        
        # 异步处理配置
        self._config.batch_size = int(config_data.get("batch_size", config_data.get("批量处理大小", 100)))
        self._config.flush_interval = float(config_data.get("flush_interval", config_data.get("刷新间隔", 5.0)))
        
        # 分区管理
        self._config.enable_partitioning = bool(config_data.get("enable_partitioning", config_data.get("启用分区管理", True)))
        self._config.auto_create_partitions = bool(config_data.get("auto_create_partitions", config_data.get("自动创建分区", True)))
        self._config.auto_drop_old_partitions = bool(config_data.get("auto_drop_old_partitions", config_data.get("自动删除旧分区", True)))
        
        # 事件调度器
        self._config.enable_event_scheduler = bool(config_data.get("enable_event_scheduler", config_data.get("启用事件调度器", True)))
        
        # 备份配置
        self._config.enable_auto_backup = bool(config_data.get("enable_auto_backup", config_data.get("启用自动备份", False)))
        self._config.backup_interval = int(config_data.get("backup_interval", config_data.get("备份间隔", 24)))
        self._config.backup_retention = int(config_data.get("backup_retention", config_data.get("备份保留天数", 7)))
        self._config.backup_path = config_data.get("backup_path", config_data.get("备份文件路径", "./backups"))
        
        # 性能优化配置
        self._config.enable_query_cache = bool(config_data.get("enable_query_cache", config_data.get("启用查询缓存", True)))
        self._config.query_cache_size = int(config_data.get("query_cache_size", config_data.get("查询缓存大小", 100)))
        self._config.max_connections = int(config_data.get("max_connections", config_data.get("最大连接数", 200)))
        self._config.connection_timeout = int(config_data.get("connection_timeout", config_data.get("连接超时时间", 30)))
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        self._config.host = os.getenv("DB_HOST", "localhost")
        self._config.port = int(os.getenv("DB_PORT", "3306"))
        self._config.database = os.getenv("DB_NAME", "rpl_device")
        self._config.username = os.getenv("DB_USER", "root")
        self._config.password = os.getenv("DB_PASSWORD", "")
        self._config.charset = os.getenv("DB_CHARSET", "utf8mb4")
        self._config.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self._config.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self._config.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self._config.echo = os.getenv("DB_ECHO", "").lower() == "true"
    
    def _validate_config(self) -> bool:
        """验证配置有效性"""
        # 检查必填字段
        if not self._config.host:
            logger.error("数据库主机地址不能为空")
            return False
        
        if not self._config.database:
            logger.error("数据库名称不能为空")
            return False
        
        if not self._config.username:
            logger.error("数据库用户名不能为空")
            return False
        
        # 检查端口范围
        if not (1 <= self._config.port <= 65535):
            logger.error(f"数据库端口号无效: {self._config.port}")
            return False
        
        # 检查连接池配置
        if self._config.pool_size <= 0:
            logger.error(f"连接池大小必须大于0: {self._config.pool_size}")
            return False
        
        if self._config.max_overflow < 0:
            logger.error(f"最大溢出连接数不能为负数: {self._config.max_overflow}")
            return False
        
        if self._config.pool_recycle <= 0:
            logger.error(f"连接回收时间必须大于0: {self._config.pool_recycle}")
            return False
        
        # logger.debug("数据库配置验证通过")  # 调试信息已注释
        return True
    
    def get_database_config(self) -> DatabaseConfig:
        """获取数据库配置"""
        if not self._is_loaded:
            logger.warning("数据库配置未加载，使用默认配置")
        return self._config
    
    def get_connection_url(self) -> str:
        """获取数据库连接URL"""
        config = self.get_database_config()
        return (
            f"mysql+pymysql://{config.username}:{config.password}@"
            f"{config.host}:{config.port}/{config.database}?charset={config.charset}"
        )
    
    def update_config(self, config_data: Dict[str, Any]) -> bool:
        """更新数据库配置"""
        try:
            old_config = self._config.to_dict()
            self._load_from_dict(config_data)
            
            if self._validate_config():
                # logger.info("数据库配置更新成功")  # 调试信息已注释
                return True
            else:
                # 验证失败，恢复旧配置
                self._load_from_dict(old_config)
                logger.error("数据库配置更新失败，配置已恢复")
                return False
                
        except Exception as e:
            logger.error(f"更新数据库配置失败: {e}")
            return False
    
    def get_config_status(self) -> Dict[str, Any]:
        """获取配置状态信息"""
        config = self.get_database_config()
        return {
            "is_loaded": self._is_loaded,
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username,
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_recycle": config.pool_recycle,
            "echo": config.echo,
            "retention_status_history": config.retention_status_history,
            "retention_real_time_data": config.retention_real_time_data,
            "retention_event_records": config.retention_event_records,
            "batch_size": config.batch_size,
            "flush_interval": config.flush_interval,
            "enable_partitioning": config.enable_partitioning,
            "auto_create_partitions": config.auto_create_partitions,
            "auto_drop_old_partitions": config.auto_drop_old_partitions,
            "enable_event_scheduler": config.enable_event_scheduler,
            "enable_auto_backup": config.enable_auto_backup,
            "backup_interval": config.backup_interval,
            "backup_retention": config.backup_retention,
            "backup_path": config.backup_path,
            "enable_query_cache": config.enable_query_cache,
            "query_cache_size": config.query_cache_size,
            "max_connections": config.max_connections,
            "connection_timeout": config.connection_timeout
        }


# 默认配置管理器实例
_default_config_manager = None


def get_default_database_config_manager() -> DatabaseConfigManager:
    """获取默认数据库配置管理器"""
    global _default_config_manager
    if _default_config_manager is None:
        _default_config_manager = DatabaseConfigManager()
    return _default_config_manager
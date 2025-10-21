"""
数据库模块
提供数据库连接、模型定义、异步数据处理等功能
"""

from .database_manager import DatabaseManager
from .models import StatusHistory, RealTimeData, EventRecords, UserPermissions, DeviceDataConverter
from .async_processor import AsyncDataProcessor
from .database_initializer import DatabaseInitializer
from .backup_manager import BackupManager
from .database_config import DatabaseConfig, DatabaseConfigManager

__all__ = [
    'DatabaseManager',
    'StatusHistory',
    'RealTimeData',
    'EventRecords',
    'UserPermissions',
    'DeviceDataConverter',
    'AsyncDataProcessor',
    'DatabaseInitializer',
    'BackupManager',
    'DatabaseConfig',
    'DatabaseConfigManager'
]

__version__ = '1.0.0'
__author__ = 'RPLDevice Team'
__description__ = 'RPLDevice数据库管理模块'
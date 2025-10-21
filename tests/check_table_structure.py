#!/usr/bin/env python3
"""检查数据库表结构"""

from database.models import RealTimeData
from sqlalchemy import inspect
from database.database_manager import DatabaseManager
from config.config_manager import ConfigManager
import asyncio

async def check_table_structure():
    # 创建配置管理器
    config_manager = ConfigManager("config/config.ini")
    
    # 创建数据库管理器
    db_manager = DatabaseManager(config_manager)
    await db_manager.initialize()
    
    # 获取表结构信息
    inspector = inspect(db_manager.engine)
    columns = inspector.get_columns('real_time_data')
    
    print('实际数据库表结构:')
    for col in columns:
        print(f'列名: {col["name"]}, 类型: {col["type"]}')
    
    await db_manager.close()

asyncio.run(check_table_structure())
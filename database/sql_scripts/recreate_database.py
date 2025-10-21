#!/usr/bin/env python3
"""
重新创建数据库表结构脚本
用于更新real_time_data表结构为通用设计
"""

import asyncio
import logging
from config.config_manager import ConfigManager
from database.database_initializer import DatabaseInitializer

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def recreate_database():
    """重新创建数据库表结构"""
    try:
        # 创建配置管理器
        config_manager = ConfigManager("config/config.ini")
        
        # 创建数据库初始化器
        initializer = DatabaseInitializer(config_manager)
        
        logger.info("开始重新初始化数据库...")
        
        # 初始化数据库（强制重新创建表结构）
        success = await initializer.initialize_database(force_recreate=True)
        
        if success:
            logger.info("数据库重新初始化成功！")
            
            # 验证表结构
            await verify_table_structure(initializer.database_manager)
        else:
            logger.error("数据库重新初始化失败！")
            
    except Exception as e:
        logger.error(f"重新创建数据库时出错: {e}")

async def verify_table_structure(database_manager):
    """验证表结构是否正确"""
    try:
        from sqlalchemy import inspect
        
        # 获取表结构信息
        inspector = inspect(database_manager.engine)
        columns = inspector.get_columns('real_time_data')
        
        logger.info("验证real_time_data表结构:")
        
        # 检查关键字段是否存在
        expected_columns = ['parameter_name', 'value', 'unit']
        actual_columns = [col['name'] for col in columns]
        
        for expected_col in expected_columns:
            if expected_col in actual_columns:
                logger.info(f"✓ 字段 '{expected_col}' 存在")
            else:
                logger.error(f"✗ 字段 '{expected_col}' 不存在")
        
        # 打印所有字段
        logger.info("当前表结构:")
        for col in columns:
            logger.info(f"  列名: {col['name']}, 类型: {col['type']}")
            
    except Exception as e:
        logger.error(f"验证表结构时出错: {e}")

if __name__ == "__main__":
    asyncio.run(recreate_database())
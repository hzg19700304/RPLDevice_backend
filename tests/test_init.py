"""
数据库初始化测试脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database_initializer import DatabaseInitializer
from config.config_manager import ConfigManager


async def test_database_initialization():
    """测试数据库初始化"""
    try:
        # 加载配置
        config_manager = ConfigManager()
        await config_manager.load_config()
        
        # 初始化数据库
        initializer = DatabaseInitializer(config_manager)
        
        print("开始数据库初始化...")
        success = await initializer.initialize_database()
        
        if success:
            print("数据库初始化成功")
        else:
            print("数据库初始化失败")
            
        # 关闭连接
        await initializer.close()
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_database_initialization())
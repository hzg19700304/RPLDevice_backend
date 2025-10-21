#!/usr/bin/env python3
"""
测试数据库初始化过程
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from database.database_initializer import DatabaseInitializer

async def test_database_initialization():
    """测试数据库初始化"""
    print("开始测试数据库初始化...")
    
    try:
        # 创建配置管理器
        config_manager = ConfigManager()
        
        # 创建数据库初始化器
        initializer = DatabaseInitializer(config_manager)
        
        # 测试数据库初始化
        print("正在初始化数据库...")
        success = await initializer.initialize_database()
        
        if success:
            print("✅ 数据库初始化成功")
            
            # 检查数据库连接状态
            if initializer.database_manager and initializer.database_manager.is_connected:
                print("✅ 数据库连接状态: 已连接")
            else:
                print("❌ 数据库连接状态: 未连接")
                
        else:
            print("❌ 数据库初始化失败")
            
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

async def test_database_connection():
    """测试数据库连接"""
    print("\n开始测试数据库连接...")
    
    try:
        # 创建配置管理器
        config_manager = ConfigManager()
        
        # 创建数据库初始化器
        initializer = DatabaseInitializer(config_manager)
        
        # 测试数据库连接
        print("正在测试数据库连接...")
        
        # 获取数据库配置
        db_config = config_manager.get_database_config()
        print(f"数据库配置: {db_config}")
        
        # 测试连接
        from database.database_manager import DatabaseManager
        db_manager = DatabaseManager(config_manager)
        
        connection_success = await db_manager.initialize()
        
        if connection_success:
            print("✅ 数据库连接测试成功")
            print(f"连接状态: {db_manager.is_connected}")
        else:
            print("❌ 数据库连接测试失败")
            
    except Exception as e:
        print(f"❌ 连接测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    print("=" * 50)
    print("数据库初始化测试")
    print("=" * 50)
    
    # 测试数据库连接
    await test_database_connection()
    
    # 测试数据库初始化
    await test_database_initialization()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
数据库连接问题诊断脚本
"""

import sys
import os
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from database.database_manager import DatabaseManager
from database.database_initializer import DatabaseInitializer

def test_config():
    """测试配置加载"""
    print("=== 测试配置加载 ===")
    try:
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()
        print(f"数据库配置: {db_config}")
        
        if db_config:
            print("✓ 配置加载成功")
            return True
        else:
            print("✗ 配置加载失败")
            return False
    except Exception as e:
        print(f"✗ 配置加载异常: {e}")
        return False

async def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试数据库连接 ===")
    try:
        config_manager = ConfigManager()
        db_manager = DatabaseManager(config_manager)
        
        success = await db_manager.initialize()
        if success:
            print("✓ 数据库连接成功")
            
            # 检查连接状态
            status = db_manager.get_database_status()
            print(f"数据库状态: {status}")
            
            # 测试简单查询
            try:
                session = db_manager.get_session()
                print("✓ 会话获取成功")
                session.close()
                
                # 测试批量插入
                from database.models import RealTimeData
                test_records = [
                    RealTimeData(device_id="TEST_001", parameter_name="test_param", value=1.0, unit="unit")
                ]
                
                result = await db_manager.batch_insert_real_time_data(test_records)
                if result:
                    print("✓ 批量插入测试成功")
                else:
                    print("✗ 批量插入测试失败")
                    
            except Exception as e:
                print(f"✗ 会话或操作测试失败: {e}")
                
            await db_manager.close()
            return True
        else:
            print("✗ 数据库连接失败")
            return False
            
    except Exception as e:
        print(f"✗ 数据库连接异常: {e}")
        return False

async def test_database_initializer():
    """测试数据库初始化器"""
    print("\n=== 测试数据库初始化器 ===")
    try:
        config_manager = ConfigManager()
        initializer = DatabaseInitializer(config_manager)
        
        success = await initializer.initialize_database()
        if success:
            print("✓ 数据库初始化成功")
            
            # 获取数据库管理器并测试
            db_manager = initializer.database_manager
            if db_manager:
                status = db_manager.get_database_status()
                print(f"初始化后数据库状态: {status}")
                
                # 测试连接
                try:
                    session = db_manager.get_session()
                    print("✓ 初始化后会话获取成功")
                    session.close()
                except Exception as e:
                    print(f"✗ 初始化后会话获取失败: {e}")
                    
            return True
        else:
            print("✗ 数据库初始化失败")
            return False
            
    except Exception as e:
        print(f"✗ 数据库初始化异常: {e}")
        return False

async def test_reconnection():
    """测试重新连接功能"""
    print("\n=== 测试重新连接功能 ===")
    try:
        config_manager = ConfigManager()
        db_manager = DatabaseManager(config_manager)
        
        # 初始化连接
        success = await db_manager.initialize()
        if not success:
            print("✗ 初始连接失败")
            return False
            
        print("✓ 初始连接成功")
        
        # 模拟连接断开
        db_manager.is_connected = False
        print("模拟连接断开，设置 is_connected = False")
        
        # 测试重新连接
        try:
            session = db_manager.get_session()
            print("✗ 预期失败但成功获取会话 - 这不应该发生")
            session.close()
        except RuntimeError as e:
            print(f"✓ 预期失败: {e}")
            
            # 测试重新连接
            print("测试重新连接...")
            reconnect_success = await db_manager._reconnect()
            if reconnect_success:
                print("✓ 重新连接成功")
                
                # 检查连接状态
                status = db_manager.get_database_status()
                print(f"重新连接后状态: {status}")
                
                # 测试重新连接后是否能正常操作
                try:
                    session = db_manager.get_session()
                    print("✓ 重新连接后会话获取成功")
                    session.close()
                    
                    # 测试批量插入
                    from database.models import RealTimeData
                    test_records = [
                        RealTimeData(device_id="TEST_RECONNECT", parameter_name="reconnect_test", value=2.0, unit="unit")
                    ]
                    
                    result = await db_manager.batch_insert_real_time_data(test_records)
                    if result:
                        print("✓ 重新连接后批量插入成功")
                    else:
                        print("✗ 重新连接后批量插入失败")
                        
                except Exception as e:
                    print(f"✗ 重新连接后操作失败: {e}")
                    
            else:
                print("✗ 重新连接失败")
                
        await db_manager.close()
        return True
            
    except Exception as e:
        print(f"✗ 重新连接测试异常: {e}")
        return False

async def main():
    """主诊断函数"""
    print("开始数据库连接问题诊断...\n")
    
    # 测试配置加载
    config_ok = test_config()
    
    # 测试数据库连接
    connection_ok = await test_database_connection()
    
    # 测试数据库初始化器
    initializer_ok = await test_database_initializer()
    
    # 测试重新连接功能
    reconnection_ok = await test_reconnection()
    
    print("\n=== 诊断结果汇总 ===")
    print(f"配置加载: {'✓ 成功' if config_ok else '✗ 失败'}")
    print(f"数据库连接: {'✓ 成功' if connection_ok else '✗ 失败'}")
    print(f"数据库初始化: {'✓ 成功' if initializer_ok else '✗ 失败'}")
    print(f"重新连接功能: {'✓ 成功' if reconnection_ok else '✗ 失败'}")
    
    if all([config_ok, connection_ok, initializer_ok, reconnection_ok]):
        print("\n✓ 所有测试通过，数据库连接正常")
    else:
        print("\n✗ 存在测试失败，请检查上述错误信息")

if __name__ == "__main__":
    asyncio.run(main())
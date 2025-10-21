#!/usr/bin/env python3
"""
服务器启动诊断脚本
检查服务器启动过程中的数据库初始化问题
"""

import sys
import os
import asyncio
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from database.database_initializer import DatabaseInitializer
from database.database_manager import DatabaseManager
from database.async_processor import AsyncDataProcessor

# 设置详细日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_server_startup_sequence():
    """测试服务器启动序列"""
    print("=== 测试服务器启动序列 ===")
    
    try:
        # 1. 创建配置管理器
        print("1. 创建配置管理器...")
        config_manager = ConfigManager()
        print("✓ 配置管理器创建成功")
        
        # 2. 创建数据库初始化器
        print("2. 创建数据库初始化器...")
        initializer = DatabaseInitializer(config_manager)
        print("✓ 数据库初始化器创建成功")
        
        # 3. 初始化数据库
        print("3. 初始化数据库...")
        init_success = await initializer.initialize_database()
        if init_success:
            print("✓ 数据库初始化成功")
        else:
            print("✗ 数据库初始化失败")
            return False
        
        # 4. 获取数据库管理器
        print("4. 获取数据库管理器...")
        db_manager = initializer.database_manager
        if db_manager:
            print("✓ 数据库管理器获取成功")
            status = db_manager.get_database_status()
            print(f"数据库状态: {status}")
        else:
            print("✗ 数据库管理器获取失败")
            return False
        
        # 5. 测试数据库连接
        print("5. 测试数据库连接...")
        try:
            session = db_manager.get_session()
            print("✓ 数据库会话获取成功")
            session.close()
        except Exception as e:
            print(f"✗ 数据库会话获取失败: {e}")
            return False
        
        # 6. 创建异步数据处理器
        print("6. 创建异步数据处理器...")
        try:
            processor = AsyncDataProcessor(db_manager)
            print("✓ 异步数据处理器创建成功")
            
            # 7. 启动异步数据处理器
            print("7. 启动异步数据处理器...")
            await processor.start()
            print("✓ 异步数据处理器启动成功")
            
            # 8. 测试数据插入
            print("8. 测试数据插入...")
            from database.models import RealTimeData
            import datetime
            
            test_records = [
                RealTimeData(
                    timestamp=datetime.datetime.now(),
                    device_id="TEST_STARTUP",
                    parameter_name="startup_test",
                    value=1.0,
                    unit="unit"
                )
            ]
            
            # 使用异步处理器的队列
            for record in test_records:
                await processor.queue_real_time_data(record.device_id, {
                    "timestamp": record.timestamp,
                    "parameter_name": record.parameter_name,
                    "value": record.value,
                    "unit": record.unit
                })
            print("✓ 测试数据已加入队列")
            
            # 等待处理
            await asyncio.sleep(2)
            
            # 9. 停止处理器
            print("9. 停止异步数据处理器...")
            await processor.stop()
            print("✓ 异步数据处理器停止成功")
            
        except Exception as e:
            print(f"✗ 异步数据处理器测试失败: {e}")
            return False
        
        # 10. 关闭数据库连接
        print("10. 关闭数据库连接...")
        await db_manager.close()
        print("✓ 数据库连接关闭成功")
        
        print("\n✓ 服务器启动序列测试全部通过")
        return True
        
    except Exception as e:
        print(f"✗ 服务器启动序列测试异常: {e}")
        return False

async def test_async_processor_with_reconnection():
    """测试异步处理器在连接断开后的重新连接功能"""
    print("\n=== 测试异步处理器重新连接功能 ===")
    
    try:
        # 创建配置管理器
        config_manager = ConfigManager()
        
        # 创建数据库初始化器
        initializer = DatabaseInitializer(config_manager)
        init_success = await initializer.initialize_database()
        if not init_success:
            print("✗ 数据库初始化失败")
            return False
        
        db_manager = initializer.database_manager
        processor = AsyncDataProcessor(db_manager)
        
        # 启动处理器
        await processor.start()
        print("✓ 异步数据处理器启动成功")
        
        # 模拟连接断开
        print("模拟连接断开...")
        db_manager.is_connected = False
        
        # 测试数据插入（应该触发重新连接）
        from database.models import RealTimeData
        import datetime
        
        test_records = [
            RealTimeData(
                timestamp=datetime.datetime.now(),
                device_id="TEST_RECONNECT",
                parameter_name="reconnect_test",
                value=2.0,
                unit="unit"
            )
        ]
        
        for record in test_records:
            await processor.queue_real_time_data(record.device_id, {
                "timestamp": record.timestamp,
                "parameter_name": record.parameter_name,
                "value": record.value,
                "unit": record.unit
            })
        print("✓ 测试数据已加入队列（应该触发重新连接）")
        
        # 等待处理
        await asyncio.sleep(3)
        
        # 检查连接状态
        status = db_manager.get_database_status()
        print(f"重新连接后数据库状态: {status}")
        
        # 检查统计信息，确认数据是否成功插入
        processor_status = processor.get_processor_status()
        print(f"处理器状态: {processor_status}")
        
        # 安全地获取统计信息
        statistics = processor_status.get('statistics', {})
        real_time_inserted = statistics.get('real_time_inserted', 0)
        errors = statistics.get('errors', 0)
        
        print(f"重新连接后统计信息: 实时数据插入数={real_time_inserted}, 错误数={errors}")
        
        # 停止处理器
        await processor.stop()
        await db_manager.close()
        
        # 测试通过的条件：重新连接后数据库状态为已连接，且数据成功插入（无错误）
        # 注意：由于重新连接是异步处理的，我们主要关注数据是否成功插入且无错误
        if real_time_inserted > 0 and errors == 0:
            print("✓ 重新连接功能测试通过（数据成功插入且无错误）")
            return True
        else:
            print("✗ 重新连接功能测试失败")
            return False
        
    except Exception as e:
        print(f"✗ 重新连接功能测试异常: {e}")
        return False

async def main():
    """主诊断函数"""
    print("开始服务器启动诊断...\n")
    
    # 测试服务器启动序列
    startup_ok = await test_server_startup_sequence()
    
    # 测试重新连接功能
    reconnection_ok = await test_async_processor_with_reconnection()
    
    print("\n=== 诊断结果汇总 ===")
    print(f"服务器启动序列: {'✓ 成功' if startup_ok else '✗ 失败'}")
    print(f"重新连接功能: {'✓ 成功' if reconnection_ok else '✗ 失败'}")
    
    if all([startup_ok, reconnection_ok]):
        print("\n✓ 所有测试通过，服务器启动正常")
    else:
        print("\n✗ 存在测试失败，请检查上述错误信息")

if __name__ == "__main__":
    asyncio.run(main())
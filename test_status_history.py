#!/usr/bin/env python3
"""测试状态历史数据查询"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.database_manager import DatabaseManager
from database.database_api import DatabaseAPI
from config.config_manager import ConfigManager

async def test_status_history():
    """测试状态历史查询功能"""
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化数据库管理器
        db_manager = DatabaseManager(config_manager)
        await db_manager.initialize()
        
        # 创建数据库API实例
        db_api = DatabaseAPI(db_manager)
        
        print("=== 状态历史查询测试 ===")
        
        # 测试查询
        from datetime import datetime
        result = await db_api.get_status_history(
            start_time=datetime.fromisoformat('2025-10-16T00:00:00'),
            end_time=datetime.fromisoformat('2025-10-20T23:59:59'),
            limit=10,
            offset=0
        )
        
        print(f"状态历史记录总数: {len(result)}")
        print(f"当前页记录数: {len(result)}")
        
        if result:
            print("\n第一条记录:")
            record = result[0]
            for key, value in record.items():
                print(f"  {key}: {value}")
        else:
            print("\n数据库中没有状态历史记录")
        
        await db_manager.close()
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_status_history())
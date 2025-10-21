#!/usr/bin/env python3
"""生成状态历史测试数据"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.database_manager import DatabaseManager
from database.database_api import DatabaseAPI
from database.models import StatusHistory
from config.config_manager import ConfigManager
from sqlalchemy import select, func

async def generate_test_data():
    """生成状态历史测试数据"""
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化数据库管理器
        db_manager = DatabaseManager(config_manager)
        await db_manager.initialize()
        
        print("=== 生成状态历史测试数据 ===")
        
        # 检查现有数据
        session = db_manager.get_session()
        try:
            count = session.execute(select(func.count(StatusHistory.id))).scalar()
            print(f"当前状态历史记录数: {count}")
            
            if count > 0:
                print("数据库中已有状态历史数据，跳过生成")
                return
        finally:
            session.close()
        
        # 状态类型和名称映射
        status_configs = {
            'FaultStatus': [
                '过压故障', '欠压故障', '过流故障', '短路故障', 
                '过热故障', '绝缘故障', '接地故障', '断线故障'
            ],
            'WorkStatus': [
                '运行状态', '待机状态', '工作模式', '控制模式',
                '手动模式', '自动模式', '远程控制', '本地控制'
            ],
            'ProtectStatus': [
                '过压保护', '欠压保护', '过流保护', '短路保护',
                '过热保护', '绝缘保护', '接地保护', '防雷保护'
            ]
        }
        
        # 设备ID列表
        device_ids = ['RPL001', 'RPL002', 'RPL003']
        
        # 生成最近30天的数据
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        
        test_records = []
        
        # 生成100条测试记录
        for i in range(100):
            # 随机选择配置
            status_type = random.choice(list(status_configs.keys()))
            status_name = random.choice(status_configs[status_type])
            device_id = random.choice(device_ids)
            
            # 随机时间（在最近30天内）
            time_offset = random.randint(0, int((end_time - start_time).total_seconds()))
            timestamp = start_time + timedelta(seconds=time_offset)
            
            # 生成状态变化记录
            old_value = random.randint(0, 1)
            new_value = 1 - old_value  # 确保状态有变化
            
            record = StatusHistory(
                timestamp=timestamp,
                status_type=status_type,
                bit_position=random.randint(0, 15),
                old_value=old_value,
                new_value=new_value,
                status_name=status_name,
                device_id=device_id,
                upload_status=random.randint(0, 2)
            )
            
            test_records.append(record)
        
        # 按时间排序
        test_records.sort(key=lambda x: x.timestamp)
        
        # 批量插入数据
        session = db_manager.get_session()
        try:
            session.add_all(test_records)
            session.commit()
            print(f"成功生成 {len(test_records)} 条状态历史测试数据")
        except Exception as e:
            session.rollback()
            print(f"插入数据失败: {e}")
            raise
        finally:
            session.close()
        
        # 验证数据
        session = db_manager.get_session()
        try:
            count = session.execute(select(func.count(StatusHistory.id))).scalar()
            print(f"当前状态历史记录总数: {count}")
            
            # 显示每种状态类型的数量
            for status_type in status_configs.keys():
                type_count = session.execute(
                    select(func.count(StatusHistory.id)).where(StatusHistory.status_type == status_type)
                ).scalar()
                print(f"{status_type}: {type_count} 条")
        finally:
            session.close()
        
        await db_manager.close()
        print("测试数据生成完成！")
        
    except Exception as e:
        print(f"生成测试数据失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(generate_test_data())
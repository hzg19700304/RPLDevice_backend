#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database_manager import DatabaseManager
from database.database_api import DatabaseAPI
from config.config_manager import ConfigManager
from datetime import datetime
from sqlalchemy import select, func, desc
from database.models import RealTimeData

async def test_database():
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    # 初始化数据库管理器
    db_manager = DatabaseManager(config_manager)
    await db_manager.initialize()
    
    # 初始化数据库API
    db_api = DatabaseAPI(db_manager)
    
    start_time = datetime(2025, 10, 23, 0, 0, 0)
    end_time = datetime(2025, 10, 23, 13, 15, 0)
    param_name = '轨地电流SA1'
    
    print(f"正在查询数据库...")
    print(f"参数: {param_name}")
    print(f"时间范围: {start_time} 至 {end_time}")
    
    # 使用API查询无限制数据
    records = await db_api.get_real_time_data_unlimited(
        parameter_name=param_name,
        start_time=start_time,
        end_time=end_time
    )
    
    print(f"查询返回数据量: {len(records)}")
    
    if records:
        print(f"首条数据时间: {records[0].get('timestamp', 'N/A')}")
        print(f"末条数据时间: {records[-1].get('timestamp', 'N/A')}")
        
        # 检查时间间隔
        timestamps = []
        for record in records:
            ts_str = record.get('timestamp', '')
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    timestamps.append(ts)
                except:
                    pass
        
        if len(timestamps) > 1:
            intervals = []
            for i in range(len(timestamps)-1):
                interval = abs((timestamps[i+1] - timestamps[i]).total_seconds())
                intervals.append(interval)
            
            print(f"平均时间间隔: {sum(intervals)/len(intervals):.1f}秒")
            print(f"最小时间间隔: {min(intervals):.1f}秒")
            print(f"最大时间间隔: {max(intervals):.1f}秒")
            
            # 检查数据完整性
            expected_points = (13 * 3600 + 15 * 60)  # 13小时15分钟，每秒一个点
            print(f"期望数据点数: {expected_points}")
            print(f"实际数据点数: {len(records)}")
            print(f"数据完整性: {len(records)/expected_points*100:.1f}%")
    
    # 直接查询数据库统计
    session = db_manager.get_session()
    try:
        total_query = select(func.count(RealTimeData.id)).where(
            RealTimeData.parameter_name == param_name,
            RealTimeData.timestamp >= start_time,
            RealTimeData.timestamp <= end_time
        )
        total_count = session.execute(total_query).scalar()
        print(f"数据库中总数据量: {total_count}")
        
        # 查询时间范围
        time_query = select(
            func.min(RealTimeData.timestamp),
            func.max(RealTimeData.timestamp)
        ).where(
            RealTimeData.parameter_name == param_name
        )
        min_time, max_time = session.execute(time_query).first()
        print(f"数据库中该参数的时间范围: {min_time} 至 {max_time}")
        
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_database())
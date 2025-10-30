#!/usr/bin/env python3
"""
测试故障录波数据解析功能
验证新的数据格式：系统状态 + 3个模拟量（SA1, SA2, SV1）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket.message_handler import MessageHandler
from config.config_manager import ConfigManager

def test_fault_record_parsing():
    """测试故障录波数据解析"""
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建消息处理器
    handler = MessageHandler(None, config_manager)
    
    # 模拟故障录波数据（包含7个寄存器头部 + 数据点）
    # 格式：故障信息头（7个寄存器）+ 系统状态 + SA1 + SA2 + SV1
    test_registers = [
        # 故障信息头（7个寄存器）
        0x08F0,  # 故障发生时刻_故障信息
        0x0073,  # 故障发生时刻_毫秒
        0x0100,  # 故障发生时时刻_秒分
        0x0001,  # 故障发生时时刻_时日
        0x0100,  # 故障发生时时刻_月年
        0x0096,  # 故障点位置
        0x000A,  # 故障录波周期
        
        # 数据点1（4个寄存器）
        0xA051,  # 系统状态
        0x8000,  # SA1
        0x0000,  # SA2  
        0x0000,  # SV1
        
        # 数据点2（4个寄存器）
        0xA052,  # 系统状态
        0x8100,  # SA1
        0x0100,  # SA2
        0x0200,  # SV1
    ]
    
    # 测试解析2个数据点
    result = handler._parse_fault_record_data(
        registers=test_registers,
        data_points_count=2,
        registers_per_point=4
    )
    
    print("解析结果:")
    print(f"故障信息:")
    print(f"  故障时间: {result['fault_info']['fault_time']}")
    print(f"  故障位: {result['fault_info']['fault_bits']}")
    print(f"  故障点: {result['fault_info']['fault_point']}")
    print(f"  录波周期: {result['fault_info']['record_cycle']}ms")
    print(f"数据点数量: {len(result['data_points'])}")
    print(f"数据点:")
    
    for point in result['data_points']:
        print(f"  数据点 {point['point_index']}:")
        print(f"    系统状态: {point['system_status']}")
        print(f"    SA1 (通道1): {point['channel1_sa1']} (0x{point['channel1_sa1']:04X})")
        print(f"    SA2 (通道2): {point['channel2_sa2']} (0x{point['channel2_sa2']:04X})")
        print(f"    SV1 (通道3): {point['channel3_sv1']} (0x{point['channel3_sv1']:04X})")
    
    # 验证解析结果
    assert len(result['data_points']) == 2
    
    # 验证故障信息
    assert result['fault_info']['fault_bits'] == '0x08F0'  # 修正为实际值
    assert result['fault_info']['fault_point'] == 0x0096
    assert result['fault_info']['record_cycle'] == 0x000A
    
    # 验证第一个数据点
    point1 = result['data_points'][0]
    assert point1['system_status'] == '0xA051'
    assert point1['channel1_sa1'] == 0x8000
    assert point1['channel2_sa2'] == 0x0000
    assert point1['channel3_sv1'] == 0x0000
    
    # 验证第二个数据点
    point2 = result['data_points'][1]
    assert point2['system_status'] == '0xA052'
    assert point2['channel1_sa1'] == 0x8100
    assert point2['channel2_sa2'] == 0x0100
    assert point2['channel3_sv1'] == 0x0200
    
    print("\n✅ 所有测试通过!")

if __name__ == "__main__":
    test_fault_record_parsing()
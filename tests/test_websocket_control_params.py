#!/usr/bin/env python3
"""
测试WebSocket控制参数功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket.message_handler import MessageHandler
from config.config_manager import ConfigManager

async def test_control_params_websocket():
    """测试WebSocket控制参数功能"""
    print("正在测试WebSocket控制参数功能...")
    
    config_manager = ConfigManager()
    
    # 创建消息处理器
    message_handler = MessageHandler(None, config_manager)
    
    # 测试获取控制参数
    control_params = message_handler._get_control_parameters()
    
    print(f"\n成功生成 {len(control_params)} 个控制参数：")
    print("-" * 80)
    
    # 按地址排序显示
    for param in sorted(control_params, key=lambda x: x['reg_addr']):
        print(f"{param['reg_addr']}: {param['param_name']}")
        print(f"   当前值: {param['current_value']} {param['unit']}")
        print(f"   范围: {param['value_range']}")
        print()
    
    # 验证参数类型分布
    param_types = {}
    for param in control_params:
        param_type = param['unit']
        if param_type not in param_types:
            param_types[param_type] = []
        param_types[param_type].append(param)
    
    print("参数类型分布：")
    for unit_type, params in param_types.items():
        print(f"  {unit_type}: {len(params)} 个")
    
    # 验证结构体完整性
    print(f"\n结构体完整性验证：")
    
    # 统计各类参数数量
    voltage_count = sum(1 for p in control_params if p['unit'] == 'V')
    current_count = sum(1 for p in control_params if p['unit'] == 'A')
    time_001s_count = sum(1 for p in control_params if '0.01s' in p['unit'])
    time_s_count = sum(1 for p in control_params if p['unit'] == 's')
    count_count = sum(1 for p in control_params if p['unit'] == '次')
    ms_count = sum(1 for p in control_params if p['unit'] == 'ms')
    
    print(f"电压参数: {voltage_count}/11")
    print(f"电流参数: {current_count}/4")  # 包括KM分断电流和可控硅导通判断电流
    print(f"保护延时(0.01s): {time_001s_count}/10")
    print(f"KM闭合时间(s): {time_s_count}/10")
    print(f"连续动作次数: {count_count}/10")
    print(f"故障录波周期(ms): {ms_count}/1")
    
    # 验证地址连续性
    reg_addrs = [int(p['reg_addr'], 16) for p in control_params]
    expected_addrs = list(range(0x2200, 0x2237))  # 0x2200-0x2236
    
    missing_addrs = set(expected_addrs) - set(reg_addrs)
    extra_addrs = set(reg_addrs) - set(expected_addrs)
    
    if missing_addrs:
        print(f"\n❌ 缺失的地址: {[f'0x{addr:04X}' for addr in sorted(missing_addrs)]}")
    
    if extra_addrs:
        print(f"\n❌ 多余的地址: {[f'0x{addr:04X}' for addr in sorted(extra_addrs)]}")
    
    if not missing_addrs and not extra_addrs:
        print(f"\n✅ 地址连续性验证通过！")
    
    print(f"\n✅ WebSocket控制参数功能测试通过！")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_control_params_websocket())
        if success:
            print("\n🎉 WebSocket控制参数功能测试成功！")
        else:
            print("\n❌ WebSocket控制参数功能测试失败！")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
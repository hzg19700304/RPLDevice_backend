#!/usr/bin/env python3
"""
综合测试 - 验证系统控制参数配置完整性
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from websocket.message_handler import MessageHandler

def test_config_completeness():
    """测试配置完整性"""
    print("🧪 开始系统控制参数配置完整性测试...")
    
    config_manager = ConfigManager()
    
    # 1. 测试配置管理器
    print("\n📋 1. 配置管理器测试")
    control_mapping = config_manager.get_control_parameters_mapping()
    print(f"   ✅ 成功加载 {len(control_mapping)} 个控制参数")
    
    # 2. 验证结构体映射
    print("\n🔍 2. 结构体映射验证")
    
    # 根据结构体 SYS_PARAM_CONFIG_REGS 验证
    expected_structure = {
        'OVPD_Voltage': 11,      # 1-11段电压保护值
        'Delay_Ta': 10,          # 1-10段保护延时动作时间
        'Delay_Tb': 10,          # 1-10段KM闭合延续时间
        'Delay_Tc': 10,          # 1-10段连续动作时间
        'KMON_N': 10,            # 1-10段连续动作次数
        'KmOffCur': 1,           # KM分断电流设置值
        'Cur_SCRisON': 1,        # 可控硅导通判断电流值
        'ErrSv': 1,              # SV1与SV2允许偏差值
        'RecordPeriod': 1         # 故障录波周期
    }
    
    actual_counts = {
        'OVPD_Voltage': sum(1 for name in control_mapping.values() if '电压保护值' in name),
        'Delay_Ta': sum(1 for name in control_mapping.values() if '保护延时' in name and '0.01s' in name),
        'Delay_Tb': sum(1 for name in control_mapping.values() if 'KM闭合时间' in name),
        'Delay_Tc': sum(1 for name in control_mapping.values() if '连续动作时间' in name and 's' in name and 'KM' not in name),
        'KMON_N': sum(1 for name in control_mapping.values() if '连续动作次数' in name),
        'KmOffCur': sum(1 for name in control_mapping.values() if 'KM分断电流' in name),
        'Cur_SCRisON': sum(1 for name in control_mapping.values() if '可控硅导通判断电流' in name),
        'ErrSv': sum(1 for name in control_mapping.values() if '允许偏差值' in name),
        'RecordPeriod': sum(1 for name in control_mapping.values() if '故障录波周期' in name)
    }
    
    all_passed = True
    for struct_name, expected_count in expected_structure.items():
        actual_count = actual_counts[struct_name]
        if actual_count == expected_count:
            print(f"   ✅ {struct_name}: {actual_count}/{expected_count}")
        else:
            print(f"   ❌ {struct_name}: {actual_count}/{expected_count}")
            all_passed = False
    
    # 3. 地址范围验证
    print("\n📍 3. 地址范围验证")
    addresses = [int(addr, 16) for addr in control_mapping.keys()]
    min_addr = min(addresses)
    max_addr = max(addresses)
    expected_min = 0x2200
    expected_max = 0x2236
    
    if min_addr == expected_min and max_addr == expected_max:
        print(f"   ✅ 地址范围: 0x{min_addr:04X} - 0x{max_addr:04X}")
    else:
        print(f"   ❌ 地址范围: 0x{min_addr:04X} - 0x{max_addr:04X} (期望: 0x{expected_min:04X} - 0x{expected_max:04X})")
        all_passed = False
    
    # 4. 测试WebSocket消息处理器
    print("\n🌐 4. WebSocket消息处理器测试")
    try:
        message_handler = MessageHandler(None, config_manager)
        control_params = message_handler._get_control_parameters()
        print(f"   ✅ WebSocket成功生成 {len(control_params)} 个控制参数")
        
        # 验证WebSocket生成的参数与配置一致
        if len(control_params) == len(control_mapping):
            print(f"   ✅ 参数数量一致")
        else:
            print(f"   ❌ 参数数量不一致: WebSocket({len(control_params)}) vs 配置({len(control_mapping)})")
            all_passed = False
            
    except Exception as e:
        print(f"   ❌ WebSocket测试失败: {e}")
        all_passed = False
    
    # 5. 单位类型验证
    print("\n📏 5. 单位类型验证")
    unit_types = {}
    for param_name in control_mapping.values():
        if '电压保护值' in param_name:
            unit = 'V'
        elif '允许偏差值' in param_name:
            unit = 'V'
        elif 'KM分断电流' in param_name or '可控硅导通判断电流' in param_name:
            unit = 'A'
        elif '保护延时' in param_name:
            unit = '0.01s'
        elif 'KM闭合时间' in param_name or '连续动作时间' in param_name:
            unit = 's'
        elif '连续动作次数' in param_name:
            unit = '次'
        elif '故障录波周期' in param_name:
            unit = 'ms'
        else:
            unit = '其他'
        
        unit_types[unit] = unit_types.get(unit, 0) + 1
    
    expected_units = {
        'V': 12,      # 11个电压保护值 + 1个偏差值
        'A': 2,       # KM分断电流 + 可控硅导通判断电流
        '0.01s': 10,  # 10个保护延时
        's': 20,      # 10个KM闭合时间 + 10个连续动作时间
        '次': 10,     # 10个连续动作次数
        'ms': 1       # 1个故障录波周期
    }
    
    for unit, expected_count in expected_units.items():
        actual_count = unit_types.get(unit, 0)
        if actual_count == expected_count:
            print(f"   ✅ {unit}: {actual_count}")
        else:
            print(f"   ❌ {unit}: {actual_count} (期望: {expected_count})")
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_config_completeness()
        
        if success:
            print("\n🎉 系统控制参数配置完整性测试通过！")
            print("\n📊 总结:")
            print("   • 配置文件已正确更新为结构体 SYS_PARAM_CONFIG_REGS 格式")
            print("   • 地址范围: 0x2200 - 0x2236 (共55个参数)")
            print("   • WebSocket消息处理器已适配新配置")
            print("   • 所有参数类型和单位验证通过")
        else:
            print("\n❌ 系统控制参数配置完整性测试失败！")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
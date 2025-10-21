#!/usr/bin/env python3
"""
测试系统控制参数配置
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager

def test_control_parameters():
    """测试控制参数配置"""
    print("正在测试HMI系统控制参数配置...")
    
    config_manager = ConfigManager()
    
    # 获取控制参数映射
    control_mapping = config_manager.get_control_parameters_mapping()
    
    print(f"\n成功加载 {len(control_mapping)} 个控制参数：")
    print("-" * 80)
    
    # 按地址排序显示
    for reg_addr, param_name in sorted(control_mapping.items()):
        print(f"{reg_addr} = {param_name}")
    
    # 验证关键参数
    expected_params = [
        ('0x2200', '1段电压保护值（V）'),
        ('0x220A', '11段电压保护值（V）'),
        ('0x220B', '1段保护延时（0.01s）'),
        ('0x2214', '10段保护延时（0.01s）'),
        ('0x2215', '1段KM闭合时间（s）'),
        ('0x221E', '10段KM闭合时间（s）'),
        ('0x221F', '1段连续动作时间（s）'),
        ('0x2228', '10段连续动作时间（s）'),
        ('0x2229', '1段连续动作次数（次）'),
        ('0x2232', '10段连续动作次数（次）'),
        ('0x2233', 'KM分断电流设置值（A）'),
        ('0x2234', '可控硅导通判断电流值（A）'),
        ('0x2235', 'SV1与SV2允许偏差值（V）'),
        ('0x2236', '故障录波周期（ms）')
    ]
    
    print("\n验证关键参数：")
    all_passed = True
    
    for reg_addr, expected_name in expected_params:
        actual_name = control_mapping.get(reg_addr)
        if actual_name == expected_name:
            print(f"✅ {reg_addr}: {actual_name}")
        else:
            print(f"❌ {reg_addr}: 期望 '{expected_name}', 实际 '{actual_name}'")
            all_passed = False
    
    # 检查地址范围
    print(f"\n地址范围检查：")
    addresses = [int(addr, 16) for addr in control_mapping.keys()]
    min_addr = min(addresses)
    max_addr = max(addresses)
    print(f"最小地址: 0x{min_addr:04X} ({min_addr})")
    print(f"最大地址: 0x{max_addr:04X} ({max_addr})")
    print(f"地址数量: {len(control_mapping)}")
    
    # 检查结构体完整性
    print(f"\n结构体完整性检查：")
    # OVPD_Voltage[11] - 11个电压保护值
    voltage_count = sum(1 for addr in control_mapping.keys() if '电压保护值' in control_mapping[addr])
    print(f"电压保护值数量: {voltage_count}/11")
    
    # Delay_Ta[10] - 10个保护延时
    delay_ta_count = sum(1 for addr in control_mapping.keys() if '保护延时' in control_mapping[addr])
    print(f"保护延时数量: {delay_ta_count}/10")
    
    # Delay_Tb[10] - 10个KM闭合时间
    delay_tb_count = sum(1 for addr in control_mapping.keys() if 'KM闭合时间' in control_mapping[addr])
    print(f"KM闭合时间数量: {delay_tb_count}/10")
    
    # Delay_Tc[10] - 10个连续动作时间
    delay_tc_count = sum(1 for addr in control_mapping.keys() if '连续动作时间' in control_mapping[addr])
    print(f"连续动作时间数量: {delay_tc_count}/10")
    
    # KMON_N[10] - 10个连续动作次数
    kmon_n_count = sum(1 for addr in control_mapping.keys() if '连续动作次数' in control_mapping[addr])
    print(f"连续动作次数数量: {kmon_n_count}/10")
    
    # 其他参数
    other_params = ['KM分断电流设置值', '可控硅导通判断电流值', 'SV1与SV2允许偏差值', '故障录波周期']
    other_count = sum(1 for name in control_mapping.values() if any(param in name for param in other_params))
    print(f"其他参数数量: {other_count}/4")
    
    if all_passed:
        print("\n✅ 所有关键参数验证通过！")
        return True
    else:
        print("\n❌ 部分参数验证失败！")
        return False

if __name__ == "__main__":
    try:
        success = test_control_parameters()
        if success:
            print("\n🎉 HMI系统控制参数配置测试成功！")
        else:
            print("\n❌ HMI系统控制参数配置测试失败！")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
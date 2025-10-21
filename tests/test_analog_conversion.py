#!/usr/bin/env python3
"""
测试模拟量数据转换功能
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_comm.serial_manager import SerialManager
from config.config_manager import ConfigManager

def test_analog_conversion():
    """测试模拟量数据转换"""
    print("正在测试模拟量数据转换功能...")
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建SerialManager实例
    serial_manager = SerialManager(config_manager)
    
    # 创建模拟数据 - 包含负值测试
    from serial_comm.serial_manager import DeviceData
    
    device_data = DeviceData(
        analog_registers=[65530, 100, 200, 300, 400, 500, 600, 700],  # 65530 = -6 (负值测试)
        status_registers=[],
        coils=[],
        discrete_inputs=[],
        timestamp=time.time()
    )
    
    # 测试模拟量转换
    analog_data = serial_manager._convert_analog_data(device_data)
    
    print("\n模拟量数据转换测试结果：")
    print("-" * 60)
    
    for i, data in enumerate(analog_data, 1):
        print(f"{i}. {data['name']}:")
        print(f"   寄存器地址: {data['reg_addr']}")
        print(f"   原始值: {data['raw_value']}")
        print(f"   有符号值: {data['signed_value']}")
        print(f"   物理值: {data['physical_value']} {data['unit']}")
        print()
    
    # 验证负值转换是否正确
    max_potential = analog_data[0]  # 最大极化电位
    if max_potential['signed_value'] == -6 and max_potential['physical_value'] == -0.6:
        print("✅ 负值转换测试通过！")
    else:
        print(f"❌ 负值转换测试失败：期望 signed_value=-6, physical_value=-0.6")
        print(f"   实际 signed_value={max_potential['signed_value']}, physical_value={max_potential['physical_value']}")
    
    return analog_data

if __name__ == "__main__":
    try:
        analog_data = test_analog_conversion()
        print("\n✅ 模拟量数据转换测试通过！配置分离成功。")
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
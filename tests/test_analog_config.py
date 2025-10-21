#!/usr/bin/env python3
"""
测试模拟量参数配置加载
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager

def test_analog_config():
    """测试模拟量参数配置"""
    print("正在测试模拟量参数配置加载...")
    
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    # 获取模拟量参数映射
    analog_mapping = config_manager.get_analog_parameters_mapping()
    
    print("\n从配置文件加载的模拟量参数映射：")
    print("-" * 60)
    
    for i, mapping in enumerate(analog_mapping, 1):
        print(f"{i}. 寄存器地址: {mapping['reg_addr']}")
        print(f"   参数名称: {mapping['name']}")
        print(f"   单位: {mapping['unit']}")
        print(f"   转换系数: {mapping['scale']}")
        print()
    
    print(f"总计：{len(analog_mapping)} 个参数")
    
    # 验证配置完整性
    expected_params = 8
    if len(analog_mapping) == expected_params:
        print(f"✅ 配置加载成功，包含所有 {expected_params} 个参数")
    else:
        print(f"❌ 配置加载异常，期望 {expected_params} 个参数，实际 {len(analog_mapping)} 个")
    
    return analog_mapping

if __name__ == "__main__":
    try:
        analog_mapping = test_analog_config()
        print("\n✅ 测试通过！模拟量参数配置已成功分离到配置文件中。")
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        sys.exit(1)
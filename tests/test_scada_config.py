#!/usr/bin/env python3
"""
SCADA配置验证测试
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager

def test_scada_config():
    """测试SCADA配置"""
    print("🧪 开始SCADA配置验证测试...")
    
    config_manager = ConfigManager()
    
    # 1. 测试SCADA遥信配置
    print("\n📋 1. SCADA遥信配置测试")
    try:
        scada_teleindication = config_manager.get_section("SCADA遥信配置")
        if scada_teleindication:
            print(f"   ✅ 成功加载 {len(scada_teleindication)} 个SCADA遥信信号")
            
            # 验证关键信号
            key_signals = [
                "0x0000_bit0", "0x0000_bit1", "0x0000_bit2",  # 系统状态
                "0x0001_bit0", "0x0001_bit1", "0x0001_bit2", "0x0001_bit3",  # 输入状态
                "0x0002_bit0", "0x0002_bit1", "0x0002_bit2",  # 输出状态
                "0x0003_bit0", "0x0003_bit1", "0x0003_bit10", "0x0003_bit11", "0x0003_bit12", "0x0003_bit13"  # 故障状态
            ]
            
            for signal in key_signals:
                if signal in scada_teleindication:
                    print(f"   ✅ {signal}: {scada_teleindication[signal]}")
                else:
                    print(f"   ❌ {signal}: 未找到")
        else:
            print("   ❌ 未找到SCADA遥信配置")
    except Exception as e:
        print(f"   ❌ SCADA遥信配置测试失败: {e}")
    
    # 2. 测试SCADA遥测配置
    print("\n📊 2. SCADA遥测配置测试")
    try:
        scada_telemetry = config_manager.get_section("SCADA遥测配置")
        if scada_telemetry:
            print(f"   ✅ 成功加载 {len(scada_telemetry)} 个SCADA遥测信号")
            
            expected_signals = ["0x0006", "0x0007", "0x0008", "0x0009"]
            for signal in expected_signals:
                if signal in scada_telemetry:
                    print(f"   ✅ {signal}: {scada_telemetry[signal]}")
                else:
                    print(f"   ❌ {signal}: 未找到")
        else:
            print("   ❌ 未找到SCADA遥测配置")
    except Exception as e:
        print(f"   ❌ SCADA遥测配置测试失败: {e}")
    
    # 3. 测试SCADA遥控配置
    print("\n🎮 3. SCADA遥控配置测试")
    try:
        scada_telecontrol = config_manager.get_section("SCADA遥控配置")
        if scada_telecontrol:
            print(f"   ✅ 成功加载 {len(scada_telecontrol)} 个SCADA遥控信号")
            
            if "0x0101" in scada_telecontrol:
                print(f"   ✅ 0x0101: {scada_telecontrol['0x0101']}")
            else:
                print("   ❌ 0x0101: 未找到")
        else:
            print("   ❌ 未找到SCADA遥控配置")
    except Exception as e:
        print(f"   ❌ SCADA遥控配置测试失败: {e}")
    
    # 4. 测试SCADA定值配置
    print("\n⚙️ 4. SCADA定值配置测试")
    try:
        scada_settings = config_manager.get_section("SCADA定值配置")
        if scada_settings:
            print(f"   ✅ 成功加载 {len(scada_settings)} 个SCADA定值参数")
            
            # 验证电压保护定值
            voltage_settings = ["0x2200", "0x2202", "0x2204", "0x2206", "0x2208", "0x220A", "0x220C", "0x220E", "0x2210", "0x2212"]
            for setting in voltage_settings:
                if setting in scada_settings:
                    print(f"   ✅ {setting}: {scada_settings[setting]}")
                else:
                    print(f"   ❌ {setting}: 未找到")
            
            # 验证时间定值
            time_settings = ["0x2201", "0x2203", "0x2205", "0x2207", "0x2209", "0x220B", "0x220D", "0x220F", "0x2211", "0x2213"]
            for setting in time_settings:
                if setting in scada_settings:
                    print(f"   ✅ {setting}: {scada_settings[setting]}")
                else:
                    print(f"   ❌ {setting}: 未找到")
        else:
            print("   ❌ 未找到SCADA定值配置")
    except Exception as e:
        print(f"   ❌ SCADA定值配置测试失败: {e}")
    
    # 5. 测试SCADA系统时间配置
    print("\n⏰ 5. SCADA系统时间配置测试")
    try:
        scada_time = config_manager.get_section("SCADA系统时间配置")
        if scada_time:
            print(f"   ✅ 成功加载 {len(scada_time)} 个SCADA时间参数")
            
            time_params = ["0x3000", "0x3001", "0x3002", "0x3003"]
            for param in time_params:
                if param in scada_time:
                    print(f"   ✅ {param}: {scada_time[param]}")
                else:
                    print(f"   ❌ {param}: 未找到")
        else:
            print("   ❌ 未找到SCADA系统时间配置")
    except Exception as e:
        print(f"   ❌ SCADA系统时间配置测试失败: {e}")
    
    print("\n🎉 SCADA配置验证测试完成！")

if __name__ == "__main__":
    try:
        test_scada_config()
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
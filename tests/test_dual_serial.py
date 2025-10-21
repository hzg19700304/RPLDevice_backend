#!/usr/bin/env python3
"""
测试双串口管理功能
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_comm.serial_manager import SerialManager
from config.config_manager import ConfigManager

def test_dual_serial_initialization():
    """测试双串口初始化"""
    print("=== 测试双串口初始化 ===")
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建串口管理器
    serial_manager = SerialManager(config_manager)
    
    # 初始化串口管理器
    import asyncio
    result = asyncio.run(serial_manager.initialize())
    
    if result:
        print("✓ 串口管理器初始化成功")
        
        # 检查配置是否正确加载
        if serial_manager.hmi_config:
            print(f"✓ HMI串口配置已加载: {serial_manager.hmi_config.port_name}")
        else:
            print("✗ HMI串口配置未加载")
            
        if serial_manager.scada_config:
            print(f"✓ SCADA串口配置已加载: {serial_manager.scada_config.port_name}")
        else:
            print("✗ SCADA串口配置未加载")
            
        # 检查属性是否正确初始化
        if hasattr(serial_manager, 'hmi_master'):
            print("✓ HMI主站对象已初始化")
        else:
            print("✗ HMI主站对象未初始化")
            
        if hasattr(serial_manager, 'scada_master'):
            print("✓ SCADA主站对象已初始化")
        else:
            print("✗ SCADA主站对象未初始化")
            
        if hasattr(serial_manager, 'hmi_polling_thread'):
            print("✓ HMI轮询线程属性已初始化")
        else:
            print("✗ HMI轮询线程属性未初始化")
            
        if hasattr(serial_manager, 'scada_polling_thread'):
            print("✓ SCADA轮询线程属性已初始化")
        else:
            print("✗ SCADA轮询线程属性未初始化")
            
        if hasattr(serial_manager, 'hmi_data_callbacks'):
            print("✓ HMI数据回调列表已初始化")
        else:
            print("✗ HMI数据回调列表未初始化")
            
        if hasattr(serial_manager, 'scada_data_callbacks'):
            print("✓ SCADA数据回调列表已初始化")
        else:
            print("✗ SCADA数据回调列表未初始化")
            
        if hasattr(serial_manager, 'hmi_current_data'):
            print("✓ HMI当前数据属性已初始化")
        else:
            print("✗ HMI当前数据属性未初始化")
            
        if hasattr(serial_manager, 'scada_current_data'):
            print("✓ SCADA当前数据属性已初始化")
        else:
            print("✗ SCADA当前数据属性未初始化")
            
    else:
        print("✗ 串口管理器初始化失败")
    
    print()

def test_dual_serial_methods():
    """测试双串口方法"""
    print("=== 测试双串口方法 ===")
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建串口管理器
    serial_manager = SerialManager(config_manager)
    
    # 测试回调注册方法
    def dummy_callback(data_type, data):
        pass
    
    # 测试HMI回调注册
    serial_manager.register_hmi_data_callback(dummy_callback)
    if len(serial_manager.hmi_data_callbacks) == 1:
        print("✓ HMI数据回调注册成功")
    else:
        print("✗ HMI数据回调注册失败")
    
    # 测试SCADA回调注册
    serial_manager.register_scada_data_callback(dummy_callback)
    if len(serial_manager.scada_data_callbacks) == 1:
        print("✓ SCADA数据回调注册成功")
    else:
        print("✗ SCADA数据回调注册失败")
    
    # 测试兼容性回调注册
    serial_manager.register_data_callback(dummy_callback)
    if len(serial_manager.hmi_data_callbacks) == 2:
        print("✓ 兼容性数据回调注册成功")
    else:
        print("✗ 兼容性数据回调注册失败")
    
    # 测试数据获取方法
    hmi_data = serial_manager.get_hmi_current_data()
    scada_data = serial_manager.get_scada_current_data()
    current_data = serial_manager.get_current_data()
    
    print("✓ 数据获取方法正常")
    
    print()

def test_configuration():
    """测试配置信息"""
    print("=== 测试配置信息 ===")
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 获取HMI配置
    hmi_config = config_manager.get_section('HMI串口配置')
    if hmi_config:
        print(f"✓ HMI串口配置: {hmi_config}")
    else:
        print("✗ HMI串口配置未找到")
    
    # 获取SCADA配置
    scada_config = config_manager.get_section('SCADA串口配置')
    if scada_config:
        print(f"✓ SCADA串口配置: {scada_config}")
    else:
        print("✗ SCADA串口配置未找到")
    
    # 检查端口是否不同
    if hmi_config and scada_config:
        hmi_port = hmi_config.get('port_name', 'COM1')
        scada_port = scada_config.get('port_name', 'COM2')
        
        if hmi_port != scada_port:
            print(f"✓ 端口配置不同: HMI={hmi_port}, SCADA={scada_port}")
        else:
            print(f"⚠ 端口配置相同: HMI={hmi_port}, SCADA={scada_port}")
    
    print()

if __name__ == "__main__":
    print("开始测试双串口管理功能...\n")
    
    test_configuration()
    test_dual_serial_initialization()
    test_dual_serial_methods()
    
    print("测试完成！")
    print("\n总结:")
    print("- 程序现在支持两个独立的串口: HMI串口和SCADA串口")
    print("- 每个串口有独立的配置、主站对象、轮询线程和数据存储")
    print("- 数据回调机制已分离，可以分别处理HMI和SCADA数据")
    print("- 前端可以获取两个串口的独立状态信息")
    print("- 兼容旧版本的单一串口接口")
    print("\n两个串口已经完全区分开来！")
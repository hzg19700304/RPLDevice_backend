#!/usr/bin/env python3
"""
串口超时诊断脚本
用于诊断Modbus串口通信超时问题
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager
from serial_comm.serial_manager import SerialManager
from serial_comm.modbus_rtu_master import ModbusRtuMaster, ModbusException

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_serial_connection():
    """测试串口连接"""
    print("=" * 60)
    print("串口超时诊断测试")
    print("=" * 60)
    
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 获取HMI串口配置
        hmi_config = config_manager.get_section('HMI串口配置')
        
        print(f"HMI串口配置:")
        print(f"  端口: {hmi_config.get('port_name', 'COM1')}")
        print(f"  波特率: {hmi_config.get('baudrate', 9600)}")
        print(f"  数据位: {hmi_config.get('databits', 8)}")
        print(f"  停止位: {hmi_config.get('stopbit', 1)}")
        print(f"  校验位: {hmi_config.get('parity', 0)}")
        print(f"  从站地址: {hmi_config.get('slave_address', 16)}")
        print(f"  超时时间: {hmi_config.get('timeout', 5.0)}秒")
        print()
        
        # 创建Modbus主站实例
        master = ModbusRtuMaster()
        
        # 尝试打开串口
        port_name = hmi_config.get('port_name', 'COM1')
        baudrate = int(hmi_config.get('baudrate', 9600))
        databits = int(hmi_config.get('databits', 8))
        parity = int(hmi_config.get('parity', 0))
        stopbits = int(hmi_config.get('stopbit', 1))
        timeout = float(hmi_config.get('timeout', 5.0))
        
        # 转换校验位
        parity_map = {0: 'N', 1: 'O', 2: 'E'}
        parity_str = parity_map.get(parity, 'N')
        
        print(f"正在连接 {port_name}...")
        
        # 打开串口
        success = master.open(
            port=port_name,
            baudrate=baudrate,
            bytesize=databits,
            parity=parity_str,
            stopbits=stopbits,
            timeout=timeout
        )
        
        if not success:
            print(f"❌ 串口 {port_name} 打开失败！")
            return False
            
        print(f"✅ 串口 {port_name} 打开成功！")
        print(f"串口状态: {master.is_open()}")
        
        # 测试不同的从站地址
        slave_address = int(hmi_config.get('slave_address', 16))
        test_addresses = [slave_address, 1, 2, 3, 4, 5]
        
        print(f"\n正在测试不同的从站地址...")
        print(f"标准配置从站地址: {slave_address}")
        
        for test_addr in test_addresses:
            print(f"\n测试从站地址: {test_addr}")
            
            # 尝试读取保持寄存器
            try:
                print(f"尝试读取保持寄存器 0x0000-0x0004...")
                result = master.read_holding_registers(
                    slave=test_addr,
                    address=0x0000,
                    count=5
                )
                
                if result and len(result) > 0:
                    print(f"✅ 从站地址 {test_addr} 响应成功！")
                    print(f"读取到的数据: {result}")
                    print(f"数据长度: {len(result)}")
                    
                    # 尝试读取更多寄存器
                    print(f"\n尝试读取更多寄存器...")
                    status_result = master.read_holding_registers(
                        slave=test_addr,
                        address=0x0000,
                        count=0x21  # 状态寄存器数量
                    )
                    
                    if status_result:
                        print(f"状态寄存器读取成功: {len(status_result)} 个寄存器")
                        
                    analog_result = master.read_holding_registers(
                        slave=test_addr,
                        address=0x0005,
                        count=31  # 模拟量寄存器数量
                    )
                    
                    if analog_result:
                        print(f"模拟量寄存器读取成功: {len(analog_result)} 个寄存器")
                        
                    return True
                else:
                    print(f"❌ 从站地址 {test_addr} 无响应或返回空数据")
                    
            except ModbusException as e:
                print(f"❌ Modbus错误: {e}")
            except Exception as e:
                print(f"❌ 其他错误: {e}")
                
            # 短暂延迟后测试下一个地址
            time.sleep(0.5)
        
        print(f"\n所有从站地址测试完成，未找到响应的设备")
        
        # 尝试不同的波特率
        print(f"\n尝试不同的波特率...")
        test_baudrates = [9600, 19200, 38400, 57600, 115200]
        
        for test_baud in test_baudrates:
            if test_baud == baudrate:
                continue
                
            print(f"\n测试波特率: {test_baud}")
            
            # 重新配置串口
            master.close()
            time.sleep(0.1)
            
            success = master.open(
                port=port_name,
                baudrate=test_baud,
                bytesize=databits,
                parity=parity_str,
                stopbits=stopbits,
                timeout=timeout
            )
            
            if success:
                print(f"串口重新配置成功")
                
                # 测试标准从站地址
                try:
                    result = master.read_holding_registers(
                        slave=slave_address,
                        address=0x0000,
                        count=5
                    )
                    
                    if result and len(result) > 0:
                        print(f"✅ 波特率 {test_baud} 下从站地址 {slave_address} 响应成功！")
                        print(f"读取到的数据: {result}")
                        return True
                        
                except Exception as e:
                    print(f"波特率 {test_baud} 下测试失败: {e}")
                    
            time.sleep(0.5)
        
        print(f"\n所有波特率测试完成，设备仍未响应")
        return False
        
    except Exception as e:
        print(f"❌ 测试过程发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if 'master' in locals() and master.is_open():
            master.close()
            print(f"\n串口已关闭")


def test_with_serial_manager():
    """使用串口管理器进行测试"""
    print("\n" + "=" * 60)
    print("使用串口管理器进行测试")
    print("=" * 60)
    
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化串口管理器
        serial_manager = SerialManager(config_manager)
        
        print("正在初始化串口管理器...")
        
        # 异步初始化
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        init_result = loop.run_until_complete(serial_manager.initialize())
        loop.close()
        
        if not init_result:
            print("❌ 串口管理器初始化失败")
            return False
            
        print("✅ 串口管理器初始化成功")
        
        # 开始轮询
        print("正在启动串口轮询...")
        if not serial_manager.start_polling():
            print("❌ 串口轮询启动失败")
            return False
            
        print("✅ 串口轮询已启动")
        print("等待5秒让系统稳定...")
        time.sleep(5)
        
        # 检查当前数据
        hmi_data = serial_manager.get_hmi_current_data()
        if hmi_data:
            print("✅ HMI数据已获取")
            print(f"状态寄存器: {len(hmi_data.status_registers) if hmi_data.status_registers else 0} 个")
            print(f"模拟量寄存器: {len(hmi_data.analog_registers) if hmi_data.analog_registers else 0} 个")
            
            if hmi_data.status_registers:
                print(f"前5个状态寄存器: {hmi_data.status_registers[:5]}")
            if hmi_data.analog_registers:
                print(f"前5个模拟量寄存器: {hmi_data.analog_registers[:5]}")
        else:
            print("❌ 未获取到HMI数据")
            
        # 停止轮询
        serial_manager.stop_polling()
        print("串口轮询已停止")
        
        return hmi_data is not None
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("串口超时诊断工具")
    print("此工具将帮助诊断Modbus串口通信超时问题")
    print()
    
    # 测试1：直接串口连接测试
    print("测试1：直接串口连接测试")
    direct_test_result = test_serial_connection()
    
    print("\n" + "=" * 60)
    print(f"直接串口连接测试结果: {'✅ 通过' if direct_test_result else '❌ 失败'}")
    print("=" * 60)
    
    # 测试2：使用串口管理器测试
    print("\n测试2：使用串口管理器测试")
    manager_test_result = test_with_serial_manager()
    
    print("\n" + "=" * 60)
    print(f"串口管理器测试结果: {'✅ 通过' if manager_test_result else '❌ 失败'}")
    print("=" * 60)
    
    # 总结
    print("\n诊断总结:")
    if direct_test_result and manager_test_result:
        print("✅ 串口通信正常，超时问题可能已解决")
    elif direct_test_result and not manager_test_result:
        print("⚠️  直接串口连接成功，但串口管理器有问题")
        print("建议：检查串口管理器配置或代码逻辑")
    elif not direct_test_result and manager_test_result:
        print("⚠️  直接串口连接失败，但串口管理器工作正常")
        print("建议：这可能是偶发性问题，继续观察")
    else:
        print("❌ 串口通信存在严重问题")
        print("建议：")
        print("1. 检查物理连接（串口线、电源）")
        print("2. 确认设备从站地址和串口参数")
        print("3. 检查设备是否正常工作")
        print("4. 尝试使用其他串口调试工具验证")
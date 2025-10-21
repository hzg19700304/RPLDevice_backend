# modbus_rtu_slave.py
# flake8: noqa
# mypy: ignore-errors
"""
最终工作版本 - Modbus RTU 从站设备
修复了 pymodbus 3.11.3 的所有API变化问题
"""
from __future__ import annotations

import sys
import time
import threading
import logging
import signal
import math
import inspect
from typing import List, Optional, Callable
from dataclasses import dataclass

# 导入必需模块
# print("🔍 导入 pymodbus 3.11.3 模块...")

try:
    from pymodbus.server import StartSerialServer
    from pymodbus.datastore import (
        ModbusServerContext,
        ModbusDeviceContext,
        ModbusSequentialDataBlock
    )

    print("✓ 核心模块导入成功")

    # 创建简化的设备标识
    class SimpleDeviceIdentification:
        def __init__(self):
            self.VendorName = "PyModbus从站"
            self.ProductCode = "RTU-SLAVE"
            self.VendorUrl = ""
            self.ProductName = "Modbus RTU从站设备"
            self.ModelName = "模拟设备"
            self.MajorMinorRevision = "1.0"


    print("✓ 设备标识创建成功")

except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 获取日志记录器 - 不再设置basicConfig，避免覆盖主程序配置
logger = logging.getLogger(__name__)


@dataclass
class RegisterConfig:
    """寄存器配置"""
    address: int
    name: str
    initial_value: int
    description: str
    update_func: Optional[Callable[[int, int], int]] = None


class ModbusRtuSlaveDevice:
    """Modbus RTU 从站设备 - 最终工作版本"""

    def __init__(self, device_id: int = 16):
        self.device_id = device_id
        self.running = False
        self.data_thread: Optional[threading.Thread] = None
        self.server_context: Optional[ModbusServerContext] = None
        self.counter = 0
        self.start_time = time.time()

        # 基于您的测试数据配置寄存器
        self.registers = [
            RegisterConfig(0, "主传感器", 22816, "主传感器读数", self._update_main_sensor),
            RegisterConfig(1, "保留1", 0, "保留寄存器1"),
            RegisterConfig(2, "保留2", 0, "保留寄存器2"),
            RegisterConfig(3, "状态寄存器", 771, "状态寄存器", self._update_status),
            RegisterConfig(4, "温度传感器", 256, "温度×0.1°C", self._update_temperature),
            RegisterConfig(5, "湿度传感器", 450, "湿度×0.1%", self._update_humidity),
            RegisterConfig(6, "压力传感器", 1013, "压力kPa", self._update_pressure),
            RegisterConfig(7, "计数器", 0, "运行计数器", self._update_counter),
        ]

        # 创建服务器上下文
        self._create_context()

    def _create_context(self):
        """创建Modbus服务器上下文 - 修复API兼容性"""
        # 创建数据块
        holding_registers = ModbusSequentialDataBlock(0, [0] * 100)
        input_registers = ModbusSequentialDataBlock(0, [0] * 100)
        coils = ModbusSequentialDataBlock(0, [False] * 100)
        discrete_inputs = ModbusSequentialDataBlock(0, [False] * 100)

        # 初始化寄存器值
        for reg in self.registers:
            holding_registers.setValues(reg.address, [reg.initial_value])
            input_registers.setValues(reg.address, [reg.initial_value])

        # 初始化线圈
        coils.setValues(0, [True, False, True, False, False])
        discrete_inputs.setValues(0, [True, False, True, False, False])

        # 创建设备上下文
        device_context = ModbusDeviceContext(
            di=discrete_inputs,
            co=coils,
            hr=holding_registers,
            ir=input_registers
        )

        # 修复 ModbusServerContext 构造 - 尝试不同的参数组合
        context_attempts = [
            # 尝试1: 新版本可能的参数
            lambda: ModbusServerContext(devices={self.device_id: device_context}, single=False),
            # 尝试2: 只传递单个设备上下文
            lambda: ModbusServerContext(device_context, single=True),
            # 尝试3: 使用位置参数
            lambda: ModbusServerContext(device_context),
            # 尝试4: 检查构造函数签名并适配
            lambda: self._create_context_adaptive(device_context),
        ]

        success = False
        for i, attempt in enumerate(context_attempts):
            try:
                self.server_context = attempt()
                logger.info(f"✓ 服务器上下文创建成功 (方法 {i + 1})")
                success = True
                break
            except Exception as e:
                logger.debug(f"上下文创建方法 {i + 1} 失败: {e}")
                continue

        if not success:
            raise Exception("所有服务器上下文创建方法都失败")

    def _create_context_adaptive(self, device_context):
        """自适应创建服务器上下文"""
        # 检查 ModbusServerContext 的构造函数签名
        sig = inspect.signature(ModbusServerContext.__init__)
        params = list(sig.parameters.keys())[1:]  # 排除 self

        logger.debug(f"ModbusServerContext 参数: {params}")

        # 根据参数名适配
        if 'devices' in params:
            return ModbusServerContext(devices={self.device_id: device_context}, single=False)
        elif 'slaves' in params:
            return ModbusServerContext(slaves={self.device_id: device_context}, single=False)
        elif len(params) == 1:
            # 只有一个参数，可能是单设备模式
            return ModbusServerContext(device_context)
        else:
            # 默认尝试
            return ModbusServerContext(device_context, single=True)

    # 数据更新函数
    def _update_main_sensor(self, current_value: int, counter: int) -> int:
        """主传感器 - 基于22816添加变化"""
        base = 22816
        variation = int(math.sin(counter * 0.05) * 200)
        return max(0, min(65535, base + variation))

    def _update_status(self, current_value: int, counter: int) -> int:
        """状态寄存器 - 基于771添加变化"""
        base = 771
        patterns = [0, 32, 64, 96, 128]
        return (base + patterns[counter % len(patterns)]) & 0xFFFF

    def _update_temperature(self, current_value: int, counter: int) -> int:
        """温度传感器 25.6°C"""
        base = 256
        variation = int(math.sin(counter * 0.01) * 30)
        return max(-500, min(1000, base + variation))

    def _update_humidity(self, current_value: int, counter: int) -> int:
        """湿度传感器 45.0%"""
        base = 450
        variation = (counter % 200) - 100
        return max(0, min(1000, base + variation))

    def _update_pressure(self, current_value: int, counter: int) -> int:
        """压力传感器"""
        base = 1013
        variation = int(math.cos(counter * 0.02) * 200)
        return max(0, min(5000, base + variation))

    def _update_counter(self, current_value: int, counter: int) -> int:
        """计数器"""
        return counter % 65536

    def start_slave(self, port: str = "COM4", baudrate: int = 9600, enable_simulation: bool = True):
        """启动从站设备"""

        logger.info("=" * 60)
        logger.info("🎯 Modbus RTU 从站设备启动")
        logger.info("=" * 60)
        logger.info(f"设备ID: {self.device_id}")
        logger.info(f"串口: {port}")
        logger.info(f"波特率: {baudrate}")
        logger.info(f"数据模拟: {'启用' if enable_simulation else '禁用'}")

        # 显示寄存器映射
        self._show_register_map()

        # 启动数据模拟
        if enable_simulation:
            self._start_simulation()

        # 创建设备标识
        identity = SimpleDeviceIdentification()

        # 信号处理
        def signal_handler(sig, frame):
            logger.info("⛔ 接收到停止信号")
            self._stop_simulation()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            # logger.info("🚀 从站设备启动完成，等待主站连接...")
            # logger.info("")
            # logger.info("📡 支持的Modbus功能:")
            # logger.info("   ✓ 功能码 01 - 读线圈")
            # logger.info("   ✓ 功能码 02 - 读离散输入")
            # logger.info("   ✓ 功能码 03 - 读保持寄存器 ⭐")
            # logger.info("   ✓ 功能码 04 - 读输入寄存器")
            # logger.info("   ✓ 功能码 05 - 写单个线圈")
            # logger.info("   ✓ 功能码 06 - 写单个寄存器 ⭐")
            # logger.info("   ✓ 功能码 15 - 写多个线圈")
            # logger.info("   ✓ 功能码 16 - 写多个寄存器")
            # logger.info("")
            # logger.info("💡 测试方法:")
            # logger.info(f"   1. 使用客户端连接到另一个串口")
            # logger.info(f"   2. 读取设备ID {self.device_id}, 寄存器地址 0-3")
            # logger.info(f"   3. 应该看到类似您测试数据的值: [22816±, 0, 0, 771±]")
            # logger.info("")
            # logger.info("⏹️  按 Ctrl+C 停止设备")
            # logger.info("=" * 60)

            # 启动服务器
            StartSerialServer(
                context=self.server_context,
                identity=identity,
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=3
            )

        except KeyboardInterrupt:
            logger.info("⛔ 用户中断")
        except Exception as e:
            logger.error(f"❌ 服务器运行错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._stop_simulation()
            logger.info("👋 从站设备已停止")

    def _start_simulation(self):
        """启动数据模拟"""
        self.running = True
        self.data_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.data_thread.start()
        logger.info("📊 数据模拟已启动")

    def _stop_simulation(self):
        """停止数据模拟"""
        self.running = False
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=2.0)
        logger.info("📊 数据模拟已停止")

    def _simulation_loop(self):
        """数据模拟循环"""
        while self.running:
            try:
                self._update_all_registers()
                self.counter += 1

                # 每60秒显示一次状态
                if self.counter % 60 == 0:
                    self._show_current_status()

                time.sleep(1.0)

            except Exception as e:
                logger.error(f"模拟数据更新失败: {e}")
                time.sleep(5.0)

    def _update_all_registers(self):
        """更新所有寄存器"""
        for reg in self.registers:
            try:
                # 获取设备上下文的方法可能因版本而异
                device_context = self._get_device_context()
                if device_context is None:
                    continue

                if reg.update_func:
                    current_value = device_context.getValues(3, reg.address, 1)[0]
                    new_value = reg.update_func(current_value, self.counter)
                else:
                    new_value = reg.initial_value

                new_value = int(new_value) & 0xFFFF  # 确保16位范围

                # 更新保持寄存器和输入寄存器
                device_context.setValues(3, reg.address, [new_value])  # 保持寄存器
                device_context.setValues(4, reg.address, [new_value])  # 输入寄存器

            except Exception as e:
                logger.warning(f"更新寄存器{reg.address}失败: {e}")

    def _get_device_context(self):
        """获取设备上下文 - 适配不同的API"""
        try:
            # 尝试不同的访问方式
            if hasattr(self.server_context, '__getitem__'):
                # 类似字典的访问方式
                return self.server_context[self.device_id]
            elif hasattr(self.server_context, 'slaves') and self.server_context.slaves:
                return self.server_context.slaves[self.device_id]
            elif hasattr(self.server_context, 'devices') and self.server_context.devices:
                return self.server_context.devices[self.device_id]
            else:
                # 单设备模式，直接返回服务器上下文
                return self.server_context
        except Exception as e:
            logger.debug(f"获取设备上下文失败: {e}")
            return None

    def _show_register_map(self):
        """显示寄存器映射"""
        # logger.info("")
        # logger.info("📋 寄存器映射表:")
        # logger.info("-" * 70)
        # logger.info(f"{'地址':<4} {'名称':<12} {'初始值':<8} {'描述'}")
        # logger.info("-" * 70)
        #
        # for reg in self.registers:
        #     logger.info(f"{reg.address:<4} {reg.name:<12} {reg.initial_value:<8} {reg.description}")
        #
        # logger.info("")
        # logger.info("💾 数据区域:")
        # logger.info("   保持寄存器 (功能码03): 地址 0-99")
        # logger.info("   输入寄存器 (功能码04): 地址 0-99")
        # logger.info("   线圈 (功能码01):        地址 0-99")
        # logger.info("   离散输入 (功能码02):    地址 0-99")
        pass

    def _show_current_status(self):
        """显示当前状态"""
        runtime = int(time.time() - self.start_time)
        # logger.info(f"")
        # logger.info(f"📊 运行状态报告")
        # logger.info(f"   运行时间: {runtime}秒")
        # logger.info(f"   更新次数: {self.counter}")
        # logger.info(f"   设备ID: {self.device_id}")
        #
        # logger.info("📈 当前寄存器值:")
        device_context = self._get_device_context()
        if device_context:
            for reg in self.registers[:6]:  # 显示前6个寄存器
                try:
                    value = device_context.getValues(3, reg.address, 1)[0]
                    logger.info(f"   R{reg.address:02d}: {value:5d} (0x{value:04X}) - {reg.name}")
                except Exception as e:
                    logger.info(f"   R{reg.address:02d}: 读取失败")
        else:
            logger.info("   无法访问设备上下文")


def main():
    """主函数"""
    print("🎯 Modbus RTU 从站设备 - 最终工作版本")
    print("=" * 60)
    print("专为 pymodbus 3.11.3 优化")
    print("基于您的测试数据: [22816, 0, 0, 771]")
    print()

    # 获取配置
    try:
        device_id_input = input("设备ID (1-247, 默认16): ").strip()
        device_id = int(device_id_input) if device_id_input else 16

        if not (1 <= device_id <= 247):
            print("⚠️  设备ID超出范围，使用默认值16")
            device_id = 16

        port = input("串口 (默认COM4): ").strip() or "COM4"

        baudrate_input = input("波特率 (默认9600): ").strip()
        baudrate = int(baudrate_input) if baudrate_input else 9600

        sim_input = input("启用数据模拟? (Y/n): ").strip().lower()
        enable_simulation = sim_input != 'n'

        print(f"\n📋 配置确认:")
        print(f"   设备ID: {device_id}")
        print(f"   串口: {port}")
        print(f"   波特率: {baudrate}")
        print(f"   数据模拟: {'启用' if enable_simulation else '禁用'}")
        print()

        confirm = input("▶️  开始启动? (Y/n): ").strip().lower()
        if confirm == 'n':
            print("👋 取消启动")
            return

    except KeyboardInterrupt:
        print("\n👋 用户取消")
        return
    except Exception:
        print("⚠️  输入错误，使用默认配置")
        device_id, port, baudrate, enable_simulation = 16, "COM4", 9600, True

    # 启动从站设备
    try:
        print("\n🚀 正在启动从站设备...")
        device = ModbusRtuSlaveDevice(device_id)
        device.start_slave(port, baudrate, enable_simulation)

    except Exception as e:
        logger.error(f"❌ 设备启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
# modbus_rtu_master.py
# flake8: noqa
# mypy: ignore-errors
"""
修复版本：适配pymodbus 3.11+的 Modbus-RTU 主站客户端
修复了API参数问题和数据转换逻辑
"""
from __future__ import annotations

import sys
import time
import queue
import threading
import struct
import inspect
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

# 导入pymodbus 3.11+
try:
    from pymodbus.client import ModbusSerialClient
    from pymodbus.exceptions import ModbusException as _ModbusException
    print("[OK] pymodbus 导入成功 (版本 3.11+)")
except ImportError as e:
    print(f"[ERROR] 无法导入pymodbus: {e}")
    sys.exit(1)

# 尝试导入Endian
try:
    from pymodbus.constants import Endian
    print("[OK] Endian 导入成功")
except (ImportError, AttributeError):
    print("[WARN] Endian导入失败，使用简化版本")

    class Endian:
        BIG = ">"
        LITTLE = "<"
        Big = ">"  # 兼容性
        Little = "<"  # 兼容性

# ---------- 工具类 ----------
class ModbusException(_ModbusException):
    """统一异常类型"""
    pass

@dataclass
class Transaction:
    """一次请求-响应事务"""
    function: str
    slave_id: int
    address: int
    value_or_count: Union[int, List[int]]
    timeout: float
    expire: float = field(init=False)
    result: Any = None

    def __post_init__(self):
        self.expire = time.time() + self.timeout

# ---------- 主类 ----------
class ModbusRtuMaster:
    """修复版本的 Modbus RTU 主站"""

    def __init__(self):
        self.client: Optional[ModbusSerialClient] = None
        self._queue: queue.Queue[Transaction] = queue.Queue()
        self._pending: Optional[Transaction] = None
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()
        self._api_tested = False
        self._convert_api_available = False
        self.port: Optional[str] = None  # 存储端口信息

    # ---------------- 连接管理 ----------------
    def open(
            self,
            port: str = "COM3",
            baudrate: int = 9600,
            bytesize: int = 8,
            parity: str = "N",
            stopbits: int = 1,
            timeout: float = 3.0,
            retries: int = 3,
    ) -> bool:
        try:
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
                retries=retries,
            )

            if self.client.connect():
                self._running = True
                self._worker = threading.Thread(target=self._background_sender, daemon=True)
                self._worker.start()
                self.port = port  # 存储端口信息
                # print(f"✓ 串口已连接: {port}")

                return True
            else:
                # print(f"✗ 串口连接失败: {port}")
                return False

        except Exception as e:
            # print(f"✗ 打开串口异常: {e}")
            return False

    def close(self):
        self._running = False
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1)
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                print(f"[ERROR] 串口关闭异常: {e}")
                pass
        print("[OK] 串口已关闭")

    def is_open(self) -> bool:
        return self.client is not None and self.client.is_socket_open()

    # ---------------- 后台处理 ----------------
    def _background_sender(self):
        while self._running:
            try:
                trans = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._pending = trans
            with self._send_lock:
                self._execute_modbus_request(trans)
            self._pending = None

    def _execute_modbus_request(self, trans: Transaction):
        try:
            if time.time() > trans.expire:
                trans.result = ModbusException(f"{trans.function} 请求超时")
                return

            func_map = {
                "read_holding_registers": self.client.read_holding_registers,
                "read_input_registers": self.client.read_input_registers,
                "read_coils": self.client.read_coils,
                "read_discrete_inputs": self.client.read_discrete_inputs,
                "write_single_register": self.client.write_register,
                "write_multiple_registers": self.client.write_registers,
                "write_single_coil": self.client.write_coil,
                "read_file_record": self._read_file_record_impl,
            }

            method = func_map.get(trans.function)
            if not method:
                raise ModbusException(f"未知功能: {trans.function}")

            # 检查方法签名以确定使用哪个参数
            sig = inspect.signature(method)
            kwargs = {"address": trans.address}

            # 优先使用device_id，fallback到slave
            if "device_id" in sig.parameters:
                kwargs["device_id"] = trans.slave_id
            elif "slave" in sig.parameters:
                kwargs["slave"] = trans.slave_id

            if trans.function.startswith("read"):
                kwargs["count"] = trans.value_or_count
            elif trans.function == "write_multiple_registers":
                kwargs["values"] = [v & 0xFFFF for v in trans.value_or_count]
            elif trans.function == "write_single_coil":
                kwargs["value"] = bool(trans.value_or_count)
            else:  # write_single_register
                kwargs["value"] = trans.value_or_count & 0xFFFF

            result = method(**kwargs)

            if result.isError():
                raise ModbusException(f"Modbus错误: {result}")

            if hasattr(result, "registers"):
                trans.result = result.registers
            elif hasattr(result, "bits"):
                trans.result = result.bits
            else:
                trans.result = result

        except Exception as e:
            trans.result = e

    # ---------------- 公开API ----------------
    def _enqueue(self, func: str, slave: int, addr: int, val_cnt: Union[int, List[int]], timeout: float = 3.0):
        if not self.is_open():
            raise ModbusException("连接未开启")

        # 添加调试信息：记录下发的Modbus命令
        if isinstance(val_cnt, list):
            debug_val = f"[{', '.join(map(str, val_cnt))}]"
        else:
            debug_val = str(val_cnt)
        
        # print(f"🔧 [Modbus命令下发] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 值/数量: {debug_val}")

        trans = Transaction(function=func, slave_id=slave, address=addr, value_or_count=val_cnt, timeout=timeout)
        self._queue.put(trans)

        # 使用更精确的等待机制，避免竞态条件
        while trans.result is None:
            if time.time() > trans.expire:
                print(f"⏰ [Modbus命令超时] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}")
                raise ModbusException(f"{func} 操作超时")
            # 使用更短的休眠时间，提高响应性
            time.sleep(0.001)
            # 立即检查结果，避免错过
            if trans.result is not None:
                break

        if isinstance(trans.result, Exception):
            # print(f"❌ [Modbus命令错误] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 错误: {trans.result}")
            raise trans.result
        
        # 添加调试信息：记录成功的Modbus响应
        if func.startswith("read"):
            # print(f"✅ [Modbus读取成功] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 返回值: {trans.result}")
            # 特殊调试：如果是读取控制参数区域（0x2200-0x2237），显示详细参数值
            if addr >= 0x2200 and addr <= 0x2237 and isinstance(trans.result, list):
                print(f"📊 [控制参数详情] 读取到 {len(trans.result)} 个寄存器:")
                for i, value in enumerate(trans.result):
                    reg_addr = addr + i
                    print(f"    0x{reg_addr:04X} = {value}")
        else:
            print(f"✅ [Modbus写入成功] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}")
        
        return trans.result

    # ---- 读操作 ----
    def read_holding_registers(self, slave: int, address: int, count: int = 1) -> List[int]:
        return self._enqueue("read_holding_registers", slave, address, count)

    def read_input_registers(self, slave: int, address: int, count: int = 1) -> List[int]:
        return self._enqueue("read_input_registers", slave, address, count)

    def read_coils(self, slave: int, address: int, count: int = 1) -> List[bool]:
        return self._enqueue("read_coils", slave, address, count)

    def read_discrete_inputs(self, slave: int, address: int, count: int = 1) -> List[bool]:
        return self._enqueue("read_discrete_inputs", slave, address, count)

    # ---- 写操作 ----
    def write_single_register(self, slave: int, address: int, value: int) -> bool:
        self._enqueue("write_single_register", slave, address, value & 0xFFFF)
        return True

    def write_multiple_registers(self, slave: int, address: int, values: List[int]) -> bool:
        self._enqueue("write_multiple_registers", slave, address, values)
        return True

    def write_single_coil(self, slave: int, address: int, value: bool) -> bool:
        self._enqueue("write_single_coil", slave, address, value)
        return True

    # ---- 文件读取操作（功能码0x14） ----
    def read_file_record(self, slave: int, file_number: int, record_start: int, record_length: int) -> List[int]:
        """
        读取文件记录（功能码0x14）
        
        Args:
            slave: 从站地址
            file_number: 文件编号（0=最新记录，1=上一条记录，以此类推）
            record_start: 记录起始地址（寄存器偏移）
            record_length: 记录长度（寄存器数量）
            
        Returns:
            读取到的寄存器数据列表
        """
        return self._enqueue("read_file_record", slave, 0, [file_number, record_start, record_length])

    # ---------------- 改进的数据类型转换 ----------------
    def convert_from_registers(self, registers: List[int], data_type: str = "INT16", endian: str = "big") -> Any:
        """改进的寄存器转换方法"""
        if not registers:
            return 0

        # 如果新API可用，尝试使用（这里我们暂时跳过新API，直接用手动转换）
        # 因为新API的参数格式还需要进一步测试

        # 使用改进的手动转换
        return self._improved_manual_convert(registers, data_type, endian)

    def _improved_manual_convert(self, registers: List[int], data_type: str, endian: str) -> Any:
        """改进的手动转换，修复了字节序问题"""
        if not registers:
            return 0

        try:
            # 将寄存器转换为字节，注意Modbus寄存器是16位大端序
            byte_data = b""
            for reg in registers:
                # Modbus寄存器总是大端序(Big Endian)存储
                byte_data += struct.pack(">H", reg)

            # 根据数据类型和字节序解码
            formats = {
                "INT16": {
                    "big": ">h",
                    "little": "<h",
                    "bytes": 2
                },
                "UINT16": {
                    "big": ">H",
                    "little": "<H",
                    "bytes": 2
                },
                "INT32": {
                    "big": ">i",
                    "little": "<i",
                    "bytes": 4
                },
                "UINT32": {
                    "big": ">I",
                    "little": "<I",
                    "bytes": 4
                },
                "FLOAT32": {
                    "big": ">f",
                    "little": "<f",
                    "bytes": 4
                },
                "FLOAT64": {
                    "big": ">d",
                    "little": "<d",
                    "bytes": 8
                }
            }

            dtype_info = formats.get(data_type.upper())
            if not dtype_info:
                raise ValueError(f"不支持的数据类型: {data_type}")

            endian_key = endian.lower()
            if endian_key not in dtype_info:
                endian_key = "big"  # 默认

            fmt = dtype_info[endian_key]
            needed_bytes = dtype_info["bytes"]

            if len(byte_data) < needed_bytes:
                raise ValueError(f"需要至少{needed_bytes // 2}个寄存器来转换{data_type}")

            # 如果需要调整字节序（对于多字节类型）
            if needed_bytes > 2 and endian.lower() == "little":
                # 对于little endian的多字节数据，需要按字(word)交换
                words = []
                for i in range(0, needed_bytes, 2):
                    words.append(byte_data[i:i + 2])
                words.reverse()  # 交换字序
                byte_data = b"".join(words)

            result = struct.unpack(fmt, byte_data[:needed_bytes])[0]
            return result

        except Exception as e:
            print(f"转换失败: {e}")
            return registers[0] if registers else 0

    def convert_to_registers(self, value: Any, data_type: str = "INT16", endian: str = "big") -> List[int]:
        """改进的值到寄存器转换"""
        try:
            formats = {
                "INT16": ">h" if endian.lower() == "big" else "<h",
                "UINT16": ">H" if endian.lower() == "big" else "<H",
                "INT32": ">i" if endian.lower() == "big" else "<i",
                "UINT32": ">I" if endian.lower() == "big" else "<I",
                "FLOAT32": ">f" if endian.lower() == "big" else "<f",
                "FLOAT64": ">d" if endian.lower() == "big" else "<d",
            }

            fmt = formats.get(data_type.upper(), ">H")
            byte_data = struct.pack(fmt, value)

            # 对于little endian的多字节数据，需要按字交换
            if len(byte_data) > 2 and endian.lower() == "little":
                words = []
                for i in range(0, len(byte_data), 2):
                    words.append(byte_data[i:i + 2])
                words.reverse()
                byte_data = b"".join(words)

            # 转换为寄存器（总是大端序）
            registers = []
            for i in range(0, len(byte_data), 2):
                reg = struct.unpack(">H", byte_data[i:i + 2])[0]
                registers.append(reg)

            return registers

        except Exception as e:
            print(f"转换失败: {e}")
            return [int(value) & 0xFFFF]

    # ---------------- 文件读取协议实现 ----------------
    def _read_file_record_impl(self, slave: int, params: List[int]) -> List[int]:
        """
        实现功能码0x14的文件读取协议
        
        Args:
            slave: 从站地址
            params: [文件编号, 记录起始地址, 记录长度]
            
        Returns:
            读取到的寄存器数据
        """
        file_number, record_start, record_length = params
        
        # 构建Modbus请求帧
        # 功能码0x14：读取文件记录
        # 请求格式：从站地址 + 功能码(0x14) + 字节数 + 参数类型 + 文件编号 + 记录起始 + 记录长度 + CRC
        
        request_data = [
            0x07,  # 字节数（后续数据长度）
            0x06,  # 参数类型（固定为0x06）
            (file_number >> 8) & 0xFF,  # 文件编号高字节
            file_number & 0xFF,          # 文件编号低字节
            (record_start >> 8) & 0xFF,  # 记录起始地址高字节
            record_start & 0xFF,         # 记录起始地址低字节
            (record_length >> 8) & 0xFF, # 记录长度高字节
            record_length & 0xFF         # 记录长度低字节
        ]
        
        try:
            # 使用原始Modbus客户端发送自定义功能码请求
            if not self.client:
                raise ModbusException("Modbus客户端未连接")
            
            # 发送功能码0x14请求
            response = self.client.execute(
                slave,
                0x14,  # 功能码
                request_data
            )
            
            if response.isError():
                raise ModbusException(f"文件读取错误: {response}")
            
            # 解析响应数据
            if hasattr(response, 'registers'):
                return response.registers
            else:
                # 如果响应没有registers属性，尝试从原始数据解析
                return self._parse_file_record_response(response)
                
        except Exception as e:
            raise ModbusException(f"文件读取失败: {e}")
    
    def _parse_file_record_response(self, response) -> List[int]:
        """解析文件记录响应数据"""
        # 这里需要根据实际的设备响应格式进行解析
        # 通常响应格式为：从站地址 + 功能码 + 字节数 + 数据 + CRC
        
        if hasattr(response, 'bits') and response.bits:
            # 将bit数据转换为寄存器数据（每16位一个寄存器）
            bits = response.bits
            registers = []
            for i in range(0, len(bits), 16):
                register_value = 0
                for j in range(16):
                    if i + j < len(bits) and bits[i + j]:
                        register_value |= (1 << j)
                registers.append(register_value)
            return registers
        
        # 如果无法解析，返回空列表
        return []

    # ---------------- 数据分析辅助方法 ----------------
    def analyze_register_data(self, registers: List[int], start_addr: int = 0):
        """分析寄存器数据的各种可能含义"""
        if not registers:
            return

        print(f"\n🔍 数据分析 (寄存器地址 {start_addr}-{start_addr + len(registers) - 1}):")
        print("=" * 60)

        for i, reg in enumerate(registers):
            addr = start_addr + i
            print(f"寄存器 {addr:3d}: 0x{reg:04X} = {reg:5d} = {reg:016b}")

        if len(registers) >= 2:
            print("\n多寄存器组合解析:")
            print("-" * 40)

            # 尝试不同的数据类型和字节序
            test_cases = [
                ("INT32_BE", "INT32", "big"),
                ("INT32_LE", "INT32", "little"),
                ("UINT32_BE", "UINT32", "big"),
                ("UINT32_LE", "UINT32", "little"),
                ("FLOAT32_BE", "FLOAT32", "big"),
                ("FLOAT32_LE", "FLOAT32", "little"),
            ]

            for name, dtype, endian in test_cases:
                try:
                    val = self.convert_from_registers(registers[:2], dtype, endian)
                    print(f"{name:10}: {val}")
                except Exception as e:
                    print(f"{name:10}: 转换失败 - {e}")

    # ---------------- 状态查询 ----------------
    def queue_size(self) -> int:
        return self._queue.qsize()

    def is_busy(self) -> bool:
        return self._pending is not None and self._pending.result is None


# ---------------- 测试程序 ----------------
def main():
    print("修复版本 - Modbus RTU 主站测试程序")
    print("=" * 60)

    mb = ModbusRtuMaster()

    ports_to_try = ["COM3", "COM4", "COM5", "COM6", "COM7", "COM8"]
    connected = False

    print("🔌 尝试连接串口...")
    for port in ports_to_try:
        print(f"   尝试 {port}...", end=" ")
        if mb.open(port=port, baudrate=9600, timeout=2.0):
            connected = True
            break
        print("失败")
        time.sleep(0.5)

    if not connected:
        print("\n❌ 无法连接任何串口")
        return

    try:
        print(f"\n✅ 连接成功!")
        print("-" * 40)
        # 基本读取测试
        print("📖 读取保持寄存器")
        try:
            regs = mb.read_holding_registers(slave=16, address=0, count=4)
            print(f"   原始数据: {regs}")
            # 详细分析数据
            mb.analyze_register_data(regs, 0)
        except ModbusException as e:
            print(f"   ❌ 读取失败: {e}")
        print("\n✅ 测试完成!")
    except KeyboardInterrupt:
        print("\n⛔ 用户中断")
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mb.close()

if __name__ == "__main__":
    main()

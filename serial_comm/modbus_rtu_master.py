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
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

# 导入配置管理器
try:
    from config.config_manager import ConfigManager
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

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
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])  # 添加唯一ID

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
        
        # 初始化配置管理器
        self.config_manager = None
        self.control_register_start = 0x2200  # 默认起始地址
        self.control_register_end = 0x2237    # 默认结束地址
        
        if CONFIG_AVAILABLE:
            try:
                self.config_manager = ConfigManager()
                # 从配置文件中读取控制参数寄存器地址范围
                control_config = self.config_manager.get_section("HMI系统控制参数寄存器")
                self.control_register_start = control_config.get("control_register_start_address", 0x2200)
                control_register_count = control_config.get("control_register_count", 55)
                self.control_register_end = self.control_register_start + control_register_count - 1
                print(f"[OK] 已从配置文件加载控制参数寄存器地址范围: 0x{self.control_register_start:04X}-0x{self.control_register_end:04X}")
            except Exception as e:
                print(f"[WARN] 无法加载配置文件，使用默认控制参数寄存器地址范围: {e}")

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
                # 移除在执行前检查超时的逻辑，让事务有机会执行
                # 超时检查应该在实际通信操作中进行
                self._execute_modbus_request(trans)
            self._pending = None

    def _execute_modbus_request(self, trans: Transaction):
        try:
            # 移除这里的超时检查，由_enqueue方法中的等待循环负责
            # if time.time() > trans.expire:
            #     # 对于文件记录操作，使用特殊格式显示地址
            #     if trans.function == "read_file_record" and trans.address >= 0x1000:
            #         file_num = trans.address - 0x1000
            #         print(f"⏰ [Modbus命令超时] 功能码: {trans.function}, 从站地址: {trans.slave_id}, 文件编号: {file_num}")
            #     else:
            #         print(f"⏰ [Modbus命令超时] 功能码: {trans.function}, 从站地址: {trans.slave_id}, 寄存器地址: 0x{trans.address:04X}")
            #     trans.result = ModbusException(f"{trans.function} 请求超时")
            #     return

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

            # 特殊处理read_file_record功能码
            if trans.function == "read_file_record":
                # 对于read_file_record，trans.value_or_count是一个列表，包含[文件编号, 记录起始地址, 记录长度]
                # 直接传递给_read_file_record_impl方法
                result = method(trans.slave_id, trans.value_or_count)
            else:
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

            if hasattr(result, "isError") and result.isError():
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
        
        trans = Transaction(function=func, slave_id=slave, address=addr, value_or_count=val_cnt, timeout=timeout)
        
        # 只监视0x14（read_file_record）命令
        if func == "read_file_record" and addr >= 0x1000:
            file_num = addr - 0x1000
            print(f"[Modbus命令下发] ID:{trans.id} 功能码: {func}, 从站地址: {slave}, 文件编号: {file_num}, 参数: {debug_val}")
        # 其他命令不输出调试信息
        # print(f"[Modbus命令下发] ID:{trans.id} 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 参数: {debug_val}")
        self._queue.put(trans)

        # 等待事务完成
        start_time = time.time()
        while trans.result is None:
            # 检查是否超时
            if time.time() - start_time > timeout:
                # 只监视0x14（read_file_record）命令的超时
                if func == "read_file_record" and addr >= 0x1000:
                    file_num = addr - 0x1000
                    print(f"[Modbus命令超时] ID:{trans.id} 功能码: {func}, 从站地址: {slave}, 文件编号: {file_num}")
                # 其他命令的超时不输出调试信息
                trans.result = ModbusException(f"{func} 操作超时")
                break
                
            # 使用更短的休眠时间，提高响应性
            time.sleep(0.001)

        if isinstance(trans.result, Exception):
            # print(f"❌ [Modbus命令错误] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 错误: {trans.result}")
            raise trans.result
        
        # 只监视0x14（read_file_record）命令的响应
        if func == "read_file_record" and addr >= 0x1000:
            file_num = addr - 0x1000
            print(f"[Modbus读取成功] 功能码: {func}, 从站地址: {slave}, 文件编号: {file_num}, 返回值: {trans.result}")
        # 其他命令的响应不输出调试信息
        # print(f"[Modbus读取成功] 功能码: {func}, 从站地址: {slave}, 寄存器地址: 0x{addr:04X}, 返回值: {trans.result}")
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
        # 对于文件记录操作，使用一个特殊的地址值，便于日志识别
        # 使用0x1000作为文件记录操作的标识地址
        file_record_address = 0x1000 + file_number
        return self._enqueue("read_file_record", slave, file_record_address, [file_number, record_start, record_length])

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
        
        try:
            # 使用原始Modbus客户端发送自定义功能码请求
            if not self.client:
                raise ModbusException("Modbus客户端未连接")
            
            # 构建原始请求帧
            # 功能码0x14：读文件记录
            # 请求格式：[从站地址][功能码][字节数][参考类型][文件号][记录号][记录长度][CRC]
            request_data = bytearray()
            request_data.append(slave)  # 从站地址
            request_data.append(0x14)  # 功能码
            
            # 计算数据长度：每个记录7字节
            byte_count = 7
            request_data.append(byte_count)
            
            # 添加记录数据
            request_data.extend(struct.pack('>B', 0x06))  # 参考类型
            request_data.extend(struct.pack('>H', file_number))  # 文件号
            request_data.extend(struct.pack('>H', record_start))  # 记录号
            request_data.extend(struct.pack('>H', record_length))  # 记录长度
            
            # 计算CRC
            try:
                from pymodbus.utilities import crc
                crc_value = crc(request_data)
            except ImportError:
                # 如果新版本pymodbus中没有crc函数，使用自定义实现
                crc_value = self._calculate_crc(request_data)
            request_data.extend(struct.pack('<H', crc_value))  # 小端序CRC
            
            # 添加调试信息
            print(f"[DEBUG] 请求帧: {request_data.hex()}")
            print(f"[DEBUG] 请求参数: slave={slave}, file_number={file_number}, record_start={record_start}, record_length={record_length}")
            
            # 根据客户端类型发送请求
            # 检查是否是TCP客户端（通过检查socket是否是socket.socket类型）
            if hasattr(self.client, 'socket') and hasattr(self.client.socket, 'send') and hasattr(self.client.socket, 'recv'):
                # 如果是TCP客户端
                try:
                    # 尝试获取事务ID
                    if hasattr(self.client, 'transaction') and hasattr(self.client.transaction, 'next_tid'):
                        transaction_id = self.client.transaction.next_tid()
                    elif hasattr(self.client, 'transaction') and callable(self.client.transaction):
                        transaction_id = self.client.transaction()
                    else:
                        # 使用简单计数器作为事务ID
                        if not hasattr(self, '_transaction_id'):
                            self._transaction_id = 0
                        self._transaction_id = (self._transaction_id + 1) % 65536
                        transaction_id = self._transaction_id
                except Exception:
                    # 如果获取事务ID失败，使用随机值
                    import random
                    transaction_id = random.randint(1, 65535)
                
                # 构建Modbus TCP帧
                mbap_header = struct.pack('>HHHB', 
                    transaction_id,  # 事务ID
                    0,              # 协议ID (Modbus = 0)
                    len(request_data) - 1,  # 长度 (不包括从站地址)
                    slave           # 单元ID
                )
                
                # 发送请求
                self.client.socket.send(mbap_header + bytes(request_data[1:]))  # 不包含从站地址
                
                # 接收响应
                response_data = self.client.socket.recv(1024)
                
                # 解析响应
                if len(response_data) < 8:
                    raise ModbusException("响应数据太短")
                
                # 提取MBAP头部
                resp_transaction_id = struct.unpack('>H', response_data[0:2])[0]
                resp_protocol_id = struct.unpack('>H', response_data[2:4])[0]
                resp_length = struct.unpack('>H', response_data[4:6])[0]
                resp_unit_id = response_data[6]
                
                # 检查MBAP头部
                if resp_protocol_id != 0:
                    raise ModbusException(f"无效的协议ID: {resp_protocol_id}")
                
                if resp_unit_id != slave:
                    raise ModbusException(f"单元ID不匹配: 期望{slave}, 实际{resp_unit_id}")
                
                # 提取功能码和数据
                if len(response_data) < 7:
                    raise ModbusException("响应数据太短，无法包含功能码")
                
                function_code = response_data[7]
                
                if function_code == 0x14 | 0x80:  # 错误响应
                    error_code = response_data[8] if len(response_data) > 8 else 0
                    raise ModbusException(f"Modbus错误响应: 错误码{error_code}")
                
                if function_code != 0x14:
                    raise ModbusException(f"功能码不匹配: 期望0x14, 实际{function_code}")
                
                # 解析文件记录响应
                data_length = response_data[8] if len(response_data) > 8 else 0
                if len(response_data) < 9 + data_length:
                    raise ModbusException("响应数据不完整")
                
                # 提取数据部分
                response_payload = response_data[9:9+data_length]
                
                # 解析文件记录数据
                return self._parse_file_record_response_data(response_payload)
            elif hasattr(self.client, 'socket'):
                # 如果是RTU客户端
                # 清空输入缓冲区
                if hasattr(self.client.socket, 'flushInput'):
                    self.client.socket.flushInput()
                elif hasattr(self.client.socket, 'reset_input_buffer'):
                    self.client.socket.reset_input_buffer()
                
                # 发送请求
                self.client.socket.write(request_data)
                
                # 等待响应
                time.sleep(0.1)  # 给设备一些时间处理请求
                
                # 接收响应
                response_data = bytearray()
                if hasattr(self.client.socket, 'inWaiting'):
                    bytes_to_read = self.client.socket.inWaiting()
                elif hasattr(self.client.socket, 'in_waiting'):
                    bytes_to_read = self.client.socket.in_waiting()
                else:
                    bytes_to_read = 0
                
                if bytes_to_read > 0:
                    response_data.extend(self.client.socket.read(bytes_to_read))
                
                # 如果没有数据，再等待一段时间
                if len(response_data) == 0:
                    time.sleep(0.2)
                    if hasattr(self.client.socket, 'inWaiting'):
                        bytes_to_read = self.client.socket.inWaiting()
                    elif hasattr(self.client.socket, 'in_waiting'):
                        bytes_to_read = self.client.socket.in_waiting()
                    else:
                        bytes_to_read = 0
                    
                    if bytes_to_read > 0:
                        response_data.extend(self.client.socket.read(bytes_to_read))
                
                if len(response_data) < 3:  # 最小响应: 地址+功能码+CRC
                    raise ModbusException("响应数据太短")
                
                # 检查从站地址
                if response_data[0] != slave:
                    print(f"[WARN] 从站地址不匹配: 期望{slave}, 实际{response_data[0]}")
                    # 记录更详细的地址信息用于诊断
                    print(f"[DEBUG] 批次信息: 文件号={file_number}, 记录起始={record_start}, 记录长度={record_length}")
                    print(f"[DEBUG] 完整响应数据: {response_data.hex()}")
                    
                    # 对于第二批及以后的数据，某些设备可能会返回0xFF作为广播地址
                    # 如果地址不匹配但数据看起来有效，尝试继续处理
                    if response_data[0] == 0xFF:
                        print(f"[DEBUG] 检测到广播地址0xFF，尝试继续处理数据")
                    else:
                        # 对于非0xFF的地址不匹配，仍然抛出异常
                        # 添加批次信息到异常中，便于诊断
                        raise ModbusException(f"从站地址不匹配: 期望{slave}, 实际{response_data[0]} (文件号={file_number}, 偏移={record_start})")
                
                # 检查功能码
                function_code = response_data[1]
                
                if function_code == 0x14 | 0x80:  # 错误响应
                    error_code = response_data[2] if len(response_data) > 2 else 0
                    raise ModbusException(f"Modbus错误响应: 错误码{error_code}")
                
                if function_code != 0x14:
                    raise ModbusException(f"功能码不匹配: 期望0x14, 实际{function_code}")
                
                # 验证CRC
                if len(response_data) >= 3:
                    received_crc = struct.unpack('<H', response_data[-2:])[0]
                    try:
                        from pymodbus.utilities import crc
                        calculated_crc = crc(response_data[:-2])
                    except ImportError:
                        # 如果新版本pymodbus中没有crc函数，使用自定义实现
                        calculated_crc = self._calculate_crc(response_data[:-2])
                    
                    # 添加调试信息
                    print(f"[DEBUG] CRC校验: 接收={received_crc:04X}, 计算={calculated_crc:04X}")
                    print(f"[DEBUG] 响应数据长度: {len(response_data)}")
                    print(f"[DEBUG] 响应数据: {response_data.hex()}")
                    
                    # 严格校验CRC，不再跳过CRC校验
                    if received_crc != calculated_crc:
                        raise ModbusException(f"CRC校验失败: 接收={received_crc:04X}, 计算={calculated_crc:04X}")
                
                # 解析文件记录响应
                print(f"[DEBUG] 开始解析响应数据，总长度: {len(response_data)}")
                
                if len(response_data) < 3:
                    # 严格检查响应数据完整性
                    raise ModbusException(f"响应数据太短: 期望至少3字节, 实际{len(response_data)}字节")
                
                data_length = response_data[2] if len(response_data) > 2 else 0
                print(f"[DEBUG] 数据长度字段: {data_length}, 期望总长度: {4+data_length+2}, 实际长度: {len(response_data)}")
                
                # 根据文档示例，响应格式为: [地址][功能码][字节数][参考类型][数据...][CRC]
                # 实际数据载荷应该从参考类型之后开始，不包含参考类型字段
                if len(response_data) >= 5:  # 至少需要地址、功能码、字节数、参考类型、CRC
                    # 计算实际数据载荷长度
                    # 总数据长度 = data_length，包含参考类型和实际数据
                    # 实际数据长度 = 总数据长度 - 1（参考类型字节）
                    actual_payload_length = data_length
                    # 检查数据长度是否足够
                    expected_length = 4 + actual_payload_length + 2  # 地址+功能码+字节数+参考类型+数据+CRC
                    if len(response_data) < expected_length:
                        raise ModbusException(f"响应数据不完整: 期望{expected_length}字节, 实际{len(response_data)}字节")
                    
                    # 数据载荷从参考类型之后开始（跳过地址、功能码、字节数、参考类型）
                    response_payload = response_data[4:4+actual_payload_length]
                    print(f"[DEBUG] 提取数据载荷: 长度={actual_payload_length}, 内容: {response_payload.hex()}")
                    
                    # 解析文件记录数据
                    result = self._parse_file_record_response_data(response_payload)
                    print(f"[DEBUG] 成功解析文件记录数据，结果: {result}")
                    return result
                else:
                    raise ModbusException(f"响应数据不完整: 期望长度至少5字节, 实际长度={len(response_data)}字节")
            else:
                # 如果没有直接访问方式，尝试使用其他方法
                raise ModbusException("无法直接访问Modbus客户端")
                
        except Exception as e:
            raise ModbusException(f"文件读取失败: {e}")
    
    def _parse_file_record_response_data(self, data: bytes) -> List[int]:
        """
        解析文件记录响应数据
        
        Args:
            data: 响应数据部分（从参考类型之后开始）
            
        Returns:
            寄存器值列表
        """
        print(f"[DEBUG] 开始解析文件记录响应数据，输入数据长度: {len(data)}")
        print(f"[DEBUG] 输入数据内容: {data.hex()}")
        
        # 严格检查数据长度
        if len(data) < 2:
            print(f"[DEBUG] 响应数据太短: {len(data)}字节，至少需要2字节")
            raise ModbusException(f"响应数据太短: 期望至少2字节, 实际{len(data)}字节")
        
        # 检查数据长度是否为偶数（每个寄存器2字节）
        if len(data) % 2 != 0:
            print(f"[DEBUG] 响应数据长度不是偶数: {len(data)}字节")
            raise ModbusException(f"响应数据长度不是偶数: {len(data)}字节")
        
        # 将数据转换为寄存器列表 (每2字节一个寄存器)
        registers = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                register_value = struct.unpack('>H', data[i:i+2])[0]
                registers.append(register_value)
                print(f"[DEBUG] 解析寄存器 {len(registers)-1}: 0x{register_value:04X} ({register_value})")
            else:
                # 这种情况理论上不会发生，因为前面已经检查了长度为偶数
                raise ModbusException(f"数据解析错误: 无法解析字节{i}")
        
        print(f"[DEBUG] 解析完成，共得到 {len(registers)} 个寄存器")
        return registers
    
    def _calculate_crc(self, data: bytes) -> int:
        """
        计算Modbus RTU CRC校验值
        
        Args:
            data: 要计算CRC的数据
            
        Returns:
            CRC16校验值
        """
        crc = 0xFFFF
        
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        
        return crc
    
    def _parse_file_record_response(self, response) -> List[int]:
        """解析文件记录响应数据"""
        try:
            # 导入必要的类
            from pymodbus.pdu.file_message import ReadFileRecordResponse, FileRecord
            
            # 如果响应已经是ReadFileRecordResponse对象
            if isinstance(response, ReadFileRecordResponse):
                # 从记录中提取数据并转换为寄存器列表
                registers = []
                for record in response.records:
                    if hasattr(record, 'record_data') and record.record_data:
                        # 将字节数据转换为寄存器列表（每2字节一个寄存器）
                        data = record.record_data
                        for i in range(0, len(data), 2):
                            if i + 1 < len(data):
                                # 大端序转换
                                reg = (data[i] << 8) | data[i+1]
                                registers.append(reg)
                return registers
            
            # 如果响应有registers属性，直接返回
            if hasattr(response, 'registers'):
                return response.registers
            
            # 如果响应有bits属性，转换为寄存器
            if hasattr(response, 'bits') and response.bits:
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
            
        except Exception as e:
            print(f"解析文件记录响应失败: {e}")
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

#!/usr/bin/env python3
# flake8: noqa
"""
串口通信管理器
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .modbus_rtu_master import ModbusRtuMaster, ModbusException

logger = logging.getLogger(__name__)


@dataclass
class SerialConfig:
    """串口配置"""
    port_name: str
    baudrate: int
    databits: int
    stopbit: int
    parity: str
    slave_address: int
    timeout: float
    polling_interval: float


@dataclass
class DeviceData:
    """设备数据"""
    status_registers: Optional[List[int]] = None
    analog_registers: Optional[List[int]] = None
    control_registers: Optional[List[int]] = None
    coils: Optional[List[bool]] = None
    discrete_inputs: Optional[List[bool]] = None
    timestamp: float = 0.0


class SerialManager:
    """串口通信管理器"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.hmi_master: Optional[ModbusRtuMaster] = None
        self.scada_master: Optional[ModbusRtuMaster] = None
        self.scada_config: Optional[SerialConfig] = None
        self.hmi_config: Optional[SerialConfig] = None
        self.is_running = False
        self.hmi_polling_thread: Optional[threading.Thread] = None
        self.scada_polling_thread: Optional[threading.Thread] = None
        self.hmi_data_callbacks = []
        self.scada_data_callbacks = []
        self.error_callbacks = []
        self.hmi_current_data: Optional[DeviceData] = None
        self.scada_current_data: Optional[DeviceData] = None

    async def initialize(self):
        """初始化串口管理器"""
        try:
            # 加载SCADA串口配置
            scada_config = self.config_manager.get_section('SCADA串口配置')
            self.scada_config = SerialConfig(
                port_name=scada_config.get('port_name', 'COM2'),
                baudrate=int(scada_config.get('baudrate', 9600)),
                databits=int(scada_config.get('databits', 8)),
                stopbit=int(scada_config.get('stopbit', 1)),
                parity=self._convert_parity(int(scada_config.get('parity', 0))),
                slave_address=int(scada_config.get('slave_address', 0x5e)),
                timeout=float(scada_config.get('timeout', 5.0)),
                polling_interval=float(scada_config.get('polling_interval', 1.0))
            )

            # 加载HMI串口配置
            hmi_config = self.config_manager.get_section('HMI串口配置')
            self.hmi_config = SerialConfig(
                port_name=hmi_config.get('port_name', 'COM1'),
                baudrate=int(hmi_config.get('baudrate', 9600)),
                databits=int(hmi_config.get('databits', 8)),
                stopbit=int(hmi_config.get('stopbit', 1)),
                parity=self._convert_parity(int(hmi_config.get('parity', 0))),
                slave_address=int(hmi_config.get('slave_address', 0x10)),
                timeout=float(hmi_config.get('timeout', 5.0)),
                polling_interval=float(hmi_config.get('polling_interval', 1.0))
            )

            logger.info("串口配置加载完成")
            logger.info(f"SCADA配置: {self.scada_config}")
            logger.info(f"HMI配置: {self.hmi_config}")

            # 验证轮询间隔范围
            if not (0.3 <= self.scada_config.polling_interval <= 10.0):
                logger.warning(f"SCADA轮询间隔{self.scada_config.polling_interval}超出范围0.3-10.0，使用默认值1.0")
                self.scada_config.polling_interval = 1.0

            if not (0.3 <= self.hmi_config.polling_interval <= 10.0):
                logger.warning(f"HMI轮询间隔{self.hmi_config.polling_interval}超出范围0.3-10.0，使用默认值1.0")
                self.hmi_config.polling_interval = 1.0

            return True

        except Exception as e:
            logger.error(f"串口管理器初始化失败: {e}")
            return False

    def _convert_parity(self, parity_code: int) -> str:
        """转换奇偶校验码"""
        parity_map = {0: 'N', 1: 'O', 2: 'E'}
        return parity_map.get(parity_code, 'N')

    def start_polling(self):
        """开始轮询"""
        if self.is_running:
            logger.warning("轮询已在进行中")
            return

        # 创建Modbus主站实例
        self.hmi_master = ModbusRtuMaster()
        self.scada_master = ModbusRtuMaster()

        # 尝试连接HMI串口
        if not self._connect_hmi_serial():
            logger.error("HMI串口连接失败")
            return False

        # 尝试连接SCADA串口
        if not self._connect_scada_serial():
            logger.warning("SCADA串口连接失败，将继续使用HMI串口")

        self.is_running = True
        
        # 启动HMI串口轮询
        self.hmi_polling_thread = threading.Thread(target=self._hmi_polling_worker, daemon=True)
        self.hmi_polling_thread.start()
        
        # 启动SCADA串口轮询
        self.scada_polling_thread = threading.Thread(target=self._scada_polling_worker, daemon=True)
        self.scada_polling_thread.start()
        
        logger.info("串口轮询已启动")
        return True

    def stop_polling(self):
        """停止轮询"""
        self.is_running = False
        
        # 停止HMI串口
        if self.hmi_master:
            self.hmi_master.close()
        if self.hmi_polling_thread and self.hmi_polling_thread.is_alive():
            self.hmi_polling_thread.join(timeout=5.0)
            
        # 停止SCADA串口
        if self.scada_master:
            self.scada_master.close()
        if self.scada_polling_thread and self.scada_polling_thread.is_alive():
            self.scada_polling_thread.join(timeout=5.0)
            
        logger.info("串口轮询已停止")

    def _connect_hmi_serial(self) -> bool:
        """连接HMI串口"""
        if not self.hmi_master:
            return False

        config = self.hmi_config

        try:
            success = self.hmi_master.open(
                port=config.port_name,
                baudrate=config.baudrate,
                bytesize=config.databits,
                parity=config.parity,
                stopbits=config.stopbit,
                timeout=config.timeout
            )

            if success:
                logger.info(f"成功连接到HMI串口 {config.port_name}")
                return True
            else:
                logger.error(f"无法连接到HMI串口 {config.port_name}")
                return False

        except Exception as e:
            logger.error(f"连接HMI串口异常: {e}")
            return False

    def _connect_scada_serial(self) -> bool:
        """连接SCADA串口"""
        if not self.scada_master:
            return False

        config = self.scada_config

        try:
            success = self.scada_master.open(
                port=config.port_name,
                baudrate=config.baudrate,
                bytesize=config.databits,
                parity=config.parity,
                stopbits=config.stopbit,
                timeout=config.timeout
            )

            if success:
                logger.info(f"成功连接到SCADA串口 {config.port_name}")
                return True
            else:
                logger.error(f"无法连接到SCADA串口 {config.port_name}")
                return False

        except Exception as e:
            logger.error(f"连接SCADA串口异常: {e}")
            return False

    def _hmi_polling_worker(self):
        """HMI串口轮询工作线程"""
        last_poll_time = 0
        data_type_sequence = ['system_status', 'analog_data']  # switch_io已合并到system_status中，不再单独处理
        data_type_index = 0
        connection_error_count = 0
        max_connection_errors = 3

        while self.is_running:
            try:
                current_time = time.time()

                # 检查是否到达轮询间隔
                if current_time - last_poll_time >= self.hmi_config.polling_interval:
                    # 检查串口连接状态
                    if not self.hmi_master or not self.hmi_master.is_open():
                        logger.warning("HMI串口未连接，尝试重新连接")
                        if not self._connect_hmi_serial():
                            connection_error_count += 1
                            if connection_error_count >= max_connection_errors:
                                logger.error("HMI串口连接失败次数过多，暂停轮询")
                                # 暂停轮询一段时间
                                time.sleep(10.0)
                                connection_error_count = 0
                            continue
                        else:
                            connection_error_count = 0
                            logger.info("HMI串口重新连接成功")

                    # 读取HMI设备数据
                    device_data = self._read_hmi_device_data()

                    if device_data:
                        self.hmi_current_data = device_data

                        # 转换数据格式并发送给WebSocket后端
                        data_type = data_type_sequence[data_type_index]
                        ws_data = self._convert_to_websocket_format(data_type, device_data)

                        # 通知HMI数据回调，传递已经转换好的数据
                        for callback in self.hmi_data_callbacks:
                            try:
                                callback(data_type, ws_data)
                            except Exception as e:
                                logger.error(f"HMI数据回调异常: {e}")

                        # 更新数据类型索引
                        data_type_index = (data_type_index + 1) % len(data_type_sequence)
                    else:
                        # 读取数据失败，增加错误计数
                        connection_error_count += 1
                        if connection_error_count >= max_connection_errors:
                            logger.error("HMI数据读取失败次数过多，暂停轮询")
                            # 暂停轮询一段时间
                            time.sleep(10.0)
                            connection_error_count = 0
                        
                        # 重要修复：在读取数据失败时，不要调用数据回调
                        # 避免触发数据库插入操作

                    last_poll_time = current_time

                # 短暂休眠避免CPU占用过高
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"HMI轮询工作线程异常: {e}")
                # 通知错误回调
                for callback in self.error_callbacks:
                    try:
                        callback(e)
                    except Exception as cb_error:
                        logger.error(f"错误回调异常: {cb_error}")

                # 错误后短暂休眠
                time.sleep(1.0)

    def _scada_polling_worker(self):
        """SCADA串口轮询工作线程 - 从站设备不主动轮询"""
        # SCADA作为从站设备，不应该主动发起Modbus请求
        # 这里只维护连接状态，不进行数据轮询
        
        while self.is_running:
            try:
                # 检查SCADA串口连接状态
                if self.scada_master and self.scada_master.is_open():
                    # SCADA从站设备连接正常，但不需要主动读取数据
                    # 从站设备应该等待主站设备的请求
                    pass
                else:
                    # 尝试重新连接SCADA串口
                    if not self._connect_scada_serial():
                        logger.warning("SCADA串口连接失败")
                
                # 短暂休眠避免CPU占用过高
                time.sleep(1.0)  # 从站设备检查间隔可以更长

            except Exception as e:
                logger.error(f"SCADA轮询工作线程异常: {e}")
                # 通知错误回调
                for callback in self.error_callbacks:
                    try:
                        callback(e)
                    except Exception as cb_error:
                        logger.error(f"错误回调异常: {cb_error}")

                # 错误后短暂休眠
                time.sleep(2.0)

    def _read_hmi_device_data(self) -> Optional[DeviceData]:
        """读取HMI设备数据 - 读取状态寄存器和模拟量寄存器"""
        if not self.hmi_master or not self.hmi_master.is_open():
            # print("❌ [HMI数据读取] HMI串口未连接或未开启")
            return None

        try:
            config = self.hmi_config
            # print(f"🔍 [HMI数据读取] 开始读取HMI设备数据，从站地址: {config.slave_address}")

            # 读取状态寄存器
            status_count = int(self.config_manager.get_section('HMI系统状态寄存器').get('status_register_count', 0x21))
            status_start = int(
                self.config_manager.get_section('HMI系统状态寄存器').get('status_register_start_address', 0x0000))
            # print(f"📊 [HMI状态寄存器] 地址: 0x{status_start:04X}, 数量: {status_count}")
            status_registers = self.hmi_master.read_holding_registers(
                slave=config.slave_address,
                address=status_start,
                count=status_count
            )
            # print(f"✅ [HMI状态寄存器] 读取成功，数据长度: {len(status_registers) if status_registers else 0}")

            # 读取模拟量寄存器
            analog_count = int(self.config_manager.get_section('HMI系统模拟量寄存器').get('analog_register_count', 31))
            analog_start = int(
                self.config_manager.get_section('HMI系统模拟量寄存器').get('analog_register_start_address', 0x0005))
            # print(f"📊 [HMI模拟量寄存器] 地址: 0x{analog_start:04X}, 数量: {analog_count}")
            analog_registers = self.hmi_master.read_holding_registers(
                slave=config.slave_address,
                address=analog_start,
                count=analog_count
            )
            # print(f"✅ [HMI模拟量寄存器] 读取成功，数据长度: {len(analog_registers) if analog_registers else 0}")

            # print(f"🎯 [HMI数据读取] 状态寄存器和模拟量寄存器读取完成")
            return DeviceData(
                status_registers=status_registers,
                analog_registers=analog_registers,
                control_registers=None,  # 不再读取控制参数寄存器
                coils=None,              # 线圈状态（设备不支持直接读取）
                discrete_inputs=None,    # 离散输入（设备不支持直接读取）
                timestamp=time.time()
            )

        except ModbusException as e:
            # print(f"❌ [HMI数据读取] Modbus通信错误: {e}")
            logger.error(f"HMI Modbus通信错误: {e}")
            return None
        except Exception as e:
            # print(f"❌ [HMI数据读取] 异常错误: {e}")
            logger.error(f"读取HMI设备数据异常: {e}")
            return None

    # SCADA作为从站设备，不应该有主动读取数据的方法
    # 从站设备应该等待主站设备的请求，然后响应数据
    # 因此移除_read_scada_device_data方法

    def register_hmi_data_callback(self, callback):
        """注册HMI数据回调"""
        self.hmi_data_callbacks.append(callback)

    def register_scada_data_callback(self, callback):
        """注册SCADA数据回调"""
        self.scada_data_callbacks.append(callback)

    def register_data_callback(self, callback):
        """注册数据回调（兼容旧版本）"""
        self.hmi_data_callbacks.append(callback)

    def register_error_callback(self, callback):
        """注册错误回调"""
        self.error_callbacks.append(callback)

    def get_hmi_current_data(self) -> Optional[DeviceData]:
        """获取HMI当前数据"""
        return self.hmi_current_data

    def get_scada_current_data(self) -> Optional[DeviceData]:
        """获取SCADA当前数据"""
        return self.scada_current_data

    def get_current_data(self) -> Optional[DeviceData]:
        """获取当前数据（兼容旧版本）"""
        return self.hmi_current_data

    def read_fault_record(self, device_type: str, record_id: int, start_offset: int = 0, length: int = 125) -> Optional[List[int]]:
        """
        读取故障录波记录
        
        Args:
            device_type: 设备类型 ('hmi' 或 'scada')
            record_id: 记录编号 (0=最新记录，1=上一条记录，以此类推)
            start_offset: 记录起始偏移地址（寄存器偏移）
            length: 要读取的寄存器数量
            
        Returns:
            读取到的寄存器数据列表，失败返回None
        """
        try:
            if device_type.lower() == 'hmi':
                master = self.hmi_master
                config = self.hmi_config
            elif device_type.lower() == 'scada':
                master = self.scada_master
                config = self.scada_config
            else:
                logger.error(f"未知的设备类型: {device_type}")
                return None

            if not master or not master.is_open():
                logger.error(f"{device_type.upper()}串口未连接")
                return None

            if not config:
                logger.error(f"{device_type.upper()}配置未加载")
                return None

            # 使用功能码0x14读取文件记录
            registers = master.read_file_record(
                slave=config.slave_address,
                file_number=record_id,
                record_start=start_offset,
                record_length=length
            )

            logger.info(f"成功读取{device_type.upper()}故障录波记录: 记录ID={record_id}, 长度={len(registers)}")
            return registers

        except Exception as e:
            logger.error(f"读取{device_type.upper()}故障录波记录失败: {e}")
            return None

    def _convert_to_websocket_format(self, data_type: str, device_data: DeviceData) -> dict:
        """将设备数据转换为WebSocket格式"""
        if data_type == 'system_status':
            # 系统状态数据格式
            return self._convert_system_status(device_data)
        elif data_type == 'analog_data':
            # 模拟量数据格式
            return self._convert_analog_data(device_data)
        # switch_io数据类型已合并到system_status中，不再单独处理
        else:
            return {}

    def _convert_system_status(self, device_data: DeviceData) -> dict:
        """转换系统状态数据"""
        if not device_data.status_registers:
            return {}

        # 按照配置文件解析所有5个状态寄存器
        status_data = {}
        
        # 寄存器0x0000: HMI系统状态点表
        if len(device_data.status_registers) > 0:
            value = device_data.status_registers[0]
            system_status = {}
            for bit_pos in range(16):
                bit_value = (value >> bit_pos) & 1
                system_status[f"bit{bit_pos}"] = bit_value
            status_data["system_status"] = system_status
        
        # 寄存器0x0001: HMI主模块IGBT光纤状态
        if len(device_data.status_registers) > 1:
            value = device_data.status_registers[1]
            igbt_status = {}
            for bit_pos in range(16):
                bit_value = (value >> bit_pos) & 1
                igbt_status[f"bit{bit_pos}"] = bit_value
            status_data["igbt_fiber_status"] = igbt_status
        
        # 寄存器0x0002: HMI开关量输入点表
        if len(device_data.status_registers) > 2:
            value = device_data.status_registers[2]
            input_status = {}
            for bit_pos in range(16):
                bit_value = (value >> bit_pos) & 1
                input_status[f"bit{bit_pos}"] = bit_value
            status_data["switch_input"] = input_status
        
        # 寄存器0x0003: HMI开关量输出点表
        if len(device_data.status_registers) > 3:
            value = device_data.status_registers[3]
            output_status = {}
            for bit_pos in range(16):
                bit_value = (value >> bit_pos) & 1
                output_status[f"bit{bit_pos}"] = bit_value
            status_data["switch_output"] = output_status
        
        # 寄存器0x0004: HMI故障点表
        if len(device_data.status_registers) > 4:
            value = device_data.status_registers[4]
            fault_status = {}
            for bit_pos in range(16):
                bit_value = (value >> bit_pos) & 1
                fault_status[f"bit{bit_pos}"] = bit_value
            status_data["fault_status"] = fault_status

        return status_data

    def _convert_analog_data(self, device_data: DeviceData) -> list:
        """转换模拟量数据"""
        if not device_data.analog_registers:
            return []

        analog_data = []

        # 从配置文件获取模拟量参数映射
        analog_mapping = self.config_manager.get_analog_parameters_mapping()

        for i, reg_value in enumerate(device_data.analog_registers):
            if i < len(analog_mapping):
                mapping = analog_mapping[i]
                
                # 将无符号16位寄存器值转换为有符号整数
                # Modbus寄存器值为16位有符号整数（-32768到32767）
                if reg_value > 32767:  # 如果大于0x7FFF，表示负数
                    signed_value = reg_value - 65536  # 转换为有符号数
                else:
                    signed_value = reg_value  # 正数直接保持
                
                # 根据配置的转换系数进行物理值转换
                scale = mapping.get("scale", 10.0)
                physical_value = signed_value / scale

                analog_data.append({
                    "reg_addr": mapping["reg_addr"],
                    "name": mapping["name"],
                    "raw_value": reg_value,
                    "signed_value": signed_value,
                    "physical_value": round(physical_value, 1),
                    "unit": mapping["unit"]
                })

        return analog_data



    def _convert_scada_data(self, device_data: DeviceData) -> dict:
        """转换SCADA数据"""
        scada_data = {
            "type": "scada_data",
            "timestamp": device_data.timestamp,
            "status_registers": device_data.status_registers,
            "analog_registers": device_data.analog_registers,
            "coils": device_data.coils,
            "discrete_inputs": device_data.discrete_inputs
        }
        return scada_data

    def write_control_register(self, address: int, value: int) -> bool:
        """写入控制寄存器（HMI串口）"""
        if not self.hmi_master or not self.hmi_master.is_open():
            return False

        try:
            config = self.hmi_config
            success = self.hmi_master.write_single_register(
                slave=config.slave_address,
                address=address,
                value=value
            )
            return success
        except Exception as e:
            logger.error(f"写入控制寄存器失败: {e}")
            return False

    def write_coil(self, address: int, value: bool) -> bool:
        """写入线圈（HMI串口）"""
        if not self.hmi_master or not self.hmi_master.is_open():
            return False

        try:
            config = self.hmi_config
            success = self.hmi_master.write_single_coil(
                slave=config.slave_address,
                address=address,
                value=value
            )
            return success
        except Exception as e:
            logger.error(f"写入线圈失败: {e}")
            return False

    def write_scada_control_register(self, address: int, value: int) -> bool:
        """写入SCADA控制寄存器"""
        if not self.scada_master or not self.scada_master.is_open():
            return False

        try:
            config = self.scada_config
            success = self.scada_master.write_single_register(
                slave=config.slave_address,
                address=address,
                value=value
            )
            return success
        except Exception as e:
            logger.error(f"写入SCADA控制寄存器失败: {e}")
            return False

    def write_scada_coil(self, address: int, value: bool) -> bool:
        """写入SCADA线圈"""
        if not self.scada_master or not self.scada_master.is_open():
            return False

        try:
            config = self.scada_config
            success = self.scada_master.write_single_coil(
                slave=config.slave_address,
                address=address,
                value=value
            )
            return success
        except Exception as e:
            logger.error(f"写入SCADA线圈失败: {e}")
            return False
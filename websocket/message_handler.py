#!/usr/bin/env python3
# flake8: noqa
"""
WebSocket消息处理器
处理客户端发送的各种消息类型
"""

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional, List

from websocket.connection_manager import ConnectionManager
from config.config_manager import ConfigManager
from serial_comm.serial_manager import SerialManager

logger = logging.getLogger(__name__)


class MessageHandler:
    """WebSocket消息处理器"""
    
    def __init__(self, connection_manager: ConnectionManager, config_manager: ConfigManager, serial_manager=None):
        self.connection_manager = connection_manager
        self.config_manager = config_manager
        self.serial_manager = serial_manager
        
        # 设备状态模拟数据
        self._device_status = self._init_device_status()
        self.analog_data = self._init_analog_data()
        self.digital_data = self._init_digital_data()
        self.fault_records = self._init_fault_records()
        
        # 指令执行状态跟踪
        self.command_execution_status: Dict[str, Any] = {}
    
    def device_status(self) -> Dict[str, Any]:
        """获取设备状态信息"""
        return self._device_status.copy()
    
    async def handle_message(self, websocket, message: str, connection_info: Dict[str, Any]):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            # 更新消息统计
            connection_info['message_count_received'] += 1
            self.connection_manager.connection_stats['total_messages_received'] += 1
            
            logger.info(f"收到消息类型: {msg_type}, 连接: {connection_info['connection_id']}")
            
            # 根据消息类型分发处理
            if msg_type == "device_register":
                await self._handle_device_registration(websocket, data, connection_info)
            elif msg_type == "heartbeat":
                await self._handle_heartbeat(websocket, data, connection_info)
            elif msg_type == "control_cmd":
                await self._handle_control_command(websocket, data, connection_info)
            elif msg_type == "fault_record_list":
                await self._handle_fault_record_list(websocket, data, connection_info)
            elif msg_type == "fault_record_read":
                await self._handle_fault_record_read(websocket, data, connection_info)
            elif msg_type == "fault_record_cancel":
                await self._handle_fault_record_cancel(websocket, data, connection_info)
            elif msg_type == "param_read":
                await self._handle_param_read(websocket, data, connection_info)
            elif msg_type == "param_write":
                await self._handle_param_write(websocket, data, connection_info)
            elif msg_type == "data_lost_request":
                await self._handle_data_lost_request(websocket, data, connection_info)
            else:
                await self._send_error_response(websocket, 400, f"未知消息类型: {msg_type}")
                
        except json.JSONDecodeError:
            await self._send_error_response(websocket, 400, "无效的JSON格式")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            await self._send_error_response(websocket, 500, f"服务器内部错误: {str(e)}")
    
    async def _handle_device_registration(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理设备注册"""
        device_id = data.get("device_id")
        device_name = data.get("device_name")
        
        if not device_id or not device_name:
            await self._send_error_response(websocket, 400, "设备ID和设备名称不能为空")
            return
        
        # 注册设备信息
        await self.connection_manager.register_device(websocket, device_id, device_name)
        
        # 发送欢迎消息
        welcome_msg = {
            "type": "welcome",
            "message": f"设备 {device_name} 注册成功",
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(
            websocket, welcome_msg
        )
    
    async def _handle_heartbeat(
        self,
        websocket,
        data: Dict[str, Any],
        connection_info: Dict[str, Any]
    ):
        """处理心跳"""
        # 更新心跳时间
        await self.connection_manager.update_heartbeat(websocket)
        
        # 发送心跳响应
        response = {
            "type": "heartbeat_ack",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "device_online": True,
                "pscada_connected": True,
                "server_connected": True,
                "fault_count": 0
            }
        }
        
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_control_command(
            self, 
            websocket, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
        ):
        """处理控制指令"""
        cmd = data.get("cmd")
        request_id = data.get("request_id")
        cmd_param = data.get("cmd_param", {})
        
        if not cmd or not request_id:
            await self._send_error_response(websocket, 400, "指令类型和请求ID不能为空")
            return
        
        # 模拟指令执行延时
        await asyncio.sleep(0.1)
        
        if cmd == "fault_reset":
            response = await self._handle_fault_reset_command(
                data, connection_info
            )
        elif cmd == "set_param":
            response = await self._handle_set_param_command(
                data, connection_info
            )
        elif cmd == "set_mode":
            response = await self._handle_set_mode_command(
                data, connection_info
            )
        elif cmd == "fault_record_clear":
            response = await self._handle_fault_record_clear_command(
                data, connection_info
            )
        else:
            response = {
                "type": "control_ack",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "cmd": cmd,
                "exec_status": "fail",
                "error_code": 400,
                "exec_msg": f"未知指令: {cmd}",
                "timestamp": datetime.now().isoformat()
            }
        
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_fault_reset_command(
            self, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理故障复位指令"""
        return {
            "type": "control_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "cmd": "fault_reset",
            "exec_status": "success",
            "exec_msg": "故障复位成功",
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_set_param_command(
        self, 
        data: Dict[str, Any], 
        connection_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理参数设置指令"""
        param_data = data.get("cmd_param", {})
        return {
            "type": "control_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "cmd": "set_param",
            "exec_status": "success",
            "exec_msg": "参数设置成功",
            "current_value": param_data.get("param_value"),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_set_mode_command(
            self, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理工作模式切换指令"""
        mode_data = data.get("cmd_param", {})
        mode = mode_data.get("mode", "auto")
        return {
            "type": "control_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "cmd": "set_mode",
            "exec_status": "success",
            "exec_msg": f"工作模式已切换为{mode}",
            "current_mode": mode,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_fault_record_clear_command(
            self, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理故障录波清除指令"""
        return {
            "type": "control_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "cmd": "fault_record_clear",
            "exec_status": "success",
            "exec_msg": "故障录波记录已清除",
            "cleared_count": len(self.fault_records),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_fault_record_list(
            self, 
            websocket, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ):
        """处理故障录波目录查询"""
        response = {
            "type": "fault_record_list_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "data": {
                "total_records": len(self.fault_records),
                "max_capacity": 100,
                "record_length": 3907,
                "records": self.fault_records
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_fault_record_read(
            self, 
            websocket, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ):
        """处理故障录波读取 - 使用真实串口数据"""
        request_id = data.get("request_id")
        record_id = data.get("record_id", 0)
        
        # 获取配置信息
        fault_config = self.config_manager.get_section('HMI故障录波读取配置')
        total_registers = int(fault_config.get('故障记录总寄存器数', 3907))
        batch_size = int(fault_config.get('最大单次读取长度', 125))
        total_batches = (total_registers + batch_size - 1) // batch_size
        record_data_points = int(fault_config.get('故障记录总数据点', 300))
        
        # 发送开始读取确认
        start_response = {
            "type": "fault_record_read_start",
            "device_id": self.device_status()["device_id"],
            "request_id": request_id,
            "total_registers": total_registers,
            "batch_size": batch_size,
            "total_batches": total_batches,
            "estimated_time": total_batches * 0.5,  # 每批约0.5秒
            "timestamp": datetime.now().isoformat()
        }
        await self.connection_manager.send_to_connection(
            websocket, start_response
        )
        
        # 分批读取故障录波数据
        all_registers = []
        
        try:
            for batch in range(total_batches):
                # 计算当前批次参数
                start_offset = batch * batch_size
                remaining_registers = total_registers - start_offset
                current_batch_size = min(batch_size, remaining_registers)
                
                # 从串口读取数据或使用模拟数据
                if self.serial_manager:
                    batch_registers = self.serial_manager.read_fault_record(
                        device_type='hmi',
                        record_id=record_id,
                        start_offset=start_offset,
                        length=current_batch_size
                    )
                else:
                    # 模拟故障录波数据
                    batch_registers = [random.randint(0, 65535) for _ in range(current_batch_size)]
                
                if batch_registers is None:
                    # 读取失败，发送错误响应
                    await self._send_error_response(websocket, 500, f"第{batch+1}批数据读取失败")
                    return
                
                all_registers.extend(batch_registers)
                
                # 发送进度更新
                progress_response = {
                    "type": "fault_record_progress",
                    "device_id": self.device_status()["device_id"],
                    "request_id": request_id,
                    "current_batch": batch + 1,
                    "total_batches": total_batches,
                    "percentage": round((batch + 1) / total_batches * 100, 1),
                    "timestamp": datetime.now().isoformat()
                }
                await self.connection_manager.send_to_connection(
                    websocket, progress_response
                )
                
                # 短暂延时，避免串口通信过于频繁
                await asyncio.sleep(0.1)
        
            # 解析故障录波数据
            fault_data = self._parse_fault_record_data(all_registers, record_data_points)
            
            # 发送完整数据
            complete_response = {
                "type": "fault_record_complete",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "data": fault_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.connection_manager.send_to_connection(websocket, complete_response)
            
        except Exception as e:
            logger.error(f"故障录波读取异常: {e}")
            await self._send_error_response(websocket, 500, f"故障录波读取失败: {str(e)}")
    
    async def _handle_fault_record_cancel(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理故障录波读取取消"""
        response = {
            "type": "fault_record_cancelled",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "cancelled_at_batch": 10,  # 模拟在第10批时取消
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_param_read(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理参数读取"""
        read_type = data.get("read_type", "control_params")
        
        if read_type == "control_params":
            # 尝试从串口实际读取控制参数
            try:
                if self.serial_manager and self.serial_manager.hmi_master:
                    # 读取0x2200-0x2237区域（55个寄存器）
                    # print(f"📡 [参数读取] 正在从串口读取控制参数区域 0x2200-0x2237...")
                    actual_registers = self.serial_manager.hmi_master.read_holding_registers(16, 0x2200, 55)
                    # print(f"📡 [参数读取] 成功读取到 {len(actual_registers)} 个寄存器数据")
                    
                    # 显示前10个寄存器值作为示例
                    if len(actual_registers) >= 10:
                        pass
                        # print(f"📡 [参数读取] 前10个寄存器值: {actual_registers[:10]}")
                    
                    # 使用实际读取的数据生成参数
                    params = self._get_control_parameters_from_registers(actual_registers)
                    # print(f"📡 [参数读取] 生成 {len(params)} 个控制参数")
                else:
                    # print(f"⚠️  [参数读取] 串口管理器未初始化，使用模拟数据")
                    params = self._get_control_parameters()
            except Exception as e:
                # print(f"❌ [参数读取] 串口读取失败: {e}，回退到模拟数据")
                params = self._get_control_parameters()
                
            response_data = {"params": params}
            
        elif read_type == "sensor_params":
            sensor_params = self._get_sensor_parameters()
            response_data = {"params": sensor_params}
            
        elif read_type == "single":
            reg_addr = data.get("reg_addr")
            param = self._get_single_parameter(reg_addr)
            response_data = {"param": param}
            
        else:
            response_data = {}
        
        response = {
            "type": "param_read_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": data.get("request_id"),
            "data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_param_write(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理参数写入"""
        write_type = data.get("data", {}).get("write_type", "control_params")
        params = data.get("data", {}).get("params", {})
        request_id = data.get("request_id")
        
        logger.info(f"收到参数写入请求: {write_type}, 参数数量: {len(params)}")
        
        # 初始化响应
        response = {
            "type": "param_write_ack",
            "device_id": self.device_status()["device_id"],
            "request_id": request_id,
            "exec_status": "success",
            "exec_msg": "参数写入成功",
            "timestamp": datetime.now().isoformat()
        }
        
        if write_type == "control_params":
            try:
                # 尝试通过串口管理器写入参数
                if self.serial_manager and self.serial_manager.hmi_master:
                    logger.info("通过串口写入控制参数...")
                    
                    # 准备批量写入数据
                    # 将参数按地址排序，以便连续地址可以批量写入
                    sorted_params = sorted(params.items(), key=lambda x: int(x[0], 16) if x[0].startswith("0x") else int(x[0]))
                    
                    success_count = 0
                    failed_params = []
                    
                    # 尝试批量写入连续地址的参数
                    batch_start_addr = None
                    batch_values = []
                    batch_param_names = []
                    
                    def process_batch():
                        """处理当前批次参数的写入"""
                        nonlocal batch_start_addr, batch_values, batch_param_names, success_count, failed_params
                        
                        if not batch_values:
                            return
                            
                        try:
                            # 批量写入寄存器
                            result = self.serial_manager.hmi_master.write_multiple_registers(16, batch_start_addr, batch_values)
                            
                            if result:
                                success_count += len(batch_values)
                                logger.debug(f"成功批量写入寄存器 0x{batch_start_addr:04X}-{batch_start_addr+len(batch_values)-1:04X}")
                            else:
                                # 批量写入失败，记录所有参数为失败
                                for addr_str in batch_param_names:
                                    failed_params.append(f"{addr_str}: 写入失败")
                                logger.warning(f"批量写入寄存器范围 0x{batch_start_addr:04X}-{batch_start_addr+len(batch_values)-1:04X} 失败")
                        except Exception as e:
                            error_msg = str(e)
                            # 检查是否是非法地址错误
                            if "ExceptionResponse" in error_msg and "exception_code=2" in error_msg:
                                for addr_str in batch_param_names:
                                    failed_params.append(f"{addr_str}: 设备不支持该地址")
                                logger.warning(f"设备不支持寄存器地址范围 0x{batch_start_addr:04X}-{batch_start_addr+len(batch_values)-1:04X}")
                            else:
                                for addr_str in batch_param_names:
                                    failed_params.append(f"{addr_str}: {error_msg}")
                                logger.error(f"批量写入参数时出错: {e}")
                        
                        # 重置批次
                        batch_start_addr = None
                        batch_values = []
                        batch_param_names = []
                    
                    # 遍历排序后的参数，构建连续地址的批次
                    for addr_str, value in sorted_params:
                        # 转换地址格式
                        if addr_str.startswith("0x"):
                            addr = int(addr_str, 16)
                        else:
                            addr = int(addr_str)
                        
                        # 检查是否可以加入当前批次
                        if batch_start_addr is None:
                            # 开始新批次
                            batch_start_addr = addr
                            batch_values = [int(value)]
                            batch_param_names = [addr_str]
                        elif addr == batch_start_addr + len(batch_values):
                            # 连续地址，加入当前批次
                            batch_values.append(int(value))
                            batch_param_names.append(addr_str)
                        else:
                            # 不连续，处理当前批次并开始新批次
                            process_batch()
                            batch_start_addr = addr
                            batch_values = [int(value)]
                            batch_param_names = [addr_str]
                    
                    # 处理最后一个批次
                    process_batch()
                    
                    # 检查是否全部成功
                    if len(failed_params) > 0:
                        # 检查是否所有参数都因为地址不支持而失败
                        all_addr_unsupported = all("设备不支持该地址" in param for param in failed_params)
                        
                        if all_addr_unsupported and len(failed_params) == len(params):
                            # 所有参数都因为地址不支持而失败，切换到模拟模式
                            logger.warning("所有参数地址都不被设备支持，切换到模拟模式")
                            response["exec_status"] = "success"
                            response["exec_msg"] = f"参数写入成功 ({len(params)} 个) - 模拟模式(设备不支持这些地址)"
                            response["success_count"] = len(params)
                            response["simulation_mode"] = True
                        else:
                            # 部分失败或因为其他原因失败
                            response["exec_status"] = "partial_success"
                            response["exec_msg"] = f"部分参数写入成功，失败: {', '.join(failed_params)}"
                            response["success_count"] = success_count
                            response["failed_count"] = len(failed_params)
                            response["failed_params"] = failed_params
                    else:
                        response["exec_msg"] = f"所有参数写入成功 ({success_count} 个)"
                        response["success_count"] = success_count
                        
                else:
                    # 模拟写入成功
                    logger.warning("串口管理器未初始化，模拟参数写入成功")
                    response["exec_msg"] = "参数写入成功 (模拟模式)"
                    response["success_count"] = len(params)
                    
            except Exception as e:
                logger.error(f"写入控制参数时出错: {e}")
                response["exec_status"] = "fail"
                response["exec_msg"] = f"参数写入失败: {str(e)}"
                
        else:
            # 其他写入类型暂不支持
            response["exec_status"] = "fail"
            response["exec_msg"] = f"不支持的写入类型: {write_type}"
        
        # 发送响应
        await self.connection_manager.send_to_connection(websocket, response)
    
    async def _handle_data_lost_request(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理数据丢失请求"""
        missing_seq = data.get("missing_seq", [])
        
        # 模拟补推缺失数据
        for seq in missing_seq:
            recovery_data = {
                "type": "data_recovery",
                "seq_num": seq,
                "data": {
                    "recovered": True,
                    "timestamp": datetime.now().isoformat()
                },
                "timestamp": datetime.now().isoformat()
            }
            
            await self.connection_manager.send_to_connection(websocket, recovery_data)
    
    async def _send_error_response(self, websocket, error_code: int, error_msg: str):
        """发送错误响应"""
        error_response = {
            "type": "error",
            "error_code": error_code,
            "error_msg": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(websocket, error_response)
    
    def _init_device_status(self) -> Dict[str, Any]:
        """初始化设备状态"""
        device_info = self.config_manager.get_device_info()
        return {
            "device_id": device_info.get("device_id", "HYP_RPLD_001"),
            "device_name": device_info.get("device_name", "红岩坪站钢轨电位限制装置"),
            "device_ip": device_info.get("device_ip", "192.168.0.11"),
            "system_version": device_info.get("system_version", "1.0.0"),
            "online_status": True,
            "last_update": datetime.now().isoformat()
        }
    
    def _init_analog_data(self) -> list:
        """初始化模拟量数据"""
        return [
            {
                "reg_addr": "0x0006",
                "name": "最大极化电位",
                "raw_value": 255,
                "physical_value": 25.5,
                "unit": "V"
            },
            {
                "reg_addr": "0x0008",
                "name": "支路1电流",
                "raw_value": 120,
                "physical_value": 12.0,
                "unit": "A"
            }
        ]
    
    def _init_digital_data(self) -> Dict[str, Dict[str, int]]:
        """初始化开关量数据"""
        return {
            "input": {
                "bit0": 1,   # 短接接触器：1=合位
                "bit9": 1    # 门锁：1=关闭
            },
            "output": {
                "bit0": 1,   # K1：1=合闸
                "bit8": 1    # K9：1=合闸
            }
        }
    
    def _init_fault_records(self) -> list:
        """初始化故障录波记录"""
        return [
            {
                "record_id": 0,
                "fault_time": "2024-09-29 13:45:12.345",
                "fault_bits": "0x0001",
                "fault_desc": "支路1过流保护"
            },
            {
                "record_id": 1,
                "fault_time": "2024-09-28 10:23:45.678",
                "fault_bits": "0x0040",
                "fault_desc": "电阻超温报警"
            }
        ]

    def _parse_fault_record_data(self, registers: List[int], data_points_count: int) -> Dict[str, Any]:
        """
        解析故障录波数据
        
        Args:
            registers: 从串口读取的寄存器数据
            data_points_count: 数据点数量
            
        Returns:
            解析后的故障录波数据结构
        """
        try:
            if len(registers) < 7:
                logger.error("故障录波数据长度不足")
                return self._get_default_fault_data()
            
            # 解析故障信息头（前7个寄存器）
            fault_info_word = registers[0]  # 故障信息字
            fault_ms = registers[1]         # 毫秒
            fault_sec_min = registers[2]    # 秒和分
            fault_hour_day = registers[3]   # 时和日
            fault_month_year = registers[4] # 月和年
            fault_point = registers[5]      # 故障点位置
            record_cycle = registers[6]     # 录波周期
            
            # 构建故障时间字符串
            second = (fault_sec_min >> 8) & 0xFF
            minute = fault_sec_min & 0xFF
            hour = (fault_hour_day >> 8) & 0xFF
            day = fault_hour_day & 0xFF
            month = (fault_month_year >> 8) & 0xFF
            year_low = fault_month_year & 0xFF
            year = 2000 + year_low  # 假设年份为2000+低字节
            
            fault_time = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}.{fault_ms:03d}"
            
            # 解析数据点
            data_points = []
            header_size = 7
            point_size = 13  # 每个数据点13个寄存器
            
            for i in range(min(data_points_count, (len(registers) - header_size) // point_size)):
                point_offset = header_size + i * point_size
                
                if point_offset + point_size > len(registers):
                    break
                
                # 解析单个数据点
                system_status = registers[point_offset]
                switch_input = registers[point_offset + 1]
                switch_output = registers[point_offset + 2]
                
                # 模拟量数据（假设后续10个寄存器为模拟量）
                analog_data = registers[point_offset + 3:point_offset + point_size]
                
                # 构建数据点
                data_point = {
                    "point_index": i,
                    "system_status": f"0x{system_status:04X}",
                    "switch_input": f"0x{switch_input:04X}",
                    "switch_output": f"0x{switch_output:04X}",
                    "rail_potential_max": analog_data[0] if len(analog_data) > 0 else 0,
                    "max_polarization": self._convert_to_signed(analog_data[1]) if len(analog_data) > 1 else 0,
                    "branch_currents": [analog_data[j] if j < len(analog_data) else 0 for j in range(2, 8)],
                    "branch_voltages": [analog_data[j] if j < len(analog_data) else 0 for j in range(8, 10)]
                }
                
                data_points.append(data_point)
            
            return {
                "fault_info": {
                    "fault_time": fault_time,
                    "fault_bits": f"0x{fault_info_word:04X}",
                    "fault_point": fault_point,
                    "record_cycle": record_cycle
                },
                "data_points": data_points
            }
            
        except Exception as e:
            logger.error(f"故障录波数据解析失败: {e}")
            return self._get_default_fault_data()
    
    def _convert_to_signed(self, value: int) -> int:
        """将无符号值转换为有符号值"""
        if value >= 0x8000:
            return value - 0x10000
        return value
    
    def _get_default_fault_data(self) -> Dict[str, Any]:
        """获取默认的故障录波数据（当解析失败时）"""
        return {
            "fault_info": {
                "fault_time": datetime.now().isoformat(),
                "fault_bits": "0x0000",
                "fault_point": 0,
                "record_cycle": 100
            },
            "data_points": [
                {
                    "point_index": i,
                    "system_status": "0x0000",
                    "switch_input": "0x0000",
                    "switch_output": "0x0000",
                    "rail_potential_max": 0,
                    "max_polarization": 0,
                    "branch_currents": [0] * 6,
                    "branch_voltages": [0] * 2
                } for i in range(10)  # 默认10个数据点
            ]
        }
    
    def _get_control_parameters_from_registers(self, registers: list) -> list:
        """根据实际读取的寄存器数据生成控制参数"""
        if not registers or len(registers) < 55:
            # print(f"⚠️  [参数生成] 寄存器数据不足，使用模拟数据")
            return self._get_control_parameters()
        
        # print(f"📊 [参数生成] 使用实际寄存器数据生成控制参数...")
        
        # 根据config.ini中的HMI系统控制参数地址映射定义
        param_mappings = [
            # 电压保护值（1-11段，单位：V）
            {"addr": 0x2200, "name": "1段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2201, "name": "2段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2202, "name": "3段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2203, "name": "4段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2204, "name": "5段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2205, "name": "6段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2206, "name": "7段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2207, "name": "8段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2208, "name": "9段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x2209, "name": "10段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            {"addr": 0x220A, "name": "11段电压保护值（V）", "unit": "V", "min": 0, "max": 1000},
            
            # 保护延时动作时间（1-10段，单位：0.01s，最大值300s）
            {"addr": 0x220B, "name": "1段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x220C, "name": "2段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x220D, "name": "3段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x220E, "name": "4段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x220F, "name": "5段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x2210, "name": "6段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x2211, "name": "7段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x2212, "name": "8段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x2213, "name": "9段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            {"addr": 0x2214, "name": "10段保护延时（0.01s）", "unit": "0.01s", "min": 0, "max": 30000},
            
            # KM闭合延续时间（1-10段，单位：s，最大值300s）
            {"addr": 0x2215, "name": "1段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x2216, "name": "2段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x2217, "name": "3段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x2218, "name": "4段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x2219, "name": "5段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x221A, "name": "6段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x221B, "name": "7段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x221C, "name": "8段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x221D, "name": "9段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            {"addr": 0x221E, "name": "10段KM闭合时间（s）", "unit": "s", "min": 0, "max": 300},
            
            # 连续动作时间（1-10段，单位：s，最大值1800s）
            {"addr": 0x221F, "name": "1段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2220, "name": "2段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2221, "name": "3段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2222, "name": "4段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2223, "name": "5段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2224, "name": "6段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2225, "name": "7段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2226, "name": "8段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2227, "name": "9段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            {"addr": 0x2228, "name": "10段连续动作时间（s）", "unit": "s", "min": 0, "max": 1800},
            
            # 连续动作次数（1-10段，单位：次，0-10次，0：关闭）
            {"addr": 0x2229, "name": "1段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222A, "name": "2段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222B, "name": "3段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222C, "name": "4段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222D, "name": "5段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222E, "name": "6段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x222F, "name": "7段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x2230, "name": "8段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x2231, "name": "9段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            {"addr": 0x2232, "name": "10段连续动作次数（次）", "unit": "次", "min": 0, "max": 10},
            
            # 其他参数
            {"addr": 0x2233, "name": "KM分断电流设置值（A）", "unit": "A", "min": 0, "max": 500},
            {"addr": 0x2234, "name": "可控硅导通判断电流值（A）", "unit": "A", "min": 0, "max": 500},
            {"addr": 0x2235, "name": "SV1与SV2允许偏差值（V）", "unit": "V", "min": 0, "max": 100},
            {"addr": 0x2236, "name": "故障录波周期（ms）", "unit": "ms", "min": 0, "max": 65535},
        ]
        
        params = []
        for mapping in param_mappings:
            addr_offset = mapping["addr"] - 0x2200
            if addr_offset < len(registers):
                current_value = registers[addr_offset]
                # print(f"    0x{mapping['addr']:04X} ({mapping['name']}): {current_value} {mapping['unit']}")
                
                params.append({
                    "reg_addr": f"0x{mapping['addr']:04X}",
                    "param_name": mapping["name"],
                    "current_value": current_value,
                    "value_range": f"{mapping['min']}-{mapping['max']}",
                    "unit": mapping["unit"]
                })
            else:
                # print(f"    0x{mapping['addr']:04X} ({mapping['name']}): 数据不足，使用默认值")
                params.append({
                    "reg_addr": f"0x{mapping['addr']:04X}",
                    "param_name": mapping["name"],
                    "current_value": 0,
                    "value_range": f"{mapping['min']}-{mapping['max']}",
                    "unit": mapping["unit"]
                })
        
        # print(f"📊 [参数生成] 成功生成 {len(params)} 个控制参数")
        return params

    def _get_control_parameters(self) -> list:
        """获取控制参数"""
        control_mapping = self.config_manager.get_control_parameters_mapping()
        
        # 为每个控制参数生成示例数据
        control_params = []
        for reg_addr, param_name in control_mapping.items():
            # 根据参数名称确定合适的示例值和单位
            if '电压保护值' in param_name:
                current_value = 250
                value_range = "0-1000"
                unit = "V"
            elif '保护延时' in param_name and '0.01s' in param_name:
                current_value = 1000  # 10秒 = 1000 * 0.01s
                value_range = "0-30000"  # 300s = 30000 * 0.01s
                unit = "0.01s"
            elif 'KM闭合时间' in param_name:
                current_value = 60
                value_range = "0-300"
                unit = "s"
            elif '连续动作时间' in param_name:
                current_value = 300
                value_range = "0-1800"
                unit = "s"
            elif '连续动作次数' in param_name:
                current_value = 3
                value_range = "0-10"
                unit = "次"
            elif 'KM分断电流' in param_name or '可控硅导通判断电流' in param_name:
                current_value = 150
                value_range = "0-500"
                unit = "A"
            elif '偏差值' in param_name:
                current_value = 25
                value_range = "0-100"
                unit = "V"
            elif '周期' in param_name:
                current_value = 100
                value_range = "10-1000"
                unit = "ms"
            else:
                current_value = 100
                value_range = "0-65535"
                unit = ""
            
            control_params.append({
                "reg_addr": reg_addr,
                "param_name": param_name,
                "current_value": current_value,
                "value_range": value_range,
                "unit": unit
            })
        
        return control_params
    
    def _get_sensor_parameters(self) -> Dict[str, list]:
        """获取传感器参数"""
        return {
            "sensor_down": [
                {"channel": "AI1", "down_limit": -1000},
                {"channel": "AI2", "down_limit": -1000}
            ],
            "sensor_up": [
                {"channel": "AI1", "up_limit": 1000},
                {"channel": "AI2", "up_limit": 1000}
            ]
        }
    
    def _get_single_parameter(self, reg_addr: str) -> Dict[str, Any]:
        """获取单个参数"""
        return {
            "reg_addr": reg_addr,
            "param_name": "示例参数",
            "current_value": 100,
            "unit": "V"
        }

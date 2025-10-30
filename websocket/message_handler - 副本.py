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
        
        # 故障录波读取取消标志
        self.fault_record_cancel_flags: Dict[str, bool] = {}
        
        # 故障录波读取任务管理 - 跟踪正在运行的读取任务
        self.fault_record_tasks: Dict[str, asyncio.Task] = {}
    
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
            
            # 添加调试信息
            logger.info(f"收到消息类型: {msg_type}, 连接: {connection_info['connection_id']}")
            logger.info(f"消息内容: {message}")
            
            # 特别记录取消消息
            if msg_type == "fault_record_cancel":
                request_id = data.get("data", {}).get("request_id")
                logger.info(f"🔍 收到故障录波取消消息 - 连接ID: {connection_info['connection_id']}, request_id: {request_id}")
                logger.info(f"🔍 当前取消标志状态: {dict(self.fault_record_cancel_flags)}")
            
            # 根据消息类型分发处理
            if msg_type == "device_register":
                logger.info("处理设备注册消息")
                await self._handle_device_registration(websocket, data, connection_info)
            elif msg_type == "heartbeat":
                logger.info("处理心跳消息")
                await self._handle_heartbeat(websocket, data, connection_info)
            elif msg_type == "control_cmd":
                logger.info("处理控制指令消息")
                await self._handle_control_command(websocket, data, connection_info)
            elif msg_type == "fault_record_list":
                logger.info("处理故障录波目录查询消息")
                await self._handle_fault_record_list(websocket, data, connection_info)
            elif msg_type == "fault_record_read":
                logger.info("处理故障录波读取消息")
                await self._handle_fault_record_read(websocket, data, connection_info)
            elif msg_type == "fault_record_cancel":
                logger.info("处理故障录波取消消息")
                await self._handle_fault_record_cancel(websocket, data, connection_info)
            elif msg_type == "param_read":
                logger.info("处理参数读取消息")
                await self._handle_param_read(websocket, data, connection_info)
            elif msg_type == "param_write":
                logger.info("处理参数写入消息")
                await self._handle_param_write(websocket, data, connection_info)
            elif msg_type == "data_lost_request":
                logger.info("处理数据丢失请求消息")
                await self._handle_data_lost_request(websocket, data, connection_info)
            else:
                logger.warning(f"未知消息类型: {msg_type}")
                await self._send_error_response(websocket, 400, f"未知消息类型: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error(f"JSON解析错误: {message}")
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
        # 尝试从串口读取故障记录目录信息（寄存器0x0300-0x0303）
        try:
            if self.serial_manager and self.serial_manager.hmi_master:
                # 从串口读取4个寄存器的值
                registers = self.serial_manager.hmi_master.read_holding_registers(16, 0x0300, 4)
                if registers and len(registers) >= 4:
                    total_records = registers[0]  # 0x0300: 当前故障录波记录数
                    record_length = registers[1]  # 0x0301: 记录长度
                    max_capacity = registers[3]  # 0x0303: 最多存放记录数
                    
                    response = {
                        "type": "fault_record_list_ack",
                        "device_id": self.device_status()["device_id"],
                        "request_id": data.get("request_id"),
                        "data": {
                            "total_records": total_records,
                            "record_length": record_length,
                            "max_capacity": max_capacity
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await self.connection_manager.send_to_connection(websocket, response)
                else:
                    # 串口读取失败，返回错误信息
                    await self._send_error_response(websocket, 500, "读取故障记录目录信息失败：串口返回数据无效")
            else:
                # 串口管理器未初始化，返回错误信息
                await self._send_error_response(websocket, 500, "读取故障记录目录信息失败：串口管理器未初始化")
        except Exception as e:
            logger.error(f"读取故障记录目录信息失败: {e}")
            # 返回错误信息
            await self._send_error_response(websocket, 500, f"读取故障记录目录信息失败: {str(e)}")
    
    async def _handle_fault_record_read(
            self, 
            websocket, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any]
    ):
        """处理故障录波读取 - 使用真实串口数据"""
        request_id = data.get("request_id")
        record_id = data.get("record_id", 0)
        
        # 检查是否已有相同request_id的任务在运行
        if request_id in self.fault_record_tasks and not self.fault_record_tasks[request_id].done():
            logger.warning(f"🔄 已存在request_id为 {request_id} 的故障录波读取任务，忽略重复请求")
            return
        
        # 创建新的读取任务 - 使用局部变量确保request_id不会丢失
        task = asyncio.create_task(self._execute_fault_record_read(websocket, data, connection_info, request_id))
        self.fault_record_tasks[request_id] = task
        
        # 设置任务完成时的清理回调
        def cleanup_task(task):
            if request_id in self.fault_record_tasks:
                del self.fault_record_tasks[request_id]
                logger.info(f"🧹 清理完成request_id为 {request_id} 的故障录波读取任务")
        
        task.add_done_callback(cleanup_task)
        logger.info(f"🚀 启动故障录波读取任务 - request_id: {request_id}")
    
    async def _execute_fault_record_read(
            self, 
            websocket, 
            data: Dict[str, Any], 
            connection_info: Dict[str, Any],
            request_id: str
    ):
        """实际执行故障录波读取的逻辑"""
        record_id = data.get("record_id", 0)
        
        # 🔍 调试日志：记录初始request_id
        logger.info(f"🚀 _execute_fault_record_read 开始执行 - request_id: {request_id}, data keys: {list(data.keys())}")
        
        # 获取配置信息
        fault_config = self.config_manager.get_section('HMI故障录波读取配置')
        total_registers = int(fault_config.get('故障记录总寄存器数', 3907))
        record_data_points = int(fault_config.get('故障记录总数据点', 300))
        wave_data_registers_per_group = int(fault_config.get('故障记录数据点寄存器数', 4))  # 从配置文件读取数据点寄存器数
        
        # 根据测试文件，使用更合理的读取策略
        # 第一次读取故障信息头寄存器数，后续每次读取wave_data_registers_per_group个寄存器（录波数据）
        fault_info_registers = int(fault_config.get('故障记录头寄存器数', 7))  # 从配置文件读取故障信息头寄存器数
        total_wave_groups = record_data_points  # 使用配置文件中读取的数据点数量
        total_read_registers = fault_info_registers + (wave_data_registers_per_group * total_wave_groups)
        
        # 发送开始读取确认
        start_response = {
            "type": "fault_record_read_start",
            "device_id": self.device_status()["device_id"],
            "request_id": request_id,
            "total_registers": total_read_registers,
            "record_data_points": record_data_points,
            "total_batches": total_wave_groups + 1,  # 故障信息头 + 录波数据组数 = 301
            "estimated_time": 300.0,  # 预计8秒完成（考虑多次读取）
            "timestamp": datetime.now().isoformat()
        }
        await self.connection_manager.send_to_connection(
            websocket, start_response
        )
        
        try:
            all_registers = []
            
            # 第一步：读取故障信息头（fault_info_registers个寄存器）
            logger.info(f"第一步：读取故障信息头（{fault_info_registers}个寄存器）")
            fault_header = self.serial_manager.read_fault_record(
                device_type='hmi',
                record_id=record_id,
                start_offset=0,
                length=fault_info_registers
            )
            
            if fault_header is None:
                raise Exception("故障信息头读取失败")
            
            all_registers.extend(fault_header)
            logger.info(f"成功读取故障信息头：{len(fault_header)} 个寄存器")
            
            # 发送进度更新（故障信息头完成）
            progress_response = {
                "type": "fault_record_progress",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "current_batch": 1,
                "total_batches": total_wave_groups + 1,  # 301
                "percentage": int((1 / (total_wave_groups + 1)) * 100),
                "timestamp": datetime.now().isoformat()
            }
            await self.connection_manager.send_to_connection(
                websocket, progress_response
            )
            
            # 第二步：分步读取录波数据（每次wave_data_registers_per_group个寄存器）
            logger.info(f"第二步：读取录波数据（每次{wave_data_registers_per_group}个寄存器）")
            current_offset = fault_info_registers  # 录波数据从故障信息头寄存器数开始
            
            # 进度日志控制 - 每10%记录一次主要进度，每1%记录一次详细进度
            last_major_log_percentage = 0
            last_detail_log_percentage = 0

            for i in range(total_wave_groups):
                # 智能日志记录 - 减少重复日志
                current_percentage = int(((i + 1) / total_wave_groups) * 100)
                
                # 每10%记录一次主要进度
                if current_percentage >= last_major_log_percentage + 10:
                    logger.info(f"进度：{current_percentage}% - 已读取 {i+1}/{total_wave_groups} 组录波数据")
                    last_major_log_percentage = current_percentage
                # 每1%记录一次详细进度（但限制频率）
                elif current_percentage >= last_detail_log_percentage + 1 and i % 10 == 0:
                    logger.debug(f"读取第 {i+1} 组录波数据（{wave_data_registers_per_group}个寄存器）...")
                    last_detail_log_percentage = current_percentage
                
                # 带重试机制的读取
                max_retries = 3
                wave_data = None
                
                for retry in range(max_retries):
                    try:
                        wave_data = self.serial_manager.read_fault_record(
                            device_type='hmi',
                            record_id=record_id,
                            start_offset=current_offset,
                            length=wave_data_registers_per_group
                        )
                        
                        if wave_data is not None and len(wave_data) > 0:
                            # 读取成功，跳出重试循环
                            if retry > 0:
                                logger.info(f"第 {i + 1} 组录波数据在第{retry + 1}次重试后读取成功")
                            break
                        else:
                            # 读取结果为None或空，记录警告并继续重试
                            logger.warning(f"第 {i + 1} 组录波数据第{retry + 1}次读取失败（无数据），准备重试...")
                            
                    except Exception as e:
                        logger.warning(f"第 {i + 1} 组录波数据第{retry + 1}次读取异常：{e}")
                    
                    # 如果不是最后一次重试，添加延迟后重试
                    if retry < max_retries - 1:
                        await asyncio.sleep(0.5 * (retry + 1))  # 递增延迟：0.5s, 1s, 1.5s
                
                if wave_data is None:
                    logger.error(f"第 {i + 1} 组录波数据在{max_retries}次重试后仍然读取失败！")
                    logger.error(f"失败详情：从站地址=16, 记录ID={record_id}, 起始偏移={current_offset}, 长度={wave_data_registers_per_group}（{wave_data_registers_per_group}个寄存器）")
                    logger.error(f"可能的故障原因：1)设备通信异常 2)Modbus地址超出范围 3)设备存储器损坏 4)电源/接线问题")
                    
                    # 发送错误通知并结束整个读取流程
                    error_response = {
                        "type": "fault_record_error",
                        "device_id": self.device_status()["device_id"],
                        "request_id": request_id,
                        "error": f"第 {i + 1} 组录波数据读取失败（重试{max_retries}次），已停止读取",
                        "failed_at_group": i + 1,
                        "total_groups": total_wave_groups,
                        "retry_count": max_retries,
                        "timestamp": datetime.now().isoformat()
                    }
                    await self.connection_manager.send_to_connection(
                        websocket, error_response
                    )
                    
                    # 清理取消标志（如果存在）
                    if request_id in self.fault_record_cancel_flags:
                        del self.fault_record_cancel_flags[request_id]
                    
                    # 直接结束整个读取流程
                    logger.warning(f"录波数据读取在第{i+1}组失败，已停止读取流程")
                    return
                
                all_registers.extend(wave_data)
                current_offset += wave_data_registers_per_group
                
                # 只在详细日志模式下记录每组成功信息
                if i % 10 == 0:  # 每10组记录一次
                    logger.debug(f"成功读取第 {i+1} 组：{len(wave_data)} 个寄存器（{len(wave_data)}个数据寄存器）")
                
                # 发送进度更新 - 修复进度计算精度问题
                actual_percentage = min(99, int(((i + 2) / (total_wave_groups + 1)) * 100))
                progress_response = {
                    "type": "fault_record_progress",
                    "device_id": self.device_status()["device_id"],
                    "request_id": request_id,
                    "current_batch": i + 2,  # +2 因为故障信息头是第1批
                    "total_batches": total_wave_groups + 1,  # 301
                    "percentage": actual_percentage,
                    "current_group": i + 1,
                    "total_groups": total_wave_groups,  # 300
                    "timestamp": datetime.now().isoformat()
                }
                await self.connection_manager.send_to_connection(
                    websocket, progress_response
                )
                
                # 🔥 关键修复：更新心跳时间，防止长时间读取被误判为超时
                await self.connection_manager.update_heartbeat(websocket)
                
                # 检查是否被取消
                logger.debug(f"🔍 检查取消标志 - request_id: {request_id}, 当前标志: {dict(self.fault_record_cancel_flags)}")
                logger.debug(f"🔍 request_id参数值: {request_id}")
                if self.fault_record_cancel_flags.get(request_id, False):
                    logger.info(f"🛑 故障录波读取在第{i+1}组被取消，request_id: {request_id}")
                    
                    # 发送取消通知
                    cancel_response = {
                        "type": "fault_record_cancelled",
                        "device_id": self.device_status()["device_id"],
                        "request_id": request_id,
                        "cancelled_at_batch": i + 2,  # +2 因为故障信息头是第1批
                        "cancelled_at_group": i + 1,
                        "total_groups": total_wave_groups,
                        "timestamp": datetime.now().isoformat()
                    }
                    await self.connection_manager.send_to_connection(
                        websocket, cancel_response
                    )
                    
                    # 清理取消标志
                    del self.fault_record_cancel_flags[request_id]
                    
                    # 直接结束整个读取流程
                    logger.warning(f"🛑 录波数据读取在第{i+1}组被取消，已停止读取流程")
                    return
                
                # 添加短暂延迟，避免读取过快
                await asyncio.sleep(0.01)
            
            logger.info(f"总共读取 {len(all_registers)} 个寄存器")
            
            # 发送最终进度更新（100%）
            final_progress_response = {
                "type": "fault_record_progress",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "current_batch": total_wave_groups + 1,  # 301
                "total_batches": total_wave_groups + 1,  # 301
                "percentage": 100,
                "timestamp": datetime.now().isoformat()
            }
            await self.connection_manager.send_to_connection(
                websocket, final_progress_response
            )
            
            # 🔥 关键修复：更新心跳时间，防止长时间读取被误判为超时
            await self.connection_manager.update_heartbeat(websocket)
            
            # 添加短暂延迟，确保前端能处理进度消息
            await asyncio.sleep(0.1)
            
            # 解析故障录波数据
            fault_data = self._parse_fault_record_data(all_registers, record_data_points, wave_data_registers_per_group)
            
            # 发送完整数据
            complete_response = {
                "type": "fault_record_complete",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "data": fault_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.connection_manager.send_to_connection(websocket, complete_response)
            
            # 清理取消标志（如果存在）
            if request_id in self.fault_record_cancel_flags:
                del self.fault_record_cancel_flags[request_id]
                
        except asyncio.CancelledError:
            logger.info(f"🛑 故障录波读取任务 {request_id} 被取消")
            
            # 发送取消通知
            cancel_response = {
                "type": "fault_record_cancelled",
                "device_id": self.device_status()["device_id"],
                "request_id": request_id,
                "cancelled_at_batch": 0,  # 任务级别取消
                "cancel_reason": "任务被取消",
                "timestamp": datetime.now().isoformat()
            }
            await self.connection_manager.send_to_connection(websocket, cancel_response)
            
            # 清理取消标志
            if request_id in self.fault_record_cancel_flags:
                del self.fault_record_cancel_flags[request_id]
            
            # 重新抛出异常，让调用者知道任务被取消
            raise
            
        except Exception as e:
            logger.error(f"故障录波读取异常: {e}")
            await self._send_error_response(websocket, 500, f"故障录波读取失败: {str(e)}")
            
            # 清理取消标志（如果存在）
            if request_id in self.fault_record_cancel_flags:
                del self.fault_record_cancel_flags[request_id]
    
    async def _handle_fault_record_cancel(self, websocket, data: Dict[str, Any], connection_info: Dict[str, Any]):
        """处理故障录波取消消息"""
        request_id = data.get("data", {}).get("request_id")
        
        # 🔍 调试日志：记录取消请求中的request_id
        logger.info(f"📨 收到取消请求 - 原始data: {data}")
        logger.info(f"📨 data类型: {type(data)}")
        logger.info(f"📨 data.keys(): {list(data.keys())}")
        logger.info(f"📨 data.get('data'): {data.get('data')}")
        logger.info(f"📨 data.get('data', {{}}).get('request_id'): {data.get('data', {}).get('request_id')}")
        logger.info(f"📨 解析后的request_id: {request_id}")
        
        logger.info(f"🔍 执行故障录波取消逻辑 - request_id: {request_id}")
        logger.info(f"🔍 取消标志字典当前状态: {dict(self.fault_record_cancel_flags)}")
        logger.info(f"🔍 当前运行任务: {list(self.fault_record_tasks.keys())}")
        
        # 设置取消标志
        if request_id:
            self.fault_record_cancel_flags[request_id] = True
            logger.info(f"✅ 设置故障录波读取取消标志: {request_id}")
            logger.info(f"✅ 取消标志字典更新后状态: {dict(self.fault_record_cancel_flags)}")
            
            # 🔥 关键修复：尝试取消正在运行的任务
            if request_id in self.fault_record_tasks:
                task = self.fault_record_tasks[request_id]
                if not task.done():
                    logger.info(f"🛑 正在取消request_id为 {request_id} 的故障录波读取任务")
                    task.cancel()
                    try:
                        await task
                        logger.info(f"✅ 成功取消任务: {request_id}")
                    except asyncio.CancelledError:
                        logger.info(f"✅ 任务 {request_id} 已被成功取消")
                    except Exception as e:
                        logger.error(f"❌ 取消任务 {request_id} 时出错: {e}")
                else:
                    logger.info(f"ℹ️ 任务 {request_id} 已经完成，无需取消")
            else:
                logger.info(f"ℹ️ 未找到request_id为 {request_id} 的运行中任务，仅设置取消标志")
        else:
            logger.warning("⚠️ 未提供request_id，无法设置取消标志")
        
        response = {
            "type": "fault_record_cancelled",
            "device_id": self.device_status()["device_id"],
            "request_id": request_id,
            "cancelled_at_batch": 10,  # 模拟在第10批时取消
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.send_to_connection(websocket, response)
        logger.info(f"✅ 发送取消响应: {response}")
    
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

    def _parse_fault_record_data(self, registers: List[int], data_points_count: int, registers_per_point: int = 4) -> Dict[str, Any]:
        """
        解析故障录波数据（紧凑模式：registers_per_point个寄存器每数据点）
        
        Args:
            registers: 从串口读取的寄存器数据
            data_points_count: 数据点数量
            registers_per_point: 每个数据点的寄存器数（默认4个）
            
        Returns:
            解析后的故障录波数据结构
        """
        try:
            if len(registers) < 7:
                logger.error("故障录波数据长度不足")
                raise ValueError("故障录波数据长度不足，至少需要7个寄存器")
            
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
            
            # 解析数据点 - 紧凑模式：每个数据点registers_per_point个寄存器
            data_points = []
            header_size = 7
            point_size = registers_per_point  # 使用参数中的寄存器数
            
            # 计算实际可解析的数据点数量
            remaining_registers = len(registers) - header_size
            actual_data_points = min(data_points_count, remaining_registers // point_size)
            logger.info(f"紧凑模式解析：期望{data_points_count}个数据点，实际可用{actual_data_points}个")
            
            for i in range(actual_data_points):
                point_offset = header_size + i * point_size
                
                if point_offset + point_size > len(registers):
                    break
                
                # 紧凑解析模式（registers_per_point个寄存器每数据点）
                # 根据需求文档：系统状态 + 3个模拟量数值
                # 寄存器0: 系统状态（16位）
                # 寄存器1: 通道1模拟量数值 = 轨地电流SA1
                # 寄存器2: 通道2模拟量数值 = 轨地电流SA2  
                # 寄存器3: 通道3模拟量数值 = 轨地电压SV1
                system_status = registers[point_offset]      # 寄存器0: 系统状态（16位）
                channel1_sa1 = self._convert_to_signed(registers[point_offset + 1]) if registers_per_point > 1 else 0  # 寄存器1: 通道1轨地电流SA1（16位）
                channel2_sa2 = self._convert_to_signed(registers[point_offset + 2]) if registers_per_point > 2 else 0  # 寄存器2: 通道2轨地电流SA2（16位）
                channel3_sv1 = self._convert_to_signed(registers[point_offset + 3]) if registers_per_point > 3 else 0  # 寄存器3: 通道3轨地电压SV1（16位）
                
                data_point = {
                    "point_index": i,
                    "system_status": f"0x{system_status:04X}",    # 系统状态（16位十六进制字符串）
                    "channel1_sa1": channel1_sa1,    # 通道1轨地电流SA1
                    "channel2_sa2": channel2_sa2,    # 通道2轨地电流SA2
                    "channel3_sv1": channel3_sv1    # 通道3轨地电压SV1
                }
                
                data_points.append(data_point)
            logger.info(f"成功解析 {len(data_points)} 个数据点")
            
            # 如果实际数据点少于期望值，直接抛出异常
            if len(data_points) < data_points_count:
                raise ValueError(f"故障录波数据点数量不足，期望 {data_points_count} 个，实际只有 {len(data_points)} 个")
            
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
            import traceback
            traceback.print_exc()
            raise ValueError(f"故障录波数据解析失败: {e}")
    
    def _convert_to_signed(self, value: int) -> int:
        """将无符号值转换为有符号值"""
        if value >= 0x8000:
            return value - 0x10000
        return value
    
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

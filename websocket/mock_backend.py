#!/usr/bin/env python3
# flake8: noqa
"""
模拟后端WebSocket服务器
Mock Backend WebSocket Server
基于WebSocket及API接口协议完整版实现
"""

import asyncio
import websockets
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Set
from pathlib import Path
import sys
import os

# 添加项目根目录到路径，确保模块导入正确
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入配置管理器
from config.config_manager import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入串口管理器，如果失败则使用模拟模式
try:
    from serial_comm.serial_manager import SerialManager
    SERIAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"串口模块不可用，将使用模拟模式: {e}")
    SERIAL_AVAILABLE = False
    SerialManager = None  # type: ignore

class MockBackendServer:
    """模拟后端服务器 - 符合WebSocket协议规范"""
    
    def __init__(self):
        self.connected_clients: Dict[websockets.WebSocketServerProtocol, Dict] = {}
        self.seq_num = 1000  # 序列号计数器
        self.device_status = self._init_device_status()
        self.analog_data = self._init_analog_data()
        self.digital_data = self._init_digital_data()
        self.fault_records = self._init_fault_records()
        
        # 串口管理器实例
        self.serial_manager = None
        self.serial_connected = False
        self.last_serial_data = None
        
    def _init_device_status(self):
        """初始化设备状态"""
        return {
            "device_id": "HYP_RPLD_001",
            "device_name": "红岩坪站钢轨电位限制装置",
            "device_ip": "192.168.0.11",
            "system_version": "1.0.0",
            "online_status": True,
            "last_update": datetime.now().isoformat()
        }
    
    def _init_analog_data(self):
        """初始化模拟量数据 - 匹配数据库和前端期望的SA1/SA2/SV1/SV2参数"""
        return [
            {
                "reg_addr": "0x0006",
                "name": "轨地电流SA1",
                "raw_value": 120,
                "physical_value": 12.0,
                "unit": "A"
            },
            {
                "reg_addr": "0x0007", 
                "name": "可控硅电流SA2",
                "raw_value": 130,
                "physical_value": 13.0,
                "unit": "A"
            },
            {
                "reg_addr": "0x0008",
                "name": "轨地电压SV1", 
                "raw_value": 2200,
                "physical_value": 220.0,
                "unit": "V"
            },
            {
                "reg_addr": "0x0009",
                "name": "轨地电压SV2",
                "raw_value": 2150,
                "physical_value": 215.0,
                "unit": "V"
            }
        ]
    
    def _init_digital_data(self):
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
    
    def _init_fault_records(self):
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
    
    def _get_next_seq_num(self):
        """获取下一个序列号"""
        self.seq_num += 1
        return self.seq_num
    
    def _update_analog_values(self):
        """更新模拟量数值（模拟实时变化）"""
        for item in self.analog_data:
            if "电流" in item["name"]:
                # 电流在8-15A之间变化
                base_value = 10.0 + random.uniform(-2, 5)
                item["physical_value"] = round(base_value, 1)
                item["raw_value"] = int(base_value * 10)
            elif "电压" in item["name"]:
                # 电压在210-230V之间变化
                base_value = 220.0 + random.uniform(-10, 10)
                item["physical_value"] = round(base_value, 1)
                item["raw_value"] = int(base_value * 10)
            elif "电位" in item["name"]:
                # 电位在-30到30V之间变化
                base_value = random.uniform(-30, 30)
                item["physical_value"] = round(base_value, 1)
                item["raw_value"] = int(base_value * 10)
    
    def _update_digital_values(self):
        """更新开关量数值（偶尔变化）"""
        # 一般开关量变化（15%概率，降低频率）
        if random.random() < 0.15:
            # 随机改变一个开关量状态（但排除KM1）
            if random.random() < 0.5:
                # 输入开关量变化
                bit_key = random.choice(list(self.digital_data["input"].keys()))
                self.digital_data["input"][bit_key] = 1 - self.digital_data["input"][bit_key]
                logger.info(f"开关量输入变化: {bit_key} = {self.digital_data['input'][bit_key]}")
            else:
                # 输出开关量变化（排除bit0即KM1）
                output_keys = [k for k in self.digital_data["output"].keys() if k != "bit0"]
                if output_keys:
                    bit_key = random.choice(output_keys)
                    self.digital_data["output"][bit_key] = 1 - self.digital_data["output"][bit_key]
                    logger.info(f"开关量输出变化: {bit_key} = {self.digital_data['output'][bit_key]}")
        
        # KM1状态变化（20%概率，更合理的频率）
        if random.random() < 0.20:
            old_value = self.digital_data["output"]["bit0"]
            self.digital_data["output"]["bit0"] = 1 - self.digital_data["output"]["bit0"]
            new_value = self.digital_data["output"]["bit0"]
            status_text = "合位" if new_value == 1 else "分位"
            logger.info(f"KM1状态变化: bit0 = {old_value} -> {new_value} ({status_text})")
        
    async def register_client(self, websocket):
        """注册新客户端"""
        connection_id = f"conn_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.connected_clients[websocket] = {
            "connection_id": connection_id,
            "connected_at": datetime.now(),
            "device_registered": False
        }
        
        logger.info(f"客户端已连接: {connection_id}, 当前连接数: {len(self.connected_clients)}")
        
        # 发送连接确认
        connect_ack = {
            "type": "connect_ack",
            "status": "success", 
            "connection_id": connection_id,
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await websocket.send(json.dumps(connect_ack, ensure_ascii=False))
            logger.info(f"连接确认已发送: {connection_id}")
        except Exception as e:
            logger.error(f"发送连接确认失败: {e}")
    
    async def unregister_client(self, websocket):
        """注销客户端"""
        if websocket in self.connected_clients:
            client_info = self.connected_clients.pop(websocket)
            logger.info(f"客户端已断开: {client_info.get('connection_id')}")
        
        logger.info(f"当前连接数: {len(self.connected_clients)}")
    
    async def handle_device_registration(self, websocket, data):
        """处理设备注册"""
        device_id = data.get("device_id")
        device_name = data.get("device_name")
        
        # 更新客户端信息
        if websocket in self.connected_clients:
            self.connected_clients[websocket]["device_registered"] = True
            self.connected_clients[websocket]["device_id"] = device_id
            
        logger.info(f"设备已注册: {device_id} - {device_name}")
        
        # 发送欢迎消息
        welcome_msg = {
            "type": "welcome",
            "message": f"设备 {device_name} 注册成功",
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send(json.dumps(welcome_msg, ensure_ascii=False))
    
    async def handle_message(self, websocket, message):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            logger.info(f"收到消息类型: {msg_type}")
            
            if msg_type == "device_register":
                # 设备注册
                await self.handle_device_registration(websocket, data)
                
            elif msg_type == "heartbeat":
                # 心跳响应
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
                await websocket.send(json.dumps(response, ensure_ascii=False))
                
            elif msg_type == "control_cmd":
                # 控制指令
                await self.handle_control_command(websocket, data)
                
            elif msg_type == "fault_record_list":
                # 故障录波目录查询
                await self.handle_fault_record_list(websocket, data)
                
            elif msg_type == "fault_record_read":
                # 故障录波读取
                await self.handle_fault_record_read(websocket, data)
                
            elif msg_type == "param_read":
                # 参数读取
                await self.handle_param_read(websocket, data)
                
            else:
                # 未知消息类型
                response = {
                    "type": "error",
                    "error_code": 400,
                    "error_msg": f"未知消息类型: {msg_type}",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))
                
        except json.JSONDecodeError:
            error_response = {
                "type": "error",
                "error_code": 400,
                "error_msg": "无效的JSON格式",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response, ensure_ascii=False))
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            error_response = {
                "type": "error",
                "error_code": 500,
                "error_msg": f"服务器内部错误: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response, ensure_ascii=False))
    
    async def handle_control_command(self, websocket, data):
        """处理控制指令"""
        cmd = data.get("cmd")
        request_id = data.get("request_id")
        
        # 模拟指令执行延时
        await asyncio.sleep(0.1)
        
        if cmd == "fault_reset":
            response = {
                "type": "control_ack",
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "cmd": cmd,
                "exec_status": "success",
                "exec_msg": "故障复位成功",
                "timestamp": datetime.now().isoformat()
            }
        elif cmd == "set_param":
            param_data = data.get("cmd_param", {})
            response = {
                "type": "control_ack", 
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "cmd": cmd,
                "exec_status": "success",
                "exec_msg": "参数设置成功",
                "current_value": param_data.get("param_value"),
                "timestamp": datetime.now().isoformat()
            }
        elif cmd == "set_mode":
            mode_data = data.get("cmd_param", {})
            response = {
                "type": "control_ack",
                "device_id": self.device_status["device_id"], 
                "request_id": request_id,
                "cmd": cmd,
                "exec_status": "success",
                "exec_msg": f"工作模式已切换为{mode_data.get('mode')}",
                "current_mode": mode_data.get("mode"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            response = {
                "type": "control_ack",
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "cmd": cmd,
                "exec_status": "fail",
                "error_code": 400,
                "exec_msg": f"未知指令: {cmd}",
                "timestamp": datetime.now().isoformat()
            }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
    
    async def handle_fault_record_list(self, websocket, data):
        """处理故障录波目录查询"""
        try:
            request_id = data.get("request_id")
            if not request_id:
                raise ValueError("缺少request_id参数")
            
            # 模拟从寄存器0x0300-0x0303读取的值
            total_records = len(self.fault_records)  # 0x0300: 当前故障录波记录数
            record_length = 3907                     # 0x0301: 记录长度
            max_capacity = 100                       # 0x0303: 最多存放记录数
            
            response = {
                "type": "fault_record_list_ack",
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "data": {
                    "total_records": total_records,
                    "record_length": record_length,
                    "max_capacity": max_capacity
                },
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
            
            await websocket.send(json.dumps(response, ensure_ascii=False))
            
        except Exception as e:
            error_response = {
                "type": "fault_record_list_ack",
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }
            await websocket.send(json.dumps(error_response, ensure_ascii=False))
    
    async def handle_fault_record_read(self, websocket, data):
        """处理故障录波读取"""
        request_id = data.get("request_id")
        record_id = data.get("record_id", 0)
        
        # 发送开始读取确认
        start_response = {
            "type": "fault_record_read_start",
            "device_id": self.device_status["device_id"],
            "request_id": request_id,
            "total_registers": 3907,
            "batch_size": 125,
            "total_batches": 32,
            "estimated_time": 15,
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send(json.dumps(start_response, ensure_ascii=False))
        
        # 模拟分批读取进度
        for batch in range(1, 33):
            await asyncio.sleep(0.5)  # 模拟读取延时
            
            progress_response = {
                "type": "fault_record_progress",
                "device_id": self.device_status["device_id"],
                "request_id": request_id,
                "current_batch": batch,
                "total_batches": 32,
                "percentage": round(batch / 32 * 100, 1),
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(progress_response, ensure_ascii=False))
        
        # 发送完整数据
        complete_response = {
            "type": "fault_record_complete",
            "device_id": self.device_status["device_id"],
            "request_id": request_id,
            "data": {
                "fault_info": {
                    "fault_time": "2024-09-29 13:45:12.345",
                    "fault_bits": "0x0001",
                    "fault_point": 150,
                    "record_cycle": 100
                },
                "data_points": [
                    {
                        "point_index": i,
                        "system_status": "0x0104",
                        "switch_input": "0x0200", 
                        "switch_output": "0x0101",
                        "rail_potential_max": random.randint(200, 300),
                        "max_polarization": random.randint(-150, -100),
                        "branch_currents": [random.randint(10, 15) for _ in range(6)],
                        "branch_voltages": [random.randint(220, 230) for _ in range(2)]
                    } for i in range(300)  # 300个数据点
                ]
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send(json.dumps(complete_response, ensure_ascii=False))
    
    async def handle_param_read(self, websocket, data):
        """处理参数读取"""
        request_id = data.get("request_id")
        read_type = data.get("read_type", "control_params")
        
        if read_type == "control_params":
            params = [
                {
                    "reg_addr": "0x2200",
                    "param_name": "过压保护延时(ms)",
                    "current_value": 500,
                    "value_range": "0-65535",
                    "unit": "ms"
                },
                {
                    "reg_addr": "0x2201", 
                    "param_name": "支路过流保护值(A)",
                    "current_value": 150,
                    "value_range": "0-500",
                    "unit": "A"
                }
            ]
        elif read_type == "sensor_params":
            params = {
                "sensor_down": [
                    {"channel": "AI1", "down_limit": -1000},
                    {"channel": "AI2", "down_limit": -1000}
                ],
                "sensor_up": [
                    {"channel": "AI1", "up_limit": 1000},
                    {"channel": "AI2", "up_limit": 1000}
                ]
            }
        else:
            params = []
        
        response = {
            "type": "param_read_ack",
            "device_id": self.device_status["device_id"],
            "request_id": request_id,
            "data": {"params": params} if read_type == "control_params" else params,
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
    
    async def broadcast_system_status(self):
        """广播系统状态数据"""
        if not self.connected_clients:
            return
            
        # 获取当前开关量状态
        km1_status = self.digital_data["output"].get("bit0", 0)
        
        system_status_data = {
            "type": "system_status",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": {
                "system_status": {
                    "bit5": 0,   # 故障状态：0=正常
                    "bit7": 1,   # 参数状态：1=正确
                    "bit8": 0,   # KM1状态：0=恢复
                    "bit9": 1    # 存储器：1=正常
                },
                "switch_output": {
                    "bit0": km1_status  # KM1状态
                }
            },
            "status": "success"
        }
        
        await self._broadcast_to_all(system_status_data)
    
    async def broadcast_analog_data(self):
        """广播模拟量数据"""
        if not self.connected_clients:
            return
            
        # 更新模拟量数值
        self._update_analog_values()
        
        analog_data = {
            "type": "analog_data",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": self.analog_data.copy(),
            "status": "success"
        }
        
        await self._broadcast_to_all(analog_data)
    
    async def broadcast_digital_data(self):
        """广播开关量数据"""
        if not self.connected_clients:
            return
            
        # 更新开关量数值
        self._update_digital_values()
        
        digital_data = {
            "type": "switch_io",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": self.digital_data.copy(),
            "status": "success"
        }
        
        # 添加详细日志
        km1_status = self.digital_data["output"].get("bit0", 0)
        logger.info(f"📡 广播开关量数据 - KM1状态: bit0={km1_status} ({'🟢合位' if km1_status == 1 else '🔴分位'})")
        logger.debug(f"完整开关量数据: {self.digital_data}")
        
        await self._broadcast_to_all(digital_data)
    
    async def broadcast_full_snapshot(self):
        """广播全量快照（每30秒）"""
        if not self.connected_clients:
            return
            
        # 更新所有数据
        self._update_analog_values()
        self._update_digital_values()
        
        full_snapshot = {
            "type": "full_snapshot",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": {
                "system_status": {
                    "bit0": 0, "bit1": 0, "bit5": 0, "bit7": 1, "bit8": 0, "bit9": 1, "bit15": 0
                },
                "switch_input": self.digital_data["input"],
                "switch_output": self.digital_data["output"],
                "analog_data": self.analog_data,
                "fault_status": {
                    "bit0": 0, "bit1": 0, "bit15": 0
                }
            },
            "status": "success"
        }
        
        await self._broadcast_to_all(full_snapshot)
    
    async def _broadcast_to_all(self, data):
        """向所有客户端广播数据"""
        disconnected_clients = []
        
        for websocket in list(self.connected_clients.keys()):
            try:
                await websocket.send(json.dumps(data, ensure_ascii=False))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(websocket)
            except Exception as e:
                logger.error(f"广播数据失败: {e}")
                disconnected_clients.append(websocket)
        
        # 清理断开的连接
        for websocket in disconnected_clients:
            await self.unregister_client(websocket)
    
    async def initialize_serial_communication(self):
        """初始化串口通信"""
        if not SERIAL_AVAILABLE:
            logger.info("串口模块不可用，使用模拟数据模式")
            self.serial_connected = False
            return
            
        try:
            # 使用项目中的配置管理器
            config_manager = ConfigManager()
            self.serial_manager = SerialManager(config_manager)
            
            # 注册串口数据回调
            self.serial_manager.register_data_callback(self._handle_serial_data)
            
            # 初始化串口管理器
            await self.serial_manager.initialize()
            
            # 启动轮询
            self.serial_manager.start_polling()
            self.serial_connected = True
            
            logger.info("✅ 串口通信已初始化并启动轮询")
            
        except Exception as e:
            logger.error(f"❌ 串口通信初始化失败: {e}")
            self.serial_connected = False
    
    async def _handle_serial_data(self, data_type: str, data: Dict[str, Any]) -> None:
        """处理串口接收到的数据"""
        try:
            serial_data: Dict[str, Any] = {
                'type': data_type,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            self.last_serial_data = serial_data
            
            # 根据数据类型进行相应的广播
            if data_type == 'system_status':
                await self.broadcast_system_status_from_serial(data)
            elif data_type == 'analog_data':
                await self.broadcast_analog_data_from_serial(data)
            elif data_type == 'switch_io':
                await self.broadcast_digital_data_from_serial(data)
                
        except Exception as e:
            logger.error(f"处理串口数据时出错: {e}")
    
    async def broadcast_system_status_from_serial(self, serial_data):
        """从串口数据广播系统状态"""
        if not self.connected_clients:
            return
            
        system_status_data = {
            "type": "system_status",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": serial_data,
            "source": "serial",
            "status": "success"
        }
        
        await self._broadcast_to_all(system_status_data)
    
    async def broadcast_analog_data_from_serial(self, serial_data):
        """从串口数据广播模拟量数据"""
        if not self.connected_clients:
            return
            
        analog_data = {
            "type": "analog_data",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": serial_data,
            "source": "serial",
            "status": "success"
        }
        
        await self._broadcast_to_all(analog_data)
    
    async def broadcast_digital_data_from_serial(self, serial_data):
        """从串口数据广播开关量数据"""
        if not self.connected_clients:
            return
            
        digital_data = {
            "type": "switch_io",
            "device_id": self.device_status["device_id"],
            "timestamp": datetime.now().isoformat(),
            "seq_num": self._get_next_seq_num(),
            "data": serial_data,
            "source": "serial",
            "status": "success"
        }
        
        # 添加详细日志
        if 'output' in serial_data and 'bit0' in serial_data['output']:
            km1_status = serial_data['output']['bit0']
            logger.info(f"📡 串口广播开关量数据 - KM1状态: bit0={km1_status} ({'🟢合位' if km1_status == 1 else '🔴分位'})")
        
        await self._broadcast_to_all(digital_data)
    
    async def periodic_broadcast(self):
        """定期广播任务"""
        last_full_snapshot = time.time()
        last_system_status = time.time()
        last_analog_data = time.time()
        last_digital_data = time.time()
        
        # 初始化串口通信
        await self.initialize_serial_communication()
        
        while True:
            try:
                current_time = time.time()
                
                # 如果串口连接正常，优先使用串口数据
                if self.serial_connected and self.last_serial_data:
                    # 串口数据已通过回调自动广播
                    pass
                else:
                    # 使用模拟数据作为备用
                    # 每3秒广播系统状态
                    if current_time - last_system_status >= 3:
                        await self.broadcast_system_status()
                        last_system_status = current_time
                    
                    # 每2秒广播模拟量数据（模拟量变化较频繁）
                    if current_time - last_analog_data >= 2:
                        await self.broadcast_analog_data()
                        last_analog_data = current_time
                    
                    # 每4秒广播开关量数据（开关量变化相对较少）
                    if current_time - last_digital_data >= 4:
                        await self.broadcast_digital_data()
                        last_digital_data = current_time
                
                # 每30秒广播全量快照
                if current_time - last_full_snapshot >= 30:
                    await self.broadcast_full_snapshot()
                    last_full_snapshot = current_time
                
                await asyncio.sleep(0.5)  # 检查间隔0.5秒
                
            except Exception as e:
                logger.error(f"定期广播任务异常: {e}")
                await asyncio.sleep(5)
    
    async def handle_client(self, websocket):
        """处理客户端连接"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"处理客户端连接异常: {e}")
        finally:
            await self.unregister_client(websocket)

async def main():
    """启动模拟服务器"""
    server = MockBackendServer()
    
    # 启动定期广播任务
    broadcast_task = asyncio.create_task(server.periodic_broadcast())
    
    # 启动WebSocket服务器
    logger.info("=" * 60)
    logger.info("启动模拟WebSocket服务器 (基于协议规范)")
    logger.info("服务器地址: ws://localhost:8765")
    logger.info("支持的消息类型:")
    logger.info("  - device_register: 设备注册")
    logger.info("  - heartbeat: 心跳检测")
    logger.info("  - control_cmd: 控制指令")
    logger.info("  - fault_record_list: 故障录波目录")
    logger.info("  - fault_record_read: 故障录波读取")
    logger.info("  - param_read: 参数读取")
    logger.info("自动推送数据:")
    logger.info("  - system_status: 系统状态 (每3秒)")
    logger.info("  - analog_data: 模拟量数据 (每2秒)")
    logger.info("  - switch_io: 开关量数据 (每4秒)")
    logger.info("  - full_snapshot: 全量快照 (每30秒)")
    logger.info("KM1状态变化频率: 20% (每次开关量更新时)")
    logger.info("按 Ctrl+C 停止服务器")
    logger.info("=" * 60)
    
    async with websockets.serve(server.handle_client, "localhost", 8765):
        try:
            await asyncio.Future()  # 永远运行
        except KeyboardInterrupt:
            logger.info("正在关闭服务器...")
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    asyncio.run(main())

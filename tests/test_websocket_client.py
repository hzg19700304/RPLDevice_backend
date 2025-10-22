#!/usr/bin/env python3
"""
WebSocket测试客户端
用于测试WebSocket服务器的各项功能
"""

import asyncio
import json
import logging
import websockets
import time
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WebSocketTestClient:
    """WebSocket测试客户端"""
    
    def __init__(self, uri: str = "ws://localhost:8766"):
        self.uri = uri
        self.websocket = None
        self.is_connected = False
        self.message_count = 0
        self.last_message_time = None
        
        # 测试统计
        self.stats = {
            "messages_received": 0,
            "messages_sent": 0,
            "connection_time": None,
            "last_activity": None
        }
    
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            logger.info(f"正在连接到 {self.uri}...")
            self.websocket = await websockets.connect(self.uri)
            self.is_connected = True
            self.stats["connection_time"] = datetime.now().isoformat()
            logger.info("连接成功")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("连接已断开")
    
    async def send_message(self, message: Dict[str, Any]):
        """发送消息到服务器"""
        if not self.is_connected:
            logger.error("未连接到服务器")
            return False
        
        try:
            message_str = json.dumps(message)
            await self.websocket.send(message_str)
            self.stats["messages_sent"] += 1
            self.stats["last_activity"] = datetime.now().isoformat()
            logger.debug(f"发送消息: {message['type']}")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def receive_messages(self, timeout: int = 30):
        """接收消息"""
        if not self.is_connected:
            logger.error("未连接到服务器")
            return
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=1.0
                    )
                    
                    # 处理接收到的消息
                    await self.handle_message(message)
                    
                except asyncio.TimeoutError:
                    # 超时是正常的，继续等待
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info("连接已关闭")
                    self.is_connected = False
                    break
                    
        except Exception as e:
            logger.error(f"接收消息时出错: {e}")
    
    async def handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "unknown")
            
            self.stats["messages_received"] += 1
            self.stats["last_activity"] = datetime.now().isoformat()
            
            # 根据消息类型处理
            if message_type == "connect_ack":
                logger.info(f"收到连接确认: {data.get('connection_id')}")
            elif message_type == "welcome":
                logger.info(f"收到欢迎消息: {data.get('message')}")
            elif message_type == "heartbeat_ack":
                logger.info(f"收到心跳响应: 设备在线={data.get('summary', {}).get('device_online')}")
            elif message_type == "control_ack":
                logger.info(f"收到控制响应: {data.get('cmd')} - {data.get('exec_status')}")
            elif message_type == "fault_record_list_ack":
                logger.info(f"收到故障录波目录: {data.get('data', {}).get('total_records')}条记录")
            elif message_type == "param_read_ack":
                logger.info(f"收到参数读取响应: {len(data.get('data', {}).get('params', []))}个参数")
            elif message_type == "system_status":
                logger.info(f"收到系统状态: 设备ID={data.get('device_id')}")
            elif message_type == "analog_data":
                logger.info(f"收到模拟量数据: {len(data.get('data', []))}个通道")
            elif message_type == "switch_io":
                logger.info(f"收到开关量数据")
            elif message_type == "full_snapshot":
                logger.info("收到全量快照数据")
            elif message_type == "error":
                logger.error(f"收到错误消息: {data.get('error_code')} - {data.get('error_msg')}")
            else:
                logger.info(f"收到未知类型消息: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"消息JSON解析失败: {e}")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
    
    async def test_device_registration(self):
        """测试设备注册"""
        registration_message = {
            "type": "device_register",
            "device_id": "HYP_RPLD_001",
            "device_name": "红岩坪站钢轨电位限制装置",
            "timestamp": datetime.now().isoformat()
        }
        
        return await self.send_message(registration_message)
    
    async def test_heartbeat(self):
        """测试心跳"""
        heartbeat_message = {
            "type": "heartbeat",
            "device_id": "HYP_RPLD_001",
            "timestamp": datetime.now().isoformat(),
            "seq_num": 2
        }
        
        return await self.send_message(heartbeat_message)
    
    async def test_control_command(self, command: str = "fault_reset"):
        """测试控制指令"""
        control_message = {
            "type": "control_cmd",
            "device_id": "HYP_RPLD_001",
            "request_id": 1001,
            "cmd": command,
            "timestamp": datetime.now().isoformat()
        }
        
        return await self.send_message(control_message)
    
    async def test_fault_record_list(self):
        """测试故障录波目录查询"""
        query_message = {
            "type": "fault_record_list",
            "device_id": "HYP_RPLD_001",
            "request_id": 1002,
            "timestamp": datetime.now().isoformat()
        }
        
        return await self.send_message(query_message)
    
    async def test_param_read(self):
        """测试参数读取"""
        query_message = {
            "type": "param_read",
            "device_id": "HYP_RPLD_001",
            "request_id": 1003,
            "read_type": "control_params",
            "timestamp": datetime.now().isoformat()
        }
        
        return await self.send_message(query_message)
    
    async def run_comprehensive_test(self, duration: int = 60):
        """运行综合测试"""
        if not await self.connect():
            return False
        
        logger.info("开始综合测试...")
        
        # 测试设备注册
        logger.info("测试设备注册...")
        await self.test_device_registration()
        await asyncio.sleep(1)
        
        # 测试心跳
        logger.info("测试心跳...")
        await self.test_heartbeat()
        await asyncio.sleep(1)
        
        # 测试控制指令
        logger.info("测试控制指令...")
        await self.test_control_command("read_params")
        await asyncio.sleep(1)
        
        # 测试故障录波目录查询
        logger.info("测试故障录波目录查询...")
        await self.test_fault_record_list()
        await asyncio.sleep(1)
        
        # 测试参数读取
        logger.info("测试参数读取...")
        await self.test_param_read()
        await asyncio.sleep(1)
        
        # 开始接收消息
        logger.info("开始接收实时数据...")
        receive_task = asyncio.create_task(self.receive_messages(duration))
        
        # 定期发送心跳
        heartbeat_task = asyncio.create_task(self._periodic_heartbeat(duration))
        
        # 等待测试完成
        await asyncio.gather(receive_task, heartbeat_task)
        
        # 断开连接
        await self.disconnect()
        
        # 打印测试统计
        self.print_test_stats()
        
        return True
    
    async def _periodic_heartbeat(self, duration: int):
        """定期发送心跳"""
        start_time = time.time()
        heartbeat_count = 0
        
        while time.time() - start_time < duration:
            if self.is_connected:
                await self.test_heartbeat()
                heartbeat_count += 1
            await asyncio.sleep(10)  # 每10秒发送一次心跳
    
    def print_test_stats(self):
        """打印测试统计"""
        logger.info("=" * 50)
        logger.info("测试统计:")
        logger.info(f"连接时间: {self.stats['connection_time']}")
        logger.info(f"最后活动: {self.stats['last_activity']}")
        logger.info(f"发送消息数: {self.stats['messages_sent']}")
        logger.info(f"接收消息数: {self.stats['messages_received']}")
        logger.info("=" * 50)


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建测试客户端
    client = WebSocketTestClient()
    
    # 运行综合测试
    await client.run_comprehensive_test(duration=30)


if __name__ == "__main__":
    asyncio.run(main())
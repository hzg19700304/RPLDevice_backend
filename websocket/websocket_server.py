#!/usr/bin/env python3
# flake8: noqa
"""
WebSocket服务器主文件
基于WebSocket及API接口协议完整版实现
"""

import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Set, Optional
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket.connection_manager import ConnectionManager
from websocket.message_handler import MessageHandler
from websocket.data_pusher import DataPusher
from websocket.auth_manager import AuthManager
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket服务器主类"""
    
    def __init__(self, config_manager: ConfigManager, serial_manager=None):
        self.config_manager = config_manager
        self.connection_manager = ConnectionManager()
        self.message_handler = MessageHandler(self.connection_manager, config_manager, serial_manager=serial_manager)
        self.data_pusher = DataPusher(self.connection_manager, config_manager, serial_manager=serial_manager)
        # 保存串口管理器以便生成连接状态摘要
        self.serial_manager = serial_manager
        self.auth_manager = AuthManager(config_manager)
        
        # 获取WebSocket配置
        self.websocket_config = config_manager.get_websocket_config()
        self.listen_ip = self.websocket_config.get('listen_ip', '0.0.0.0')
        self.listen_port = self.websocket_config.get('listen_port', 8765)
        self.heartbeat_interval = self.websocket_config.get('heartbeat_interval', 10)
        
        # 服务器状态
        self.is_running = False
        self.server = None
        
    async def start_server(self):
        """启动WebSocket服务器"""
        try:
            # 启动数据推送器（在后台运行）
            self.data_pusher_task = asyncio.create_task(self.data_pusher.start_data_pushing())
            
            # 启动WebSocket服务器
            self.server = await websockets.serve(
                self.handle_connection,
                self.listen_ip,
                self.listen_port
            )
            
            self.is_running = True
            logger.info(f"WebSocket服务器已启动，监听地址: {self.listen_ip}:{self.listen_port}")
            
            # 等待服务器关闭
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"WebSocket服务器启动失败: {e}")
            raise
    
    async def handle_connection(self, websocket):
        """处理WebSocket连接"""
        # 简化连接处理 - 直接接受所有连接
        connection_info = await self.connection_manager.register_connection(
            websocket, {"user_type": "test", "device_id": "test_device"}
        )
        
        # 发送连接确认
        await self._send_connect_ack(websocket, connection_info)
        # 发送一次合并后的连接状态（包含websocket与串口状态）
        await self._send_connection_status(websocket)
        
        try:
            # 处理消息循环
            async for message in websocket:
                await self.message_handler.handle_message(websocket, message, connection_info)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"连接已关闭: {connection_info['connection_id']}")
        except Exception as e:
            logger.error(f"处理连接时出错: {e}")
        finally:
            # 注销连接
            await self.connection_manager.unregister_connection(websocket)
    
    def _parse_query_params(self, path: str) -> Dict[str, str]:
        """解析查询参数"""
        params = {}
        if '?' in path:
            query_string = path.split('?', 1)[1]
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
        return params
    
    async def _send_connect_ack(self, websocket, connection_info: Dict[str, Any]):
        """发送连接确认"""
        connect_ack = {
            "type": "connect_ack",
            "status": "success",
            "connection_id": connection_info['connection_id'],
            "device_id": self.config_manager.get_device_info().get('device_id', 'HYP_RPLD_001'),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await websocket.send(json.dumps(connect_ack, ensure_ascii=False))
            logger.info(f"连接确认已发送: {connection_info['connection_id']}")
        except Exception as e:
            logger.error(f"发送连接确认失败: {e}")
    
    async def _send_connect_fail(self, websocket, error_code: int, error_msg: str):
        """发送连接失败响应"""
        connect_fail = {
            "type": "connect_fail",
            "status": "error",
            "error_code": error_code,
            "error_msg": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await websocket.send(json.dumps(connect_fail, ensure_ascii=False))
            await websocket.close()
        except Exception as e:
            logger.error(f"发送连接失败响应失败: {e}")

    async def _send_connection_status(self, websocket=None):
        """发送合并后的连接状态（websocket + 串口）"""
        try:
            # websocket 连接状态：如果websocket对象存在且在活跃连接列表中，则认为已连接
            websocket_connected = bool(websocket and websocket in self.connection_manager.active_connections)
            # 对所有连接广播时，websocket_connected 恒为True）  
            if websocket is None:
                websocket_connected = True
            # 串口状态
            hmi_ok = False
            scada_ok = False
            if self.serial_manager:
                try:
                    hmi_ok = bool(getattr(self.serial_manager, 'hmi_master', None) and self.serial_manager.hmi_master.is_open())
                except Exception:
                    hmi_ok = False
                try:
                    scada_ok = bool(getattr(self.serial_manager, 'scada_master', None) and self.serial_manager.scada_master.is_open())
                except Exception:
                    scada_ok = False
            #构建消息体
            payload = {
                "type": "connection_status",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "websocket_connected": websocket_connected,
                    "hmi_serial_available": hmi_ok,
                    "scada_serial_available": scada_ok,
                    "control_board_serial_available": hmi_ok  # 控制板串口状态（与HMI串口相同）
                }
            }
            #序列化消息体
            text = json.dumps(payload, ensure_ascii=False)
            # 发送消息
            if websocket is not None: 
                await websocket.send(text) # 单播
            else:
                await self.connection_manager.broadcast_to_all(payload) # 广播
        except Exception as e:
            logger.error(f"发送连接状态失败: {e}")

    async def broadcast_connection_status(self):
        """向所有连接广播一次合并后的连接状态"""
        await self._send_connection_status(websocket=None)
    
    async def _send_error(self, websocket, error_msg: str):
        """发送错误响应"""
        error_response = {
            "type": "error",
            "error_code": 400,
            "error_msg": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await websocket.send(json.dumps(error_response, ensure_ascii=False))
            await websocket.close()
        except Exception as e:
            logger.error(f"发送错误响应失败: {e}")
    
    async def stop_server(self):
        """停止WebSocket服务器"""
        if self.server:
            # 停止数据推送器
            await self.data_pusher.stop_data_pushing()
            
            # 取消数据推送任务
            if hasattr(self, 'data_pusher_task') and not self.data_pusher_task.done():
                self.data_pusher_task.cancel()
                try:
                    await self.data_pusher_task
                except asyncio.CancelledError:
                    pass
            
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False
            logger.info("WebSocket服务器已停止")


async def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 加载配置
        config_manager = ConfigManager()
        await config_manager.load_config()
        
        # 创建并启动WebSocket服务器
        server = WebSocketServer(config_manager)
        await server.start_server()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())
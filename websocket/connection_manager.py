#!/usr/bin/env python3
# flake8: noqa
"""
WebSocket连接管理器
管理所有WebSocket连接的注册、注销和状态跟踪
"""

import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Set, Optional, List
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 活跃连接字典：websocket -> connection_info
        self.active_connections: Dict[websockets.WebSocketServerProtocol, Dict] = {}
        
        # 连接统计信息
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'max_concurrent_connections': 0,
            'total_messages_sent': 0,
            'total_messages_received': 0
        }
        
        # 心跳管理
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        # 序列号计数器
        self.seq_num = 1000
        
    async def register_connection(self, websocket, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """注册新连接"""
        connection_id = f"conn_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        connection_info = {
            'connection_id': connection_id,
            'websocket': websocket,
            'user_info': user_info,
            'connected_at': datetime.now(),
            'last_heartbeat': datetime.now(),
            'message_count_sent': 0,
            'message_count_received': 0,
            'device_registered': False,
            'device_id': None,
            'device_name': None
        }
        
        logger.info(f"开始注册连接: {connection_id}, websocket: {websocket}")
        self.active_connections[websocket] = connection_info
        logger.info(f"连接已添加到active_connections: {connection_id}")
        
        # 更新统计信息
        self.connection_stats['total_connections'] += 1
        self.connection_stats['active_connections'] = len(self.active_connections)
        self.connection_stats['max_concurrent_connections'] = max(
            self.connection_stats['max_concurrent_connections'],
            len(self.active_connections)
        )
        
        # 启动心跳监控任务
        self.heartbeat_tasks[connection_id] = asyncio.create_task(
            self._monitor_heartbeat(connection_id)
        )
        
        logger.info(f"连接已注册: {connection_id}, 活跃连接数: {len(self.active_connections)}")
        logger.debug(f"连接详情: {connection_info}")
        
        return connection_info
    
    async def unregister_connection(self, websocket):
        """注销连接"""
        if websocket in self.active_connections:
            connection_info = self.active_connections.pop(websocket)
            connection_id = connection_info['connection_id']
            
            # 取消心跳监控任务
            if connection_id in self.heartbeat_tasks:
                self.heartbeat_tasks[connection_id].cancel()
                del self.heartbeat_tasks[connection_id]
            
            # 更新统计信息
            self.connection_stats['active_connections'] = len(self.active_connections)
            
            logger.info(f"连接已注销: {connection_id}, 活跃连接数: {len(self.active_connections)}")
            
            return connection_info
        
        return None
    
    async def update_heartbeat(self, websocket):
        """更新心跳时间"""
        if websocket in self.active_connections:
            self.active_connections[websocket]['last_heartbeat'] = datetime.now()
    
    async def register_device(self, websocket, device_id: str, device_name: str):
        """注册设备信息"""
        if websocket in self.active_connections:
            self.active_connections[websocket]['device_registered'] = True
            self.active_connections[websocket]['device_id'] = device_id
            self.active_connections[websocket]['device_name'] = device_name
            
            logger.info(f"设备已注册: {device_id} - {device_name}")
    
    def get_next_seq_num(self) -> int:
        """获取下一个序列号"""
        self.seq_num += 1
        return self.seq_num
    
    def get_connection_info(self, websocket) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        return self.active_connections.get(websocket)
    
    def get_all_connections(self) -> List[Dict[str, Any]]:
        """获取所有连接信息"""
        return list(self.active_connections.values())
    
    def get_active_connection_count(self) -> int:
        """获取活跃连接数"""
        return len(self.active_connections)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """向所有连接广播消息"""
        if not self.active_connections:  # 如果没有活跃连接，直接返回
            return

        message_json = json.dumps(message, ensure_ascii=False)  # 序列化消息
        disconnected_websockets = []

        # 创建连接列表的副本以避免在遍历时修改字典
        connections_copy = list(self.active_connections.items())
        
        # 遍历所有连接
        for websocket, connection_info in connections_copy:
            if websocket not in self.active_connections:  # 检查连接是否仍然存在
                continue
                
            try:
                await websocket.send(message_json)  # 发送消息
                connection_info['message_count_sent'] += 1  # 更新每个连接的发送计数
                self.connection_stats['total_messages_sent'] += 1  # 更新统计信息
            except websockets.exceptions.ConnectionClosed:  # 连接已关闭
                disconnected_websockets.append(websocket)
            except Exception as e:  # 其他异常
                logger.error(f"广播消息失败: {e}")
                disconnected_websockets.append(websocket)  # 标记为断开连接
        
        # 清理断开的连接
        for websocket in disconnected_websockets:
            await self.unregister_connection(websocket)  # 注销连接
    
    async def send_to_connection(
        self,
        websocket,
        message: Dict[str, Any]
    ) -> bool:
        """向指定连接发送消息"""
        if websocket not in self.active_connections:
            return False
        
        try:
            await websocket.send(json.dumps(message, ensure_ascii=False))
            self.active_connections[websocket]['message_count_sent'] += 1
            self.connection_stats['total_messages_sent'] += 1
            return True
        except websockets.exceptions.ConnectionClosed:
            await self.unregister_connection(websocket)
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            await self.unregister_connection(websocket)
            return False
    
    async def _monitor_heartbeat(self, connection_id: str):
        """监控心跳"""
        try:
            # 等待初始心跳建立时间
            await asyncio.sleep(5)  # 给连接5秒时间建立初始心跳
            
            while True:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                # 查找对应的连接
                websocket_to_check = None
                for websocket, info in self.active_connections.items():
                    if info['connection_id'] == connection_id:
                        websocket_to_check = websocket
                        break
                
                if not websocket_to_check:
                    logger.info(f"连接 {connection_id} 已不存在，心跳监控任务退出")
                    break
                
                connection_info = self.active_connections[websocket_to_check]
                last_heartbeat = connection_info['last_heartbeat']
                time_since_last_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
                
                # 如果超过60秒没有心跳，断开连接
                if time_since_last_heartbeat > 60:
                    logger.warning(f"连接 {connection_id} 心跳超时，即将断开")
                    
                    # 发送连接丢失通知
                    connection_lost_msg = {
                        "type": "connection_lost",
                        "reason": "心跳超时",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    try:
                        await websocket_to_check.send(json.dumps(connection_lost_msg, ensure_ascii=False))
                    except:
                        pass
                    
                    # 断开连接
                    await self.unregister_connection(websocket_to_check)
                    break
                    
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            logger.info(f"连接 {connection_id} 的心跳监控任务被取消")
            pass
        except Exception as e:
            logger.error(f"心跳监控任务出错: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        stats = self.connection_stats.copy()
        
        # 添加设备注册信息
        registered_devices = 0
        for connection_info in self.active_connections.values():
            if connection_info['device_registered']:
                registered_devices += 1
        
        stats['registered_devices'] = registered_devices
        stats['unregistered_connections'] = len(self.active_connections) - registered_devices
        
        return stats
    
    async def close_all_connections(self):
        """关闭所有连接"""
        logger.info("正在关闭所有WebSocket连接...")
        
        # 发送关闭通知
        close_message = {
            "type": "server_shutdown",
            "message": "服务器正在关闭",
            "timestamp": datetime.now().isoformat()
        }
        
        close_message_json = json.dumps(close_message, ensure_ascii=False)
        
        disconnected_websockets = []
        for websocket in list(self.active_connections.keys()):
            try:
                await websocket.send(close_message_json)
                await websocket.close()
            except:
                pass
            disconnected_websockets.append(websocket)
        
        # 清理所有连接
        for websocket in disconnected_websockets:
            await self.unregister_connection(websocket)
        
        # 取消所有心跳任务
        for task in self.heartbeat_tasks.values():
            task.cancel()
        
        self.heartbeat_tasks.clear()
        
        logger.info("所有WebSocket连接已关闭")
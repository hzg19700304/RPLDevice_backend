#!/usr/bin/env python3
# flake8: noqa
"""
WebSocket数据推送器
负责定时推送各种类型的数据到客户端
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from websocket.connection_manager import ConnectionManager
from config.config_manager import ConfigManager
from serial_comm.serial_manager import SerialManager

logger = logging.getLogger(__name__)


class DataPusher:
    """WebSocket数据推送器"""
    
    def __init__(self, connection_manager: ConnectionManager, config_manager: ConfigManager, serial_manager: Optional[SerialManager] = None):
        self.connection_manager = connection_manager
        self.config_manager = config_manager
        self.serial_manager = serial_manager
        
        # 数据推送配置
        self.push_config = {
            'system_status_interval': 1.0,      # 系统状态推送间隔（秒）
            'analog_data_interval': 1.0,        # 模拟量推送间隔（秒）
            'digital_data_interval': 1.0,       # 开关量推送间隔（秒）
            'full_snapshot_interval': 30.0,    # 全量快照推送间隔（秒）
            'fault_check_interval': 5.0        # 故障检查间隔（秒）
        }
        
        # 缓存真实数据
        self.cached_system_status = {}
        self.cached_analog_data = []
        self.cached_fault_status = {}
        self.cached_igbt_fiber_status = {}
        
        # 推送任务
        self.push_tasks = []
        self.is_running = False
        
        # 全量快照计数器
        self.full_snapshot_counter = 0
        
        # 注册串口数据回调（如果有SerialManager）
        if self.serial_manager:
            self.serial_manager.register_hmi_data_callback(self._on_serial_data_received)
    
    async def start_data_pushing(self):
        """启动数据推送任务"""
        if self.is_running:
            logger.warning("数据推送器已经在运行")
            return
        
        self.is_running = True
        
        # 启动各种数据推送任务
        tasks = [
            asyncio.create_task(self._push_system_status()),
            asyncio.create_task(self._push_analog_data()),
            asyncio.create_task(self._push_full_snapshot()),
            asyncio.create_task(self._check_fault_status())
        ]
        
        self.push_tasks = tasks
        
        logger.info("数据推送器已启动")
        
        # 等待所有任务完成（通常不会发生，除非服务器停止）
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("数据推送任务被取消")
        except Exception as e:
            logger.error(f"数据推送任务出错: {e}")
    
    async def stop_data_pushing(self):
        """停止数据推送任务"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 取消所有任务
        for task in self.push_tasks:
            task.cancel()
        
        # 等待任务完成取消
        await asyncio.gather(*self.push_tasks, return_exceptions=True)
        
        self.push_tasks = []
        logger.info("数据推送器已停止")
    
    async def _push_system_status(self):
        """推送系统状态数据"""
        while self.is_running:
            try:
                # 获取设备信息
                device_info = self.config_manager.get_device_info()
                
                # 构建系统状态消息
                system_status_data = {
                    "type": "system_status",
                    "device_id": device_info.get("device_id", "HYP_RPLD_001"),
                    "timestamp": datetime.now().isoformat(),
                    "seq_num": self.connection_manager.get_next_seq_num(),
                    "data": self.cached_system_status,
                    "status": "success"
                }
                
                # 广播到所有连接
                await self.connection_manager.broadcast_to_all(system_status_data)
                
                # 等待推送间隔
                await asyncio.sleep(self.push_config['system_status_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"推送系统状态数据时出错: {e}")
                await asyncio.sleep(1)  # 出错后等待1秒再重试
    
    async def _push_analog_data(self):
        """推送模拟量数据"""
        while self.is_running:
            try:
                # 获取设备信息
                device_info = self.config_manager.get_device_info()
                
                # 构建模拟量消息
                analog_data = {
                    "type": "analog_data",
                    "device_id": device_info.get("device_id", "HYP_RPLD_001"),
                    "timestamp": datetime.now().isoformat(),
                    "seq_num": self.connection_manager.get_next_seq_num(),
                    "data": self.cached_analog_data.copy(),
                    "status": "success"
                }
                
                # 广播到所有连接
                await self.connection_manager.broadcast_to_all(analog_data)
                
                # 等待推送间隔
                await asyncio.sleep(self.push_config['analog_data_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"推送模拟量数据时出错: {e}")
                await asyncio.sleep(1)
    
    # switch_io数据类型已合并到system_status中，不再单独推送
    # async def _push_digital_data(self):
    #     """推送开关量数据"""
    #     while self.is_running:
    #         try:
    #             # 获取设备信息
    #             device_info = self.config_manager.get_device_info()
    #             
    #             # 构建开关量消息
    #             digital_data = {
    #                 "type": "switch_io",
    #                 "device_id": device_info.get("device_id", "HYP_RPLD_001"),
    #                 "timestamp": datetime.now().isoformat(),
    #                 "seq_num": self.connection_manager.get_next_seq_num(),
    #                 "data": self.cached_digital_data.copy(),
    #                 "status": "success"
    #             }
    #             
    #             # 广播到所有连接
    #             await self.connection_manager.broadcast_to_all(digital_data)
    #             
    #             # 等待推送间隔
    #             await asyncio.sleep(self.push_config['digital_data_interval'])
    #             
    #         except asyncio.CancelledError:
    #             break
    #         except Exception as e:
    #             logger.error(f"推送开关量数据时出错: {e}")
    #             await asyncio.sleep(1)
    
    async def _push_full_snapshot(self):
        """推送全量快照数据"""
        while self.is_running:
            try:
                # 检查是否到达推送时间
                self.full_snapshot_counter += 1
                if self.full_snapshot_counter * self.push_config['system_status_interval'] < self.push_config['full_snapshot_interval']:
                    await asyncio.sleep(self.push_config['system_status_interval'])
                    continue
                
                # 重置计数器
                self.full_snapshot_counter = 0
                
                # 获取设备信息
                device_info = self.config_manager.get_device_info()
                
                # 构建全量快照消息
                full_snapshot_data = {
                    "type": "full_snapshot",
                    "device_id": device_info.get("device_id", "HYP_RPLD_001"),
                    "timestamp": datetime.now().isoformat(),
                    "seq_num": self.connection_manager.get_next_seq_num(),
                    "data": {
                        "system_status": self.cached_system_status,
                        "analog_data": self.cached_analog_data.copy()
                    },
                    "status": "success"
                }
                
                # 广播到所有连接
                await self.connection_manager.broadcast_to_all(full_snapshot_data)
                
                logger.info("全量快照数据已推送")
                
                # 等待推送间隔
                await asyncio.sleep(self.push_config['system_status_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"推送全量快照数据时出错: {e}")
                await asyncio.sleep(1)
    
    async def _check_fault_status(self):
        """检查故障状态"""
        while self.is_running:
            try:
                # 获取设备信息
                device_info = self.config_manager.get_device_info()
                
                # 检查是否有故障状态变化
                old_fault_status = self.cached_fault_status.copy()
                
                # 如果有故障状态变化，推送故障消息
                if self.cached_fault_status != old_fault_status:
                    fault_data = {
                        "type": "fault",
                        "device_id": device_info.get("device_id", "HYP_RPLD_001"),
                        "timestamp": datetime.now().isoformat(),
                        "seq_num": self.connection_manager.get_next_seq_num(),
                        "data": {
                            "fault_bits": self.cached_fault_status,
                            "fault_desc": "系统故障状态变化",
                            "fault_status": 1 if any(self.cached_fault_status.values()) else 0
                        },
                        "status": "success"
                    }
                    
                    await self.connection_manager.broadcast_to_all(fault_data)
                    logger.info("故障状态变化已推送")
                
                # 等待检查间隔
                await asyncio.sleep(self.push_config['fault_check_interval'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"检查故障状态时出错: {e}")
                await asyncio.sleep(1)
    
    def _on_serial_data_received(self, data_type: str, data: dict):
        """串口数据回调函数"""
        try:
            if data_type == 'system_status':
                self.cached_system_status = data if isinstance(data, dict) else {}
                # 如果系统状态数据中包含IGBT光纤状态，单独缓存
                if isinstance(data, dict) and 'igbt_fiber_status' in data:
                    self.cached_igbt_fiber_status = data['igbt_fiber_status']
                    logger.debug(f"IGBT光纤状态数据已缓存: {self.cached_igbt_fiber_status}")
                # 如果系统状态数据中包含故障状态，单独缓存
                if isinstance(data, dict) and 'fault_status' in data:
                    self.cached_fault_status = data['fault_status']
                    logger.debug(f"故障状态数据已缓存: {self.cached_fault_status}")
            elif data_type == 'analog_data':
                self.cached_analog_data = data if isinstance(data, list) else []
            else:
                logger.warning(f"未知的数据类型: {data_type}")
        except Exception as e:
            logger.error(f"处理串口数据回调时出错: {e}")
    
    def get_push_statistics(self) -> Dict[str, Any]:
        """获取推送统计信息"""
        return {
            "is_running": self.is_running,
            "active_tasks": len(self.push_tasks),
            "push_config": self.push_config,
            "full_snapshot_counter": self.full_snapshot_counter
        }
    
    async def start(self):
        """启动数据推送（简化方法，兼容测试代码）"""
        return await self.start_data_pushing()
    
    async def stop(self):
        """停止数据推送（简化方法，兼容测试代码）"""
        return await self.stop_data_pushing()
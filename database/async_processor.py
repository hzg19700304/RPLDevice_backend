# flake8: noqa
"""
异步数据处理器
负责异步数据插入和批量处理，提高数据库写入性能
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from queue import Queue, Empty
from threading import Lock
import time

from .models import StatusHistory, RealTimeData, EventRecords, DeviceDataConverter
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AsyncDataProcessor:
    """异步数据处理器"""
    
    def __init__(self, database_manager: DatabaseManager, batch_size: int = 100, flush_interval: float = 5.0):
        self.database_manager = database_manager
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # 数据队列
        self.status_queue = Queue()
        self.real_time_queue = Queue()
        self.event_queue = Queue()
        
        # 批量缓冲区
        # 注意：状态缓冲区不再使用，状态历史数据通过insert_status_immediately直接插入数据库
        self.real_time_buffer: List[RealTimeData] = []
        self.event_buffer: List[EventRecords] = []
        
        # 锁和状态
        self.lock = Lock()
        self.is_running = False
        self.processing_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            'real_time_inserted': 0,
            'event_inserted': 0,
            'last_flush_time': time.time(),
            'errors': 0
        }
        
        self.data_converter = DeviceDataConverter()
    
    def _clear_all_buffers_and_queues(self):
        """清空所有缓冲区和队列"""
        # 清空缓冲区
        # 注意：状态缓冲区不再使用
        self.real_time_buffer.clear()
        self.event_buffer.clear()
        
        # 清空队列
        while not self.status_queue.empty():
            try:
                self.status_queue.get_nowait()
            except Empty:
                break
        
        while not self.real_time_queue.empty():
            try:
                self.real_time_queue.get_nowait()
            except Empty:
                break
        
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Empty:
                break
        
        # logger.debug("所有缓冲区和队列已清空")  # 调试信息已注释
    
    async def start(self) -> bool:
        """启动异步处理器"""
        if self.is_running:
            logger.warning("异步处理器已经在运行")
            return True
        
        # logger.info("开始启动异步数据处理器...")  # 调试信息已注释
        
        try:
            # 在启动前清空所有缓冲区和队列，避免残留测试数据
            # logger.debug("清空所有缓冲区和队列...")  # 调试信息已注释
            self._clear_all_buffers_and_queues()
            
            self.is_running = True
            # logger.debug("设置处理器运行状态为True")  # 调试信息已注释
            
            self.processing_task = asyncio.create_task(self._processing_loop())
            # logger.debug("创建异步处理任务")  # 调试信息已注释
            
            # logger.info("异步数据处理器已成功启动")  # 调试信息已注释
            # logger.debug(f"处理器配置 - 批量大小: {self.batch_size}, 刷新间隔: {self.flush_interval}秒")  # 调试信息已注释
            return True
        except Exception as e:
            logger.error(f"启动异步处理器失败: {e}")
            logger.error(f"失败类型: {type(e).__name__}")
            self.is_running = False
            return False
    
    async def stop(self) -> bool:
        """停止异步处理器"""
        if not self.is_running:
            # logger.debug("异步处理器未运行，无需停止")  # 调试信息已注释
            return True
        
        # logger.info("开始停止异步数据处理器...")  # 调试信息已注释
        
        try:
            self.is_running = False
            # logger.debug("设置处理器运行状态为False")  # 调试信息已注释
            
            # 等待处理任务完成
            if self.processing_task:
                # logger.debug("等待异步处理任务完成...")  # 调试信息已注释
                await self.processing_task
                # logger.debug("异步处理任务已完成")  # 调试信息已注释
            
            # 刷新所有缓冲区
            # logger.debug("开始刷新所有缓冲区...")  # 调试信息已注释
            await self._flush_all_buffers()
            # logger.debug("所有缓冲区已刷新")  # 调试信息已注释
            
            # logger.info("异步数据处理器已成功停止")  # 调试信息已注释
            # logger.debug(f"最终统计信息: {self.stats}")  # 调试信息已注释
            return True
        except Exception as e:
            logger.error(f"停止异步处理器失败: {e}")
            logger.error(f"失败类型: {type(e).__name__}")
            return False
    
    def get_processor_status(self) -> dict:
        """获取处理器状态信息"""
        return {
            "is_running": self.is_running,
            "queue_sizes": {
                "status_queue": self.status_queue.qsize(),
                "real_time_queue": self.real_time_queue.qsize(),
                "event_queue": self.event_queue.qsize()
            },
            "buffers": {
                "real_time_buffer": len(self.real_time_buffer),
                "event_buffer": len(self.event_buffer)
            },
            "statistics": {
                "real_time_inserted": self.stats['real_time_inserted'],
                "event_inserted": self.stats['event_inserted'],
                "last_flush_time": self.stats['last_flush_time'],
                "errors": self.stats['errors']
            }
        }
    
    async def _processing_loop(self):
        """异步处理循环"""
        last_flush_time = time.time()
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # 处理队列中的数据
                await self._process_queues()
                
                # 检查是否需要刷新缓冲区
                # 注意：状态缓冲区不再使用，只检查实时数据和事件缓冲区
                if (current_time - last_flush_time >= self.flush_interval or
                    len(self.real_time_buffer) >= self.batch_size or
                    len(self.event_buffer) >= self.batch_size):
                    
                    await self._flush_all_buffers()
                    last_flush_time = current_time
                
                # 短暂休眠避免CPU占用过高
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"异步处理循环错误: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(1)  # 错误后短暂休眠
    
    async def _process_queues(self):
        """处理队列中的数据"""
        # 注意：状态历史数据不应该在这里处理，它们应该通过insert_status_immediately直接插入数据库
        # 这里只处理实时数据和事件数据
        
        # 处理实时数据队列
        while not self.real_time_queue.empty():
            try:
                device_id, real_time_data = self.real_time_queue.get_nowait()
                # logger.debug(f"从实时数据队列获取数据 - 设备: {device_id}, 数据: {real_time_data}")  # 调试信息已注释
                
                # 使用数据转换器将字典转换为模型对象
                real_time_record = self.data_converter.convert_to_real_time_data(
                    real_time_data,
                    real_time_data.get("parameter_name", "unknown"),
                    real_time_data.get("value", 0.0),
                    real_time_data.get("unit", "N/A"),
                    device_id
                )
                
                # logger.debug(f"实时数据转换完成 - 记录类型: {type(real_time_record).__name__}")  # 调试信息已注释
                
                self.real_time_buffer.append(real_time_record)
                # logger.debug(f"实时数据记录已添加到缓冲区，当前缓冲区大小: {len(self.real_time_buffer)}")  # 调试信息已注释
                
                if len(self.real_time_buffer) >= self.batch_size:
                    # logger.debug(f"实时数据缓冲区达到批量大小 {self.batch_size}，开始刷新")  # 调试信息已注释
                    await self._flush_real_time_buffer()
                    
            except Empty:
                # logger.debug("实时数据队列为空，退出处理循环")  # 调试信息已注释
                break
            except Exception as e:
                logger.error(f"处理实时数据队列错误: {e}")
                logger.error(f"错误类型: {type(e).__name__}")
                self.stats['errors'] += 1
        
        # 处理事件队列
        while not self.event_queue.empty():
            try:
                device_id, event_data = self.event_queue.get_nowait()
                # logger.debug(f"从事件队列获取数据 - 设备: {device_id}, 数据: {event_data}")  # 调试信息已注释
                
                # 从event_data中提取事件类型和级别
                event_type = event_data.get("event_type", "UNKNOWN_EVENT")
                event_level = event_data.get("severity", "INFO")
                
                # 使用数据转换器将字典转换为模型对象
                event_record = self.data_converter.convert_to_event_record(
                    event_type,
                    device_id,
                    f"{event_type} - {event_level}"
                )
                
                # logger.debug(f"事件数据转换完成 - 记录类型: {type(event_record).__name__}")  # 调试信息已注释
                
                self.event_buffer.append(event_record)
                # logger.debug(f"事件记录已添加到缓冲区，当前缓冲区大小: {len(self.event_buffer)}")  # 调试信息已注释
                
                if len(self.event_buffer) >= self.batch_size:
                    # logger.debug(f"事件缓冲区达到批量大小 {self.batch_size}，开始刷新")  # 调试信息已注释
                    await self._flush_event_buffer()
                    
            except Empty:
                # logger.debug("事件队列为空，退出处理循环")  # 调试信息已注释
                break
            except Exception as e:
                logger.error(f"处理事件队列错误: {e}")
                logger.error(f"错误类型: {type(e).__name__}")
                self.stats['errors'] += 1
    
    async def _flush_all_buffers(self):
        """刷新所有缓冲区"""
        tasks = []
        
        # 注意：状态缓冲区不再使用，只刷新实时数据和事件缓冲区
        if self.real_time_buffer:
            tasks.append(self._flush_real_time_buffer())
        if self.event_buffer:
            tasks.append(self._flush_event_buffer())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # 注意：状态缓冲区不再使用，状态历史数据应该通过insert_status_immediately直接插入数据库
    
    async def _flush_real_time_buffer(self):
        """刷新实时数据缓冲区"""
        if not self.real_time_buffer:
            # logger.debug("实时数据缓冲区为空，跳过刷新")  # 调试信息已注释
            return
        
        # logger.debug(f"开始刷新实时数据缓冲区，记录数量: {len(self.real_time_buffer)}")  # 调试信息已注释
        
        try:
            with self.lock:
                buffer_to_flush = self.real_time_buffer.copy()
                self.real_time_buffer.clear()
            
            # logger.debug(f"实时数据缓冲区已清空，准备插入 {len(buffer_to_flush)} 条记录")  # 调试信息已注释
            
            success = await self.database_manager.batch_insert_real_time_data(buffer_to_flush)
            
            if success:
                self.stats['real_time_inserted'] += len(buffer_to_flush)
                # logger.info(f"成功插入 {len(buffer_to_flush)} 条实时数据记录")  # 调试信息已注释
            else:
                logger.warning("实时数据记录插入失败，数据将丢弃")
                logger.warning(f"失败记录数量: {len(buffer_to_flush)}")
                # 注意：不能直接将RealTimeData对象放回队列，因为队列期望的是(device_id, real_time_data)格式
                # 而是应该记录错误并丢弃数据
                self.stats['errors'] += len(buffer_to_flush)
                
        except Exception as e:
            logger.error(f"刷新实时数据缓冲区失败: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            self.stats['errors'] += 1
            # 注意：不能直接将RealTimeData对象放回队列，因为队列期望的是(device_id, real_time_data)格式
            # 而是应该记录错误并丢弃数据
            self.stats['errors'] += len(buffer_to_flush)
    
    async def _flush_event_buffer(self):
        """刷新事件缓冲区"""
        if not self.event_buffer:
            # logger.debug("事件缓冲区为空，跳过刷新")  # 调试信息已注释
            return
        
        # logger.debug(f"开始刷新事件缓冲区，记录数量: {len(self.event_buffer)}")  # 调试信息已注释
        
        try:
            with self.lock:
                buffer_to_flush = self.event_buffer.copy()
                self.event_buffer.clear()
            
            # logger.debug(f"事件缓冲区已清空，准备插入 {len(buffer_to_flush)} 条记录")  # 调试信息已注释
            
            success = await self.database_manager.batch_insert_event_records(buffer_to_flush)
            
            if success:
                self.stats['event_inserted'] += len(buffer_to_flush)
                # logger.info(f"成功插入 {len(buffer_to_flush)} 条事件记录")  # 调试信息已注释
            else:
                logger.warning("事件记录插入失败，数据将重新排队")
                logger.warning(f"失败记录数量: {len(buffer_to_flush)}")
                # 注意：不能直接将EventRecords对象放回队列，因为队列期望的是(device_id, event_type, event_data, severity)格式
                # 而是应该记录错误并丢弃数据，或者重新转换为队列格式
                self.stats['errors'] += len(buffer_to_flush)
                
        except Exception as e:
            logger.error(f"刷新事件缓冲区失败: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            self.stats['errors'] += 1
            # 注意：不能直接将EventRecords对象放回队列，因为队列期望的是(device_id, event_type, event_data, severity)格式
            # 而是应该记录错误并丢弃数据
            self.stats['errors'] += len(buffer_to_flush)
    
    # 公共接口方法    
    async def queue_real_time_data(self, device_id: str, real_time_data: Dict[str, Any]) -> bool:
        """队列实时数据"""
        try:
            # logger.debug(f"队列实时数据 - 设备: {device_id}, 数据: {real_time_data}")  # 调试信息已注释
            # 放入队列，格式为 (device_id, real_time_data)
            self.real_time_queue.put((device_id, real_time_data))
            # logger.debug(f"实时数据已加入队列，当前队列大小: {self.real_time_queue.qsize()}")  # 调试信息已注释
            return True
            
        except Exception as e:
            logger.error(f"队列实时数据失败: {e}")
            logger.error(f"失败数据 - 设备: {device_id}, 数据: {real_time_data}")
            return False
    
    async def queue_event_data(self, device_id: str, event_data: Dict[str, Any]) -> bool:
        """队列事件数据"""
        try:
            # logger.debug(f"队列事件数据 - 设备: {device_id}, 数据: {event_data}")  # 调试信息已注释
            # 放入队列，格式为 (device_id, event_data)
            self.event_queue.put((device_id, event_data))
            # logger.debug(f"事件数据已加入队列，当前队列大小: {self.event_queue.qsize()}")  # 调试信息已注释
            
            # 如果队列中只有少量数据，立即触发处理，避免数据延迟
            if self.event_queue.qsize() <= 10:
                await self._process_queues()
                
            return True
            
        except Exception as e:
            logger.error(f"队列事件数据失败: {e}")
            logger.error(f"失败数据 - 设备: {device_id}, 数据: {event_data}")
            return False
    
    # 立即插入方法（用于重要数据）
    async def insert_status_immediately(self, device_id: str, status_data: Dict[str, Any]) -> bool:
        """立即插入状态数据"""
        try:
            # 从状态数据中提取必要参数
            status_type = status_data.get('status_type', 'WorkStatus')
            bit_position = status_data.get('bit_position', 0)
            old_value = status_data.get('old_value', 0)
            new_value = status_data.get('new_value', 0)
            status_name = status_data.get('status_name', '未知状态')
            
            status_record = self.data_converter.convert_to_status_history(
                status_type, bit_position, old_value, new_value, status_name, device_id
            )
            
            # logger.debug(f"状态数据转换完成 - 记录类型: {type(status_record).__name__}")  # 调试信息已注释
            # logger.debug(f"状态记录内容: {status_record}")  # 调试信息已注释
            
            return await self.database_manager.insert_status_history(status_record)
        except Exception as e:
            logger.error(f"立即插入状态数据失败: {e}")
            return False
    
    async def insert_real_time_immediately(self, device_id: str, real_time_data: Dict[str, Any]) -> bool:
        """立即插入实时数据"""
        try:
            # 从实时数据中提取必要参数
            parameter_name = real_time_data.get('parameter_name', 'unknown')
            value = real_time_data.get('value', 0.0)
            unit = real_time_data.get('unit', 'N/A')
            
            real_time_record = self.data_converter.convert_to_real_time_data(
                real_time_data, parameter_name, value, unit, device_id
            )
            return await self.database_manager.insert_real_time_data(real_time_record)
        except Exception as e:
            logger.error(f"立即插入实时数据失败: {e}")
            return False
    
    async def insert_event_immediately(self, device_id: str, event_type: str,
                                     event_data: Dict[str, Any], severity: str = 'INFO') -> bool:
        """立即插入事件数据"""
        try:
            # 从事件数据中提取描述信息
            description = event_data.get('description', f"事件类型: {event_type}")
            if not description:
                description = f"事件类型: {event_type}"
            
            event_record = self.data_converter.convert_to_event_record(
                event_type, device_id, description
            )
            return await self.database_manager.insert_event_record(event_record)
        except Exception as e:
            logger.error(f"立即插入事件数据失败: {e}")
            return False
    
    def get_processor_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            'is_running': self.is_running,
            'queue_sizes': {
                'status_queue': self.status_queue.qsize(),
                'real_time_queue': self.real_time_queue.qsize(),
                'event_queue': self.event_queue.qsize()
            },
            'buffer_sizes': {
                'status_buffer': len(self.status_buffer),
                'real_time_buffer': len(self.real_time_buffer),
                'event_buffer': len(self.event_buffer)
            },
            'stats': self.stats.copy(),
            'batch_size': self.batch_size,
            'flush_interval': self.flush_interval
        }
    
    def update_config(self, batch_size: Optional[int] = None, flush_interval: Optional[float] = None):
        """更新处理器配置"""
        if batch_size is not None:
            self.batch_size = batch_size
        if flush_interval is not None:
            self.flush_interval = flush_interval
        
        # logger.info(f"异步处理器配置已更新: batch_size={self.batch_size}, flush_interval={self.flush_interval}")  # 调试信息已注释
#!/usr/bin/env python3
# flake8: noqa
"""
RPLDevice主服务器
整合WebSocket实时数据推送和Restful API接口
"""

import asyncio
import logging
import signal
import sys
import time
import queue
from pathlib import Path
from typing import Dict, Any
import os
from logging.handlers import RotatingFileHandler

# 在导入任何可能使用pymodbus的模块之前，先配置日志级别
# 先创建临时配置管理器来获取日志级别
from config.config_manager import ConfigManager

temp_config_manager = ConfigManager()
log_config = temp_config_manager.get_section("日志配置")
log_level_str = log_config.get("日志级别", "info").lower()
log_file_path = log_config.get("日志文件路径", "D:/rpldevice/logs")
log_file_name = log_config.get("日志文件名称", "log.log")
log_file_max_size = int(log_config.get("日志文件最大大小", "10"))  # MB

# 转换日志级别字符串为logging常量
log_level_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}
log_level = log_level_map.get(log_level_str, logging.INFO)

# 创建日志目录
os.makedirs(log_file_path, exist_ok=True)
log_file_full_path = os.path.join(log_file_path, log_file_name)

# 配置日志格式
log_formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# 清除现有的处理器
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# 创建文件处理器（使用RotatingFileHandler）
file_handler = RotatingFileHandler(
    log_file_full_path,
    maxBytes=log_file_max_size * 1024 * 1024,  # 转换为字节
    backupCount=5,  # 保留5个备份文件
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# 专门控制pymodbus的日志级别
pymodbus_logger = logging.getLogger('pymodbus')
pymodbus_logger.setLevel(logging.WARNING)
logging.getLogger('pymodbus.logging').setLevel(logging.WARNING)
logging.getLogger('pymodbus.client').setLevel(logging.WARNING)
logging.getLogger('pymodbus.server').setLevel(logging.WARNING)

# 控制HTTP客户端日志级别（减少HTTP请求调试信息）
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx.http2').setLevel(logging.WARNING)
logging.getLogger('httpx.connection').setLevel(logging.WARNING)

# 控制WebSocket服务器日志级别（减少WebSocket消息调试信息）
logging.getLogger('websockets.server').setLevel(logging.WARNING)
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logging.getLogger('websockets.protocol').setLevel(logging.WARNING)

# 控制WebSocket数据推送器日志级别（减少数据缓存调试信息）
logging.getLogger('websocket.data_pusher').setLevel(logging.INFO)

print(f"日志配置完成 - 级别: {log_level_str}, 文件: {log_file_full_path}")
if log_level > logging.INFO:
    print(f"已预先禁用pymodbus和HTTP客户端调试日志输出")

from websocket.websocket_server import WebSocketServer
from websocket.connection_manager import ConnectionManager
from websocket.message_handler import MessageHandler
from serial_comm.serial_manager import SerialManager
from api.api_server import APIServer
from database.database_manager import DatabaseManager
from database.async_processor import AsyncDataProcessor
from database.database_initializer import DatabaseInitializer

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class RPLDeviceServer:
    """RPLDevice主服务器类"""
    
    def __init__(self, config_file: str = "config/config.ini"):
        # 配置管理器
        self.config_manager = ConfigManager(config_file)
        
        # 获取服务器配置
        self.server_config = self.config_manager.get_server_config()
        
        # 初始化各个组件
        self.connection_manager = ConnectionManager()
        self.message_handler = MessageHandler(
            self.connection_manager, self.config_manager
        )
        self.serial_manager = SerialManager(self.config_manager)
        
        # 数据库管理器
        self.database_manager = DatabaseManager(self.config_manager)
        
        # 异步数据处理器
        # 从配置文件获取批量处理大小和刷新间隔
        db_config = self.config_manager.get_database_config()
        batch_size = db_config.get("批量处理大小", 500)
        flush_interval = db_config.get("刷新间隔", 10.0)
        self.async_processor = AsyncDataProcessor(
            self.database_manager,
            batch_size=batch_size,
            flush_interval=flush_interval
        )
        
        # 数据库初始化器
        self.database_initializer = DatabaseInitializer(self.config_manager)
        
        # 获取WebSocket配置
        websocket_config = self.config_manager.get_websocket_config()
        
        # WebSocket服务器
        self.websocket_server = WebSocketServer(
            config_manager=self.config_manager,
            serial_manager=self.serial_manager
        )
        
        # API服务器
        self.api_server = APIServer(
            config_manager=self.config_manager,
            host=self.server_config.get("服务器IP", "0.0.0.0"),
            port=self.server_config.get("端口号", 8000),
            serial_manager=self.serial_manager,
            connection_manager=self.connection_manager
        )
        
        # 服务器运行状态
        self.is_running = False
        self.server_tasks: list[asyncio.Task] = []
        # 状态缓存：{device_id: {status_name: last_value}}
        self._last_status_cache: Dict[str, Dict[str, Any]] = {}
        # 串口连接状态
        self.serial_available = False
        self.hmi_serial_available = False
        self.scada_serial_available = False
        # 串口数据队列（线程安全）
        self.serial_data_queue = queue.Queue()
        # 保存WebSocket配置用于日志
        self.websocket_config = websocket_config

    async def start(self):
        """启动主服务器"""
        if self.is_running:
            logger.warning("服务器已经在运行")
            return
        
        logger.info("正在启动RPLDevice主服务器...")
        
        try:
            # 启动数据库组件
            if not await self.database_initializer.initialize_database():
                logger.error("数据库初始化失败")
                return
            
            # 使用数据库初始化器创建的数据库管理器
            self.database_manager = self.database_initializer.database_manager
            
            # 重新创建异步数据处理器，使用新的数据库管理器实例
            await self.async_processor.stop()  # 先停止旧的处理器
            # 从配置文件获取批量处理大小和刷新间隔
            db_config = self.config_manager.get_database_config()
            batch_size = db_config.get("批量处理大小", 500)
            flush_interval = db_config.get("刷新间隔", 10.0)
            self.async_processor = AsyncDataProcessor(
                self.database_manager,
                batch_size=batch_size,
                flush_interval=flush_interval
            )
            
            # 启动异步数据处理器
            if not await self.async_processor.start():
                logger.error("异步数据处理器启动失败")
                return
            
        # 注册数据推送回调到连接管理器
            self.serial_manager.register_hmi_data_callback(
                self._handle_hmi_serial_data
            )
            self.serial_manager.register_scada_data_callback(
                self._handle_scada_serial_data
            )
            self.serial_manager.register_error_callback(
                self._handle_serial_error
            )
            
            # 初始化串口管理器
            if not await self.serial_manager.initialize():
                logger.warning("串口管理器初始化失败，串口功能不可用")
                self.serial_available = False
                self.hmi_serial_available = False
                self.scada_serial_available = False
                # 发送一次合并后的连接状态
                await self.websocket_server.broadcast_connection_status()
            else:
                # 启动串口轮询
                if not self.serial_manager.start_polling():
                    logger.warning("串口轮询启动失败，串口功能不可用")
                    self.serial_available = False
                    self.hmi_serial_available = False
                    self.scada_serial_available = False
                    # 发送一次合并后的连接状态
                    await self.websocket_server.broadcast_connection_status()
                else:
                    # 检查HMI串口连接状态
                    if self.serial_manager.hmi_master and self.serial_manager.hmi_master.is_open():
                        self.hmi_serial_available = True
                        logger.info("HMI串口已成功连接")
                    else:
                        self.hmi_serial_available = False
                        logger.warning("HMI串口连接失败")
                    
                    # 检查SCADA串口连接状态
                    if self.serial_manager.scada_master and self.serial_manager.scada_master.is_open():
                        self.scada_serial_available = True
                        logger.info("SCADA串口已成功连接")
                    else:
                        self.scada_serial_available = False
                        logger.warning("SCADA串口连接失败")
                    
                    # 整体串口状态（任一串口可用即为可用）
                    self.serial_available = self.hmi_serial_available or self.scada_serial_available
                    
                    logger.info("串口管理器已成功启动")
            # 发送一次合并后的连接状态
            await self.websocket_server.broadcast_connection_status()
            
            # 启动串口数据处理任务
            serial_data_task = asyncio.create_task(self._process_serial_data())
            self.server_tasks.append(serial_data_task)
            
            # 串口状态改为随连接状态合并推送，不再单独定时发送
            
            # 启动WebSocket服务器
            websocket_task = asyncio.create_task(self.websocket_server.start_server())
            self.server_tasks.append(websocket_task)
            
            # 启动API服务器
            api_task = asyncio.create_task(self.api_server.start())
            self.server_tasks.append(api_task)
            
            self.is_running = True
            
            # logger.info(f"WebSocket服务器已启动，监听地址: {self.websocket_config.get('listen_ip', '0.0.0.0')}:{self.websocket_config.get('listen_port', 8765)}")
            # logger.info(f"API服务器已启动，监听地址: {self.server_config.get('服务器IP', '0.0.0.0')}:{self.server_config.get('端口号', 8000)}")
            # logger.info("串口管理器已启动，开始从下位机获取数据")
            # logger.info("数据库管理器已启动，数据将自动保存到数据库")
            
            # 等待所有服务器任务完成
            await asyncio.gather(*self.server_tasks)
            
        except Exception as e:
            logger.error(f"启动主服务器时出错: {e}")
            await self.stop()
    

    
    async def stop(self):
        """停止服务器"""
        if not self.is_running:
            logger.info("服务器未运行，无需停止")
            return
        
        logger.info("正在停止RPLDevice主服务器...")
        self.is_running = False
        
        # 先关闭数据库连接
        if self.database_manager:
            await self.database_manager.close()
        
        # 然后停止异步处理器
        if self.async_processor:
            await self.async_processor.stop()
        
        # 停止串口管理器
        if self.serial_manager:
            self.serial_manager.stop_polling()
        
        # 停止WebSocket服务器
        if self.websocket_server:
            await self.websocket_server.stop_server()
        
        # 停止API服务器
        if self.api_server:
            await self.api_server.stop()
        
        # 取消所有服务器任务
        for task in self.server_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.server_tasks.clear()
        
        logger.info("RPLDevice主服务器已停止")
    
    def _handle_hmi_serial_data(self, data_type, ws_data):
        """处理HMI串口数据回调"""
        try:
            # 直接使用已经转换好的数据，无需再次转换
            message = {
                "timestamp": time.time(),
                "source": "hmi",
                "type": data_type,
                "data": ws_data
            }
            
            # 将数据放入队列，由主线程处理
            if hasattr(self, 'serial_data_queue') and self.is_running:
                self.serial_data_queue.put({
                    "type": "hmi",
                    "message": message,
                    "device_data": None  # 不再需要原始设备数据
                })
            
            # 同时调用数据推送器的回调函数，更新数据推送器的缓存
            if hasattr(self.websocket_server, 'data_pusher') and self.websocket_server.data_pusher:
                try:
                    self.websocket_server.data_pusher._on_serial_data_received(data_type, ws_data)
                except Exception as e:
                    logger.warning(f"调用数据推送器回调失败: {e}")
                
        except Exception as e:
            logger.error(f"处理HMI串口数据出错: {e}")

    def _handle_scada_serial_data(self, data_type, scada_data):
        """处理SCADA串口数据回调"""
        try:
            # 直接使用已经转换好的数据，无需再次转换
            message = {
                "timestamp": time.time(),
                "source": "scada",
                "type": data_type,  # 使用标准字段名type而不是data_type
                "data": scada_data
            }
            
            # 将数据放入队列，由主线程处理
            if hasattr(self, 'serial_data_queue') and self.is_running:
                self.serial_data_queue.put({
                    "type": "scada",
                    "message": message,
                    "device_data": None  # 不再需要原始设备数据
                })
                
        except Exception as e:
            logger.error(f"处理SCADA串口数据出错: {e}")

    # 注意：_handle_serial_data方法已移除，使用专门的HMI/SCADA处理方法
    
    async def _process_serial_data(self):
        """处理串口数据队列"""
        while self.is_running:
            try:
                # 从队列中获取数据，设置超时时间避免阻塞
                try:
                    data_item = self.serial_data_queue.get(timeout=0.1)
                except queue.Empty:
                    # 队列为空，继续循环
                    await asyncio.sleep(0.1)
                    continue
                
                if data_item["type"] == "hmi":
                    await self._async_handle_hmi_data(data_item["message"], None)
                elif data_item["type"] == "scada":
                    await self._async_handle_scada_data(data_item["message"], None)
                
                # 标记任务完成
                self.serial_data_queue.task_done()
                
            except Exception as e:
                logger.error(f"处理串口数据队列出错: {e}")
                await asyncio.sleep(0.1)
    
    async def _async_handle_hmi_data(self, message, device_data):
        """异步处理HMI数据"""
        try:
            # 广播到所有WebSocket连接
            await self.websocket_server.connection_manager.broadcast_to_all(message)
            
            # 异步保存数据到数据库
            await self._save_data_to_database(message)
        except Exception as e:
            logger.error(f"异步处理HMI数据出错: {e}")
    
    async def _async_handle_scada_data(self, message, device_data):
        """异步处理SCADA数据"""
        try:
            # 广播到所有WebSocket连接
            await self.websocket_server.connection_manager.broadcast_to_all(message)
            
            # 异步保存数据到数据库
            await self._save_data_to_database(message)
        except Exception as e:
            logger.error(f"异步处理SCADA数据出错: {e}")
    
    async def _save_data_to_database(self, message: Dict[str, Any]):
        """异步保存数据到数据库"""
        try:
            # 从配置文件中获取设备ID
            device_id = self.config_manager.get_section('设备配置').get('设备ID', 'rpl_device_001')
            
            # 保存状态历史数据
            await self._save_status_history_data(device_id, message)
            
            # 保存实时数据
            await self._save_real_time_data(device_id, message)
            
        except Exception as e:
            logger.error(f"保存数据到数据库出错: {e}")
            # 记录错误事件
            await self.async_processor.queue_event_data(
                "system", 
                {"event_type": "DATABASE_ERROR", "data": {"error": str(e), "operation": "save_data"}, "severity": "ERROR"}
            )
    
    async def _save_status_history_data(self, device_id: str, message: Dict[str, Any]):
        try:
            # 从消息的data字段获取实际数据
            data_content = message.get("data", {})
            data_type = message.get("type", "")  # 使用type字段而不是data_type
            
            # 获取设备缓存
            cache = self._last_status_cache.setdefault(device_id, {})
            
            # 根据数据类型处理不同的状态数据
            if data_type == "system_status":
                # 处理系统状态数据 - 根据配置文件中定义的5个寄存器结构
                system_status = data_content if isinstance(data_content, dict) else {}
                
                # 处理系统状态 (寄存器0x0000)
                if "system_status" in system_status:
                    status_data = system_status["system_status"]
                    if isinstance(status_data, dict):
                        await self._process_status_bits(device_id, cache, status_data, "SystemStatus", 0x0000)
                
                # 处理IGBT光纤状态 (寄存器0x0001)
                if "igbt_fiber_status" in system_status:
                    status_data = system_status["igbt_fiber_status"]
                    if isinstance(status_data, dict):
                        await self._process_status_bits(device_id, cache, status_data, "IGBTStatus", 0x0001)
                
                # 处理开关量输入状态 (寄存器0x0002)
                if "switch_input" in system_status:
                    status_data = system_status["switch_input"]
                    if isinstance(status_data, dict):
                        await self._process_status_bits(device_id, cache, status_data, "InputStatus", 0x0002)
                
                # 处理开关量输出状态 (寄存器0x0003)
                if "switch_output" in system_status:
                    status_data = system_status["switch_output"]
                    if isinstance(status_data, dict):
                        await self._process_status_bits(device_id, cache, status_data, "OutputStatus", 0x0003)
                
                # 处理故障状态 (寄存器0x0004)
                if "fault_status" in system_status:
                    status_data = system_status["fault_status"]
                    if isinstance(status_data, dict):
                        await self._process_status_bits(device_id, cache, status_data, "FaultStatus", 0x0004)
        except Exception as e:
            logger.error(f"保存状态历史数据出错: {e}")
            await self.async_processor.queue_event_data(
                "system", 
                {"event_type": "STATUS_SAVE_ERROR", "data": {"error": str(e), "device_id": device_id}, "severity": "ERROR"}
            )
    
    async def _save_real_time_data(
        self, device_id: str, message: Dict[str, Any]
    ):
        """保存实时数据"""
        try:
            # 从消息的data字段获取实际数据
            data_content = message.get("data", {})
            data_type = message.get("type", "")  # 使用type字段而不是data_type
            
            # 获取设备实时数据缓存
            cache = self._last_status_cache.setdefault(device_id, {})
            
            # 根据数据类型处理不同的数据
            if data_type == "analog_data":
                # 处理模拟量数据 - 实时数据应该直接插入，不考虑值是否变化
                analog_data = data_content if isinstance(data_content, list) else []
                for analog_item in analog_data:
                    parameter_name = analog_item.get("name", "unknown")
                    physical_value = analog_item.get("physical_value", 0.0)
                    unit = analog_item.get("unit", "N/A")
                    
                    # 实时数据直接插入数据库
                    real_time_data = {
                        "parameter_name": parameter_name,
                        "value": float(physical_value),
                        "unit": unit
                    }
                    await self.async_processor.queue_real_time_data(
                        device_id, real_time_data
                    )                
        except Exception as e:
            logger.error(f"保存实时数据出错: {e}")
    
    def _parse_bit_position(self, bit_name: str) -> int:
        """解析位位置"""
        try:
            # 位名称格式如 "bit0", "bit15" 等
            if bit_name.startswith("bit") and len(bit_name) > 3:
                return int(bit_name[3:])
            return 0
        except (ValueError, IndexError):
            return 0
    
    async def _process_status_bits(self, device_id: str, cache: dict, status_data: dict, status_type: str, register_address: int):
        """处理状态位数据 - 确保old_value和new_value为单个位的整数值"""
        for bit_name, bit_value in status_data.items():
            bit_position = self._parse_bit_position(bit_name)
            status_name = f"{status_type}_bit{bit_position}"
            
            # 确保bit_value是整数（0或1）
            current_value = int(bit_value) if bit_value is not None else 0
            old_value = cache.get(status_name, 0)
            
            # 只有当值发生变化时才保存历史记录
            if old_value != current_value:
                status_data_record = {
                    "status_type": status_type,
                    "bit_position": bit_position,
                    "old_value": old_value,      # 单个位的整数值（0或1）
                    "new_value": current_value,  # 单个位的整数值（0或1）
                    "status_name": status_name,
                    "register_address": register_address
                }
                # 状态数据直接插入数据库，不进入缓冲区
                await self.async_processor.insert_status_immediately(
                    device_id, status_data_record
                )
                cache[status_name] = current_value


    
    def _handle_serial_error(self, error: Exception):
        """处理串口错误回调"""
        logger.error(f"串口通信错误: {error}")
        
        # 推送错误消息到前端
        error_message = {
            "type": "error",
            "timestamp": time.time(),
            "data": {
                "error_type": "serial_communication",
                "error_message": str(error),
                "recovery_action": "尝试重新连接串口"
            }
        }
        
        # 异步推送错误消息
        asyncio.create_task(self.websocket_server.connection_manager.broadcast_to_all(error_message))
        
        # 异步记录错误到数据库
        asyncio.create_task(self._save_error_to_database(error))
    
    async def _save_error_to_database(self, error: Exception):
        """异步保存错误信息到数据库"""
        try:
            await self.async_processor.queue_event_data(
                "system",
                {
                    "event_type": "SERIAL_COMMUNICATION_ERROR",
                    "data": {
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "recovery_action": "尝试重新连接串口"
                    },
                    "severity": "ERROR"
                }
            )
        except Exception as e:
            logger.error(f"保存错误信息到数据库出错: {e}")
    
    def get_server_status(self) -> dict:
        """获取服务器状态信息"""
        return {
            "is_running": self.is_running,
            "server_config": self.server_config,
            "connection_stats": self.websocket_server.connection_manager.get_connection_stats(),
            "serial_status": {
                "is_polling": self.serial_manager.is_running if hasattr(self.serial_manager, 'is_running') else False,
                "current_data": self.serial_manager.get_current_data() is not None
            },
            "database_status": self.database_manager.get_database_status() if self.database_manager else {},
            "async_processor_status": self.async_processor.get_processor_status() if self.async_processor else {}
        }


async def main():
    """主函数"""
    # 配置管理器已经在文件顶部创建，这里直接使用
    config_manager = ConfigManager()
    
    # 从配置文件获取日志级别（用于确认）
    log_config = config_manager.get_section("日志配置")
    log_level_str = log_config.get("日志级别", "info").lower()
    
    # 转换日志级别字符串为logging常量
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }
    log_level = log_level_map.get(log_level_str, logging.INFO)
    
    # 再次确认pymodbus日志级别设置
    if log_level >= logging.INFO:
        logging.getLogger('pymodbus').setLevel(logging.WARNING)
        logging.getLogger('pymodbus.logging').setLevel(logging.WARNING)
        logging.getLogger('pymodbus.client').setLevel(logging.WARNING)
        logging.getLogger('pymodbus.server').setLevel(logging.WARNING)
        
        # 控制HTTP客户端日志级别（减少HTTP请求调试信息）
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('httpx.http2').setLevel(logging.WARNING)
        logging.getLogger('httpx.connection').setLevel(logging.WARNING)
        
        # 控制Uvicorn访问日志（减少HTTP请求日志）
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
    
    logger.info(f"日志级别已设置为: {log_level_str} ({log_level})")
    
    # 创建服务器实例
    server = RPLDeviceServer()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在优雅关闭服务器...")
        asyncio.create_task(server.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动服务器
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
    finally:
        # 确保服务器被正确关闭
        if server.is_running:
            await server.stop()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())

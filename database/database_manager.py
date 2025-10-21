# flake8: noqa
"""
数据库管理器
负责数据库连接、会话管理和基本CRUD操作
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json

from .models import Base, StatusHistory, RealTimeData, EventRecords, UserPermissions

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.engine = None
        self.SessionLocal = None
        self.is_connected = False
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        
    async def initialize(self) -> bool:
        """初始化数据库连接"""
        try:
            # 从配置获取数据库连接信息
            db_config = self.config_manager.get_database_config()
            
            if not db_config:
                logger.error("数据库配置未找到")
                return False
            
            # 构建数据库连接URL
            db_url = self._build_database_url(db_config)
            
            # 创建数据库引擎
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False  # 生产环境设为False
            )
            
            # 创建会话工厂
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # 测试连接
            await self._test_connection()
            
            self.is_connected = True
            # logger.info("数据库连接初始化成功")  # 调试信息已注释
            return True
            
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            return False
    
    def _build_database_url(self, db_config: Dict[str, Any]) -> str:
        """构建数据库连接URL"""
        host = db_config.get('数据库地址', db_config.get('host', 'localhost'))
        port = db_config.get('数据库端口', db_config.get('port', 3306))
        database = db_config.get('数据库名称', db_config.get('database', 'rpl_device'))
        username = db_config.get('数据库用户名', db_config.get('username', 'root'))
        password = db_config.get('数据库密码', db_config.get('password', ''))
        
        # 如果数据库为None，表示不指定数据库（用于创建数据库前的连接）
        if database is None:
            if not password:
                return f"mysql+pymysql://{username}@{host}:{port}/?charset=utf8mb4"
            else:
                return f"mysql+pymysql://{username}:{password}@{host}:{port}/?charset=utf8mb4"
        
        # 如果密码为空，使用无密码连接
        if not password:
            return f"mysql+pymysql://{username}@{host}:{port}/{database}?charset=utf8mb4"
        else:
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    
    async def _test_connection(self):
        """测试数据库连接"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.thread_pool, self._sync_test_connection)
    
    def _sync_test_connection(self):
        """同步测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # logger.debug("数据库连接测试成功")  # 调试信息已注释
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            raise
    
    def get_session(self):
        """获取数据库会话（同步版本）"""
        if not self.is_connected:
            raise RuntimeError("数据库未连接")
        
        return self.SessionLocal()
    
    async def create_tables(self) -> bool:
        """创建数据库表"""
        if not self.is_connected:
            logger.error("数据库未连接，无法创建表")
            return False
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.thread_pool, self._sync_create_tables)
            # logger.info("数据库表创建成功")  # 调试信息已注释
            return True
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            return False
    
    def _sync_create_tables(self):
        """同步创建数据库表"""
        try:
            Base.metadata.create_all(bind=self.engine)
        except Exception as e:
            logger.error(f"同步创建表失败: {e}")
            raise
    
    # 状态历史记录操作
    async def insert_status_history(self, status_data: StatusHistory) -> bool:
        """插入状态历史记录"""
        return await self._insert_record(status_data)
    
    async def get_status_history(self, device_id: str, limit: int = 100, 
                                start_time: Optional[str] = None, 
                                end_time: Optional[str] = None) -> List[StatusHistory]:
        """查询状态历史记录"""
        return await self._query_records(
            StatusHistory, 
            device_id=device_id, 
            limit=limit, 
            start_time=start_time, 
            end_time=end_time
        )
    
    # 实时数据操作
    async def insert_real_time_data(self, real_time_data: RealTimeData) -> bool:
        """插入实时数据记录"""
        return await self._insert_record(real_time_data)
    
    async def get_real_time_data(self, device_id: str, limit: int = 100,
                                start_time: Optional[str] = None,
                                end_time: Optional[str] = None) -> List[RealTimeData]:
        """查询实时数据记录"""
        return await self._query_records(
            RealTimeData,
            device_id=device_id,
            limit=limit,
            start_time=start_time,
            end_time=end_time
        )
    
    # 事件记录操作
    async def insert_event_record(self, event_record: EventRecords) -> bool:
        """插入事件记录"""
        return await self._insert_record(event_record)
    
    async def get_event_records(self, device_id: str, limit: int = 100,
                              start_time: Optional[str] = None,
                              end_time: Optional[str] = None) -> List[EventRecords]:
        """查询事件记录"""
        return await self._query_records(
            EventRecords,
            device_id=device_id,
            limit=limit,
            start_time=start_time,
            end_time=end_time
        )
    
    # 通用CRUD操作
    async def _insert_record(self, record) -> bool:
        """通用插入记录方法"""
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.thread_pool, self._sync_insert_record, record)
            return True
        except Exception as e:
            logger.error(f"插入记录失败: {e}")
            
            # 检查是否是连接问题，如果是则尝试重新连接
            error_str = str(e).lower()
            if ("connection" in error_str or 
                "lost connection" in error_str or 
                "mysql server has gone away" in error_str or
                "operationalerror" in error_str or
                "interfaceerror" in error_str or
                "disconnected" in error_str or
                "数据库未连接" in str(e)):
                logger.warning("检测到数据库连接问题，尝试重新连接")
                self.is_connected = False
                if await self._reconnect():
                    # logger.info("数据库重新连接成功，重试插入记录")  # 调试信息已注释
                    # 重新连接成功后，更新连接状态
                    self.is_connected = True
                    return await self._insert_record(record)
            
            return False
    
    def _sync_insert_record(self, record):
        """同步插入记录"""
        session = self.get_session()
        try:
            # 调试日志：检查记录的类型和内容
            # logger.debug(f"_sync_insert_record接收到的记录类型: {type(record).__name__}")  # 调试信息已注释
            # logger.debug(f"_sync_insert_record记录内容: {record}")  # 调试信息已注释
            
            # 添加更详细的类型检查
            if hasattr(record, '__dict__'):
                # logger.debug(f"记录属性: {record.__dict__}")  # 调试信息已注释
                # 检查每个属性的类型
                for attr_name, attr_value in record.__dict__.items():
                    if attr_value is not None:
                        # logger.debug(f"属性 {attr_name}: 类型={type(attr_value).__name__}, 值={attr_value}")  # 调试信息已注释
                        # 检查是否有属性是字典类型
                        if isinstance(attr_value, dict):
                            logger.error(f"发现属性 {attr_name} 是字典类型，这可能导致SQLAlchemy错误")
            else:
                # logger.debug("记录没有 __dict__ 属性")  # 调试信息已注释
                pass
            
            session.add(record)
            session.commit()
            # logger.debug("记录插入成功")  # 调试信息已注释
        except Exception as e:
            logger.error(f"_sync_insert_record插入失败: {e}")
            logger.error(f"失败记录类型: {type(record).__name__}")
            logger.error(f"失败记录内容: {record}")
            if hasattr(record, '__dict__'):
                logger.error(f"失败记录属性: {record.__dict__}")
            session.rollback()
            raise
        finally:
            session.close()
    
    async def _query_records(self, model_class, device_id: str, limit: int,
                           start_time: Optional[str] = None,
                           end_time: Optional[str] = None) -> List:
        """通用查询记录方法"""
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.thread_pool, 
                self._sync_query_records, 
                model_class, device_id, limit, start_time, end_time
            )
            return result
        except Exception as e:
            logger.error(f"查询记录失败: {e}")
            
            # 检查是否是连接问题，如果是则尝试重新连接
            error_str = str(e).lower()
            if ("connection" in error_str or 
                "lost connection" in error_str or 
                "mysql server has gone away" in error_str or
                "operationalerror" in error_str or
                "interfaceerror" in error_str or
                "disconnected" in error_str):
                logger.warning("检测到数据库连接问题，尝试重新连接")
                self.is_connected = False
                if await self._reconnect():
                    # logger.info("数据库重新连接成功，重试查询记录")  # 调试信息已注释
                    # 重新连接成功后，更新连接状态
                    self.is_connected = True
                    return await self._query_records(model_class, device_id, limit, start_time, end_time)
            
            return []
    
    def _sync_query_records(self, model_class, device_id: str, limit: int,
                          start_time: Optional[str], end_time: Optional[str]) -> List:
        """同步查询记录"""
        session = self.get_session()
        try:
            query = session.query(model_class).filter(
                model_class.device_id == device_id
            )
            
            if start_time:
                query = query.filter(model_class.timestamp >= start_time)
            if end_time:
                query = query.filter(model_class.timestamp <= end_time)
            
            return query.order_by(model_class.timestamp.desc()).limit(limit).all()
        finally:
            session.close()
    
    # 批量操作
    async def batch_insert_status_history(self, status_records: List[StatusHistory]) -> bool:
        """批量插入状态历史记录"""
        try:
            return await self._batch_insert_records(status_records)
        except Exception as e:
            logger.error(f"批量插入状态历史记录出错: {e}")
            return False
    
    async def batch_insert_real_time_data(self, real_time_records: List[RealTimeData]) -> bool:
        """批量插入实时数据"""
        try:
            return await self._batch_insert_records(real_time_records)
        except Exception as e:
            logger.error(f"批量插入实时数据出错: {e}")
            return False
    
    async def batch_insert_event_records(self, event_records: List[EventRecords]) -> bool:
        """批量插入事件记录"""
        try:
            return await self._batch_insert_records(event_records)
        except Exception as e:
            logger.error(f"批量插入事件记录出错: {e}")
            return False
    
    async def _check_connection_health(self) -> bool:
        """检查数据库连接健康状态"""
        if not self.is_connected:
            logger.warning("数据库连接状态为未连接，尝试重新连接")
            return await self._reconnect()
        
        try:
            # 测试连接是否仍然有效
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.thread_pool, self._sync_test_connection)
            return True
        except Exception as e:
            logger.warning(f"数据库连接健康检查失败: {e}")
            logger.warning("尝试重新连接数据库")
            return await self._reconnect()
    
    async def _reconnect(self) -> bool:
        """重新连接数据库"""
        try:
            # logger.info("开始重新连接数据库...")  # 调试信息已注释
            
            # 先关闭现有连接
            if self.engine:
                self.engine.dispose()
            
            # 重新初始化连接
            success = await self.initialize()
            
            if success:
                # logger.info("数据库重新连接成功")  # 调试信息已注释
                # 重新连接成功后，更新连接状态
                self.is_connected = True
                return True
            else:
                logger.error("数据库重新连接失败")
                self.is_connected = False
                return False
                
        except Exception as e:
            logger.error(f"数据库重新连接异常: {e}")
            self.is_connected = False
            return False

    async def _batch_insert_records(self, records: List) -> bool:
        """通用批量插入记录方法"""
        if not records:
            # logger.debug("批量插入记录为空，跳过插入")  # 调试信息已注释
            return True
        
        # logger.debug(f"开始批量插入 {len(records)} 条记录")  # 调试信息已注释
        
        try:
            # 调试信息：显示第一条记录的内容
            if records:
                first_record = records[0]
                # logger.debug(f"第一条记录类型: {type(first_record).__name__}")  # 调试信息已注释
                # logger.debug(f"第一条记录内容: {first_record}")  # 调试信息已注释
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.thread_pool, self._sync_batch_insert_records, records)
            # logger.info(f"批量插入 {len(records)} 条记录成功")  # 调试信息已注释
            return True
        except Exception as e:
            logger.error(f"批量插入记录失败: {e}")
            logger.error(f"失败记录数量: {len(records)}")
            if records:
                logger.error(f"第一条失败记录类型: {type(records[0]).__name__}")
                logger.error(f"第一条失败记录内容: {records[0]}")
            
            # 检查是否是连接问题，如果是则尝试重新连接
            error_str = str(e).lower()
            if ("connection" in error_str or 
                "lost connection" in error_str or 
                "mysql server has gone away" in error_str or
                "operationalerror" in error_str or
                "interfaceerror" in error_str or
                "disconnected" in error_str or
                "数据库未连接" in str(e)):
                logger.warning("检测到数据库连接问题，尝试重新连接")
                self.is_connected = False
                if await self._reconnect():
                    # logger.info("数据库重新连接成功，重试批量插入")  # 调试信息已注释
                    # 重新连接成功后，更新连接状态
                    self.is_connected = True
                    return await self._batch_insert_records(records)
            
            return False
    
    def _sync_batch_insert_records(self, records: List):
        """同步批量插入记录"""
        # logger.debug(f"同步批量插入开始，记录数量: {len(records)}")  # 调试信息已注释
        session = self.get_session()
        try:
            # logger.debug("数据库会话创建成功")  # 调试信息已注释
            session.add_all(records)
            # logger.debug("记录已添加到会话")  # 调试信息已注释
            session.commit()
            # logger.debug("事务提交成功")  # 调试信息已注释
            # logger.info(f"同步批量插入 {len(records)} 条记录成功")  # 调试信息已注释
        except Exception as e:
            logger.error(f"同步批量插入失败: {e}")
            logger.error(f"失败记录数量: {len(records)}")
            if records:
                logger.error(f"第一条失败记录类型: {type(records[0]).__name__}")
                logger.error(f"第一条失败记录内容: {records[0]}")
            session.rollback()
            raise
        finally:
            session.close()
    
    async def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self.is_connected = False
            # logger.info("数据库连接已关闭")  # 调试信息已注释
        
        # 不要关闭线程池，以便可以重新初始化
        # if self.thread_pool:
        #     self.thread_pool.shutdown(wait=True)
        #     logger.info("线程池已关闭")
    
    def get_database_status(self) -> Dict[str, Any]:
        """获取数据库状态信息"""
        return {
            "is_connected": self.is_connected,
            "engine_info": str(self.engine) if self.engine else None,
            "thread_pool_active": self.thread_pool._max_workers if self.thread_pool else 0
        }

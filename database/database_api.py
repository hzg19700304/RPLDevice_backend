# flake8: noqa
"""
数据库API接口
提供数据库查询和操作的API接口
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.sql import func
import bcrypt
from .database_manager import DatabaseManager
from .models import StatusHistory, RealTimeData, EventRecords, UserPermissions

logger = logging.getLogger(__name__)


class DatabaseAPI:
    """数据库API接口类"""
    
    def __init__(self, database_manager: DatabaseManager):
        """
        初始化数据库API
        
        Args:
            database_manager: 数据库管理器实例
        """
        self.database_manager = database_manager
    
    async def get_status_history(
        self, 
        device_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取状态历史数据
        
        Args:
            device_id: 设备ID，如果为None则获取所有设备
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回记录数
            offset: 偏移量
            
        Returns:
            List[Dict]: 状态历史数据列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_status_history,
                device_id, start_time, end_time, limit, offset
            )
            
            return [self._status_history_to_dict(record) for record in records]
                
        except Exception as e:
            logger.error(f"获取状态历史数据失败: {e}")
            return []
    
    def _sync_get_status_history(self, device_id, start_time, end_time, limit, offset):
        """同步获取状态历史数据"""
        session = self.database_manager.get_session()
        try:
            query = select(StatusHistory)
            
            # 添加过滤条件
            if device_id:
                query = query.where(StatusHistory.device_id == device_id)
            
            if start_time:
                query = query.where(StatusHistory.timestamp >= start_time)
            
            if end_time:
                query = query.where(StatusHistory.timestamp <= end_time)
            
            # 按时间倒序排列
            query = query.order_by(asc(StatusHistory.timestamp))
            
            # 添加分页
            query = query.limit(limit).offset(offset)
            
            logger.info(f"执行查询: {query}")
            
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def get_real_time_data(
        self,
        device_id: Optional[str] = None,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取实时数据
        
        Args:
            device_id: 设备ID
            parameter_name: 参数名称
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            List[Dict[str, Any]]: 实时数据列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_real_time_data,
                device_id, parameter_name, start_time, end_time, limit, offset
            )
            
            return [self._real_time_data_to_dict(record) for record in records]
                
        except Exception as e:
            logger.error(f"获取实时数据失败: {e}")
            return []
    
    async def get_real_time_data_unlimited(
        self,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取实时数据（无数量限制）
        
        Args:
            parameter_name: 参数名称
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[Dict[str, Any]]: 实时数据列表（无数量限制）
        """
        try:
            # logger.info(f"=== 异步无限制查询开始 ===")
            # logger.info(f"查询参数 - parameter_name: {parameter_name}")
            # logger.info(f"时间范围 - start_time: {start_time}, end_time: {end_time}")
            
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_real_time_data_unlimited,
                parameter_name, start_time, end_time
            )
            
            # logger.info(f"异步查询结果数量: {len(records)}")
            # if records:
                # logger.info(f"异步查询第一条记录时间: {records[0].timestamp}, 最后一条记录时间: {records[-1].timestamp}")
            # logger.info(f"=== 异步无限制查询结束 ===")
            
            return [self._real_time_data_to_dict(record) for record in records]
                
        except Exception as e:
            logger.error(f"获取无限制实时数据失败: {e}")
            return []
    
    def _sync_get_real_time_data_unlimited(self, parameter_name, start_time, end_time):
        """同步获取实时数据（无数量限制）"""
        session = self.database_manager.get_session()
        try:
            query = select(RealTimeData)
            
            # 添加过滤条件
            # if device_id:
            #     query = query.where(RealTimeData.device_id == device_id)
            
            if parameter_name:
                query = query.where(RealTimeData.parameter_name == parameter_name)
            
            if start_time:
                query = query.where(RealTimeData.timestamp >= start_time)
            
            if end_time:
                query = query.where(RealTimeData.timestamp <= end_time)
            
            # 按时间倒序排列，不限制数量
            query = query.order_by(asc(RealTimeData.timestamp)) 
            
            # 调试信息：打印查询语句和参数
            # print(f"=== 无限制查询SQL开始 ===")
            # print(f"查询对象: {query}")
            # print(f"查询参数 - parameter_name: {parameter_name}")
            # print(f"时间范围 - start_time: {start_time}, end_time: {end_time}")
            
            result = session.execute(query)
            records = result.scalars().all()
            
            # 调试信息：打印查询结果数量
            # print(f"查询结果数量: {len(records)}")
            # if records:
            #     print(f"第一条记录时间: {records[0].timestamp}, 最后一条记录时间: {records[-1].timestamp}")
            # print(f"=== 无限制查询SQL结束 ===") 
            
            return records
        finally:
            session.close()
    
    def _sync_get_real_time_data(self, device_id, parameter_name, start_time, end_time, limit, offset):
        """同步获取实时数据"""
        session = self.database_manager.get_session()
        try:
            query = select(RealTimeData)
            
            # 添加过滤条件
            if device_id:
                query = query.where(RealTimeData.device_id == device_id)
            
            if parameter_name:
                query = query.where(RealTimeData.parameter_name == parameter_name)
            
            if start_time:
                query = query.where(RealTimeData.timestamp >= start_time)
            
            if end_time:
                query = query.where(RealTimeData.timestamp <= end_time)
            
            # 按时间倒序排列
            query = query.order_by(asc(RealTimeData.timestamp))
            
            # 添加分页
            query = query.limit(limit).offset(offset)
            
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def get_event_records(
        self,
        device_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取事件记录
        
        Args:
            device_id: 设备ID
            event_type: 事件类型
            severity: 严重程度
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            List[Dict[str, Any]]: 事件记录列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_event_records,
                device_id, event_type, start_time, end_time, limit, offset
            )
            
            return [self._event_record_to_dict(record) for record in records]
                
        except Exception as e:
            logger.error(f"获取事件记录失败: {e}")
            return []
    
    async def get_event_records_unlimited(
        self,
        device_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取事件记录（无数量限制）
        
        Args:
            device_id: 设备ID
            event_type: 事件类型
            severity: 严重程度
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[Dict[str, Any]]: 事件记录列表（无数量限制）
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_event_records_unlimited,
                device_id, event_type, start_time, end_time
            )
            
            return [self._event_record_to_dict(record) for record in records]
                
        except Exception as e:
            logger.error(f"获取无限制事件记录失败: {e}")
            return []
    
    def _sync_get_event_records_unlimited(self, device_id, event_type, start_time, end_time):
        """同步获取事件记录（无数量限制）"""
        session = self.database_manager.get_session()
        try:
            query = select(EventRecords)
            
            # 添加过滤条件
            if device_id:
                query = query.where(EventRecords.device_id == device_id)
            
            if event_type:
                query = query.where(EventRecords.event_type == event_type)
            
            if start_time:
                query = query.where(EventRecords.event_time >= start_time)
            
            if end_time:
                query = query.where(EventRecords.event_time <= end_time)
            
            # 按时间倒序排列，不限制数量
            query = query.order_by(desc(EventRecords.event_time))
            
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    def _sync_get_event_records(self, device_id, event_type, start_time, end_time, limit, offset):
        """同步获取事件记录"""
        session = self.database_manager.get_session()
        try:
            query = select(EventRecords)
            
            # 添加过滤条件
            if device_id:
                query = query.where(EventRecords.device_id == device_id)
            
            if event_type:
                query = query.where(EventRecords.event_type == event_type)
            
            if start_time:
                query = query.where(EventRecords.event_time >= start_time)
            
            if end_time:
                query = query.where(EventRecords.event_time <= end_time)
            
            # 按时间倒序排列
            query = query.order_by(desc(EventRecords.event_time))
            
            # 添加分页
            query = query.limit(limit).offset(offset)
            
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def get_statistics(
        self,
        device_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            device_id: 设备ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            Dict: 统计信息
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_statistics,
                device_id, start_time, end_time
            )
            
            return stats
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def _sync_get_statistics(self, device_id, start_time, end_time):
        """同步获取统计信息"""
        session = self.database_manager.get_session()
        try:
            stats = {}
            
            # 状态历史统计
            query = select(
                func.count(StatusHistory.id),
                func.min(StatusHistory.timestamp),
                func.max(StatusHistory.timestamp)
            )
            
            if device_id:
                query = query.where(StatusHistory.device_id == device_id)
            
            if start_time:
                query = query.where(StatusHistory.timestamp >= start_time)
            
            if end_time:
                query = query.where(StatusHistory.timestamp <= end_time)
            
            result = session.execute(query)
            count, min_time, max_time = result.one()
            
            stats['status_history'] = {
                'count': count,
                'time_range': {
                    'min': min_time.isoformat() if min_time else None,
                    'max': max_time.isoformat() if max_time else None
                }
            }
            
            # 实时数据统计
            query = select(
                func.count(RealTimeData.id),
                func.min(RealTimeData.timestamp),
                func.max(RealTimeData.timestamp)
            )
            
            if device_id:
                query = query.where(RealTimeData.device_id == device_id)
            
            if start_time:
                query = query.where(RealTimeData.timestamp >= start_time)
            
            if end_time:
                query = query.where(RealTimeData.timestamp <= end_time)
            
            result = session.execute(query)
            count, min_time, max_time = result.one()
            
            stats['real_time_data'] = {
                'count': count,
                'time_range': {
                    'min': min_time.isoformat() if min_time else None,
                    'max': max_time.isoformat() if max_time else None
                }
            }
            
            # 事件记录统计
            query = select(
                func.count(EventRecords.id),
                func.min(EventRecords.event_time),
                func.max(EventRecords.event_time)
            )
            
            if start_time:
                query = query.where(EventRecords.event_time >= start_time)
            
            if end_time:
                query = query.where(EventRecords.event_time <= end_time)
            
            result = session.execute(query)
            count, min_time, max_time = result.one()
            
            stats['event_records'] = {
                'count': count,
                'time_range': {
                    'min': min_time.isoformat() if min_time else None,
                    'max': max_time.isoformat() if max_time else None
                }
            }
            
            return stats
        finally:
            session.close()
    
    async def get_device_list(self) -> List[str]:
        """
        获取设备列表
        
        Returns:
            List[str]: 设备ID列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            devices = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_device_list
            )
            
            return list(devices)
                
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []
    
    def _sync_get_device_list(self):
        """同步获取设备列表"""
        session = self.database_manager.get_session()
        try:
            query = select(StatusHistory.device_id).distinct()
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def get_parameter_names(self) -> List[str]:
        """
        获取参数名称列表
        
        Returns:
            List[str]: 参数名称列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            parameter_names = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_parameter_names
            )
            
            return list(parameter_names)
                
        except Exception as e:
            logger.error(f"获取参数名称列表失败: {e}")
            return []
    
    def _sync_get_parameter_names(self):
        """同步获取参数名称列表"""
        session = self.database_manager.get_session()
        try:
            query = select(RealTimeData.parameter_name).distinct()
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def get_event_types(self) -> List[str]:
        """
        获取事件类型列表
        
        Returns:
            List[str]: 事件类型列表
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            event_types = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_event_types
            )
            
            return list(event_types)
                
        except Exception as e:
            logger.error(f"获取事件类型列表失败: {e}")
            return []
    
    def _sync_get_event_types(self):
        """同步获取事件类型列表"""
        session = self.database_manager.get_session()
        try:
            query = select(EventRecords.event_type).distinct()
            result = session.execute(query)
            return result.scalars().all()
        finally:
            session.close()
    
    async def check_user_exists(self, username: str) -> bool:
        """
        检查用户是否存在
        
        Args:
            username: 用户名
            
        Returns:
            bool: 用户是否存在
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_check_user_exists,
                username
            )
            
            return exists
                
        except Exception as e:
            logger.error(f"检查用户是否存在失败: {e}")
            return False
    
    def _sync_check_user_exists(self, username: str) -> bool:
        """同步检查用户是否存在"""
        session = self.database_manager.get_session()
        try:
            # 查询用户是否存在 - 使用原始SQL查询避免模型字段不匹配问题
            from sqlalchemy import text
            query = text("SELECT id FROM user_permissions WHERE username = :username")
            result = session.execute(query, {"username": username})
            user_row = result.fetchone()
            
            return user_row is not None
                
        finally:
            session.close()
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        用户认证
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Optional[Dict[str, Any]]: 用户信息，如果认证失败返回None
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            user_info = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_authenticate_user,
                username, password
            )
            
            return user_info
                
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            return None
    
    def _sync_authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """同步用户认证"""
        session = self.database_manager.get_session()
        try:
            # 查询用户信息 - 使用原始SQL查询避免模型字段不匹配问题
            from sqlalchemy import text
            query = text("SELECT id, username, password_hash, role, permissions, is_active FROM user_permissions WHERE username = :username")
            result = session.execute(query, {"username": username})
            user_row = result.fetchone()
            
            if user_row is None:
                logger.warning(f"用户不存在: {username}")
                return None
            
            # 提取用户信息
            user_id, username, password_hash, role, permissions, is_active = user_row
            
            # 检查用户是否激活
            if not is_active:
                logger.warning(f"用户已被禁用: {username}")
                return None
            
            # 验证密码 - 支持bcrypt哈希密码和明文密码
            # 检查是否是bcrypt哈希（以$2b$开头）
            if password_hash.startswith('$2b$'):
                # 使用bcrypt验证密码
                if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                    return {
                        'user_id': str(user_id),  # 使用数据库中的id作为user_id
                        'username': username,
                        'permission_type': role,  # 使用数据库中的role字段
                        'allowed_commands': permissions or {}  # 使用数据库中的permissions字段
                    }
                else:
                    logger.warning(f"bcrypt密码验证失败: {username}")
                    return None
            else:
                # 使用明文密码验证（向后兼容）
                if password_hash == password:
                    return {
                        'user_id': str(user_id),
                        'username': username,
                        'permission_type': role,
                        'allowed_commands': permissions or {}
                    }
                else:
                    logger.warning(f"明文密码验证失败: {username}")
                    return None
                
        finally:
            session.close()
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据用户ID获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[Dict[str, Any]]: 用户信息，如果用户不存在返回None
        """
        try:
            # 使用同步方式执行查询
            loop = asyncio.get_event_loop()
            user_info = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_get_user_by_id,
                user_id
            )
            
            return user_info
                
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        修改用户密码
        
        Args:
            user_id: 用户ID
            current_password: 当前密码
            new_password: 新密码
            
        Returns:
            bool: 修改是否成功
        """
        try:
            # 使用同步方式执行修改
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_change_password,
                user_id, current_password, new_password
            )
            
            return result
                
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return False
    
    def _sync_get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """同步根据用户ID获取用户信息"""
        session = self.database_manager.get_session()
        try:
            # 查询用户信息
            query = select(UserPermissions).where(UserPermissions.user_id == user_id)
            result = session.execute(query)
            user = result.scalar_one_or_none()
            
            if user is None:
                logger.warning(f"用户不存在: {user_id}")
                return None
            
            return {
                'user_id': user.user_id,
                'username': user.username,
                'permission_type': user.permission_type,
                'allowed_commands': user.allowed_commands
            }
                
        finally:
            session.close()
    
    def _sync_change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """同步修改用户密码"""
        session = self.database_manager.get_session()
        try:
            # 查询用户信息 - 使用原始SQL查询避免模型字段不匹配问题
            from sqlalchemy import text
            query = text("SELECT id, username, password_hash, role, permissions, is_active FROM user_permissions WHERE id = :user_id")
            result = session.execute(query, {"user_id": user_id})
            user_row = result.fetchone()
            
            if user_row is None:
                logger.warning(f"用户不存在: {user_id}")
                return False
            
            # 提取用户信息
            db_id, username, password_hash, role, permissions, is_active = user_row
            
            # 检查用户是否激活
            if not is_active:
                logger.warning(f"用户已被禁用: {username}")
                return False
            
            # 验证当前密码 - 支持bcrypt哈希密码和明文密码
            # 检查是否是bcrypt哈希（以$2b$开头）
            if password_hash.startswith('$2b$'):
                # 使用bcrypt验证密码
                if not bcrypt.checkpw(current_password.encode('utf-8'), password_hash.encode('utf-8')):
                    logger.warning(f"当前密码验证失败: {username}")
                    return False
            else:
                # 使用明文密码验证（向后兼容）
                if password_hash != current_password:
                    logger.warning(f"当前密码验证失败: {username}")
                    return False
            
            # 生成新的密码哈希
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # 更新密码
            update_query = text("UPDATE user_permissions SET password_hash = :password_hash WHERE id = :user_id")
            session.execute(update_query, {
                "password_hash": new_password_hash,
                "user_id": user_id
            })
            session.commit()
            
            logger.info(f"用户密码修改成功: {username}")
            return True
                
        except Exception as e:
            logger.error(f"修改密码操作失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def _status_history_to_dict(self, record: StatusHistory) -> Dict[str, Any]:
        """将状态历史记录转换为字典"""
        return {
            'id': record.id,
            'device_id': record.device_id,
            'timestamp': record.timestamp.isoformat(),
            'status_type': record.status_type,
            'bit_position': record.bit_position,
            'old_value': record.old_value,
            'new_value': record.new_value,
            'status_name': record.status_name
        }
    
    def _real_time_data_to_dict(self, record: RealTimeData) -> Dict[str, Any]:
        """将实时数据记录转换为字典"""
        return {
            'id': record.id,
            'device_id': record.device_id,
            'timestamp': record.timestamp.isoformat(),
            'parameter_name': record.parameter_name,
            'value': record.value,
            'unit': record.unit
        }
    
    def _event_record_to_dict(self, record: EventRecords) -> Dict[str, Any]:
        """将事件记录转换为字典"""
        return {
            'id': record.id,
            'device_id': record.device_id,
            'event_time': record.event_time.isoformat(),
            'event_type': record.event_type,
            'description': record.description
        }


async def main():
    """测试数据库API"""
    from config.config_manager import ConfigManager
    from database.database_manager import DatabaseManager
    
    config_manager = ConfigManager()
    database_manager = DatabaseManager(config_manager)
    
    try:
        if await database_manager.initialize():
            api = DatabaseAPI(database_manager)
            
            # 测试获取设备列表
            devices = await api.get_device_list()
            # print(f"设备列表: {devices}")  # 调试信息已注释
            
            # 测试获取统计信息
            stats = await api.get_statistics()
            # print(f"统计信息: {stats}")  # 调试信息已注释
            
        else:
            pass
            # print("数据库管理器初始化失败")  # 调试信息已注释
    finally:
        await database_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
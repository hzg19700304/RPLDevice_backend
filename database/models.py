# flake8: noqa
"""
数据库模型定义
基于需求文档中的表结构定义SQLAlchemy模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, DECIMAL, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.mysql import TINYINT
import datetime

Base = declarative_base()


class StatusHistory(Base):
    """状态历史表模型"""
    __tablename__ = 'status_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    record_time = Column(DateTime, default=datetime.datetime.now, comment='记录插入时间')
    timestamp = Column(DateTime(3), nullable=False, comment='状态变化时间戳（毫秒精度）')
    status_type = Column(String(50), nullable=False, comment='状态类型：WorkStatus/OutputStatus/FaultStatus/InputStatus/IGBTStatus')
    bit_position = Column(Integer, nullable=False, comment='位位置（0-15）')
    old_value = Column(TINYINT, nullable=False, comment='变化前的状态值（0或1）')
    new_value = Column(TINYINT, nullable=False, comment='变化后的状态值（0或1）')
    status_name = Column(String(100), nullable=False, comment='状态名称描述')
    device_id = Column(String(50), nullable=False, comment='设备ID')
    upload_status = Column(TINYINT, default=0, comment='上传状态：0-待上传，1-已上传，2-上传失败')
    upload_time = Column(DateTime, comment='实际上传时间')
    retry_count = Column(TINYINT, default=0, comment='重试次数')
    last_error = Column(String(255), comment='最后错误信息')
    
    __table_args__ = (
        Index('idx_status_device_timestamp', 'device_id', 'timestamp'),
        Index('idx_status_type_timestamp', 'status_type', 'timestamp'),
        Index('idx_status_bit_position', 'bit_position'),
    )
    
    def __repr__(self):
        return f"<StatusHistory(device_id={self.device_id}, status_type={self.status_type}, timestamp={self.timestamp})>"


class RealTimeData(Base):
    """实时数据表模型"""
    __tablename__ = 'real_time_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    timestamp = Column(DateTime(3), nullable=False, comment='数据采集时间戳（毫秒精度）')
    device_id = Column(String(50), nullable=False, comment='设备ID')
    parameter_name = Column(String(50), nullable=False, comment='模拟量名称（如SV1/SA1）')
    value = Column(DECIMAL(10, 3), nullable=False, comment='模拟量值')
    unit = Column(String(10), nullable=False, comment='单位（如V/A/℃）')
    upload_status = Column(TINYINT, default=0, comment='上传状态：0-待上传，1-已上传，2-上传失败')
    upload_time = Column(DateTime, comment='实际上传时间')
    retry_count = Column(TINYINT, default=0, comment='重试次数')
    last_error = Column(String(255), comment='最后错误信息')
    
    def __repr__(self):
        return f"<RealTimeData(device_id={self.device_id}, parameter={self.parameter_name}, value={self.value})>"


class EventRecords(Base):
    """事件记录表模型"""
    __tablename__ = 'event_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    event_time = Column(DateTime(3), nullable=False, comment='事件发生时间戳（毫秒精度）')
    event_type = Column(String(50), nullable=False, comment='事件类型')
    device_id = Column(String(50), nullable=False, comment='设备ID')
    description = Column(Text, comment='事件描述')
    upload_status = Column(TINYINT, default=0, comment='上传状态：0-待上传，1-已上传，2-上传失败')
    upload_time = Column(DateTime, comment='实际上传时间')
    retry_count = Column(TINYINT, default=0, comment='重试次数')
    last_error = Column(String(255), comment='最后错误信息')
    
    def __repr__(self):
        return f"<EventRecords(device_id={self.device_id}, event_type={self.event_type}, time={self.event_time})>"


class UserPermissions(Base):
    """用户权限表模型"""
    __tablename__ = 'user_permissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = Column(String(50), nullable=False, unique=True, comment='用户ID')
    username = Column(String(50), nullable=False, comment='用户名')
    password_hash = Column(String(255), nullable=False, comment='密码哈希')
    permission_type = Column(String(50), default='view_only', comment='权限类型：view_only/control/admin')
    allowed_commands = Column(JSON, comment='允许执行的指令列表')
    created_at = Column(DateTime, default=datetime.datetime.now, comment='创建时间')
    last_login = Column(DateTime, comment='最后登录时间')
    is_active = Column(TINYINT, default=1, comment='是否激活：1-激活，0-禁用')
    
    def __repr__(self):
        return f"<UserPermissions(user_id={self.user_id}, username={self.username}, permission={self.permission_type})>"


# 数据转换辅助类
class DeviceDataConverter:
    """设备数据转换器"""
    
    @staticmethod
    def convert_to_status_history(status_type, bit_position, old_value, new_value, status_name, device_id):
        """将设备数据转换为状态历史记录"""
        return StatusHistory(
            timestamp=datetime.datetime.now().replace(microsecond=datetime.datetime.now().microsecond // 1000 * 1000),
            status_type=status_type,
            bit_position=bit_position,
            old_value=old_value,
            new_value=new_value,
            status_name=status_name,
            device_id=device_id
        )
    
    @staticmethod
    def convert_to_real_time_data(device_data, parameter_name, value, unit, device_id):
        """将设备数据转换为实时数据记录"""
        return RealTimeData(
            timestamp=datetime.datetime.now(),
            device_id=device_id,
            parameter_name=parameter_name,
            value=value,
            unit=unit
        )
    
    @staticmethod
    def convert_to_event_record(event_type, device_id, description):
        """将事件数据转换为事件记录"""
        return EventRecords(
            event_time=datetime.datetime.now(),
            event_type=event_type,
            device_id=device_id,
            description=description
        )
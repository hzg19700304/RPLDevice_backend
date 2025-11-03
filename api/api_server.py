#!/usr/bin/env python3
# flake8: noqa
"""
RPLDevice API服务器
基于FastAPI实现Restful API接口
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.config_manager import ConfigManager
from database.database_api import DatabaseAPI
from database.database_manager import DatabaseManager
from api.auth import AuthManager

logger = logging.getLogger(__name__)


# 数据模型定义
class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    """Token响应模型"""
    token: str
    token_type: str = "Bearer"
    expires_in: int
    user_info: Dict[str, Any]


class DeviceInfo(BaseModel):
    """设备信息模型"""
    device_id: str
    device_name: str
    device_ip: str
    system_version: str
    online_status: bool
    last_update: str


class ConnectionStatus(BaseModel):
    """连接状态模型"""
    hmi_serial: Dict[str, Any]
    pscada_serial: Dict[str, Any]
    server_tcp: Dict[str, Any]
    websocket: Dict[str, Any]


class HistoryDataRequest(BaseModel):
    """历史数据请求模型"""
    start_time: str
    end_time: str
    param_name: Optional[str] = None
    page: int = 1
    page_size: int = 20


class HistoryDataResponse(BaseModel):
    """历史数据响应模型"""
    total: int
    page: int
    page_size: int
    list: List[Dict[str, Any]]


class EventRecord(BaseModel):
    """事件记录请求模型"""
    id: str
    device_id: str
    event_time: str
    event_type: str
    description: str


class EventRecordsResponse(BaseModel):
    """事件记录响应模型"""
    total: int
    page: int
    page_size: int
    list: List[EventRecord]


class ControlCommand(BaseModel):
    """控制指令模型"""
    device_id: str
    command_type: str  # "remote_control", "parameter_set", "fault_reset"
    command_data: Dict[str, Any]


class APIServer:
    """API服务器类"""
    
    def __init__(self, config_manager: ConfigManager, host: str = "0.0.0.0", port: int = 8000, 
                 serial_manager=None, connection_manager=None):
        self.config_manager = config_manager
        self.host = host
        self.port = port
        
        # 创建数据库管理器
        self.database_manager = DatabaseManager(config_manager)
        self.database_api = None
        self.auth_manager = AuthManager()
        
        # 串口管理器和连接管理器
        self.serial_manager = serial_manager
        self.connection_manager = connection_manager
        
        # 创建FastAPI应用
        self.app = FastAPI(
            title="RPLDevice API",
            description="钢轨电位限制装置RESTful API接口",
            version="1.0.0"
        )
        
        # 配置CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 生产环境应限制域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 设置路由
        self._setup_routes()
        
        # 服务器实例
        self.server = None
    
    def _setup_routes(self):
        """设置API路由"""
        
        # 认证接口
        @self.app.post("/api/v1/auth/login", response_model=Dict[str, Any])
        async def login(request: LoginRequest):
            """用户登录"""
            return await self._handle_login(request)
        
        @self.app.post("/api/v1/auth/refresh", response_model=Dict[str, Any])
        async def refresh_token(request: Request):
            """刷新Token"""
            return await self._handle_refresh_token(request)
        
        @self.app.post("/api/v1/auth/logout", response_model=Dict[str, Any])
        async def logout():
            """退出登录"""
            return await self._handle_logout()
        
        @self.app.post("/api/v1/auth/change_password", response_model=Dict[str, Any])
        async def change_password(request: Request, password_request: ChangePasswordRequest):
            """修改密码"""
            return await self._handle_change_password(request, password_request)
        
        # 设备信息接口
        @self.app.get("/api/v1/device/info", response_model=Dict[str, Any])
        async def get_device_info():
            """获取设备基础信息"""
            return await self._handle_get_device_info()
        
        @self.app.get("/api/v1/device/connection_status", response_model=Dict[str, Any])
        async def get_connection_status():
            """获取连接状态"""
            return await self._handle_get_connection_status()
        
        # 历史数据查询接口
        @self.app.get("/api/v1/history/analog", response_model=Dict[str, Any])
        async def get_analog_history(
            start_time: str = Query(..., description="开始时间"),
            end_time: str = Query(..., description="结束时间"),
            param_name: Optional[str] = Query(None, description="参数名称"),
            page: int = Query(1, description="页码"),
            page_size: int = Query(20, description="每页条数")
        ):
            """查询历史模拟量数据"""
            return await self._handle_get_analog_history(
                start_time, end_time, param_name, page, page_size
            )
        
        # 事件记录查询接口
        @self.app.get("/api/v1/history/events", response_model=EventRecordsResponse)
        async def get_event_records(
            start_time: str = Query(..., description="开始时间"),
            end_time: str = Query(..., description="结束时间"),
            device_id: Optional[str] = Query(None, description="设备ID"),
            event_type: Optional[str] = Query(None, description="事件类型"),
            page: int = Query(1, description="页码"),
            page_size: int = Query(20, description="每页条数")
        ):
            """查询事件记录"""
            return await self._handle_get_event_records(
                start_time, end_time, device_id, event_type, page, page_size
            )
        
        # 状态历史查询接口
        @self.app.get("/api/v1/history/status", response_model=Dict[str, Any])
        async def get_status_history(
            start_time: str = Query(..., description="开始时间"),
            end_time: str = Query(..., description="结束时间"),
            device_id: Optional[str] = Query(None, description="设备ID"),
            status_type: Optional[str] = Query(None, description="状态类型"),
            page: int = Query(1, description="页码"),
            page_size: int = Query(20, description="每页条数")
        ):
            """查询状态历史数据"""
            return await self._handle_get_status_history(
                start_time, end_time, device_id, status_type, page, page_size
            )
        
        # 控制指令接口
        @self.app.post("/api/v1/control/command", response_model=Dict[str, Any])
        async def send_control_command(command: ControlCommand):
            """发送控制指令"""
            return await self._handle_send_control_command(command)
        
        # 健康检查接口
        @self.app.get("/api/v1/health", response_model=Dict[str, Any])
        async def health_check():
            """健康检查"""
            return await self._handle_health_check()
    
    # API处理函数
    async def _handle_login(self, request: LoginRequest) -> Dict[str, Any]:
        """处理登录请求"""
        try:
            # 检查数据库API是否可用
            if not self.database_api:
                raise HTTPException(status_code=500, detail="数据库API未初始化")
            
            # 先检查用户是否存在
            user_exists = await self.database_api.check_user_exists(request.username)
            
            if not user_exists:
                raise HTTPException(status_code=401, detail="用户不存在")
            
            # 使用数据库API进行用户认证
            user_info = await self.database_api.authenticate_user(request.username, request.password)
            
            if user_info is None:
                # 用户存在但认证失败，说明密码错误
                raise HTTPException(status_code=401, detail="密码错误")
            
            # 使用认证管理器创建Token
            token = self.auth_manager.create_access_token(user_info)
            
            return {
                "code": 200,
                "msg": "登录成功",
                "data": {
                    "token": token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "user_info": {
                        "user_id": user_info.get("user_id", ""),
                        "username": user_info.get("username", ""),
                        "permission_type": user_info.get("permission_type", "viewer")
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"用户登录时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="登录失败，请稍后重试")
    
    async def _handle_refresh_token(self, request: Request) -> Dict[str, Any]:
        """处理Token刷新"""
        try:
            # 检查认证管理器是否可用
            if not self.auth_manager:
                raise HTTPException(status_code=500, detail="认证管理器未初始化")
            
            # 从请求头中获取Authorization信息
            authorization = request.headers.get("Authorization")
            
            if not authorization:
                raise HTTPException(status_code=401, detail="缺少Authorization头")
            
            # 提取Bearer Token
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Authorization格式错误，应为Bearer Token")
            
            token = authorization[7:]  # 移除"Bearer "前缀
            
            if not token:
                raise HTTPException(status_code=401, detail="Token不能为空")
            
            # 使用认证管理器刷新Token
            new_token = self.auth_manager.refresh_token(token)
            
            # 返回新的Token信息
            return {
                "code": 200,
                "msg": "Token刷新成功",
                "data": {
                    "token": new_token,
                    "token_type": "Bearer",
                    "expires_in": self.auth_manager.token_expire_hours * 3600  # 转换为秒
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"Token刷新时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="Token刷新失败，请稍后重试")
    
    async def _handle_logout(self) -> Dict[str, Any]:
        """处理退出登录"""
        # TODO: 实现退出登录逻辑
        return {
            "code": 200,
            "msg": "已退出登录",
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_change_password(self, request: Request, password_request: ChangePasswordRequest) -> Dict[str, Any]:
        """处理修改密码请求"""
        try:
            # 从请求头中获取Authorization信息
            authorization = request.headers.get("Authorization")
            
            if not authorization:
                raise HTTPException(status_code=401, detail="缺少Authorization头")
            
            # 提取Bearer Token
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Authorization格式错误，应为Bearer Token")
            
            token = authorization[7:]  # 移除"Bearer "前缀
            
            if not token:
                raise HTTPException(status_code=401, detail="Token不能为空")
            
            # 验证Token并获取用户信息
            if not self.auth_manager:
                raise HTTPException(status_code=500, detail="认证管理器未初始化")
            
            payload = self.auth_manager.verify_token(token)
            user_id = payload.get("sub")
            
            if not user_id:
                raise HTTPException(status_code=401, detail="Token中缺少用户ID")
            
            # 检查数据库API是否可用
            if not self.database_api:
                raise HTTPException(status_code=500, detail="数据库API未初始化")
            
            # 使用数据库API修改密码
            success = await self.database_api.change_password(
                user_id, 
                password_request.current_password, 
                password_request.new_password
            )
            
            if not success:
                raise HTTPException(status_code=400, detail="修改密码失败，请检查当前密码是否正确")
            
            return {
                "code": 200,
                "msg": "密码修改成功",
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"修改密码时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="修改密码失败，请稍后重试")
    
    async def _handle_health_check(self) -> Dict[str, Any]:
        """处理健康检查"""
        try:
            # 检查关键服务组件是否可用
            health_status = {
                "overall_status": "healthy",
                "components": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # 检查配置管理器
            if not self.config_manager:
                health_status["components"]["config_manager"] = {
                    "status": "unhealthy",
                    "detail": "配置管理器未初始化"
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["components"]["config_manager"] = {
                    "status": "healthy",
                    "detail": "配置管理器运行正常"
                }
            
            # 检查数据库API
            if not self.database_api:
                health_status["components"]["database_api"] = {
                    "status": "unhealthy",
                    "detail": "数据库API未初始化"
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["components"]["database_api"] = {
                    "status": "healthy",
                    "detail": "数据库API运行正常"
                }
            
            # 检查认证管理器
            if not self.auth_manager:
                health_status["components"]["auth_manager"] = {
                    "status": "unhealthy",
                    "detail": "认证管理器未初始化"
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["components"]["auth_manager"] = {
                    "status": "healthy",
                    "detail": "认证管理器运行正常"
                }
            
            # 根据整体状态返回不同的响应
            if health_status["overall_status"] == "healthy":
                return {
                    "code": 200,
                    "msg": "服务正常",
                    "data": health_status,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "code": 503,
                    "msg": "服务异常",
                    "data": health_status,
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"健康检查时发生错误: {str(e)}")
            
            # 返回服务不可用状态
            return {
                "code": 503,
                "msg": "健康检查失败",
                "data": {
                    "overall_status": "unhealthy",
                    "components": {
                        "health_check_service": {
                            "status": "unhealthy",
                            "detail": f"健康检查服务异常: {str(e)}"
                        }
                    },
                    "timestamp": datetime.now().isoformat()
                },
                "timestamp": datetime.now().isoformat()
            }
    
    async def _handle_get_device_info(self) -> Dict[str, Any]:
        """处理获取设备信息"""
        try:
            # 检查配置管理器是否可用
            if not self.config_manager:
                raise HTTPException(status_code=500, detail="配置管理器未初始化")
            
            # 获取设备信息
            device_info = self.config_manager.get_device_info()
            
            # 验证设备信息是否有效
            if not device_info:
                raise HTTPException(status_code=500, detail="设备信息获取失败")
            
            # 检查必要字段是否存在
            required_fields = ["device_id", "device_name", "device_ip", "system_version"]
            missing_fields = []
            for field in required_fields:
                if field not in device_info or not device_info[field]:
                    missing_fields.append(field)
                    logger.warning(f"设备信息字段 {field} 缺失或为空")
            
            # 如果有缺失字段，抛出错误
            if missing_fields:
                raise HTTPException(
                    status_code=500, 
                    detail=f"设备信息不完整，缺失字段: {', '.join(missing_fields)}"
                )
            
            # 使用配置文件中实际的设备信息
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "device_id": device_info["device_id"],
                    "device_name": device_info["device_name"],
                    "device_ip": device_info["device_ip"],
                    "system_version": device_info["system_version"],
                    "online_status": True,
                    "last_update": datetime.now().isoformat()
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"获取设备信息时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="获取设备信息失败，请稍后重试")
    
    async def _handle_get_connection_status(self) -> Dict[str, Any]:
        """处理获取连接状态"""
        try:
            # 检查配置管理器是否可用
            if not self.config_manager:
                raise HTTPException(status_code=500, detail="配置管理器未初始化")
            
            # 获取实际的串口连接状态
            hmi_status = "offline"
            pscada_status = "offline"
            hmi_port = "未知"
            pscada_port = "未知"
            
            # 检查HMI串口连接状态
            if hasattr(self, 'serial_manager') and self.serial_manager:
                if self.serial_manager.hmi_master and self.serial_manager.hmi_master.is_open():
                    hmi_status = "online"
                    # 获取实际的HMI串口端口
                    if hasattr(self.serial_manager.hmi_master, 'port') and self.serial_manager.hmi_master.port:
                        hmi_port = self.serial_manager.hmi_master.port
                else:
                    hmi_status = "offline"
                
                # 检查SCADA串口连接状态
                if self.serial_manager.scada_master and self.serial_manager.scada_master.is_open():
                    pscada_status = "online"
                    # 获取实际的SCADA串口端口
                    if hasattr(self.serial_manager.scada_master, 'port') and self.serial_manager.scada_master.port:
                        pscada_port = self.serial_manager.scada_master.port
                else:
                    pscada_status = "offline"
            
            # 获取WebSocket连接统计
            websocket_connections = 0
            if hasattr(self, 'connection_manager') and self.connection_manager:
                websocket_connections = len(self.connection_manager.active_connections)
            
            connection_status = {
                "hmi_serial": {
                    "status": hmi_status,
                    "port": hmi_port,
                    "last_connected": datetime.now().isoformat()
                },
                "pscada_serial": {
                    "status": pscada_status,
                    "port": pscada_port,
                    "last_connected": datetime.now().isoformat()
                },
                "control_board_serial": {
                    "status": hmi_status,
                    "port": hmi_port,
                    "last_connected": datetime.now().isoformat()
                },
                "server_tcp": {
                    "status": "online",
                    "server_ip": "192.168.0.1",
                    "last_connected": datetime.now().isoformat()
                },
                "websocket": {
                    "active_connections": websocket_connections,
                    "max_connections": 10
                }
            }
            
            # 验证连接状态数据是否有效
            if not connection_status:
                raise HTTPException(status_code=500, detail="连接状态数据获取失败")
            
            # 检查关键连接状态
            critical_connections = ["hmi_serial", "pscada_serial"]
            for conn_name in critical_connections:
                if conn_name not in connection_status:
                    logger.warning(f"关键连接状态 {conn_name} 缺失")
                elif connection_status[conn_name].get("status") == "offline":
                    logger.warning(f"关键连接 {conn_name} 处于离线状态")
            
            return {
                "code": 200,
                "msg": "success",
                "data": connection_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"获取连接状态时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="获取连接状态失败，请稍后重试")
    
    async def _handle_get_analog_history(
        self, start_time: str, end_time: str, param_name: Optional[str], 
        page: int, page_size: int
    ) -> Dict[str, Any]:
        """处理获取历史模拟量数据"""
        try:
            # 检查数据库API是否可用
            if not self.database_api:
                raise HTTPException(status_code=500, detail="数据库API未初始化")
            
            # 验证时间参数格式
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"时间参数格式错误: {str(e)}")
            
            # 验证时间范围
            if start_dt >= end_dt:
                raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
            
            # 验证分页参数 - 移除page_size限制，允许查询任意数量数据
            if page < 1:
                raise HTTPException(status_code=400, detail="页码必须大于等于1")
            # 不再限制page_size，允许查询上万条数据
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 从数据库查询实时数据 - 如果page_size <= 0则查询所有数据
            if page_size <= 0:
                # 查询所有数据，不限制数量
                real_time_data = await self.database_api.get_real_time_data_unlimited(
                    parameter_name=param_name,
                    start_time=start_dt,
                    end_time=end_dt
                )
            else:
                # 分页查询
                real_time_data = await self.database_api.get_real_time_data(
                    device_id=None,  # 查询所有设备
                    parameter_name=param_name,
                    start_time=start_dt,
                    end_time=end_dt,
                    limit=page_size,
                    offset=offset
                )
            
            # 验证查询结果
            if not real_time_data:
                # 如果没有数据，返回空列表
                return {
                    "code": 200,
                    "msg": "success",
                    "data": {
                        "total": 0,
                        "page": page,
                        "page_size": page_size,
                        "list": []
                    },
                    "timestamp": datetime.now().isoformat()
                }
            
            # 获取总记录数用于分页
            total_count = await self._get_total_real_time_count(start_dt, end_dt, param_name)
            
            # 转换数据格式
            data_list = []
            for record in real_time_data:
                data_list.append({
                    "timestamp": record.get('timestamp', ''),
                    "parameter_name": record.get('parameter_name', ''),
                    "value": float(record.get('value', 0)),
                    "unit": record.get('unit', '')
                })
            
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "list": data_list
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"查询历史模拟量数据时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="查询历史数据失败，请稍后重试")
    
    async def _get_total_real_time_count(
        self, start_time: datetime, end_time: datetime, param_name: Optional[str]
    ) -> int:
        """获取实时数据总记录数"""
        try:
            # 获取统计信息
            stats = await self.database_api.get_statistics(
                device_id=None,
                start_time=start_time,
                end_time=end_time
            )
            
            # 返回实时数据记录数
            return stats.get('real_time_data', {}).get('count', 0)
            
        except Exception as e:
            logger.error(f"获取实时数据总记录数失败: {str(e)}")
            return 0
    
    async def _handle_get_event_records(
        self, start_time: str, end_time: str, device_id: Optional[str], 
        event_type: Optional[str], page: int, page_size: int
    ) -> EventRecordsResponse:
        """处理获取事件记录"""
        try:
            # 检查数据库API是否可用
            if not self.database_api:
                raise HTTPException(status_code=500, detail="数据库API未初始化")
            
            # 验证时间参数格式
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"时间参数格式错误: {str(e)}")
            
            # 验证时间范围
            if start_dt >= end_dt:
                raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
            
            # 验证分页参数 - 移除page_size限制，允许查询任意数量数据
            if page < 1:
                raise HTTPException(status_code=400, detail="页码必须大于等于1")
            # 不再限制page_size，允许查询上万条数据
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 从数据库查询事件记录 - 如果page_size <= 0则查询所有数据
            if page_size <= 0:
                # 查询所有数据，不限制数量
                event_records = await self.database_api.get_event_records_unlimited(
                    device_id=device_id,
                    event_type=event_type,
                    start_time=start_dt,
                    end_time=end_dt
                )
            else:
                # 分页查询
                event_records = await self.database_api.get_event_records(
                    device_id=device_id,
                    event_type=event_type,
                    start_time=start_dt,
                    end_time=end_dt,
                    limit=page_size,
                    offset=offset
                )
            
            # 验证查询结果
            if not event_records:
                # 如果没有数据，返回空列表
                return EventRecordsResponse(
                    total=0,
                    page=page,
                    page_size=page_size,
                    list=[]
                )
            
            # 获取总记录数用于分页
            total_count = await self._get_total_event_count(start_dt, end_dt, device_id, event_type)
            
            # 转换数据格式为EventRecord模型
            event_record_list = []
            for record in event_records:
                event_record = EventRecord(
                    id=str(record.get('id', '')),
                    device_id=record.get('device_id', ''),
                    event_time=record.get('event_time', ''),
                    event_type=record.get('event_type', ''),
                    description=record.get('description', '')
                )
                event_record_list.append(event_record)
            
            return EventRecordsResponse(
                total=total_count,
                page=page,
                page_size=page_size,
                list=event_record_list
            )
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"查询事件记录时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="查询事件记录失败，请稍后重试")
    
    async def _get_total_event_count(
        self, start_time: datetime, end_time: datetime, 
        device_id: Optional[str], event_type: Optional[str]
    ) -> int:
        """获取事件记录总记录数"""
        try:
            # 获取统计信息
            stats = await self.database_api.get_statistics(
                device_id=device_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # 返回事件记录数
            return stats.get('event_records', {}).get('count', 0)
            
        except Exception as e:
            logger.error(f"获取事件记录总记录数失败: {str(e)}")
            return 0
    
    async def _handle_get_status_history(
        self, start_time: str, end_time: str, device_id: Optional[str], 
        status_type: Optional[str], page: int, page_size: int
    ) -> Dict[str, Any]:
        """处理获取状态历史数据"""
        try:
            # 检查数据库API是否可用
            if not self.database_api:
                raise HTTPException(status_code=500, detail="数据库API未初始化")
            
            # 验证时间参数格式
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"时间参数格式错误: {str(e)}")
            
            # 验证时间范围
            if start_dt >= end_dt:
                raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
            
            # 验证分页参数
            if page < 1:
                raise HTTPException(status_code=400, detail="页码必须大于等于1")
            if page_size < 1 or page_size > 100:
                raise HTTPException(status_code=400, detail="每页条数必须在1-100之间")
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 从数据库查询状态历史数据
            status_history = await self.database_api.get_status_history(
                device_id=device_id,
                start_time=start_dt,
                end_time=end_dt,
                limit=page_size,
                offset=offset
            )
            
            # 验证查询结果
            if not status_history:
                # 如果没有数据，返回空列表
                return {
                    "code": 200,
                    "msg": "查询成功",
                    "data": {
                        "total": 0,
                        "page": page,
                        "page_size": page_size,
                        "list": []
                    },
                    "timestamp": datetime.now().isoformat()
                }
            
            # 过滤状态类型（如果指定了）
            filtered_data = []
            for record in status_history:
                # 如果指定了状态类型，进行过滤
                if status_type and record.get('status_type') != status_type:
                    continue
                filtered_data.append(record)
            
            # 获取总记录数用于分页（基于过滤后的数据计算）
            total_count = await self._get_total_status_count(start_dt, end_dt, device_id, status_type)
            
            return {
                "code": 200,
                "msg": "查询成功",
                "data": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "list": filtered_data
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"查询状态历史数据时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail="查询状态历史数据失败，请稍后重试")
    
    async def _get_total_status_count(
        self, start_time: datetime, end_time: datetime, 
        device_id: Optional[str], status_type: Optional[str]
    ) -> int:
        """获取状态历史总记录数"""
        try:
            # 先获取基础统计数据
            stats = await self.database_api.get_statistics(
                device_id=device_id,
                start_time=start_time,
                end_time=end_time
            )
            
            total_count = stats.get('status_history', {}).get('count', 0)
            
            # 如果指定了状态类型，需要重新计算总数
            if status_type:
                # 从数据库查询该状态类型的记录数
                # 由于数据库API不支持状态类型过滤，我们需要分页查询所有记录并计数
                # 这里使用一个较大的limit来获取所有记录
                all_records = await self.database_api.get_status_history(
                    device_id=device_id,
                    start_time=start_time,
                    end_time=end_time,
                    limit=10000,  # 假设单页最多1万条记录
                    offset=0
                )
                
                # 过滤状态类型并计数
                filtered_count = 0
                for record in all_records:
                    if record.get('status_type') == status_type:
                        filtered_count += 1
                
                return filtered_count
            
            return total_count
            
        except Exception as e:
            logger.error(f"获取状态历史总记录数失败: {str(e)}")
            return 0
    
    async def _handle_send_control_command(self, command: ControlCommand) -> Dict[str, Any]:
        """处理发送控制指令"""
        # TODO: 实现控制指令下发逻辑
        return {
            "code": 200,
            "msg": "控制指令已发送",
            "data": {
                "command_id": f"cmd_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "command_type": command.command_type,
                "status": "sent",
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def start(self):
        """启动API服务器"""
        try:
            # 初始化数据库
            if await self.database_manager.initialize():
                self.database_api = DatabaseAPI(self.database_manager)
                logger.info("数据库管理器初始化成功")
            else:
                logger.error("数据库管理器初始化失败")
                raise Exception("数据库管理器初始化失败")
            
            import uvicorn
            config = uvicorn.Config(
                self.app, 
                host=self.host, 
                port=self.port,
                log_level="info"
            )
            self.server = uvicorn.Server(config)
            await self.server.serve()
        except ImportError:
            logger.error("未安装uvicorn，无法启动API服务器")
            logger.info("请安装: pip install uvicorn fastapi")
        except Exception as e:
            logger.error(f"API服务器启动失败: {e}")
    
    async def stop(self):
        """停止API服务器"""
        if self.server:
            self.server.should_exit = True
        
        # 关闭数据库连接
        if self.database_manager:
            await self.database_manager.close()
            logger.info("数据库连接已关闭")


async def main():
    """API服务器主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建API服务器
    api_server = APIServer(config_manager, host="0.0.0.0", port=8000)
    
    try:
        # 启动API服务器
        await api_server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭API服务器...")
    except Exception as e:
        logger.error(f"API服务器运行出错: {e}")
    finally:
        # 确保服务器被正确关闭
        await api_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
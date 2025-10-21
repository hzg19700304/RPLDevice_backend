#!/usr/bin/env python3
# flake8: noqa
"""
认证模块
处理用户认证、Token管理等
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException
from jose import jwt, JWTError


class AuthManager:
    """认证管理器"""
    
    def __init__(self, secret_key: str = "your-secret-key-change-in-production", 
                 algorithm: str = "HS256", token_expire_hours: int = 24):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expire_hours = token_expire_hours
        
        # 模拟用户数据库
        self.users = {
            "admin": {
                "password": "admin123",  # 生产环境应使用哈希密码
                "user_id": "admin001",
                "username": "admin",
                "permission_type": "admin",
                "full_name": "系统管理员"
            },
            "operator": {
                "password": "operator123",
                "user_id": "operator001",
                "username": "operator",
                "permission_type": "operator",
                "full_name": "操作员"
            }
        }
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """用户认证"""
        user = self.users.get(username)
        if user and user["password"] == password:
            return {
                "user_id": user["user_id"],
                "username": user["username"],
                "permission_type": user["permission_type"],
                "full_name": user["full_name"]
            }
        return None
    
    def create_access_token(self, user_info: Dict[str, Any]) -> str:
        """创建访问Token"""
        expire = datetime.utcnow() + timedelta(hours=self.token_expire_hours)
        
        payload = {
            "sub": user_info["user_id"],
            "username": user_info["username"],
            "permission_type": user_info["permission_type"],
            "exp": expire
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证Token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="无效Token")
    
    def refresh_token(self, token: str) -> str:
        """刷新Token"""
        payload = self.verify_token(token)
        
        # 创建新的Token
        user_info = {
            "user_id": payload["sub"],
            "username": payload["username"],
            "permission_type": payload["permission_type"]
        }
        
        return self.create_access_token(user_info)


def get_auth_manager() -> AuthManager:
    """获取认证管理器实例"""
    return AuthManager()
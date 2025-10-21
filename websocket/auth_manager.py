#!/usr/bin/env python3
# flake8: noqa
"""
WebSocket认证管理器
处理WebSocket连接的认证和授权
"""

import logging
from typing import Dict, Any
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AuthManager:
    """WebSocket认证管理器"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
        # 获取认证配置
        self.auth_config = config_manager.get_websocket_config().get('auth', {})
        
        # 简单的令牌验证（生产环境应使用更安全的方案）
        self.valid_tokens = {
            'default_token': {
                'user_id': 'default_user',
                'username': '默认用户',
                'permissions': ['read', 'write', 'control']
            },
            'admin_token': {
                'user_id': 'admin_user',
                'username': '管理员',
                'permissions': ['read', 'write', 'control', 'admin']
            }
        }
    
    async def authenticate_connection(self, token: str) -> Dict[str, Any]:
        """
        认证WebSocket连接
        
        Args:
            token: 认证令牌
            
        Returns:
            认证结果字典
        """
        try:
            # 如果配置中禁用了认证，则直接通过
            if not self.auth_config.get('enabled', True):
                return {
                    'success': True,
                    'user_info': {
                        'user_id': 'anonymous',
                        'username': '匿名用户',
                        'permissions': ['read']
                    },
                    'error_code': 0,
                    'error_msg': ''
                }
            
            # 检查令牌是否为空
            if not token:
                return {
                    'success': False,
                    'user_info': {},
                    'error_code': 401,
                    'error_msg': '认证令牌不能为空'
                }
            
            # 验证令牌
            if token in self.valid_tokens:
                user_info = self.valid_tokens[token].copy()
                user_info['token'] = token
                
                logger.info(f"认证成功: {user_info['username']}")
                
                return {
                    'success': True,
                    'user_info': user_info,
                    'error_code': 0,
                    'error_msg': ''
                }
            else:
                logger.warning(f"认证失败: 无效的令牌")
                
                return {
                    'success': False,
                    'user_info': {},
                    'error_code': 403,
                    'error_msg': '无效的认证令牌'
                }
                
        except Exception as e:
            logger.error(f"认证过程中出错: {e}")
            
            return {
                'success': False,
                'user_info': {},
                'error_code': 500,
                'error_msg': f'认证服务内部错误: {str(e)}'
            }
    
    def validate_permission(self, user_info: Dict[str, Any], permission: str) -> bool:
        """
        验证用户权限
        
        Args:
            user_info: 用户信息
            permission: 需要验证的权限
            
        Returns:
            是否具有权限
        """
        try:
            permissions = user_info.get('permissions', [])
            return permission in permissions
        except Exception as e:
            logger.error(f"权限验证失败: {e}")
            return False
    
    def get_auth_config(self) -> Dict[str, Any]:
        """获取认证配置"""
        return self.auth_config.copy()
    
    def add_valid_token(self, token: str, user_info: Dict[str, Any]):
        """添加有效的令牌"""
        self.valid_tokens[token] = user_info
        logger.info(f"已添加令牌: {user_info.get('username', '未知用户')}")
    
    def remove_token(self, token: str):
        """移除令牌"""
        if token in self.valid_tokens:
            user_info = self.valid_tokens.pop(token)
            logger.info(f"已移除令牌: {user_info.get('username', '未知用户')}")
        else:
            logger.warning(f"尝试移除不存在的令牌: {token}")
    
    def get_valid_tokens_count(self) -> int:
        """获取有效令牌数量"""
        return len(self.valid_tokens)
#!/usr/bin/env python3
"""
测试用的简单配置管理器
"""

class TestConfigManager:
    """测试配置管理器"""
    
    def __init__(self):
        self.config = {
            'database': {
                'host': 'localhost',
                'port': 3306,
                'database': 'rpl_device_test',
                'username': 'root',
                'password': ''
            }
        }
    
    def get_database_config(self):
        """获取数据库配置"""
        return self.config.get('database', {})
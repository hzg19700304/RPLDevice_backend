# flake8: noqa
"""
数据库初始化模块
负责数据库的初始化和升级管理
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import pymysql
from sqlalchemy import text
from .database_manager import DatabaseManager
from .database_config import DatabaseConfigManager

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, config_manager):
        """
        初始化数据库初始化器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.database_manager: Optional[DatabaseManager] = None
        self.sql_scripts_path = Path(__file__).parent / "sql_scripts"
    
    async def initialize_database(self, force_recreate: bool = False) -> bool:
        """
        初始化数据库
        
        Args:
            force_recreate: 是否强制重新创建表结构
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 首先检查数据库是否存在（使用临时连接）
            if not await self._check_database_exists_with_temp_connection():
                # logger.info("数据库不存在，开始创建数据库...")  # 调试信息已注释
                await self._create_database()
                # 新数据库，需要执行完整初始化
                need_full_initialization = True
            else:
                # 数据库已存在，检查是否已完成初始化
                need_full_initialization = not await self._check_database_initialized()
                if need_full_initialization:
                    # logger.info("数据库存在但未完成初始化，执行完整初始化流程")  # 调试信息已注释
                    pass
                else:
                    # logger.info("数据库已初始化完成，跳过完整初始化流程")  # 调试信息已注释
                    pass
            
            # 创建数据库管理器并初始化连接
            self.database_manager = DatabaseManager(self.config_manager)
            await self.database_manager.initialize()
            
            # 创建表结构
            await self.database_manager.create_tables()
            
            if need_full_initialization or force_recreate:
                # 执行初始化脚本（包含分区表检查和创建）
                await self._execute_init_scripts(force_recreate=force_recreate)
                
                # 强制重新创建存储过程和事件调度器（包含分区和事件调度器脚本）
                try:
                    await self._force_recreate_procedures_and_events()
                except Exception as e:
                    logger.warning(f"强制重新创建存储过程和事件调度器失败，但继续执行: {e}")
                
                # 标记数据库已初始化完成
                await self._mark_database_initialized()
                
                if force_recreate:
                    # logger.info("强制重新创建表结构完成")  # 调试信息已注释
                    pass
            else:
                # 只检查表结构是否需要更新
                await self._check_and_update_table_structures()
            
            # logger.info("数据库初始化完成")  # 调试信息已注释
            return True
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return False
    
    async def _check_database_exists_with_temp_connection(self) -> bool:
        """使用临时连接检查数据库是否存在"""
        try:
            # 使用同步方式检查数据库存在性
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_check_database_exists_with_temp_connection)
        except Exception as e:
            logger.warning(f"检查数据库存在性失败: {e}")
            return False
    
    async def _check_database_exists(self) -> bool:
        """检查数据库是否存在"""
        try:
            # 使用同步方式检查数据库存在性
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_check_database_exists)
        except Exception as e:
            logger.warning(f"检查数据库存在性失败: {e}")
            return False
    
    async def _check_database_initialized(self) -> bool:
        """检查数据库是否已完成初始化"""
        try:
            # 使用同步方式检查数据库初始化状态
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_check_database_initialized)
        except Exception as e:
            logger.warning(f"检查数据库初始化状态失败: {e}")
            return False
    
    def _sync_check_database_initialized(self) -> bool:
        """同步检查数据库是否已完成初始化"""
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 检查是否存在初始化标记表或记录
                # 使用与_create_database_connection相同的键名映射逻辑
                db_config = self.config_manager.get_database_config()
                database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
                
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'system_config'
                """, (database_name,))
                
                table_exists = cursor.fetchone()[0] > 0
                
                if table_exists:
                    # 检查是否存在初始化标记记录
                    cursor.execute("""
                        SELECT COUNT(*) FROM system_config 
                        WHERE config_key = 'database.initialized'
                    """)
                    
                    initialized = cursor.fetchone()[0] > 0
                    return initialized
                
                return False
                
        except Exception as e:
            logger.warning(f"检查数据库初始化状态失败: {e}")
            return False
        finally:
            if 'connection' in locals() and connection:
                connection.close()
    
    def _sync_check_database_exists_with_temp_connection(self) -> bool:
        """使用临时连接同步检查数据库是否存在"""
        try:
            # 获取数据库配置
            db_config = self.config_manager.get_database_config()
            database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
            
            # 构建临时数据库URL（不包含数据库名称）
            from sqlalchemy import create_engine, text
            
            # 构建基础URL（不包含数据库名称）
            host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
            port = db_config.get('port', db_config.get('数据库端口', 3306))
            username = db_config.get('username', db_config.get('数据库用户名', 'root'))
            password = db_config.get('password', db_config.get('数据库密码', ''))
            
            # 构建基础连接URL（不包含数据库名称）
            base_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/?charset=utf8mb4"
            
            # 创建临时引擎
            engine = create_engine(base_url)
            
            # 查询所有数据库
            with engine.connect() as conn:
                result = conn.execute(text("SHOW DATABASES"))
                databases = [row[0] for row in result]
            
            # 关闭引擎
            engine.dispose()
            
            return database_name in databases
            
        except Exception as e:
            logger.warning(f"使用临时连接检查数据库存在性失败: {e}")
            return False
    
    def _sync_check_database_exists(self) -> bool:
        """同步检查数据库是否存在"""
        try:
            session = self.database_manager.get_session()
            try:
                result = session.execute(text("SELECT DATABASE()"))
                current_db = result.scalar()
                db_config = self.config_manager.get_database_config()
                session.commit()
                return current_db == db_config.get('database', 'rpl_device')
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"同步检查数据库存在性失败: {e}")
            return False
    
    async def _create_database(self):
        """创建数据库"""
        try:
            # 获取数据库配置
            db_config = self.config_manager.get_database_config()
            database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
            
            # 构建临时数据库URL（不包含数据库名称）
            from sqlalchemy import create_engine, text
            
            # 构建基础URL（不包含数据库名称）
            host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
            port = db_config.get('port', db_config.get('数据库端口', 3306))
            username = db_config.get('username', db_config.get('数据库用户名', 'root'))
            password = db_config.get('password', db_config.get('数据库密码', ''))
            
            # 构建基础连接URL（不包含数据库名称）
            base_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/?charset=utf8mb4"
            
            # 创建临时引擎
            engine = create_engine(base_url)
            
            # 创建数据库
            with engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {database_name} "
                                 f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                conn.commit()
            
            # 关闭引擎
            engine.dispose()
            
            # logger.info(f"数据库 {database_name} 创建成功")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"创建数据库失败: {e}")
            raise
    
    async def _check_and_recreate_partitioned_tables(self):
        """检查表是否为分区表，如果不是则重新创建"""
        # logger.info("开始检查表分区状态...")  # 调试信息已注释
        
        try:
            # 使用同步方式检查表分区状态
            loop = asyncio.get_event_loop()
            need_recreate = await loop.run_in_executor(None, self._sync_check_partitioned_tables)
            
            if need_recreate:
                # logger.info("检测到表需要重新创建为分区表")  # 调试信息已注释
                await loop.run_in_executor(None, self._sync_recreate_partitioned_tables)
            else:
                # logger.info("表分区状态正常，无需重新创建")  # 调试信息已注释
                pass
                
        except Exception as e:
            logger.error(f"检查表分区状态失败: {e}")
            raise

    async def _mark_database_initialized(self):
        """标记数据库已完成初始化"""
        try:
            # 使用同步方式标记数据库初始化完成
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_mark_database_initialized)
        except Exception as e:
            logger.warning(f"标记数据库初始化完成失败: {e}")
    
    def _sync_mark_database_initialized(self):
        """同步标记数据库已完成初始化"""
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 插入或更新初始化标记记录
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description) 
                    VALUES ('database.initialized', 'true', '数据库初始化完成标记')
                    ON DUPLICATE KEY UPDATE config_value = 'true', description = '数据库初始化完成标记'
                """)
                
                connection.commit()
                # logger.info("数据库初始化完成标记已设置")  # 调试信息已注释
                
        except Exception as e:
            logger.error(f"标记数据库初始化完成失败: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
    
    async def _check_and_update_table_structures(self):
        """检查并更新表结构（仅用于已初始化的数据库）"""
        # logger.info("开始检查表结构是否需要更新...")  # 调试信息已注释
        
        try:
            # 检查分区表状态
            await self._check_and_recreate_partitioned_tables()
            
            # 检查分区表结构
            await self._check_and_update_partitioned_table_structures()
            
            # 检查非分区表结构
            await self._check_and_update_non_partitioned_tables()
            
            # logger.info("表结构检查完成")  # 调试信息已注释
            
        except Exception as e:
            logger.warning(f"表结构检查失败: {e}")
            # 不抛出异常，继续执行后续流程
    
    async def _check_and_update_partitioned_table_structures(self):
        """检查并更新分区表的结构"""
        # logger.info("开始检查分区表结构...")  # 调试信息已注释
        
        try:
            # 使用同步方式检查分区表结构
            loop = asyncio.get_event_loop()
            need_update = await loop.run_in_executor(None, self._sync_check_partitioned_table_structures)
            
            if need_update:
                # logger.info("检测到分区表需要更新结构")  # 调试信息已注释
                await loop.run_in_executor(None, self._sync_update_partitioned_table_structures)
            else:
                # logger.info("分区表结构正常，无需更新")  # 调试信息已注释
                pass
                
        except Exception as e:
            logger.error(f"检查分区表结构失败: {e}")
            # 不抛出异常，继续执行后续流程
            logger.warning("分区表结构检查失败，但继续执行后续流程")
    
    def _sync_check_partitioned_table_structures(self):
        """同步检查分区表结构"""
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 需要检查的分区表
                partitioned_tables = ['status_history', 'real_time_data', 'event_records']
                need_update = False
                
                # 获取数据库名称（使用与_create_database_connection相同的键名映射逻辑）
                db_config = self.config_manager.get_database_config()
                database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
                
                for table in partitioned_tables:
                    # 检查表是否存在
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    """, (database_name, table))
                    
                    table_exists = cursor.fetchone()[0] > 0
                    
                    if table_exists:
                        # logger.info(f"表 {table} 存在，检查表结构是否需要更新")  # 调试信息已注释
                        
                        # 检查表结构是否与预期一致
                        if table == 'status_history':
                            # 检查status_history表的关键列是否存在
                            cursor.execute("""
                                SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_schema = %s AND table_name = %s 
                                AND column_name IN ('id', 'record_time', 'timestamp', 'status_type', 'bit_position', 'old_value', 'new_value', 'status_name', 'device_id', 'upload_status', 'upload_time', 'retry_count', 'last_error')
                            """, (database_name, table))
                            
                            key_columns_exist = cursor.fetchone()[0] >= 12  # 至少12个关键列
                            
                            if not key_columns_exist:
                                # logger.info(f"表 {table} 缺少关键列，需要更新结构")  # 调试信息已注释
                                need_update = True
                            else:
                                # logger.info(f"表 {table} 结构正常，无需更新")  # 调试信息已注释
                                pass                        
                        elif table == 'real_time_data':
                            # 检查real_time_data表的关键列是否存在
                            cursor.execute("""
                                SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_schema = %s AND table_name = %s 
                                AND column_name IN ('id', 'timestamp', 'device_id', 'parameter_name', 'value', 'unit', 'upload_status', 'upload_time', 'retry_count', 'last_error')
                            """, (database_name, table))
                            
                            key_columns_exist = cursor.fetchone()[0] >= 10  # 至少10个关键列
                            
                            if not key_columns_exist:
                                # logger.info(f"表 {table} 缺少关键列，需要更新结构")  # 调试信息已注释
                                need_update = True
                            else:
                                # logger.info(f"表 {table} 结构正常，无需更新")  # 调试信息已注释
                                pass                        
                        elif table == 'event_records':
                            # 检查event_records表的关键列是否存在
                            cursor.execute("""
                                SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_schema = %s AND table_name = %s 
                                AND column_name IN ('id', 'event_time', 'event_type', 'device_id', 'description', 'upload_status', 'upload_time', 'retry_count', 'last_error')
                            """, (database_name, table))
                            
                            key_columns_exist = cursor.fetchone()[0] >= 9  # 至少9个关键列
                            
                            if not key_columns_exist:
                                # logger.info(f"表 {table} 缺少关键列，需要更新结构")  # 调试信息已注释
                                need_update = True
                            else:
                                # logger.info(f"表 {table} 结构正常，无需更新")  # 调试信息已注释
                                pass                        
                    else:
                        # logger.info(f"表 {table} 不存在，需要创建")  # 调试信息已注释
                        need_update = True
            
            connection.close()
            return need_update
            
        except Exception as e:
            logger.error(f"检查分区表结构时出错: {e}")
            if 'connection' in locals() and connection:
                connection.close()
            return True  # 出错时默认需要更新
    
    def _sync_update_partitioned_table_structures(self):
        """同步更新分区表结构"""
        # logger.info("开始更新分区表结构...")  # 调试信息已注释
        
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 执行数据库初始化脚本
                # logger.info("执行数据库初始化脚本以更新表结构...")  # 调试信息已注释
                
                # 读取并执行初始化脚本
                init_script_path = os.path.join(os.path.dirname(__file__), 'sql_scripts', 'database_init.sql')
                
                if os.path.exists(init_script_path):
                    with open(init_script_path, 'r', encoding='utf-8') as f:
                        sql_script = f.read()
                    
                    # 使用智能分割SQL语句，处理分区定义中的分号
                sql_statements = self._split_sql_statements(sql_script)
                # logger.info(f"分割SQL语句完成，共 {len(sql_statements)} 条语句")  # 调试信息已注释
                
                for i, statement in enumerate(sql_statements):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            # logger.info(f"正在执行第{i+1}条语句: {statement[:100]}...")  # 调试信息已注释
                            cursor.execute(statement)
                            # logger.info(f"执行第{i+1}条语句成功")  # 调试信息已注释
                        except Exception as e:
                            logger.error(f"执行第{i+1}条语句失败: {e}")
                            logger.error(f"失败语句: {statement}")
                            # 继续执行下一条语句
                else:
                    logger.error(f"数据库初始化脚本不存在: {init_script_path}")
                    raise FileNotFoundError(f"数据库初始化脚本不存在: {init_script_path}")
            
            connection.commit()
            # logger.info("分区表结构更新完成")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"更新分区表结构时出错: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
    
    async def _check_and_update_non_partitioned_tables(self):
        """检查并更新非分区表的结构"""
        # logger.info("开始检查非分区表结构...")  # 调试信息已注释
        
        try:
            # 使用同步方式检查非分区表结构
            loop = asyncio.get_event_loop()
            need_update = await loop.run_in_executor(None, self._sync_check_non_partitioned_tables)
            
            if need_update:
                # logger.info("检测到非分区表需要更新结构")  # 调试信息已注释
                await loop.run_in_executor(None, self._sync_update_non_partitioned_tables)
            else:
                # logger.info("非分区表结构正常，无需更新")  # 调试信息已注释
                pass                        
        except Exception as e:
            logger.error(f"检查非分区表结构失败: {e}")
            # 不抛出异常，继续执行后续流程
            logger.warning("非分区表结构检查失败，但继续执行后续流程")

    def _sync_check_non_partitioned_tables(self):
        """同步检查非分区表结构"""
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 需要检查的非分区表
                non_partitioned_tables = ['user_permissions', 'system_config']
                need_update = False
                
                # 获取数据库名称（使用与_create_database_connection相同的键名映射逻辑）
                db_config = self.config_manager.get_database_config()
                database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
                
                for table in non_partitioned_tables:
                    # 检查表是否存在
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    """, (database_name, table))
                    
                    table_exists = cursor.fetchone()[0] > 0
                    
                    if table_exists:
                        logger.info(f"表 {table} 存在，检查表结构是否需要更新")
                        
                        # 检查表结构是否与预期一致
                        # 这里添加更详细的表结构检查逻辑
                        if table == 'user_permissions':
                            # 检查user_permissions表的关键列是否存在
                            cursor.execute("""
                                SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_schema = %s AND table_name = %s 
                                AND column_name IN ('id', 'username', 'password_hash', 'role', 'is_active')
                            """, (database_name, table))
                            
                            key_columns_exist = cursor.fetchone()[0] >= 5  # 至少5个关键列
                            
                            if not key_columns_exist:
                                logger.info(f"表 {table} 缺少关键列，需要更新结构")
                                need_update = True
                            else:
                                logger.info(f"表 {table} 结构正常，无需更新")
                                pass
                        
                        elif table == 'system_config':
                            # 检查system_config表的关键列是否存在
                            cursor.execute("""
                                SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_schema = %s AND table_name = %s 
                                AND column_name IN ('id', 'config_key', 'config_value', 'description', 'is_active')
                            """, (database_name, table))
                            
                            key_columns_exist = cursor.fetchone()[0] >= 5  # 至少5个关键列
                            
                            if not key_columns_exist:
                                logger.info(f"表 {table} 缺少关键列，需要更新结构")
                                need_update = True
                            else:
                                logger.info(f"表 {table} 结构正常，无需更新")
                    else:
                        logger.info(f"表 {table} 不存在，需要创建")
                        need_update = True
            
            connection.close()
            return need_update
            
        except Exception as e:
            logger.error(f"检查非分区表结构时出错: {e}")
            if 'connection' in locals() and connection:
                connection.close()
            return True  # 出错时默认需要更新

    def _sync_update_non_partitioned_tables(self):
        """同步更新非分区表结构"""
        # logger.info("开始更新非分区表结构...")  # 调试信息已注释
        
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 重新创建用户权限表
                # logger.info("重新创建 user_permissions 表...")  # 调试信息已注释
                cursor.execute("DROP TABLE IF EXISTS user_permissions")
                
                create_table_sql = """
                CREATE TABLE user_permissions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
                    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
                    role ENUM('admin', 'operator', 'viewer') DEFAULT 'viewer' COMMENT '用户角色',
                    permissions JSON COMMENT '权限配置',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                    last_login DATETIME COMMENT '最后登录时间',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_username (username),
                    INDEX idx_role (role),
                    INDEX idx_is_active (is_active)
                ) COMMENT='用户权限表';
                """
                cursor.execute(create_table_sql)
                # logger.info("user_permissions 表创建成功")  # 调试信息已注释
                
                # 重新创建系统配置表
                # logger.info("重新创建 system_config 表...")  # 调试信息已注释
                cursor.execute("DROP TABLE IF EXISTS system_config")
                
                create_table_sql = """
                CREATE TABLE system_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
                    config_value JSON COMMENT '配置值',
                    description TEXT COMMENT '配置描述',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_config_key (config_key),
                    INDEX idx_is_active (is_active)
                ) COMMENT='系统配置表';
                """
                cursor.execute(create_table_sql)
        # logger.info("system_config 表创建成功")  # 调试信息已注释
            
            connection.commit()
            # logger.info("非分区表结构更新完成")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"更新非分区表结构时出错: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()

    def _sync_check_partitioned_tables(self):
        """同步检查表是否为分区表"""
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 检查需要分区的表
                partitioned_tables = ['status_history', 'real_time_data', 'event_records']
                need_recreate = False
                
                # 获取数据库名称（使用与_create_database_connection相同的键名映射逻辑）
                db_config = self.config_manager.get_database_config()
                database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
                
                for table in partitioned_tables:
                    # 检查表是否存在
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    """, (database_name, table))
                    
                    table_exists = cursor.fetchone()[0] > 0
                    
                    if table_exists:
                        # 检查表是否为分区表
                        cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.partitions 
                            WHERE table_schema = %s AND table_name = %s 
                            AND partition_name IS NOT NULL
                        """, (database_name, table))
                        
                        is_partitioned = cursor.fetchone()[0] > 0
                        
                        if not is_partitioned:
                            logger.warning(f"表 {table} 存在但不是分区表，需要重新创建")
                            need_recreate = True
                    else:
                        logger.info(f"表 {table} 不存在，将正常创建")
        
            connection.close()
            return need_recreate
            
        except Exception as e:
            logger.error(f"检查表分区状态时出错: {e}")
            if 'connection' in locals() and connection:
                connection.close()
            return True  # 出错时默认需要重新创建
    
    def _sync_recreate_partitioned_tables(self):
        """同步重新创建分区表"""
        logger.info("开始重新创建分区表...")
        
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 获取当前年份和月份
                cursor.execute("SELECT YEAR(CURDATE()), MONTH(CURDATE())")
                current_year, current_month = cursor.fetchone()
                logger.info(f"当前年份: {current_year}, 当前月份: {current_month}")
                
                # 计算未来几个月的分区
                partitions = []
                for i in range(13):  # 创建未来12个月的分区
                    year = current_year
                    month = current_month + i
                    
                    if month > 12:
                        month = month - 12
                        year = current_year + 1
                    
                    partitions.append((year, month))
                
                logger.info(f"将创建 {len(partitions)} 个月的分区")
                
                # 读取数据库初始化脚本
                init_script_path = self.sql_scripts_path / "database_init.sql"
                if not init_script_path.exists():
                    logger.error("数据库初始化脚本不存在，无法重新创建表结构")
                    return
                
                with open(init_script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # 分割SQL语句
                statements = self._split_sql_statements(sql_script)
                
                # 执行表创建语句
                for statement in statements:
                    if statement.strip() and not statement.strip().startswith('--'):
                        # 检查是否是创建表的语句
                        if 'CREATE TABLE' in statement.upper():
                            table_name = self._extract_table_name(statement)
                            if table_name in ['status_history', 'real_time_data', 'event_records']:
                                logger.info(f"重新创建表 {table_name}...")
                                
                                # 删除现有表
                                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                                
                                # 修改CREATE TABLE语句，添加分区定义
                                modified_statement = self._add_partition_to_create_table(statement, partitions)
                                
                                try:
                                    cursor.execute(modified_statement)
                                    logger.info(f"表 {table_name} 创建成功")
                                except Exception as e:
                                    logger.error(f"创建表 {table_name} 失败: {e}")
                                    logger.error(f"失败语句: {modified_statement[:200]}")
            
            connection.commit()
            logger.info("分区表重新创建完成")
            
        except Exception as e:
            logger.error(f"重新创建分区表时出错: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()

    def _extract_table_name(self, create_table_statement):
        """从CREATE TABLE语句中提取表名"""
        import re
        # 匹配CREATE TABLE后面的表名
        match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([^`\s(]+)`?', create_table_statement, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _add_partition_to_create_table(self, create_table_statement, partitions):
        """在CREATE TABLE语句中添加分区定义"""
        # 移除末尾的分号（如果有）
        statement = create_table_statement.rstrip().rstrip(';')
        
        # 添加分区定义
        statement += "\nPARTITION BY RANGE (TO_DAYS(timestamp)) (\n"
        
        # 添加分区定义
        for i, (year, month) in enumerate(partitions):
            next_year = year
            next_month = month + 1
            if next_month > 12:
                next_month = 1
                next_year = year + 1
            
            partition_name = f"p{year}_{month:02d}"
            partition_value = f"TO_DAYS('{next_year}-{next_month:02d}-01')"
            
            if i == len(partitions) - 1:
                statement += f"    PARTITION {partition_name} VALUES LESS THAN ({partition_value})\n"
            else:
                statement += f"    PARTITION {partition_name} VALUES LESS THAN ({partition_value}),\n"
        
        statement += ")"
        
        return statement

    async def _execute_init_scripts(self, force_recreate=False):
        """执行数据库初始化脚本
        
        Args:
            force_recreate: 是否强制重新创建表结构
        """
        init_script_path = self.sql_scripts_path / "database_init.sql"
        
        if not init_script_path.exists():
            logger.warning("数据库初始化脚本不存在，跳过执行")
            return
        
        try:
            if force_recreate:
                # 强制重新创建分区表结构
                logger.info("强制重新创建分区表结构...")
                await self._force_recreate_partitioned_tables()
            else:
                # 先检查表是否为分区表，如果不是则重新创建
                await self._check_and_recreate_partitioned_tables()
            
            # 检查并更新非分区表的结构
            await self._check_and_update_non_partitioned_tables()
            
            with open(init_script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # 使用智能分割SQL语句，处理分区定义中的分号
            statements = self._split_sql_statements(sql_script)
            # logger.info(f"分割SQL语句完成，共 {len(statements)} 条语句")  # 调试信息已注释
            
            # 使用同步方式执行SQL脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_execute_init_scripts, statements)
            
        except Exception as e:
            logger.error(f"执行数据库初始化脚本失败: {e}")
            raise
    
    def _sync_execute_init_scripts(self, statements):
        """同步执行数据库初始化脚本"""
        logger.info(f"开始执行数据库初始化脚本，共{len(statements)}条语句")
        
        # 使用统一的数据库连接方法
        try:
            connection = self._create_database_connection()
            
            # logger.info("数据库连接成功")  # 调试信息已注释
            
            with connection.cursor() as cursor:
                for i, statement in enumerate(statements):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            # logger.info(f"正在执行第{i+1}条语句: {statement[:100]}...")  # 调试信息已注释
                            cursor.execute(statement)
                            # logger.info(f"执行第{i+1}条语句成功")  # 调试信息已注释
                        except Exception as e:
                            logger.error(f"执行第{i+1}条语句失败: {e}")
                            logger.error(f"失败语句: {statement}")
                            # 继续执行下一条语句
                            continue
            
            connection.commit()
            
        except Exception as e:
            logger.error(f"执行数据库初始化脚本时发生错误: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
    
    async def _execute_partition_scripts(self):
        """执行分区管理脚本"""
        partition_script_path = self.sql_scripts_path / "partition_management.sql"
        
        logger.info(f"检查分区管理脚本路径: {partition_script_path}")
        
        if not partition_script_path.exists():
            logger.warning("分区管理脚本不存在，跳过执行")
            return
        
        logger.info("分区管理脚本存在，开始执行")
        
        try:
            with open(partition_script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            logger.info(f"读取分区管理脚本成功，脚本长度: {len(sql_script)} 字符")
            
            # 使用智能分割SQL语句，处理存储过程分隔符
            statements = self._split_sql_statements(sql_script)
            logger.info(f"分割SQL语句完成，共 {len(statements)} 条语句")
            
            # 使用同步方式执行SQL脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_execute_partition_scripts, statements)
            
            logger.info("分区管理脚本执行完成")
            
        except Exception as e:
            logger.error(f"执行分区管理脚本失败: {e}")
            # 不抛出异常，继续执行后续流程
            logger.warning("分区管理脚本执行失败，但继续执行后续流程")
            
        # 尝试调用分区管理存储过程来创建分区
        try:
            logger.info("开始调用分区管理存储过程...")
            await self._call_partition_management_procedure()
            logger.info("分区管理存储过程调用完成")
        except Exception as e:
            logger.warning(f"调用分区管理存储过程失败: {e}")
            logger.info("存储过程调用失败，但继续执行后续流程")
    
    def _sync_execute_partition_scripts(self, statements):
        """同步执行分区管理脚本"""
        logger.info(f"开始执行分区管理脚本，共{len(statements)}条语句")
        
        # 获取数据库配置
        db_config = self.config_manager.get_database_config()
        
        # 处理中文键名映射到英文键名
        host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
        port = db_config.get('port', db_config.get('数据库端口', 3306))
        username = db_config.get('username', db_config.get('数据库用户名', 'root'))
        password = db_config.get('password', db_config.get('数据库密码', ''))
        database = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
        
        # logger.info(f"数据库配置: host={host}, port={port}, database={database}")  # 调试信息已注释
        
        try:
            # 连接数据库
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                charset='utf8mb4'
            )
            
            logger.info("数据库连接成功")
            
            with connection.cursor() as cursor:
                for i, statement in enumerate(statements):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            logger.info(f"正在执行第{i+1}条语句: {statement[:100]}...")
                            cursor.execute(statement)
                            logger.info(f"执行第{i+1}条语句成功")
                        except Exception as e:
                            logger.error(f"执行分区管理脚本时发生错误: {e}")
                            logger.error(f"失败语句: {statement}")
                            # 继续执行下一条语句
                            continue
            
            connection.commit()
            
        except Exception as e:
            logger.error(f"执行分区管理脚本时发生错误: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
    
    async def _execute_scheduler_scripts(self):
        """执行事件调度器脚本"""
        scheduler_script_path = self.sql_scripts_path / "event_scheduler.sql"
        
        if not scheduler_script_path.exists():
            logger.warning("事件调度器脚本不存在，跳过执行")
            return
        
        try:
            with open(scheduler_script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # 使用更智能的SQL语句分割，处理事件定义中的分号
            statements = self._split_sql_statements(sql_script)
            
            # 使用同步方式执行SQL脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_execute_scheduler_scripts, statements)
            
        except Exception as e:
            logger.error(f"执行事件调度器脚本失败: {e}")
            raise
    
    def _split_sql_statements(self, sql_script):
        """智能分割SQL语句，处理DELIMITER语句和存储过程分隔符"""
        statements = []
        current_statement = ""
        delimiter = ';'  # 默认分隔符
        
        for line in sql_script.split('\n'):
            line = line.strip()
            
            # 检查DELIMITER语句
            if line.upper().startswith('DELIMITER '):
                # 保存当前语句（如果有）
                if current_statement.strip():
                    statements.append(current_statement.strip())
                    current_statement = ""
                
                # 更新分隔符
                parts = line.split()
                if len(parts) >= 2:
                    delimiter = parts[1]
                
                # DELIMITER语句本身不执行
                continue
            
            # 检查是否是单行注释（只检查当前行，不检查整个语句）
            if line.startswith('--'):
                # 单行注释，不添加到语句中
                continue
            
            # 添加当前行到语句中
            if current_statement:
                current_statement += '\n' + line
            else:
                current_statement = line
            
            # 检查是否结束语句（使用当前分隔符）
            if line.endswith(delimiter):
                # 移除分隔符
                current_statement = current_statement[:-len(delimiter)].strip()
                
                # 保存语句
                if current_statement.strip():
                    statements.append(current_statement.strip())
                
                current_statement = ""
        
        # 添加最后一个语句（如果没有分隔符结尾）
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements

    async def _call_partition_management_procedure(self):
        """调用分区管理存储过程来创建分区"""
        logger.info("开始异步调用分区管理存储过程")
        try:
            # 使用同步方式调用存储过程
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_call_partition_management_procedure)
            
            logger.info("分区管理存储过程调用完成")
            
        except Exception as e:
            logger.error(f"调用分区管理存储过程失败: {e}")
            raise

    def _sync_call_partition_management_procedure(self):
        """同步调用分区管理存储过程"""
        logger.info("开始调用分区管理存储过程...")
        
        # 获取数据库配置
        db_config = self.config_manager.get_database_config()
        
        # 处理中文键名映射到英文键名
        host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
        port = db_config.get('port', db_config.get('数据库端口', 3306))
        username = db_config.get('username', db_config.get('数据库用户名', 'root'))
        password = db_config.get('password', db_config.get('数据库密码', ''))
        database = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
        
        logger.info(f"存储过程调用数据库配置: host={host}, database={database}")
        
        try:
            # 连接数据库
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                charset='utf8mb4'
            )
            
            logger.info("存储过程调用数据库连接成功")
            
            with connection.cursor() as cursor:
                # 调用存储过程
                logger.info("正在调用存储过程: manage_all_partitions")
                cursor.callproc('manage_all_partitions')
                logger.info("分区管理存储过程调用成功")
            
            connection.commit()
            logger.info("存储过程调用事务已提交")
            
        except Exception as e:
            logger.error(f"调用分区管理存储过程失败: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
                logger.info("存储过程调用数据库连接已关闭")

    async def _force_recreate_partitioned_tables(self):
        """强制重新创建分区表结构"""
        # logger.info("开始强制重新创建分区表结构...")  # 调试信息已注释
        
        try:
            # 使用同步方式强制重新创建分区表
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_force_recreate_partitioned_tables)
            
            logger.info("分区表结构强制重新创建完成")
            
        except Exception as e:
            logger.error(f"强制重新创建分区表结构失败: {e}")
            raise

    def _sync_force_recreate_partitioned_tables(self):
        """同步强制重新创建分区表结构"""
        logger.info("开始同步强制重新创建分区表结构...")
        
        try:
            # 使用统一的数据库连接方法
            connection = self._create_database_connection()
            
            with connection.cursor() as cursor:
                # 获取当前年份和月份
                cursor.execute("SELECT YEAR(CURDATE()), MONTH(CURDATE())")
                current_year, current_month = cursor.fetchone()
                logger.info(f"当前年份: {current_year}, 当前月份: {current_month}")
                
                # 计算未来几个月的分区
                partitions = []
                for i in range(13):  # 创建未来12个月的分区
                    year = current_year
                    month = current_month + i
                    
                    if month > 12:
                        month = month - 12
                        year = current_year + 1
                    
                    partitions.append((year, month))
                
                logger.info(f"将创建 {len(partitions)} 个月的分区")
                
                # 读取数据库初始化脚本
                init_script_path = self.sql_scripts_path / "database_init.sql"
                if not init_script_path.exists():
                    logger.error("数据库初始化脚本不存在，无法重新创建表结构")
                    return
                
                with open(init_script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # 分割SQL语句
                statements = self._split_sql_statements(sql_script)
                
                # 执行表创建语句
                for statement in statements:
                    if statement.strip() and not statement.strip().startswith('--'):
                        # 检查是否是创建表的语句
                        if 'CREATE TABLE' in statement.upper():
                            table_name = self._extract_table_name(statement)
                            if table_name in ['status_history', 'real_time_data', 'event_records']:
                                logger.info(f"强制重新创建表 {table_name}...")
                                
                                # 删除现有表
                                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                                
                                # 修改CREATE TABLE语句，添加分区定义
                                modified_statement = self._add_partition_to_create_table(statement, partitions)
                                
                                try:
                                    cursor.execute(modified_statement)
                                    logger.info(f"表 {table_name} 强制重新创建成功")
                                except Exception as e:
                                    logger.error(f"强制重新创建表 {table_name} 失败: {e}")
                                    logger.error(f"失败语句: {modified_statement[:200]}")
            
            connection.commit()
            logger.info("分区表结构强制重新创建完成")
            
        except Exception as e:
            logger.error(f"同步强制重新创建分区表结构时出错: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()

    async def _force_recreate_procedures_and_events(self):
        """强制重新创建存储过程和事件调度器"""
        # logger.info("开始强制重新创建存储过程和事件调度器...")  # 调试信息已注释
        
        try:
            # 首先执行完整的分区管理脚本，创建所有存储过程
            await self._execute_partition_scripts()
            
            # 强制重新创建存储过程（确保关键存储过程存在）
            await self._execute_partition_scripts_with_force()
            
            # 强制重新创建事件调度器
            await self._execute_scheduler_scripts_with_force()
            
            # logger.info("存储过程和事件调度器强制重新创建完成")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"强制重新创建存储过程和事件调度器失败: {e}")
            raise

    async def _execute_partition_scripts_with_force(self):
        """强制重新创建分区管理存储过程"""
        partition_script_path = self.sql_scripts_path / "partition_management.sql"
        
        if not partition_script_path.exists():
            logger.warning("分区管理脚本不存在，跳过执行")
            return
        
        # logger.info("强制重新创建分区管理存储过程...")  # 调试信息已注释
        
        try:
            with open(partition_script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # 使用智能分割SQL语句，处理存储过程分隔符
            statements = self._split_sql_statements(sql_script)
            logger.info(f"分割SQL语句完成，共 {len(statements)} 条语句")
            
            # 使用同步方式执行SQL脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_execute_partition_scripts_with_force, statements)
            
        except Exception as e:
            logger.error(f"强制重新创建分区管理存储过程失败: {e}")
            raise

    def _sync_execute_partition_scripts_with_force(self, statements):
        """同步强制重新创建分区管理存储过程"""
        # logger.info(f"开始强制重新创建分区管理存储过程，共{len(statements)}条语句")  # 调试信息已注释
        
        # 获取数据库配置
        db_config = self.config_manager.get_database_config()
        
        # 处理中文键名映射到英文键名
        host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
        port = db_config.get('port', db_config.get('数据库端口', 3306))
        username = db_config.get('username', db_config.get('数据库用户名', 'root'))
        password = db_config.get('password', db_config.get('数据库密码', ''))
        database = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
        
        logger.info(f"数据库配置: host={host}, port={port}, database={database}")
        
        try:
            # 连接数据库
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                charset='utf8mb4'
            )
            
            logger.info("数据库连接成功")
            
            with connection.cursor() as cursor:
                # 先删除所有现有的存储过程
                # logger.info("删除现有存储过程...")  # 调试信息已注释
                cursor.execute("DROP PROCEDURE IF EXISTS manage_all_partitions")
                cursor.execute("DROP PROCEDURE IF EXISTS manage_status_history_partitions")
                cursor.execute("DROP PROCEDURE IF EXISTS manage_real_time_data_partitions")
                cursor.execute("DROP PROCEDURE IF EXISTS manage_event_records_partitions")
                cursor.execute("DROP PROCEDURE IF EXISTS simple_drop_old_partitions")
                # logger.info("现有存储过程删除完成")  # 调试信息已注释
                
                # 执行完整的分区管理脚本中的所有语句
                # logger.info("开始执行完整的分区管理脚本...")  # 调试信息已注释
                for i, statement in enumerate(statements):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            logger.info(f"正在执行第{i+1}条语句: {statement[:100]}...")
                            cursor.execute(statement)
                            logger.info(f"执行第{i+1}条语句成功")
                        except Exception as e:
                            logger.error(f"执行分区管理脚本时发生错误: {e}")
                            logger.error(f"失败语句: {statement}")
                            # 继续执行下一条语句
                            continue
            
            connection.commit()
            # logger.info("分区管理存储过程强制重新创建完成")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"强制重新创建分区管理存储过程时发生错误: {e}")
            raise
        finally:
            if 'connection' in locals() and connection:
                connection.close()
                # logger.info("数据库连接已关闭")  # 调试信息已注释

    async def _execute_scheduler_scripts_with_force(self):
        """强制重新创建事件调度器"""
        scheduler_script_path = self.sql_scripts_path / "event_scheduler.sql"
        
        if not scheduler_script_path.exists():
            logger.warning("事件调度器脚本不存在，跳过执行")
            return
        
        # logger.info("强制重新创建事件调度器...")  # 调试信息已注释
        
        try:
            with open(scheduler_script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # 使用更智能的SQL语句分割，处理事件定义中的分号
            statements = self._split_sql_statements(sql_script)
            
            # 使用同步方式执行SQL脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_execute_scheduler_scripts_with_force, statements)
            
        except Exception as e:
            logger.error(f"强制重新创建事件调度器失败: {e}")
            raise

    def _sync_execute_scheduler_scripts_with_force(self, statements):
        """同步强制重新创建事件调度器"""
        # 使用pymysql直接执行SQL脚本
        try:
            # 获取数据库配置
            db_config = self.config_manager.get_database_config()
            database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
            host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
            port = db_config.get('port', db_config.get('数据库端口', 3306))
            username = db_config.get('username', db_config.get('数据库用户名', 'root'))
            password = db_config.get('password', db_config.get('数据库密码', ''))
            
            # 连接数据库
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database_name,
                charset='utf8mb4'
            )
            
            # logger.info(f"开始强制重新创建事件调度器，共 {len(statements)} 条语句")  # 调试信息已注释
            
            with connection.cursor() as cursor:
                # 先删除所有现有的事件
                # logger.info("删除现有事件...")  # 调试信息已注释
                cursor.execute("DROP EVENT IF EXISTS daily_partition_management")
                cursor.execute("DROP EVENT IF EXISTS weekly_data_statistics")
                cursor.execute("DROP EVENT IF EXISTS monthly_data_cleanup")
                cursor.execute("DROP EVENT IF EXISTS database_optimization")
                # logger.info("现有事件删除完成")  # 调试信息已注释
                
                # 重新创建事件
                for i, statement in enumerate(statements):
                    if statement:
                        try:
                            # logger.info(f"执行第 {i+1} 条语句: {statement[:100]}...")  # 调试信息已注释
                            cursor.execute(statement)
                            # logger.info(f"第 {i+1} 条语句执行成功")  # 调试信息已注释
                        except Exception as e:
                            logger.error(f"执行事件调度器语句失败: {statement[:100]}... 错误: {e}")
                            # 继续执行下一条语句
                            continue
            
            connection.commit()
            # logger.info("事件调度器强制重新创建完成")  # 调试信息已注释
            
        except Exception as e:
            logger.error(f"强制重新创建事件调度器失败: {e}")
            raise

    def _sync_execute_scheduler_scripts(self, statements):
        """同步执行事件调度器脚本"""
        # 使用pymysql直接执行SQL脚本
        try:
            # 获取数据库配置
            db_config = self.config_manager.get_database_config()
            database_name = db_config.get('database', db_config.get('数据库名称', 'rpldevice'))
            host = db_config.get('host', db_config.get('数据库地址', '127.0.0.1'))
            port = db_config.get('port', db_config.get('数据库端口', 3306))
            username = db_config.get('username', db_config.get('数据库用户名', 'root'))
            password = db_config.get('password', db_config.get('数据库密码', ''))
            
            # 连接数据库
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database_name,
                charset='utf8mb4'
            )
            
            # logger.info(f"开始执行事件调度器脚本，共 {len(statements)} 条语句")  # 调试信息已注释
            
            with connection.cursor() as cursor:
                for i, statement in enumerate(statements):
                    if statement:
                        try:
                            # logger.info(f"执行第 {i+1} 条语句: {statement[:100]}...")  # 调试信息已注释
                            cursor.execute(statement)
                            # logger.info(f"第 {i+1} 条语句执行成功")  # 调试信息已注释
                        except Exception as e:
                            logger.error(f"执行事件调度器语句失败: {statement[:100]}... 错误: {e}")
                            # 继续执行下一条语句
                            continue
            
            connection.commit()
            logger.info("事件调度器脚本执行完成")
            connection.close()
            
        except Exception as e:
            logger.error(f"执行事件调度器脚本失败: {e}")
            raise
    
    def _create_database_connection(self):
        """创建数据库连接"""
        try:
            # 获取数据库配置
            db_config = self.config_manager.get_database_config()
            
            # 处理中文键名到英文键名的映射
            config_map = {
                'host': db_config.get('host', db_config.get('数据库地址', '127.0.0.1')),
                'port': db_config.get('port', db_config.get('数据库端口', 3306)),
                'user': db_config.get('username', db_config.get('数据库用户名', 'root')),
                'password': db_config.get('password', db_config.get('数据库密码', '')),
                'database': db_config.get('database', db_config.get('数据库名称', 'rpldevice')),
                'charset': 'utf8mb4'
            }
            
            # 创建数据库连接
            connection = pymysql.connect(**config_map)
            logger.info("数据库连接创建成功")
            return connection
            
        except Exception as e:
            logger.error(f"创建数据库连接失败: {e}")
            raise

    async def close(self):
        """关闭数据库连接"""
        if self.database_manager:
            await self.database_manager.close()


async def main():
    """测试数据库初始化"""
    from config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    initializer = DatabaseInitializer(config_manager)
    
    try:
        success = await initializer.initialize_database()
        if success:
            print("数据库初始化成功")
        else:
            print("数据库初始化失败")
    finally:
        await initializer.close()


if __name__ == "__main__":
    asyncio.run(main())
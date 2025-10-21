# flake8: noqa
"""
数据库备份和恢复管理器
负责数据库的备份、恢复和验证
"""

import asyncio
import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from .database_manager import DatabaseManager
from .database_config import DatabaseConfigManager

logger = logging.getLogger(__name__)


class BackupManager:
    """数据库备份管理器"""
    
    def __init__(self, config_manager):
        """
        初始化备份管理器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.database_manager: Optional[DatabaseManager] = None
        self.backup_path = Path("./backups")
        self.backup_path.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """初始化备份管理器"""
        try:
            self.database_manager = DatabaseManager(self.config_manager)
            await self.database_manager.initialize()
            return True
        except Exception as e:
            logger.error(f"备份管理器初始化失败: {e}")
            return False
    
    async def create_backup(self, backup_name: Optional[str] = None) -> Optional[Path]:
        """
        创建数据库备份
        
        Args:
            backup_name: 备份文件名，如果为None则自动生成
            
        Returns:
            Path: 备份文件路径，如果失败返回None
        """
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"rpl_device_backup_{timestamp}.sql"
        
        backup_file = self.backup_path / backup_name
        
        try:
            config = self.database_manager.config
            
            # 使用mysqldump创建备份
            cmd = [
                "mysqldump",
                f"--host={config.host}",
                f"--port={config.port}",
                f"--user={config.username}",
                f"--password={config.password}",
                "--single-transaction",
                "--routines",
                "--triggers",
                "--events",
                config.database
            ]
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"备份失败: {result.stderr}")
                backup_file.unlink(missing_ok=True)
                return None
            
            # 压缩备份文件
            compressed_file = await self._compress_backup(backup_file)
            
            # logger.info(f"数据库备份创建成功: {compressed_file}")  # 调试信息已注释
            return compressed_file
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            backup_file.unlink(missing_ok=True)
            return None
    
    async def _compress_backup(self, backup_file: Path) -> Path:
        """压缩备份文件"""
        # logger.info(f"开始压缩备份文件: {backup_file}")  # 调试信息已注释 
        compressed_file = backup_file.with_suffix('.sql.gz')
        
        try:
            import gzip
            
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 删除原始备份文件
            backup_file.unlink()
            
            return compressed_file
            
        except Exception as e:
            logger.error(f"压缩备份文件失败: {e}")
            return backup_file
    
    async def restore_backup(self, backup_file: Path) -> bool:
        """
        从备份文件恢复数据库
        
        Args:
            backup_file: 备份文件路径
            
        Returns:
            bool: 恢复是否成功
        """
        if not backup_file.exists():
            logger.error(f"备份文件不存在: {backup_file}")
            return False
        
        try:
            config = self.database_manager.config
            
            # 如果是压缩文件，先解压
            if backup_file.suffix == '.gz':
                backup_file = await self._decompress_backup(backup_file)
            
            # 使用mysql命令恢复
            cmd = [
                "mysql",
                f"--host={config.host}",
                f"--port={config.port}",
                f"--user={config.username}",
                f"--password={config.password}",
                config.database
            ]
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"恢复失败: {result.stderr}")
                return False
            
            # logger.info("数据库恢复成功")  # 调试信息已注释
            return True
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False
    
    async def _decompress_backup(self, backup_file: Path) -> Path:
        """解压备份文件"""
        decompressed_file = backup_file.with_suffix('')  # 移除.gz后缀
        
        try:
            import gzip
            
            with gzip.open(backup_file, 'rb') as f_in:
                with open(decompressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return decompressed_file
            
        except Exception as e:
            logger.error(f"解压备份文件失败: {e}")
            return backup_file
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        列出所有备份文件
        
        Returns:
            List[Dict]: 备份文件信息列表
        """
        backups = []
        
        for file_path in self.backup_path.glob("*.sql*"):
            stat = file_path.stat()
            backups.append({
                "name": file_path.name,
                "size": stat.st_size,
                "created_time": datetime.fromtimestamp(stat.st_ctime),
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "is_compressed": file_path.suffix == '.gz'
            })
        
        # 按修改时间排序
        backups.sort(key=lambda x: x["modified_time"], reverse=True)
        
        return backups
    
    async def cleanup_old_backups(self, retention_days: int = 7) -> int:
        """
        清理过期备份文件
        
        Args:
            retention_days: 保留天数
            
        Returns:
            int: 删除的文件数量
        """
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for file_path in self.backup_path.glob("*.sql*"):
            modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            if modified_time < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    # logger.info(f"删除过期备份: {file_path.name}")  # 调试信息已注释
                except Exception as e:
                    logger.error(f"删除备份文件失败 {file_path.name}: {e}")
        
        return deleted_count
    
    async def verify_backup(self, backup_file: Path) -> bool:
        """
        验证备份文件完整性
        
        Args:
            backup_file: 备份文件路径
            
        Returns:
            bool: 备份文件是否有效
        """
        if not backup_file.exists():
            return False
        
        try:
            # 检查文件大小
            if backup_file.stat().st_size == 0:
                return False
            
            # 如果是压缩文件，检查是否可以解压
            if backup_file.suffix == '.gz':
                import gzip
                with gzip.open(backup_file, 'rb') as f:
                    # 尝试读取文件头
                    header = f.read(100)
                    if not header:
                        return False
            
            return True
            
        except Exception:
            return False
    
    async def get_backup_status(self) -> Dict[str, Any]:
        """获取备份状态信息"""
        backups = await self.list_backups()
        
        return {
            "total_backups": len(backups),
            "total_size": sum(b["size"] for b in backups),
            "latest_backup": backups[0] if backups else None,
            "backup_path": str(self.backup_path.absolute())
        }
    
    async def close(self):
        """关闭数据库连接"""
        if self.database_manager:
            await self.database_manager.close()


async def main():
    """测试备份管理器"""
    from config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    backup_manager = BackupManager(config_manager)
    
    try:
        if await backup_manager.initialize():
            # 创建备份
            backup_file = await backup_manager.create_backup()
            if backup_file:
                # print(f"备份创建成功: {backup_file}")  # 调试信息已注释
                pass
            
            # 列出备份
            backups = await backup_manager.list_backups()
            # print(f"备份文件数量: {len(backups)}")  # 调试信息已注释
            
            # 验证备份
            if backup_file:
                is_valid = await backup_manager.verify_backup(backup_file)
                # print(f"备份文件验证: {'有效' if is_valid else '无效'}")  # 调试信息已注释
        else:
            # print("备份管理器初始化失败")  # 调试信息已注释
            pass
            pass
    finally:
        await backup_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
"""
数据库功能测试脚本
测试数据库连接、模型操作、异步处理等功能
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager
from database.async_processor import AsyncDataProcessor
from database.database_initializer import DatabaseInitializer
from database.database_api import DatabaseAPI
from database.models import StatusHistory, RealTimeData, EventRecords
from config.config_manager import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseTester:
    """数据库测试器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.database_manager = None
        self.async_processor = None
        self.database_initializer = None
        self.database_api = None
    
    async def setup(self):
        """设置测试环境"""
        logger.info("开始设置测试环境...")
        
        # 加载配置
        await self.config_manager.load_config()
        
        # 初始化数据库
        self.database_initializer = DatabaseInitializer(self.config_manager)
        success = await self.database_initializer.initialize_database()
        
        if not success:
            logger.error("数据库初始化失败")
            return False
        
        # 创建数据库管理器
        self.database_manager = DatabaseManager(self.config_manager)
        await self.database_manager.initialize()
        
        # 创建异步处理器
        self.async_processor = AsyncDataProcessor(self.database_manager)
        await self.async_processor.start()
        
        # 创建数据库API
        self.database_api = DatabaseAPI(self.database_manager)
        
        logger.info("测试环境设置完成")
        return True
    
    async def test_database_connection(self):
        """测试数据库连接"""
        logger.info("测试数据库连接...")
        
        try:
            status = self.database_manager.get_database_status()
            logger.info(f"数据库连接状态: {status}")
            
            if status["is_connected"]:
                logger.info("数据库连接测试通过")
                return True
            else:
                logger.error("数据库连接测试失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库连接测试异常: {e}")
            return False
    
    async def test_async_processor(self):
        """测试异步处理器"""
        logger.info("测试异步处理器...")
        
        try:
            # 测试状态历史数据
            await self.async_processor.queue_status_data(
                device_id="test_device_001",
                status_data={
                    "status": "RUNNING",
                    "value": 100.5,
                    "unit": "RPM",
                    "description": "测试设备运行状态"
                }
            )
            
            # 测试实时数据
            await self.async_processor.queue_real_time_data(
                device_id="test_device_001",
                real_time_data={
                    "data_type": "temperature",
                    "value": 25.3,
                    "unit": "°C",
                    "quality": 95
                }
            )
            
            # 测试事件记录
            await self.async_processor.queue_event_data(
                device_id="test_device_001",
                event_data={"event_type": "TEST_EVENT", "data": {"test": "value"}, "severity": "INFO"}
            )
            
            # 等待数据处理
            await asyncio.sleep(2)
            
            # 检查处理器状态
            status = self.async_processor.get_processor_status()
            logger.info(f"异步处理器状态: {status}")
            
            # 检查是否有数据被处理（通过队列大小或缓冲区大小判断）
            if (status["queue_sizes"]["status_queue"] == 0 and 
                status["queue_sizes"]["real_time_queue"] == 0 and 
                status["queue_sizes"]["event_queue"] == 0):
                logger.info("异步处理器测试通过")
                return True
            else:
                logger.error("异步处理器测试失败")
                return False
                
        except Exception as e:
            logger.error(f"异步处理器测试异常: {e}")
            return False
    
    async def test_database_api(self):
        """测试数据库API"""
        logger.info("测试数据库API...")
        
        try:
            # 测试获取设备列表
            devices = await self.database_api.get_device_list()
            logger.info(f"设备列表: {devices}")
            
            # 测试获取统计信息
            stats = await self.database_api.get_statistics()
            logger.info(f"统计信息: {stats}")
            
            # 测试获取状态历史数据
            status_history = await self.database_api.get_status_history(
                device_id="test_device_001",
                limit=10
            )
            logger.info(f"状态历史数据数量: {len(status_history)}")
            
            # 测试获取实时数据
            real_time_data = await self.database_api.get_real_time_data(
                device_id="test_device_001",
                limit=10
            )
            logger.info(f"实时数据数量: {len(real_time_data)}")
            
            # 测试获取事件记录
            event_records = await self.database_api.get_event_records(
                event_type="TEST_EVENT",
                limit=10
            )
            logger.info(f"事件记录数量: {len(event_records)}")
            
            logger.info("数据库API测试通过")
            return True
            
        except Exception as e:
            logger.error(f"数据库API测试异常: {e}")
            return False
    
    async def test_data_operations(self):
        """测试数据操作"""
        logger.info("测试数据操作...")
        
        try:
            # 测试直接插入数据 - 使用同步方式避免异步上下文管理器错误
            loop = asyncio.get_event_loop()
            
            # 插入状态历史记录
            status_record = StatusHistory(
                device_id="direct_test_device",
                timestamp=datetime.now(),
                status_type="WorkStatus",
                bit_position=5,
                old_value=0,
                new_value=1,
                status_name="测试状态"
            )
            await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_insert_status_record,
                status_record
            )
            
            # 插入实时数据
            real_time_record = RealTimeData(
                device_id="direct_test_device",
                timestamp=datetime.now(),
                parameter_name="test_parameter",
                value=88.8,
                unit="TEST"
            )
            await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_insert_real_time_record,
                real_time_record
            )
            
            # 插入事件记录
            event_record = EventRecords(
                device_id="direct_test_device",
                event_time=datetime.now(),  # 使用event_time而不是timestamp
                event_type="设备状态变化",
                description="测试事件"
            )
            await loop.run_in_executor(
                self.database_manager.thread_pool,
                self._sync_insert_event_record,
                event_record
            )
            
            logger.info("数据操作测试通过")
            return True
            
        except Exception as e:
            logger.error(f"数据操作测试异常: {e}")
            return False

    def _sync_insert_status_record(self, record):
        """同步插入状态历史记录"""
        session = self.database_manager.get_session()
        try:
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _sync_insert_real_time_record(self, record):
        """同步插入实时数据记录"""
        session = self.database_manager.get_session()
        try:
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _sync_insert_event_record(self, record):
        """同步插入事件记录"""
        session = self.database_manager.get_session()
        try:
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始运行数据库功能测试...")
        
        # 设置测试环境
        if not await self.setup():
            logger.error("测试环境设置失败，终止测试")
            return False
        
        test_results = {}
        
        try:
            # 运行各个测试
            test_results["database_connection"] = await self.test_database_connection()
            test_results["async_processor"] = await self.test_async_processor()
            test_results["database_api"] = await self.test_database_api()
            test_results["data_operations"] = await self.test_data_operations()
            
            # 统计测试结果
            total_tests = len(test_results)
            passed_tests = sum(test_results.values())
            
            logger.info(f"测试完成: {passed_tests}/{total_tests} 通过")
            
            # 输出详细结果
            for test_name, result in test_results.items():
                status = "通过" if result else "失败"
                logger.info(f"{test_name}: {status}")
            
            return all(test_results.values())
            
        except Exception as e:
            logger.error(f"测试过程中发生异常: {e}")
            return False
        
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """清理测试环境"""
        logger.info("清理测试环境...")
        
        try:
            if self.async_processor:
                await self.async_processor.stop()
            
            if self.database_manager:
                await self.database_manager.close()
            
            if self.database_initializer:
                await self.database_initializer.close()
                
            logger.info("测试环境清理完成")
            
        except Exception as e:
            logger.error(f"清理测试环境时发生异常: {e}")


async def main():
    """主测试函数"""
    tester = DatabaseTester()
    
    try:
        success = await tester.run_all_tests()
        
        if success:
            logger.info("所有数据库功能测试通过!")
            return 0
        else:
            logger.error("部分数据库功能测试失败!")
            return 1
            
    except Exception as e:
        logger.error(f"测试执行过程中发生异常: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
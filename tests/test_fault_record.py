#!/usr/bin/env python3
"""
故障录波读取功能测试脚本
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_fault_record_read():
    """测试故障录波读取功能"""
    try:
        import websockets
        
        # 连接到WebSocket服务器 - SimpleWebSocketServer不需要特定路径
        uri = "ws://localhost:8765"
        logger.info(f"连接到WebSocket服务器: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket连接已建立")
            
            # 等待一小段时间确保服务器准备好
            await asyncio.sleep(0.5)
            
            # 首先发送设备注册消息（不需要等待连接确认）
            register_msg = {
                "type": "device_register",
                "device_id": "TEST_DEVICE_001",
                "device_name": "测试设备"
            }
            logger.debug(f"发送注册消息: {register_msg}")
            await websocket.send(json.dumps(register_msg))
            logger.info("发送设备注册消息")
            
            # 等待注册响应
            try:
                register_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"收到注册响应: {register_response}")
            except asyncio.TimeoutError:
                logger.warning("注册响应超时，继续等待...")
            
            # 发送故障录波列表查询
            list_msg = {
                "type": "fault_record_list",
                "request_id": "test_list_001"
            }
            await websocket.send(json.dumps(list_msg))
            logger.info("发送故障录波列表查询")
            
            # 等待列表响应
            list_response = await websocket.recv()
            logger.info(f"收到列表响应: {list_response}")
            
            # 发送故障录波读取请求
            read_msg = {
                "type": "fault_record_read",
                "record_id": 0,
                "request_id": "test_read_001"
            }
            await websocket.send(json.dumps(read_msg))
            logger.info("发送故障录波读取请求")
            
            # 等待读取响应（可能需要接收多个消息）
            timeout = 30  # 30秒超时
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"收到响应: {response}")
                    
                    # 解析响应
                    data = json.loads(response)
                    if data.get("type") == "fault_record_complete":
                        logger.info("收到完整的故障录波数据")
                        break
                    elif data.get("type") == "fault_record_progress":
                        logger.info(f"读取进度: {data.get('percentage', 0)}%")
                    elif data.get("type") == "error":
                        logger.error(f"收到错误响应: {data.get('error_msg', '未知错误')}")
                        break
                        
                except asyncio.TimeoutError:
                    logger.warning("等待响应超时，继续等待...")
                    continue
            
            logger.info("测试完成")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        logger.error(f"详细错误信息: {traceback.format_exc()}")

if __name__ == "__main__":
    logger.info("开始测试故障录波读取功能")
    asyncio.run(test_fault_record_read())
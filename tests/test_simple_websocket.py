#!/usr/bin/env python3
"""
简化版WebSocket连接测试
"""

import asyncio
import websockets
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_simple_connection():
    """测试简单WebSocket连接"""
    uri = "ws://localhost:8766/ws/device?token=test_token"
    
    try:
        logger.info("开始测试WebSocket连接...")
        logger.info(f"连接URI: {uri}")
        
        # 建立连接
        logger.info("正在建立WebSocket连接...")
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket连接已建立")
            logger.info(f"WebSocket状态: {websocket.state}")
            logger.info(f"本地地址: {websocket.local_address}")
            logger.info(f"远程地址: {websocket.remote_address}")
            
            # 等待连接确认消息
            logger.info("等待连接确认消息...")
            try:
                connect_ack = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                logger.info(f"收到连接确认: {connect_ack}")
            except asyncio.TimeoutError:
                logger.warning("等待连接确认超时")
            
            # 尝试发送一个简单的ping消息
            ping_msg = json.dumps({"type": "ping"})
            logger.info(f"发送ping消息: {ping_msg}")
            await websocket.send(ping_msg)
            logger.info("ping消息发送成功")
            
            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"收到响应: {response}")
            except asyncio.TimeoutError:
                logger.warning("等待响应超时")
            
            # 等待更多消息
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.info(f"收到消息: {message}")
            except asyncio.TimeoutError:
                logger.info("没有更多消息")
                
    except Exception as e:
        logger.error(f"连接失败: {e}")
        logger.error(f"详细错误: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(test_simple_connection())
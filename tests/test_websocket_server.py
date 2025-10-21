#!/usr/bin/env python3
"""
专门测试websocket_server.py的连接
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

async def test_websocket_server():
    """测试websocket_server.py的连接"""
    # websocket_server.py监听8766端口
    uri = "ws://localhost:8766"
    
    try:
        logger.info(f"正在连接到 {uri}...")
        
        # 建立连接
        websocket = await websockets.connect(uri)
        logger.info("WebSocket连接已建立")
        logger.info(f"WebSocket状态: {websocket.state}")
        logger.info(f"本地地址: {websocket.local_address}")
        logger.info(f"远程地址: {websocket.remote_address}")
        
        # 发送心跳消息
        heartbeat_msg = json.dumps({"type": "heartbeat", "timestamp": "2024-01-01T00:00:00"})
        logger.info(f"发送心跳消息: {heartbeat_msg}")
        await websocket.send(heartbeat_msg)
        
        # 接收响应
        response = await websocket.recv()
        logger.info(f"收到响应: {response}")
        
        # 发送设备注册消息
        register_msg = json.dumps({
            "type": "device_register",
            "device_id": "test_device_001",
            "device_name": "测试设备"
        })
        logger.info(f"发送设备注册消息: {register_msg}")
        await websocket.send(register_msg)
        
        # 接收响应
        response = await websocket.recv()
        logger.info(f"收到响应: {response}")
        
        # 关闭连接
        await websocket.close()
        logger.info("连接已关闭")
        
    except Exception as e:
        logger.error(f"连接失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_websocket_server())
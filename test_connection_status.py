#!/usr/bin/env python3
"""
测试连接状态消息（包含串口状态）
"""
import asyncio
import json
import time
from datetime import datetime
import websockets
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket服务器配置
WS_URL = "ws://localhost:8766"

# 消息统计
message_stats = {
    "total_messages": 0,
    "message_types": {},
    "connection_status_count": 0,
    "first_connection_status_time": None,
    "last_connection_status_time": None
}

def analyze_connection_status(data):
    """分析连接状态消息"""
    try:
        websocket_connected = data.get("websocket_connected", False)
        hmi_serial_available = data.get("hmi_serial_available", False)
        scada_serial_available = data.get("scada_serial_available", False)
        
        logger.info(f"连接状态分析:")
        logger.info(f"  WebSocket连接: {'✓' if websocket_connected else '✗'}")
        logger.info(f"  HMI串口可用: {'✓' if hmi_serial_available else '✗'}")
        logger.info(f"  SCADA串口可用: {'✓' if scada_serial_available else '✗'}")
        
        return {
            "websocket_connected": websocket_connected,
            "hmi_serial_available": hmi_serial_available,
            "scada_serial_available": scada_serial_available
        }
    except Exception as e:
        logger.error(f"分析连接状态失败: {e}")
        return None

async def test_connection_status():
    """测试连接状态消息"""
    start_time = time.time()
    
    try:
        logger.info(f"正在连接到WebSocket服务器: {WS_URL}")
        
        async with websockets.connect(WS_URL) as websocket:
            logger.info("WebSocket连接已建立")
            
            # 记录连接建立时间
            connection_time = time.time()
            
            # 监听消息
            while time.time() - start_time < 60:  # 运行60秒
                try:
                    # 等待接收消息，设置超时
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    # 解析消息
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type", "unknown")
                        
                        # 更新消息统计
                        message_stats["total_messages"] += 1
                        message_stats["message_types"][msg_type] = message_stats["message_types"].get(msg_type, 0) + 1
                        
                        logger.info(f"收到消息类型: {msg_type}")
                        
                        # 特殊处理连接状态消息
                        if msg_type == "connection_status":
                            message_stats["connection_status_count"] += 1
                            
                            if message_stats["first_connection_status_time"] is None:
                                message_stats["first_connection_status_time"] = time.time() - start_time
                            
                            message_stats["last_connection_status_time"] = time.time() - start_time
                            
                            # 分析连接状态
                            status_data = data.get("data", {})
                            analyze_connection_status(status_data)
                        
                        # 记录完整消息内容（仅用于调试）
                        if msg_type == "connection_status":
                            logger.info(f"连接状态消息内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"解析消息失败: {e}")
                        logger.error(f"原始消息: {message}")
                    
                except asyncio.TimeoutError:
                    # 超时继续循环
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket连接已关闭")
                    break
                except Exception as e:
                    logger.error(f"接收消息出错: {e}")
                    await asyncio.sleep(0.1)
            
            # 计算运行时间
            run_time = time.time() - start_time
            
            # 输出分析结果
            logger.info("\n" + "="*60)
            logger.info("连接状态消息测试完成")
            logger.info("="*60)
            logger.info(f"运行时间: {run_time:.1f}秒")
            logger.info(f"总消息数: {message_stats['total_messages']}")
            logger.info(f"消息类型统计: {message_stats['message_types']}")
            
            # 连接状态消息分析
            logger.info(f"连接状态消息数量: {message_stats['connection_status_count']}")
            if message_stats['first_connection_status_time'] is not None:
                logger.info(f"首次连接状态消息时间: {message_stats['first_connection_status_time']:.1f}秒")
                logger.info(f"最后连接状态消息时间: {message_stats['last_connection_status_time']:.1f}秒")
            
            # 分析结果
            if message_stats['connection_status_count'] == 0:
                logger.warning("⚠️ 未收到connection_status消息")
                logger.info("可能原因:")
                logger.info("1. 串口管理器未正确初始化")
                logger.info("2. WebSocket服务器配置问题")
                logger.info("3. 连接状态发送机制异常")
            else:
                logger.info("✓ 成功收到connection_status消息")
                logger.info("串口状态现在通过connection_status消息发送，而不是单独的serial_status消息")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    logger.info("开始测试连接状态消息（包含串口状态）")
    logger.info("注意：串口状态现在通过connection_status消息发送，而不是单独的serial_status消息")
    
    # 运行测试
    success = asyncio.run(test_connection_status())
    
    if success:
        logger.info("测试完成")
    else:
        logger.error("测试失败")
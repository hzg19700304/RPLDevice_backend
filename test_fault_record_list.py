#!/usr/bin/env python3
"""
测试故障录波目录查询功能
"""
import asyncio
import websockets
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fault_record_list():
    """测试故障录波目录查询"""
    uri = "ws://127.0.0.1:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket连接成功")
            
            # 发送设备注册消息
            register_msg = {
                "type": "device_register",
                "device_id": "HYP_RPLD_001",
                "device_name": "红岩坪站钢轨电位限制装置",
                "device_ip": "192.168.0.11",
                "system_version": "1.0.0",
                "timestamp": "2025-10-24T16:05:00.000"
            }
            
            await websocket.send(json.dumps(register_msg))
            logger.info("发送设备注册消息")
            
            # 接收欢迎消息
            welcome_msg = await websocket.recv()
            logger.info(f"收到欢迎消息: {welcome_msg}")
            
            # 发送故障录波目录查询消息
            fault_list_msg = {
                "type": "fault_record_list",
                "device_id": "HYP_RPLD_001",
                "request_id": "test_req_123456"
            }
            
            await websocket.send(json.dumps(fault_list_msg))
            logger.info("发送故障录波目录查询消息")
            
            # 接收响应 - 尝试接收多个响应
            for i in range(5):  # 最多尝试接收5次
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)  # 设置2秒超时
                    logger.info(f"收到响应 {i+1}: {response}")
                    
                    # 解析响应
                    response_data = json.loads(response)
                    if response_data.get("type") == "fault_record_list_ack":
                        data = response_data.get("data", {})
                        total_records = data.get("total_records", 0)
                        logger.info(f"故障录波目录查询成功，总记录数: {total_records}")
                        
                        # 打印记录详情
                        records = data.get("records", [])
                        for record in records:
                            logger.info(f"记录ID: {record.get('record_id')}, 故障时间: {record.get('fault_time')}, 故障描述: {record.get('fault_desc')}")
                        break
                    elif response_data.get("type") == "connection_status":
                        logger.info("收到连接状态消息，继续等待...")
                        continue
                    else:
                        logger.error(f"收到意外的响应类型: {response_data.get('type')}")
                except asyncio.TimeoutError:
                    logger.info(f"等待响应 {i+1} 超时")
                    continue
            
    except Exception as e:
        logger.error(f"测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_fault_record_list())
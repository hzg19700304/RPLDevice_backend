#!/usr/bin/env python3
"""
测试前端故障录波目录查询功能
Test Frontend Fault Record Directory Query
"""

import asyncio
import json
import websockets
from datetime import datetime

async def test_frontend_fault_record_query():
    """测试前端故障录波目录查询功能"""
    try:
        # 连接到WebSocket服务器
        uri = "ws://127.0.0.1:8765"
        print(f"正在连接到WebSocket服务器: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("WebSocket连接成功")
            
            # 发送设备注册信息
            register_msg = {
                "type": "device_register",
                "device_id": "HYP_RPLD_001",
                "device_name": "红岩坪站钢轨电位限制装置",
                "device_ip": "192.168.0.11",
                "system_version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(register_msg, ensure_ascii=False))
            print(f"发送设备注册信息: {register_msg}")
            
            # 等待服务器响应
            response = await websocket.recv()
            print(f"收到服务器响应: {response}")
            
            # 发送故障录波目录查询请求（模拟前端发送的请求）
            query_msg = {
                "type": "fault_record_list",
                "device_id": "HYP_RPLD_001",
                "request_id": f"req_dir_{datetime.now().timestamp()}"
            }
            
            await websocket.send(json.dumps(query_msg, ensure_ascii=False))
            print(f"发送故障录波目录查询请求: {query_msg}")
            
            # 等待并接收多个响应
            for i in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    print(f"收到响应 {i+1}: {data}")
                    
                    # 检查是否是故障录波目录查询响应
                    if data.get('type') == 'fault_record_list_ack':
                        print("收到故障录波目录查询响应!")
                        records_data = data.get('data', {})
                        total_records = records_data.get('total_records', 0)
                        records = records_data.get('records', [])
                        print(f"总记录数: {total_records}")
                        print(f"记录详情: {records}")
                        break
                except asyncio.TimeoutError:
                    print(f"等待响应 {i+1} 超时")
                    continue
            
            print("测试完成")
            
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_frontend_fault_record_query())
#!/usr/bin/env python3
"""
测试故障录波目录查询
Test Fault Record Directory Query
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_fault_record_query():
    """测试故障录波目录查询"""
    try:
        # 连接到WebSocket服务器
        uri = "ws://localhost:8765"
        async with websockets.connect(uri) as websocket:
            print("已连接到WebSocket服务器")
            
            # 发送设备注册信息
            register_message = {
                "type": "device_register",
                "device_id": "HYP_RPLD_001",
                "device_name": "红岩坪站钢轨电位限制装置",
                "device_ip": "192.168.0.11",
                "system_version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(register_message, ensure_ascii=False))
            print("已发送设备注册信息")
            
            # 等待连接确认
            response = await websocket.recv()
            print(f"收到响应: {response}")
            
            # 发送故障录波目录查询请求
            query_message = {
                'type': 'fault_record_list',
                'device_id': 'HYP_RPLD_001',
                'request_id': f'req_dir_{datetime.now().timestamp()}'
            }
            
            print(f"发送故障录波目录查询请求: {query_message}")
            await websocket.send(json.dumps(query_message, ensure_ascii=False))
            
            # 等待响应
            response = await websocket.recv()
            print(f"收到故障录波目录查询响应: {response}")
            
            # 解析响应
            response_data = json.loads(response)
            if response_data.get('type') == 'fault_record_list_ack':
                data = response_data.get('data', {})
                total_records = data.get('total_records', 0)
                records = data.get('records', [])
                
                print(f"故障录波记录总数: {total_records}")
                print("故障录波记录列表:")
                for i, record in enumerate(records):
                    print(f"  {i+1}. ID: {record.get('record_id')}, 时间: {record.get('fault_time')}, 故障码: {record.get('fault_code')}, 描述: {record.get('fault_desc')}")
            
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_fault_record_query())
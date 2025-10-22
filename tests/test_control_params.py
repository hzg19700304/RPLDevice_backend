#!/usr/bin/env python3
"""
控制参数读取测试脚本
专门测试WebSocket控制参数读取功能
"""

import asyncio
import json
import websockets
import time

class ControlParamsTestClient:
    def __init__(self, uri="ws://localhost:8766"):
        self.uri = uri
        self.websocket = None
        
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(self.uri)
            print(f"✅ 连接到WebSocket服务器: {self.uri}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            print("🔌 断开连接")
    
    async def send_message(self, message):
        """发送消息"""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
            print(f"📤 发送消息: {message}")
    
    async def receive_messages(self, timeout=10):
        """接收消息"""
        messages = []
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                data = json.loads(message)
                messages.append(data)
                
                # 打印所有收到的消息类型（用于调试）
                print(f"📨 收到消息类型: {data.get('type')}")
                
                # 如果收到控制参数响应，打印详细信息
                if data.get("type") == "param_read_ack":
                    print(f"\n🎯 收到控制参数响应:")
                    response_data = data.get("data", {})
                    params = response_data.get("params", [])
                    print(f"参数数量: {len(params)}")
                    
                    # 打印前5个参数作为示例
                    for i, param in enumerate(params[:5]):
                        print(f"  {i+1}. {param.get('param_name')}: {param.get('current_value')} {param.get('unit')}")
                    
                    if len(params) > 5:
                        print(f"  ... 还有 {len(params)-5} 个参数")
                    break
                    
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"接收消息错误: {e}")
        
        return messages

async def test_control_params():
    """测试控制参数读取"""
    client = ControlParamsTestClient()
    
    # 连接
    if not await client.connect():
        return
    
    try:
        # 等待1秒让连接稳定
        await asyncio.sleep(1)
        
        # 发送控制参数读取请求
        control_params_request = {
            "type": "param_read",
            "read_type": "control_params",
            "timestamp": int(time.time() * 1000)
        }
        
        await client.send_message(control_params_request)
        
        # 接收响应
        messages = await client.receive_messages(timeout=5)
        
        print(f"\n📊 测试完成，共收到 {len(messages)} 条消息")
        
        # 分析结果
        control_params_response = None
        for msg in messages:
            if msg.get("type") == "param_read_ack":
                control_params_response = msg
                break
        
        if control_params_response:
            print("✅ 成功收到控制参数响应")
            response_data = control_params_response.get("data", {})
            params = response_data.get("params", [])
            print(f"参数数量: {len(params)}")
            
            if len(params) > 0:
                print("前几个参数:")
                for i, param in enumerate(params[:3]):
                    print(f"  {param.get('param_name')}: {param.get('current_value')} {param.get('unit')}")
            
            # 检查是否包含预期的参数
            param_names = [p.get('param_name') for p in params]
            expected_params = ['1段电压保护值（V）', '1段保护延时（0.01s）', '1段KM闭合时间（s）']
            
            for expected in expected_params:
                if expected in param_names:
                    print(f"✅ 找到参数: {expected}")
                else:
                    print(f"❌ 缺少参数: {expected}")
        else:
            print("❌ 未收到控制参数响应")
            
    except Exception as e:
        print(f"测试过程出错: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("🚀 开始控制参数读取测试...")
    asyncio.run(test_control_params())
    print("🏁 测试完成")
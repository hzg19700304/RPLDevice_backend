import requests
import json
from datetime import datetime, timedelta

# 测试设备ID为 direct_test_device 的查询
api_url = "http://localhost:8001/api/v1/history/events"

# 构建查询参数
params = {
    'start_time': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
    'end_time': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    'device_id': 'direct_test_device',  # 使用正确的设备ID
    'page': 1,
    'page_size': 20
}

print(f"测试设备ID: {params['device_id']}")
print(f"时间范围: {params['start_time']} 到 {params['end_time']}")

try:
    response = requests.get(api_url, params=params)
    print(f"\n状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"响应格式: {type(result)}")
        
        if isinstance(result, dict) and 'code' in result:
            print(f"标准格式 - code: {result.get('code')}")
            if result.get('code') == 200:
                data = result.get('data', {})
                print(f"数据: total={data.get('total')}, list长度={len(data.get('list', []))}")
                if data.get('list'):
                    print("前3条记录:")
                    for i, item in enumerate(data['list'][:3]):
                        print(f"  {i+1}: {item}")
            else:
                print(f"错误信息: {result.get('msg')}")
        else:
            print(f"直接格式 - total: {result.get('total')}, list长度: {len(result.get('list', []))}")
            if result.get('list'):
                print("前3条记录:")
                for i, item in enumerate(result['list'][:3]):
                    print(f"  {i+1}: {item}")
    else:
        print(f"API请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        
except Exception as e:
    print(f"请求异常: {e}")
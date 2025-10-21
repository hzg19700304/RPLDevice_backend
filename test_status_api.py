import requests
import json

# 查询状态历史
try:
    response = requests.get('http://localhost:8001/api/v1/history/status', params={
        'start_time': '2024-01-01T00:00:00',
        'end_time': '2025-12-31T23:59:59',
        'device_id': '1',
        'page': '1',
        'page_size': '10'
    })
    
    if response.status_code == 200:
        result = response.json()
        print('API响应格式:')
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 检查数据格式
        if 'data' in result and 'list' in result['data']:
            for item in result['data']['list']:
                print(f"状态项: status_name={item.get('status_name')}, status_type={item.get('status_type')}, bit_position={item.get('bit_position')}")
    else:
        print(f'API请求失败: {response.status_code}')
        print(response.text)
        
except Exception as e:
    print(f'请求异常: {e}')
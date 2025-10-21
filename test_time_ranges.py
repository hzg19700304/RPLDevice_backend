import requests
import json
from datetime import datetime, timedelta

def test_event_api(start_time, end_time, device_id='HYP_RPLD_001'):
    """测试事件记录API"""
    url = 'http://localhost:8001/api/v1/history/events'
    params = {
        'start_time': start_time,
        'end_time': end_time,
        'page': 1,
        'page_size': 20,
        'device_id': device_id
    }
    
    try:
        response = requests.get(url, params=params)
        print(f'Time Range: {start_time} to {end_time}')
        print(f'Status Code: {response.status_code}')
        
        result = response.json()
        print(f"Total: {result.get('total', 'No total')}")
        rows = result.get('list', [])
        print(f"List Length: {len(rows)}")
        if rows:
            print(f"First Row: {rows[0]}")
        else:
            print("No data found")
        print("-" * 50)
        
        return result
    except Exception as e:
        print(f'Error: {e}')
        return None

# 测试不同的时间范围
now = datetime.now()

# 1. 测试最近7天
start_time = (now - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00')
end_time = now.strftime('%Y-%m-%dT23:59:59')
test_event_api(start_time, end_time)

# 2. 测试最近30天
start_time = (now - timedelta(days=30)).strftime('%Y-%m-%dT00:00:00')
end_time = now.strftime('%Y-%m-%dT23:59:59')
test_event_api(start_time, end_time)

# 3. 测试所有时间（不限制设备ID）
start_time = '2024-01-01T00:00:00'
end_time = now.strftime('%Y-%m-%dT23:59:59')
test_event_api(start_time, end_time, device_id='')

# 4. 测试不限制设备ID的最近7天
start_time = (now - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00')
end_time = now.strftime('%Y-%m-%dT23:59:59')
test_event_api(start_time, end_time, device_id='')
import requests
import json

# 测试事件记录API
url = 'http://localhost:8001/api/v1/history/events'
params = {
    'start_time': '2025-10-13T00:00:00',
    'end_time': '2025-10-20T23:59:59',
    'page': 1,
    'page_size': 20,
    'device_id': 'HYP_RPLD_001'
}

try:
    response = requests.get(url, params=params)
    print(f'Status Code: {response.status_code}')
    
    result = response.json()
    print(f'Response Type: {type(result)}')
    print(f'Response Keys: {list(result.keys()) if isinstance(result, dict) else "Not a dict"}')
    
    if isinstance(result, dict) and 'code' in result:
        print(f"Code: {result.get('code')}")
        data = result.get('data', {})
        print(f"Data Type: {type(data)}")
        if isinstance(data, dict):
            print(f"Total: {data.get('total', 'No total')}")
            rows = data.get('list', [])
            print(f"List Length: {len(rows)}")
            if rows:
                print(f"First Row: {rows[0]}")
    else:
        print(f"Direct result - Total: {result.get('total', 'No total')}")
        rows = result.get('list', [])
        print(f"Direct result - List Length: {len(rows)}")
        if rows:
            print(f"First Row: {rows[0]}")
            
except Exception as e:
    print(f'Error: {e}')
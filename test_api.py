import asyncio
import aiohttp
from datetime import datetime

async def test_api():
    start_time = '2025-10-23T00:00:00+00:00'
    end_time = '2025-10-23T13:15:00+00:00'
    param_name = '轨地电流SA1'
    
    api_params = {
        'start_time': start_time,
        'end_time': end_time,
        'param_name': param_name,
        'page': 1,
        'page_size': 0
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'http://localhost:8001/api/v1/history/analog',
            params=api_params
        ) as response:
            if response.status == 200:
                result = await response.json()
                data = result.get('data', {})
                records = data.get('list', [])
                total_count = data.get('total_count', 0)
                
                print(f'参数: {param_name}')
                print(f'查询时间范围: {start_time} 至 {end_time}')
                print(f'返回数据点数: {len(records)}')
                print(f'总数据点数: {total_count}')
                
                if records:
                    print(f'首条数据时间: {records[0]["timestamp"]}')
                print(f'末条数据时间: {records[-1]["timestamp"]}')
                
                return len(records), total_count
            else:
                print(f'API请求失败: HTTP {response.status}')
                return 0, 0

# 运行测试
result = asyncio.run(test_api())
print(f'\nAPI查询结果: {result[0]}个数据点，总计{result[1]}个')
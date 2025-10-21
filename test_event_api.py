import asyncio
import httpx
from datetime import datetime, timedelta

async def test_event_api():
    """测试事件记录API"""
    start_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
    end_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    print(f'测试时间范围: {start_time} 到 {end_time}')
    
    params = {
        'start_time': start_time,
        'end_time': end_time,
        'page': 1,
        'page_size': 20
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get('http://localhost:8001/api/v1/history/events', params=params)
            print(f'状态码: {response.status_code}')
            print(f'响应头: {dict(response.headers)}')
            
            if response.status_code == 200:
                result = response.json()
                print(f'完整响应数据: {result}')
                
                # 检查数据结构
                if 'data' in result:
                    data = result['data']
                    print(f'总记录数: {data.get("total", 0)}')
                    print(f'记录列表长度: {len(data.get("list", []))}')
                    
                    # 打印第一条记录
                    if data.get('list'):
                        print(f'第一条记录: {data["list"][0]}')
                        print(f'记录字段: {list(data["list"][0].keys())}')
                else:
                    print('响应中没有data字段')
            else:
                print(f'错误响应: {response.text}')
                
    except Exception as e:
        print(f'API调用失败: {e}')

if __name__ == '__main__':
    asyncio.run(test_event_api())
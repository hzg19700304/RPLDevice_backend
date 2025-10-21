# RPLDevice WebSocket模块

## 概述

WebSocket模块为RPLDevice后端提供实时数据推送和控制指令传输功能，基于Python websockets库实现。

## 功能特性

- ✅ **实时数据推送** - 从串口获取下位机真实数据（系统状态、模拟量、开关量、故障状态）
- ✅ **单客户端支持** - 服务器只对应一个前端客户端
- ✅ **串口通信** - 通过Modbus RTU协议与下位机通信
- ✅ **设备连接管理** - 前端WebSocket连接认证和管理
- ✅ **心跳机制** - 连接状态监控和断线重连
- ✅ **控制指令下发** - 前端指令转发到下位机
- ✅ **故障录波查询** - 查询和推送故障录波数据
- ✅ **异常处理** - 完善的错误处理和日志记录

## 模块结构

```
websocket/
├── __init__.py              # 模块初始化
├── main.py                  # 主服务器启动文件
├── simple_websocket_server.py # WebSocket服务器核心（简化版，单客户端支持）
├── websocket_server.py      # WebSocket服务器（完整版，备用）
├── connection_manager.py    # 连接管理器
├── message_handler.py       # 消息处理器
├── serial_data_provider.py  # 串口数据提供器（从下位机获取数据）
├── data_pusher.py           # 数据推送器（备用，用于测试）
├── test_client.py           # 测试客户端
└── README.md                # 说明文档
```

## 数据流说明

```
下位机设备 (Modbus RTU)
       ↓ (串口通信)
串口数据提供器 (serial_data_provider.py)
       ↓ (数据转换)
WebSocket服务器 (websocket_server.py)
       ↓ (WebSocket协议)
前端客户端 (单个)
```

服务器设计为**单客户端模式**，所有数据通过串口从下位机获取，然后通过WebSocket推送到前端。

## 快速开始

### 1. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 安装依赖（直接安装）

```bash
pip install -r requirements.txt
```

### 2. 启动WebSocket服务器

```bash
cd websocket
python main.py
```

服务器将启动并监听配置文件中指定的地址和端口（默认：ws://0.0.0.0:8765）。

### 3. 运行测试客户端

```bash
python test_client.py
```

测试客户端将连接到服务器并执行综合功能测试。

## 配置说明

WebSocket服务器的配置在 `config.ini` 文件中：

```ini
[websocket]
host = 0.0.0.0
port = 8765
protocol = ws
heartbeat_interval = 10
max_connections = 100

[device]
device_id = HYP_RPLD_001
device_name = 红岩坪站钢轨电位限制装置
device_ip = 192.168.0.11
system_version = 1.0.0
```

## 消息协议

### 消息格式

所有消息都使用JSON格式：

```json
{
    "type": "消息类型",
    "device_id": "设备ID",
    "timestamp": "时间戳",
    "seq_num": "序列号",
    "data": {},
    "status": "状态"
}
```

### 消息类型

#### 客户端到服务器

- `register` - 设备注册
- `heartbeat` - 心跳
- `control` - 控制指令
- `fault_waveform` - 故障录波查询

#### 服务器到客户端

- `system_status` - 系统状态
- `analog_data` - 模拟量数据
- `switch_io` - 开关量数据
- `full_snapshot` - 全量快照
- `fault` - 故障状态
- `response` - 指令响应

### 数据推送频率

- **系统状态**: 1秒/次
- **模拟量数据**: 1秒/次  
- **开关量数据**: 1秒/次
- **全量快照**: 30秒/次
- **故障检查**: 5秒/次

## API接口

### WebSocketServer类

```python
from websocket import WebSocketServer

# 创建服务器实例
server = WebSocketServer(host="0.0.0.0", port=8765)

# 启动服务器
await server.start()

# 停止服务器
await server.stop()
```

### ConnectionManager类

```python
from websocket import ConnectionManager

# 连接管理
manager = ConnectionManager()

# 注册连接
await manager.register_connection(websocket, device_id)

# 广播消息
await manager.broadcast_to_all(message)

# 获取连接统计
stats = manager.get_connection_statistics()
```

### MessageHandler类

```python
from websocket import MessageHandler

# 消息处理
handler = MessageHandler(connection_manager, config_manager)

# 处理消息
response = await handler.handle_message(message, websocket)
```

### DataPusher类

```python
from websocket import DataPusher

# 数据推送
pusher = DataPusher(connection_manager, config_manager)

# 启动推送
await pusher.start_data_pushing()

# 停止推送
await pusher.stop_data_pushing()
```

## 测试

### 单元测试

```bash
pytest test_client.py -v
```

### 集成测试

1. 启动WebSocket服务器
2. 运行测试客户端
3. 观察日志输出和数据推送

## 故障排除

### 常见问题

1. **连接失败**: 检查服务器地址和端口配置
2. **消息格式错误**: 确保JSON格式正确
3. **心跳超时**: 检查网络连接和心跳间隔配置

### 日志查看

服务器日志包含详细的运行信息，可用于故障诊断：

```
2024-01-01 10:00:00 - websocket_server - INFO - WebSocket服务器已启动
2024-01-01 10:00:05 - connection_manager - INFO - 新连接建立: HYP_RPLD_001
2024-01-01 10:00:10 - data_pusher - INFO - 系统状态数据已推送
```

## 性能优化

- 使用异步编程提高并发性能
- 合理配置数据推送频率
- 监控连接数和内存使用
- 定期清理无效连接

## 安全考虑

- 实现连接认证机制
- 验证消息格式和内容
- 限制最大连接数
- 记录操作日志

## 扩展开发

### 添加新的消息类型

1. 在 `message_handler.py` 中添加新的处理方法
2. 更新消息类型定义
3. 测试新功能

### 自定义数据推送

1. 修改 `data_pusher.py` 中的数据生成逻辑
2. 调整推送频率配置
3. 添加新的数据字段

## 版本历史

- v1.0.0 (2024-01-01): 初始版本，实现基础WebSocket功能

## 技术支持

如有问题请联系开发团队或查看项目文档。
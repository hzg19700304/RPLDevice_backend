# RPLDevice 后端系统

红岩坪站钢轨电位限制装置（RPLDevice）后端系统，提供完整的设备监控、数据采集、WebSocket通信和数据库管理功能。

## 项目概述

RPLDevice后端系统是一个基于Python的工业自动化监控系统，专门为钢轨电位限制装置设计。系统集成了串口通信、Modbus RTU协议、WebSocket实时通信和MySQL数据库管理，为前端界面提供完整的数据支持。

### 主要功能

- **实时数据采集**：通过Modbus RTU协议从SCADA和HMI设备采集数据
- **WebSocket通信**：提供实时数据推送和前端交互接口
- **数据库管理**：MySQL数据库支持，包含数据存储、备份和性能优化
- **串口通信**：支持多串口设备同时通信
- **配置管理**：灵活的配置文件系统，支持热重载
- **异步处理**：基于asyncio的高性能异步数据处理

## 系统架构

```
RPLDevice后端系统
├── 配置管理 (config/)
├── 数据库管理 (database/)
├── 串口通信 (serial_comm/)
├── WebSocket服务 (websocket/)
├── API接口 (api/)
└── 主服务器 (main_server.py)
```

## 快速开始

### 环境要求

- Python 3.13+
- MySQL 5.7+ 或 8.0+
- Windows/Linux/macOS

### 创建虚拟环境（推荐）

为了避免依赖冲突，建议使用虚拟环境运行项目。

#### Windows 系统

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 退出虚拟环境
deactivate
```

#### Linux/macOS 系统

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 退出虚拟环境
deactivate
```

### 安装依赖

在激活虚拟环境后安装项目依赖：

```bash
pip install -r requirements.txt
```

如果遇到网络问题，可以使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 配置数据库

1. 确保MySQL服务正在运行
2. 创建数据库：
   ```sql
   CREATE DATABASE rpldevice CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. 修改配置文件 `config/config.ini` 中的数据库连接信息

### 配置文件

主要配置文件位于 `config/config.ini`，包含以下配置段：

- **数据库配置**：连接参数、性能配置、备份策略
- **服务器配置**：IP地址、端口号、服务开关
- **串口配置**：SCADA和HMI设备通信参数
- **WebSocket配置**：实时通信参数
- **设备配置**：设备信息和系统参数

### 启动系统

```bash
# 启动主服务器
python main_server.py

# 或者使用main.py（如果存在）
python main.py
```

## 项目结构

```
RPLDevice_backend/
├── config/                 # 配置管理
│   ├── config.ini         # 主配置文件
│   └── config_manager.py  # 配置管理器
├── database/              # 数据库管理
│   ├── database_manager.py     # 数据库管理器
│   ├── database_initializer.py # 数据库初始化
│   ├── async_processor.py     # 异步数据处理
│   ├── backup_manager.py      # 备份管理
│   ├── models.py              # 数据模型
│   └── sql_scripts/          # SQL脚本
├── serial_comm/           # 串口通信
│   ├── serial_manager.py      # 串口管理器
│   ├── modbus_rtu_master.py   # Modbus主站
│   └── modbus_rtu_slave.py    # Modbus从站
├── websocket/            # WebSocket服务
│   ├── websocket_server.py    # WebSocket服务器
│   ├── connection_manager.py  # 连接管理
│   ├── data_pusher.py        # 数据推送
│   └── message_handler.py    # 消息处理
├── api/                  # API接口
│   ├── api_server.py         # API服务器
│   └── auth.py              # 认证模块
├── tests/                # 测试文件
├── docs/                 # 文档
├── main_server.py        # 主服务器入口
├── requirements.txt      # 依赖列表
└── README.md            # 项目说明
```

## 配置说明

### 数据库配置

```ini
[数据库配置]
数据库类型 = mysql
数据库地址 = 127.0.0.1
数据库端口 = 3306
数据库名称 = rpldevice
数据库用户名 = root
数据库密码 = wodemima
```

### 串口配置

系统支持两个串口设备：

- **SCADA设备**：COM2，从站地址 0x5e
- **HMI设备**：COM1，从站地址 0x10

### WebSocket配置

```ini
[Web Socket配置]
listen_ip = 0.0.0.0
listen_port = 8765
protocol_type = ws
heartbeat_interval = 10
```

## 功能模块

### 1. 配置管理器 (`config_manager.py`)

- 自动加载和解析配置文件
- 支持十六进制值转换（如 `0x5e`）
- 配置热重载功能
- 类型安全的值获取

### 2. 数据库管理器 (`database_manager.py`)

- MySQL数据库连接管理
- 自动表创建和初始化
- 连接池管理
- 异步数据操作

### 3. 串口管理器 (`serial_manager.py`)

- 多串口设备管理
- Modbus RTU协议支持
- 异步数据采集
- 错误处理和重连机制

### 4. WebSocket服务器 (`websocket_server.py`)

- 实时数据推送
- 客户端连接管理
- 心跳检测
- 消息路由和处理

## 开发指南

### 添加新的配置项

1. 在 `config/config.ini` 中添加配置项
2. 在 `config_manager.py` 中添加对应的getter方法
3. 在代码中使用 `config_manager.get()` 获取配置值

### 扩展数据库模型

1. 在 `database/models.py` 中定义新的SQLAlchemy模型
2. 在 `database_manager.py` 中添加对应的CRUD操作
3. 运行系统自动创建表结构

### 添加新的API接口

1. 在 `api/api_server.py` 中定义新的路由
2. 实现对应的业务逻辑
3. 测试接口功能

## 测试

项目包含完整的测试套件：

```bash
# 运行所有测试
pytest tests/

# 运行特定测试模块
pytest tests/test_database.py
pytest tests/test_config_manager.py
```

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MySQL服务是否运行
   - 验证数据库连接参数
   - 确认数据库用户权限

2. **串口连接失败**
   - 检查串口设备是否存在
   - 验证串口配置参数
   - 确认设备地址和协议

3. **配置文件加载失败**
   - 检查配置文件路径
   - 验证配置文件格式
   - 确认文件编码为UTF-8

### 日志查看

系统日志默认输出到控制台，重要信息也会记录到文件：
```
D:/rpldevice/logs/log.log
```

## 部署说明

### 生产环境部署

1. 修改配置文件中的生产环境参数
2. 配置数据库连接池参数
3. 设置适当的日志级别
4. 配置SSL证书（如使用wss协议）

### 性能优化

- 调整数据库连接池大小
- 优化串口轮询间隔
- 配置适当的数据保留策略
- 启用查询缓存

## 版本信息

- **当前版本**: 1.0.0
- **Python版本**: 3.13+
- **数据库**: MySQL 5.7+/8.0+

## 许可证

本项目仅供红岩坪站钢轨电位限制装置使用。

## 技术支持

如有技术问题，请联系系统开发团队。

---

*最后更新: 2025-10-07*
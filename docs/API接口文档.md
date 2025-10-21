# RPLDevice API接口文档

## 概述

RPLDevice API是基于FastAPI框架实现的RESTful API接口，为钢轨电位限制装置提供设备监控、数据查询和控制功能。

### 错误响应处理现状说明

**当前实现状态**:
- ✅ **登录接口** - 已实现完整的错误处理（401错误）
- ✅ **设备信息接口** - 已实现完整的错误处理（500错误）
- ✅ **连接状态接口** - 已实现完整的错误处理（500错误）
- ✅ **历史数据查询接口** - 已实现完整的错误处理（400和500错误）
- ✅ **事件记录查询接口** - 已实现完整的错误处理（400和500错误）
- ✅ **健康检查接口** - 已实现完整的错误处理（503错误）
- ⚠️ **其他接口** - 目前仅返回成功响应，未实现具体的错误处理逻辑
- 📝 **文档说明** - 文档与代码实现保持一致

**建议**: 如需在生产环境中使用，建议为所有接口添加完整的错误处理逻辑。

**基础信息**
- **API前缀**: `/api/v1`
- **请求头**: `Authorization: Bearer {Token}`
- **响应格式**: JSON
- **编码**: UTF-8

**通用响应格式**
```json
{
  "code": 200,
  "msg": "success",
  "data": {},
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误码说明**
| 错误码 | 含义 | 说明 |
|--------|------|------|
| 200 | 成功 | 请求成功处理 |
| 400 | 参数错误 | 请求参数缺失或格式错误 |
| 401 | 未授权 | Token无效或过期 |
| 403 | 权限不足 | 用户无权执行该操作 |
| 404 | 资源不存在 | 请求的资源不存在 |
| 500 | 服务器错误 | 服务器内部错误 |

---

## 认证接口

### 1. 用户登录

**接口**: `POST /api/v1/auth/login`

**功能**: 用户登录并获取访问Token

**请求体**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应示例**:
```json
{
  "code": 200,
  "msg": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user_info": {
      "user_id": "admin001",
      "username": "admin",
      "permission_type": "admin"
    }
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:

**401 未授权**
```json
{
  "code": 401,
  "msg": "用户名或密码错误",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**500 服务器错误**
```json
{
  "code": 500,
  "msg": "数据库API未初始化",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "登录失败，请稍后重试",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**状态**: ✅ **已实现完整错误处理**

### 2. 刷新Token

**接口**: `POST /api/v1/auth/refresh`

**功能**: 刷新访问Token

**请求头**:
```
Authorization: Bearer {当前Token}
```

**响应示例**:
```json
{
  "code": 200,
  "msg": "Token刷新成功",
  "data": {
    "token": "新的Token",
    "expires_in": 3600
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

### 3. 退出登录

**接口**: `POST /api/v1/auth/logout`

**功能**: 用户退出登录

**请求头**:
```
Authorization: Bearer {当前Token}
```

**响应示例**:
```json
{
  "code": 200,
  "msg": "已退出登录",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

---

## 设备信息接口

### 4. 获取设备基础信息

**接口**: `GET /api/v1/device/info`

**功能**: 获取设备的基本信息

**请求头**:
```
Authorization: Bearer {Token}
```

**响应示例**:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "device_id": "HYP_RPLD_001",
    "device_name": "红岩坪站钢轨电位限制装置",
    "device_ip": "192.168.0.11",
    "system_version": "1.0.0",
    "online_status": true,
    "last_update": "2024-09-29T14:30:00.123"
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:

**401 未授权**
```json
{
  "code": 401,
  "msg": "Token无效或已过期",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**500 服务器错误**
```json
{
  "code": 500,
  "msg": "配置管理器未初始化",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "设备信息获取失败",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "获取设备信息失败，请稍后重试",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**状态**: ✅ **已实现完整错误处理**

### 5. 获取连接状态

**接口**: `GET /api/v1/device/connection_status`

**功能**: 获取系统各组件连接状态

**请求头**:
```
Authorization: Bearer {Token}
```

**响应示例**:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "hmi_serial": {
      "status": "online",
      "port": "COM1",
      "last_connected": "2024-09-29T14:30:00.123"
    },
    "pscada_serial": {
      "status": "online",
      "port": "COM2",
      "last_connected": "2024-09-29T14:30:00.123"
    },
    "server_tcp": {
      "status": "online",
      "server_ip": "192.168.0.1",
      "last_connected": "2024-09-29T14:30:00.123"
    },
    "websocket": {
      "active_connections": 1,
      "max_connections": 10
    }
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:

**401 未授权**
```json
{
  "code": 401,
  "msg": "Token无效或已过期",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**500 服务器错误**
```json
{
  "code": 500,
  "msg": "配置管理器未初始化",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "连接状态数据获取失败",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "获取连接状态失败，请稍后重试",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**状态**: ✅ **已实现完整错误处理**

---

## 历史数据查询接口

### 6. 查询历史模拟量数据

**接口**: `GET /api/v1/history/analog`

**功能**: 查询历史模拟量数据记录

**请求头**:
```
Authorization: Bearer {Token}
```

**查询参数**:
| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| start_time | string | 是 | 开始时间 | 2024-09-29T14:00:00 |
| end_time | string | 是 | 结束时间 | 2024-09-29T15:00:00 |
| param_name | string | 否 | 参数名称 | 支路1电流 |
| page | int | 否 | 页码，默认1 | 1 |
| page_size | int | 否 | 每页条数，默认20 | 20 |

**响应示例**:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 1580,
    "page": 1,
    "page_size": 20,
    "list": [
      {
        "timestamp": "2024-09-29T14:00:00.000",
        "parameter_name": "支路1电流",
        "value": 12.5,
        "unit": "A"
      },
      {
        "timestamp": "2024-09-29T14:01:00.000",
        "parameter_name": "支路1电流",
        "value": 12.6,
        "unit": "A"
      }
    ]
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:

**400 请求参数错误**
```json
{
  "code": 400,
  "msg": "时间参数格式错误: Invalid isoformat string",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "开始时间必须早于结束时间",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "页码必须大于等于1",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "每页条数必须在1-100之间",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**401 未授权**
```json
{
  "code": 401,
  "msg": "Token无效或已过期",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**500 服务器错误**
```json
{
  "code": 500,
  "msg": "数据库API未初始化",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "查询历史数据失败，请稍后重试",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**状态**: ✅ **已实现完整错误处理**

---

### 7. 查询事件记录

**接口**: `GET /api/v1/history/events`

**功能**: 查询系统事件记录，包括设备连接、系统启动、通信状态等事件信息

**请求头**:
```
Authorization: Bearer {Token}
```

**查询参数**:
| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| start_time | string | 是 | 开始时间 | 2024-09-29T14:00:00 |
| end_time | string | 是 | 结束时间 | 2024-09-29T15:00:00 |
| device_id | string | 否 | 设备ID | HYP_RPLD_001 |
| event_type | string | 否 | 事件类型 | 系统启动 |
| page | int | 否 | 页码，默认1 | 1 |
| page_size | int | 否 | 每页条数，默认20 | 20 |

**响应示例**:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 45,
    "page": 1,
    "page_size": 20,
    "list": [
      {
        "id": "1",
        "device_id": "HYP_RPLD_001",
        "event_time": "2024-09-29T08:00:00.000",
        "event_type": "系统启动",
        "description": "人机界面系统启动成功"
      },
      {
        "id": "2",
        "device_id": "HYP_RPLD_001",
        "event_time": "2024-09-29T08:00:05.123",
        "event_type": "通信连接正常",
        "description": "已与设备建立HMI串口通信"
      }
    ]
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:

**400 请求参数错误**
```json
{
  "code": 400,
  "msg": "时间参数格式错误: Invalid isoformat string",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "开始时间必须早于结束时间",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "页码必须大于等于1",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 400,
  "msg": "每页条数必须在1-100之间",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**401 未授权**
```json
{
  "code": 401,
  "msg": "Token无效或已过期",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**500 服务器错误**
```json
{
  "code": 500,
  "msg": "数据库API未初始化",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

```json
{
  "code": 500,
  "msg": "查询事件记录失败，请稍后重试",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**状态**: ✅ **已实现完整错误处理**

---

## 控制指令接口

### 7. 发送控制指令

**接口**: `POST /api/v1/control/command`

**功能**: 向设备发送控制指令

**请求头**:
```
Authorization: Bearer {Token}
Content-Type: application/json
```

**请求体**:
```json
{
  "device_id": "HYP_RPLD_001",
  "command_type": "remote_control",
  "command_data": {
    "coil_address": "0x0120",
    "operation": "set",
    "value": 1
  }
}
```

**command_type说明**:
- `remote_control`: 远程控制指令
- `parameter_set`: 参数设置指令
- `fault_reset`: 故障复位指令

**响应示例**:
```json
{
  "code": 200,
  "msg": "控制指令已发送",
  "data": {
    "command_id": "cmd_20240929143001",
    "command_type": "remote_control",
    "status": "sent",
    "timestamp": "2024-09-29T14:30:01.123"
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**错误响应**:
```json
{
  "code": 403,
  "msg": "权限不足，无法执行控制指令",
  "data": null,
  "timestamp": "2024-09-29T14:30:00.123"
}
```

---

## 系统状态接口

### 8. 健康检查

**接口**: `GET /api/v1/health`

**功能**: 检查API服务健康状态，包括配置管理器、数据库API、认证管理器等关键组件的可用性

**请求**: 无需认证

**响应示例**:

**200 服务正常**
```json
{
  "code": 200,
  "msg": "服务正常",
  "data": {
    "overall_status": "healthy",
    "components": {
      "config_manager": {
        "status": "healthy",
        "detail": "配置管理器运行正常"
      },
      "database_api": {
        "status": "healthy",
        "detail": "数据库API运行正常"
      },
      "auth_manager": {
        "status": "healthy",
        "detail": "认证管理器运行正常"
      }
    },
    "timestamp": "2024-09-29T14:30:00.123"
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**503 服务异常**
```json
{
  "code": 503,
  "msg": "服务异常",
  "data": {
    "overall_status": "unhealthy",
    "components": {
      "config_manager": {
        "status": "unhealthy",
        "detail": "配置管理器未初始化"
      },
      "database_api": {
        "status": "healthy",
        "detail": "数据库API运行正常"
      },
      "auth_manager": {
        "status": "healthy",
        "detail": "认证管理器运行正常"
      }
    },
    "timestamp": "2024-09-29T14:30:00.123"
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

**503 健康检查服务异常**
```json
{
  "code": 503,
  "msg": "健康检查失败",
  "data": {
    "overall_status": "unhealthy",
    "components": {
      "health_check_service": {
        "status": "unhealthy",
        "detail": "健康检查服务异常: 具体错误信息"
      }
    },
    "timestamp": "2024-09-29T14:30:00.123"
  },
  "timestamp": "2024-09-29T14:30:00.123"
}
```

---

## 使用示例

### Python示例

```python
import requests
import json

# 1. 用户登录
login_url = "http://localhost:8000/api/v1/auth/login"
login_data = {
    "username": "admin",
    "password": "admin123"
}

response = requests.post(login_url, json=login_data)
if response.status_code == 200:
    result = response.json()
    token = result["data"]["token"]
    print(f"登录成功，Token: {token}")
else:
    print(f"登录失败: {response.text}")

# 2. 获取设备信息（需要认证）
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

device_url = "http://localhost:8000/api/v1/device/info"
response = requests.get(device_url, headers=headers)
if response.status_code == 200:
    device_info = response.json()
    print(f"设备信息: {device_info}")

# 3. 查询历史数据
history_url = "http://localhost:8000/api/v1/history/analog"
params = {
    "start_time": "2024-09-29T14:00:00",
    "end_time": "2024-09-29T15:00:00",
    "param_name": "支路1电流",
    "page": 1,
    "page_size": 10
}

response = requests.get(history_url, headers=headers, params=params)
if response.status_code == 200:
    history_data = response.json()
    print(f"历史数据: {history_data}")
```

### JavaScript示例

```javascript
// 使用fetch API
const API_BASE = 'http://localhost:8000/api/v1';

// 1. 用户登录
async function login(username, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password })
    });
    
    if (response.ok) {
        const result = await response.json();
        return result.data.token;
    } else {
        throw new Error('登录失败');
    }
}

// 2. 获取设备信息
async function getDeviceInfo(token) {
    const response = await fetch(`${API_BASE}/device/info`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (response.ok) {
        return await response.json();
    } else {
        throw new Error('获取设备信息失败');
    }
}

// 使用示例
login('admin', 'admin123')
    .then(token => {
        console.log('登录成功，Token:', token);
        return getDeviceInfo(token);
    })
    .then(deviceInfo => {
        console.log('设备信息:', deviceInfo);
    })
    .catch(error => {
        console.error('操作失败:', error);
    });
```

---

## 注意事项

1. **Token有效期**: Token有效期为1小时，过期前10分钟内可刷新
2. **权限控制**: 控制指令接口需要`control`或`admin`权限
3. **时间格式**: 所有时间参数使用ISO 8601格式
4. **分页查询**: 历史数据查询支持分页，默认每页20条
5. **错误处理**: 所有接口都返回标准错误码和错误信息
6. **连接超时**: 建议设置合理的请求超时时间（建议30秒）

---

## 版本信息

- **文档版本**: v1.0
- **API版本**: v1.0
- **更新日期**: 2024-09-29
- **维护人员**: RPLDevice开发团队

如需更多技术支持，请联系开发团队。
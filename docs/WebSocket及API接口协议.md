# WebSocket及API接口协议完整版

结合串口协议和config.ini配置，设计**WebSocket实时推送协议**和**API接口协议**，确保三者数据逻辑一致（串口解析结果→WebSocket推送→API查询无缝衔接）。

------

## 一、基础约定（贯穿两个协议）

### 1.1 数据格式

- 所有交互采用`JSON`，编码`UTF-8`

### 1.2 时间戳

- 统一格式：`YYYY-MM-DD HH:MM:SS.sss`（毫秒级）

### 1.3 设备标识

- 所有协议携带`device_id`（如`HYP_RPLD_001`）

### 1.4 状态枚举

- 基于config.ini点表定义：`0=正常/分位/分闸/关闭，1=故障/合位/合闸/启动`

### 1.5 错误码

| 错误码 | 含义       | 适用场景                       |
| ------ | ---------- | ------------------------------ |
| 200    | 成功       | 所有正常响应                   |
| 400    | 参数错误   | API请求参数缺失/格式错误       |
| 401    | 未授权     | Token无效/过期                 |
| 403    | 权限不足   | 用户无权执行该操作             |
| 404    | 资源不存在 | 查询的数据不存在               |
| 409    | 指令冲突   | 高优先级指令正在执行           |
| 500    | 后端异常   | 串口读取失败/数据库错误        |
| 503    | 服务不可用 | WebSocket连接达到上限/串口断开 |

------

## 二、WebSocket实时推送协议

### 2.1 连接建立规则

**连接地址**：

```
ws://{工控机IP}:8765/ws/device?token={JWT_Token}
```

**连接流程**：

```json
// 1. 前端发起连接（携带Token）
ws://192.168.0.11:8765/ws/device?token=eyJhbGc...

// 2. 后端返回连接确认
{
  "type": "connect_ack",
  "status": "success",
  "connection_id": "conn_20240929143000",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:00.123"
}

// 3. 连接失败响应
{
  "type": "connect_fail",
  "status": "error",
  "error_code": 401,
  "error_msg": "Token已过期，请重新登录",
  "timestamp": "2024-09-29 14:30:00.123"
}
```

**心跳机制**：

```json
// 前端每10s发送心跳
{
  "type": "heartbeat"
}

// 后端响应心跳（附带关键状态摘要）
{
  "type": "heartbeat_ack",
  "timestamp": "2024-09-29 14:30:10.123",
  "summary": {
    "device_online": true,
    "pscada_connected": true,
    "server_connected": true,
    "fault_count": 0
  }
}
```

### 2.2 数据推送类型

#### （1）系统状态推送

```json
{
  "type": "system_status",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:00.123",
  "seq_num": 1001,  // 序列号，用于检测数据丢失
  "data": {
    "bit5": 0,   // 故障状态：0=正常
    "bit7": 1,   // 参数状态：1=正确
    "bit8": 0,   // KM1状态：0=恢复
    "bit9": 1    // 存储器：1=正常
  },
  "status": "success"
}
```

#### （2）开关量推送

```json
{
  "type": "switch_io",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:05.456",
  "seq_num": 1002,
  "data": {
    "input": {
      "bit0": 1,   // 短接接触器：1=合位
      "bit9": 1    // 门锁：1=关闭
    },
    "output": {
      "bit0": 1,   // K1：1=合闸
      "bit8": 1    // K9：1=合闸
    }
  },
  "status": "success"
}
```

#### （3）模拟量推送

```json
{
  "type": "analog_data",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:10.789",
  "seq_num": 1003,
  "data": [
    {
      "reg_addr": "0x0006",
      "name": "最大极化电位",
      "raw_value": 255,
      "physical_value": 25.5,
      "unit": "V"
    },
    {
      "reg_addr": "0x0008",
      "name": "支路1电流",
      "raw_value": 120,
      "physical_value": 12.0,
      "unit": "A"
    }
  ],
  "status": "success"
}
```

#### （4）故障推送

```json
{
  "type": "fault",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:15.123",
  "seq_num": 1004,
  "data": {
    "fault_bit": 0,
    "fault_code": "VOLTAGE_PROTECTION_1",
    "fault_desc": "1段电压保护",
    "fault_status": 1,  // 1=故障触发
    "recovery_method": "手动复位故障线圈（0x0101）"
  },
  "status": "success"
}
```

#### （5）全量快照推送（每30秒）

```json
{
  "type": "full_snapshot",
  "device_id": "HYP_RPLD_001",
  "timestamp": "2024-09-29 14:30:00.000",
  "seq_num": 1005,
  "data": {
    "system_status": {
      "bit0": 0, "bit1": 0, /* ... */ "bit15": 0,
      "switch_input": {
        "bit0": 1, "bit1": 0, /* ... */ "bit15": 0
      },
      "switch_output": {
        "bit0": 1, "bit8": 1, /* ... */ "bit15": 0
      }
    },
    "analog_data": [
      {"reg_addr": "0x0006", "name": "最大极化电位", "value": 25.5, "unit": "V"},
      /* ... 所有模拟量 */
    ],
    "fault_status": {
      "bit0": 0, "bit1": 0, /* ... */ "bit15": 0
    }
  },
  "status": "success"
}
```

### 2.3 指令下发格式

#### （1）故障复位指令

```json
// 前端发送
{
  "type": "control_cmd",
  "device_id": "HYP_RPLD_001",
  "cmd": "fault_reset",
  "cmd_param": {
    "coil_addr": "0x0101"
  },
  "request_id": "req_20240929143000",
  "timestamp": "2024-09-29 14:30:00.000"
}

// 后端响应
{
  "type": "control_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_20240929143000",
  "cmd": "fault_reset",
  "exec_status": "success",
  "exec_msg": "故障复位成功",
  "timestamp": "2024-09-29 14:30:00.456"
}
```

#### （2）参数设置指令

```json
// 前端发送
{
  "type": "control_cmd",
  "device_id": "HYP_RPLD_001",
  "cmd": "set_param",
  "cmd_param": {
    "reg_addr": "0x2200",
    "param_name": "过压保护延时(ms)",
    "param_value": 500
  },
  "request_id": "req_20240929143001"
}

// 后端响应
{
  "type": "control_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_20240929143001",
  "cmd": "set_param",
  "exec_status": "success",
  "exec_msg": "参数设置成功",
  "current_value": 500,
  "timestamp": "2024-09-29 14:30:01.123"
}
```

#### （3）工作模式切换指令

```json
// 前端发送
{
  "type": "control_cmd",
  "device_id": "HYP_RPLD_001",
  "cmd": "set_mode",
  "cmd_param": {
    "mode": "auto",  // auto/manual_on/manual_off/remote_on/remote_off
    "coil_addr": "0x0122"
  },
  "request_id": "req_20240929143002"
}

// 后端响应
{
  "type": "control_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_20240929143002",
  "cmd": "set_mode",
  "exec_status": "success",
  "exec_msg": "工作模式已切换为自动排流",
  "current_mode": "auto",
  "timestamp": "2024-09-29 14:30:02.123"
}
```

#### （4）指令冲突响应

```json
{
  "type": "control_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_20240929143003",
  "cmd": "set_param",
  "exec_status": "fail",
  "error_code": 409,
  "exec_msg": "CONFLICT_HIGH_PRIORITY：系统服务器正在执行配置更新",
  "timestamp": "2024-09-29 14:30:03.000"
}
```

### 2.4 故障录波操作（串口0x14命令）

#### （1）查询故障录波目录

```json
// 前端发送
{
  "type": "fault_record_list",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_list_001"
}

// 后端响应（读取0x0300-0x0303寄存器）
{
  "type": "fault_record_list_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_list_001",
  "data": {
    "total_records": 15,      // 当前故障录波记录数（0x0300）
    "max_capacity": 100,      // 最多存放记录数（0x0303）
    "record_length": 3907,    // 每条记录长度（0x0301）
    "records": [
      {
        "record_id": 0,       // 0=最新记录
        "fault_time": "2024-09-29 13:45:12.345",
        "fault_bits": "0x0001",
        "fault_desc": "支路1过流保护"
      },
      {
        "record_id": 1,
        "fault_time": "2024-09-28 10:23:45.678",
        "fault_bits": "0x0040",
        "fault_desc": "电阻超温报警"
      }
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）读取故障录波详情（分批读取）

```json
// 前端发送读取请求
{
  "type": "fault_record_read",
  "device_id": "HYP_RPLD_001",
  "record_id": 0,           // 0=最新记录
  "request_id": "req_fault_read_001"
}

// 后端返回开始读取确认
{
  "type": "fault_record_read_start",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001",
  "total_registers": 3907,
  "batch_size": 125,        // 每批读取125个寄存器
  "total_batches": 32,      // 共需32批
  "estimated_time": 15,     // 预计耗时(秒)
  "timestamp": "2024-09-29 14:30:00.123"
}

// 后端推送读取进度（每读取一批推送一次）
{
  "type": "fault_record_progress",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001",
  "current_batch": 5,
  "total_batches": 32,
  "percentage": 15.6,
  "timestamp": "2024-09-29 14:30:02.500"
}

// 读取完成，推送完整数据
{
  "type": "fault_record_complete",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001",
  "data": {
    "fault_info": {
      "fault_time": "2024-09-29 13:45:12.345",
      "fault_bits": "0x0001",
      "fault_point": 150,
      "record_cycle": 100
    },
    "data_points": [
      {
        "point_index": 0,
        "system_status": "0x0104",
        "switch_input": "0x0200",
        "switch_output": "0x0101",
        "rail_potential_max": 255,
        "max_polarization": -120,
        "branch_currents": [12, 13, 11, 10, 9, 8],
        "branch_voltages": [24, 25]
      }
      // ... 共300个数据点
    ]
  },
  "timestamp": "2024-09-29 14:30:15.123"
}

// 读取失败响应
{
  "type": "fault_record_error",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001",
  "error_code": 500,
  "error_msg": "串口通信超时：第10批数据读取失败",
  "current_batch": 10,
  "timestamp": "2024-09-29 14:30:05.123"
}
```

#### （3）取消故障录波读取

```json
// 前端发送取消请求（用户点击取消按钮）
{
  "type": "fault_record_cancel",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001"  // 匹配原读取请求ID
}

// 后端确认取消
{
  "type": "fault_record_cancelled",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_read_001",
  "cancelled_at_batch": 10,  // 在第10批时取消
  "timestamp": "2024-09-29 14:30:05.456"
}
```

#### （4）清除故障录波记录

```json
// 前端发送清除请求（对应线圈0x0110）
{
  "type": "control_cmd",
  "device_id": "HYP_RPLD_001",
  "cmd": "fault_record_clear",
  "cmd_param": {
    "coil_addr": "0x0110",
    "confirm": true
  },
  "request_id": "req_fault_clear_001"
}

// 后端响应
{
  "type": "control_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_fault_clear_001",
  "cmd": "fault_record_clear",
  "exec_status": "success",
  "exec_msg": "故障录波记录已清除",
  "cleared_count": 15,
  "timestamp": "2024-09-29 14:30:00.456"
}
```

### 2.5 参数查询操作（串口0x03读取寄存器）

#### （1）读取控制参数

```json
// 前端发送读取请求（读取0x2200-0x221A寄存器）
{
  "type": "param_read",
  "device_id": "HYP_RPLD_001",
  "read_type": "control_params",  // control_params/sensor_params/all
  "request_id": "req_param_read_001"
}

// 后端响应（串口读取27个控制参数寄存器）
{
  "type": "param_read_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_param_read_001",
  "data": {
    "params": [
      {
        "reg_addr": "0x2200",
        "param_name": "过压保护延时(ms)",
        "current_value": 500,
        "value_range": "0-65535",
        "unit": "ms"
      },
      {
        "reg_addr": "0x2201",
        "param_name": "支路过流保护值(A)",
        "current_value": 150,
        "value_range": "0-500",
        "unit": "A"
      }
      // ... 全部27个控制参数
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）读取传感器参数

```json
// 前端发送读取请求（读取0x2000-0x200F寄存器）
{
  "type": "param_read",
  "device_id": "HYP_RPLD_001",
  "read_type": "sensor_params",
  "request_id": "req_sensor_read_001"
}

// 后端响应（读取16个传感器参数寄存器）
{
  "type": "param_read_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_sensor_read_001",
  "data": {
    "sensor_down": [
      {"channel": "AI1", "down_limit": -1000},
      {"channel": "AI2", "down_limit": -1000}
      // ... AI1-AI8下限
    ],
    "sensor_up": [
      {"channel": "AI1", "up_limit": 1000},
      {"channel": "AI2", "up_limit": 1000}
      // ... AI1-AI8上限
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （3）读取单个参数

```json
// 前端发送读取单个参数请求
{
  "type": "param_read",
  "device_id": "HYP_RPLD_001",
  "read_type": "single",
  "reg_addr": "0x2200",
  "request_id": "req_single_read_001"
}

// 后端响应
{
  "type": "param_read_ack",
  "device_id": "HYP_RPLD_001",
  "request_id": "req_single_read_001",
  "data": {
    "reg_addr": "0x2200",
    "param_name": "过压保护延时(ms)",
    "current_value": 500,
    "unit": "ms"
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 2.6 异常通知

#### （1）序列号缺失

```json
// 前端检测到序列号从1005跳到1007，发送请求
{
  "type": "data_lost_request",
  "missing_seq": [1006]
}

// 后端补推缺失数据
{
  "type": "data_recovery",
  "seq_num": 1006,
  "data": { /* 原始数据 */ }
}
```

#### （2）连接异常

```json
{
  "type": "connection_lost",
  "reason": "心跳超时",
  "timestamp": "2024-09-29 14:35:00.000"
}
```

#### （3）串口通信异常

```json
{
  "type": "serial_error",
  "serial_type": "HMI",  // HMI/PSCADA
  "error_code": 503,
  "error_msg": "串口COM1连接断开",
  "timestamp": "2024-09-29 14:35:00.000"
}
```

------

## 三、API接口协议

### 3.1 基础规则

- **接口前缀**：`/api/v1`
- **请求方法**：`GET`（查询）、`POST`（提交/修改）、`DELETE`（删除）
- **请求头**：`Authorization: Bearer {Token}`
- **响应格式**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {},
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 3.2 认证接口

#### （1）用户登录

- **接口**：`POST /api/v1/auth/login`
- **请求**：

```json
{
  "username": "admin",
  "password": "hashed_password"  // 前端SHA-256加密后传输
}
```

- **响应**：

```json
{
  "code": 200,
  "msg": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,  // 1小时
    "user_info": {
      "user_id": "admin001",
      "username": "admin",
      "permission_type": "admin"
    }
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）Token刷新

- **接口**：`POST /api/v1/auth/refresh`
- **请求头**：`Authorization: Bearer {旧Token}`
- **响应**：

```json
{
  "code": 200,
  "msg": "Token刷新成功",
  "data": {
    "token": "新的Token",
    "expires_in": 3600
  },
  "timestamp": "2024-09-29 15:30:00.123"
}
```

#### （3）退出登录

- **接口**：`POST /api/v1/auth/logout`
- **响应**：

```json
{
  "code": 200,
  "msg": "已退出登录",
  "timestamp": "2024-09-29 16:30:00.123"
}
```

### 3.3 设备信息接口

#### （1）设备基础信息

- **接口**：`GET /api/v1/device/info`
- **响应**：

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
    "last_update": "2024-09-29 14:30:00.123"
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）连接状态查询

- **接口**：`GET /api/v1/device/connection_status`
- **响应**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "hmi_serial": {
      "status": "online",
      "port": "COM1",
      "last_connected": "2024-09-29 08:00:00.000"
    },
    "pscada_serial": {
      "status": "online",
      "port": "COM2",
      "last_connected": "2024-09-29 08:00:05.000"
    },
    "server_tcp": {
      "status": "online",
      "server_ip": "192.168.0.1",
      "last_connected": "2024-09-29 08:00:10.000"
    },
    "websocket": {
      "active_connections": 2,
      "max_connections": 10
    }
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 3.4 历史数据查询接口

#### （1）历史模拟量数据

- **接口**：`GET /api/v1/history/analog`
- **参数**：

| 参数名     | 类型   | 必选 | 说明                            |
| ---------- | ------ | ---- | ------------------------------- |
| start_time | string | 是   | 开始时间（YYYY-MM-DD HH:MM:SS） |
| end_time   | string | 是   | 结束时间                        |
| param_name | string | 否   | 参数名称（如"支路1电流"）       |
| page       | int    | 否   | 页码（默认1）                   |
| page_size  | int    | 否   | 每页条数（默认20，最大100）     |

- **响应**：

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
        "timestamp": "2024-09-29 14:00:00.000",
        "parameter_name": "支路1电流",
        "value": 12.5,
        "unit": "A"
      },
      {
        "timestamp": "2024-09-29 14:01:00.000",
        "parameter_name": "支路1电流",
        "value": 12.6,
        "unit": "A"
      }
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）历史状态变化记录

- **接口**：`GET /api/v1/history/status`
- **参数**：同上，增加`status_type`（可选，如"FaultStatus"）
- **响应**：

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
        "timestamp": "2024-09-29 13:45:12.345",
        "status_type": "FaultStatus",
        "bit_position": 0,
        "old_value": 0,
        "new_value": 1,
        "status_name": "1段电压保护"
      }
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （3）事件记录查询

- **接口**：`GET /api/v1/history/events`
- **参数**：同上，增加`event_type`（可选）
- **响应**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 12,
    "list": [
      {
        "event_time": "2024-09-29 08:00:00.000",
        "event_type": "系统启动",
        "description": "人机界面系统启动成功"
      },
      {
        "event_time": "2024-09-29 08:00:05.123",
        "event_type": "通信连接正常",
        "description": "已与设备建立HMI串口通信"
      }
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 3.5 配置管理接口

**⚠️ 重要说明：**

- **控制参数读取**（0x2200寄存器）已移至WebSocket（见2.5节），通过串口实时读取
- **传感器参数读取**（0x2000寄存器）已移至WebSocket（见2.5节），通过串口实时读取
- API仅提供系统配置查询（从config.ini读取，不涉及串口）

#### 获取系统配置

- **接口**：`GET /api/v1/config/system`
- **功能**：查询config.ini中的配置信息（不涉及串口）
- **响应**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "device_id": "HYP_RPLD_001",
    "device_name": "红岩坪站钢轨电位限制装置",
    "device_ip": "192.168.0.11",
    "system_version": "1.0.0",
    "hmi_serial": {
      "port_name": "COM1",
      "baudrate": 9600,
      "slave_address": "0x10"
    },
    "pscada_serial": {
      "port_name": "COM2",
      "baudrate": 9600,
      "slave_address": "0x5e"
    },
    "websocket": {
      "listen_ip": "0.0.0.0",
      "listen_port": 8765,
      "heartbeat_interval": 10
    },
    "server": {
      "server_ip": "192.168.0.1",
      "port": 8000,
      "upload_interval": 5
    },
    "database": {
      "type": "mysql",
      "host": "127.0.0.1",
      "port": 3306,
      "database": "rpldevice"
    }
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 3.8 数据上传状态接口

#### （1）查询待上传数据统计

- **接口**：`GET /api/v1/upload/pending_stats`
- **响应**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "status_history": {
      "pending": 125,
      "failed": 3,
      "total_retry": 5
    },
    "real_time_data": {
      "pending": 458,
      "failed": 0,
      "total_retry": 0
    },
    "event_records": {
      "pending": 2,
      "failed": 0,
      "total_retry": 0
    },
    "last_upload_time": "2024-09-29 14:29:55.123"
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

#### （2）手动触发数据上传

- **接口**：`POST /api/v1/upload/trigger`
- **请求**：

```json
{
  "data_type": "all"  // all/status_history/real_time_data/event_records
}
```

- **响应**：

```json
{
  "code": 200,
  "msg": "数据上传任务已触发",
  "data": {
    "task_id": "upload_20240929143000",
    "estimated_time": 30  // 预计耗时(秒)
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 3.9 日志查询接口

#### （1）操作日志查询

- **接口**：`GET /api/v1/logs/operations`
- **参数**：

| 参数名     | 类型   | 必选 | 说明                        |
| ---------- | ------ | ---- | --------------------------- |
| start_time | string | 是   | 开始时间                    |
| end_time   | string | 是   | 结束时间                    |
| log_level  | string | 否   | 日志级别（info/warn/error） |
| keyword    | string | 否   | 关键词搜索                  |
| page       | int    | 否   | 页码                        |
| page_size  | int    | 否   | 每页条数                    |

- **响应**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 230,
    "list": [
      {
        "log_time": "2024-09-29 14:25:30.123",
        "log_level": "info",
        "module": "serial_comm",
        "message": "HMI串口读取成功：寄存器0x0000",
        "user_id": "admin001"
      },
      {
        "log_time": "2024-09-29 14:20:15.456",
        "log_level": "warn",
        "module": "websocket",
        "message": "WebSocket连接断开：conn_20240929142000",
        "user_id": null
      }
    ]
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

------

## 四、错误处理规范

### 4.1 API错误响应格式

```json
{
  "code": 400,
  "msg": "参数错误",
  "error": {
    "error_code": "INVALID_PARAM",
    "error_detail": "start_time格式错误，应为YYYY-MM-DD HH:MM:SS",
    "field": "start_time"
  },
  "timestamp": "2024-09-29 14:30:00.123"
}
```

### 4.2 WebSocket错误通知

```json
{
  "type": "error",
  "error_code": 500,
  "error_msg": "串口通信异常：COM1端口断开",
  "timestamp": "2024-09-29 14:30:00.123"
}
```

------

## 五、数据完整性保障

### 5.1 序列号机制

- WebSocket推送数据携带递增序列号
- 前端检测序列号缺失时发送`data_lost_request`
- 后端1秒内补推缺失数据

### 5.2 重传机制

- 指令下发后500ms内未收到响应，自动重发1次
- 数据上传失败自动标记`upload_status=2`，定时重试（最多3次）

### 5.3 数据校验

- 关键指令携带MD5校验码
- 后端校验不通过返回`DATA_TAMPERED`错误

------

## 六、性能优化建议

### 6.1 API查询优化

- 历史数据查询限制时间范围≤7天
- 单次查询最大返回100条记录
- 大数据量查询使用分页+游标

### 6.2 WebSocket推送优化

- 采用"变化驱动"模式，仅推送变化的数据点
- 每30秒推送全量快照，确保前端数据完整性
- 心跳包附带关键状态摘要，减少额外查询

### 6.3 缓存策略

- 系统配置缓存30秒
- 设备状态缓存5秒
- 历史数据查询结果缓存1分钟

------

## 七、安全加固

### 7.1 JWT Token机制

- Token有效期1小时
- 刷新Token需在过期前10分钟内
- Token包含用户权限信息，后端校验权限

### 7.2 API访问控制

- 所有API需携带有效Token
- 控制类接口需`control`或`admin`权限
- 配置修改接口需`admin`权限

### 7.3 指令防重放

- 每个指令携带唯一`request_id`
- 后端缓存已执行的`request_id`（缓存10分钟）
- 重复`request_id`直接返回原执行结果

------

## 八、测试用例示例

### 8.1 WebSocket连接测试

```javascript
// 测试Token过期
ws = new WebSocket('ws://192.168.0.11:8765/ws/device?token=expired_token');
// 预期响应：connect_fail，error_code=401

// 测试心跳超时
// 停止发送心跳30秒
// 预期：收到CONNECTION_LOST通知并断开连接
```

### 8.2 API接口测试

```bash
# 测试未授权访问
curl -X GET http://192.168.0.11:8000/api/v1/device/info
# 预期响应：401 Unauthorized

# 测试参数错误
curl -X GET "http://192.168.0.11:8000/api/v1/history/analog?start_time=invalid"
# 预期响应：400 Bad Request

# 测试正常查询
curl -X GET "http://192.168.0.11:8000/api/v1/history/analog?start_time=2024-09-29%2014:00:00&end_time=2024-09-29%2014:30:00" \
  -H "Authorization: Bearer valid_token"
# 预期响应：200 OK，返回数据列表
```

------

## 完成

此协议文档涵盖了WebSocket实时推送和API接口的完整定义，确保与串口协议、config.ini配置、数据库结构的无缝衔接。
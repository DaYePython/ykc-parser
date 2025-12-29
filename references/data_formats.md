# 云快充协议数据格式定义

## 数据类型

### BCD码 (Binary-Coded Decimal)
- 二进制编码的十进制
- 每个字节表示两位十进制数
- 例如: 0x12 表示十进制的 12
- 桩编码、流水号等使用BCD码

### BIN码 (Binary)
- 二进制码
- **字节序**: 低位在前,高位在后(小端序)
- 例如: 电压2251(0x08CB) 存储为 `CB 08`
- 状态码、电压、电流、电量等使用BIN码

### ASCII码
- 美国信息交换标准代码
- 版本号、字符串信息使用ASCII码
- 不足位数补0x00
- 例如: "v4.1.50" 编码为 `76 34 2E 31 2E 35 30 00`

## 数值处理规则

### 小数处理
协议中小数值均乘倍率(保留小数点位数)上送平台

**示例**:
- 电压 225.1V (保留一位小数) → 2251 → 0x08CB
- 电量 123.4567度 (保留四位小数) → 1234567 → 0x0012D687

### 温度处理
温度值有偏移量 **-50℃**

**示例**:
- 实际温度 25℃ → 上送值 75 (0x4B)
- 实际温度 -10℃ → 上送值 40 (0x28)
- 上送值 0 → 实际温度 -50℃

### BCD码转换

**编码示例**:
```python
# 数字 123456 转 BCD码
# 结果: 0x12 0x34 0x56

def int_to_bcd(num: int, byte_len: int) -> bytes:
    """整数转BCD码"""
    bcd_str = f"{num:0{byte_len*2}d}"
    return bytes([int(bcd_str[i:i+2], 16) for i in range(0, len(bcd_str), 2)])
```

**解码示例**:
```python
# BCD码 0x12 0x34 0x56 转数字
# 结果: 123456

def bcd_to_int(bcd_bytes: bytes) -> int:
    """BCD码转整数"""
    return int(''.join([f"{b:02X}" for b in bcd_bytes]))
```

### BIN码转换(小端序)

**编码示例**:
```python
# 数字 2251 (0x08CB) 转2字节BIN码
# 结果: 0xCB 0x08 (低字节在前)

def int_to_bin_le(num: int, byte_len: int) -> bytes:
    """整数转小端BIN码"""
    return num.to_bytes(byte_len, byteorder='little')
```

**解码示例**:
```python
# BIN码 0xCB 0x08 转数字
# 结果: 2251

def bin_le_to_int(bin_bytes: bytes) -> int:
    """小端BIN码转整数"""
    return int.from_bytes(bin_bytes, byteorder='little')
```

## 特殊值规则

### 置零规则
以下情况相关字段必须置零:
- **待机状态**: 电压、电流、SOC、温度、充电时间、电量、金额
- **无法获取**: 枪线编码、SIM卡号
- **交流桩**: SOC、剩余时间、电池温度

### 不足位补零
- BCD码桩编码不足7字节补前导零
- ASCII码版本号不足8字节补尾部0x00
- BCD码SIM卡不足10字节补前导零

## 常见字段定义

### 状态码 (1字节 BIN)
- 0x00: 离线
- 0x01: 故障
- 0x02: 空闲
- 0x03: 充电

### 桩类型 (1字节 BIN)
- 0x00: 直流桩
- 0x01: 交流桩

### 加密标志 (1字节 BIN)
- 0x00: 不加密
- 0x01: 3DES加密

### 网络链接类型 (1字节 BIN)
- 0x00: SIM卡
- 0x01: LAN
- 0x02: WAN
- 0x03: 其他

### 运营商 (1字节 BIN)
- 0x00: 移动
- 0x02: 电信
- 0x03: 联通
- 0x04: 其他

## CP56Time2a时间格式

7字节时间格式:

| 字节 | 内容 | 说明 |
|------|------|------|
| Byte1 | Milliseconds(D7-D0) | 毫秒低字节 |
| Byte2 | Milliseconds(D15-D8) | 毫秒高字节 |
| Byte3 | IV(D7) RES1 Minutes(D5-D0) | 分钟 |
| Byte4 | SU(D7) RES2 Hours(D4-D0) | 小时 |
| Byte5 | DAY of WEEK DAY of MONTH(D4-D0) | 星期和日期 |
| Byte6 | RES3 Month(D3-D0) | 月份 |
| Byte7 | RES4 Years(D6-D0) | 年份 |

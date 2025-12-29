# 云快充报文解析器

一个用于解析云快充充电桩通信协议报文的Python工具，支持云快充协议V1.6。

## 功能特性

- **完整报文解析**: 解析起始标志、数据长度、序列号、加密标志、帧类型、消息体、CRC校验等完整报文结构
- **CRC16校验**: 基于Modbus算法的CRC16校验，即使校验失败也继续解析
- **多种帧类型支持**: 支持登录认证、实时数据、心跳包等多种帧类型的详细解析
- **数据类型转换**: 自动处理BCD码、BIN码、ASCII码等多种数据格式
- **错误诊断**: 提供详细的错误信息和容错处理
- **标准JSON输出**: 返回结构化的JSON格式数据，便于集成

## 支持的帧类型

| 帧类型 | 说明 | 解析状态 |
|--------|------|---------|
| 0x01 | 充电桩登录认证 | ✅ 完整解析 |
| 0x02 | 登录认证应答 | ✅ 完整解析 |
| 0x12 | 读取实时监测数据 | ✅ 完整解析 |
| 0x13 | 上传实时监测数据 | ✅ 完整解析 |
| 其他 | 其他帧类型 | ⚠️ 返回原始数据 |

## 安装要求

- Python 3.6+
- 无需额外依赖库

## 快速开始

### 基本使用

```bash
python scripts/parse_ykc.py "68 22 0000 00 01 55031412782305 00 02 0F 56342E312E353000 01 01010101010101010101 04 675A"
```

### 在代码中使用

```python
from scripts.parse_ykc import YKCParser

# 创建解析器实例
parser = YKCParser()

# 解析报文
hex_string = "68 22 0000 00 01 55031412782305 00 02 0F 56342E312E353000 01 01010101010101010101 04 675A"
result = parser.parse(hex_string)

# 输出结果
print(result)
```

## 使用示例

### 示例1: 解析登录认证报文

**输入报文:**
```
68 22 0000 00 01 55031412782305 00 02 0F 56342E312E353000 01 01010101010101010101 04 675A
```

**解析结果:**
```json
{
  "code": 200,
  "msg": "解析成功",
  "start_flag": "0x68",
  "data_length": 34,
  "sequence_number": 0,
  "encrypt_flag": "0x00",
  "is_encrypted": false,
  "frame_type": "0x01",
  "frame_type_name": "充电桩登录认证",
  "body_length": 28,
  "crc16_received": "0x675A",
  "crc16_calculated": "0x675A",
  "crc16_valid": true,
  "body_data": {
    "pile_code": "55031412782305",
    "pile_type": "直流桩",
    "gun_count": 2,
    "protocol_version": "v1.5",
    "program_version": "v4.1.50",
    "network_type": "LAN",
    "sim_card": "01010101010101010101",
    "operator": "其他"
  }
}
```

### 示例2: 解析实时监测数据

**输入报文:**
```
68 40 1A03 00 13 01 01 00 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 00000000 00000000 00 00 00 00 00 00 9DAC
```

**解析结果:**
```json
{
  "code": 200,
  "msg": "解析成功",
  "frame_type": "0x13",
  "frame_type_name": "上传实时监测数据",
  "body_data": {
    "gun_no": 1,
    "work_status": "空闲中",
    "soc": 0,
    "voltage": 0.0,
    "current": 0.0,
    "charged_kwh": 0.0,
    "charged_duration": 0,
    "reserved": "..."
  }
}
```

## 项目结构

```
ykc-parser/
├── scripts/
│   ├── parse_ykc.py          # 主解析脚本
│   ├── crc16.py              # CRC16校验模块
│   ├── frame_parsers.py      # 帧类型解析器
│   └── parser_factory.py     # 解析器工厂
├── references/
│   ├── docs/                 # 完整协议文档
│   ├── protocol_structure.md # 协议结构快速参考
│   ├── data_formats.md       # 数据格式定义
│   └── frame_types.md        # 帧类型定义表
├── .claude-plugin/
│   └── marketplace.json      # Claude技能配置
├── test_all_frames.py        # 测试脚本
├── SKILL.md                  # 技能说明文档
└── README.md                 # 本文件
```

## 参考文档

项目包含完整的云快充协议V1.6参考文档：

- **协议基础**: `references/docs/02-协议基础/`
  - 通信协议结构
  - 应用层报文帧格式
  - 数据格式定义
  - 帧类型定义表

- **业务流程**: `references/docs/`
  - 登录认证流程
  - 心跳包协议
  - 实时数据上报
  - 充电启动/停止流程
  - 平台设置、远程维护等

- **附录**: `references/docs/11-附录/`
  - CRC16校验计算方法
  - 充电停止原因代码表
  - 协议注意事项

## 技术细节

### CRC16校验

- 算法: Modbus CRC16（多项式0x180D）
- 校验范围: 序列号域到消息体结束
- 字节序: 小端序（低字节在前）
- 初始值: 0xFFFF
- 实现方式: 查表法

### 数据类型

| 类型 | 说明 | 转换方式 |
|------|------|---------|
| BCD码 | 每字节表示两位十进制数 | 直接转十六进制字符串 |
| BIN小端 | 小端序二进制 | `int.from_bytes(byteorder='little')` |
| ASCII码 | ASCII字符串 | `decode('ascii')` 并移除尾部0x00 |

### 精度处理

- 电压/电流: 精确到0.1，除以10
- 电量/金额: 精确到0.0001，除以10000
- 温度: 整数偏移-50℃

## 错误处理

解析器提供完善的错误处理机制：

- **CRC校验失败**: 标注警告但继续解析
- **报文长度不匹配**: 尽可能解析已有字段
- **数据类型错误**: 返回错误信息并标注位置
- **未知帧类型**: 返回原始十六进制数据

## 作为Claude技能使用

本项目可作为Claude Code技能使用，让Claude自动解析云快充报文。

### 安装方法

#### 方法1: 从Claude Marketplace安装（推荐）

1. 首先注册本仓库到Claude Code的Marketplace：
```
/plugin marketplace add DaYePython/ykc-parser
```

2. 然后在Claude Code中打开Marketplace：
```
/marketplace
```

3. 搜索 `ykc-parser` 或 `云快充`，点击安装即可

这是最简单的安装方式，Claude会自动下载和配置技能。只需在首次使用时注册一次marketplace。

#### 方法2: 从GitHub克隆

1. 打开终端，进入Claude技能目录：
```bash
cd ~/.claude/skills
```

2. 克隆本仓库：
```bash
git clone https://github.com/DaYePython/ykc-parser.git
```

3. 重启Claude Code或重新加载技能列表

#### 方法3: 手动下载

1. 下载本仓库的ZIP文件：
   - 访问 https://github.com/DaYePython/ykc-parser
   - 点击 "Code" > "Download ZIP"

2. 解压到Claude技能目录：
   - Windows: `C:\Users\<你的用户名>\.claude\skills\ykc-parser`
   - macOS/Linux: `~/.claude/skills/ykc-parser`

3. 重启Claude Code

### 验证安装

安装完成后，在Claude Code中输入：
```
/skills
```
查看技能列表中是否有`ykc-parser`。

### 使用示例

安装成功后，你可以直接在Claude Code中使用：

```
帮我解析这个云快充报文: 68 22 0000 00 01 55031412782305 00 02 0F 56342E312E353000 01 01010101010101010101 04 675A
```

或者明确调用技能：
```
使用ykc-parser技能解析报文: 68 40 1A03 00 13 ...
```

Claude会自动：
1. 识别这是云快充报文解析任务
2. 调用解析脚本
3. 返回结构化的JSON结果
4. 解释报文内容


## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: https://github.com/DaYePython/ykc-parser/issues
- 项目地址: https://github.com/DaYePython/ykc-parser

---

**注意**: 本项目用于云快充充电桩通信协议的学习和开发，请遵守相关协议规范和使用条款。

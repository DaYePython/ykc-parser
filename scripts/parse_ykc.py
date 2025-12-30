#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云快充协议解析器 - 重构版本
使用策略模式 + 工厂模式
"""

import sys
import json
from typing import Dict, List, Any
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from crc16 import calculate_crc16
from parser_factory import FrameParserFactory


class ParserContext:
    """解析器上下文 - 提供通用辅助方法"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def bcd_to_str(self, bcd_bytes: bytes) -> str:
        """BCD码转字符串"""
        try:
            return ''.join([f"{b:02X}" for b in bcd_bytes])
        except Exception:
            return "无效BCD"

    def ascii_to_str(self, ascii_bytes: bytes) -> str:
        """ASCII码转字符串"""
        try:
            text = ascii_bytes.rstrip(b'\x00').decode('ascii')
            if not all(32 <= ord(c) < 127 or c == '\0' for c in ascii_bytes.decode('ascii', errors='ignore')):
                self.warnings.append(f"ASCII字段包含非ASCII字符: {ascii_bytes.hex()}")
            return text
        except Exception:
            self.warnings.append(f"ASCII解码失败: {ascii_bytes.hex()}")
            return ascii_bytes.hex().upper()

    def parse_cp56time2a(self, time_bytes: bytes) -> str:
        """解析CP56Time2a时间格式 (7字节)"""
        if len(time_bytes) < 7:
            return "无效时间"

        try:
            millisec = int.from_bytes(time_bytes[0:2], byteorder='little')
            minute = time_bytes[2] & 0x3F
            hour = time_bytes[3] & 0x1F
            day = time_bytes[4] & 0x1F
            month = time_bytes[5] & 0x0F
            year = 2000 + (time_bytes[6] & 0x7F)

            seconds = millisec // 1000
            millis = millisec % 1000

            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{seconds:02d}.{millis:03d}"
        except Exception as e:
            self.warnings.append(f"CP56Time2a解析失败: {str(e)}")
            return "无效时间"

    def parse_fault_bits(self, fault: int) -> List[str]:
        """解析硬件故障位"""
        fault_names = [
            "急停按钮动作", "无可用整流模块", "出风口温度过高", "交流防雷故障",
            "DC20通信中断", "FC08通信中断", "电度表通信中断", "读卡器通信中断",
            "RC10通信中断", "风扇调速板故障", "直流熔断器故障", "高压接触器故障",
            "门打开"
        ]

        faults = []
        for i, name in enumerate(fault_names):
            if fault & (1 << i):
                faults.append(name)

        return faults if faults else ["无故障"]


class YKCProtocolParser:
    """云快充协议解析器主类"""

    # 帧类型名称映射
    FRAME_TYPES = {
        0x01: "充电桩登录认证",
        0x02: "登录认证应答",
        0x03: "充电桩心跳包",
        0x04: "心跳包应答",
        0x05: "计费模型验证请求",
        0x06: "计费模型验证应答",
        0x09: "充电桩计费模型请求",
        0x0A: "计费模型请求应答",
        0x12: "读取实时监测数据",
        0x13: "上传实时监测数据",
        0x15: "充电握手",
        0x17: "参数配置",
        0x19: "充电结束",
        0x1B: "错误报文",
        0x1D: "充电阶段BMS中止",
        0x21: "充电阶段充电机中止",
        0x23: "BMS需求/充电机输出",
        0x25: "BMS信息",
        0x31: "充电桩主动申请启动",
        0x32: "确认启动充电",
        0x33: "远程启机回复",
        0x34: "远程控制启机",
        0x35: "远程停机回复",
        0x36: "远程停机",
        0x3B: "交易记录",
        0x40: "交易记录确认",
        0x41: "余额更新应答",
        0x42: "远程账户余额更新",
        0x43: "离线卡数据同步应答",
        0x44: "离线卡数据同步",
        0x45: "离线卡数据清除应答",
        0x46: "离线卡数据清除",
        0x47: "离线卡数据查询应答",
        0x48: "离线卡数据查询",
        0x51: "工作参数设置应答",
        0x52: "工作参数设置",
        0x55: "对时设置应答",
        0x56: "对时设置",
        0x57: "计费模型应答",
        0x58: "计费模型设置",
        0x61: "地锁数据上送",
        0x62: "遥控地锁升降",
        0x63: "充电桩返回数据",
        0x91: "远程重启应答",
        0x92: "远程重启",
        0x93: "远程更新应答",
        0x94: "远程更新",
        0xA1: "主动申请并充",
        0xA2: "确认并充启动",
        0xA3: "远程并充启机回复",
        0xA4: "远程控制并充启机",
        0xF0: "后台下发二维码前缀指令",
        0xF1: "桩应答返回下发二维码前缀指令",
    }

    def __init__(self):
        self.context = ParserContext()

    def parse(self, hex_str: str) -> Dict[str, Any]:
        """
        解析报文

        Args:
            hex_str: 十六进制字符串,可以有空格分隔

        Returns:
            解析结果JSON
        """
        # 重置上下文
        self.context.errors = []
        self.context.warnings = []

        try:
            # 清理输入并转换为bytes
            hex_str = hex_str.replace(" ", "").replace("\n", "").strip()
            if len(hex_str) % 2 != 0:
                return self._error_response("报文长度必须是偶数个十六进制字符")

            data = bytes.fromhex(hex_str)

            # 基本长度检查
            if len(data) < 8:
                return self._error_response(f"报文长度过短: {len(data)}字节,最少需要8字节")

            # 解析报文结构
            result = self._parse_structure(data)

            # 返回结果
            if self.context.errors:
                result["code"] = 500
                result["msg"] = "解析失败: " + "; ".join(self.context.errors[:3])
                result["errors"] = self.context.errors
            else:
                result["code"] = 200
                result["msg"] = "解析成功"

            if self.context.warnings:
                result["warnings"] = self.context.warnings

            return result

        except ValueError as e:
            return self._error_response(f"十六进制字符串格式错误: {str(e)}")
        except Exception as e:
            return self._error_response(f"解析异常: {str(e)}")

    def _parse_structure(self, data: bytes) -> Dict[str, Any]:
        """解析报文结构"""
        result = {}

        # 1. 起始标志
        start_flag = data[0]
        result["start_flag"] = f"0x{start_flag:02X}"
        if start_flag != 0x68:
            self.context.errors.append(f"起始标志错误: 期望0x68, 实际0x{start_flag:02X}")

        # 2. 数据长度
        data_len = data[1]
        result["data_length"] = data_len
        expected_total_len = 1 + 1 + data_len + 2
        if len(data) != expected_total_len:
            self.context.errors.append(
                f"报文长度不匹配: 期望{expected_total_len}字节, 实际{len(data)}字节"
            )

        # 3. 序列号(小端序)
        if len(data) >= 4:
            seq_num = int.from_bytes(data[2:4], byteorder='little')
            result["sequence_number"] = seq_num
        else:
            self.context.errors.append("报文过短,无法读取序列号")
            return result

        # 4. 加密标志
        if len(data) >= 5:
            encrypt_flag = data[4]
            result["encrypt_flag"] = f"0x{encrypt_flag:02X}"
            result["is_encrypted"] = encrypt_flag == 0x01
        else:
            self.context.errors.append("报文过短,无法读取加密标志")
            return result

        # 5. 帧类型
        if len(data) >= 6:
            frame_type = data[5]
            result["frame_type"] = f"0x{frame_type:02X}"
            result["frame_type_name"] = self.FRAME_TYPES.get(
                frame_type, "未知帧类型"
            )
            if frame_type not in self.FRAME_TYPES:
                self.context.warnings.append(f"未知的帧类型: 0x{frame_type:02X}")
        else:
            self.context.errors.append("报文过短,无法读取帧类型")
            return result

        # 6. 消息体
        body_len = data_len - 4  # 数据长度 - (序列号2 + 加密标志1 + 帧类型1)
        if body_len < 0:
            self.context.errors.append(f"数据长度字段错误: {data_len}")
            return result

        body_start = 6
        body_end = body_start + body_len

        if len(data) < body_end:
            self.context.errors.append(
                f"报文长度不足,无法读取完整消息体: 需要{body_end}字节, 实际{len(data)}字节"
            )
            body = data[body_start:]
        else:
            body = data[body_start:body_end]

        result["body_length"] = len(body)
        result["body_hex"] = body.hex().upper()

        # 7. CRC校验
        if len(data) >= body_end + 2:
            crc_bytes = data[body_end:body_end + 2]
            # 接收到的CRC字节序与计算值顺序相反，按大端解析以匹配计算结果
            crc_received = int.from_bytes(crc_bytes, byteorder='big')
            result["crc16_received"] = f"0x{crc_received:04X}"

            # 计算CRC(从序列号到消息体)
            crc_data = data[2:body_end]
            crc_calculated = calculate_crc16(crc_data)
            result["crc16_calculated"] = f"0x{crc_calculated:04X}"

            # CRC校验
            if crc_calculated != crc_received:
                self.context.warnings.append(
                    f"CRC16校验失败: 期望0x{crc_received:04X}, 计算0x{crc_calculated:04X}"
                )
                result["crc16_valid"] = False
            else:
                result["crc16_valid"] = True
        else:
            self.context.errors.append("报文过短,无法读取CRC16校验码")
            result["crc16_valid"] = False

        # 8. 解析消息体 - 使用工厂模式
        if body:
            try:
                parser = FrameParserFactory.get_parser(frame_type, self.context)
                body_data = parser.parse(body)
                result["body_data"] = body_data
            except Exception as e:
                self.context.errors.append(f"消息体解析失败: {str(e)}")
                result["body_data"] = None

        return result

    def _error_response(self, msg: str) -> Dict[str, Any]:
        """返回错误响应"""
        return {
            "code": 500,
            "msg": msg,
            "data": None
        }


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "code": 500,
            "msg": "用法: python parse_ykc_v2.py <hex_string>",
            "data": None
        }, ensure_ascii=False, indent=2))
        return

    hex_input = ' '.join(sys.argv[1:])
    parser = YKCProtocolParser()
    result = parser.parse(hex_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

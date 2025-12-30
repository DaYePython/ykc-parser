#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云快充协议帧解析器 - 策略模式实现
每个帧类型都有独立的解析器类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class FrameParser(ABC):
    """帧解析器基类"""

    def __init__(self, context):
        """
        初始化解析器

        Args:
            context: 解析上下文，包含辅助方法和错误/警告列表
        """
        self.context = context

    @abstractmethod
    def parse(self, body: bytes) -> Dict[str, Any]:
        """
        解析消息体

        Args:
            body: 消息体字节数据

        Returns:
            解析后的字典数据
        """
        pass

    @property
    @abstractmethod
    def expected_min_length(self) -> int:
        """返回消息体的最小预期长度"""
        pass

    def validate_length(self, body: bytes) -> bool:
        """验证消息体长度"""
        if len(body) < self.expected_min_length:
            self.context.errors.append(
                f"{self.__class__.__name__} 消息体长度不足: "
                f"需要{self.expected_min_length}字节, 实际{len(body)}字节"
            )
            return False
        return True


# ==================== 注册心跳类 ====================

class LoginParser(FrameParser):
    """充电桩登录认证 (0x01)"""

    @property
    def expected_min_length(self) -> int:
        return 28

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 桩编码 (BCD 7字节)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 桩类型 (BIN 1字节)
        pile_type = body[offset]
        result["pile_type"] = "直流桩" if pile_type == 0 else "交流桩"
        result["pile_type_code"] = pile_type
        offset += 1

        # 充电枪数量 (BIN 1字节)
        result["gun_count"] = body[offset]
        offset += 1

        # 通信协议版本 (BIN 1字节)
        protocol_version = body[offset]
        result["protocol_version"] = f"v{protocol_version / 10:.1f}"
        offset += 1

        # 程序版本 (ASCII 8字节)
        result["program_version"] = self.context.ascii_to_str(body[offset:offset+8])
        offset += 8

        # 网络链接类型 (BIN 1字节)
        network_type = body[offset]
        network_types = {0: "SIM卡", 1: "LAN", 2: "WAN", 3: "其他"}
        result["network_type"] = network_types.get(network_type, f"未知({network_type})")
        offset += 1

        # SIM卡 (BCD 10字节)
        result["sim_card"] = self.context.bcd_to_str(body[offset:offset+10])
        offset += 10

        # 运营商 (BIN 1字节)
        operator = body[offset]
        operators = {0: "移动", 2: "电信", 3: "联通", 4: "其他"}
        result["operator"] = operators.get(operator, f"未知({operator})")

        return result


class LoginResponseParser(FrameParser):
    """登录认证应答 (0x02)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        login_result = body[7]
        result["login_result"] = "登录成功" if login_result == 0 else "登录失败"
        result["login_result_code"] = login_result

        return result


# ==================== 实时数据类 ====================

class ReadRealtimeParser(FrameParser):
    """读取实时监测数据 (0x12)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        result["gun_number"] = f"{body[7]:02X}"

        return result


class RealtimeDataParser(FrameParser):
    """上传实时监测数据 (0x13)"""

    @property
    def expected_min_length(self) -> int:
        return 58

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 交易流水号 (BCD 16字节)
        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16

        # 桩编码 (BCD 7字节)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 枪号 (BCD 1字节)
        result["gun_number"] = f"{body[offset]:02X}"
        offset += 1

        # 状态 (BIN 1字节)
        status = body[offset]
        statuses = {0: "离线", 1: "故障", 2: "空闲", 3: "充电"}
        result["status"] = statuses.get(status, f"未知({status})")
        result["status_code"] = status
        offset += 1

        # 枪是否归位 (BIN 1字节)
        gun_returned = body[offset]
        result["gun_returned"] = {0: "否", 1: "是", 2: "未知"}.get(gun_returned, "未知")
        offset += 1

        # 是否插枪 (BIN 1字节)
        gun_plugged = body[offset]
        result["gun_plugged"] = "是" if gun_plugged == 1 else "否"
        offset += 1

        # 输出电压 (BIN 2字节小端,精确到0.1V)
        voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["output_voltage"] = voltage / 10.0
        offset += 2

        # 输出电流 (BIN 2字节小端,精确到0.1A)
        current = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["output_current"] = current / 10.0
        offset += 2

        # 枪线温度 (BIN 1字节,偏移-50℃)
        result["cable_temperature"] = body[offset] - 50
        offset += 1

        # 枪线编码 (BIN 8字节)
        result["cable_code"] = body[offset:offset+8].hex().upper()
        offset += 8

        # SOC (BIN 1字节)
        result["soc"] = body[offset]
        offset += 1

        # 电池组最高温度 (BIN 1字节,偏移-50℃)
        result["battery_max_temperature"] = body[offset] - 50
        offset += 1

        # 累计充电时间 (BIN 2字节小端,分钟)
        charge_time = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["total_charge_time_minutes"] = charge_time
        offset += 2

        # 剩余时间 (BIN 2字节小端,分钟)
        remain_time = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["remaining_time_minutes"] = remain_time
        offset += 2

        # 充电度数 (BIN 4字节小端,精确到0.0001度)
        energy = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["charged_energy_kwh"] = energy / 10000.0
        offset += 4

        # 计损充电度数 (BIN 4字节小端,精确到0.0001度)
        energy_loss = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["charged_energy_with_loss_kwh"] = energy_loss / 10000.0
        offset += 4

        # 已充金额 (BIN 4字节小端,精确到0.0001元)
        amount = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["charged_amount_yuan"] = amount / 10000.0
        offset += 4

        # 硬件故障 (BIN 2字节小端,位标志)
        fault = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["hardware_fault_code"] = f"0x{fault:04X}"
        result["hardware_faults"] = self.context.parse_fault_bits(fault)

        return result


class ChargingHandshakeParser(FrameParser):
    """充电握手 (0x15)"""

    @property
    def expected_min_length(self) -> int:
        return 65

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 交易流水号 (BCD 16字节)
        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16

        # 桩编号 (BCD 7字节)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 枪号 (BCD 1字节)
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        # BMS通信协议版本号 (BIN 3字节)
        version_bytes = body[offset:offset+3]
        result["bms_protocol_version"] = f"V{version_bytes[2]}.{int.from_bytes(version_bytes[0:2], byteorder='little')}"
        offset += 3

        # BMS电池类型 (BIN 1字节)
        battery_type = body[offset]
        battery_types = {
            0x01: "铅酸电池", 0x02: "氢电池", 0x03: "磷酸铁锂电池",
            0x04: "锰酸锂电池", 0x05: "钴酸锂电池", 0x06: "三元材料电池",
            0x07: "聚合物锂离子电池", 0x08: "钛酸锂电池", 0xFF: "其他"
        }
        result["bms_battery_type"] = battery_types.get(battery_type, f"未知({battery_type})")
        result["bms_battery_type_code"] = battery_type
        offset += 1

        # BMS整车动力蓄电池系统额定容量 (BIN 2字节, 0.1Ah/位)
        capacity = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_rated_capacity_ah"] = capacity / 10.0
        offset += 2

        # BMS整车动力蓄电池系统额定总电压 (BIN 2字节, 0.1V/位)
        voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_rated_voltage_v"] = voltage / 10.0
        offset += 2

        # BMS电池生产厂商名称 (ASCII 4字节)
        result["bms_manufacturer"] = self.context.ascii_to_str(body[offset:offset+4])
        offset += 4

        # BMS电池组序号 (BIN 4字节)
        result["bms_battery_serial"] = body[offset:offset+4].hex().upper()
        offset += 4

        # BMS电池组生产日期 (BIN 3字节: 年/月/日)
        year = body[offset] + 1985
        month = body[offset+1]
        day = body[offset+2]
        result["bms_production_date"] = f"{year:04d}-{month:02d}-{day:02d}"
        offset += 3

        # BMS电池组充电次数 (BIN 3字节)
        charge_times = int.from_bytes(body[offset:offset+3], byteorder='little')
        result["bms_charge_times"] = charge_times
        offset += 3

        # BMS电池组产权标识 (BIN 1字节)
        ownership = body[offset]
        result["bms_ownership"] = "租赁" if ownership == 0 else "车自有"
        result["bms_ownership_code"] = ownership
        offset += 1

        # 预留位 (BIN 1字节)
        offset += 1

        # BMS车辆识别码 (BIN 17字节 VIN码)
        result["bms_vin"] = self.context.ascii_to_str(body[offset:offset+17])
        offset += 17

        # BMS软件版本号 (BIN 8字节)
        ver_bytes = body[offset:offset+8]
        result["bms_software_version"] = ver_bytes.hex().upper()

        return result


# ==================== 运营交互类 ====================

class TransactionRecordParser(FrameParser):
    """交易记录 (0x3B)"""

    @property
    def expected_min_length(self) -> int:
        return 132

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 交易流水号 (BCD 16字节)
        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16

        # 桩编号 (BCD 7字节)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 枪号 (BCD 1字节)
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        # 开始时间 (BIN 7字节 CP56Time2a)
        result["start_time"] = self.context.parse_cp56time2a(body[offset:offset+7])
        offset += 7

        # 结束时间 (BIN 7字节 CP56Time2a)
        result["end_time"] = self.context.parse_cp56time2a(body[offset:offset+7])
        offset += 7

        # 尖/峰/平/谷 电价、电量、金额
        for period_name in ["sharp", "peak", "flat", "valley"]:
            # 单价 (BIN 4字节小端, 精确到0.00001元)
            price = int.from_bytes(body[offset:offset+4], byteorder='little')
            result[f"{period_name}_unit_price"] = price / 100000.0
            offset += 4

            # 电量 (BIN 4字节小端, 精确到0.0001度)
            energy = int.from_bytes(body[offset:offset+4], byteorder='little')
            result[f"{period_name}_energy_kwh"] = energy / 10000.0
            offset += 4

            # 计损电量 (BIN 4字节小端, 精确到0.0001度)
            energy_loss = int.from_bytes(body[offset:offset+4], byteorder='little')
            result[f"{period_name}_energy_with_loss_kwh"] = energy_loss / 10000.0
            offset += 4

            # 金额 (BIN 4字节小端, 精确到0.0001元)
            amount = int.from_bytes(body[offset:offset+4], byteorder='little')
            result[f"{period_name}_amount_yuan"] = amount / 10000.0
            offset += 4

        # 电表总起值 (BIN 5字节小端, 精确到0.0001度)
        meter_start = int.from_bytes(body[offset:offset+5], byteorder='little')
        result["meter_start_value_kwh"] = meter_start / 10000.0
        offset += 5

        # 电表总止值 (BIN 5字节小端, 精确到0.0001度)
        meter_end = int.from_bytes(body[offset:offset+5], byteorder='little')
        result["meter_end_value_kwh"] = meter_end / 10000.0
        offset += 5

        # 总电量 (BIN 4字节小端, 精确到0.0001度)
        total_energy = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["total_energy_kwh"] = total_energy / 10000.0
        offset += 4

        # 计损总电量 (BIN 4字节小端, 精确到0.0001度)
        total_energy_loss = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["total_energy_with_loss_kwh"] = total_energy_loss / 10000.0
        offset += 4

        # 消费金额 (BIN 4字节小端, 精确到0.0001元)
        total_amount = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["total_amount_yuan"] = total_amount / 10000.0
        offset += 4

        # VIN码 (ASCII 17字节)
        result["vin_code"] = self.context.ascii_to_str(body[offset:offset+17])
        offset += 17

        # 交易标识 (BIN 1字节)
        trade_type = body[offset]
        trade_types = {
            0x01: "app启动", 0x02: "卡启动",
            0x04: "离线卡启动", 0x05: "VIN码启动充电"
        }
        result["trade_type"] = trade_types.get(trade_type, f"未知({trade_type})")
        result["trade_type_code"] = trade_type
        offset += 1

        # 交易日期时间 (BIN 7字节 CP56Time2a)
        result["trade_datetime"] = self.context.parse_cp56time2a(body[offset:offset+7])
        offset += 7

        # 停止原因 (BIN 1字节)
        stop_reason = body[offset]
        result["stop_reason_code"] = stop_reason
        result["stop_reason"] = f"停止原因代码: {stop_reason}"
        offset += 1

        # 物理卡号 (BIN 8字节)
        card_number = int.from_bytes(body[offset:offset+8], byteorder='little')
        result["physical_card_number"] = f"{card_number:016X}" if card_number > 0 else "无卡"

        return result


class TransactionConfirmParser(FrameParser):
    """交易记录确认 (0x40)"""

    @property
    def expected_min_length(self) -> int:
        return 17

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["transaction_id"] = self.context.bcd_to_str(body[0:16])
        confirm_result = body[16]
        result["confirm_result"] = "上传成功" if confirm_result == 0x00 else "非法账单"
        result["confirm_result_code"] = confirm_result

        return result


class BalanceUpdateRequestParser(FrameParser):
    """远程账户余额更新 (0x42)"""

    @property
    def expected_min_length(self) -> int:
        return 20

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        card_number = int.from_bytes(body[offset:offset+8], byteorder='little')
        result["physical_card_number"] = f"{card_number:016X}" if card_number > 0 else "无需校验"
        offset += 8

        balance = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["new_balance_yuan"] = balance / 100.0

        return result


class BalanceUpdateResponseParser(FrameParser):
    """余额更新应答 (0x41)"""

    @property
    def expected_min_length(self) -> int:
        return 16

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        card_number = int.from_bytes(body[offset:offset+8], byteorder='little')
        result["physical_card_number"] = f"{card_number:016X}" if card_number > 0 else "无"
        offset += 8

        modify_result = body[offset]
        modify_results = {
            0x00: "修改成功",
            0x01: "设备编号错误",
            0x02: "卡号错误"
        }
        result["modify_result"] = modify_results.get(modify_result, f"未知({modify_result})")
        result["modify_result_code"] = modify_result

        return result


# ==================== 默认解析器 ====================

class DefaultParser(FrameParser):
    """默认解析器 - 用于未实现详细解析的帧类型"""

    @property
    def expected_min_length(self) -> int:
        return 0

    def parse(self, body: bytes) -> Dict[str, Any]:
        return {
            "raw": body.hex().upper(),
            "note": "该帧类型暂未实现详细解析"
        }


# ==================== 更多BMS解析器 ====================

class ParameterConfigParser(FrameParser):
    """参数配置 (0x17)"""

    @property
    def expected_min_length(self) -> int:
        return 41

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        max_cell_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_max_cell_voltage_v"] = max_cell_voltage / 100.0
        offset += 2

        max_current = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_max_charge_current_a"] = (max_current / 10.0) - 400
        offset += 2

        total_energy = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_rated_energy_kwh"] = total_energy / 10.0
        offset += 2

        max_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_max_total_voltage_v"] = max_voltage / 10.0
        offset += 2

        max_temp = body[offset]
        result["bms_max_temperature_celsius"] = max_temp - 50
        offset += 1

        soc = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_soc_percent"] = soc / 10.0
        offset += 2

        current_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_current_voltage_v"] = current_voltage / 10.0
        offset += 2

        charger_max_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_max_output_voltage_v"] = charger_max_voltage / 10.0
        offset += 2

        charger_min_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_min_output_voltage_v"] = charger_min_voltage / 10.0
        offset += 2

        charger_max_current = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_max_output_current_a"] = (charger_max_current / 10.0) - 400
        offset += 2

        charger_min_current = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_min_output_current_a"] = (charger_min_current / 10.0) - 400

        return result


class ChargingEndParser(FrameParser):
    """充电结束 (0x19)"""

    @property
    def expected_min_length(self) -> int:
        return 35

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        result["bms_stop_soc_percent"] = body[offset]
        offset += 1

        min_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_min_cell_voltage_v"] = min_voltage / 100.0
        offset += 2

        max_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_max_cell_voltage_v"] = max_voltage / 100.0
        offset += 2

        result["bms_min_temperature_celsius"] = body[offset] - 50
        offset += 1

        result["bms_max_temperature_celsius"] = body[offset] - 50
        offset += 1

        charge_time = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_total_time_minutes"] = charge_time
        offset += 2

        output_energy = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_output_energy_kwh"] = output_energy / 10.0
        offset += 2

        charger_number = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["charger_number"] = charger_number

        return result


class ErrorMessageParser(FrameParser):
    """错误报文 (0x1B)"""

    @property
    def expected_min_length(self) -> int:
        return 32

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        error_bytes = body[offset:offset+8]
        result["error_bytes_hex"] = error_bytes.hex().upper()
        result["errors"] = [f"错误字节{i+1}: 0x{b:02X}" for i, b in enumerate(error_bytes)]

        return result


class BMSStopParser(FrameParser):
    """充电阶段BMS中止 (0x1D)"""

    @property
    def expected_min_length(self) -> int:
        return 28

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        stop_reason = body[offset]
        result["bms_stop_reason_code"] = stop_reason
        result["bms_stop_reason"] = self._parse_bms_stop_reason(stop_reason)
        offset += 1

        fault_reason = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_fault_reason_code"] = fault_reason
        result["bms_fault_reason"] = self._parse_bms_fault_reason(fault_reason)
        offset += 2

        error_reason = body[offset]
        result["bms_error_reason_code"] = error_reason
        result["bms_error_reason"] = self._parse_bms_error_reason(error_reason)

        return result

    def _parse_bms_stop_reason(self, reason: int) -> str:
        reasons = []
        if reason & 0x03:
            reasons.append("达到所需求的SOC目标值")
        if reason & 0x0C:
            reasons.append("达到总电压的设定值")
        if reason & 0x30:
            reasons.append("达到单体电压设定值")
        if reason & 0xC0:
            reasons.append("充电机主动中止")
        return "; ".join(reasons) if reasons else "无"

    def _parse_bms_fault_reason(self, fault: int) -> str:
        faults = []
        fault_names = [
            "绝缘故障", "输出连接器过温故障", "BMS元件、输出连接器过温",
            "充电连接器故障", "电池组温度过高故障", "高压继电器故障",
            "检测点2电压检测故障", "其他故障"
        ]
        for i, name in enumerate(fault_names):
            if fault & (0x03 << (i * 2)):
                faults.append(name)
        return "; ".join(faults) if faults else "无"

    def _parse_bms_error_reason(self, error: int) -> str:
        errors = []
        if error & 0x03:
            errors.append("电流过大")
        if error & 0x0C:
            errors.append("电压异常")
        return "; ".join(errors) if errors else "无"


class ChargerStopParser(FrameParser):
    """充电阶段充电机中止 (0x21)"""

    @property
    def expected_min_length(self) -> int:
        return 28

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        stop_reason = body[offset]
        result["charger_stop_reason_code"] = stop_reason
        result["charger_stop_reason"] = self._parse_charger_stop_reason(stop_reason)
        offset += 1

        fault_reason = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_fault_reason_code"] = fault_reason
        result["charger_fault_reason"] = self._parse_charger_fault_reason(fault_reason)
        offset += 2

        error_reason = body[offset]
        result["charger_error_reason_code"] = error_reason
        result["charger_error_reason"] = self._parse_charger_error_reason(error_reason)

        return result

    def _parse_charger_stop_reason(self, reason: int) -> str:
        reasons = []
        if reason & 0x03:
            reasons.append("达到充电机设定的条件中止")
        if reason & 0x0C:
            reasons.append("人工中止")
        if reason & 0x30:
            reasons.append("异常中止")
        if reason & 0xC0:
            reasons.append("BMS主动中止")
        return "; ".join(reasons) if reasons else "无"

    def _parse_charger_fault_reason(self, fault: int) -> str:
        faults = []
        fault_names = [
            "充电机过温故障", "充电连接器故障", "充电机内部过温故障",
            "所需电量不能传送", "充电机急停故障", "其他故障"
        ]
        for i, name in enumerate(fault_names):
            if fault & (0x03 << (i * 2)):
                faults.append(name)
        return "; ".join(faults) if faults else "无"

    def _parse_charger_error_reason(self, error: int) -> str:
        errors = []
        if error & 0x03:
            errors.append("电流不匹配")
        if error & 0x0C:
            errors.append("电压异常")
        return "; ".join(errors) if errors else "无"


class BMSDemandOutputParser(FrameParser):
    """BMS需求/充电机输出 (0x23)"""

    @property
    def expected_min_length(self) -> int:
        return 40

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        bms_voltage_demand = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_voltage_demand_v"] = bms_voltage_demand / 10.0
        offset += 2

        bms_current_demand = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_current_demand_a"] = (bms_current_demand / 10.0) - 400
        offset += 2

        charge_mode = body[offset]
        result["bms_charge_mode"] = "恒压充电" if charge_mode == 0x01 else "恒流充电"
        result["bms_charge_mode_code"] = charge_mode
        offset += 1

        bms_voltage_measured = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_voltage_measured_v"] = bms_voltage_measured / 10.0
        offset += 2

        bms_current_measured = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_current_measured_a"] = (bms_current_measured / 10.0) - 400
        offset += 2

        cell_voltage_data = int.from_bytes(body[offset:offset+2], byteorder='little')
        cell_voltage = (cell_voltage_data & 0x0FFF) / 100.0
        cell_group = (cell_voltage_data >> 12) & 0x0F
        result["bms_max_cell_voltage_v"] = cell_voltage
        result["bms_max_cell_group_number"] = cell_group
        offset += 2

        result["bms_current_soc_percent"] = body[offset]
        offset += 1

        remaining_time = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["bms_estimated_remaining_time_minutes"] = remaining_time
        offset += 2

        charger_voltage = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_output_voltage_v"] = charger_voltage / 10.0
        offset += 2

        charger_current = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["charger_output_current_a"] = (charger_current / 10.0) - 400
        offset += 2

        total_time = int.from_bytes(body[offset:offset+2], byteorder='little')
        result["total_charge_time_minutes"] = total_time

        return result


class BMSInfoParser(FrameParser):
    """BMS信息 (0x25)"""

    @property
    def expected_min_length(self) -> int:
        return 31

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["transaction_id"] = self.context.bcd_to_str(body[offset:offset+16])
        offset += 16
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7
        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        max_cell_number = body[offset]
        result["bms_max_cell_number"] = max_cell_number + 1
        offset += 1

        result["bms_max_temperature_celsius"] = body[offset] - 50
        offset += 1

        max_temp_sensor = body[offset]
        result["max_temperature_sensor_number"] = max_temp_sensor + 1
        offset += 1

        result["bms_min_temperature_celsius"] = body[offset] - 50
        offset += 1

        min_temp_sensor = body[offset]
        result["min_temperature_sensor_number"] = min_temp_sensor + 1
        offset += 1

        status_bytes = body[offset:offset+2]
        result["status_hex"] = status_bytes.hex().upper()
        result["status_flags"] = self._parse_bms_status_flags(status_bytes)

        return result

    def _parse_bms_status_flags(self, status_bytes: bytes) -> Dict[str, str]:
        status_int = int.from_bytes(status_bytes, byteorder='little')
        flags = {}

        cell_voltage = (status_int >> 0) & 0x03
        flags["单体电压"] = {0: "正常", 1: "过高", 2: "过低"}.get(cell_voltage, "未知")

        soc = (status_int >> 2) & 0x03
        flags["SOC"] = {0: "正常", 1: "过高", 2: "过低"}.get(soc, "未知")

        overcurrent = (status_int >> 4) & 0x03
        flags["充电过电流"] = {0: "正常", 1: "过流", 2: "不可信"}.get(overcurrent, "未知")

        temp = (status_int >> 6) & 0x03
        flags["电池温度"] = {0: "正常", 1: "过高", 2: "不可信"}.get(temp, "未知")

        insulation = (status_int >> 8) & 0x03
        flags["绝缘状态"] = {0: "正常", 1: "故障", 2: "不可信"}.get(insulation, "未知")

        connector = (status_int >> 10) & 0x03
        flags["输出连接器"] = {0: "正常", 1: "故障", 2: "不可信"}.get(connector, "未知")

        charge_permit = (status_int >> 12) & 0x03
        flags["充电许可"] = {0: "禁止", 1: "允许"}.get(charge_permit, "未知")

        return flags


# ==================== 离线卡管理类 ====================

class OfflineCardSyncParser(FrameParser):
    """离线卡数据同步 (0x44)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        card_count = body[offset]
        result["card_count"] = card_count
        offset += 1

        expected_len = 8 + card_count * 16
        if len(body) < expected_len:
            self.context.errors.append(f"离线卡数据长度不足: 需要{expected_len}字节, 实际{len(body)}字节")

        cards = []
        for i in range(min(card_count, (len(body) - 8) // 16)):
            card = {}
            card["logical_card_number"] = self.context.bcd_to_str(body[offset:offset+8])
            offset += 8
            physical = int.from_bytes(body[offset:offset+8], byteorder='little')
            card["physical_card_number"] = f"{physical:016X}"
            offset += 8
            cards.append(card)

        result["cards"] = cards
        return result


class OfflineCardSyncResponseParser(FrameParser):
    """离线卡数据同步应答 (0x43)"""

    @property
    def expected_min_length(self) -> int:
        return 9

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        save_result = body[7]
        result["save_result"] = "成功" if save_result == 0x01 else "失败"
        result["save_result_code"] = save_result

        fail_reason = body[8]
        fail_reasons = {
            0x00: "无",
            0x01: "卡号格式错误",
            0x02: "储存空间不足"
        }
        result["fail_reason"] = fail_reasons.get(fail_reason, f"未知({fail_reason})")
        result["fail_reason_code"] = fail_reason

        return result


class OfflineCardDeleteParser(FrameParser):
    """离线卡数据清除 (0x46)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        card_count = body[offset]
        result["card_count"] = card_count
        offset += 1

        expected_len = 8 + card_count * 8
        if len(body) < expected_len:
            self.context.errors.append(f"离线卡数据长度不足: 需要{expected_len}字节, 实际{len(body)}字节")

        cards = []
        for i in range(min(card_count, (len(body) - 8) // 8)):
            physical = int.from_bytes(body[offset:offset+8], byteorder='little')
            cards.append(f"{physical:016X}")
            offset += 8

        result["card_numbers"] = cards
        return result


class OfflineCardDeleteResponseParser(FrameParser):
    """离线卡数据清除应答 (0x45)"""

    @property
    def expected_min_length(self) -> int:
        return 7

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        cards = []
        while offset + 10 <= len(body):
            card = {}
            physical = int.from_bytes(body[offset:offset+8], byteorder='little')
            card["physical_card_number"] = f"{physical:016X}"
            offset += 8

            delete_flag = body[offset]
            card["delete_result"] = "清除成功" if delete_flag == 0x01 else "清除失败"
            card["delete_flag"] = delete_flag
            offset += 1

            fail_reason = body[offset]
            fail_reasons = {0x00: "清除成功", 0x01: "卡号格式错误"}
            card["fail_reason"] = fail_reasons.get(fail_reason, f"未知({fail_reason})")
            card["fail_reason_code"] = fail_reason
            offset += 1

            cards.append(card)

        result["cards"] = cards
        return result


class OfflineCardQueryParser(FrameParser):
    """离线卡数据查询 (0x48)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        card_count = body[offset]
        result["card_count"] = card_count
        offset += 1

        expected_len = 8 + card_count * 8
        if len(body) < expected_len:
            self.context.errors.append(f"离线卡数据长度不足: 需要{expected_len}字节, 实际{len(body)}字节")

        cards = []
        for i in range(min(card_count, (len(body) - 8) // 8)):
            physical = int.from_bytes(body[offset:offset+8], byteorder='little')
            cards.append(f"{physical:016X}")
            offset += 8

        result["card_numbers"] = cards
        return result


class OfflineCardQueryResponseParser(FrameParser):
    """离线卡数据查询应答 (0x47)"""

    @property
    def expected_min_length(self) -> int:
        return 7

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        cards = []
        while offset + 9 <= len(body):
            card = {}
            physical = int.from_bytes(body[offset:offset+8], byteorder='little')
            card["physical_card_number"] = f"{physical:016X}"
            offset += 8

            query_result = body[offset]
            card["exists"] = query_result == 0x01
            card["query_result"] = "存在" if query_result == 0x01 else "不存在"
            card["query_result_code"] = query_result
            offset += 1

            cards.append(card)

        result["cards"] = cards
        return result





# ==================== 心跳类 ====================

class HeartbeatParser(FrameParser):
    """充电桩心跳包 (0x03)"""

    @property
    def expected_min_length(self) -> int:
        return 7

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        return result


class HeartbeatResponseParser(FrameParser):
    """心跳包应答 (0x04)"""

    @property
    def expected_min_length(self) -> int:
        return 7

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        return result


# ==================== 运营交互类 - 启动停机 ====================

class ChargingStartRequestParser(FrameParser):
    """充电桩主动申请启动 (0x31)"""

    @property
    def expected_min_length(self) -> int:
        return 21

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        card_number = int.from_bytes(body[offset:offset+8], byteorder='little')
        result["physical_card_number"] = f"{card_number:016X}" if card_number > 0 else "无卡"
        offset += 8

        balance = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["card_balance_yuan"] = balance / 100.0
        offset += 4

        start_mode = body[offset]
        start_modes = {0x01: "刷卡启动", 0x02: "VIN启动", 0x03: "自动充满", 0x04: "按电量", 0x05: "按金额", 0x06: "按时间"}
        result["start_mode"] = start_modes.get(start_mode, f"未知({start_mode})")
        result["start_mode_code"] = start_mode

        return result


class ChargingStartConfirmParser(FrameParser):
    """确认启动充电 (0x32)"""

    @property
    def expected_min_length(self) -> int:
        return 13

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        start_result = body[offset]
        result["start_result"] = "启动成功" if start_result == 0x00 else "启动失败"
        result["start_result_code"] = start_result
        offset += 1

        charge_mode = body[offset]
        charge_modes = {0x01: "自动充满", 0x02: "按电量", 0x03: "按金额", 0x04: "按时间"}
        result["charge_mode"] = charge_modes.get(charge_mode, f"未知({charge_mode})")
        result["charge_mode_code"] = charge_mode
        offset += 1

        order_number = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["order_number"] = order_number

        return result


class RemoteStartReplyParser(FrameParser):
    """远程启机回复 (0x33)"""

    @property
    def expected_min_length(self) -> int:
        return 15

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        exec_result = body[offset]
        result["exec_result"] = "执行成功" if exec_result == 0x00 else "执行失败"
        result["exec_result_code"] = exec_result
        offset += 1

        order_number = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["order_number"] = order_number
        offset += 4

        fail_reason = body[offset]
        fail_reasons = {
            0x00: "无",
            0x01: "此充电桩不存在",
            0x02: "此充电枪不存在",
            0x03: "设备故障",
            0x04: "设备离线",
            0x05: "充电桩有车占位",
            0x06: "充电桩已在充电"
        }
        result["fail_reason"] = fail_reasons.get(fail_reason, f"未知({fail_reason})")
        result["fail_reason_code"] = fail_reason

        return result


class RemoteStartCommandParser(FrameParser):
    """远程控制启机 (0x34)"""

    @property
    def expected_min_length(self) -> int:
        return 21

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        card_number = int.from_bytes(body[offset:offset+8], byteorder='little')
        result["physical_card_number"] = f"{card_number:016X}" if card_number > 0 else "无卡"
        offset += 8

        balance = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["card_balance_yuan"] = balance / 100.0
        offset += 4

        charge_mode = body[offset]
        charge_modes = {0x01: "自动充满", 0x02: "按电量", 0x03: "按金额", 0x04: "按时间"}
        result["charge_mode"] = charge_modes.get(charge_mode, f"未知({charge_mode})")
        result["charge_mode_code"] = charge_mode

        return result


class RemoteStopReplyParser(FrameParser):
    """远程停机回复 (0x35)"""

    @property
    def expected_min_length(self) -> int:
        return 14

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        exec_result = body[offset]
        result["exec_result"] = "执行成功" if exec_result == 0x00 else "执行失败"
        result["exec_result_code"] = exec_result
        offset += 1

        order_number = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["order_number"] = order_number
        offset += 4

        fail_reason = body[offset]
        fail_reasons = {
            0x00: "无",
            0x01: "此充电桩不存在",
            0x02: "此充电枪不存在",
            0x03: "设备故障",
            0x04: "设备离线",
            0x05: "充电枪空闲"
        }
        result["fail_reason"] = fail_reasons.get(fail_reason, f"未知({fail_reason})")
        result["fail_reason_code"] = fail_reason

        return result


class RemoteStopCommandParser(FrameParser):
    """远程停机 (0x36)"""

    @property
    def expected_min_length(self) -> int:
        return 12

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        result["gun_number"] = self.context.bcd_to_str(body[offset:offset+1])
        offset += 1

        order_number = int.from_bytes(body[offset:offset+4], byteorder='little')
        result["order_number"] = order_number

        return result

# ==================== 平台设置类 ====================

class WorkParameterSetResponseParser(FrameParser):
    """工作参数设置应答 (0x51)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        set_result = body[7]
        result["set_result"] = "设置成功" if set_result == 0x00 else "设置失败"
        result["set_result_code"] = set_result

        return result


class WorkParameterSetParser(FrameParser):
    """工作参数设置 (0x52)"""

    @property
    def expected_min_length(self) -> int:
        return 18

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        param_type = body[offset]
        param_types = {
            0x01: "心跳周期",
            0x02: "IP地址",
            0x03: "端口号",
            0x04: "APN",
            0x05: "服务器域名"
        }
        result["param_type"] = param_types.get(param_type, f"未知({param_type})")
        result["param_type_code"] = param_type
        offset += 1

        param_value = body[offset:offset+10]
        result["param_value"] = param_value.hex().upper()
        result["param_value_ascii"] = self.context.ascii_to_str(param_value)

        return result


class TimeSyncResponseParser(FrameParser):
    """对时设置应答 (0x55)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        sync_result = body[7]
        result["sync_result"] = "对时成功" if sync_result == 0x00 else "对时失败"
        result["sync_result_code"] = sync_result

        return result


class TimeSyncParser(FrameParser):
    """对时设置 (0x56)"""

    @property
    def expected_min_length(self) -> int:
        return 14

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        result["sync_time"] = self.context.parse_cp56time2a(body[7:14])

        return result


class BillingModelResponseParser(FrameParser):
    """计费模型应答 (0x57)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        set_result = body[7]
        result["set_result"] = "设置成功" if set_result == 0x00 else "设置失败"
        result["set_result_code"] = set_result

        return result


class BillingModelSetParser(FrameParser):
    """计费模型设置 (0x58)"""

    @property
    def expected_min_length(self) -> int:
        return 29

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        result["billing_model_data"] = body[7:].hex().upper()
        result["note"] = "计费模型数据结构待详细解析"

        return result


# ==================== 车位锁类 ====================

class ParkingLockStatusParser(FrameParser):
    """地锁数据上送 (0x61)"""

    @property
    def expected_min_length(self) -> int:
        return 9

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        lock_status = body[7]
        lock_statuses = {0x00: "降下", 0x01: "升起", 0x02: "故障"}
        result["lock_status"] = lock_statuses.get(lock_status, f"未知({lock_status})")
        result["lock_status_code"] = lock_status

        battery_level = body[8]
        result["battery_level_percent"] = battery_level

        return result


class ParkingLockControlParser(FrameParser):
    """遥控地锁升降 (0x62)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        control_cmd = body[7]
        control_cmds = {0x00: "降下", 0x01: "升起"}
        result["control_command"] = control_cmds.get(control_cmd, f"未知({control_cmd})")
        result["control_command_code"] = control_cmd

        return result


class ParkingLockResponseParser(FrameParser):
    """充电桩返回数据 (0x63)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        exec_result = body[7]
        result["exec_result"] = "执行成功" if exec_result == 0x00 else "执行失败"
        result["exec_result_code"] = exec_result

        return result


# ==================== 远程维护类 ====================

class RemoteRebootResponseParser(FrameParser):
    """远程重启应答 (0x91)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        reboot_result = body[7]
        result["reboot_result"] = "重启成功" if reboot_result == 0x00 else "重启失败"
        result["reboot_result_code"] = reboot_result

        return result


class RemoteRebootParser(FrameParser):
    """远程重启 (0x92)"""

    @property
    def expected_min_length(self) -> int:
        return 7

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        return result


class RemoteUpdateResponseParser(FrameParser):
    """远程更新应答 (0x93)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        update_result = body[7]
        result["update_result"] = "更新成功" if update_result == 0x00 else "更新失败"
        result["update_result_code"] = update_result

        return result


class RemoteUpdateParser(FrameParser):
    """远程更新 (0x94)"""

    @property
    def expected_min_length(self) -> int:
        return 17

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])
        result["update_params"] = body[7:].hex().upper()
        result["note"] = "更新参数数据待详细解析"

        return result


# ==================== 并充模式类 ====================

class ParallelChargingRequestParser(FrameParser):
    """主动申请并充 (0xA1)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        request_type = body[7]
        result["request_type"] = "申请并充" if request_type == 0x01 else f"未知({request_type})"
        result["request_type_code"] = request_type

        return result


class ParallelChargingConfirmParser(FrameParser):
    """确认并充启动 (0xA2)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        confirm_result = body[7]
        result["confirm_result"] = "确认成功" if confirm_result == 0x00 else "确认失败"
        result["confirm_result_code"] = confirm_result

        return result


class ParallelChargingReplyParser(FrameParser):
    """远程并充启机回复 (0xA3)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        exec_result = body[7]
        result["exec_result"] = "执行成功" if exec_result == 0x00 else "执行失败"
        result["exec_result_code"] = exec_result

        return result


class ParallelChargingCommandParser(FrameParser):
    """远程控制并充启机 (0xA4)"""

    @property
    def expected_min_length(self) -> int:
        return 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        result["pile_code"] = self.context.bcd_to_str(body[0:7])

        control_cmd = body[7]
        result["control_command"] = "启动并充" if control_cmd == 0x01 else f"未知({control_cmd})"
        result["control_command_code"] = control_cmd

        return result


class QRCodePrefixSetParser(FrameParser):
    """后台下发二维码前缀指令 (0xF0)"""

    @property
    def expected_min_length(self) -> int:
        return 9  # 7(桩编码) + 1(前缀编码) + 1(前缀长度) = 9

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 桩编码 (7字节 BCD码)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 二维码前缀编码 (1字节)
        prefix_format = body[offset]
        prefix_formats = {
            0x00: "第一种前缀+桩编号",
            0x01: "第二种前缀+组织号+桩编号"
        }
        result["qrcode_prefix_format"] = prefix_formats.get(prefix_format, f"未知({prefix_format})")
        result["qrcode_prefix_format_code"] = prefix_format
        offset += 1

        # 二维码前缀长度 (1字节)
        prefix_length = body[offset]
        result["qrcode_prefix_length"] = prefix_length
        offset += 1

        # 二维码前缀 (可变长度 ASCII)
        remaining = len(body) - offset
        take = max(0, min(prefix_length, remaining))
        prefix_bytes = body[offset:offset+take]

        result["qrcode_prefix"] = self.context.ascii_to_str(prefix_bytes) if take > 0 else ""
        result["qrcode_prefix_hex"] = prefix_bytes.hex().upper()

        if remaining < prefix_length:
            self.context.warnings.append(
            f"二维码前缀数据不完整: 期望{prefix_length}字节，实际{remaining}字节"
            )
        elif remaining > prefix_length:
            self.context.warnings.append(
            f"二维码前缀数据长度超出预期: 期望{prefix_length}字节，实际{remaining}字节"
            )

        return result


class QRCodePrefixSetResponseParser(FrameParser):
    """桩应答返回下发二维码前缀指令 (0xF1)"""

    @property
    def expected_min_length(self) -> int:
        return 8  # 7(桩编码) + 1(下发结果) = 8

    def parse(self, body: bytes) -> Dict[str, Any]:
        if not self.validate_length(body):
            return {}

        result = {}
        offset = 0

        # 桩编码 (7字节 BCD码)
        result["pile_code"] = self.context.bcd_to_str(body[offset:offset+7])
        offset += 7

        # 下发结果 (1字节)
        set_result = body[offset]
        result["set_result"] = "成功" if set_result == 0x01 else "失败"
        result["set_result_code"] = set_result

        if set_result == 0x01:
            self.context.warnings.append("注意: 返回成功不代表二维码一定设置成功，需要确认厂商实现方式")

        return result

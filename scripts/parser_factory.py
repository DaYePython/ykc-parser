#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云快充协议解析器工厂
"""

from typing import Dict, Type
from frame_parsers import (
    FrameParser, DefaultParser,
    # 注册心跳类
    LoginParser, LoginResponseParser,
    HeartbeatParser, HeartbeatResponseParser,
    # 实时数据类
    ReadRealtimeParser, RealtimeDataParser, ChargingHandshakeParser,
    ParameterConfigParser, ChargingEndParser, ErrorMessageParser,
    BMSStopParser, ChargerStopParser, BMSDemandOutputParser, BMSInfoParser,
    # 运营交互类
    ChargingStartRequestParser, ChargingStartConfirmParser,
    RemoteStartReplyParser, RemoteStartCommandParser,
    RemoteStopReplyParser, RemoteStopCommandParser,
    TransactionRecordParser, TransactionConfirmParser,
    BalanceUpdateRequestParser, BalanceUpdateResponseParser,
    OfflineCardSyncParser, OfflineCardSyncResponseParser,
    OfflineCardDeleteParser, OfflineCardDeleteResponseParser,
    OfflineCardQueryParser, OfflineCardQueryResponseParser,
    # 平台设置类
    WorkParameterSetResponseParser, WorkParameterSetParser,
    TimeSyncResponseParser, TimeSyncParser,
    BillingModelResponseParser, BillingModelSetParser,
    # 车位锁类
    ParkingLockStatusParser, ParkingLockControlParser, ParkingLockResponseParser,
    # 远程维护类
    RemoteRebootResponseParser, RemoteRebootParser,
    RemoteUpdateResponseParser, RemoteUpdateParser,
    # 并充模式类
    ParallelChargingRequestParser, ParallelChargingConfirmParser,
    ParallelChargingReplyParser, ParallelChargingCommandParser,
)


class FrameParserFactory:
    """帧解析器工厂类"""

    # 帧类型到解析器类的映射
    _parsers: Dict[int, Type[FrameParser]] = {
        # 注册心跳类 (0x01-0x0A)
        0x01: LoginParser,
        0x02: LoginResponseParser,
        0x03: HeartbeatParser,
        0x04: HeartbeatResponseParser,

        # 实时数据类 (0x12-0x25)
        0x12: ReadRealtimeParser,
        0x13: RealtimeDataParser,
        0x15: ChargingHandshakeParser,
        0x17: ParameterConfigParser,
        0x19: ChargingEndParser,
        0x1B: ErrorMessageParser,
        0x1D: BMSStopParser,
        0x21: ChargerStopParser,
        0x23: BMSDemandOutputParser,
        0x25: BMSInfoParser,

        # 运营交互类 (0x31-0x48)
        0x31: ChargingStartRequestParser,
        0x32: ChargingStartConfirmParser,
        0x33: RemoteStartReplyParser,
        0x34: RemoteStartCommandParser,
        0x35: RemoteStopReplyParser,
        0x36: RemoteStopCommandParser,
        0x3B: TransactionRecordParser,
        0x40: TransactionConfirmParser,
        0x41: BalanceUpdateResponseParser,
        0x42: BalanceUpdateRequestParser,
        0x43: OfflineCardSyncResponseParser,
        0x44: OfflineCardSyncParser,
        0x45: OfflineCardDeleteResponseParser,
        0x46: OfflineCardDeleteParser,
        0x47: OfflineCardQueryResponseParser,
        0x48: OfflineCardQueryParser,

        # 平台设置类 (0x51-0x58)
        0x51: WorkParameterSetResponseParser,
        0x52: WorkParameterSetParser,
        0x55: TimeSyncResponseParser,
        0x56: TimeSyncParser,
        0x57: BillingModelResponseParser,
        0x58: BillingModelSetParser,

        # 车位锁类 (0x61-0x63)
        0x61: ParkingLockStatusParser,
        0x62: ParkingLockControlParser,
        0x63: ParkingLockResponseParser,

        # 远程维护类 (0x91-0x94)
        0x91: RemoteRebootResponseParser,
        0x92: RemoteRebootParser,
        0x93: RemoteUpdateResponseParser,
        0x94: RemoteUpdateParser,

        # 并充模式类 (0xA1-0xA4)
        0xA1: ParallelChargingRequestParser,
        0xA2: ParallelChargingConfirmParser,
        0xA3: ParallelChargingReplyParser,
        0xA4: ParallelChargingCommandParser,
    }

    @classmethod
    def get_parser(cls, frame_type: int, context) -> FrameParser:
        """
        根据帧类型获取对应的解析器

        Args:
            frame_type: 帧类型码
            context: 解析上下文

        Returns:
            对应的解析器实例
        """
        parser_class = cls._parsers.get(frame_type, DefaultParser)
        return parser_class(context)

    @classmethod
    def register_parser(cls, frame_type: int, parser_class: Type[FrameParser]):
        """
        注册新的解析器

        Args:
            frame_type: 帧类型码
            parser_class: 解析器类
        """
        cls._parsers[frame_type] = parser_class

    @classmethod
    def get_supported_frame_types(cls) -> list:
        """获取所有已支持的帧类型"""
        return sorted(cls._parsers.keys())


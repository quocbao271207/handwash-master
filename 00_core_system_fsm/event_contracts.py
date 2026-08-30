"""
Module: event_contracts.py
Phụ trách: Toàn đội
Mô tả: Định nghĩa cấu trúc dữ liệu chuẩn (Data Contracts & Enums) dùng chung giữa các Module 1, 2, 3 và Core FSM.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class HandState(Enum):
    UNSTERILE = "UNSTERILE"      # Bàn tay chưa vô trùng (trạng thái mặc định hoặc sau tiếp xúc bề mặt)
    STERILE = "STERILE"          # Bàn tay đã vô trùng (sau khi hoàn thành quy trình rửa tay đạt chuẩn)
    BIOHAZARD = "BIOHAZARD"      # Bàn tay dính dịch tiết sinh học (nguy cơ cao, bắt buộc phải rửa ngay)


class WHOMoment(Enum):
    MOMENT_1_BEFORE_PATIENT = "M1_BEFORE_PATIENT"                # Thời điểm 1: Trước khi chạm bệnh nhân
    MOMENT_2_BEFORE_ASEPTIC = "M2_BEFORE_ASEPTIC"                # Thời điểm 2: Trước thủ thuật sạch/vô trùng
    MOMENT_3_AFTER_BODY_FLUID = "M3_AFTER_BODY_FLUID"            # Thời điểm 3: Sau tiếp xúc nguy cơ dịch cơ thể
    MOMENT_4_AFTER_PATIENT = "M4_AFTER_PATIENT"                  # Thời điểm 4: Sau khi chạm bệnh nhân
    MOMENT_5_AFTER_SURROUNDINGS = "M5_AFTER_SURROUNDINGS"        # Thời điểm 5: Sau khi chạm vật dụng xung quanh bệnh nhân


class ViolationSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class PersonContactEvent:
    """Sự kiện gửi từ Module 01 (Bảo): Tiếp xúc giữa Y tá và Bệnh nhân."""
    frame_id: int
    timestamp: float
    nurse_id: int
    patient_id: int
    is_touching: bool
    contact_confidence: float
    nurse_wrist_pos: Tuple[float, float]
    patient_body_part: str
    touch_duration_sec: float = 0.0


@dataclass
class EquipmentContactEvent:
    """Sự kiện gửi từ Module 02 (Thái): Tiếp xúc giữa Y tá và Thiết bị / Vùng vô khuẩn / Dịch tiết."""
    frame_id: int
    timestamp: float
    nurse_id: int
    equipment_type: str            # 'VENTILATOR', 'MONITOR', 'BED_RAIL', 'ASEPTIC_TRAY', 'CATHETER'
    is_aseptic_zone: bool          # Vùng thủ thuật vô khuẩn
    is_body_fluid_risk: bool       # Vùng dịch cơ thể / chất thải
    is_sanitizer: bool             # Vùng bình rửa tay cồn
    contact_iou: float
    contact_duration_sec: float = 0.0


@dataclass
class HandwashStateEvent:
    """Sự kiện gửi từ Module 03 (Vinh): Trạng thái tự chạm tay và nhận diện hành động rửa tay."""
    frame_id: int
    timestamp: float
    nurse_id: int
    is_self_touching: bool
    is_washing_action: bool
    action_confidence: float
    wash_duration_sec: float
    is_wash_completed: bool


@dataclass
class WHOViolationAlert:
    """Cảnh báo vi phạm xuất ra cho hệ thống giám sát và Dashboard."""
    frame_id: int
    timestamp: float
    nurse_id: int
    violated_moment: WHOMoment
    severity: ViolationSeverity
    description: str

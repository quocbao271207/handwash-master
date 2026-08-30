"""
Module: who_fsm_engine.py
Phụ trách: Toàn đội
Mô tả: Bộ máy Finite State Machine (FSM) và Engine kiểm tra vi phạm 5 thời điểm WHO trong phòng ICU.
"""

from typing import Dict, List, Optional
from event_contracts import (
    HandState,
    WHOMoment,
    ViolationSeverity,
    PersonContactEvent,
    EquipmentContactEvent,
    HandwashStateEvent,
    WHOViolationAlert,
)


class NurseStateMachine:
    """Quản lý trạng thái vô trùng độc lập cho từng y tá."""
    def __init__(self, nurse_id: int):
        self.nurse_id = nurse_id
        self.current_state = HandState.UNSTERILE
        self.last_patient_contact_time: Optional[float] = None
        self.last_equipment_contact_time: Optional[float] = None
        self.in_contact_with_patient = False
        self.in_contact_with_body_fluid = False

    def transition_to(self, new_state: HandState):
        self.current_state = new_state


class WHOComplianceEngine:
    """Engine nhận chuỗi sự kiện và đối chiếu 5 thời điểm vàng WHO."""
    def __init__(self):
        self.nurses: Dict[int, NurseStateMachine] = {}
        self.alerts_history: List[WHOViolationAlert] = []

    def get_or_create_nurse(self, nurse_id: int) -> NurseStateMachine:
        if nurse_id not in self.nurses:
            self.nurses[nurse_id] = NurseStateMachine(nurse_id)
        return self.nurses[nurse_id]

    def process_handwash_event(self, evt: HandwashStateEvent) -> Optional[WHOViolationAlert]:
        """Xử lý sự kiện rửa tay từ Module 03 (Vinh)."""
        nurse = self.get_or_create_nurse(evt.nurse_id)
        
        if evt.is_wash_completed:
            # Rửa tay thành công -> Nâng trạng thái lên STERILE
            nurse.transition_to(HandState.STERILE)
            nurse.in_contact_with_body_fluid = False
        return None

    def process_person_contact_event(self, evt: PersonContactEvent) -> Optional[WHOViolationAlert]:
        """Xử lý sự kiện tiếp xúc Người - Người từ Module 01 (Bảo)."""
        nurse = self.get_or_create_nurse(evt.nurse_id)
        alert = None

        if evt.is_touching:
            # Thời điểm 1: Trước khi chạm bệnh nhân, tay phải là STERILE
            if nurse.current_state != HandState.STERILE and not nurse.in_contact_with_patient:
                alert = WHOViolationAlert(
                    frame_id=evt.frame_id,
                    timestamp=evt.timestamp,
                    nurse_id=evt.nurse_id,
                    violated_moment=WHOMoment.MOMENT_1_BEFORE_PATIENT,
                    severity=ViolationSeverity.CRITICAL,
                    description=f"Y tá {evt.nurse_id} chạm bệnh nhân {evt.patient_id} khi tay đang ở trạng thái {nurse.current_state.value} (Chưa sát khuẩn)."
                )
                self.alerts_history.append(alert)

            nurse.in_contact_with_patient = True
            nurse.last_patient_contact_time = evt.timestamp
        else:
            # Thời điểm 4: Sau khi kết thúc chạm bệnh nhân -> Tay bị nhiễm bẩn (UNSTERILE)
            if nurse.in_contact_with_patient:
                nurse.in_contact_with_patient = False
                nurse.transition_to(HandState.UNSTERILE)

        return alert

    def process_equipment_contact_event(self, evt: EquipmentContactEvent) -> Optional[WHOViolationAlert]:
        """Xử lý sự kiện tiếp xúc Thiết bị / Vùng vô khuẩn / Dịch tiết từ Module 02 (Thái)."""
        nurse = self.get_or_create_nurse(evt.nurse_id)
        alert = None

        # Thời điểm 2: Trước thủ thuật vô khuẩn
        if evt.is_aseptic_zone:
            if nurse.current_state != HandState.STERILE:
                alert = WHOViolationAlert(
                    frame_id=evt.frame_id,
                    timestamp=evt.timestamp,
                    nurse_id=evt.nurse_id,
                    violated_moment=WHOMoment.MOMENT_2_BEFORE_ASEPTIC,
                    severity=ViolationSeverity.CRITICAL,
                    description=f"Y tá {evt.nurse_id} thao tác tại vùng vô khuẩn {evt.equipment_type} mà chưa đảm bảo tay STERILE."
                )
                self.alerts_history.append(alert)

        # Thời điểm 3: Tiếp xúc nguy cơ dịch cơ thể
        elif evt.is_body_fluid_risk:
            nurse.in_contact_with_body_fluid = True
            nurse.transition_to(HandState.BIOHAZARD)

        # Thời điểm 5: Sau khi chạm vật dụng xung quanh bệnh nhân
        elif not evt.is_sanitizer:
            if nurse.current_state == HandState.STERILE:
                # Chạm vào thiết bị xung quanh làm mất trạng thái vô trùng
                nurse.transition_to(HandState.UNSTERILE)

        return alert

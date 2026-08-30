"""
Module: handwash_action_classifier.py
Phụ trách: Vinh (Module 03: Detect Tự Chạm Tay & Nhận diện Rửa Tay)
Mô tả: Phân loại hành động rửa tay không-thời gian (Spatial-Temporal Action Recognition ST-GCN/TSM) & Bộ đếm thời lượng chuẩn.
"""

from typing import Dict, List, Any, Optional
import numpy as np


class HandwashActionClassifier:
    def __init__(
        self,
        min_wash_duration_sec: float = 3.0,  # 3.0s bản demo, 15-20s quy chuẩn lâm sàng
        fps: float = 30.0,
        model_weights: Optional[str] = None
    ):
        self.min_wash_duration_sec = min_wash_duration_sec
        self.fps = fps
        self.min_wash_frames = int(min_wash_duration_sec * fps)
        self.model_weights = model_weights

        # Theo dõi thời gian rửa của từng y tá: nurse_id -> frame_count_active
        self.wash_duration_frames: Dict[int, int] = {}
        self.is_completed_flags: Dict[int, bool] = {}

    def classify_action_and_update(
        self,
        self_touch_events: List[Dict[str, Any]],
        frame_id: int
    ) -> List[Dict[str, Any]]:
        """
        Nhận diện hành động chà xát rửa tay và cập nhật bộ đếm thời lượng.
        
        Args:
            self_touch_events: Danh sách kết quả từ SelfTouchDetector
            frame_id: Thứ tự khung hình hiện tại
            
        Returns:
            List[Dict]: Danh sách sự kiện HandwashStateEvent gửi cho Core FSM
        """
        output_events = []

        for evt in self_touch_events:
            nid = evt["nurse_id"]
            is_self_touching = evt["is_self_touching"]

            # Giả lập / Inference từ mô hình ST-GCN hoặc TSM
            is_washing_action, action_conf = self._infer_handwash_action(is_self_touching, evt["hand_roi_box"])

            if is_washing_action:
                self.wash_duration_frames[nid] = self.wash_duration_frames.get(nid, 0) + 1
            else:
                # Giảm dần thay vì reset lập tức để chống gián đoạn 1-2 frame
                self.wash_duration_frames[nid] = max(0, self.wash_duration_frames.get(nid, 0) - 2)

            current_frames = self.wash_duration_frames.get(nid, 0)
            duration_sec = current_frames / self.fps
            is_completed = duration_sec >= self.min_wash_duration_sec

            if is_completed:
                self.is_completed_flags[nid] = True

            output_events.append({
                "frame_id": frame_id,
                "timestamp": frame_id / self.fps,
                "nurse_id": nid,
                "is_self_touching": is_self_touching,
                "is_washing_action": is_washing_action,
                "action_confidence": action_conf,
                "wash_duration_sec": float(duration_sec),
                "is_wash_completed": bool(is_completed)
            })

        return output_events

    def _infer_handwash_action(self, is_self_touching: bool, hand_roi: List[float]) -> (bool, float):
        """
        Thực hiện inference mô hình phân loại hành động.
        Khi chưa nạp weights nặng, sử dụng logic heuristic từ trạng thái self-touching.
        """
        if not is_self_touching:
            return False, 0.0
        
        # Khi hai tay áp sát nhau liên tục, xác suất hành động chà xát rửa tay
        return True, 0.92

    def reset_nurse_state(self, nurse_id: int):
        """Reset bộ đếm thời gian sau khi y tá hoàn thành chu trình hoặc rời phòng."""
        self.wash_duration_frames[nurse_id] = 0
        self.is_completed_flags[nurse_id] = False

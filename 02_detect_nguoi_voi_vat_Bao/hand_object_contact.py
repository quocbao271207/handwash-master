"""
Module: hand_object_contact.py
Phụ trách: Thái (Module 02: Detect Người với Vật & Thiết bị ICU)
Mô tả: Nhận diện tương tác Bàn tay - Thiết bị (Hand-Object Interaction HOI Contact State) phục vụ Thời điểm 2, 3, 5.
"""

from typing import Dict, List, Any, Optional, Tuple
import numpy as np


class HandObjectContactDetector:
    def __init__(
        self,
        iou_touch_threshold: float = 0.12,
        min_contact_frames: int = 6,
        fps: float = 30.0,
    ):
        """
        Args:
            iou_touch_threshold: Ngưỡng diện tích chồng lấn giữa BBox Bàn tay và BBox Thiết bị
            min_contact_frames: Số khung hình tiếp xúc liên tục để xác nhận tiếp xúc
            fps: Tốc độ khung hình
        """
        self.iou_touch_threshold = iou_touch_threshold
        self.min_contact_frames = min_contact_frames
        self.fps = fps
        # Lưu số frame tiếp xúc: (nurse_id, roi_idx) -> frame_count
        self.contact_accumulators: Dict[Tuple[int, int], int] = {}

    def detect_contacts(
        self,
        nurses_hand_bboxes: List[Dict[str, Any]],
        active_rois: List[Dict[str, Any]],
        frame_id: int
    ) -> List[Dict[str, Any]]:
        """
        Kiểm tra tiếp xúc giữa bàn tay của tất cả y tá với các vùng ROI thiết bị.
        
        Args:
            nurses_hand_bboxes: Danh sách {'nurse_id': int, 'hand_type': 'LEFT'|'RIGHT', 'bbox': [x1, y1, x2, y2]}
            active_rois: Danh sách ROI từ DynamicROIManager
            frame_id: Thứ tự khung hình hiện tại
            
        Returns:
            List[Dict]: Danh sách sự kiện EquipmentContactEvent
        """
        contact_events = []

        for nurse_hand in nurses_hand_bboxes:
            nid = nurse_hand["nurse_id"]
            hand_box = nurse_hand["bbox"]

            for roi_idx, roi in enumerate(active_rois):
                roi_box = roi["bbox"]
                overlap_iou = self._compute_bbox_iou(hand_box, roi_box)
                
                pair_key = (nid, roi_idx)
                if overlap_iou >= self.iou_touch_threshold:
                    self.contact_accumulators[pair_key] = self.contact_accumulators.get(pair_key, 0) + 1
                else:
                    self.contact_accumulators[pair_key] = max(0, self.contact_accumulators.get(pair_key, 0) - 2)

                frames_active = self.contact_accumulators.get(pair_key, 0)
                if frames_active >= self.min_contact_frames:
                    contact_events.append({
                        "frame_id": frame_id,
                        "timestamp": frame_id / self.fps,
                        "nurse_id": nid,
                        "equipment_type": roi["class_name"],
                        "is_aseptic_zone": roi["is_aseptic_zone"],
                        "is_body_fluid_risk": roi["is_body_fluid_risk"],
                        "is_sanitizer": roi["is_sanitizer"],
                        "contact_iou": float(overlap_iou),
                        "contact_duration_sec": frames_active / self.fps
                    })

        return contact_events

    def _compute_bbox_iou(self, boxA: List[float], boxB: List[float]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter_w = max(0.0, xB - xA)
        inter_h = max(0.0, yB - yA)
        inter_area = inter_w * inter_h

        boxA_area = max(1.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        boxB_area = max(1.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

        # Dùng Overlap Ratio tương đối theo diện tích bàn tay
        return inter_area / boxA_area

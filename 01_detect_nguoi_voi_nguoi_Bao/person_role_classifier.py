"""
Module: person_role_classifier.py
Phụ trách: Bảo (Module 01: Detect Người với Người)
Mô tả: Phân loại vai trò trong ICU: Y tá/Bác sĩ (Nurse - di chuyển linh hoạt) vs Bệnh nhân (Patient - nằm bất động trên giường).
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import numpy as np


class PersonRoleClassifier:
    def __init__(
        self,
        velocity_window: int = 30,
        velocity_threshold: float = 2.5,
        bed_roi_overlap_thresh: float = 0.5,
    ):
        """
        Args:
            velocity_window: Số frames tính vận tốc trung bình của tâm đối tượng
            velocity_threshold: Ngưỡng vận tốc pixel/frame để phân biệt đứng yên vs di chuyển
            bed_roi_overlap_thresh: Ngưỡng IoU/Overlap với vùng giường bệnh
        """
        self.velocity_window = velocity_window
        self.velocity_threshold = velocity_threshold
        self.bed_roi_overlap_thresh = bed_roi_overlap_thresh
        
        # Lưu lịch sử tâm đối tượng {track_id: deque([(x, y, frame_id)])}
        self.position_history: Dict[int, deque] = {}
        # Lưu nhãn vai trò đã gán {track_id: "NURSE" | "PATIENT"}
        self.role_cache: Dict[int, str] = {}

    def update_roles(
        self,
        tracked_persons: List[Dict[str, Any]],
        bed_roi: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Phân loại vai trò cho danh sách đối tượng người trong khung hình.
        
        Args:
            tracked_persons: Danh sách người từ PoseTracker
            bed_roi: Tọa độ vùng giường bệnh [x1, y1, x2, y2] (nhận từ Module 2 của Thái)
            
        Returns:
            List[Dict]: Danh sách người được bổ sung trường 'role' ("NURSE" hoặc "PATIENT")
        """
        for person in tracked_persons:
            tid = person["track_id"]
            bbox = person["bbox"]
            center_x = (bbox[0] + bbox[2]) / 2.0
            center_y = (bbox[1] + bbox[3]) / 2.0
            
            if tid not in self.position_history:
                self.position_history[tid] = deque(maxlen=self.velocity_window)
            self.position_history[tid].append((center_x, center_y))

            # Tính vận tốc trung bình
            avg_velocity = self._compute_average_velocity(tid)
            
            # Kiểm tra vị trí nằm trong giường bệnh
            in_bed = self._is_inside_bed_roi(bbox, bed_roi) if bed_roi else False

            # Logic phân loại
            if in_bed and avg_velocity < self.velocity_threshold:
                role = "PATIENT"
            else:
                role = "NURSE"

            self.role_cache[tid] = role
            person["role"] = role
            person["avg_velocity"] = avg_velocity

        return tracked_persons

    def _compute_average_velocity(self, track_id: int) -> float:
        history = self.position_history[track_id]
        if len(history) < 2:
            return 0.0
        
        total_dist = 0.0
        for i in range(1, len(history)):
            p1 = np.array(history[i - 1])
            p2 = np.array(history[i])
            total_dist += np.linalg.norm(p2 - p1)
        return float(total_dist / (len(history) - 1))

    def _is_inside_bed_roi(self, bbox: List[float], bed_roi: List[float]) -> bool:
        """Kiểm tra tỷ lệ diện tích giao nhau giữa BBox người và Bed ROI."""
        bx1, by1, bx2, by2 = bbox
        rx1, ry1, rx2, ry2 = bed_roi
        
        ix1 = max(bx1, rx1)
        iy1 = max(by1, ry1)
        ix2 = min(bx2, rx2)
        iy2 = min(by2, ry2)
        
        if ix2 <= ix1 or iy2 <= iy1:
            return False
        
        intersection = (ix2 - ix1) * (iy2 - iy1)
        person_area = max(1.0, (bx2 - bx1) * (by2 - by1))
        return (intersection / person_area) >= self.bed_roi_overlap_thresh

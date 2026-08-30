"""
Module: self_touch_detector.py
Phụ trách: Vinh (Module 03: Detect Tự Chạm Tay & Nhận diện Rửa Tay)
Mô tả: Nhận diện 2 bàn tay tự chạm nhau (Self-touching Detection) sử dụng Scale-Aware Distance.
"""

from typing import Dict, List, Any, Tuple
import numpy as np
from scale_normalizer import ScaleNormalizer


class SelfTouchDetector:
    def __init__(
        self,
        touch_threshold_gamma: float = 0.42,
        min_consecutive_frames: int = 5,
        fps: float = 30.0,
    ):
        """
        Args:
            touch_threshold_gamma: Ngưỡng khoảng cách chuẩn hóa D_norm để coi là tự chạm tay
            min_consecutive_frames: Số frames thỏa mãn liên tục để xác nhận
            fps: Tốc độ khung hình
        """
        self.touch_threshold_gamma = touch_threshold_gamma
        self.min_consecutive_frames = min_consecutive_frames
        self.fps = fps
        self.normalizer = ScaleNormalizer()
        self.touch_history: Dict[int, int] = {}  # nurse_id -> frame_count

    def detect_self_touch(
        self,
        nurse_persons: List[Dict[str, Any]],
        frame_id: int
    ) -> List[Dict[str, Any]]:
        """
        Kiểm tra trạng thái tự chạm tay cho từng nhân viên y tế.
        
        Returns:
            List[Dict]: Danh sách kết quả self-touching kèm tọa độ vùng hộp bao 2 bàn tay gộp
        """
        results = []

        for nurse in nurse_persons:
            nid = nurse["track_id"]
            kpts = nurse["keypoints"]
            bbox = nurse.get("bbox")

            d_norm, raw_dist = self.normalizer.compute_normalized_wrist_distance(kpts, bbox)
            is_close = d_norm < self.touch_threshold_gamma

            if is_close:
                self.touch_history[nid] = self.touch_history.get(nid, 0) + 1
            else:
                self.touch_history[nid] = max(0, self.touch_history.get(nid, 0) - 2)

            is_self_touching = self.touch_history.get(nid, 0) >= self.min_consecutive_frames

            # Ước lượng Hand ROI Box để cắt (crop) cho mô hình Action Classifier
            hand_roi_box = self._extract_hands_combined_bbox(kpts, bbox)

            results.append({
                "nurse_id": nid,
                "frame_id": frame_id,
                "timestamp": frame_id / self.fps,
                "d_norm": float(d_norm),
                "raw_pixel_dist": float(raw_dist),
                "is_self_touching": bool(is_self_touching),
                "hand_roi_box": hand_roi_box,
                "consecutive_touch_frames": self.touch_history.get(nid, 0)
            })

        return results

    def _extract_hands_combined_bbox(
        self,
        keypoints: np.ndarray,
        nurse_bbox: List[float]
    ) -> List[float]:
        """Tạo Bounding Box bao quanh 2 cổ tay với lề an toàn (padding)."""
        l_wrist = keypoints[9][:2]
        r_wrist = keypoints[10][:2]

        pts = np.array([l_wrist, r_wrist])
        x_min, y_min = np.min(pts, axis=0)
        x_max, y_max = np.max(pts, axis=0)

        # Padding dựa trên kích thước thân
        pad = 40.0
        return [
            max(0.0, float(x_min - pad)),
            max(0.0, float(y_min - pad)),
            float(x_max + pad),
            float(y_max + pad)
        ]

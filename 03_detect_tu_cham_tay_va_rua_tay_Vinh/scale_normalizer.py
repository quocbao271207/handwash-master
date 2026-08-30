"""
Module: scale_normalizer.py
Phụ trách: Vinh (Module 03: Detect Tự Chạm Tay & Nhận diện Rửa Tay)
Mô tả: Thuật toán Scale-Aware Body Normalization chuẩn hóa khoảng cách theo tỉ lệ cơ thể thực tế.
"""

from typing import List, Tuple, Optional
import math
import numpy as np


class ScaleNormalizer:
    def __init__(self, fallback_bbox_scale: float = 0.28):
        """
        Args:
            fallback_bbox_scale: Tỉ lệ ước lượng kích thước vai từ đường chéo Bounding Box người
        """
        self.fallback_bbox_scale = fallback_bbox_scale

    def compute_body_scale(self, keypoints: np.ndarray, bbox: Optional[List[float]] = None) -> float:
        """
        Tính chiều dài chuẩn hóa cơ thể (L_norm) từ khoảng cách 2 vai hoặc cẳng tay.
        
        Keypoints format: (17, 3) [x, y, conf]
          - 5: Left Shoulder, 6: Right Shoulder
          - 7: Left Elbow, 8: Right Elbow
          - 9: Left Wrist, 10: Right Wrist
        """
        l_sh = keypoints[5]
        r_sh = keypoints[6]

        # Phương án 1: Nếu thấy rõ cả 2 vai (confidence > 0.35)
        if l_sh[2] > 0.35 and r_sh[2] > 0.35:
            shoulder_dist = np.linalg.norm(l_sh[:2] - r_sh[:2])
            if shoulder_dist > 5.0:
                return float(shoulder_dist)

        # Phương án 2: Dùng chiều dài cẳng tay (Elbow - Wrist) * 1.6
        l_el, l_wr = keypoints[7], keypoints[9]
        r_el, r_wr = keypoints[8], keypoints[10]

        if l_el[2] > 0.35 and l_wr[2] > 0.35:
            forearm_len = np.linalg.norm(l_el[:2] - l_wr[:2])
            if forearm_len > 5.0:
                return float(forearm_len * 1.6)

        if r_el[2] > 0.35 and r_wr[2] > 0.35:
            forearm_len = np.linalg.norm(r_el[:2] - r_wr[:2])
            if forearm_len > 5.0:
                return float(forearm_len * 1.6)

        # Phương án 3: Dự phòng theo BBox
        if bbox is not None:
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            diag = math.sqrt(w * w + h * h)
            return float(diag * self.fallback_bbox_scale)

        return 100.0  # Giá trị an toàn mặc định

    def compute_normalized_wrist_distance(
        self,
        keypoints: np.ndarray,
        bbox: Optional[List[float]] = None
    ) -> Tuple[float, float]:
        """
        Tính khoảng cách chuẩn hóa giữa 2 cổ tay: D_norm = ||W_L - W_R|| / L_norm.
        
        Returns:
            Tuple[float, float]: (D_norm, raw_pixel_distance)
        """
        l_wrist = keypoints[9]
        r_wrist = keypoints[10]

        if l_wrist[2] < 0.25 or r_wrist[2] < 0.25:
            return 999.0, 999.0

        raw_dist = float(np.linalg.norm(l_wrist[:2] - r_wrist[:2]))
        l_norm = self.compute_body_scale(keypoints, bbox)
        d_norm = raw_dist / max(1e-3, l_norm)

        return d_norm, raw_dist

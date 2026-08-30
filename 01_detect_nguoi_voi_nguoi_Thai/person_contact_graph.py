"""
Module: person_contact_graph.py
Phụ trách: Bảo (Module 01: Detect Người với Người)
Mô tả: Đồ thị tương tác không-thời gian (Spatio-Temporal Keypoint Interaction Graph) và Bộ lọc chống rung One-Euro Filter.
"""

from typing import Dict, List, Any, Optional, Tuple
import math
import numpy as np


class OneEuroFilter:
    """Bộ lọc 1€ (One-Euro Filter) chống rung giật cho chuỗi tọa độ keypoints."""
    def __init__(self, freq: float = 30.0, mincutoff: float = 1.0, beta: float = 0.007, dcutoff: float = 1.0):
        self.freq = freq
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.x_prev = None
        self.dx_prev = 0.0

    def _alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        te = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: np.ndarray) -> np.ndarray:
        if self.x_prev is None:
            self.x_prev = x
            return x
        
        dx = (x - self.x_prev) * self.freq
        edx = self._alpha(self.dcutoff) * dx + (1 - self._alpha(self.dcutoff)) * self.dx_prev
        self.dx_prev = edx
        
        cutoff = self.mincutoff + self.beta * np.abs(edx)
        alpha = self._alpha(np.mean(cutoff))
        x_hat = alpha * x + (1 - alpha) * self.x_prev
        self.x_prev = x_hat
        return x_hat


class PersonContactGraph:
    """
    Xác định sự kiện tiếp xúc giữa Bàn tay Y tá và Cơ thể Bệnh nhân (WHO Moments 1 & 4).
    COCO Keypoints Index:
      - 9: Left Wrist, 10: Right Wrist
      - 5, 6: Shoulders; 11, 12: Hips
    """
    def __init__(
        self,
        contact_threshold: float = 0.35,
        min_touch_duration_sec: float = 0.3,
        fps: float = 30.0,
    ):
        self.contact_threshold = contact_threshold
        self.min_touch_frames = int(min_touch_duration_sec * fps)
        self.fps = fps
        self.touch_accumulators: Dict[Tuple[int, int], int] = {}  # (nurse_id, patient_id) -> frame_count
        self.filters: Dict[int, OneEuroFilter] = {}

    def compute_contact(
        self,
        persons: List[Dict[str, Any]],
        frame_id: int
    ) -> List[Dict[str, Any]]:
        """
        Tính toán tiếp xúc giữa mọi cặp (Nurse, Patient) trong khung hình.
        
        Returns:
            List[Dict]: Danh sách sự kiện tiếp xúc PersonContactEvent
        """
        nurses = [p for p in persons if p.get("role") == "NURSE"]
        patients = [p for p in persons if p.get("role") == "PATIENT"]
        
        events = []
        
        for nurse in nurses:
            nid = nurse["track_id"]
            if nid not in self.filters:
                self.filters[nid] = OneEuroFilter(freq=self.fps)
            
            # Keypoints lọc chống rung
            nurse_kpts = self.filters[nid].filter(nurse["keypoints"])
            
            # Cổ tay trái & phải của y tá
            left_wrist = nurse_kpts[9][:2]
            right_wrist = nurse_kpts[10][:2]
            nurse_wrists = [("LEFT_WRIST", left_wrist), ("RIGHT_WRIST", right_wrist)]

            for patient in patients:
                pid = patient["track_id"]
                patient_kpts = patient["keypoints"]
                
                # Tính kích thước thân bệnh nhân (vai - hông) để chuẩn hóa
                torso_len = self._compute_torso_length(patient_kpts)
                if torso_len <= 1e-3:
                    torso_len = 100.0  # Fallback nếu keypoint thân bị khuất

                is_touching, min_dist, closest_part = self._check_wrist_to_patient_contact(
                    nurse_wrists, patient_kpts, torso_len
                )
                
                pair_key = (nid, pid)
                if is_touching:
                    self.touch_accumulators[pair_key] = self.touch_accumulators.get(pair_key, 0) + 1
                else:
                    self.touch_accumulators[pair_key] = max(0, self.touch_accumulators.get(pair_key, 0) - 2)

                consecutive_frames = self.touch_accumulators.get(pair_key, 0)
                touch_confirmed = consecutive_frames >= self.min_touch_frames
                
                if touch_confirmed:
                    events.append({
                        "frame_id": frame_id,
                        "timestamp": frame_id / self.fps,
                        "nurse_id": nid,
                        "patient_id": pid,
                        "is_touching": True,
                        "contact_confidence": float(np.clip(1.0 - (min_dist / self.contact_threshold), 0.5, 1.0)),
                        "nurse_wrist_pos": left_wrist.tolist(),
                        "patient_body_part": closest_part,
                        "touch_duration_sec": consecutive_frames / self.fps
                    })

        return events

    def _compute_torso_length(self, kpts: np.ndarray) -> float:
        l_shoulder, r_shoulder = kpts[5][:2], kpts[6][:2]
        l_hip, r_hip = kpts[11][:2], kpts[12][:2]
        shoulder_mid = (l_shoulder + r_shoulder) / 2.0
        hip_mid = (l_hip + r_hip) / 2.0
        return float(np.linalg.norm(shoulder_mid - hip_mid))

    def _check_wrist_to_patient_contact(
        self,
        nurse_wrists: List[Tuple[str, np.ndarray]],
        patient_kpts: np.ndarray,
        torso_len: float
    ) -> Tuple[bool, float, str]:
        min_normalized_dist = 999.0
        closest_part = "UNKNOWN"

        body_parts = {
            "HEAD": [0, 1, 2, 3, 4],
            "UPPER_BODY": [5, 6, 11, 12],
            "ARMS": [7, 8, 9, 10],
            "LEGS": [13, 14, 15, 16]
        }

        for _, w_pos in nurse_wrists:
            for part_name, idx_list in body_parts.items():
                for k_idx in idx_list:
                    k_pos = patient_kpts[k_idx][:2]
                    conf = patient_kpts[k_idx][2]
                    if conf > 0.3:
                        dist = np.linalg.norm(w_pos - k_pos)
                        norm_dist = dist / torso_len
                        if norm_dist < min_normalized_dist:
                            min_normalized_dist = norm_dist
                            closest_part = part_name

        is_touch = min_normalized_dist < self.contact_threshold
        return is_touch, min_normalized_dist, closest_part

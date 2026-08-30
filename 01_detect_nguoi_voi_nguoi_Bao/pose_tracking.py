"""
Module: pose_tracking.py
Phụ trách: Bảo (Module 01: Detect Người với Người)
Mô tả: Ước lượng tư thế đa người (Multi-Person Pose Estimation) và theo dõi bám vết (BoT-SORT Tracking).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np


class PoseTracker:
    def __init__(
        self,
        model_weights: str = "yolo11x-pose.pt",
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        track_buffer: int = 30,
    ):
        """
        Khởi tạo bộ theo dõi tư thế đa người.
        
        Args:
            model_weights: Đường dẫn tới trọng số YOLO11-pose hoặc RTMPose
            conf_threshold: Ngưỡng tự tin phát hiện người
            iou_threshold: Ngưỡng IoU cho bộ theo dõi
            track_buffer: Số frame lưu vết khi mất dấu đối tượng
        """
        self.model_weights = model_weights
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.track_buffer = track_buffer
        self.model = None  # Sẽ nạp ultralytics.YOLO(model_weights) khi chạy thực tế

    def load_model(self):
        """Nạp mô hình YOLO pose vào bộ nhớ GPU/CPU."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_weights)
            print(f"[PoseTracker] Đã nạp thành công mô hình: {self.model_weights}")
        except ImportError:
            print("[PoseTracker] Cảnh báo: Chưa cài đặt ultralytics. Đang chạy chế độ mô phỏng.")

    def track_frame(self, frame: np.ndarray, frame_id: int) -> List[Dict[str, Any]]:
        """
        Xử lý 1 khung hình video, trả về danh sách đối tượng có Track ID, BBox và 17 Keypoints.
        
        Args:
            frame: Ảnh RGB dạng numpy array (H, W, 3)
            frame_id: Thứ tự khung hình hiện tại
            
        Returns:
            List[Dict]: Danh sách các đối tượng người phát hiện được:
                - track_id: int
                - bbox: [x1, y1, x2, y2]
                - keypoints: ndarray shape (17, 3) [x, y, confidence]
                - conf: float
        """
        tracked_persons = []
        
        if self.model is not None:
            results = self.model.track(
                frame,
                persist=True,
                tracker="botsort.yaml",
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False
            )
            for res in results:
                if res.boxes is not None and res.keypoints is not None:
                    boxes = res.boxes.xyxy.cpu().numpy()
                    track_ids = res.boxes.id.int().cpu().numpy() if res.boxes.id is not None else range(len(boxes))
                    kpts = res.keypoints.data.cpu().numpy()  # (N, 17, 3)
                    confs = res.boxes.conf.cpu().numpy()

                    for idx, tid in enumerate(track_ids):
                        tracked_persons.append({
                            "track_id": int(tid),
                            "bbox": boxes[idx].tolist(),
                            "keypoints": kpts[idx],
                            "conf": float(confs[idx]),
                            "frame_id": frame_id
                        })
        return tracked_persons

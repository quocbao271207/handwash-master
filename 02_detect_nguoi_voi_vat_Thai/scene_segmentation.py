"""
Module: scene_segmentation.py
Phụ trách: Thái (Module 02: Detect Người với Vật & Thiết bị ICU)
Mô tả: Phân đoạn ngữ nghĩa không gian ICU (Semantic Scene Parsing & Segmentation) bằng YOLO11-Seg.
"""

from typing import Dict, List, Any, Optional
import numpy as np


class ICUSceneSegmenter:
    def __init__(
        self,
        model_weights: str = "yolo11x-seg.pt",
        conf_threshold: float = 0.45,
        target_classes: Optional[List[str]] = None,
    ):
        """
        Khởi tạo module phân đoạn thiết bị phòng ICU.
        
        Args:
            model_weights: Trọng số mô hình YOLO11-Seg
            conf_threshold: Ngưỡng tự tin nhận diện
            target_classes: Danh sách nhãn cần trích xuất (máy thở, monitor, giường, v.v.)
        """
        self.model_weights = model_weights
        self.conf_threshold = conf_threshold
        self.target_classes = target_classes or [
            "bed", "ventilator", "monitor", "infusion_pump",
            "aseptic_tray", "drainage_bag", "sanitizer_dispenser"
        ]
        self.model = None

    def load_model(self):
        """Nạp mô hình Segmentation vào bộ nhớ GPU/CPU."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_weights)
            print(f"[ICUSceneSegmenter] Đã nạp thành công mô hình: {self.model_weights}")
        except ImportError:
            print("[ICUSceneSegmenter] Cảnh báo: Chưa cài đặt ultralytics. Đang chạy chế độ mô phỏng.")

    def segment_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Phân đoạn một khung hình, trả về danh sách đối tượng thiết bị kèm Polygon Mask & BBox.
        
        Args:
            frame: Ảnh RGB dạng numpy array (H, W, 3)
            
        Returns:
            List[Dict]: Danh sách thiết bị ICU phát hiện được:
                - class_name: str
                - confidence: float
                - bbox: [x1, y1, x2, y2]
                - mask_polygon: List[List[float]] (Tọa độ polygon viền đối tượng)
        """
        detected_objects = []
        if self.model is not None:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)
            for res in results:
                if res.boxes is not None:
                    boxes = res.boxes.xyxy.cpu().numpy()
                    classes = res.boxes.cls.cpu().numpy()
                    confs = res.boxes.conf.cpu().numpy()
                    names = res.names

                    masks = res.masks.xy if res.masks is not None else [None] * len(boxes)

                    for idx, cls_id in enumerate(classes):
                        cls_name = names[int(cls_id)]
                        detected_objects.append({
                            "class_name": cls_name,
                            "confidence": float(confs[idx]),
                            "bbox": boxes[idx].tolist(),
                            "mask_polygon": masks[idx].tolist() if masks[idx] is not None else []
                        })
        return detected_objects

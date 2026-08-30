"""
Module: dynamic_roi_manager.py
Phụ trách: Thái (Module 02: Detect Người với Vật & Thiết bị ICU)
Mô tả: Quản lý & Caching các vùng ROI thiết bị, phân nhóm Aseptic ROI vs Biohazard ROI và kích hoạt chạy segmentation định kỳ.
"""

from typing import Dict, List, Any, Optional
import numpy as np


class DynamicROIManager:
    def __init__(self, seg_interval_frames: int = 45):
        """
        Args:
            seg_interval_frames: Chu kỳ số frames chạy lại segmentation (45 frames ~ 1.5s @ 30 FPS)
        """
        self.seg_interval_frames = seg_interval_frames
        self.cached_rois: List[Dict[str, Any]] = []
        self.last_segmented_frame: int = -999

        # Phân loại nhóm đối tượng y tế
        self.aseptic_classes = {"aseptic_tray", "catheter", "sterile_field"}
        self.biohazard_classes = {"drainage_bag", "body_fluid_tube", "waste_bin"}
        self.equipment_classes = {"ventilator", "monitor", "infusion_pump", "bed_rail", "iv_pole"}
        self.sanitizer_classes = {"sanitizer_dispenser", "alcohol_rub"}

    def should_run_segmentation(self, frame_id: int, force_update: bool = False) -> bool:
        """Kiểm tra xem khung hình hiện tại có cần chạy model segmentation nặng hay dùng cache."""
        if force_update:
            return True
        return (frame_id - self.last_segmented_frame) >= self.seg_interval_frames

    def update_rois_from_segmentation(self, detected_objects: List[Dict[str, Any]], frame_id: int):
        """Cập nhật bộ nhớ đệm ROI từ kết quả segmentation mới nhất."""
        self.cached_rois = []
        for obj in detected_objects:
            cls = obj["class_name"].lower()
            is_aseptic = cls in self.aseptic_classes
            is_biohazard = cls in self.biohazard_classes
            is_sanitizer = cls in self.sanitizer_classes
            is_surrounding = cls in self.equipment_classes

            self.cached_rois.append({
                "class_name": cls.upper(),
                "bbox": obj["bbox"],
                "mask_polygon": obj.get("mask_polygon", []),
                "is_aseptic_zone": is_aseptic,
                "is_body_fluid_risk": is_biohazard,
                "is_sanitizer": is_sanitizer,
                "is_surrounding_equipment": is_surrounding
            })
        self.last_segmented_frame = frame_id

    def get_active_rois(self) -> List[Dict[str, Any]]:
        """Trả về danh sách ROI thiết bị đang hoạt động trong phòng."""
        return self.cached_rois

    def get_bed_roi(self) -> Optional[List[float]]:
        """Lấy BBox giường bệnh để chia sẻ cho Module 1 (Bảo)."""
        for r in self.cached_rois:
            if r["class_name"] == "BED":
                return r["bbox"]
        return None

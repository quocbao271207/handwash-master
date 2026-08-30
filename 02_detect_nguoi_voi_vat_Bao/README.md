# MODULE 02: PHÁT HIỆN TƯƠNG TÁC NGƯỜI VỚI VẬT & THIẾT BỊ ICU (HUMAN-OBJECT INTERACTION)
> **Phụ trách:** **Thái**  
> **Thư mục:** `02_detect_nguoi_voi_vat_Thai/`  
> **Phạm vi giám sát:** Thời điểm vàng WHO số **2** (*Trước thủ thuật vô trùng*), số **3** (*Sau tiếp xúc dịch cơ thể*), và số **5** (*Sau khi chạm vật dụng xung quanh*).

---

## 1. TỔNG QUAN NHIỆM VỤ CỦA THÁI

Module này đóng vai trò quyết định trong việc mở rộng hệ thống từ 2 nhãn cơ bản lên trọn vẹn cả 5 thời điểm WHO:
1. **Phân đoạn ngữ nghĩa không gian ICU (Semantic Scene Parsing):** Tự động phát hiện và tạo mặt nạ (Mask/Polygon) cho các thiết bị y tế phòng ICU (`Ventilator`, `Monitor`, `InfusionPump`, `Bed_Rail`, `Sanitizer_Dispenser`).
2. **Quản lý Dynamic ROI & Vùng Vô Trùng / Dịch Tiết:**
   - `Patient Zone`: Vùng không gian quanh giường bệnh.
   - `Aseptic ROI`: Vùng vô khuẩn (vị trí ống catheter, đường truyền tĩnh mạch trung tâm, ống nội khí quản, khay dụng cụ sạch).
   - `Body Fluid Risk ROI`: Vùng dẫn lưu dịch, sonde tiểu, bỉm/chất thải.
3. **Phát hiện tương tác Bàn tay - Thiết bị (Hand-Object Interaction - HOI Contact State):** Xác định sự kiện chạm (Contact State: `No Contact`, `Touching Device`, `Touching Aseptic Zone`, `Touching Biohazard Zone`).
4. **Tối ưu hóa GPU Caching (Dynamic ROI Caching):** Không chạy full segmentation mỗi frame (tránh quá tải GPU); chỉ chạy định kỳ (mỗi 1.5 - 2s hoặc khi cảnh biến động) và bám vết nhanh bằng Mask Overlap Gradient.

```
   [Camera Stream ICU]
           │
           ├────────────────────────────┐ (Mỗi 30-60 frames / Cảnh đổi)
           ▼                            ▼
   [Hand BBoxes từ Module 1 của Bảo] [YOLO11-Seg Semantic Parser]
           │                            │
           │                   [Dynamic ROI Manager]
           │                   - Aseptic ROI (Catheter, Tray)
           │                   - Biohazard ROI (Fluid tube)
           │                   - Medical Devices (Ventilator, Monitor)
           │                            │
           └──────────────┬─────────────┘
                          ▼
             [HOI Contact State Network]
             (Mask IoU / Overlap Gradient)
                          │
                          ▼
             [OUTPUT: EquipmentContactEvent] ──► (Gửi về 00_core_system_fsm)
```

---

## 2. CƠ SỞ LÝ THUYẾT & THUẬT TOÁN ĐỀ XUẤT

### 2.1. Phân đoạn Ngữ nghĩa Thiết bị ICU (Semantic Segmentation)
- **Mô hình đề xuất:** `YOLO11-seg` hoặc `MobileSAM` / `FastSAM`.
- **Tập nhãn ICU Classes:**
  1. `bed`: Giường bệnh (gốc của Patient Zone).
  2. `ventilator`: Máy thở nhân tạo.
  3. `infusion_pump`: Bơm tiêm điện, máy truyền dịch.
  4. `monitor`: Màn hình theo dõi sinh hiệu.
  5. `aseptic_tray`: Khay dụng cụ vô khuẩn / cổng tiêm catheter.
  6. `drainage_bag`: Túi dẫn lưu / ống dẫn dịch cơ thể.
  7. `sanitizer_dispenser`: Bình cồn sát khuẩn tay gắn tường/đầu giường.

### 2.2. Cơ chế Dynamic ROI Caching (Tối ưu hóa GPU)
Vì các thiết bị ICU lớn phần lớn là tĩnh hoặc di chuyển chậm:
- **Tần suất phân đoạn:** Chạy Full Segmentation với chu kỳ $T_{\text{seg}} = 1.5\text{s}$ (45 frames @ 30 FPS).
- **Kiểm tra dịch chuyển (Scene Shift Detector):** Dùng Background Subtraction / Optical Flow để phát hiện nếu có xe tiêm hoặc thiết bị mới đưa vào phòng $\rightarrow$ Kích hoạt chạy lại phân đoạn ngay lập tức.
- **Tiết kiệm tài nguyên:** Giảm tải GPU từ 85% xuống dưới 20%, dành tài nguyên cho Pose Tracking và Action Recognition.

### 2.3. Thuật toán Hand-Object Contact State (HOI)
Xác định mức độ tiếp xúc giữa Bàn tay Y tá ($BBox_{\text{Hand}}$ hoặc Hand Mask $\mathbf{M}_{\text{Hand}}$) và Mặt nạ Thiết bị $\mathbf{M}_{\text{Device}}$:
1. **Intersection over Union (IoU) & Overlap Ratio:**
   $$Overlap(\mathbf{M}_{\text{Hand}}, \mathbf{M}_{\text{Device}}) = \frac{|\mathbf{M}_{\text{Hand}} \cap \mathbf{M}_{\text{Device}}|}{|\mathbf{M}_{\text{Hand}}|}$$
2. **Khoảng cách Euclidean tới đường biên (Contour Distance):**
   Nếu $Overlap > 0.15$ hoặc khoảng cách từ tâm bàn tay đến viền mặt nạ thiết bị $d(\mathbf{P}_{\text{Hand}}, \partial \mathbf{M}_{\text{Device}}) < \delta_{\text{touch}}$, ghi nhận trạng thái tiếp xúc:
   $$\text{ContactType} = \begin{cases} \text{ASEPTIC\_ZONE} & \text{nếu } \text{Device} \in \{\text{Catheter}, \text{Aseptic Tray}\} \\ \text{BODY\_FLUID} & \text{nếu } \text{Device} \in \{\text{Drainage Bag}, \text{Fluid Tube}\} \\ \text{EQUIPMENT} & \text{nếu } \text{Device} \in \{\text{Ventilator}, \text{Monitor}, \text{Bed Rail}\} \end{cases}$$

---

## 3. CHUẨN HÓA GIAO TIẾP DỮ LIỆU (I/O DATA CONTRACT)

### Input yêu cầu:
- Khung hình Video RGB từ camera ICU.
- Danh sách `nurse_id` kèm tọa độ bàn tay / cổ tay từ Module 1 của Bảo.

### Output gửi cho hệ thống (`EquipmentContactEvent`):
```json
{
  "frame_id": 1120,
  "timestamp": 37.333,
  "nurse_id": 1,
  "equipment_type": "VENTILATOR",
  "is_aseptic_zone": false,
  "is_body_fluid_risk": false,
  "contact_iou": 0.38,
  "contact_duration_sec": 0.8
}
```
*(Nếu chạm vào vùng catheter: `"is_aseptic_zone": true` $\rightarrow$ Trigger FSM kiểm tra Thời điểm 2)*  
*(Nếu chạm vào túi dẫn lưu: `"is_body_fluid_risk": true` $\rightarrow$ Trigger FSM hạ trạng thái xuống `BIOHAZARD` cho Thời điểm 3)*  
*(Nếu chạm vào máy thở/thanh giường: `"equipment_type": "VENTILATOR"` $\rightarrow$ Trigger FSM cho Thời điểm 5)*

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT (TASK BREAKDOWN FOR THÁI)

- [ ] **Task 2.1: Huấn luyện / Tinh chỉnh YOLO11-Seg trên dữ liệu thiết bị ICU**
  - Fine-tune bộ trọng số segmentation cho 7 lớp thiết bị ICU (`scene_segmentation.py`).
- [ ] **Task 2.2: Xây dựng Dynamic ROI Manager**
  - Cài đặt `dynamic_roi_manager.py`: Bộ nhớ đệm ROI, tự động phân nhóm Aseptic ROI vs Biohazard ROI và Scene Shift Trigger.
- [ ] **Task 2.3: Xây dựng Mạng phát hiện Hand-Object Contact**
  - Hoàn thiện `hand_object_contact.py`: Tính tỷ lệ chồng lấn mặt nạ bàn tay và bounding box thiết bị.
- [ ] **Task 2.4: Tích hợp với Module 1 (Bảo) và Module FSM**
  - Nhận BBox bàn tay từ Bảo, xuất sự kiện `EquipmentContactEvent` gửi sang FSM Engine.
- [ ] **Task 2.5: Đánh giá & Tối ưu độ trễ GPU**
  - Đo mIoU phân đoạn, benchmark tốc độ khi bật GPU Caching.

---

## 5. OUTPUT CẦN ĐẠT (DELIVERABLES & METRICS)

1. **Deliverables:**
   - Mã nguồn hoàn chỉnh: `scene_segmentation.py`, `dynamic_roi_manager.py`, `hand_object_contact.py`.
   - File cấu hình và tọa độ mẫu ICU: `icu_rois_config.yaml`.
   - Video demo phân vùng trực quan (Overlay Segmentation Masks + Equipment Contact Bounding Boxes).
2. **Chỉ số kỹ thuật bắt buộc (KPIs):**
   - **Độ chính xác phân đoạn (mIoU):** $\ge 80\%$ trên tập thiết bị ICU chính.
   - **Độ chính xác phát hiện chạm thiết bị (HOI Contact Accuracy):** $\ge 88\%$.
   - **Tần suất chạy Segmentation:** $1.5\text{s} - 2.0\text{s}$ (không lag luồng chính).
   - **Độ trễ xử lý contact frame-by-frame:** $\le 10$ ms/frame.

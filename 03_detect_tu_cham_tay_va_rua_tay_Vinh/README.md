# MODULE 03: PHÁT HIỆN TỰ CHẠM TAY & NHẬN DIỆN HÀNH ĐỘNG RỬA TAY
> **Phụ trách:** **Vinh**  
> **Thư mục:** `03_detect_tu_cham_tay_va_rua_tay_Vinh/`  
> **Phạm vi giám sát:** Điều kiện tiên quyết và Hành động xác lập trạng thái Vô trùng (`STERILE`) cho cả 5 thời điểm WHO.

---

## 1. TỔNG QUAN NHIỆM VỤ CỦA VINH

Module 03 là "trái tim" của hệ thống đánh giá kỹ thuật vệ sinh tay:
1. **Thuật toán Scale-Aware Body Normalization:** Khắc phục triệt để lỗi sai khoảng cách pixel cố định khi y tá đứng xa/gần camera bằng cách chuẩn hóa khoảng cách 2 cổ tay theo chiều rộng vai hoặc chiều dài cẳng tay.
2. **Phát hiện 2 bàn tay tự chạm nhau (Self-touching Detection):** Đóng vai trò bộ kích hoạt nhẹ (Lightweight Trigger) để không phải chạy mô hình nhận diện hành động nặng liên tục ở mọi frame.
3. **Cắt và trích xuất chi tiết vùng bàn tay (High-Res Hand Cropper & 21-Keypoints):** Trích xuất vùng ảnh bàn tay hoặc 21 khớp xương bàn tay (MediaPipe Hands / Hand Pose).
4. **Mô hình nhận diện hành động chà xát rửa tay (Spatial-Temporal Action Recognition):** Dùng `ST-GCN` (Graph Convolutional Net) trên 21 keypoints hoặc `TSM-MobileNetV3` để phân biệt chính xác: **Rửa tay thật (Scrubbing)** vs **Nắm tay, Đan tay, Cầm đồ vật, Đứng yên**.
5. **Bộ đếm thời lượng và Xác nhận đạt chuẩn:** Tích lũy thời gian rửa tay liên tục ($\ge 3-5$s trong chế độ thử nghiệm, $\ge 15-20$s trong quy chuẩn lâm sàng) $\rightarrow$ Xuất sự kiện `HandwashStateEvent` chuyển trạng thái y tá thành `STERILE`.

```
        [Tọa độ Keypoints Y tá từ Module 1]
                        │
                        ▼
   [1. Scale-Aware Normalization (L_norm)]
   L_norm = ||Vai Trái - Vai Phải||
   D_norm = ||Cổ tay Trái - Cổ tay Phải|| / L_norm
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
   D_norm < Thresh_touch         D_norm >= Thresh_touch
   (2 Cổ tay áp sát)             (2 Tay cách xa nhau)
         │                             │
         ▼                             ▼
   [2. Hand BBox Cropper]      [Trạng thái: IDLE]
         │
         ▼
   [3. ST-GCN / TSM Action Classifier]
   (Phân biệt Rửa tay vs Cầm vật / Đan tay)
         │
         ▼
   [4. Wash Duration Accumulator]
   (Duy trì liên tục >= T_standard)
         │
         ▼
   [OUTPUT: HandwashStateEvent] ──► (Gửi về 00_core_system_fsm)
```

---

## 2. CƠ SỞ LÝ THUYẾT TOÁN HỌC & THUẬT TOÁN

### 2.1. Chuẩn hóa theo Tỉ lệ Khung xương Cơ thể (Scale-Aware Normalization)
Để khoảng cách đo lường độc lập với cự ly từ nhân viên y tế đến ống kính camera:
1. **Thước đo chuẩn tỷ lệ cơ thể ($L_{\text{norm}}$):**
   $$L_{\text{norm}} = \begin{cases} \|\mathbf{P}_{\text{Left\_Shoulder}} - \mathbf{P}_{\text{Right\_Shoulder}}\|_2 & \text{nếu thấy rõ 2 vai} \\ 1.6 \times \|\mathbf{P}_{\text{Elbow}} - \mathbf{P}_{\text{Wrist}}\|_2 & \text{nếu vai bị che khuất} \\ \sqrt{\text{Area}(BBox_{\text{Nurse}}) \times 0.08} & \text{phương án dự phòng} \end{cases}$$
2. **Khoảng cách tương đối giữa 2 cổ tay ($D_{\text{norm}}$):**
   $$D_{\text{norm}} = \frac{\|\mathbf{P}_{\text{Left\_Wrist}} - \mathbf{P}_{\text{Right\_Wrist}}\|_2}{L_{\text{norm}}}$$
3. **Điều kiện xác nhận Self-touching:**
   $$D_{\text{norm}} < \gamma_{\text{touch}} \quad (\text{với } \gamma_{\text{touch}} \approx 0.38 - 0.45)$$
   Kết hợp điều kiện phụ: Khoảng cách giữa 2 hộp bao bàn tay $IoU(BBox_{\text{Left\_Hand}}, BBox_{\text{Right\_Hand}}) > 0.15$.

### 2.2. Nhận diện Hành động Rửa tay Không-Thời Gian (Spatial-Temporal Action Net)
Thay vì CNN 2D tĩnh dễ bị nhiễu màu da/ánh sáng, đề xuất 2 kiến trúc hiện đại:
- **Option A (Khuyên dùng - Skeleton-based ST-GCN):**
  - Trích xuất 21 keypoints bàn tay qua MediaPipe.
  - Sử dụng mạng tích chập đồ thị không gian-thời gian (**ST-GCN** hoặc **PoseC3D**).
  - Kích thước siêu nhẹ ($< 3\text{ MB}$), tốc độ cực nhanh ($> 60\text{ FPS}$), kháng 100% điều kiện bóng đổ và màu da găng tay.
- **Option B (Video-based TSM - Temporal Shift Module):**
  - Backbone `MobileNetV3` với module Temporal Shift trên chuỗi 16 khung hình bàn tay.
  - Độ chính xác phân loại các bước chà ngón, chà mu bàn tay $\ge 95\%$.

### 2.3. Tích lũy Thời lượng & Máy trạng thái Rửa tay
- Đặt thời gian tích lũy $T_{\text{wash}}$:
  $$T_{\text{wash}}(t) = T_{\text{wash}}(t-1) + \Delta t \quad \text{khi } \text{Action}(t) == \text{"WASHING"}$$
- Nếu gián đoạn dưới $0.5\text{s}$ (bù trừ nhiễu frame), bộ đếm không bị reset về 0.
- Khi $T_{\text{wash}} \ge T_{\text{threshold}}$ (mặc định $3.0\text{s}$ bản demo, $20.0\text{s}$ bản thực tế), kích hoạt chuyển trạng thái thành công.

---

## 3. CHUẨN HÓA GIAO TIẾP DỮ LIỆU (I/O DATA CONTRACT)

### Input yêu cầu:
- Khung hình video và tọa độ keypoints của y tá từ Module 1 của Bảo.
- (Tùy chọn) Vị trí bình cồn từ Module 2 của Thái để tăng trọng số ưu tiên.

### Output gửi cho hệ thống (`HandwashStateEvent`):
```json
{
  "frame_id": 1250,
  "timestamp": 41.667,
  "nurse_id": 1,
  "is_self_touching": true,
  "is_washing_action": true,
  "action_confidence": 0.94,
  "wash_duration_sec": 3.8,
  "is_wash_completed": true
}
```

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT (TASK BREAKDOWN FOR VINH)

- [ ] **Task 3.1: Hoàn thiện Thuật toán Scale-Aware Normalization**
  - Viết module `scale_normalizer.py`: Tính $L_{\text{norm}}$ linh hoạt theo vai/khuỷu tay/bbox.
- [ ] **Task 3.2: Xây dựng Module Tự Chạm Tay (Self-Touch Detector)**
  - Viết module `self_touch_detector.py`: Đánh giá $D_{\text{norm}}$ và IoU bàn tay, duy trì bộ đệm trạng thái mượt mà.
- [ ] **Task 3.3: Tích hợp Hand Cropper & MediaPipe / Keypoint Extractor**
  - Trích xuất tự động vùng bàn tay độ phân giải cao và tọa độ 21 điểm khớp bàn tay.
- [ ] **Task 3.4: Huấn luyện / Tích hợp Mô hình ST-GCN / TSM**
  - Viết module `handwash_action_classifier.py`: Phân biệt `WASHING` vs `IDLE_TOUCH` / `HOLDING_OBJECT`.
- [ ] **Task 3.5: Bộ tích lũy thời gian & Kiểm thử Benchmarking**
  - Đánh giá khả năng chống báo ảo khi y tá đan tay nói chuyện hoặc cầm điện thoại.

---

## 5. OUTPUT CẦN ĐẠT (DELIVERABLES & METRICS)

1. **Deliverables:**
   - Mã nguồn hoàn chỉnh: `scale_normalizer.py`, `self_touch_detector.py`, `handwash_action_classifier.py`.
   - File trọng số mô hình hành động: `handwash_action_model.pth` hoặc ONNX.
   - Video demo nhận diện rửa tay trực quan (Hiển thị thước đo $D_{\text{norm}}$, thanh tiến trình rửa tay Progress Bar và cảnh báo hoàn thành).
2. **Chỉ số kỹ thuật bắt buộc (KPIs):**
   - **Độ chính xác Self-touching (F1-Score):** $\ge 92\%$ ở mọi cự ly camera (gần $1\text{m}$ đến xa $5\text{m}$).
   - **Độ chính xác phân loại Rửa tay thật (Action Accuracy):** $\ge 93\%$.
   - **Tỷ lệ báo ảo khi đan tay / cầm vật:** $\le 5\%$.
   - **Tốc độ xử lý:** $\ge 35$ FPS trên GPU hoặc $\ge 25$ FPS trên CPU thông thường.

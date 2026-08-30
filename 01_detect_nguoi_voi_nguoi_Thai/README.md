# MODULE 01: PHÁT HIỆN TƯƠNG TÁC NGƯỜI VỚI NGƯỜI (HUMAN-TO-HUMAN INTERACTION)
> **Phụ trách:** **Bảo**  
> **Thư mục:** `01_detect_nguoi_voi_nguoi_Bao/`  
> **Phạm vi giám sát:** Thời điểm vàng WHO số **1** (*Trước khi chạm bệnh nhân*) & số **4** (*Sau khi chạm bệnh nhân*).

---

## 1. TỔNG QUAN NHIỆM VỤ CỦA BẢO

Module này chịu trách nhiệm làm nền móng thị giác không gian cho toàn hệ thống:
1. **Ước lượng tư thế đa người (Multi-Person 2D Pose Estimation):** Trích xuất tọa độ 17 điểm khớp xương (COCO keypoints) cho mọi cá thể trong khung hình ICU.
2. **Theo dõi và Tái định danh (Tracking & Re-ID):** Duy trì `Track_ID` cố định cho từng người ngay cả khi bị che khuất một phần (occlusion) bởi máy móc, rèm che hoặc nhân viên khác.
3. **Phân loại vai trò (Role Classification):** Tự động tách biệt **Bệnh nhân (Patient - nằm cố định tại giường)** và **Nhân viên y tế (Nurse/Doctor - di chuyển linh hoạt)**.
4. **Đồ thị tương tác không-thời gian (Spatio-Temporal Keypoint Interaction Graph):** Tính toán khoảng cách và xác suất tiếp xúc thực giữa bàn tay/cổ tay của y tá với các vùng cơ thể của bệnh nhân (ngực, bụng, tay, chân, đầu).

```
   [Camera Stream ICU]
           │
           ▼
   [1. YOLO11-Pose Multi-Person]
           │ (BBoxes + Keypoints)
           ▼
   [2. BoT-SORT Tracking + Re-ID]
           │ (Consistent Person IDs)
           ▼
   [3. Person Role Classifier] ──► {Patient (Static ROI), Nurse (Dynamic)}
           │
           ▼
   [4. One-Euro Anti-Jitter Filter]
           │ (Smoothed Keypoints)
           ▼
   [5. Spatio-Temporal Contact Graph]
           │
           ▼
   [OUTPUT: PersonContactEvent] ──► (Gửi về 00_core_system_fsm)
```

---

## 2. CƠ SỞ LÝ THUYẾT & THUẬT TOÁN ĐỀ XUẤT

### 2.1. Ước lượng tư thế & Bám vết (Pose Estimation & Tracking)
- **Mô hình đề xuất:** `YOLO11x-pose` hoặc `RTMPose-m` (Real-time Multi-Person Pose).
- **Bộ theo dõi:** `BoT-SORT` tích hợp trích xuất đặc trưng ngoại hình (Appearance Feature Re-ID via `FastReID` / `OSNet`).
- **Ưu điểm:** Khắc phục triệt để lỗi mất dấu ID hoặc hoán đổi ID (ID Switch) khi y tá cúi người hoặc bước qua sau lưng đồng nghiệp.

### 2.2. Thuật toán Phân loại Vai trò (Role Classification)
Trong phòng ICU, bệnh nhân nằm trên giường bệnh (vận tốc di chuyển tâm cơ thể $\approx 0$), còn y tá di chuyển liên tục xung quanh:
$$\text{Role}(i) = \begin{cases} \text{PATIENT} & \text{nếu } \text{IoU}(BBox_i, Bed\_ROI) > 0.6 \text{ và } \bar{v}_i < v_{thresh} \\ \text{NURSE} & \text{ngược lại} \end{cases}$$
Trong đó:
- $Bed\_ROI$: Vùng chữ nhật giường bệnh (nhận từ Module 2 của Thái hoặc cấu hình tĩnh ban đầu).
- $\bar{v}_i$: Vận tốc trung bình của tâm khung xương người $i$ trong cửa sổ trượt $W = 30$ frames:
$$\bar{v}_i = \frac{1}{W} \sum_{t=1}^{W} \|\mathbf{P}_{center, i}(t) - \mathbf{P}_{center, i}(t-1)\|_2$$

### 2.3. Bộ lọc chống rung giật Keypoint (One-Euro Filter / Kalman Filter)
Do hiện tượng rung giật (jitter) khi keypoint bị che khuất một phần, áp dụng bộ lọc **$1€$ Filter** (One-Euro Filter) trên từng tọa độ keypoint $(x, y)$:
$$\hat{x}_t = \alpha \cdot x_t + (1 - \alpha) \cdot \hat{x}_{t-1}, \quad \alpha = \frac{1}{1 + \frac{\tau}{T_e}}, \quad \tau = \frac{1}{2\pi (f_c + \beta |\dot{x}_t|)}$$
Bộ lọc tự động thích ứng: mượt mà khi đứng yên ($|\dot{x}_t| \to 0$), không trễ khi chuyển động nhanh.

### 2.4. Đồ thị Tương tác Tiếp xúc Người - Người (Contact Probability Graph)
Xác định tiếp xúc giữa Cổ tay Y tá ($\mathbf{W}_{\text{nurse}} \in \{W_{\text{left}}, W_{\text{right}}\}$) và Tập keypoints Bệnh nhân $\mathbf{K}_{\text{patient}} = \{K_1, K_2, \dots, K_{17}\}$:
1. **Khoảng cách tối thiểu:**
   $$d_{\min}(t) = \min_{j \in \mathbf{K}_{\text{patient}}} \|\mathbf{W}_{\text{nurse}}(t) - K_j(t)\|_2$$
2. **Chuẩn hóa khoảng cách theo kích thước thân bệnh nhân ($L_{\text{torso}}$):**
   $$D_{\text{contact}}(t) = \frac{d_{\min}(t)}{\|\mathbf{P}_{\text{Shoulder}} - \mathbf{P}_{\text{Hip}}\|_{\text{patient}}}$$
3. **Xác suất tiếp xúc (Contact Probability):**
   $$P_{\text{contact}}(t) = \sigma \left( \frac{\theta_{\text{contact}} - D_{\text{contact}}(t)}{\tau} \right)$$
   Nếu $P_{\text{contact}}(t) \ge 0.75$ liên tục trong $\ge 0.3$ giây (9 frames @ 30 FPS) $\rightarrow$ Kích hoạt sự kiện **`PersonContactEvent(is_touching=True)`**.

---

## 3. CHUẨN HÓA GIAO TIẾP DỮ LIỆU (I/O DATA CONTRACT)

### Input yêu cầu:
- Video Stream 1080p@30fps từ camera ICU.
- (Tùy chọn) `Bed_ROI` từ Module 2 của Thái để tăng độ chuẩn xác phân loại vai trò.

### Output gửi cho hệ thống (`PersonContactEvent`):
```json
{
  "frame_id": 1045,
  "timestamp": 34.833,
  "nurse_id": 1,
  "patient_id": 2,
  "is_touching": true,
  "contact_confidence": 0.92,
  "nurse_wrist_pos": [412.5, 680.2],
  "patient_body_part": "RIGHT_ARM",
  "touch_duration_sec": 1.2
}
```

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT (TASK BREAKDOWN FOR BẢO)

- [ ] **Task 1.1: Thiết lập Pose Estimator & BoT-SORT Pipeline**
  - Tích hợp `YOLO11x-pose` với `BoT-SORT`.
  - Viết module `pose_tracking.py` xử lý video và trả về danh sách đối tượng có `track_id` ổn định.
- [ ] **Task 1.2: Xây dựng Role Classifier**
  - Hoàn thiện `person_role_classifier.py`: Tính vận tốc dịch chuyển trọng tâm $\bar{v}_i$ và đối chiếu tọa độ với vùng giường bệnh.
- [ ] **Task 1.3: Cài đặt One-Euro Filter chống rung Keypoints**
  - Áp dụng bộ lọc One-Euro vào tọa độ cổ tay và các khớp quan trọng.
- [ ] **Task 1.4: Xây dựng Spatio-Temporal Interaction Graph**
  - Hoàn thiện `person_contact_graph.py`: Tính $D_{\text{contact}}$, chuẩn hóa khoảng cách theo thân người và phát hiện sự kiện chạm.
- [ ] **Task 1.5: Đóng gói và Kiểm thử Benchmark**
  - Chạy benchmark trên video ICU mẫu, đo FPS, độ trễ và độ chính xác phân loại tiếp xúc.

---

## 5. OUTPUT CẦN ĐẠT (DELIVERABLES & METRICS)

1. **Deliverables:**
   - Mã nguồn hoàn chỉnh: `pose_tracking.py`, `person_role_classifier.py`, `person_contact_graph.py`.
   - File cấu hình mô hình và bộ lọc: `config_pose.yaml`.
   - Video demo kết quả trực quan (Visual Overlay Bounding Box + Skeletons + Contact Alerts).
2. **Chỉ số kỹ thuật bắt buộc (KPIs):**
   - **Tốc độ xử lý:** $\ge 30$ FPS (trên GPU RTX 3060/4070 hoặc T4/Colab).
   - **Độ chính xác Role Classification:** $\ge 98\%$ (không nhầm y tá với bệnh nhân).
   - **Độ chính xác phát hiện tiếp xúc Người - Người (T1 & T4):**
     - **Precision:** $\ge 90\%$ (hạn chế tối đa cảnh báo ảo).
     - **Recall:** $\ge 88\%$ (không bỏ sót khi y tá chạm bệnh nhân).
   - **ID Switch Rate:** $< 2$ lần/phút khi có che khuất nhẹ.

# MODULE 00: CORE FSM & BỘ MÁY ĐỐI CHIẾU 5 THỜI ĐIỂM WHO
> **Phụ trách:** **Toàn đội (Tích hợp hệ thống chung)**  
> **Thư mục:** `00_core_system_fsm/`  
> **Chức năng:** Quản lý vòng đời trạng thái vô trùng của nhân viên y tế và bắt lỗi vi phạm theo tiêu chuẩn WHO.

---

## 1. TỔNG QUAN KIẾN TRÚC TÍCH HỢP

Module `00_core_system_fsm` là trung tâm điều phối và tổng hợp tín hiệu từ cả 3 module nhánh:
- **Module 1 (Bảo):** Cung cấp sự kiện tương tác Người - Người (`PersonContactEvent`).
- **Module 2 (Thái):** Cung cấp sự kiện tương tác Thiết bị & Vùng vô khuẩn/dịch tiết (`EquipmentContactEvent`).
- **Module 3 (Vinh):** Cung cấp sự kiện Tự chạm tay & Hoàn thành rửa tay (`HandwashStateEvent`).

```
   [Module 1 - Bảo]          [Module 2 - Thái]        [Module 3 - Vinh]
   (PersonContactEvent)   (EquipmentContactEvent)   (HandwashStateEvent)
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │      CENTRAL EVENT BUS SYNC      │
                    └────────────────┬─────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │    FINITE STATE MACHINE (FSM)    │
                    │    - UNSTERILE                   │
                    │    - STERILE                     │
                    │    - BIOHAZARD                   │
                    └────────────────┬─────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │    WHO 5-MOMENTS RULE ENGINE     │
                    │  Đối chiếu vi phạm Thời điểm 1-5  │
                    └────────────────┬─────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │  OUTPUT: Alerts & Log Dashboard  │
                    └──────────────────────────────────┘
```

---

## 2. MA TRẬN CHUYỂN TRẠNG THÁI FSM (STATE TRANSITION MATRIX)

| Trạng thái Hiện tại | Sự kiện kích hoạt (Event Trigger) | Trạng thái Mới | Đánh giá Tuân thủ WHO |
| :--- | :--- | :--- | :--- |
| **UNSTERILE** | Rửa tay đạt chuẩn (`is_wash_completed=True`) | **STERILE** | Hợp lệ $\rightarrow$ Nâng trạng thái sạch. |
| **UNSTERILE** | Chạm Bệnh nhân (`PersonContactEvent`) | **UNSTERILE** | 🚨 **VI PHẠM THỜI ĐIỂM 1** (*Trước khi chạm bệnh nhân*). |
| **UNSTERILE** | Chạm Vùng Vô khuẩn (`is_aseptic_zone=True`) | **UNSTERILE** | 🚨 **VI PHẠM THỜI ĐIỂM 2** (*Trước thủ thuật vô trùng*). |
| **STERILE** | Chạm Vùng Dịch tiết (`is_body_fluid_risk=True`) | **BIOHAZARD** | Hợp lệ khi thao tác, hạ trạng thái xuống nhiễm khuẩn nguy cơ. |
| **BIOHAZARD** | Chạm bất kỳ vật/người khác mà chưa rửa tay | **BIOHAZARD** | 🚨 **VI PHẠM THỜI ĐIỂM 3** (*Sau tiếp xúc dịch cơ thể*). |
| **STERILE** | Rời khỏi Bệnh nhân (`PersonContact` kết thúc) | **UNSTERILE** | ⚠️ Yêu cầu rửa tay tiếp theo (Thời điểm 4). |
| **STERILE** | Chạm Thiết bị giường bệnh (`is_surrounding=True`) | **UNSTERILE** | ⚠️ Yêu cầu rửa tay tiếp theo (Thời điểm 5). |

---

## 3. CÁC TỆP MÃ NGUỒN CỐT LÕI

1. `event_contracts.py`: Định nghĩa các cấu trúc dữ liệu `dataclass` và `Enum` dùng chung giữa các thành viên.
2. `who_fsm_engine.py`: Bộ máy Finite State Machine xử lý chuỗi sự kiện và xuất cảnh báo theo thời gian thực.

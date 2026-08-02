# Báo cáo nhanh: Cấu trúc dữ liệu 12 bước & Kiến trúc train

*Cập nhật: 02/08/2026 — chụp lại đúng tình trạng đang có trên đĩa.*

---

## 1. Bộ nhãn: 13 lớp

Định nghĩa duy nhất ở [`src/steps_config.py`](../src/steps_config.py).

| idx | code | kind | needs_scene | 6 bước cũ |
|---:|---|---|---|---|
| 0 | S00_OTHER | – | – | – |
| 1 | S01_WET | non_rub | ✔ | – |
| 2 | S02_SOAP | non_rub | ✔ | – |
| 3 | S03_PALM | rub | – | B1 |
| 4 | S04_DORSUM | rub | – | B2 |
| 5 | S05_INTERLACE | rub | – | B3 |
| 6 | S06_BACKFINGER | rub | – | B4 |
| 7 | S07_THUMB | rub | – | B5 |
| 8 | S08_FINGERTIP | rub | – | B6 |
| 9 | S09_RINSE | non_rub | ✔ | – |
| 10 | S10_DRY | non_rub | ✔ | – |
| 11 | S11_FAUCET | non_rub | ✔ | – |
| 12 | S12_SAFE | terminal | ✔ | – |

`NUM_CLASSES = 13`. Bước 12 do state machine suy ra, không train.

---

## 2. Cấu trúc dữ liệu trên đĩa

```
handwash/
├── data_public_raw/              # dataset gốc, chưa xử lý (1.3 GB)
│   ├── kaggle-dataset-6classes.tar
│   └── kaggle_sample/            # bản giải nén: 7 thư mục lớp 0..6
├── data_public/                  # video đã đổi tên theo index dự án (1.3 GB)
│   └── {0,3,4,5,6,7,8}/*.mp4     # 300 video
└── processed_data/               # frame đã tiền xử lý (56 MB)
    ├── sources.json              # {video: {fps: 15.0}} — dataset.py đọc để tính stride
    ├── split_report.json
    ├── train/{0,3,4,5,6,7,8}/{hand,scene}/<vid>_f<idx>.jpg
    └── val/  {0,3,4,5,6,7,8}/{hand,scene}/<vid>_f<idx>.jpg
```

Mỗi lớp có **2 luồng song song, cùng tên file** để đồng bộ theo thời gian:
- `hand/` — crop sát union-box 2 bàn tay (MediaPipe HandLandmarker, pad 30px, nhớ box 15 frame)
- `scene/` — toàn vùng ROI bồn rửa (`roi.json`)

Ảnh **112×112 RGB**, lấy mẫu về **15 fps** ngay từ khâu tiền xử lý (nên `dataset.py` chạy stride = 1).

### Số liệu hiện có

| Lớp | train video | val video | train frame | val frame |
|---:|---:|---:|---:|---:|
| 0 (Other) | 2 | 1 | 187 | 93 |
| 3 | 2 | 1 | 338 | 271 |
| 4 | 2 | 1 | 331 | 134 |
| 5 | 2 | 1 | 370 | 203 |
| 6 | 2 | 1 | 375 | 204 |
| 7 | 2 | 1 | 303 | 170 |
| 8 | 2 | 1 | 271 | 162 |
| **Tổng** | **14** | **7** | **2.175** | **1.237** |

*(frame = mỗi luồng; trên đĩa gấp đôi vì có cả hand + scene)*

### Độ phủ 12 bước

| Trạng thái | Bước | Ghi chú |
|---|---|---|
| ✅ Có data | 0, 3, 4, 5, 6, 7, 8 | từ `kaggle_sample`, mới ở mức **sample** (3 video/lớp) |
| ⚠️ Có nguồn, chưa tải | 11 | tar hiện tại chỉ có thư mục `0..6`, thiếu `7` → cần PSKUS (Zenodo 4537209, code 7) hoặc `kaggle_full` |
| ❌ Không có nguồn công khai | 1, 2, 9, 10 | **bắt buộc tự quay** |
| — | 12 | state machine suy ra, không cần data |

→ **7/13 lớp có dữ liệu.** Với data hiện tại, model chỉ học được 6 động tác chà xát + Other.

---

## 3. Pipeline tiền xử lý — [`src/prepare_data.py`](../src/prepare_data.py)

3 nguồn job đầu vào, gộp chung:
1. `label.xlsx` (nguồn BAO, 15.15 fps) — nhãn theo khoảng thời gian
2. `Handwashing_Dataset_Labels.xlsx` (video_0X, nhãn ghi ở 24fps → nhân 2.5 ra frame 60fps, **đọc cả 2 sheet**)
3. thư mục lớp của dataset công khai (`data_public/<idx>/*.mp4`)

Các điểm quan trọng:
- **Tự sinh lớp Other** từ khoảng trống giữa các đoạn đã gán nhãn (chỉ lấy đoạn > 1.5s, tối đa 200 frame/video).
- **Chia train/val theo VIDEO**, không theo frame (`split_by_video`, val_ratio 0.2, seed 42) → chống rò rỉ.
- MediaPipe chỉ chạy trên frame đã lấy mẫu 15fps → nhanh gấp 2–4 lần trên video 30/60fps.
- Ghi `sources.json` với **fps sau lấy mẫu**, tránh dataset lấy mẫu chồng lần hai.

---

## 4. Dataset loader — [`src/dataset.py`](../src/dataset.py)

`HandwashClipDataset` trả về `(hand, scene, label)`, clip shape `(3, 16, 112, 112)` — 16 frame @ 15fps ≈ 1.07s.

- **Cửa sổ trượt có chồng lấn**: overlap 0.5 khi train, 0.0 khi val (bản cũ cắt khối rời rạc + drop-last, mất data).
- Đoạn ngắn hơn 1 clip vẫn dùng được bằng `linspace` lấy đủ 16 frame.
- Chuẩn hóa theo **mean/std Kinetics-400** (khớp pretrain của r3d_18), không phải chia 255.
- Tự phát hiện layout `nested` (có `hand/`) hay `flat` (cũ); thiếu `scene/` → tự chuyển single-stream; thiếu ảnh scene lẻ → thay tensor 0.
- `class_weights()` = nghịch đảo tần suất, chỉ tính trên lớp có mặt.

---

## 5. Kiến trúc model — [`src/model.py`](../src/model.py)

```
hand  (B,3,16,112,112) ─► r3d_18 backbone (fc=Identity) ─► 512 ┐
                                                                ├─ concat 1024
scene (B,3,16,112,112) ─► r3d_18 backbone (fc=Identity) ─► 512 ┘
                                    │
                    Dropout(0.5) → Linear(1024→512) → ReLU → Dropout(0.25) → Linear(512→13)
```

- Backbone chọn được: `r3d_18` (mặc định), `mc3_18`, `r2plus1d_18`. Pretrained Kinetics-400.
- **Vì sao phải dual-stream:** ở mức crop bàn tay, "làm ướt tay" (1) và "tráng tay" (9) giống hệt nhau; thông tin phân biệt nằm ở bối cảnh — vòi nước, bình xà phòng, cái khăn.
- `scene=None` → thay bằng vector 0, chạy được ở chế độ 1 nhánh.
- `load_legacy_6class_checkpoint()` cấy backbone model 6 lớp cũ vào **cả 2 nhánh**, và cấy 6 hàng `fc` cũ theo B1..B6 → WHO 3..8 (chỉ khi shape khớp; classifier nhiều lớp thì bỏ qua, học lại).
- Tham số: **66.86M** (dual-stream) / **33.44M** (single-stream) — backbone r3d_18 chiếm 33.17M mỗi nhánh.

---

## 6. Quy trình train — [`src/train.py`](../src/train.py)

### Fine-tune 2 pha
| Pha | Epoch | Trạng thái backbone | LR | Scheduler |
|---|---|---|---|---|
| 1 – warm-up | 0 → 3 | **đóng băng** cả hand + scene | 1e-3 | – |
| 2 – fine-tune | 3 → hết | mở băng toàn mạng | 1e-4 | CosineAnnealingLR |

Lý do pha 1: classifier khởi tạo ngẫu nhiên sẽ đẩy gradient lớn phá backbone đã học tốt.

### Chống mất cân bằng lớp (3 lớp bảo vệ)
1. `class_weights` trong `CrossEntropyLoss` (nghịch đảo tần suất)
2. `WeightedRandomSampler` — mỗi batch phân bố lớp gần đều
3. Chọn best model theo **macro-F1**, không phải accuracy

### Cấu hình mặc định
`AdamW`, weight_decay 1e-4, dropout 0.5, label_smoothing 0.05, batch 8, clip 16 frame, overlap 0.5, grad clip norm 5.0, 30 epoch.
Augment: `TemporalJitter` (brightness/contrast ±0.2, p=0.5). **Không lật ngang** — bước 4/6/7/8 có tính trái/phải, lật sẽ đảo nghĩa động tác.

Device tự chọn: MPS → CUDA → CPU.

### Đầu ra
`checkpoints/handwash12_best.pth` (theo macro-F1), `handwash12_last.pth`, `history_12steps.json`.
Mỗi 5 epoch in báo cáo per-class + confusion matrix, kèm cảnh báo lớp không có mẫu val.

### Lệnh chạy
```bash
python src/prepare_data.py                                   # tiền xử lý
python src/train.py --legacy-checkpoint checkpoints/model_best.pth --epochs 30
python src/train.py --no-scene --epochs 20                   # chỉ nhánh hand
python src/train.py --resume checkpoints/handwash12_best.pth
```

---

## 7. Nhận định

**Chạy được ngay:** pipeline hoàn chỉnh và nhất quán đầu-cuối, taxonomy 13 lớp thông suốt mọi module, các lỗi cũ (rò rỉ train/val, đếm thời gian sai theo fps, bỏ sót sheet Excel) đã sửa.

**Chặn lại:**
1. Chỉ **3 video/lớp** — quá ít để có con số baseline có ý nghĩa; val chỉ 1 video/lớp nên phương sai rất lớn.
2. **6/12 bước không có 1 frame nào** (1, 2, 9, 10, 11). Nhánh `scene` hiện gần như vô dụng vì các lớp cần bối cảnh đều rỗng — train dual-stream lúc này chỉ tốn gấp đôi tính toán.

**Thứ tự nên làm:**
1. Tải thêm dataset công khai để lớp 3–8 đủ dày (`pskus` / `metc` / `kaggle_full`), đồng thời lấp được lớp 11.
2. Trong lúc chờ data mới → train `--no-scene` để có baseline 7 lớp.
3. Tự quay bước 1, 2, 9, 10 theo protocol ở [Mục 7 báo cáo chính](BAOCAO_12_BUOC_RUA_TAY.md) → mới bật dual-stream đầy đủ.

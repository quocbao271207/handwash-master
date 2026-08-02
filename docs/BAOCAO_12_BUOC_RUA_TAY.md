# BÁO CÁO: NÂNG CẤP HỆ THỐNG NHẬN DIỆN RỬA TAY TỪ 6 BƯỚC LÊN 12 BƯỚC

**Dự án:** Handwashing Recognition (Kịch bản 4 — camera cố định, góc trực diện từ trên xuống)
**Ngày:** 02/08/2026
**Phạm vi:** Định nghĩa bộ 12 bước, thiết kế quy trình nhận diện, khảo sát nguồn dữ liệu,
xây dựng mô hình huấn luyện kế thừa từ mô hình 6 bước hiện có.

---

## 1. TÓM TẮT ĐIỀU HÀNH

| Hạng mục | Kết luận |
|---|---|
| Bộ nhãn | 12 bước WHO "How to Handwash" + 1 lớp nền → **13 lớp** |
| Tái sử dụng dữ liệu cũ | **100%** — 6 bước B1–B6 hiện có ánh xạ 1-1 sang bước WHO 3–8 |
| Tái sử dụng mô hình cũ | **Có** — cấy trọng số backbone + fine-tune 2 pha |
| Dữ liệu công khai | Phủ **7/12 bước** (3–8 và 11). **5 bước phải tự quay** |
| Thay đổi kiến trúc | Bắt buộc chuyển sang **dual-stream** (hand crop + scene ROI) |
| Lỗi phát hiện trong code cũ | **3 lỗi**, trong đó 1 lỗi làm sai lệch toàn bộ chỉ số đánh giá |

**Rủi ro lớn nhất:** 5 bước mới (làm ướt tay, lấy xà phòng, tráng nước, lau khô, khóa vòi)
**không có nguồn dữ liệu công khai nào dùng được**. Nếu không quay bổ sung, hệ thống 12 bước
sẽ chỉ hoạt động đúng trên 7/12 bước. Chi tiết ở Mục 4 và Mục 7.

---

## 2. QUY TRÌNH 12 BƯỚC RỬA TAY (WHO — "How to Handwash")

WHO quy định hai quy trình vệ sinh tay riêng biệt:

- **Handrub** (chà tay bằng cồn) — 8 bước, 20–30 giây.
- **Handwash** (rửa tay bằng xà phòng và nước) — **12 bước, 40–60 giây**. ← dự án dùng bộ này.

Điểm khác biệt then chốt so với bộ 6 bước cũ: bộ 6 bước của Bộ Y tế chỉ mô tả **phần chà xát**.
Bộ 12 bước WHO bao trọn **cả phiên rửa tay**, gồm cả các thao tác có nước, xà phòng và khăn.

### 2.1. Bảng 12 bước

| # | Mã | Tên bước (tiếng Việt) | Tên WHO | Loại | Thời gian tối thiểu |
|---|---|---|---|---|---|
| 1 | `S01_WET` | Làm ướt hai bàn tay bằng nước | Wet hands with water | non-rub | 1.0 s |
| 2 | `S02_SOAP` | Lấy đủ lượng xà phòng phủ kín hai bàn tay | Apply enough soap | non-rub | 1.0 s |
| 3 | `S03_PALM` | Chà hai lòng bàn tay vào nhau | Rub hands palm to palm | rub | 2.0 s |
| 4 | `S04_DORSUM` | Lòng bàn tay này chà lên mu bàn tay kia, các ngón đan vào nhau và đổi bên | Palm over dorsum, fingers interlaced | rub | 2.0 s |
| 5 | `S05_INTERLACE` | Hai lòng bàn tay áp vào nhau, các ngón đan vào nhau, miết kẽ ngón | Palm to palm, fingers interlaced | rub | 2.0 s |
| 6 | `S06_BACKFINGER` | Mặt ngoài các ngón tay áp vào lòng bàn tay đối diện, các ngón móc vào nhau | Backs of fingers to opposing palms | rub | 2.0 s |
| 7 | `S07_THUMB` | Xoay ngón cái của bàn tay này trong lòng bàn tay kia và đổi bên | Rotational rubbing of thumb | rub | 2.0 s |
| 8 | `S08_FINGERTIP` | Chụm đầu ngón tay xoay trong lòng bàn tay kia và đổi bên | Rotational rubbing, clasped fingers in palm | rub | 2.0 s |
| 9 | `S09_RINSE` | Tráng sạch hai bàn tay bằng nước | Rinse hands with water | non-rub | 2.0 s |
| 10 | `S10_DRY` | Lau khô tay bằng khăn dùng một lần | Dry with single use towel | non-rub | 2.0 s |
| 11 | `S11_FAUCET` | Dùng khăn để khóa vòi nước | Use towel to turn off faucet | non-rub | 1.0 s |
| 12 | `S12_SAFE` | Tay của bạn đã an toàn | And your hands are safe | terminal | — |

> Định nghĩa gốc nằm trong [src/steps_config.py](src/steps_config.py) — đây là **nguồn chân lý duy nhất**,
> mọi module khác đều import từ đó. Muốn sửa taxonomy chỉ cần sửa một file.

### 2.2. Lớp nền `S00_OTHER` (index 0)

Ngoài 12 bước, mô hình có thêm **lớp 0 = Khác/Nghỉ**. Đây không phải chi tiết kỹ thuật vụn vặt
mà là yêu cầu bắt buộc:

Trong một video giám sát thực tế, **phần lớn thời gian không thuộc bước nào** — người mới bước
tới bồn, khoảng chuyển giao giữa hai bước, tay ra khỏi khung hình. Mô hình 12 lớp thuần buộc
phải gán một nhãn sai cho những đoạn này, khiến state machine liên tục "công nhận" các bước
chưa hề xảy ra. Dataset PSKUS cũng dùng đúng cách này (movement code 0 = *other*).

→ **Tổng số lớp đầu ra của mô hình = 13.**

### 2.3. Xử lý bước 12

Bước 12 ("Tay của bạn đã an toàn") **không phải một động tác** mà là trạng thái kết thúc.
Hệ thống không đánh giá nó bằng thị giác mà **suy ra từ state machine**: khi cả 11 bước bắt buộc
đã hoàn thành. Vì vậy `REQUIRED_STEP_IDS = [1..11]`.

### 2.4. Ánh xạ từ bộ 6 bước cũ — dữ liệu cũ tái sử dụng được 100%

Điểm thuận lợi lớn nhất của dự án: 6 động tác của Bộ Y tế **trùng khớp 1-1** với 6 động tác
chà xát của WHO. Không cần gán nhãn lại bất kỳ video nào.

| Nhãn cũ | Mô tả cũ | → Bước WHO mới |
|---|---|---|
| B1 | Chà 2 lòng bàn tay | **3** |
| B2 | Chà mu bàn tay và kẽ ngoài | **4** |
| B3 | Chà 2 lòng bàn tay, miết kẽ ngón | **5** |
| B4 | Chà mặt ngoài các ngón tay | **6** |
| B5 | Xoay ngón tay cái | **7** |
| B6 | Xoay các đầu ngón tay | **8** |

Toàn bộ nhãn trong `label.xlsx` (14 video BAO) và `Handwashing_Dataset_Labels.xlsx`
(6 video video_0X) được `prepare_data.py` tự động chuyển đổi.

---

## 3. QUY TRÌNH NHẬN DIỆN

### 3.1. Sơ đồ tổng thể

```
                    ┌─────────────────────────────────────────┐
   Video / Camera ──▶│  1. ROI tĩnh (roi.json)                │
                    │     cắt cứng vùng bồn rửa               │
                    └──────────────┬──────────────────────────┘
                                   │ frame_roi
                    ┌──────────────▼──────────────────────────┐
                    │  2. MediaPipe HandLandmarker            │
                    │     union bbox 2 bàn tay + padding 30px │
                    │     ★ nhớ bbox 15 frame khi mất dấu     │
                    └──────┬───────────────────┬──────────────┘
                           │ hand crop         │ scene ROI
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │ resize      │     │ resize      │
                    │ 112×112     │     │ 112×112     │
                    └──────┬──────┘     └──────┬──────┘
                           │                   │
                    ┌──────▼───────────────────▼──────────────┐
                    │  3. Buffer 16 frame, stride = fps/15    │
                    │     → clip ~1.07 giây                    │
                    └──────┬───────────────────┬──────────────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │ 3D ResNet-18│     │ 3D ResNet-18│   ★ nhánh mới
                    │  (hand)     │     │  (scene)    │
                    └──────┬──────┘     └──────┬──────┘
                        512│                   │512
                           └────────┬──────────┘
                            concat 1024
                    ┌───────────────▼─────────────────────────┐
                    │  4. Classifier → 13 logits              │
                    └───────────────┬─────────────────────────┘
                    ┌───────────────▼─────────────────────────┐
                    │  5. Làm mượt: trung bình softmax 5 lần  │
                    │     + ngưỡng tin cậy 0.35 → OTHER       │
                    └───────────────┬─────────────────────────┘
                    ┌───────────────▼─────────────────────────┐
                    │  6. State machine 12 bước               │
                    │     IDLE → IN_PROGRESS → DONE           │
                    │     ★ đo thời gian THẬT, không đếm frame│
                    └───────────────┬─────────────────────────┘
                    ┌───────────────▼─────────────────────────┐
                    │  7. Chấm điểm tuân thủ + video overlay  │
                    │     compliance_report.json              │
                    └─────────────────────────────────────────┘
```

`★` = thành phần mới hoặc đã sửa lỗi so với bản 6 bước.

### 3.2. Vì sao PHẢI đổi sang kiến trúc dual-stream

Đây là quyết định kỹ thuật quan trọng nhất của bản nâng cấp.

Mô hình 6 bước cũ chỉ nhận **ảnh đã crop sát hai bàn tay**. Cách này hoàn toàn hợp lý cho 6 động
tác chà xát — thông tin phân biệt nằm ở tư thế và chuyển động ngón tay, cắt sát giúp loại bỏ nhiễu
nền.

Nhưng với 5 bước mới thì cách này **không thể hoạt động**. Ở mức crop bàn tay:

- "Làm ướt tay" (bước 1) và "Tráng tay" (bước 9) — **giống hệt nhau**, cùng là hai bàn tay hứng nước.
- "Lấy xà phòng" (bước 2) — chỉ là một bàn tay đưa ra, khác biệt nằm ở **bình xà phòng** phía trên.
- "Lau khô" (bước 10) và "Khóa vòi" (bước 11) — khác biệt nằm ở **cái khăn đang chạm vào đâu**.

Thông tin phân biệt nằm ở **bối cảnh** (vòi nước có đang chảy không, bình xà phòng ở đâu, khăn
đang ở vị trí nào) — mà crop bàn tay đã cắt bỏ hoàn toàn. Không có lượng dữ liệu nào cứu được
kiến trúc single-stream ở đây, vì đầu vào **về mặt vật lý không chứa** thông tin cần thiết.

**Giải pháp:** hai nhánh 3D ResNet-18 song song, chia sẻ cùng trục thời gian:

| Nhánh | Đầu vào | Vai trò |
|---|---|---|
| `hand_backbone` | crop sát 2 bàn tay, 112×112 | chuyển động ngón tay tinh vi → phân biệt bước 3–8 |
| `scene_backbone` | toàn vùng ROI bồn rửa, 112×112 | vòi/xà phòng/khăn → phân biệt bước 1, 2, 9, 10, 11 |

Đặc trưng hai nhánh (512 + 512) được nối lại → classifier → 13 lớp.

Mô hình vẫn chạy được khi **thiếu luồng scene** (thay bằng tensor 0), nên có thể huấn luyện giai
đoạn đầu chỉ với dữ liệu hand crop rồi bổ sung nhánh scene sau — xem `HandwashDualStream.forward`
trong [src/model.py](src/model.py).

**Chi phí:** số tham số tăng từ ~33M lên ~66M. Trên máy Mac (MPS) thời gian suy luận mỗi clip
tăng khoảng gấp đôi; bù lại `--infer-every 4` giảm số lần chạy model xuống 4 lần so với bản cũ,
nên tốc độ thực tế **nhanh hơn** bản 6 bước (xem Mục 6.3).

### 3.3. Chuẩn hóa tốc độ khung hình

Dữ liệu đến từ nhiều nguồn với fps khác nhau (15.15 / 30 / 60). Nếu không chuẩn hóa, cùng một
động tác sẽ có "tốc độ" khác nhau trong mắt mô hình.

Hệ thống chuẩn hóa mọi nguồn về **15 fps hiệu dụng**: `stride = round(fps_nguồn / 15)`.
Một clip 16 frame luôn tương ứng **~1.07 giây thực tế**, bất kể nguồn.

| Nguồn | fps | stride | 16 frame ≈ |
|---|---|---|---|
| BAO* | 15.15 | 1 | 1.06 s |
| HandWash_* / PSKUS | 30 | 2 | 1.07 s |
| video_0X | 60 | 4 | 1.07 s |

fps thật được ghi vào `processed_data/sources.json` lúc tiền xử lý, thay vì đoán theo tiền tố
tên file như bản cũ.

### 3.4. State machine và chấm điểm tuân thủ

```
   IDLE ──(giữ 1 bước đủ min_sec)──▶ IN_PROGRESS ──(đủ 11 bước)──▶ DONE
     ▲                                                              │
     └──────────────(sau 5 giây)────────────────────────────────────┘
```

Một bước chỉ được công nhận khi mô hình **giữ nhãn đó liên tục đủ `min_sec` giây** — ngưỡng
riêng cho từng bước (bảng Mục 2.1). Điều này lọc bỏ các nhãn nhiễu thoáng qua ở biên giữa hai bước.

Đầu ra là `output/compliance_report.json`:

```json
{
  "state": "DONE",
  "compliant": true,
  "total_duration_sec": 47.3,
  "steps_completed": 11,
  "steps_required": 11,
  "order_performed": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
  "in_who_order": true,
  "durations_sec": { "3_S03_PALM": 5.2, "7_S07_THUMB": 4.1, "...": 0 },
  "missing_steps": []
}
```

Hệ thống đánh giá được cả ba khía cạnh mà bản 6 bước không làm được:

1. **Đủ bước không** — `missing_steps` liệt kê chính xác bước bị bỏ qua.
2. **Đúng thứ tự không** — `in_who_order`.
3. **Đủ thời gian không** — `total_duration_sec` so với khuyến nghị 40–60 giây của WHO.

---

## 4. KHẢO SÁT NGUỒN DỮ LIỆU

### 4.1. Kết luận

> **Không tồn tại dataset công khai nào phủ đủ 12 bước WHO.**

Toàn bộ các dataset rửa tay công khai đều được xây dựng cho bài toán **phân loại động tác chà
xát** (6 hoặc 7 lớp WHO), không phải cho bài toán giám sát trọn phiên rửa tay. Kết quả khảo sát:

| Nhóm bước | Bước | Nguồn công khai | Đánh giá |
|---|---|---|---|
| Chà xát | 3, 4, 5, 6, 7, 8 | PSKUS, METC, Kaggle, MFH | ✅ **Rất dồi dào** (hàng chục nghìn clip) |
| Khóa vòi | 11 | PSKUS (movement code 7) | ✅ **Có** |
| Nền | 0 (Other) | PSKUS (code 0) + tự sinh | ✅ **Có** |
| Ướt / Xà phòng / Tráng / Lau khô | 1, 2, 9, 10 | — | ❌ **Không có** |
| Kết thúc | 12 | — | (suy ra từ state machine) |

### 4.2. Chi tiết các dataset đã khảo sát

#### PSKUS — giá trị nhất
- **Nguồn:** [zenodo.org/record/4537209](https://zenodo.org/record/4537209)
- **Quy mô:** 3.185 phiên rửa tay, 18.4 GB, 30 FPS, 320×240 và 640×480
- **License:** CC BY-SA 4.0 (dùng được, phải ghi nguồn và chia sẻ tương tự)
- **Nhãn:** movement code 0–7 — 6 động tác WHO + code 7 = *turning off the faucet with a paper
  towel* + code 0 = *other*
- **Vì sao quan trọng:** quay trong **bệnh viện thật** (Pauls Stradiņš Clinical University
  Hospital), điều kiện nhiễu tự nhiên. Đây là dataset duy nhất phủ được **bước 11**.
- Ánh xạ nhãn đã cài sẵn: `PSKUS_TO_12` trong `steps_config.py`.

#### METC
- **Nguồn:** [zenodo.org/record/5808789](https://zenodo.org/record/5808789), CC BY-SA 4.0
- Quay trong phòng lab của Riga Stradiņš University, ánh sáng chuẩn. Cùng bộ nhãn PSKUS.
- Vai trò: tăng đa dạng điều kiện chụp.

#### Kaggle Hand Wash Dataset
- **Nguồn:** [kaggle.com/datasets/realtimear/hand-wash-dataset](https://www.kaggle.com/datasets/realtimear/hand-wash-dataset)
- 292 video, 3.504 clip.
- ⚠️ **Lưu ý quan trọng:** dataset này cũng được mô tả là "12 bước", nhưng **12 lớp ở đây là
  7 động tác WHO tách trái/phải** (`Step_2_Left`, `Step_2_Right`, …), **không phải** 12 bước
  đầy đủ của quy trình handwash. Đây là điểm rất dễ nhầm khi tìm dữ liệu. Ánh xạ gộp về bộ nhãn
  dự án đã cài sẵn: `KAGGLE_TO_12`.
- **Bản tải tự động:** nhóm EDI Riga đã resort lại thành 7 lớp và host tại
  [github.com/atiselsts/data](https://github.com/atiselsts/data) — **tải trực tiếp không cần
  tài khoản Kaggle**. Đây là nguồn nhanh nhất để có dữ liệu ngay.

#### MFH (Multi-viewpoint Fine-grained Hand hygiene)
- **Nguồn:** [github.com/willogy-team/hand-gesture-recognition-smc2021](https://github.com/willogy-team/hand-gesture-recognition-smc2021)
- 731.147 mẫu, 7 lớp WHO, thu ở **6 vị trí camera khác nhau**.
- Vai trò: giảm phụ thuộc góc quay — hữu ích vì dự án cố định một góc top-down.

#### Class-23 (Purdue, food safety) — có nhãn non-rub nhưng không công khai
- **Nguồn:** [PMC8472252](https://pmc.ncbi.nlm.nih.gov/articles/PMC8472252/)
- Là dataset **duy nhất** tìm được có nhãn cho thao tác non-rub: *touch faucet with hand*,
  *rub hands with water*, *rub hands without water*, *apply soap*, *drying hands with paper towel*.
- **Nhưng:** chỉ 23 người, 105 video, và **bài báo không công bố đường dẫn tải**. Không dùng được
  trực tiếp; có thể liên hệ nhóm tác giả nếu muốn theo đuổi.

#### Dataset tổng hợp (synthetic)
- Có một bộ dữ liệu rửa tay sinh bằng đồ họa (96.000 frame, 8 động tác, 4 nhân vật, 4 môi trường),
  công bố kèm bài [MDPI J. Imaging 11(7):208](https://www.mdpi.com/2313-433X/11/7/208).
- Vai trò khả dĩ: bù dữ liệu cho các bước hiếm. Rủi ro: khoảng cách miền (domain gap) giữa ảnh
  tổng hợp và ảnh thật thường lớn ở bài toán có nước và bọt xà phòng.

### 4.3. Công cụ đã xây dựng

[src/download_public_data.py](src/download_public_data.py) đóng gói toàn bộ kết quả khảo sát
thành công cụ chạy được:

```bash
python src/download_public_data.py --list            # xem toàn bộ khảo sát
python src/download_public_data.py --dataset kaggle_sample   # tải + convert tự động
python src/download_public_data.py --coverage        # kiểm tra bước nào còn thiếu
```

Script tự tải, giải nén (có chặn path traversal), ánh xạ nhãn về bộ 13 lớp của dự án, rồi in
**báo cáo độ phủ** chỉ rõ bước nào chưa có dữ liệu và phải xử lý thế nào.

---

## 5. BA LỖI PHÁT HIỆN TRONG CODE HIỆN CÓ

Trong quá trình nâng cấp, ba lỗi sau đã được phát hiện và sửa. Lỗi số 1 nghiêm trọng vì nó làm
**mọi chỉ số đánh giá của mô hình 6 bước hiện tại đều không đáng tin**.

### Lỗi 1 — Rò rỉ dữ liệu giữa train và val (nghiêm trọng)

`prepare_data.py` cũ gom toàn bộ ảnh của một lớp, `random.shuffle` ở **mức từng frame**, rồi cắt
80/20:

```python
imgs = glob.glob(os.path.join(label_dir, '*.*'))
random.shuffle(imgs)              # ← trộn ở mức FRAME
val_imgs   = imgs[:val_size]
train_imgs = imgs[val_size:]
```

Hệ quả: frame thứ 100 và frame thứ 101 của cùng một video — gần như **giống hệt nhau** — bị chia
về hai tập khác nhau. Tập val do đó chứa gần đúng nội dung tập train. **Val accuracy đo được là
ảo và cao hơn thực tế rất nhiều.**

Ảnh hưởng lan sang cả `dataset.py` cũ: nó gom frame theo tên video để tạo clip, nên các clip
trong tập val được ghép từ những frame nằm rải rác giữa các frame đã có trong tập train.

**Đã sửa:** `split_by_video()` chia theo **video** (group split) — mọi frame của một video chỉ
nằm ở đúng một tập.

> **Khuyến nghị:** sau khi chạy lại pipeline mới, con số val accuracy sẽ **thấp hơn đáng kể** so
> với báo cáo trước đây. Đó không phải mô hình kém đi — đó là lần đầu tiên chỉ số được đo đúng.

### Lỗi 2 — Bộ đếm thời gian sai theo fps

`predict.py` cũ tăng `current_step_counter` theo **mỗi frame đọc vào**, nhưng so sánh với
`frames_for_hold = int(2 * fps)`. Trong khi đó model chỉ chạy trên các frame **đã lấy mẫu theo
stride**. Với video 60 fps (`stride=4`), bộ đếm chạy nhanh gấp 4 lần ý định — điều kiện "giữ 2
giây" thực chất chỉ còn **0.5 giây**.

**Đã sửa:** state machine mới đo bằng **timestamp thật** (`frame_idx / fps`), đúng ở mọi fps.
Test `step 3 completes identically @ 15/30/60fps` xác nhận điều này.

### Lỗi 3 — Chỉ đọc sheet đầu tiên của file Excel

`Handwashing_Dataset_Labels.xlsx` có **2 sheet**. `pd.read_excel(path)` mặc định chỉ đọc sheet
đầu → toàn bộ nhãn của `video_01` và `video_05` (13 đoạn) bị bỏ sót.

**Đã sửa:** `pd.read_excel(path, sheet_name=None)` đọc tất cả sheet.

### Ngoài ra: 1 lỗi mới do test phát hiện

Trong lúc viết state machine mới, `tests/test_logic.py` phát hiện một lỗi tôi vừa tạo ra:

```python
held = ts - (self.current_start_ts or ts)   # SAI
```

Timestamp `0.0` là giá trị hợp lệ nhưng **falsy** trong Python, nên `0.0 or ts` trả về `ts` →
`held` luôn bằng 0. Bước bắt đầu tại giây 0 — tức **bước đầu tiên của mọi video** — sẽ không bao
giờ được công nhận. Đã sửa thành so sánh `is None`.

---

## 6. MÔ HÌNH VÀ CHIẾN LƯỢC HUẤN LUYỆN

### 6.1. Kế thừa từ mô hình 6 bước

Yêu cầu "train dựa trên mô hình sẵn có" được thực hiện qua `load_legacy_6class_checkpoint()`:

1. **Backbone:** toàn bộ trọng số conv/bn của `r3d_18` đã train 6 bước được nạp vào nhánh `hand`
   — và cả nhánh `scene`, vì với miền ảnh bồn rửa tay đây vẫn là khởi tạo tốt hơn Kinetics-400 thuần.
2. **Lớp phân loại:** 6 hàng trọng số `fc` cũ được cấy vào đúng các hàng tương ứng của lớp mới
   theo ánh xạ B1–B6 → WHO 3–8.

Nhờ đó 6 bước chà xát khởi động ở mức chính xác gần như ngay lập tức; mạng chỉ còn phải học
5 bước mới.

### 6.2. Fine-tune hai pha

| Pha | Epoch | Trạng thái backbone | LR | Mục đích |
|---|---|---|---|---|
| 1 — Warm-up | 1–3 | Đóng băng | 1e-3 | Lớp classifier mới (khởi tạo ngẫu nhiên) không phá hỏng backbone đã học tốt bằng gradient lớn |
| 2 — Fine-tune | 4–30 | Mở băng toàn bộ | 1e-4 + cosine decay | Tinh chỉnh toàn mạng |

### 6.3. Xử lý mất cân bằng lớp

Đây là vấn đề nghiêm trọng của bộ 12 bước: dữ liệu công khai chỉ phủ 6 bước chà xát, nên các
bước đó có thể nhiều **gấp hàng trăm lần** 5 bước mới.

Với `CrossEntropyLoss` thuần, mô hình đạt accuracy rất cao bằng cách **bỏ qua hoàn toàn** các
bước hiếm. Ba biện pháp đối phó:

1. **Class weights** — trọng số nghịch đảo tần suất trong hàm loss.
2. **WeightedRandomSampler** — mỗi batch có phân bố lớp gần đều.
3. **Chọn model theo macro-F1, không phải accuracy.**

Điểm 3 quan trọng nhất và được test kiểm chứng trực tiếp:

```
Mô hình "lười": 98 mẫu lớp 3, 2 mẫu lớp 9, luôn đoán lớp 3
   → accuracy = 0.980  (trông rất tốt)
   → macro-F1 = 0.495  (lộ ra ngay là mô hình vô dụng)
```

### 6.4. Về augmentation lật ngang — không dùng

Lật ngang (horizontal flip) là augmentation mặc định trong hầu hết pipeline thị giác, nhưng ở
bài toán này **phải tắt**: các bước 4, 6, 7, 8 có tính **trái/phải** rõ rệt. Lật ngang biến
"lòng bàn tay phải chà mu bàn tay trái" thành động tác ngược lại — tức là **sinh ra nhãn sai**.

Chỉ dùng jitter độ sáng/tương phản, giữ nguyên trục thời gian.

---

## 7. KẾ HOẠCH THU THẬP DỮ LIỆU CHO 5 BƯỚC CÒN THIẾU

Vì không có nguồn công khai, 5 bước sau **bắt buộc phải tự quay**: 1 (làm ướt), 2 (lấy xà phòng),
9 (tráng nước), 10 (lau khô), 11 (khóa vòi — có thể bổ sung từ PSKUS nhưng nên quay thêm cho
khớp bối cảnh).

### 7.1. Khối lượng đề xuất

| Hạng mục | Số lượng |
|---|---|
| Người tham gia | ≥ 15 (đa dạng giới tính, cỡ tay, màu da, có/không đeo nhẫn–đồng hồ) |
| Phiên rửa tay đầy đủ / người | 3–5 phiên trọn vẹn 12 bước |
| Tổng số phiên | 45–75 |
| Thời lượng mỗi phiên | 40–60 giây (theo chuẩn WHO) |
| Ước tính clip cho mỗi bước hiếm | ~500–800 clip 1 giây |

Quay **trọn phiên** thay vì quay rời từng bước, vì:
- Có luôn dữ liệu lớp 0 (khoảng chuyển giao) một cách tự nhiên.
- Có dữ liệu để đánh giá state machine đầu-cuối, không chỉ đánh giá bộ phân loại.

### 7.2. Protocol quay

- **Camera:** giữ nguyên vị trí top-down hiện tại. Ghi lại `roi.json` cho mỗi lần đặt máy.
- **Bắt buộc phải thấy trong khung hình:** vòi nước, bình xà phòng, hộp khăn giấy — đây chính là
  thông tin mà nhánh `scene` cần để phân biệt 5 bước mới. Nếu ROI cắt mất bình xà phòng, bước 2
  sẽ không bao giờ học được.
- **Biến thiên có chủ đích:** 2–3 điều kiện ánh sáng, có/không đeo trang sức, tay ướt/khô, tốc độ
  làm nhanh–chậm khác nhau.
- **Quay cả ca sai:** cố tình bỏ bước, làm sai thứ tự, làm quá nhanh. Cần thiết để kiểm thử phần
  chấm điểm tuân thủ — hiện chưa có dữ liệu nào loại này.

### 7.3. Gán nhãn

Dùng lại đúng định dạng `Handwashing_Dataset_Labels.xlsx` nhưng mở rộng `Label ID` từ `B1`–`B6`
thành `B1`–`B12`, hoặc đặt video vào `data_12steps/<class_idx>/`. Cả hai đường đều đã được
`prepare_data.py` hỗ trợ sẵn.

### 7.4. Chiến lược triển khai theo giai đoạn

Không nên chờ đủ dữ liệu 12 bước mới bắt đầu. Đề xuất 3 giai đoạn:

| GĐ | Dữ liệu | Chế độ | Kết quả sử dụng được |
|---|---|---|---|
| **1** | Dữ liệu hiện có + Kaggle sample | single-stream, 7 lớp có mặt | Xác nhận pipeline chạy đúng, đo lại baseline 6 bước **không rò rỉ** |
| **2** | + PSKUS | single/dual, 8 lớp | Thêm bước 11 và lớp 0 thật; mô hình khỏe hơn hẳn nhờ dữ liệu bệnh viện |
| **3** | + video tự quay | dual-stream, đủ 13 lớp | Hệ thống 12 bước hoàn chỉnh |

Ở GĐ 1–2, các lớp thiếu dữ liệu vẫn nằm trong đầu ra mô hình nhưng không bao giờ được dự đoán;
`prepare_data.py` và `train.py` đều in cảnh báo rõ ràng về việc này.

---

## 8. HƯỚNG DẪN CHẠY

```bash
# 0. Cài môi trường (trên máy Mac của dự án)
pip install torch torchvision opencv-python mediapipe pandas openpyxl tqdm numpy

# 1. Xem khảo sát dataset và tải nguồn tự động được
python src/download_public_data.py --list
python src/download_public_data.py --dataset kaggle_sample
python src/download_public_data.py --coverage

# 2. Tiền xử lý (chia theo VIDEO, xuất 2 luồng hand + scene)
python src/prepare_data.py
#    Chỉ hand crop (khi chưa cần nhánh scene):
python src/prepare_data.py --no-scene

# 3. Huấn luyện, kế thừa từ checkpoint 6 bước cũ
python src/train.py --legacy-checkpoint checkpoints/model_best.pth --epochs 30

# 4. Suy luận + chấm điểm tuân thủ
python src/predict.py                        # toàn bộ data_predict/
python src/predict.py --camera 0             # webcam thời gian thực

# 5. Kiểm thử logic (chạy được không cần torch/cv2)
python tests/test_logic.py
```

---

## 9. DANH MỤC TỆP

| Tệp | Trạng thái | Vai trò |
|---|---|---|
| [src/steps_config.py](src/steps_config.py) | **mới** | Taxonomy 12 bước, ánh xạ 6→12 và ánh xạ dataset công khai |
| [src/model.py](src/model.py) | sửa lớn | Dual-stream 13 lớp, cấy trọng số từ checkpoint 6 lớp |
| [src/dataset.py](src/dataset.py) | sửa lớn | Clip dataset 2 luồng, cửa sổ trượt, chuẩn hóa Kinetics |
| [src/prepare_data.py](src/prepare_data.py) | sửa lớn | Chia theo video, khai thác lớp Other, bám tay bền hơn |
| [src/train.py](src/train.py) | sửa lớn | Fine-tune 2 pha, cân bằng lớp, macro-F1, confusion matrix |
| [src/predict.py](src/predict.py) | sửa lớn | State machine 12 bước, chấm điểm tuân thủ |
| [src/download_public_data.py](src/download_public_data.py) | **mới** | Tải/convert dataset công khai, báo cáo độ phủ |
| [tests/test_logic.py](tests/test_logic.py) | **mới** | 90 test cho taxonomy, state machine, metrics |
| [src/select_roi.py](src/select_roi.py) | giữ nguyên | Chọn ROI thủ công |

---

## 10. TÌNH TRẠNG KIỂM THỬ

- ✅ 7/7 module biên dịch sạch (`py_compile`).
- ✅ 90/90 test logic pass — bao trùm taxonomy, ánh xạ nhãn, khai thác lớp Other, metrics mất
  cân bằng, state machine (đủ bước / thiếu bước / sai thứ tự / nhiễu thoáng qua / tự reset /
  bất biến theo fps).
- ⚠️ **Chưa chạy được huấn luyện thật.** Máy Windows hiện tại không có `torch`, `cv2`,
  `mediapipe` (dự án chạy trên Mac — code dùng thiết bị `mps`). Các phần cần chạy trên máy dự án
  để xác nhận: forward/backward của model dual-stream, tốc độ suy luận thực tế, và chất lượng
  crop của MediaPipe ở các bước có nước và bọt xà phòng.

---

## 11. NGUỒN THAM KHẢO

- WHO — *Hand Hygiene: Why, How and When* / poster *How to Handwash* (12 bước, 40–60 giây)
- [Hand-Washing Video Dataset Annotated According to the WHO's Hand-Washing Guidelines](https://zenodo.org/record/4537209) — PSKUS, CC BY-SA 4.0
- [METC Hand Washing Dataset](https://zenodo.org/record/5808789) — Riga Stradiņš University
- [edi-riga/handwash](https://github.com/edi-riga/handwash) — mã nguồn phân loại động tác rửa tay
- [Kaggle Hand Wash Dataset](https://www.kaggle.com/datasets/realtimear/hand-wash-dataset)
- [Real-time Action Recognition for Fine-Grained Actions and The Hand Wash Dataset](https://arxiv.org/abs/2210.07400) — arXiv 2210.07400
- [Fine-grained Hand Gesture Recognition in Multi-viewpoint Hand Hygiene](https://arxiv.org/abs/2109.02917) — MFH dataset, IEEE SMC 2021
- [Designing a Computer-Vision Application: Hand-Hygiene Assessment in an Open-Room Environment](https://pmc.ncbi.nlm.nih.gov/articles/PMC8472252/) — Class-23 dataset
- [Hand Hygiene Assessment via Joint Step Segmentation and Key Action Scorer](https://arxiv.org/abs/2209.12221) — arXiv 2209.12221
- [Hand Washing Gesture Recognition Using Synthetic Dataset](https://www.mdpi.com/2313-433X/11/7/208) — MDPI J. Imaging

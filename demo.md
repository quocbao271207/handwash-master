# TÓM TẮT LUỒNG THUẬT TOÁN HỆ THỐNG GIÁM SÁT VỆ SINH TAY

## LUỒNG THUẬT TOÁN CHÍNH (MAIN ALGORITHM)
1. **Nhận diện người:** Xác định các cá nhân trong khung hình.
2. **Nhận diện cổ tay:** Tính toán khoảng cách để gán nhãn hành vi "Tự chạm tay" (Self-touching) hoặc "Chạm bệnh nhân" (People-touching).
3. **Nhận diện rửa tay:** Kích hoạt mô hình phân loại khi có nhãn "Tự chạm tay".
4. **Cập nhật trạng thái:** Nếu hành động "Đang rửa tay" (Sanitizing) duy trì liên tục $\ge$ 3 giây ➔ Chuyển trạng thái từ "Chưa vô trùng" (Unsterile) sang "Đã vô trùng" (Sterile).
5. **Đối chiếu tiêu chuẩn WHO:** Kiểm tra 5 thời điểm vàng của Tổ chức Y tế Thế giới (WHO) để đánh giá nhân viên y tế có vi phạm quy tắc hay không.

---

## GIAI ĐOẠN 0: CHUẨN BỊ DỮ LIỆU HUẤN LUYỆN (DATASET)
- **Thu thập dữ liệu vùng tay:** Do nhân viên y tế di chuyển liên tục, hệ thống sử dụng `YOLO11n-pose` để trích xuất các điểm neo xương khớp (keypoints) của toàn cơ thể. Dựa vào tệp dán nhãn (label) về mốc thời gian bắt đầu/kết thúc rửa tay, hệ thống sẽ trích xuất các khung hình tập trung vào 2 điểm neo ở cổ tay.
- **Tiền xử lý:** Vì khung hình có thể xuất hiện nhiều bàn tay của cả nhân viên y tế và bệnh nhân, bước này cần bộ lọc để xác định chính xác bàn tay của nhân viên y tế.
- **Phân loại dữ liệu:** Tập dữ liệu sẽ được chia thành 2 loại hành vi chính: "Đang rửa tay" (Sanitizing) và "Chạm vào bệnh nhân" (People-touching).
- **Huấn luyện mô hình:** Sử dụng Mạng nơ-ron tích chập (CNN) để học và nhận diện chuỗi hình ảnh cổ tay trong 10 chu kỳ (epochs).

## GIAI ĐOẠN 1: THEO DÕI NHÂN VIÊN Y TẾ VÀ BỆNH NHÂN (TRACKING)
- **Mục tiêu:** Phân loại và theo dõi (tracking) chính xác đối tượng là nhân viên y tế hay bệnh nhân.
- **Phương pháp:**
  1. Sử dụng mô hình nhận diện tư thế `YOLO11n-pose` để vẽ các điểm neo xương khớp cho mọi cá nhân trong khung hình.
  2. Dựa trên đặc thù bệnh nhân trong phòng ICU thường nằm bất động trên giường, hệ thống sẽ khoanh vùng quan tâm (ROI) cố định quanh khu vực giường bệnh. Do đó, thuật toán theo dõi luân chuyển (tracking) sẽ tập trung chủ yếu vào việc bám sát nhân viên y tế.

## GIAI ĐOẠN 2: PHÂN TÍCH LOGIC KHÔNG GIAN CỔ TAY
- **Mục tiêu:** Phân loại hành vi thành "Tự chạm tay" (điều kiện tiên quyết để kích hoạt nhận diện rửa tay) và "Chạm bệnh nhân" (hành vi quyết định việc giữ hay thu hồi trạng thái vô trùng).
- **Phương pháp:**
  1. **Tự chạm tay:** Dựa vào keypoints của nhân viên y tế, tính toán khoảng cách không gian giữa cổ tay trái và cổ tay phải. Nếu khoảng cách này nhỏ hơn một ngưỡng định sẵn ➔ Gán nhãn "Tự chạm tay".
  2. **Chạm bệnh nhân:** Tính toán khoảng cách từ cổ tay của nhân viên y tế đến các keypoints của bệnh nhân. Nếu khoảng cách nhỏ hơn ngưỡng định sẵn ➔ Gán nhãn "Chạm bệnh nhân".
  3. **Xử lý che khuất (Occlusion):** Tính năng xử lý các trường hợp khuất tầm nhìn sẽ được nghiên cứu và bổ sung khi thu thập đủ dữ liệu thực tế.

## GIAI ĐOẠN 3 & 4: NHẬN DIỆN RỬA TAY VÀ QUẢN LÝ TRẠNG THÁI
- **Mục tiêu:** Xác định xem nhân viên y tế có thực hiện thao tác chà xát tay hay không (ưu tiên xác định hành vi rửa tay thay vì ép buộc đánh giá độ chính xác của toàn bộ 6 bước quy chuẩn).
- **Phương pháp:** 
  - Khi cổ tay được gán nhãn "Tự chạm tay", mô hình CNN sẽ được kích hoạt để phân tích chuỗi khung hình.
  - Nếu mô hình liên tục trả về kết quả "Đang rửa tay" đủ thời lượng (ví dụ: 3 giây), hệ thống sẽ cập nhật trạng thái của nhân viên y tế từ "Chưa vô trùng" sang "Đã vô trùng".

## GIAI ĐOẠN 5: ĐỐI CHIẾU 5 THỜI ĐIỂM VÀNG CỦA WHO
- **Mục tiêu:** Kết hợp lịch sử trạng thái vô trùng và các sự kiện chạm bệnh nhân để đối chiếu với 5 thời điểm bắt buộc vệ sinh tay của WHO.
- **Phương pháp:** Hệ thống sẽ giám sát các mốc thời gian tiếp xúc và đối chiếu xem nhân viên y tế có tuân thủ đúng quy định rửa tay trước và sau khi tiếp xúc với bệnh nhân (hoặc môi trường xung quanh) hay không.

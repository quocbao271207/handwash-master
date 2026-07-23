import os
import pandas as pd
import numpy as np
import torch
from tqdm import tqdm
import sys

# Ensure src is in path to import preprocess_hybrid
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from preprocess_hybrid import HybridFeatureExtractor

def extract_features_data02():
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Sử dụng thiết bị trích xuất: {device}")
    
    extractor = HybridFeatureExtractor(device)
    excel_path = "Data_02/Handwashing_Dataset_Labels.xlsx"
    
    # Tạo thư mục gốc
    out_base = "Data_02_features"
    os.makedirs(out_base, exist_ok=True)
    
    # Process Train (Sheet 0) and Test (Sheet 1)
    splits = [
        {"sheet": 0, "dir": "Data_02/train", "out": "train"},
        {"sheet": 1, "dir": "Data_02/test", "out": "test"}
    ]
    
    for split in splits:
        print(f"\n🚀 Đang xử lý tập {split['out'].upper()}...")
        out_split_dir = os.path.join(out_base, split["out"])
        
        # Create class folders 0-5
        for i in range(6):
            os.makedirs(os.path.join(out_split_dir, str(i)), exist_ok=True)
            
        df = pd.read_excel(excel_path, sheet_name=split["sheet"])
        # Nhóm theo Video ID để chỉ extract video 1 lần
        grouped = df.groupby("Video ID")
        
        for video_id, group in grouped:
            video_path = os.path.join(split["dir"], f"{video_id}.mov")
            # Fallback nếu viết hoa
            if not os.path.exists(video_path):
                video_path = os.path.join(split["dir"], f"{video_id}.MOV")
            if not os.path.exists(video_path):
                # Fallback .mp4
                video_path = os.path.join(split["dir"], f"{video_id}.mp4")
                
            if not os.path.exists(video_path):
                print(f"⚠️ Không tìm thấy file video: {video_path}")
                continue
                
            print(f"Đang phân tích video nguyên bản: {video_path}")
            # Trích xuất toàn bộ frame của video
            full_img_feat, full_skel_feat = extractor.extract_video(video_path)
            
            # Cắt theo frame của từng bước
            for index, row in group.iterrows():
                label_id = row['Label ID'] # B1, B2...
                if not isinstance(label_id, str) or not label_id.startswith('B'):
                    continue
                
                class_idx = int(label_id[1]) - 1 # B1 -> 0, B2 -> 1, ... B6 -> 5
                
                start_frame = int(row['Start Frame'])
                end_frame = int(row['End Frame'])
                
                # Cắt (slicing)
                # Đảm bảo không vượt quá độ dài array
                end_frame = min(end_frame, full_img_feat.shape[0])
                start_frame = min(start_frame, end_frame - 1)
                
                img_slice = full_img_feat[start_frame:end_frame]
                skel_slice = full_skel_feat[start_frame:end_frame]
                
                if len(img_slice) > 0:
                    out_filename = f"{video_id}_{label_id}.npy"
                    out_filepath = os.path.join(out_split_dir, str(class_idx), out_filename)
                    np.save(out_filepath, {'img_feat': img_slice, 'skel_feat': skel_slice})
            
            print(f"✅ Đã xử lý xong cắt đoạn cho {video_id}.")
            
if __name__ == "__main__":
    extract_features_data02()

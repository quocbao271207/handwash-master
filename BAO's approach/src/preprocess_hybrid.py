import os
import glob
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models
import mediapipe as mp
from tqdm import tqdm
import torchvision.transforms as T

class HybridFeatureExtractor:
    def __init__(self, device):
        self.device = device
        # 1. Khởi tạo mạng CNN trích xuất ảnh (MobileNetV3 cho tốc độ)
        # Sử dụng pretrained weights để làm backbone feature extractor
        mobilenet = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        # Bỏ đi classifier cuối cùng, chỉ lấy các layers trích xuất đặc trưng
        self.img_encoder = nn.Sequential(*list(mobilenet.children())[:-1]).to(device)
        self.img_encoder.eval()
        
        # 2. Khởi tạo MediaPipe cho Skeleton (Tasks API)
        if not os.path.exists('hand_landmarker.task'):
            os.system('curl -so hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task')
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
        self.detector = vision.HandLandmarker.create_from_options(options)
            
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def extract_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        img_features = []
        skel_features = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            # --- Xử lý Skeleton ---
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            results = self.detector.detect(mp_image)
            skel_feat = np.zeros((2, 21, 3), dtype=np.float32)
            if results.hand_landmarks and results.handedness:
                for hand_landmarks, handedness in zip(results.hand_landmarks, results.handedness):
                    label = handedness[0].category_name
                    idx = 0 if label == 'Left' else 1
                    wrist_pt = np.array([hand_landmarks[0].x, hand_landmarks[0].y, hand_landmarks[0].z])
                    for i in range(21):
                        lm = hand_landmarks[i]
                        pt = np.array([lm.x, lm.y, lm.z])
                        skel_feat[idx, i] = pt - wrist_pt # chuẩn hoá theo cổ tay
            skel_features.append(skel_feat.flatten())
            
            # --- Xử lý Hình Ảnh ---
            img_tensor = self.transform(frame_rgb).unsqueeze(0).to(self.device)
            with torch.no_grad():
                feat = self.img_encoder(img_tensor) # [1, 576, 1, 1]
                img_features.append(feat.cpu().numpy().flatten())
                
        cap.release()
        return np.array(img_features), np.array(skel_features)

def preprocess_dataset(raw_dir="data/kaggle-dataset-6classes", out_dir="data/processed_features", max_videos_per_class=None):
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Đang sử dụng thiết bị trích xuất: {device}")
    
    extractor = HybridFeatureExtractor(device)
    
    classes = sorted([d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d)) and not d.startswith('.')])
    
    for c_idx, c_name in enumerate(classes):
        class_out_dir = os.path.join(out_dir, c_name)
        os.makedirs(class_out_dir, exist_ok=True)
        
        video_files = glob.glob(os.path.join(raw_dir, c_name, "*.mp4"))
        if max_videos_per_class:
            video_files = video_files[:max_videos_per_class]
            
        print(f"🔄 Đang xử lý class {c_name} ({len(video_files)} videos)...")
        for video_path in tqdm(video_files):
            basename = os.path.basename(video_path)
            out_file = os.path.join(class_out_dir, basename.replace('.mp4', '.npy'))
            
            if os.path.exists(out_file):
                continue
                
            img_f, skel_f = extractor.extract_video(video_path)
            if len(img_f) > 0:
                np.save(out_file, {'img_feat': img_f, 'skel_feat': skel_f})

if __name__ == "__main__":
    import argparse
    import torch.nn as nn # Bổ sung cho HybridFeatureExtractor
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", action="store_true", help="Chỉ xử lý 1 số video nhỏ để test")
    args = parser.parse_args()
    
    if args.trial:
        print("⚠️ Trial Mode: Đang chạy tạo data mẫu (Fake data) để pass qua bài test mà không tốn thời gian MediaPipe...")
        out_dir = "data/processed_features"
        classes = ["0", "1", "2"]
        subjects = ["G_01", "G_02", "G_03"]
        for c in classes:
            c_dir = os.path.join(out_dir, c)
            os.makedirs(c_dir, exist_ok=True)
            for s in subjects:
                # Tạo array random kích thước 100 frames
                fake_img = np.random.randn(100, 576).astype(np.float32)
                fake_skel = np.random.randn(100, 126).astype(np.float32)
                np.save(os.path.join(c_dir, f"HandWash_001_A_11_{s}.npy"), {'img_feat': fake_img, 'skel_feat': fake_skel})
        print("Đã tạo xong fake data!")
    else:
        preprocess_dataset()
